"""Spectroscopic preprocessing primitives.

These functions all operate on plain ``numpy`` arrays — they know nothing
about the canonical CSV. The training pipeline pulls a ``(N, 288)`` block
out via :func:`vera.io_csv.extract_spectra` and pushes it through here.

All functions are vectorised over the leading axis (samples).
"""

from __future__ import annotations

import numpy as np
from scipy.signal import savgol_filter
from scipy.sparse import csc_matrix, diags
from scipy.sparse.linalg import spsolve

# ---------------------------------------------------------------------------
# Reflectance normalisation (dark / white)
# ---------------------------------------------------------------------------


def reflectance_normalise(
    raw: np.ndarray,
    dark: np.ndarray,
    white: np.ndarray,
    *,
    eps: float = 1e-6,
) -> np.ndarray:
    """Convert raw counts to reflectance with dark + white references.

    Parameters
    ----------
    raw   : (N, K) raw counts
    dark  : (K,)   dark spectrum (probe shuttered)
    white : (K,)   white reference spectrum (Spectralon-equivalent)

    Returns
    -------
    (N, K) reflectance, clipped to [0, 1.5] (small overshoot allowed for
    noise headroom).
    """
    raw = np.asarray(raw, dtype=np.float64)
    dark = np.asarray(dark, dtype=np.float64)
    white = np.asarray(white, dtype=np.float64)
    if raw.ndim != 2:
        raise ValueError(f"raw must be 2-D, got shape {raw.shape}")
    if dark.shape != raw.shape[1:] or white.shape != raw.shape[1:]:
        raise ValueError("dark/white must have shape matching raw[1:]")
    denom = (white - dark)
    denom = np.where(np.abs(denom) < eps, eps, denom)
    out = (raw - dark[None, :]) / denom[None, :]
    return np.clip(out, 0.0, 1.5)


# ---------------------------------------------------------------------------
# Savitzky-Golay smoothing / derivatives
# ---------------------------------------------------------------------------


def savgol_smooth(
    spectra: np.ndarray,
    window_length: int = 11,
    polyorder: int = 3,
    deriv: int = 0,
) -> np.ndarray:
    """Savitzky-Golay smoothing or derivative along the spectral axis.

    Wraps :func:`scipy.signal.savgol_filter` with sane defaults for the
    C12880MA (~1.78 nm/px) — an 11-pixel window covers ~20 nm.
    """
    if window_length % 2 == 0:
        raise ValueError("window_length must be odd")
    if window_length <= polyorder:
        raise ValueError("window_length must be > polyorder")
    return savgol_filter(
        spectra,
        window_length=window_length,
        polyorder=polyorder,
        deriv=deriv,
        axis=-1,
        mode="interp",
    )


def first_derivative(spectra: np.ndarray, window_length: int = 11) -> np.ndarray:
    """First derivative via Savitzky-Golay (less noisy than np.gradient)."""
    return savgol_smooth(spectra, window_length=window_length, polyorder=3, deriv=1)


# ---------------------------------------------------------------------------
# Asymmetric least squares baseline (AsLS, Eilers & Boelens 2005)
# ---------------------------------------------------------------------------


def asls_baseline(
    spectrum: np.ndarray,
    *,
    lam: float = 1e5,
    p: float = 0.01,
    n_iter: int = 10,
) -> np.ndarray:
    """Estimate the baseline of a single 1-D spectrum via AsLS.

    A small ``p`` (0.001–0.05) pulls the baseline toward the lower envelope,
    which is what we want for emission/absorption spectra. ``lam`` controls
    smoothness.
    """
    y = np.asarray(spectrum, dtype=np.float64).ravel()
    L = y.size
    if L < 5:
        return np.zeros_like(y)
    D = diags([1.0, -2.0, 1.0], [0, -1, -2], shape=(L, L - 2), format="csc")
    DtD = D @ D.T
    w = np.ones(L)
    z = y.copy()
    for _ in range(n_iter):
        W = diags(w, 0, shape=(L, L), format="csc")
        Z = csc_matrix(W + lam * DtD)
        z = spsolve(Z, w * y)
        w = p * (y > z) + (1 - p) * (y < z)
    return z


