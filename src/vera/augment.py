"""Physically motivated augmentations for spectra.

The hardware will see effects we cannot model with infinite fidelity in
:mod:`vera.synth`, so we additionally augment training spectra at load
time. Each augmentation is a function ``(spectrum, rng) -> spectrum`` that
preserves shape ``(K,)`` and clips to a sane range.

Augmentations are deliberately *small* and *physical*. Aggressive
augmentation tends to wash out the absorption features the model needs.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# ---------------------------------------------------------------------------
# Atomic augmentations
# ---------------------------------------------------------------------------


def add_gaussian_noise(
    spectrum: np.ndarray, rng: np.random.Generator, sigma: float = 0.005
) -> np.ndarray:
    """Per-channel Gaussian noise — represents residual readout noise."""
    return spectrum + rng.normal(0.0, sigma, size=spectrum.shape)


def intensity_jitter(
    spectrum: np.ndarray, rng: np.random.Generator, sigma: float = 0.05
) -> np.ndarray:
    """Multiplicative global intensity scaling — packing/standoff variation."""
    scale = 1.0 + rng.normal(0.0, sigma)
    return spectrum * scale


def baseline_shift(
    spectrum: np.ndarray, rng: np.random.Generator, amp: float = 0.02
) -> np.ndarray:
    """Smooth additive baseline drift (low-order polynomial)."""
    K = spectrum.shape[-1]
    x = np.linspace(-1.0, 1.0, K)
    coeffs = rng.uniform(-1.0, 1.0, size=4)
    poly = coeffs[0] + coeffs[1] * x + coeffs[2] * x**2 + coeffs[3] * x**3
    poly = poly / (np.max(np.abs(poly)) + 1e-12)
    return spectrum + amp * poly


def channel_dropout(
    spectrum: np.ndarray, rng: np.random.Generator, p: float = 0.01
) -> np.ndarray:
    """Zero out a small fraction of channels.

    Models a flaky pixel or a single LED outage. ``p`` is per-channel.
    """
    if p <= 0:
        return spectrum.copy()
    mask = rng.uniform(0.0, 1.0, size=spectrum.shape) >= p
    return spectrum * mask


def wavelength_shift(
    spectrum: np.ndarray, rng: np.random.Generator, max_shift_px: int = 1
) -> np.ndarray:
    """Tiny integer-pixel shift along the spectral axis.

    Represents a small wavelength-calibration error. Edge values are
    repeated rather than wrapped.
    """
    if max_shift_px <= 0:
        return spectrum.copy()
    shift = int(rng.integers(-max_shift_px, max_shift_px + 1))
    if shift == 0:
        return spectrum.copy()
    out = np.roll(spectrum, shift, axis=-1)
    if shift > 0:
        out[..., :shift] = spectrum[..., :1]
    else:
        out[..., shift:] = spectrum[..., -1:]
    return out


# ---------------------------------------------------------------------------
# Composite pipeline
# ---------------------------------------------------------------------------


@dataclass
class AugmentConfig:
    """Knobs for the default training-time augmentation pipeline."""

    p_apply: float = 0.8           # probability the whole pipeline runs
    gaussian_sigma: float = 0.010  # 2x: force robustness to readout noise
    intensity_sigma: float = 0.08  # 2x: simulate LED intensity variations
    baseline_amp: float = 0.030    # 2x: ambient light / stray light leaks
    dropout_p: float = 0.008       # dead pixel rate
    max_shift_px: int = 2          # wavelength calibration uncertainty
    clip_lo: float = 0.0
    clip_hi: float = 1.5


# Augmentations applied only to the 288-channel spectrometer block.
# LEDs, AS7265x, SWIR, and LIF channels are NOT augmented — adding
# noise to LED duty values would model an electrical fault rather than
# a measurement variation, and similarly for the other modalities.
def augment_spectrum(
    spectrum: np.ndarray,
    rng: np.random.Generator,
    cfg: AugmentConfig | None = None,
) -> np.ndarray:
    """Apply the full augmentation pipeline to a single spectrum.

    With probability ``1 - cfg.p_apply`` the spectrum is returned unchanged
    (so the model still sees clean examples).
    """
    cfg = cfg or AugmentConfig()
    if rng.uniform(0.0, 1.0) >= cfg.p_apply:
        return np.clip(spectrum.copy(), cfg.clip_lo, cfg.clip_hi)
    out = spectrum.astype(np.float64, copy=True)
    out = intensity_jitter(out, rng, sigma=cfg.intensity_sigma)
    out = baseline_shift(out, rng, amp=cfg.baseline_amp)
    out = wavelength_shift(out, rng, max_shift_px=cfg.max_shift_px)
    out = add_gaussian_noise(out, rng, sigma=cfg.gaussian_sigma)
    out = channel_dropout(out, rng, p=cfg.dropout_p)
    return np.clip(out, cfg.clip_lo, cfg.clip_hi)


def augment_batch(
    spectra: np.ndarray,
    rng: np.random.Generator,
    cfg: AugmentConfig | None = None,
) -> np.ndarray:
    """Apply :func:`augment_spectrum` independently to each row of a (N, K) batch."""
    if spectra.ndim != 2:
        raise ValueError(f"spectra must be 2-D, got shape {spectra.shape}")
    out = np.empty_like(spectra, dtype=np.float64)
    for i in range(spectra.shape[0]):
        out[i] = augment_spectrum(spectra[i], rng, cfg)
    return out


__all__ = [
    "AugmentConfig",
    "add_gaussian_noise",
    "augment_batch",
    "augment_spectrum",
    "baseline_shift",
    "channel_dropout",
    "intensity_jitter",
    "wavelength_shift",
]
