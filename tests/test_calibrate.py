"""Tests for the hardware calibration pipeline."""

from __future__ import annotations

import numpy as np
import pytest

from vera.calibrate import (
    DARK_REF_TEMP_C,
    REFL_CLIP_MAX,
    SAT_THRESHOLD_COUNTS,
    CalibrationFrames,
    CalibrationProfile,
    calibrate_spectrum,
    calibrate_with_profile,
    correct_dark_for_temperature,
    detect_saturation,
    fit_dark_current_coefficients,
    lambertian_correction,
    lommel_seeliger_correction,
    normalise_integration_time,
    saturation_fraction,
)
from vera.schema import N_SPEC


def _flat_frame(value: float) -> np.ndarray:
    """Helper: build a flat (N_SPEC,) frame at the given count level."""
    return np.full(N_SPEC, value, dtype=np.float64)


def _basic_frames(*, dark: float = 100.0, white: float = 3000.0) -> CalibrationFrames:
    return CalibrationFrames(
        dark=_flat_frame(dark),
        white=_flat_frame(white),
        dark_integration_ms=10.0,
        white_integration_ms=10.0,
    )


# ---------------------------------------------------------------------------
# CalibrationFrames validation
# ---------------------------------------------------------------------------


def test_calframes_rejects_wrong_shape():
    with pytest.raises(ValueError):
        CalibrationFrames(
            dark=np.zeros(50),  # wrong length
            white=np.zeros(N_SPEC),
            dark_integration_ms=10.0,
            white_integration_ms=10.0,
        )


def test_calframes_rejects_zero_integration():
    with pytest.raises(ValueError):
        CalibrationFrames(
            dark=np.zeros(N_SPEC),
            white=np.zeros(N_SPEC),
            dark_integration_ms=0.0,
            white_integration_ms=10.0,
        )


# ---------------------------------------------------------------------------
# Integration time normalization
# ---------------------------------------------------------------------------


def test_integration_time_doubles_at_double_exposure():
    raw = _flat_frame(1000.0)
    out = normalise_integration_time(raw, integration_ms=20.0, target_ms=10.0)
    # 20 ms exposure → halved to match 10 ms reference
    np.testing.assert_allclose(out, 500.0)


def test_integration_time_no_change():
    raw = _flat_frame(1500.0)
    out = normalise_integration_time(raw, integration_ms=10.0, target_ms=10.0)
    np.testing.assert_allclose(out, raw)


def test_integration_time_rejects_negative():
    with pytest.raises(ValueError):
        normalise_integration_time(_flat_frame(1.0), integration_ms=-1.0, target_ms=10.0)


# ---------------------------------------------------------------------------
# Dark current temperature correction
# ---------------------------------------------------------------------------


def test_dark_temp_correction_adds_counts_above_reference():
    dark = _flat_frame(100.0)
    out = correct_dark_for_temperature(
        dark, measurement_temp_c=DARK_REF_TEMP_C + 10.0
    )
    # +10 °C * 2 counts/°C = +20 counts
    np.testing.assert_allclose(out, 120.0)


def test_dark_temp_correction_subtracts_below_reference():
    dark = _flat_frame(100.0)
    out = correct_dark_for_temperature(
        dark, measurement_temp_c=DARK_REF_TEMP_C - 5.0
    )
    np.testing.assert_allclose(out, 90.0)  # -5 °C * 2 = -10


# ---------------------------------------------------------------------------
# Full calibration
# ---------------------------------------------------------------------------


def test_calibrate_spectrum_white_returns_unity():
    cal = _basic_frames(dark=100.0, white=3000.0)
    # Bright frame matching the white reference → reflectance ≈ 1.0
    refl = calibrate_spectrum(
        _flat_frame(3000.0),
        integration_ms=cal.white_integration_ms,
        temp_c=DARK_REF_TEMP_C,
        cal=cal,
    )
    np.testing.assert_allclose(refl, 1.0, atol=1e-6)