def asls_baseline_batch(
    spectra: np.ndarray,
    *,
    lam: float = 1e5,
    p: float = 0.01,
    n_iter: int = 10,
) -> np.ndarray:
    """Vectorised wrapper around :func:`asls_baseline` over a (N, K) batch."""
    spectra = np.asarray(spectra, dtype=np.float64)
    if spectra.ndim != 2:
        raise ValueError(f"spectra must be 2-D, got shape {spectra.shape}")
    out = np.empty_like(spectra)
    for i in range(spectra.shape[0]):
        out[i] = asls_baseline(spectra[i], lam=lam, p=p, n_iter=n_iter)
    return out


# ---------------------------------------------------------------------------
# Continuum removal (convex hull / "rubber band")
# ---------------------------------------------------------------------------


def continuum_removal(
    spectrum: np.ndarray,
    wavelengths: np.ndarray,
) -> np.ndarray:
    """Continuum-removed spectrum (1-D) using the upper convex hull.

    R_cr(λ) = R(λ) / hull(λ); the result lives in [0, 1] with absorption
    bands as dips below 1.
    """
    y = np.asarray(spectrum, dtype=np.float64).ravel()
    x = np.asarray(wavelengths, dtype=np.float64).ravel()
    if y.shape != x.shape:
        raise ValueError("spectrum and wavelengths must have the same shape")
    n = y.size
    if n < 3:
        return np.ones_like(y)

    # Andrew's monotone chain on (x, y), keeping only the upper hull.
    pts = list(range(n))
    upper: list[int] = []
    for i in pts:
        while len(upper) >= 2:
            a, b = upper[-2], upper[-1]
            cross = (x[b] - x[a]) * (y[i] - y[a]) - (y[b] - y[a]) * (x[i] - x[a])
            if cross >= 0:
                upper.pop()
            else:
                break
        upper.append(i)
    hull_x = x[upper]
    hull_y = y[upper]
    hull_interp = np.interp(x, hull_x, hull_y)
    hull_interp = np.where(hull_interp < 1e-9, 1e-9, hull_interp)
    return y / hull_interp


def continuum_removal_batch(
    spectra: np.ndarray,
    wavelengths: np.ndarray,
) -> np.ndarray:
    spectra = np.asarray(spectra, dtype=np.float64)
    if spectra.ndim != 2:
        raise ValueError(f"spectra must be 2-D, got shape {spectra.shape}")
    out = np.empty_like(spectra)
    for i in range(spectra.shape[0]):
        out[i] = continuum_removal(spectra[i], wavelengths)
    return out


# ---------------------------------------------------------------------------
# Standard scaler that's safe for small synthetic datasets
# ---------------------------------------------------------------------------


def standardise(spectra: np.ndarray, axis: int = 0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Z-score along ``axis``. Returns (z, mean, std).

    ``std`` is floored at ``1e-9`` to avoid division by zero on constant
    columns.
    """
    mean = spectra.mean(axis=axis, keepdims=True)
    std = spectra.std(axis=axis, keepdims=True)
    std = np.where(std < 1e-9, 1.0, std)
    return (spectra - mean) / std, mean.squeeze(0), std.squeeze(0)


def apply_standardise(spectra: np.ndarray, mean: np.ndarray, std: np.ndarray) -> np.ndarray:
    """Apply a previously fit (mean, std) to new data."""
    safe_std = np.where(std < 1e-9, 1.0, std)
    return (spectra - mean) / safe_std


__all__ = [
    "apply_standardise",
    "asls_baseline",
    "asls_baseline_batch",
    "continuum_removal",
    "continuum_removal_batch",
    "first_derivative",
    "reflectance_normalise",
    "savgol_smooth",
    "standardise",
]
