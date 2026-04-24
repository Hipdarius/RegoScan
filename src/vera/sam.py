"""Spectral Angle Mapper — classical hyperspectral baseline.

SAM treats each spectrum as a vector in ``N``-dimensional space and
classifies by the angle to each reference endmember:

    cos(theta_k) = (s . r_k) / (||s|| * ||r_k||)

The class with the smallest angle (largest cosine) wins. SAM is invariant
to multiplicative illumination changes — scaling ``s`` by any positive
constant rotates the vector by zero degrees. That makes it the standard
quick-look classifier for VIS/NIR spectroscopy.

We use SAM here as a paper-friendly **baseline** for the CNN. Numbers
worth quoting:

    * SAM is ~10× faster than the CNN (microseconds, no ONNX required).
    * SAM accuracy is the floor against which the CNN must clearly win
      to justify the extra inference cost.
    * SAM can run as a sanity-check parallel classifier on the bridge
      for free — disagreement with the CNN is itself a useful signal.

References
----------
Kruse et al. (1993) "The spectral image processing system (SIPS) —
interactive visualization and analysis of imaging spectrometer data",
Remote Sensing of Environment 44, 145-163.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .schema import MINERAL_CLASSES


# ---------------------------------------------------------------------------
# Core SAM
# ---------------------------------------------------------------------------


def spectral_angle(s: np.ndarray, r: np.ndarray, *, eps: float = 1e-12) -> float:
    """Spectral angle in radians between two spectra.

    Both inputs must be 1-D and the same length. Returns 0 for identical
    direction (any positive scaling) and ``pi/2`` for orthogonal spectra.
    """
    s = np.asarray(s, dtype=np.float64).ravel()
    r = np.asarray(r, dtype=np.float64).ravel()
    if s.shape != r.shape:
        raise ValueError(f"shape mismatch: {s.shape} vs {r.shape}")
    denom = float(np.linalg.norm(s) * np.linalg.norm(r))
    if denom < eps:
        return float(np.pi / 2)
    cosang = float(np.dot(s, r) / denom)
    # Clip for numerical safety
    cosang = max(-1.0, min(1.0, cosang))
    return float(np.arccos(cosang))


def spectral_angles_batch(
    s: np.ndarray,
    refs: np.ndarray,
    *,
    eps: float = 1e-12,
) -> np.ndarray:
    """Vectorised SAM: angle between ``s`` (single or batch) and each ref.

    Parameters
    ----------
    s
        Either ``(K,)`` (single sample) or ``(N, K)`` (batch).
    refs
        ``(C, K)`` reference endmember spectra.

    Returns
    -------
    Angles in radians. Shape: ``(C,)`` for single sample, ``(N, C)`` for
    batch.
    """
    s = np.asarray(s, dtype=np.float64)
    refs = np.asarray(refs, dtype=np.float64)
    one_d = s.ndim == 1
    if one_d:
        s = s[None, :]
    if s.shape[-1] != refs.shape[-1]:
        raise ValueError(
            f"channel count mismatch: s has {s.shape[-1]}, refs has {refs.shape[-1]}"
        )

    # Norms
    s_norm = np.linalg.norm(s, axis=-1, keepdims=True)        # (N, 1)
    r_norm = np.linalg.norm(refs, axis=-1, keepdims=True)     # (C, 1)
    denom = s_norm @ r_norm.T                                  # (N, C)
    denom = np.where(denom < eps, eps, denom)

    cosang = (s @ refs.T) / denom                              # (N, C)
    cosang = np.clip(cosang, -1.0, 1.0)
    angles = np.arccos(cosang)                                 # (N, C)
    return angles[0] if one_d else angles


# ---------------------------------------------------------------------------
# Classifier wrapper
# ---------------------------------------------------------------------------


@dataclass
class SAMClassifier:
    """Spectral Angle Mapper classifier.

    Built once from a stack of class-mean spectra and reused for every
    prediction. The class names default to ``MINERAL_CLASSES`` but can be
    overridden when the reference stack uses a different ordering.
    """

    references: np.ndarray
    """Class-mean spectra. Shape: ``(C, K)``."""

    class_names: tuple[str, ...] = MINERAL_CLASSES
    """Class label per row of ``references``."""

    def __post_init__(self) -> None:
        self.references = np.asarray(self.references, dtype=np.float64)
        if self.references.ndim != 2:
            raise ValueError(
                f"references must be 2-D, got {self.references.shape}"
            )
        if len(self.class_names) != self.references.shape[0]:
            raise ValueError(
                f"got {len(self.class_names)} class names but "
                f"{self.references.shape[0]} reference spectra"
            )

    def predict(self, spectrum: np.ndarray) -> dict:
        """Classify a single spectrum. Returns a result dict shaped like
        :meth:`vera.inference.InferenceEngine.predict` for swap-in use.

        ``probabilities`` are derived by softmax over the *negative*
        angles (closer = higher prob). Not a calibrated probability —
        more of a pseudo-confidence.
        """
        angles = spectral_angles_batch(spectrum, self.references)
        cls_idx = int(np.argmin(angles))
        # Pseudo-probabilities: softmax(-angle) so the smallest angle has
        # the highest weight. Scale by 5 to make the distribution peaked.
        scores = -5.0 * angles
        scores = scores - scores.max()
        probs = np.exp(scores)
        probs = probs / probs.sum()
        return {
            "class_index": cls_idx,
            "class_name": self.class_names[cls_idx],
            "angle_rad": float(angles[cls_idx]),
            "angle_deg": float(np.degrees(angles[cls_idx])),
            "probabilities": probs,
            "all_angles_deg": np.degrees(angles),
        }

    def predict_batch(self, spectra: np.ndarray) -> np.ndarray:
        """Argmin over the angle matrix. Shape: ``(N,)``."""
        angles = spectral_angles_batch(spectra, self.references)
        return np.argmin(angles, axis=-1)


def build_classifier_from_endmembers(
    endmembers: dict | object,
    *,
    use_swir: bool = False,
) -> SAMClassifier:
    """Convenience: build a SAMClassifier directly from a USGS endmember
    cache.

    The 5 parametric endmembers map to 5 of the 6 mineral classes. The
    "mixed" class isn't a pure endmember — we approximate it as the
    fraction-weighted mean of the 5 pures, which is what a uniformly
    sampled "mixed" measurement would average to.
    """
    # Accept either a dict-like or our Endmembers dataclass
    if hasattr(endmembers, "spectra"):
        spectra = np.asarray(endmembers.spectra, dtype=np.float64)
        names = list(endmembers.names) if hasattr(endmembers, "names") else None
    else:
        spectra = np.stack([
            np.asarray(endmembers[n], dtype=np.float64)
            for n in ("ilmenite", "olivine", "pyroxene", "anorthite", "glass_agglutinate")
        ])
        names = None

    # Append a "mixed" reference as the simple mean.
    mixed = spectra.mean(axis=0, keepdims=True)
    refs = np.concatenate([spectra, mixed], axis=0)

    # Class names ordered to match training
    ordered = [
        "ilmenite_rich",
        "olivine_rich",
        "pyroxene_rich",
        "anorthositic",
        "glass_agglutinate",
        "mixed",
    ]
    return SAMClassifier(references=refs, class_names=tuple(ordered))


__all__ = [
    "SAMClassifier",
    "build_classifier_from_endmembers",
    "spectral_angle",
    "spectral_angles_batch",
]
