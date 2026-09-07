"""Robust-inference helpers — TTA, sample fusion, calibrated probabilities.

These wrap :class:`vera.inference.InferenceEngine` with three orthogonal
techniques that each independently improve real-world performance:

1. **Test-time augmentation (TTA)** — predict on N noisy copies of the
   input and average the softmax outputs. Cuts variance on borderline
   cases without retraining.

2. **Sample-level fusion** — when the probe takes M measurements per
   sample, average their softmax outputs into a single prediction.
   Aligns inference with how the hardware actually scans.

3. **Temperature-scaled softmax** — fit a single temperature ``T`` on a
   held-out validation set so that predicted confidence matches actual
   accuracy. Modern deep nets are systematically over-confident; T > 1
   flattens the distribution to match reality (Guo et al. 2017).

All three are post-hoc — no retraining required, no architectural
changes. They operate on the existing ONNX graph via the standard
``InferenceEngine`` interface.

References
----------
Guo, Pleiss, Sun, Weinberger (2017) "On calibration of modern neural
networks", ICML 2017.

Lakshminarayanan, Pritzel, Blundell (2017) "Simple and scalable
predictive uncertainty estimation using deep ensembles", NeurIPS 2017.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from .inference import InferenceEngine
from .uncertainty import classify_uncertainty

# ---------------------------------------------------------------------------
# Test-time augmentation
# ---------------------------------------------------------------------------


# Default sigma was tuned against the synth-data noise floor — too
# high and TTA averages over a broader posterior than the model
# actually sees on real samples; too low and the augmentation is a
# no-op. Real-sample tuning is the next milestone.
def tta_predict(
    engine: InferenceEngine,
    features: np.ndarray,
    *,
    n_samples: int = 8,
    noise_sigma: float = 0.005,
    seed: int | None = None,
) -> dict[str, Any]:
    """Average softmax over N noisy copies of the input.

    The noise level is calibrated to be small relative to typical
    measurement noise — large enough to break the model's overconfidence
    on borderline cases, small enough not to change the actual class.

    Parameters
    ----------
    engine
        Loaded inference engine.
    features
        Single feature vector, shape ``(K,)``.
    n_samples
        Number of TTA passes. 8 is a good default — diminishing returns
        beyond ~16.
    noise_sigma
        Per-channel Gaussian noise added before each forward pass.
    seed
        RNG seed for reproducibility.

    Returns
    -------
    Same shape as :meth:`InferenceEngine.predict` but with averaged
    probabilities and an extra ``tta_n`` field.
    """
    rng = np.random.default_rng(seed)
    feat = np.asarray(features, dtype=np.float32)
    probs_acc = np.zeros(0, dtype=np.float64)
    ilm_acc = 0.0
    for i in range(n_samples):
        noise = rng.normal(0.0, noise_sigma, size=feat.shape).astype(np.float32)
        # Add the original (no noise) on the first pass so we don't drift
        # the mean if n_samples is small.
        sample = feat if i == 0 else np.clip(feat + noise, 0.0, 1.5)
        r = engine.predict(sample)
        if probs_acc.size == 0:
            probs_acc = np.zeros_like(r["probabilities"], dtype=np.float64)
        probs_acc += r["probabilities"]
        ilm_acc += r["ilmenite_fraction"]

    probs_avg = probs_acc / n_samples
    ilm_avg = ilm_acc / n_samples
    cls_idx = int(np.argmax(probs_avg))
    u = classify_uncertainty(probs_avg)
    return {
        "class_index": cls_idx,
        "probabilities": probs_avg,
        "ilmenite_fraction": float(np.clip(ilm_avg, 0.0, 1.0)),
        "confidence": u.confidence,
        "entropy": u.entropy,
        "margin": u.margin,
        "status": u.status,
        "tta_n": int(n_samples),
    }


# ---------------------------------------------------------------------------
# Sample-level fusion (multiple measurements → one prediction)
# ---------------------------------------------------------------------------


def fuse_sample_predictions(
    engine: InferenceEngine,
    feature_matrix: np.ndarray,
    *,
    method: str = "mean",
) -> dict[str, Any]:
    """Aggregate predictions across multiple measurements of one sample.

    The hardware takes ``measurements_per_sample`` shots per physical
    sample — they share the same ground-truth class but each has
    independent measurement noise. Averaging in probability space
    (rather than voting on argmax) is the optimal aggregation under
    independent Gaussian noise.

    Parameters
    ----------
    feature_matrix
        Stack of feature vectors. Shape: ``(M, K)``.
    method
        ``"mean"`` (default) — average softmax across measurements.
        ``"vote"`` — majority vote on argmax. Use when measurements are
        very heterogeneous (different illumination angles).

    Returns
    -------
    Single prediction dict in the canonical schema.
    """
    if feature_matrix.ndim != 2:
        raise ValueError(
            f"feature_matrix must be 2-D, got {feature_matrix.shape}"
        )
    M = feature_matrix.shape[0]
    if M == 0:
        raise ValueError("need at least one measurement")

    if method == "mean":
        probs_acc = None
        ilm_acc = 0.0
        for x in feature_matrix:
            r = engine.predict(x)
            probs_acc = (
                r["probabilities"] if probs_acc is None
                else probs_acc + r["probabilities"]
            )
            ilm_acc += r["ilmenite_fraction"]
        probs_avg = probs_acc / M
        ilm_avg = ilm_acc / M
    elif method == "vote":
        votes = np.zeros(0, dtype=np.int64)
        ilm_acc = 0.0
        for x in feature_matrix:
            r = engine.predict(x)
            if votes.size == 0:
                votes = np.zeros(r["probabilities"].size, dtype=np.int64)
            votes[int(np.argmax(r["probabilities"]))] += 1
            ilm_acc += r["ilmenite_fraction"]
        probs_avg = votes / float(M)
        ilm_avg = ilm_acc / M
    else:
        raise ValueError(f"unknown fusion method: {method!r}")

    cls_idx = int(np.argmax(probs_avg))
    u = classify_uncertainty(probs_avg)
    return {
        "class_index": cls_idx,
        "probabilities": probs_avg,
        "ilmenite_fraction": float(np.clip(ilm_avg, 0.0, 1.0)),
        "confidence": u.confidence,
        "entropy": u.entropy,
        "margin": u.margin,
        "status": u.status,
        "fused_n": int(M),
        "fusion_method": method,
    }


# ---------------------------------------------------------------------------
# Temperature scaling: fit T on validation set
# ---------------------------------------------------------------------------


def fit_temperature(
    logits: np.ndarray,
    labels: np.ndarray,
    *,
    grid: np.ndarray | None = None,
) -> float:
    """Find the temperature T that minimizes NLL on a validation set.

    Uses a 1-D grid search rather than gradient descent — the loss is
    convex in T, the grid is small, and this avoids dragging in
    autograd. Returns the optimum T (typical range: 1.0 to 3.0).

    Parameters
    ----------
    logits
        Raw network outputs (pre-softmax). Shape: ``(N, K)``.
    labels
        Integer class indices. Shape: ``(N,)``.
    grid
        Custom temperature grid. Default is 100 points from 0.5 to 5.0.
    """
    logits = np.asarray(logits, dtype=np.float64)
    labels = np.asarray(labels, dtype=np.int64)
    if grid is None:
        grid = np.linspace(0.5, 5.0, 100)

    best_T = 1.0
    best_nll = float("inf")
    N = labels.size
    for T in grid:
        z = logits / T
        z = z - z.max(axis=-1, keepdims=True)
        e = np.exp(z)
        p = e / e.sum(axis=-1, keepdims=True)
        # Negative log-likelihood (clip for stability)
        p_correct = np.clip(p[np.arange(N), labels], 1e-12, 1.0)
        nll = -float(np.mean(np.log(p_correct)))
        if nll < best_nll:
            best_nll = nll
            best_T = float(T)
    return best_T


def expected_calibration_error(
    probs: np.ndarray,
    labels: np.ndarray,
    *,
    n_bins: int = 15,
) -> float:
    """ECE: weighted average gap between predicted confidence and accuracy.

    Bins predictions by their max-softmax confidence and compares the
    mean confidence in each bin to the actual accuracy in that bin.
    Returns 0 for perfectly calibrated, up to 1.0 for maximally
    miscalibrated.
    """
    probs = np.asarray(probs, dtype=np.float64)
    labels = np.asarray(labels, dtype=np.int64)
    confidences = probs.max(axis=-1)
    predictions = np.argmax(probs, axis=-1)
    accuracies = (predictions == labels).astype(np.float64)

    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    N = labels.size
    for lo, hi in zip(bin_edges[:-1], bin_edges[1:]):
        in_bin = (confidences > lo) & (confidences <= hi)
        n_bin = int(in_bin.sum())
        if n_bin == 0:
            continue
        avg_conf = float(confidences[in_bin].mean())
        avg_acc = float(accuracies[in_bin].mean())
        ece += (n_bin / N) * abs(avg_conf - avg_acc)
    return float(ece)


# ---------------------------------------------------------------------------
# Calibration persistence (write to meta.json)
# ---------------------------------------------------------------------------


def save_temperature(run_dir: Path, T: float, *, ece_before: float, ece_after: float) -> None:
    """Persist the fitted temperature alongside the model so that
    :func:`apply_temperature` can be enabled at inference."""
    meta_path = Path(run_dir) / "meta.json"
    meta = json.loads(meta_path.read_text())
    meta["temperature"] = float(T)
    meta["ece_before"] = float(ece_before)
    meta["ece_after"] = float(ece_after)
    meta_path.write_text(json.dumps(meta, indent=2))


def apply_temperature(probs: np.ndarray, T: float) -> np.ndarray:
    """Re-scale already-computed probabilities to a new temperature.

    Going through logits = log(probs) is correct because softmax is
    invariant to additive shifts. Useful when you only have ONNX
    softmax output rather than raw logits.
    """
    if T <= 0:
        raise ValueError(f"T must be positive, got {T}")
    if abs(T - 1.0) < 1e-9:
        return np.asarray(probs)
    logits = np.log(np.clip(probs, 1e-12, 1.0))
    z = logits / T
    z = z - z.max(axis=-1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=-1, keepdims=True)


__all__ = [
    "apply_temperature",
    "expected_calibration_error",
    "fit_temperature",
    "fuse_sample_predictions",
    "save_temperature",
    "tta_predict",
]
