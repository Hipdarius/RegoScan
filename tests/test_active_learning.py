"""Tests for the pool-based active-learning module."""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pytest

from vera.active_learning import (
    AcquisitionScore,
    acquisition_score,
    disagreement_rate,
    rank_pool,
)


# ---------------------------------------------------------------------------
# Mocks
# ---------------------------------------------------------------------------


def _engine_returning(*, class_idx: int, probs: list[float], entropy=None,
                     margin=None, confidence=None, status="nominal"):
    """Build an InferenceEngine mock with controllable predict() output."""
    p = np.asarray(probs, dtype=np.float64)
    K = p.size

    if entropy is None:
        # Recompute entropy in nats so we get a realistic value
        clipped = np.clip(p, 1e-12, 1.0)
        entropy = float(-np.sum(clipped * np.log(clipped)))
    if margin is None:
        s = np.sort(p)[::-1]
        margin = float(s[0] - s[1])
    if confidence is None:
        confidence = float(np.max(p))

    engine = MagicMock()
    engine.predict.return_value = {
        "class_index": int(class_idx),
        "probabilities": p,
        "ilmenite_fraction": 0.1,
        "confidence": confidence,
        "entropy": entropy,
        "margin": margin,
        "status": status,
    }
    return engine


def _sam_returning(class_idx: int):
    sam = MagicMock()
    sam.predict.return_value = {"class_index": int(class_idx)}
    return sam


# ---------------------------------------------------------------------------
# acquisition_score
# ---------------------------------------------------------------------------


def test_score_confident_agreement_is_low():
    """If CNN and SAM agree confidently, the score should be tiny."""
    engine = _engine_returning(
        class_idx=2, probs=[0.005, 0.005, 0.97, 0.005, 0.005, 0.01],
    )
    sam = _sam_returning(2)
    s = acquisition_score(0, np.zeros(321), np.zeros(288), engine, sam)
    assert s.composite < 0.2
    assert not s.disagreement


def test_score_uniform_distribution_is_high():
    """A maximally uncertain CNN scores high on entropy."""
    engine = _engine_returning(
        class_idx=0, probs=[1 / 6] * 6,
    )
    sam = _sam_returning(0)
    s = acquisition_score(0, np.zeros(321), np.zeros(288), engine, sam)
    # Entropy is ln(6)/ln(6) = 1, weight 0.4 → at least 0.4
    assert s.composite >= 0.4


def test_score_disagreement_dominates_when_models_differ():
    """SAM picks class 0, CNN picks class 1, both confidently — must
    flag disagreement and lift the composite."""
    engine = _engine_returning(
        class_idx=1, probs=[0.05, 0.92, 0.01, 0.005, 0.005, 0.01],
    )
    sam = _sam_returning(0)
    s = acquisition_score(0, np.zeros(321), np.zeros(288), engine, sam)
    assert s.disagreement
    # Disagreement adds 0.3 to composite even with low entropy/margin
    assert s.composite >= 0.30


def test_score_records_all_diagnostic_fields():
    engine = _engine_returning(class_idx=3, probs=[0.1] * 6, confidence=0.166)
    sam = _sam_returning(3)
    s = acquisition_score(7, np.zeros(321), np.zeros(288), engine, sam)
    assert isinstance(s, AcquisitionScore)
    assert s.sample_idx == 7
    assert s.cnn_class == 3
    assert s.sam_class == 3
    assert 0.0 <= s.entropy_norm <= 1.0
    assert 0.0 <= s.margin <= 1.0
    assert 0.0 <= s.composite <= 1.0


def test_score_custom_weights_change_composite():
    engine = _engine_returning(class_idx=0, probs=[1 / 6] * 6)
    sam = _sam_returning(0)
    base = acquisition_score(0, np.zeros(321), np.zeros(288), engine, sam,
                             weights=(1.0, 0.0, 0.0))
    swap = acquisition_score(0, np.zeros(321), np.zeros(288), engine, sam,
                             weights=(0.0, 1.0, 0.0))
    # Different weight emphasis → different composite
    assert base.composite != swap.composite


# ---------------------------------------------------------------------------
# rank_pool
# ---------------------------------------------------------------------------


def test_rank_pool_orders_descending():
    """Build a pool with one clearly-informative and one clearly-not
    sample; verify the informative one ranks first."""

    # First sample: confident agreement (low score)
    # Second sample: full disagreement + uniform (high score)
    call_log = {"i": 0}

    def cnn_predict(features):
        idx = call_log["i"]
        call_log["i"] += 1
        if idx % 2 == 0:
            # Even sample idx → confident agreement
            return {
                "class_index": 0,
                "probabilities": np.array([0.97, 0.005, 0.005, 0.005, 0.005, 0.01]),
                "ilmenite_fraction": 0.1,
                "confidence": 0.97,
                "entropy": 0.15,
                "margin": 0.96,
                "status": "nominal",
            }
        return {
            "class_index": 1,
            "probabilities": np.full(6, 1 / 6),
            "ilmenite_fraction": 0.1,
            "confidence": 1 / 6,
            "entropy": float(np.log(6)),
            "margin": 0.0,
            "status": "likely_ood",
        }

    sam_call = {"i": 0}

    def sam_predict(spectrum):
        idx = sam_call["i"]
        sam_call["i"] += 1
        # Even idx → CNN class (agree); odd idx → different class (disagree)
        return {"class_index": 0 if idx % 2 == 0 else 5}

    engine = MagicMock()
    engine.predict.side_effect = cnn_predict
    sam = MagicMock()
    sam.predict.side_effect = sam_predict

    pool_features = np.zeros((4, 321))
    pool_spectra = np.zeros((4, 288))
    ranked = rank_pool(pool_features, pool_spectra, engine, sam)

    # Top of the list should be the high-uncertainty disagreement samples (odd idx)
    assert ranked[0].sample_idx in (1, 3)
    assert ranked[0].composite > ranked[-1].composite
    # All four samples returned, sorted desc
    assert len(ranked) == 4


def test_rank_pool_top_k_truncates():
    engine = _engine_returning(class_idx=0, probs=[1.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    sam = _sam_returning(0)
    pool = np.zeros((10, 321))
    spectra = np.zeros((10, 288))
    out = rank_pool(pool, spectra, engine, sam, top_k=3)
    assert len(out) == 3


def test_rank_pool_rejects_mismatched_pool_lengths():
    engine = _engine_returning(class_idx=0, probs=[1.0, 0.0])
    sam = _sam_returning(0)
    with pytest.raises(ValueError):
        rank_pool(np.zeros((5, 321)), np.zeros((4, 288)), engine, sam)


def test_disagreement_rate():
    scores = [
        AcquisitionScore(0, 0, 0, 0.9, 0.1, 0.8, False, 0.1, "nominal"),
        AcquisitionScore(1, 0, 1, 0.9, 0.1, 0.8, True, 0.5, "borderline"),
        AcquisitionScore(2, 0, 1, 0.9, 0.1, 0.8, True, 0.5, "borderline"),
    ]
    assert disagreement_rate(scores) == pytest.approx(2 / 3)
    assert disagreement_rate([]) == 0.0