def test_calibrate_spectrum_dark_returns_zero():
    cal = _basic_frames(dark=100.0, white=3000.0)
    refl = calibrate_spectrum(
        _flat_frame(100.0),
        integration_ms=cal.white_integration_ms,
        temp_c=DARK_REF_TEMP_C,
        cal=cal,
    )
    np.testing.assert_allclose(refl, 0.0, atol=1e-6)


def test_calibrate_spectrum_clips_negative_to_zero():
    cal = _basic_frames(dark=100.0, white=3000.0)
    # Dark < dark frame → would yield negative reflectance, clipped to 0
    refl = calibrate_spectrum(
        _flat_frame(50.0),
        integration_ms=cal.white_integration_ms,
        temp_c=DARK_REF_TEMP_C,
        cal=cal,
    )
    np.testing.assert_allclose(refl, 0.0)


def test_calibrate_spectrum_clips_above_max():
    cal = _basic_frames(dark=100.0, white=3000.0)
    # Brighter than white reference → would exceed 1.0; clipped to 1.5
    refl = calibrate_spectrum(
        _flat_frame(10000.0),
        integration_ms=cal.white_integration_ms,
        temp_c=DARK_REF_TEMP_C,
        cal=cal,
    )
    np.testing.assert_allclose(refl, REFL_CLIP_MAX)


def test_calibrate_spectrum_handles_integration_mismatch():
    # White at 10 ms, live at 20 ms → live raw should be halved before
    # subtraction, giving the same reflectance as if it were taken at 10 ms.
    cal = _basic_frames(dark=100.0, white=3000.0)
    refl_short = calibrate_spectrum(
        _flat_frame(1550.0),
        integration_ms=10.0,
        temp_c=DARK_REF_TEMP_C,
        cal=cal,
    )
    refl_long = calibrate_spectrum(
        _flat_frame(3100.0),  # 2x longer integration → 2x signal
        integration_ms=20.0,
        temp_c=DARK_REF_TEMP_C,
        cal=cal,
    )
    np.testing.assert_allclose(refl_short, refl_long, atol=1e-6)


def test_calibrate_spectrum_2d_batch():
    cal = _basic_frames()
    raw_batch = np.stack([_flat_frame(1500.0), _flat_frame(3000.0)])
    refl = calibrate_spectrum(
        raw_batch,
        integration_ms=cal.white_integration_ms,
        temp_c=DARK_REF_TEMP_C,
        cal=cal,
    )
    assert refl.shape == (2, N_SPEC)
    # First row ≈ 0.483, second row ≈ 1.0
    np.testing.assert_allclose(refl[1], 1.0, atol=1e-6)
    assert 0.4 < refl[0].mean() < 0.6


# ---------------------------------------------------------------------------
# Saturation detection
# ---------------------------------------------------------------------------


def test_detect_saturation_flags_high_pixels():
    raw = _flat_frame(2000.0)
    raw[10] = SAT_THRESHOLD_COUNTS + 100
    raw[20] = SAT_THRESHOLD_COUNTS - 100
    mask = detect_saturation(raw)
    assert mask[10]
    assert not mask[20]


def test_saturation_fraction():
    raw = _flat_frame(0.0)
    raw[:50] = 4095.0  # 50 pixels saturated out of 288
    frac = saturation_fraction(raw)
    assert frac == pytest.approx(50 / N_SPEC, abs=1e-9)


# ---------------------------------------------------------------------------
# Photometric correction
# ---------------------------------------------------------------------------


def test_lommel_seeliger_normal_incidence_normal_emission():
    """At normal incidence and emission, the L-S factor is (1+1)/1 = 2."""
    refl = np.array([0.5, 0.4])
    out = lommel_seeliger_correction(refl, incidence_deg=0.0, emission_deg=0.0)
    np.testing.assert_allclose(out, refl * 2.0)


