"""Tests for the Spectral Angle Mapper baseline classifier."""

from __future__ import annotations

import numpy as np
import pytest

from vera.sam import SAMClassifier, spectral_angle, spectral_angles_batch


def test_angle_identical_vectors_is_zero():
    # arccos near 1 is numerically sensitive — use a loose tolerance.
    s = np.array([0.1, 0.5, 0.9])
    assert spectral_angle(s, s) == pytest.approx(0.0, abs=1e-6)


def test_angle_invariant_to_positive_scaling():
    s = np.array([0.1, 0.5, 0.9])
    a1 = spectral_angle(s, s)
    a2 = spectral_angle(s, 5.0 * s)
    # Both should be ~0 (within floating-point arccos noise)
    assert a1 == pytest.approx(0.0, abs=1e-6)
    assert a2 == pytest.approx(0.0, abs=1e-6)


def test_angle_orthogonal_vectors_is_pi_over_2():
    a = np.array([1.0, 0.0, 0.0])
    b = np.array([0.0, 1.0, 0.0])
    assert spectral_angle(a, b) == pytest.approx(np.pi / 2, abs=1e-9)


def test_angle_handles_zero_vector():
    a = np.array([0.0, 0.0, 0.0])
    b = np.array([1.0, 1.0, 1.0])
    # Should return pi/2 rather than NaN
    angle = spectral_angle(a, b)
    assert np.isfinite(angle)
    assert angle == pytest.approx(np.pi / 2, abs=1e-9)


def test_angle_shape_mismatch_raises():
    with pytest.raises(ValueError):
        spectral_angle(np.array([1.0, 2.0]), np.array([1.0, 2.0, 3.0]))


def test_batch_angles_shape():
    s_batch = np.random.RandomState(0).uniform(0, 1, size=(10, 50))
    refs = np.random.RandomState(1).uniform(0, 1, size=(6, 50))
    angles = spectral_angles_batch(s_batch, refs)
    assert angles.shape == (10, 6)


def test_batch_angles_match_loop():
    s_batch = np.random.RandomState(0).uniform(0, 1, size=(5, 20))
    refs = np.random.RandomState(1).uniform(0, 1, size=(3, 20))
    batch = spectral_angles_batch(s_batch, refs)
    for i in range(5):
        for j in range(3):
            scalar = spectral_angle(s_batch[i], refs[j])
            assert batch[i, j] == pytest.approx(scalar, abs=1e-9)


def test_classifier_predicts_pure_endmember():
    """A pure endmember spectrum should classify as itself.

    SAM is invariant to multiplicative scaling, so all-flat references
    that differ only in brightness collapse to the same direction in
    vector space. Real mineral spectra have *shape* differences (Fe2+
    bands, slope reversals, etc.) — we encode that here so the test
    actually exercises SAM's discriminative power.
    """
    refs = np.array([
        [0.10, 0.12, 0.11, 0.10, 0.11],     # ilmenite — flat with tiny noise
        [0.20, 0.45, 0.55, 0.40, 0.30],     # olivine — bump 700–850 nm
        [0.15, 0.30, 0.50, 0.70, 0.85],     # pyroxene — monotone rise
        [0.55, 0.65, 0.75, 0.85, 0.90],     # anorthite — gentle rise (bright)
        [0.05, 0.10, 0.18, 0.30, 0.45],     # glass — steep exp ramp
        [0.20, 0.30, 0.40, 0.45, 0.40],     # mixed — symmetric peak
    ])
    clf = SAMClassifier(references=refs)
    for i in range(6):
        result = clf.predict(refs[i])
        assert result["class_index"] == i, (
            f"row {i} ({clf.class_names[i]}) misclassified as "
            f"{clf.class_names[result['class_index']]}"
        )


def test_classifier_predict_returns_canonical_dict():
    refs = np.eye(6) + 0.1
    clf = SAMClassifier(references=refs)
    s = refs[2] + np.random.RandomState(0).normal(0, 0.01, 6)
    r = clf.predict(s)
    assert "class_index" in r
    assert "probabilities" in r
    assert "angle_deg" in r
    assert r["probabilities"].shape == (6,)
    assert abs(r["probabilities"].sum() - 1.0) < 1e-6


def test_classifier_batch_prediction():
    refs = np.eye(3) + 0.1
    clf = SAMClassifier(
        references=refs,
        class_names=("a", "b", "c"),
    )
    spectra = np.stack([refs[0], refs[1], refs[2], refs[0]])
    preds = clf.predict_batch(spectra)
    np.testing.assert_array_equal(preds, [0, 1, 2, 0])


def test_classifier_rejects_mismatched_class_count():
    refs = np.eye(3)
    with pytest.raises(ValueError):
        SAMClassifier(references=refs, class_names=("a", "b"))
