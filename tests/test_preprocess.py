"""Tests for the preprocessing primitives."""

from __future__ import annotations

import numpy as np
import pytest

from vera.preprocess import (
    apply_standardise,
    asls_baseline,
    asls_baseline_batch,
    continuum_removal,
    continuum_removal_batch,
    first_derivative,
    reflectance_normalise,
    savgol_smooth,
    standardise,
)
from vera.schema import N_SPEC, WAVELENGTHS

# ---------------------------------------------------------------------------
# reflectance_normalise
# ---------------------------------------------------------------------------


def test_reflectance_normalise_basic():
    rng = np.random.default_rng(0)
    raw = rng.uniform(100, 200, size=(4, N_SPEC))
    dark = np.full(N_SPEC, 50.0)
    white = np.full(N_SPEC, 250.0)
    out = reflectance_normalise(raw, dark, white)
    assert out.shape == (4, N_SPEC)
    assert np.all(out >= 0) and np.all(out <= 1.5)
    # for raw=150 → (150-50)/(250-50) = 0.5
    raw2 = np.full((1, N_SPEC), 150.0)
    out2 = reflectance_normalise(raw2, dark, white)
    np.testing.assert_allclose(out2, 0.5)


def test_reflectance_normalise_handles_degenerate_white():
    raw = np.full((1, N_SPEC), 100.0)
    dark = np.full(N_SPEC, 50.0)
    white = np.full(N_SPEC, 50.0)  # white == dark
    out = reflectance_normalise(raw, dark, white)
    assert np.all(np.isfinite(out))


def test_reflectance_normalise_shape_mismatch_raises():
    with pytest.raises(ValueError):
        reflectance_normalise(
            np.zeros((2, 100)), np.zeros(50), np.ones(100)
        )


# ---------------------------------------------------------------------------
# Savitzky-Golay
# ---------------------------------------------------------------------------


def test_savgol_smooth_preserves_shape():
    rng = np.random.default_rng(1)
    x = rng.uniform(0, 1, size=(3, N_SPEC))
    y = savgol_smooth(x, window_length=11, polyorder=3)
    assert y.shape == x.shape


def test_savgol_smooth_actually_smooths():
    rng = np.random.default_rng(2)
    base = np.sin(np.linspace(0, 4 * np.pi, N_SPEC))
    noisy = base + rng.normal(0, 0.2, size=N_SPEC)
    smoothed = savgol_smooth(noisy[None, :], window_length=21, polyorder=3)[0]
    assert np.std(smoothed - base) < np.std(noisy - base)


def test_first_derivative_of_linear_is_constant():
    x = np.linspace(0, 1, N_SPEC)
    y = (3.0 * x)[None, :]  # slope 3 / N_SPEC per pixel
    d = first_derivative(y, window_length=11)[0]
    interior = d[20:-20]
    # interior should be approximately constant (relative std < 1%)
    assert np.std(interior) / (np.abs(np.mean(interior)) + 1e-9) < 0.05


def test_savgol_invalid_window_raises():
    x = np.zeros((1, N_SPEC))
    with pytest.raises(ValueError):
        savgol_smooth(x, window_length=10, polyorder=3)
    with pytest.raises(ValueError):
        savgol_smooth(x, window_length=5, polyorder=5)


# ---------------------------------------------------------------------------
# AsLS baseline
# ---------------------------------------------------------------------------


def test_asls_baseline_smaller_than_signal_with_peak():
    """A spectrum with a positive bump should have a baseline below the peak."""
    x = np.linspace(0, 1, 200)
    baseline_true = 0.2 + 0.3 * x
    peak = 0.4 * np.exp(-((x - 0.5) ** 2) / (2 * 0.03**2))
    y = baseline_true + peak
    z = asls_baseline(y, lam=1e4, p=0.01, n_iter=10)
    assert z.shape == y.shape
    # baseline should NOT track the peak — should stay near baseline_true at x=0.5
    assert z[100] < y[100] - 0.10
    # baseline should be roughly correct at the edges
    assert abs(z[0] - baseline_true[0]) < 0.1
    assert abs(z[-1] - baseline_true[-1]) < 0.1


def test_asls_baseline_batch_shape():
    rng = np.random.default_rng(3)
    x = rng.uniform(0.2, 0.8, size=(3, 100))
    z = asls_baseline_batch(x, lam=1e3, p=0.05, n_iter=5)
    assert z.shape == x.shape


# ---------------------------------------------------------------------------
# Continuum removal
# ---------------------------------------------------------------------------


def test_continuum_removal_flat_spectrum_is_one():
    y = np.full(N_SPEC, 0.7)
    cr = continuum_removal(y, WAVELENGTHS)
    np.testing.assert_allclose(cr, 1.0)


def test_continuum_removal_dip_below_one():
    y = np.full(N_SPEC, 0.7)
    # carve a Gaussian-ish absorption around the centre
    centre = N_SPEC // 2
    for i in range(N_SPEC):
        y[i] -= 0.3 * np.exp(-((i - centre) ** 2) / (2 * 10.0**2))
    cr = continuum_removal(y, WAVELENGTHS)
    assert cr.shape == y.shape
    # the dip must remain a dip after CR
    assert cr[centre] < 0.95
    # endpoints lie on the hull, so CR there ≈ 1
    assert abs(cr[0] - 1.0) < 1e-6
    assert abs(cr[-1] - 1.0) < 1e-6


def test_continuum_removal_batch_matches_single():
    rng = np.random.default_rng(4)
    spec = rng.uniform(0.2, 0.8, size=(3, N_SPEC))
    out_batch = continuum_removal_batch(spec, WAVELENGTHS)
    for i in range(3):
        np.testing.assert_allclose(
            out_batch[i], continuum_removal(spec[i], WAVELENGTHS)
        )


# ---------------------------------------------------------------------------
# Standardise
# ---------------------------------------------------------------------------


def test_standardise_zero_mean_unit_std():
    rng = np.random.default_rng(5)
    x = rng.uniform(0, 10, size=(50, 6))
    z, mean, std = standardise(x, axis=0)
    assert z.shape == x.shape
    np.testing.assert_allclose(z.mean(axis=0), 0.0, atol=1e-12)
    np.testing.assert_allclose(z.std(axis=0), 1.0, atol=1e-9)
    # apply on the same data should reproduce z
    z2 = apply_standardise(x, mean, std)
    np.testing.assert_allclose(z, z2)


def test_standardise_handles_constant_columns():
    x = np.zeros((10, 4))
    z, mean, std = standardise(x, axis=0)
    assert np.all(np.isfinite(z))