def test_lommel_seeliger_oblique_brightens_dark_target():
    """At grazing emission, L-S factor approaches 1 — sample appears
    less corrected (because R_observed is already attenuated)."""
    refl = np.array([0.5])
    factor_normal = lommel_seeliger_correction(refl, incidence_deg=0.0, emission_deg=0.0)[0]
    factor_oblique = lommel_seeliger_correction(refl, incidence_deg=0.0, emission_deg=60.0)[0]
    # cos(60) = 0.5, so factor = (1 + 0.5)/1 = 1.5; less than 2.
    assert factor_oblique < factor_normal
    assert factor_oblique == pytest.approx(refl[0] * 1.5)


def test_lommel_seeliger_rejects_grazing_incidence():
    refl = np.array([0.5])
    with pytest.raises(ValueError):
        lommel_seeliger_correction(refl, incidence_deg=90.0, emission_deg=0.0)


def test_lambertian_corrects_oblique_illumination():
    refl = np.array([0.5])
    # Illuminated at 60° → cos = 0.5, so divide by 0.5 → doubles
    out = lambertian_correction(refl, incidence_deg=60.0)
    np.testing.assert_allclose(out, [1.0])


def test_lambertian_no_op_at_normal_incidence():
    refl = np.array([0.3, 0.7])
    out = lambertian_correction(refl, incidence_deg=0.0)
    np.testing.assert_allclose(out, refl)


def test_lambertian_rejects_grazing_incidence():
    with pytest.raises(ValueError):
        lambertian_correction(np.array([0.5]), incidence_deg=90.0)


# ---------------------------------------------------------------------------
# fit_dark_current_coefficients
# ---------------------------------------------------------------------------


