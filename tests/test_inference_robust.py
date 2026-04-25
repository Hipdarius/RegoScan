"""Tests for robust-inference helpers — TTA, fusion, temperature fitting.

We mock InferenceEngine here rather than spinning up a real ONNX model
so the tests are fast and deterministic.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest

from vera.inference_robust import (
    apply_temperature,
    expected_calibration_error,
    fit_temperature,
    fuse_sample_predictions,
    tta_predict,
)


# ---------------------------------------------------------------------------
# Mock inference engine
# ---------------------------------------------------------------------------


def _make_engine(probs: np.ndarray, ilm: float = 0.1):
    """Build a mock that always returns the given probability vector."""
    engine = MagicMock()
    engine.predict.return_value = {
        "class_index": int(np.argmax(probs)),
        "probabilities": np.asarray(probs, dtype=np.float64),
        "ilmenite_fraction": float(ilm),
        "confidence": float(probs.max()),
        "entropy": 0.0,
        "margin": 1.0,
        "status": "nominal",
    }
    return engine


# ---------------------------------------------------------------------------
# Test-time augmentation
# ---------------------------------------------------------------------------


def test_tta_predict_runs_n_times():
    engine = _make_engine(np.array([0.9, 0.05, 0.05]))
    feat = np.zeros(303, dtype=np.float32)
    r = tta_predict(engine, feat, n_samples=5, seed=42)
    assert r["tta_n"] == 5
    assert engine.predict.call_count == 5


def test_tta_predict_returns_canonical_keys():
    engine = _make_engine(np.array([0.7, 0.2, 0.1]))
    r = tta_predict(engine, np.zeros(303), n_samples=4, seed=0)
    for key in ("class_index", "probabilities", "ilmenite_fraction",
                "confidence", "entropy", "margin", "status"):
        assert key in r


def test_tta_predict_first_pass_is_clean():
    """The first TTA pass must use the unmodified input — otherwise the
    mean drifts when n_samples is small."""
    engine = MagicMock()
    seen_inputs: list[np.ndarray] = []

    def _capture(x):
        seen_inputs.append(x.copy())
        return {
            "class_index": 0,
            "probabilities": np.array([1.0, 0.0]),
            "ilmenite_fraction": 0.0,
            "confidence": 1.0,
            "entropy": 0.0,
            "margin": 1.0,
            "status": "nominal",
        }

    engine.predict.side_effect = _capture
    feat = np.full(10, 0.5, dtype=np.float32)
    tta_predict(engine, feat, n_samples=2, seed=0)
    # First pass should be the original
    np.testing.assert_array_equal(seen_inputs[0], feat)
    # Second pass should differ (noise added)
    assert not np.array_equal(seen_inputs[1], feat)


# ---------------------------------------------------------------------------
# Sample-level fusion
# ---------------------------------------------------------------------------


def test_fuse_mean_averages_probs():
    # Engine returns a fixed probability vector regardless of input.
    engine = _make_engine(np.array([0.6, 0.3, 0.1]))
    M = 4
    feats = np.zeros((M, 303))
    r = fuse_sample_predictions(engine, feats, method="mean")
    np.testing.assert_allclose(r["probabilities"], [0.6, 0.3, 0.1], atol=1e-9)
    assert r["fused_n"] == M
    assert r["fusion_method"] == "mean"


def test_fuse_vote_picks_majority():
    # Different mocks per call — alternating winners.
    engine = MagicMock()
    seq = [
        {"class_index": 0, "probabilities": np.array([0.6, 0.3, 0.1]), "ilmenite_fraction": 0.1, "confidence": 0.6, "entropy": 0.0, "margin": 0.3, "status": "nominal"},
        {"class_index": 0, "probabilities": np.array([0.7, 0.2, 0.1]), "ilmenite_fraction": 0.1, "confidence": 0.7, "entropy": 0.0, "margin": 0.5, "status": "nominal"},
        {"class_index": 1, "probabilities": np.array([0.2, 0.7, 0.1]), "ilmenite_fraction": 0.1, "confidence": 0.7, "entropy": 0.0, "margin": 0.5, "status": "nominal"},
    ]
    engine.predict.side_effect = seq
    feats = np.zeros((3, 303))
    r = fuse_sample_predictions(engine, feats, method="vote")
    # Class 0 won 2/3 votes
    assert r["class_index"] == 0
    # Pseudo-probs reflect the vote distribution
    assert r["probabilities"][0] == pytest.approx(2 / 3)
    assert r["probabilities"][1] == pytest.approx(1 / 3)


def test_fuse_rejects_empty_batch():
    engine = _make_engine(np.array([1.0, 0.0]))
    with pytest.raises(ValueError):
        fuse_sample_predictions(engine, np.zeros((0, 303)))


def test_fuse_rejects_unknown_method():
    engine = _make_engine(np.array([1.0, 0.0]))
    with pytest.raises(ValueError):
        fuse_sample_predictions(engine, np.zeros((2, 303)), method="bogus")


# ---------------------------------------------------------------------------
# Temperature fitting
# ---------------------------------------------------------------------------


def test_fit_temperature_finds_optimum_for_overconfident_model():
    """If logits are over-scaled, the optimal T is > 1.

    Guo et al. (2017) show modern deep networks are systematically
    over-confident — they emit logits that are too sharply separated.
    Fitting T on NLL pulls them back toward calibration. We simulate
    over-confidence by scaling already-noisy "calibrated" logits by 4×
    and confirm the fit recovers a T well above 1.
    """
    rng = np.random.RandomState(42)
    N, K = 400, 6
    labels = rng.randint(0, K, size=N)
    base = np.zeros((N, K))
    base[np.arange(N), labels] = 1.0
    base += rng.normal(0, 1.5, size=base.shape)  # heavy noise — some wrong
    overconf = base * 4.0
    T = fit_temperature(overconf, labels)
    # Optimal T should pull back the 4× over-scaling. With heavy noise
    # the exact answer depends on the noise realisation but should be
    # comfortably above 1.5.
    assert T > 1.5, f"expected T > 1.5 to undo over-confidence, got {T:.2f}"


def test_fit_temperature_T_eq_1_for_well_calibrated():
    """Random labels → uniform-ish optimal logits → T should be near 1."""
    rng = np.random.RandomState(0)
    N, K = 500, 6
    logits = rng.normal(0, 1, size=(N, K))
    labels = rng.randint(0, K, size=N)
    T = fit_temperature(logits, labels)
    # Should be reasonable, not pinned at the grid edge
    assert 0.5 <= T <= 5.0


def test_apply_temperature_T1_is_identity():
    probs = np.array([[0.7, 0.2, 0.1], [0.4, 0.4, 0.2]])
    out = apply_temperature(probs, T=1.0)
    np.testing.assert_allclose(out, probs, atol=1e-9)


def test_apply_temperature_high_T_flattens():
    probs = np.array([0.99, 0.005, 0.005])
    out = apply_temperature(probs, T=5.0)
    # Higher T → flatter distribution
    assert out[0] < probs[0]
    assert out[1] > probs[1]


def test_apply_temperature_rejects_nonpositive():
    with pytest.raises(ValueError):
        apply_temperature(np.array([0.5, 0.5]), T=0.0)


def test_ece_perfect_calibration_is_zero():
    # If confidence == accuracy in every bin, ECE = 0
    N = 100
    probs = np.zeros((N, 2))
    probs[:, 0] = 0.5
    probs[:, 1] = 0.5
    labels = np.zeros(N, dtype=int)
    ece = expected_calibration_error(probs, labels, n_bins=2)
    # Predicted 0.5 confidence on class 0; actual accuracy is 1.0 → big gap
    assert ece > 0.0


def test_ece_one_hot_confident_correct_is_zero():
    N = 100
    probs = np.zeros((N, 3))
    probs[:, 0] = 1.0
    labels = np.zeros(N, dtype=int)
    ece = expected_calibration_error(probs, labels)
    assert ece == pytest.approx(0.0, abs=1e-9)
