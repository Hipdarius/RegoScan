"""Hand-crafted features used by the PLSR/RandomForest baselines.

These are *not* fed to the CNN — the CNN consumes the full preprocessed
spectrum directly. They exist so the baseline has a fighting chance with
small synthetic datasets.

Each feature is computed from one or more of:
  - the full 288-channel spectrum (after preprocessing)
  - the 12 LED narrowband reflectances
  - the LIF photodiode value

Features:
  * broad_albedo            mean reflectance over 500–800 nm
  * vis_red_slope           slope (per-nm) of a 1st-order fit on 500–800 nm
  * uv_blue_drop            mean(340–420) / mean(500–600)
  * band_depth_~700         continuum-removed depth around 700 nm
  * band_depth_~620         continuum-removed depth around 620 nm
  * led_red_blue_ratio      led_660 / led_450
  * led_nir_vis_ratio       mean(led_730, led_780, led_850) / mean(led_450, led_525)
  * lif_normalised          lif_450lp / (broad_albedo + eps)
"""

from __future__ import annotations

import numpy as np

from vera.preprocess import continuum_removal_batch
from vera.schema import AS7265X_BANDS, LED_WAVELENGTHS_NM, N_AS7265X, SENSOR_MODES, WAVELENGTHS

EPS = 1e-6

# Pre-compute index masks once.
_VIS_BAND = (WAVELENGTHS >= 500) & (WAVELENGTHS <= 800)
_UV_BAND = (WAVELENGTHS >= 340) & (WAVELENGTHS <= 420)
_GREEN_BAND = (WAVELENGTHS >= 500) & (WAVELENGTHS <= 600)
_BAND_700 = (WAVELENGTHS >= 680) & (WAVELENGTHS <= 720)
_BAND_620 = (WAVELENGTHS >= 600) & (WAVELENGTHS <= 640)

LED_INDEX = {w: i for i, w in enumerate(LED_WAVELENGTHS_NM)}

FEATURE_NAMES: tuple[str, ...] = (
    "broad_albedo",
    "vis_red_slope",
    "uv_blue_drop",
    "band_depth_700",
    "band_depth_620",
    "led_red_blue_ratio",
    "led_nir_vis_ratio",
    "lif_normalised",
)
N_FEATURES: int = len(FEATURE_NAMES)


def _broad_albedo(spectra: np.ndarray) -> np.ndarray:
    return spectra[:, _VIS_BAND].mean(axis=1)


def _vis_red_slope(spectra: np.ndarray) -> np.ndarray:
    lam = WAVELENGTHS[_VIS_BAND]
    block = spectra[:, _VIS_BAND]
    lam_c = lam - lam.mean()
    denom = (lam_c**2).sum()
    return (block - block.mean(axis=1, keepdims=True)) @ lam_c / denom


def _uv_blue_drop(spectra: np.ndarray) -> np.ndarray:
    uv = spectra[:, _UV_BAND].mean(axis=1)
    green = spectra[:, _GREEN_BAND].mean(axis=1)
    return uv / (green + EPS)


