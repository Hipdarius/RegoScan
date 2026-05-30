"""Hardware calibration pipeline for VERA.

Real spectrometer data needs to be normalized before it can be fed to the
classifier. The C12880MA outputs 12-bit raw counts that depend on:

* integration time (linear)
* dark current (additive offset, drifts with temperature)
* illumination intensity (multiplicative gain on the optical path)
* sensor non-uniformity (per-pixel response variation)

The training pipeline in :mod:`vera.synth` already produces values that
look like reflectance ∈ [0, 1.5]. To feed *real* hardware frames to the
same model, we need the inverse of the synthesizer — turn raw counts back
into reflectance using on-board reference measurements.

This module is the single source of truth for that conversion. It mirrors
:func:`vera.preprocess.reflectance_normalise` but adds the steps the raw
preprocess function omitted: integration time correction, temperature
compensation of the dark frame, and bright-pixel saturation flagging.

Usage
-----
::

    from vera.calibrate import CalibrationFrames, calibrate_spectrum

    # Captured once per session (or whenever lab conditions change)
    cal = CalibrationFrames(
        dark=dark_raw,                # (288,) raw counts, lights off
        white=white_raw,              # (288,) raw counts, broadband on Spectralon
        dark_integration_ms=10,
        white_integration_ms=10,
        dark_temp_c=22.0,
        white_temp_c=22.0,
    )

    # Per-frame call from bridge.py
    refl = calibrate_spectrum(
        raw=frame_raw,                # (288,) raw counts from probe
        integration_ms=frame.integration_time_ms,
        temp_c=frame.ambient_temp_c,
        cal=cal,
    )                                 # (288,) reflectance ∈ [0, 1.5]
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .schema import N_SPEC

# ---------------------------------------------------------------------------
# Constants — tuneable from bench characterization
# ---------------------------------------------------------------------------

#: NTC dark-current temperature coefficient (counts per °C above reference).
#: Si CMOS dark current roughly doubles every 8 °C; for the C12880MA at
#: room temperature with 10 ms integration, that's ~2 counts/°C. This is
#: a coarse estimate — replace with measured values once we have them.
DARK_TEMP_COEFF_PER_C: float = 2.0

#: Reference temperature at which dark/white frames are assumed to be valid.
DARK_REF_TEMP_C: float = 22.0

#: Saturation threshold (counts). The C12880MA's 12-bit ADC tops out at
#: 4095; we flag pixels above 4000 as potentially saturated.
SAT_THRESHOLD_COUNTS: int = 4000

#: Maximum allowed reflectance value before clipping. Real bright targets
#: like Spectralon can briefly exceed 1.0 due to specular components, so
#: we clip at 1.5 to give some headroom while rejecting nonsense.
REFL_CLIP_MAX: float = 1.5


# ---------------------------------------------------------------------------
# CalibrationFrames container
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CalibrationFrames:
    """Reference frames captured before a measurement session.

    The ``dark`` frame is the sensor reading with the optical path
    blocked (or all illumination off). The ``white`` frame is the
    sensor reading with broadband illumination on a known reflectance
    standard (Spectralon or BaSO₄, R ≈ 0.99).

    Both frames must use the same wavelength grid as the live measurement
    (288 channels for the C12880MA). Integration times can differ from
    the live frame — we scale them linearly during calibration.
    """

    dark: np.ndarray
    """Dark reference (raw counts). Shape: (N_SPEC,)."""

    white: np.ndarray
    """White reference (raw counts). Shape: (N_SPEC,)."""

    dark_integration_ms: float
    """Integration time used to capture the dark frame, in ms."""

    white_integration_ms: float
    """Integration time used to capture the white frame, in ms."""

    dark_temp_c: float = DARK_REF_TEMP_C
    """Probe temperature when the dark frame was captured."""

    white_temp_c: float = DARK_REF_TEMP_C
    """Probe temperature when the white frame was captured."""

    def __post_init__(self) -> None:  # validation
        for name, arr in (("dark", self.dark), ("white", self.white)):
            a = np.asarray(arr)
            if a.ndim != 1 or a.shape[0] != N_SPEC:
                raise ValueError(
                    f"{name} must have shape ({N_SPEC},), got {a.shape}"
                )
        if self.dark_integration_ms <= 0 or self.white_integration_ms <= 0:
            raise ValueError("integration times must be positive")


# ---------------------------------------------------------------------------
# Core calibration
# ---------------------------------------------------------------------------


def correct_dark_for_temperature(
    dark: np.ndarray,
    *,
    measurement_temp_c: float,
    reference_temp_c: float = DARK_REF_TEMP_C,
    coeff_per_c: float = DARK_TEMP_COEFF_PER_C,
) -> np.ndarray:
    """Adjust the dark frame for the probe's current temperature.

    Si CMOS dark current is exponential in temperature, but over the
    narrow operating range of the VERA probe (15–35 °C) a linear model
    is sufficient. The coefficient is measured per-pixel ideally; we
    use a single value as a conservative default.

    Parameters
    ----------
    dark
        Dark frame captured at ``reference_temp_c``.
    measurement_temp_c
        Probe temperature at the time of the live frame.
    reference_temp_c
        Temperature when ``dark`` was captured.
    coeff_per_c
        Counts per °C of dark current rise.

    Returns
    -------
    Adjusted dark frame, same shape as input.
    """
    delta_c = float(measurement_temp_c) - float(reference_temp_c)
    return np.asarray(dark, dtype=np.float64) + delta_c * coeff_per_c


def normalise_integration_time(
    raw: np.ndarray,
    *,
    integration_ms: float,
    target_ms: float,
) -> np.ndarray:
    """Linearly scale raw counts to a reference integration time.

    The C12880MA accumulates photoelectrons linearly over the integration
    window (until saturation), so doubling the integration time doubles
    the signal and the dark current. This function undoes that scaling
    so that frames captured at different integration times can be
    compared against the same calibration frames.

    Parameters
    ----------
    raw
        Raw counts. Shape: (..., N_SPEC).
    integration_ms
        Actual integration time of the live frame.
    target_ms
        Reference integration time (typically the dark/white frame time).

    Returns
    -------
    Scaled counts.
    """
    if integration_ms <= 0 or target_ms <= 0:
        raise ValueError("integration times must be positive")
    scale = float(target_ms) / float(integration_ms)
    return np.asarray(raw, dtype=np.float64) * scale


def calibrate_spectrum(
    raw: np.ndarray,
    *,
    integration_ms: float,
    temp_c: float,
    cal: CalibrationFrames,
    eps: float = 1e-6,
) -> np.ndarray:
    """Full calibration: raw counts → reflectance.

    Pipeline:

    1. Scale ``raw`` to match the dark/white reference integration time.
    2. Adjust the dark frame for the current temperature.
    3. Apply ``(raw - dark) / (white - dark)``.
    4. Clip to ``[0, REFL_CLIP_MAX]``.

    Saturated pixels (raw > SAT_THRESHOLD_COUNTS) are not flagged here —
    use :func:`detect_saturation` separately.

    Parameters
    ----------
    raw
        Raw counts from the live frame. Shape: (N_SPEC,) or (N, N_SPEC).
    integration_ms
        Integration time of the live frame, in ms.
    temp_c
        Probe temperature at the time of the live frame, in °C.
    cal
        Calibration frames captured before the session.
    eps
        Floor for the ``white - dark`` denominator to avoid division by
        zero on dead pixels.

    Returns
    -------
    Reflectance, same shape as ``raw``, clipped to ``[0, 1.5]``.
    """
    raw_arr = np.asarray(raw, dtype=np.float64)
    one_d = raw_arr.ndim == 1
    if one_d:
        raw_arr = raw_arr[None, :]
    if raw_arr.shape[-1] != N_SPEC:
        raise ValueError(
            f"raw must have last axis = {N_SPEC}, got {raw_arr.shape}"
        )

    # Step 1: scale raw counts to white-frame integration time
    target_ms = float(cal.white_integration_ms)
    raw_scaled = normalise_integration_time(
        raw_arr,
        integration_ms=integration_ms,
        target_ms=target_ms,
    )

    # Step 2: prepare dark and white at target_ms with temperature correction
    dark_scaled = normalise_integration_time(
        cal.dark,
        integration_ms=cal.dark_integration_ms,
        target_ms=target_ms,
    )
    dark_corrected = correct_dark_for_temperature(
        dark_scaled,
        measurement_temp_c=temp_c,
        reference_temp_c=cal.dark_temp_c,
    )
    white_scaled = normalise_integration_time(
        cal.white,
        integration_ms=cal.white_integration_ms,
        target_ms=target_ms,
    )

    # Step 3: dark subtraction + white reference division
    denom = white_scaled - dark_corrected
    denom = np.where(np.abs(denom) < eps, eps, denom)
    refl = (raw_scaled - dark_corrected[None, :]) / denom[None, :]

    # Step 4: clip
    refl = np.clip(refl, 0.0, REFL_CLIP_MAX)
    return refl[0] if one_d else refl


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------


def detect_saturation(
    raw: np.ndarray,
    *,
    threshold: int = SAT_THRESHOLD_COUNTS,
) -> np.ndarray:
    """Return a boolean mask of pixels that may be saturated.

    The C12880MA's 12-bit ADC tops out at 4095. Pixels above ``threshold``
    have lost their linear response and should not be trusted by the
    classifier. Bridge.py can use this to log warnings or to retry the
    scan with shorter integration time.
    """
    return np.asarray(raw) >= int(threshold)


def saturation_fraction(raw: np.ndarray, **kw) -> float:
    """Convenience: fraction of pixels at or above the saturation threshold."""
    mask = detect_saturation(raw, **kw)
    return float(mask.mean())


# ---------------------------------------------------------------------------
# Photometric correction (Lommel-Seeliger)
# ---------------------------------------------------------------------------


def lommel_seeliger_correction(
    refl: np.ndarray,
    *,
    incidence_deg: float,
    emission_deg: float,
) -> np.ndarray:
    """Lommel-Seeliger photometric normalization.

    Real-sample reflectance depends on the angle of illumination and
    viewing — the same mineral looks darker when lit obliquely. Lunar
    surface photometry uses the Lommel-Seeliger model as the simplest
    physically motivated correction:

        R_normalized = R_observed * (mu_0 + mu) / mu_0

    where ``mu_0 = cos(incidence)`` and ``mu = cos(emission)``. The
    factor goes to 1 at zero phase (head-on), making the corrected
    reflectance comparable to reference spectra captured under the same
    convention.

    For the VERA bench probe with normal-incidence illumination we
    typically don't need this — but real-world deployment over
    irregular regolith surfaces does. Apply it before passing reflectance
    into the classifier when the probe geometry isn't normal.

    Parameters
    ----------
    refl
        Reflectance values, any shape.
    incidence_deg
        Angle between the surface normal and the illumination direction.
    emission_deg
        Angle between the surface normal and the viewing direction.

    Returns
    -------
    Lommel-Seeliger-corrected reflectance, same shape as input.
    """
    mu0 = float(np.cos(np.radians(incidence_deg)))
    mu = float(np.cos(np.radians(emission_deg)))
    if mu0 < 1e-6:  # treat anything within ~0.01° of grazing as invalid
        raise ValueError(
            f"incidence_deg must give cos > 0 (got {incidence_deg}° → "
            f"mu0 = {mu0:.2e})"
        )
    factor = (mu0 + mu) / mu0
    return np.asarray(refl, dtype=np.float64) * factor


def lambertian_correction(
    refl: np.ndarray,
    *,
    incidence_deg: float,
) -> np.ndarray:
    """Lambertian photometric correction: divide by cos(incidence).

    Simpler than Lommel-Seeliger but valid for matte (Lambertian)
    surfaces under collimated illumination. Use this for white-reference
    measurements taken on a Spectralon tile where the surface is by
    construction near-Lambertian.
    """
    mu0 = float(np.cos(np.radians(incidence_deg)))
    if mu0 < 1e-6:
        raise ValueError(
            f"incidence_deg must give cos > 0 (got {incidence_deg}° → "
            f"mu0 = {mu0:.2e})"
        )
    return np.asarray(refl, dtype=np.float64) / mu0


# ---------------------------------------------------------------------------
# Per-pixel dark-current temperature coefficient fitting
# ---------------------------------------------------------------------------


def fit_dark_current_coefficients(
    dark_frames: np.ndarray,
    temperatures_c: np.ndarray,
    *,
    reference_temp_c: float = DARK_REF_TEMP_C,
) -> tuple[np.ndarray, np.ndarray]:
    """Fit per-pixel dark current vs. temperature on real bench data.

    For each of the ``N_SPEC`` pixels, fits

        dark_pixel(T) = intercept + slope * (T - reference_temp_c)

    via vectorised ordinary least squares. The intercept is the dark
    count at the reference temperature; the slope is the per-pixel
    counts-per-degree-Celsius coefficient. ``DARK_TEMP_COEFF_PER_C`` is
    a single scalar default — using the per-pixel slope from this fit
    is meaningfully more accurate (typical pixel-to-pixel spread is
    ±50% around the array mean).

    Parameters
    ----------
    dark_frames
        Stack of dark frames captured at known temperatures. Shape:
        ``(M, N_SPEC)``. Need at least 2 frames at distinct temperatures
        to fit a slope.
    temperatures_c
        Probe temperature when each frame was captured. Shape: ``(M,)``.
    reference_temp_c
        Reference temperature for the intercept (typically 22 °C).

    Returns
    -------
    intercept, slope : ndarray, ndarray
        Both shape ``(N_SPEC,)``. ``slope`` is in counts/°C.
    """
    df = np.asarray(dark_frames, dtype=np.float64)
    T = np.asarray(temperatures_c, dtype=np.float64) - float(reference_temp_c)
    if df.ndim != 2 or df.shape[1] != N_SPEC:
        raise ValueError(
            f"dark_frames must have shape (M, {N_SPEC}), got {df.shape}"
        )
    if T.shape != (df.shape[0],):
        raise ValueError(
            f"temperatures_c must be 1-D length {df.shape[0]}, got {T.shape}"
        )
    if T.shape[0] < 2:
        raise ValueError("need at least 2 temperatures to fit a slope")
    if np.allclose(T, T[0]):
        raise ValueError(
            "all temperatures are identical — cannot solve for slope"
        )

    # Build the design matrix once; solve all 288 pixels simultaneously.
    A = np.column_stack([np.ones_like(T), T])  # (M, 2)
    # lstsq returns (2, N_SPEC) when the RHS is (M, N_SPEC)
    coeffs, *_ = np.linalg.lstsq(A, df, rcond=None)
    intercept = coeffs[0].astype(np.float64)
    slope = coeffs[1].astype(np.float64)
    return intercept, slope


@dataclass(frozen=True)
class CalibrationProfile:
    """Persisted calibration capturing real-bench characterization.

    Distinct from ``CalibrationFrames``: that one holds two snapshots
    (dark + white) at fixed conditions. ``CalibrationProfile`` holds
    the *fitted* characterization — per-pixel dark slope from a
    multi-temperature sweep — so a single live frame can be calibrated
    at any operating temperature.
    """

    dark_intercept: np.ndarray   # (N_SPEC,) dark counts at reference_temp_c
    dark_slope: np.ndarray       # (N_SPEC,) counts per °C above reference
    white: np.ndarray            # (N_SPEC,) white reference counts
    white_integration_ms: float
    dark_integration_ms: float
    reference_temp_c: float = DARK_REF_TEMP_C
    n_temperatures_fitted: int = 0
    fit_residual_mean: float = 0.0  # mean abs residual across pixels (counts)

    def __post_init__(self) -> None:
        for name, arr in (
            ("dark_intercept", self.dark_intercept),
            ("dark_slope", self.dark_slope),
            ("white", self.white),
        ):
            a = np.asarray(arr)
            if a.ndim != 1 or a.shape[0] != N_SPEC:
                raise ValueError(
                    f"{name} must have shape ({N_SPEC},), got {a.shape}"
                )

    def save(self, path) -> None:
        from pathlib import Path
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez(
            path,
            dark_intercept=self.dark_intercept,
            dark_slope=self.dark_slope,
            white=self.white,
            white_integration_ms=self.white_integration_ms,
            dark_integration_ms=self.dark_integration_ms,
            reference_temp_c=self.reference_temp_c,
            n_temperatures_fitted=self.n_temperatures_fitted,
            fit_residual_mean=self.fit_residual_mean,
        )

    @classmethod
    def load(cls, path) -> CalibrationProfile:
        d = np.load(path)
        return cls(
            dark_intercept=d["dark_intercept"],
            dark_slope=d["dark_slope"],
            white=d["white"],
            white_integration_ms=float(d["white_integration_ms"]),
            dark_integration_ms=float(d["dark_integration_ms"]),
            reference_temp_c=float(d["reference_temp_c"]),
            n_temperatures_fitted=int(d.get("n_temperatures_fitted", 0)),
            fit_residual_mean=float(d.get("fit_residual_mean", 0.0)),
        )

    @classmethod
    def fit(
        cls,
        dark_frames: np.ndarray,
        dark_temperatures_c: np.ndarray,
        white: np.ndarray,
        *,
        white_integration_ms: float,
        dark_integration_ms: float,
        reference_temp_c: float = DARK_REF_TEMP_C,
    ) -> CalibrationProfile:
        """Convenience: run :func:`fit_dark_current_coefficients` and
        package the result in a ``CalibrationProfile`` with residual
        diagnostics."""
        intercept, slope = fit_dark_current_coefficients(
            dark_frames,
            dark_temperatures_c,
            reference_temp_c=reference_temp_c,
        )
        # Compute mean absolute residual (counts) for QA logging.
        T = np.asarray(dark_temperatures_c, dtype=np.float64) - reference_temp_c
        predicted = intercept[None, :] + T[:, None] * slope[None, :]
        residual = float(np.mean(np.abs(np.asarray(dark_frames, dtype=np.float64) - predicted)))
        return cls(
            dark_intercept=intercept,
            dark_slope=slope,
            white=np.asarray(white, dtype=np.float64),
            white_integration_ms=float(white_integration_ms),
            dark_integration_ms=float(dark_integration_ms),
            reference_temp_c=float(reference_temp_c),
            n_temperatures_fitted=int(np.asarray(dark_temperatures_c).shape[0]),
            fit_residual_mean=residual,
        )


def calibrate_with_profile(
    raw: np.ndarray,
    *,
    integration_ms: float,
    temp_c: float,
    profile: CalibrationProfile,
    eps: float = 1e-6,
) -> np.ndarray:
    """Calibrate a live frame using a fitted ``CalibrationProfile``.

    This is the production calibration entrypoint once a real bench
    sweep has been performed. It uses **per-pixel** dark slopes
    (from :class:`CalibrationProfile`) instead of the single scalar
    coefficient that :func:`calibrate_spectrum` falls back to.
    """
    raw_arr = np.asarray(raw, dtype=np.float64)
    one_d = raw_arr.ndim == 1
    if one_d:
        raw_arr = raw_arr[None, :]
    if raw_arr.shape[-1] != N_SPEC:
        raise ValueError(
            f"raw must have last axis = {N_SPEC}, got {raw_arr.shape}"
        )

    target_ms = profile.white_integration_ms

    # Scale live frame to target integration time
    raw_scaled = normalise_integration_time(
        raw_arr, integration_ms=integration_ms, target_ms=target_ms
    )

    # Per-pixel dark at the current temperature
    delta_T = float(temp_c) - profile.reference_temp_c
    dark_at_T = profile.dark_intercept + delta_T * profile.dark_slope
    dark_scaled = normalise_integration_time(
        dark_at_T,
        integration_ms=profile.dark_integration_ms,
        target_ms=target_ms,
    )

    # White reference (already at target_ms by definition)
    white = profile.white

    denom = white - dark_scaled
    denom = np.where(np.abs(denom) < eps, eps, denom)
    refl = (raw_scaled - dark_scaled[None, :]) / denom[None, :]
    refl = np.clip(refl, 0.0, REFL_CLIP_MAX)
    return refl[0] if one_d else refl


__all__ = [
    "DARK_REF_TEMP_C",
    "DARK_TEMP_COEFF_PER_C",
    "REFL_CLIP_MAX",
    "SAT_THRESHOLD_COUNTS",
    "CalibrationFrames",
    "CalibrationProfile",
    "calibrate_spectrum",
    "calibrate_with_profile",
    "correct_dark_for_temperature",
    "detect_saturation",
    "fit_dark_current_coefficients",
    "lambertian_correction",
    "lommel_seeliger_correction",
    "normalise_integration_time",
    "saturation_fraction",
]
