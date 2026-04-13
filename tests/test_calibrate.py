"""Tests for the hardware calibration pipeline."""

from __future__ import annotations

import numpy as np
import pytest

from vera.calibrate import (
    DARK_REF_TEMP_C,
    REFL_CLIP_MAX,
    SAT_THRESHOLD_COUNTS,
    CalibrationFrames,
    calibrate_spectrum,
    correct_dark_for_temperature,
    detect_saturation,
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