def _band_depth(spectra_cr: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Depth = 1 - min(continuum_removed) inside ``mask``."""
    return 1.0 - spectra_cr[:, mask].min(axis=1)


def compute_features(
    spectra: np.ndarray,
    leds: np.ndarray,
    lif: np.ndarray,
) -> np.ndarray:
    """Stack all hand-crafted features into a single (N, F) matrix.

    ``spectra`` is the (N, 288) reflectance block (already dark/white
    normalised). ``leds`` is (N, 12), ``lif`` is (N,).
    """
    spectra = np.asarray(spectra, dtype=np.float64)
    leds = np.asarray(leds, dtype=np.float64)
    lif = np.asarray(lif, dtype=np.float64).ravel()

    if spectra.ndim != 2 or spectra.shape[1] != WAVELENGTHS.size:
        raise ValueError(f"spectra must be (N, {WAVELENGTHS.size}); got {spectra.shape}")
    if leds.shape != (spectra.shape[0], len(LED_WAVELENGTHS_NM)):
        raise ValueError(f"leds must be (N, {len(LED_WAVELENGTHS_NM)})")
    if lif.shape != (spectra.shape[0],):
        raise ValueError(f"lif must be (N,) matching spectra")

    albedo = _broad_albedo(spectra)
    slope = _vis_red_slope(spectra)
    uv = _uv_blue_drop(spectra)

    cr = continuum_removal_batch(spectra, WAVELENGTHS)
    bd700 = _band_depth(cr, _BAND_700)
    bd620 = _band_depth(cr, _BAND_620)

    led_red = leds[:, LED_INDEX[660]]
    led_blue = leds[:, LED_INDEX[450]]
    led_red_blue = led_red / (led_blue + EPS)

    nir_idx = [LED_INDEX[w] for w in (730, 780, 850)]
    vis_idx = [LED_INDEX[w] for w in (450, 525)]
    led_nir_vis = leds[:, nir_idx].mean(axis=1) / (leds[:, vis_idx].mean(axis=1) + EPS)

    lif_norm = lif / (albedo + EPS)

    feats = np.stack(
        [albedo, slope, uv, bd700, bd620, led_red_blue, led_nir_vis, lif_norm],
        axis=1,
    )
    return feats


# ---------------------------------------------------------------------------
# AS7265x multispectral features
# ---------------------------------------------------------------------------

# Build a lookup from AS7265x band wavelength to column index
_AS7_INDEX: dict[int, int] = {w: i for i, w in enumerate(AS7265X_BANDS)}

MULTISPECTRAL_FEATURE_NAMES: tuple[str, ...] = (
    "as7_broad_albedo",        # mean of VIS-range AS7265x channels
    "as7_vis_nir_slope",       # slope across VIS-to-NIR channels
    "as7_blue_red_ratio",      # 460 nm / 680 nm
    "as7_nir_vis_ratio",       # mean(810,860,900) / mean(460,510,560)
    "as7_band_depth_700",      # 1 - (ch_680 / mean(ch_645, ch_730))
    "as7_uv_drop",             # ch_410 / ch_535
    "led_red_blue_ratio",      # same as full-mode (shared LEDs)
    "led_nir_vis_ratio",       # same as full-mode (shared LEDs)
    "lif_normalised",          # lif / (as7_broad_albedo + eps)
)
N_MULTISPECTRAL_FEATURES: int = len(MULTISPECTRAL_FEATURE_NAMES)


def compute_features_multispectral(
    as7265x: np.ndarray,
    leds: np.ndarray,
    lif: np.ndarray,
) -> np.ndarray:
    """Hand-crafted features from AS7265x 18-band data.

    ``as7265x`` is (N, 18), ``leds`` is (N, 12), ``lif`` is (N,).
    Returns (N, 9) feature matrix.
    """
    as7265x = np.asarray(as7265x, dtype=np.float64)
    leds = np.asarray(leds, dtype=np.float64)
    lif = np.asarray(lif, dtype=np.float64).ravel()

    n = as7265x.shape[0]
    if as7265x.ndim != 2 or as7265x.shape[1] != N_AS7265X:
        raise ValueError(f"as7265x must be (N, {N_AS7265X}); got {as7265x.shape}")
    if leds.shape != (n, len(LED_WAVELENGTHS_NM)):
        raise ValueError(f"leds must be (N, {len(LED_WAVELENGTHS_NM)})")
    if lif.shape != (n,):
        raise ValueError("lif must be (N,) matching as7265x")

    # VIS-range channels for broad albedo (510..680 nm)
    vis_idx = [_AS7_INDEX[w] for w in (510, 535, 560, 585, 610, 645, 680)]
    as7_albedo = as7265x[:, vis_idx].mean(axis=1)

    # VIS-to-NIR slope: simple linear fit over all 18 channels
    band_arr = np.array(AS7265X_BANDS, dtype=np.float64)
    band_c = band_arr - band_arr.mean()
    denom = (band_c ** 2).sum()
    as7_slope = (as7265x - as7265x.mean(axis=1, keepdims=True)) @ band_c / denom

    # Ratios
    ch_460 = as7265x[:, _AS7_INDEX[460]]
    ch_680 = as7265x[:, _AS7_INDEX[680]]
    as7_blue_red = ch_460 / (ch_680 + EPS)

    nir_idx = [_AS7_INDEX[w] for w in (810, 860, 900)]
    vis_ratio_idx = [_AS7_INDEX[w] for w in (460, 510, 560)]
    as7_nir_vis = as7265x[:, nir_idx].mean(axis=1) / (
        as7265x[:, vis_ratio_idx].mean(axis=1) + EPS
    )

    # Band depth around 680 nm using 645 and 730 as shoulders
    ch_645 = as7265x[:, _AS7_INDEX[645]]
    ch_730 = as7265x[:, _AS7_INDEX[730]]
    continuum_700 = (ch_645 + ch_730) / 2.0
    as7_bd700 = 1.0 - ch_680 / (continuum_700 + EPS)

    # UV drop: 410 / 535
    ch_410 = as7265x[:, _AS7_INDEX[410]]
    ch_535 = as7265x[:, _AS7_INDEX[535]]
    as7_uv_drop = ch_410 / (ch_535 + EPS)

    # Shared LED features (identical to full-mode)
    led_red = leds[:, LED_INDEX[660]]
    led_blue = leds[:, LED_INDEX[450]]
    led_red_blue = led_red / (led_blue + EPS)

    nir_led_idx = [LED_INDEX[w] for w in (730, 780, 850)]
    vis_led_idx = [LED_INDEX[w] for w in (450, 525)]
    led_nir_vis = leds[:, nir_led_idx].mean(axis=1) / (
        leds[:, vis_led_idx].mean(axis=1) + EPS
    )

    lif_norm = lif / (as7_albedo + EPS)

    return np.stack(
        [
            as7_albedo,
            as7_slope,
            as7_blue_red,
            as7_nir_vis,
            as7_bd700,
            as7_uv_drop,
            led_red_blue,
            led_nir_vis,
            lif_norm,
        ],
        axis=1,
    )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


def compute_features_dispatch(
    sensor_mode: str,
    *,
    spectra: np.ndarray | None = None,
    as7265x: np.ndarray | None = None,
    leds: np.ndarray,
    lif: np.ndarray,
) -> np.ndarray:
    """Route to the correct feature extractor based on *sensor_mode*.

    Parameters
    ----------
    sensor_mode : str
        ``"full"`` uses only C12880MA spectra, ``"multispectral"`` uses
        only AS7265x, ``"combined"`` concatenates both feature sets.
    spectra : array, optional
        Required when *sensor_mode* is ``"full"`` or ``"combined"``.
    as7265x : array, optional
        Required when *sensor_mode* is ``"multispectral"`` or ``"combined"``.
    leds, lif : array
        Always required.

    Returns
    -------
    np.ndarray
        (N, F) feature matrix. F depends on *sensor_mode*.
    """
    if sensor_mode not in SENSOR_MODES:
        raise ValueError(
            f"Unknown sensor_mode: {sensor_mode!r}; expected one of {SENSOR_MODES}"
        )

    if sensor_mode == "full":
        if spectra is None:
            raise ValueError("spectra is required for sensor_mode='full'")
        return compute_features(spectra, leds, lif)

    if sensor_mode == "multispectral":
        if as7265x is None:
            raise ValueError("as7265x is required for sensor_mode='multispectral'")
        return compute_features_multispectral(as7265x, leds, lif)

    # combined: concatenate both feature sets
    if spectra is None:
        raise ValueError("spectra is required for sensor_mode='combined'")
    if as7265x is None:
        raise ValueError("as7265x is required for sensor_mode='combined'")
    full_feats = compute_features(spectra, leds, lif)
    multi_feats = compute_features_multispectral(as7265x, leds, lif)
    return np.concatenate([full_feats, multi_feats], axis=1)


__all__ = [
    "FEATURE_NAMES",
    "N_FEATURES",
    "compute_features",
    "MULTISPECTRAL_FEATURE_NAMES",
    "N_MULTISPECTRAL_FEATURES",
    "compute_features_multispectral",
    "compute_features_dispatch",
]
