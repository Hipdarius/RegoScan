"""Tests for Hapke nonlinear (intimate) mixing."""

from __future__ import annotations

import numpy as np
import pytest

from vera.synth import (
    mix_spectra,
    mixture_spectrum_hapke,
    reflectance_to_ssa,
    ssa_to_reflectance,
)

# ---------------------------------------------------------------------------
# Reflectance ↔ SSA roundtrip
# ---------------------------------------------------------------------------


def test_ssa_roundtrip_full_range():
    R = np.linspace(0.0, 0.99, 100)
    R2 = ssa_to_reflectance(reflectance_to_ssa(R))
    np.testing.assert_allclose(R, R2, atol=1e-10)


def test_ssa_R_zero_gives_w_zero():
    assert reflectance_to_ssa(np.array([0.0])) == pytest.approx(0.0)


def test_ssa_R_high_gives_w_high():
    # R close to 1 should give w close to 1 (perfect scatterer)
    w = reflectance_to_ssa(np.array([0.99]))[0]
    assert w > 0.99


def test_ssa_clips_R_above_1():
    # Robustness: don't crash on out-of-range inputs
    w = reflectance_to_ssa(np.array([1.5]))
    assert np.isfinite(w).all()


# ---------------------------------------------------------------------------
# Hapke mixing reduces brightness vs linear
# ---------------------------------------------------------------------------


def test_hapke_50_50_dark_bright_is_darker_than_linear():
    """Intimate mix of bright + dark mineral should be substantially
    darker than the linear average — that's the whole point of Hapke
    mixing for fine regolith.
    """
    fracs = np.array([0.5, 0.5])
    em = np.array([
        np.full(10, 0.80),  # bright (anorthite-like)
        np.full(10, 0.05),  # dark (ilmenite-like)
    ])
    linear = mix_spectra(fracs, em, model="linear")
    hapke = mix_spectra(fracs, em, model="hapke")
    # Linear average is 0.425; Hapke should be significantly less.
    assert linear[0] == pytest.approx(0.425, abs=1e-9)
    assert hapke[0] < linear[0] * 0.7  # at least 30% darker


def test_hapke_pure_endmember_recovers_input():
    """100% of one endmember should give back exactly that endmember's
    reflectance (no mixing happens)."""
    em = np.array([
        np.array([0.4, 0.5, 0.6]),
        np.array([0.1, 0.1, 0.1]),
    ])
    pure_a = mixture_spectrum_hapke(np.array([1.0, 0.0]), em)
    np.testing.assert_allclose(pure_a, em[0], atol=1e-10)
    pure_b = mixture_spectrum_hapke(np.array([0.0, 1.0]), em)
    np.testing.assert_allclose(pure_b, em[1], atol=1e-10)


def test_hapke_equals_linear_when_all_equal():
    """If all endmembers have identical spectra, linear and Hapke
    should produce the same result."""
    em = np.tile(np.array([[0.5, 0.5, 0.5]]), (3, 1))
    fracs = np.array([0.3, 0.4, 0.3])
    linear = mix_spectra(fracs, em, model="linear")
    hapke = mix_spectra(fracs, em, model="hapke")
    np.testing.assert_allclose(linear, hapke, atol=1e-10)


def test_hapke_preserves_shape():
    em = np.random.RandomState(0).uniform(0.05, 0.85, size=(5, 50))
    fracs = np.array([0.2, 0.3, 0.1, 0.3, 0.1])
    out = mixture_spectrum_hapke(fracs, em)
    assert out.shape == (50,)
    assert (out >= 0).all()
    assert (out <= 1).all()


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


def test_mix_spectra_linear_matches_legacy():
    em = np.random.RandomState(1).uniform(0.05, 0.85, size=(3, 20))
    fracs = np.array([0.5, 0.3, 0.2])
    direct = mix_spectra(fracs, em, model="linear")
    legacy = fracs @ em
    np.testing.assert_allclose(direct, legacy, atol=1e-10)


def test_mix_spectra_unknown_model_raises():
    with pytest.raises(ValueError):
        mix_spectra(np.array([1.0]), np.array([[0.5]]), model="bogus")


def test_hapke_endmember_shape_mismatch():
    with pytest.raises(ValueError):
        mixture_spectrum_hapke(
            fractions=np.array([0.5, 0.5]),
            endmember_spectra=np.array([0.1, 0.2, 0.3]),  # 1D, wrong shape
        )
