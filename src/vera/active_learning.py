"""Pool-based active learning — rank unlabelled samples for annotation.

When real samples start arriving, we won't be able to label everything.
Active learning ranks an unlabelled pool by *how much the model would
learn* if a human labelled it, so the human spends time on the
informative cases and skips the obvious ones.

Three orthogonal acquisition signals, combined into a single composite
score in ``[0, 1]``:

1. **Predictive entropy.** ``H(p)`` from the CNN softmax. High entropy
   means the model is hedging across many classes — labelling will
   resolve the ambiguity. Normalised by ``log(K)`` so it lies in
   ``[0, 1]``.

2. **Top-k margin.** ``p_top1 - p_top2``. A small margin (close to 0)
   means the model is torn between two specific classes; this is
   distinct from a generally diffuse distribution. We invert the
   raw margin so "more informative" → larger score.

3. **SAM ↔ CNN disagreement.** When the classical baseline
   (:class:`vera.sam.SAMClassifier`) and the CNN pick different
   classes, the sample is exercising features that distinguish the
   two methods — almost certainly informative. Boolean signal.

Composite weights default to ``(0.4, 0.3, 0.3)`` so no single signal
dominates. Tune via :func:`acquisition_score(weights=...)`.

Usage
-----
::

    from vera.active_learning import rank_pool
    from vera.inference import InferenceEngine
    from vera.sam import build_classifier_from_endmembers

    engine = InferenceEngine("runs/cnn_v2/model.onnx")
    sam = build_classifier_from_endmembers(em)

    # pool_features: (N, 321), pool_spectra: (N, 288)
    top10 = rank_pool(pool_features, pool_spectra, engine, sam, top_k=10)

    for s in top10:
        print(f"sample {s.sample_idx}: {s.composite:.3f}  "
              f"{'DISAGREE' if s.disagreement else 'agree'}  "
              f"H={s.entropy_norm:.2f}  margin={s.margin:.2f}")
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# ---------------------------------------------------------------------------
# Acquisition score
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AcquisitionScore:
    """Per-sample acquisition score with full diagnostic breakdown."""

    sample_idx: int
    cnn_class: int
    sam_class: int
    confidence: float
    entropy_norm: float          # ∈ [0, 1] — entropy / log(K)
    margin: float                # ∈ [0, 1] — top1 − top2
    disagreement: bool           # CNN class ≠ SAM class
    composite: float             # weighted combination ∈ [0, 1]
    status: str                  # forward from uncertainty.classify_uncertainty


def acquisition_score(
    sample_idx: int,
    features: np.ndarray,
    spectrum: np.ndarray,
    engine,
    sam,
    *,
    weights: tuple[float, float, float] = (0.4, 0.3, 0.3),
) -> AcquisitionScore:
    """Score one sample for acquisition. Higher = more informative."""
    cnn = engine.predict(features)
    sam_r = sam.predict(spectrum)
    K = int(np.asarray(cnn["probabilities"]).size)

    entropy_norm = float(cnn.get("entropy", 0.0)) / float(np.log(K))
    margin_inv = 1.0 - float(cnn.get("margin", 0.0))
    disagreement = int(cnn["class_index"]) != int(sam_r["class_index"])

    w_e, w_m, w_d = weights
    composite = w_e * entropy_norm + w_m * margin_inv + w_d * float(disagreement)
    composite = float(np.clip(composite, 0.0, 1.0))

    return AcquisitionScore(
        sample_idx=int(sample_idx),
        cnn_class=int(cnn["class_index"]),
        sam_class=int(sam_r["class_index"]),
        confidence=float(cnn.get("confidence", float(np.max(cnn["probabilities"])))),
        entropy_norm=entropy_norm,
        margin=float(cnn.get("margin", 0.0)),
        disagreement=bool(disagreement),
        composite=composite,
        status=str(cnn.get("status", "nominal")),
    )


def rank_pool(
    pool_features: np.ndarray,
    pool_spectra: np.ndarray,
    engine,
    sam,
    *,
    top_k: int | None = None,
    weights: tuple[float, float, float] = (0.4, 0.3, 0.3),
) -> list[AcquisitionScore]:
    """Score and rank an unlabelled pool, return top-k descending.

    Parameters
    ----------
    pool_features
        ``(N, K)`` feature matrix — what the CNN consumes.
    pool_spectra
        ``(N, N_SPEC)`` raw spectra — what SAM consumes (different
        feature space).
    engine, sam
        Loaded inference + SAM classifiers.
    top_k
        Return the top-k highest-scoring samples. ``None`` returns all.
    weights
        ``(w_entropy, w_margin, w_disagree)`` summing to ~1.0.
    """
    pool_features = np.asarray(pool_features)
    pool_spectra = np.asarray(pool_spectra)
    if pool_features.shape[0] != pool_spectra.shape[0]:
        raise ValueError(
            f"pool_features ({pool_features.shape[0]}) and pool_spectra "
            f"({pool_spectra.shape[0]}) must have the same number of samples"
        )

    scores = [
        acquisition_score(
            i, pool_features[i], pool_spectra[i], engine, sam, weights=weights
        )
        for i in range(pool_features.shape[0])
    ]
    scores.sort(key=lambda s: s.composite, reverse=True)
    return scores if top_k is None else scores[: int(top_k)]


def disagreement_rate(scores: list[AcquisitionScore]) -> float:
    """Fraction of pool samples where SAM and CNN disagree.

    Useful as a single number to track over time: high disagreement
    indicates the pool is rich in informative samples; low disagreement
    indicates the model and the baseline are converging on the same
    class boundaries.
    """
    if not scores:
        return 0.0
    return float(sum(s.disagreement for s in scores) / len(scores))


__all__ = [
    "AcquisitionScore",
    "acquisition_score",
    "disagreement_rate",
    "rank_pool",
]