def _synth_dark_sweep(
    n_temps: int = 5,
    *,
    base_intercept: float = 100.0,
    base_slope: float = 2.0,
    pixel_variation: float = 0.5,
    seed: int = 0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Build a synthetic dark sweep with known per-pixel slopes.

    Returns (frames, temps, true_intercept, true_slope).
    """
    rng = np.random.default_rng(seed)
    temps = np.linspace(15.0, 35.0, n_temps)
    # Per-pixel coefficients with realistic variation
    true_intercept = base_intercept + rng.normal(0, 5.0, size=N_SPEC)
    true_slope = base_slope + rng.normal(0, base_slope * pixel_variation, size=N_SPEC)
    # Build frames (no noise — exact fit case)
    delta = temps - DARK_REF_TEMP_C
    frames = true_intercept[None, :] + delta[:, None] * true_slope[None, :]
    return frames, temps, true_intercept, true_slope


def test_fit_dark_current_recovers_known_coefficients():
    """No-noise synthetic sweep must recover the exact slopes/intercepts."""
    frames, temps, true_intercept, true_slope = _synth_dark_sweep(n_temps=5)
    intercept, slope = fit_dark_current_coefficients(frames, temps)
    np.testing.assert_allclose(intercept, true_intercept, atol=1e-9)
    np.testing.assert_allclose(slope, true_slope, atol=1e-9)


def test_fit_dark_current_handles_noise():
    """With Gaussian read noise the fit recovers slopes within tolerance."""
    frames, temps, true_int, true_slope = _synth_dark_sweep(n_temps=8)
    rng = np.random.default_rng(42)
    frames_noisy = frames + rng.normal(0, 0.5, size=frames.shape)
    intercept, slope = fit_dark_current_coefficients(frames_noisy, temps)
    # Slopes recovered to within a few % of the noise-free truth
    np.testing.assert_allclose(slope, true_slope, atol=0.3)


def test_fit_dark_current_rejects_single_temp():
    frames = np.zeros((1, N_SPEC))
    temps = np.array([22.0])
    with pytest.raises(ValueError, match="at least 2"):
        fit_dark_current_coefficients(frames, temps)


def test_fit_dark_current_rejects_identical_temps():
    """Cannot solve for slope when ΔT = 0."""
    frames = np.zeros((3, N_SPEC))
    temps = np.array([22.0, 22.0, 22.0])
    with pytest.raises(ValueError, match="identical"):
        fit_dark_current_coefficients(frames, temps)


def test_fit_dark_current_rejects_wrong_shape():
    with pytest.raises(ValueError):
        fit_dark_current_coefficients(np.zeros((3, 50)), np.array([15.0, 22.0, 30.0]))


# ---------------------------------------------------------------------------
# CalibrationProfile
# ---------------------------------------------------------------------------


def test_profile_fit_packages_per_pixel_slope():
    frames, temps, _, true_slope = _synth_dark_sweep(n_temps=5)
    white = _flat_frame(3000.0)
    profile = CalibrationProfile.fit(
        frames,
        temps,
        white,
        white_integration_ms=10.0,
        dark_integration_ms=10.0,
    )
    assert profile.n_temperatures_fitted == 5
    assert profile.dark_slope.shape == (N_SPEC,)
    np.testing.assert_allclose(profile.dark_slope, true_slope, atol=1e-9)
    assert profile.fit_residual_mean < 1e-6  # no-noise case


def test_profile_save_load_roundtrip(tmp_path):
    frames, temps, _, _ = _synth_dark_sweep(n_temps=4)
    profile = CalibrationProfile.fit(
        frames,
        temps,
        _flat_frame(3000.0),
        white_integration_ms=10.0,
        dark_integration_ms=10.0,
    )
    out = tmp_path / "cal.npz"
    profile.save(out)
    reloaded = CalibrationProfile.load(out)
    np.testing.assert_allclose(reloaded.dark_intercept, profile.dark_intercept)
    np.testing.assert_allclose(reloaded.dark_slope, profile.dark_slope)
    np.testing.assert_allclose(reloaded.white, profile.white)
    assert reloaded.white_integration_ms == profile.white_integration_ms
    assert reloaded.n_temperatures_fitted == profile.n_temperatures_fitted


def test_calibrate_with_profile_white_returns_unity():
    frames, temps, _, _ = _synth_dark_sweep(n_temps=3)
    white = _flat_frame(3000.0)
    profile = CalibrationProfile.fit(
        frames, temps, white, white_integration_ms=10.0, dark_integration_ms=10.0
    )
    refl = calibrate_with_profile(
        white,
        integration_ms=10.0,
        temp_c=DARK_REF_TEMP_C,
        profile=profile,
    )
    np.testing.assert_allclose(refl, 1.0, atol=1e-6)


def test_calibrate_with_profile_uses_per_pixel_slope():
    """Two pixels with very different slopes should produce different
    reflectance values at elevated temperature even when given identical
    raw counts — proves the per-pixel slope is being applied."""
    frames = np.zeros((3, N_SPEC), dtype=np.float64)
    # Pixel 0: slope = 0 counts/°C; Pixel 1: slope = 20 counts/°C
    delta_T = np.array([-7.0, 0.0, 13.0])  # T = 15, 22, 35
    frames[:, 0] = 100.0 + delta_T * 0.0     # Always 100
    frames[:, 1] = 100.0 + delta_T * 20.0    # 100 → 240 → 360 counts
    # Other pixels constant
    frames[:, 2:] = 100.0

    profile = CalibrationProfile.fit(
        frames,
        np.array([15.0, 22.0, 35.0]),
        np.full(N_SPEC, 3000.0),
        white_integration_ms=10.0,
        dark_integration_ms=10.0,
    )
    # Same raw frame at high temperature: pixel 1 should subtract more dark
    raw = np.full(N_SPEC, 1000.0)
    refl_hot = calibrate_with_profile(
        raw, integration_ms=10.0, temp_c=35.0, profile=profile
    )
    # Pixel 0 has zero slope → dark stays at 100
    # Pixel 1 has 20 counts/°C → dark = 100 + 13*20 = 360 at 35°C
    # So pixel 1's reflectance must be lower than pixel 0's
    assert refl_hot[1] < refl_hot[0]
