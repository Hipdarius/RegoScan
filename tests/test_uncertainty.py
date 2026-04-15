"""Tests for uncertainty quantification and OOD flagging."""

from __future__ import annotations

import numpy as np
import pytest

from vera.uncertainty import (
    BORDERLINE_MARGIN,
    ENTROPY_OOD_THRESHOLD,
    LOW_CONF_THRESHOLD,
    OOD_THRESHOLD,
    UncertaintyReport,
    classify_uncertainty,
    softmax_entropy,
    temperature_scale,
    top_k_margin,
)


# ---------------------------------------------------------------------------
# Entropy
# ---------------------------------------------------------------------------


def test_entropy_one_hot_is_zero():
    p = np.array([0.0, 1.0, 0.0, 0.0, 0.0, 0.0])
    assert softmax_entropy(p) == pytest.approx(0.0, abs=1e-9)


def test_entropy_uniform_is_log_K():
    K = 6
    p = np.ones(K) / K
    assert softmax_entropy(p) == pytest.approx(np.log(K), abs=1e-9)


def test_entropy_handles_zeros():
    # 1e-12 floor must keep log(0) finite.
    p = np.array([0.5, 0.5, 0.0, 0.0, 0.0, 0.0])
    e = softmax_entropy(p)
    assert np.isfinite(e)
    assert e == pytest.approx(np.log(2), abs=1e-9)


# ---------------------------------------------------------------------------
# Margin
# ---------------------------------------------------------------------------


def test_margin_one_hot_is_one():
    p = np.array([0.0, 1.0, 0.0])
    assert top_k_margin(p) == pytest.approx(1.0)


def test_margin_uniform_is_zero():
    p = np.array([1 / 3, 1 / 3, 1 / 3])
    assert top_k_margin(p) == pytest.approx(0.0)


def test_margin_handles_split():
    p = np.array([0.45, 0.45, 0.10])
    assert top_k_margin(p) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# classify_uncertainty status escalation
# ---------------------------------------------------------------------------


def _confident(idx: int = 0, K: int = 6) -> np.ndarray:
    """Build a near-one-hot probability vector."""
    p = np.full(K, 0.005)
    p[idx] = 1.0 - 0.005 * (K - 1)
    return p


def _split(K: int = 6) -> np.ndarray:
    """Build a borderline split between two classes.

    Top-1 vs top-2 margin < BORDERLINE_MARGIN (0.15) so the new
    escalation flags "borderline" before "low_confidence".
    """
    p = np.full(K, 0.001)
    p[0] = 0.55
    p[1] = 0.44
    return p / p.sum()


def _peaked_low_conf(K: int = 6) -> np.ndarray:
    """Diffuse-ish distribution: top-1 leads but max_prob is below the
    low-confidence threshold. Margin is wide so it's not "borderline";
    entropy is below the OOD threshold so it's not "likely_ood".
    """
    p = np.array([0.65, 0.15, 0.05, 0.05, 0.05, 0.05])
    return p / p.sum()


def test_status_nominal_for_confident():
    rep = classify_uncertainty(_confident())
    assert rep.status == "nominal"
    assert rep.is_trustworthy
    assert rep.confidence > 0.95


def test_status_borderline_for_close_split():
    rep = classify_uncertainty(_split())
    assert rep.status == "borderline"
    assert rep.is_trustworthy  # borderline still trustable, just narrow
    assert rep.margin < BORDERLINE_MARGIN


def test_status_low_confidence_for_diffuse_distribution():
    rep = classify_uncertainty(_peaked_low_conf())
    assert rep.status == "low_confidence"
    assert not rep.is_trustworthy


def test_status_likely_ood_for_uniform():
    p = np.full(6, 1 / 6)
    rep = classify_uncertainty(p)
    assert rep.status == "likely_ood"
    assert not rep.is_trustworthy


def test_status_likely_ood_when_confidence_below_ood():
    p = np.array([0.30, 0.20, 0.18, 0.17, 0.10, 0.05])
    rep = classify_uncertainty(p)
    assert rep.confidence < OOD_THRESHOLD
    assert rep.status == "likely_ood"


def test_uncertainty_report_fields():
    rep = classify_uncertainty(_confident())
    assert isinstance(rep, UncertaintyReport)
    assert 0.0 <= rep.confidence <= 1.0
    assert 0.0 <= rep.entropy <= np.log(6) + 1e-9
    assert 0.0 <= rep.margin <= 1.0


# ---------------------------------------------------------------------------
# Temperature scaling
# ---------------------------------------------------------------------------


def test_temperature_scale_T1_matches_softmax():
    logits = np.array([2.0, 1.0, 0.0])
    p = temperature_scale(logits, T=1.0)
    assert p.sum() == pytest.approx(1.0)
    # T=1 should match a hand-computed softmax
    e = np.exp(logits - logits.max())
    expected = e / e.sum()
    np.testing.assert_allclose(p, expected, atol=1e-6)


def test_temperature_scale_high_T_flattens():
    logits = np.array([5.0, 0.0, 0.0])
    p1 = temperature_scale(logits, T=1.0)
    p_hot = temperature_scale(logits, T=10.0)
    # Higher temperature → flatter distribution (max prob lower)
    assert p_hot[0] < p1[0]
    assert softmax_entropy(p_hot) > softmax_entropy(p1)


def test_temperature_scale_rejects_zero():
    with pytest.raises(ValueError):
        temperature_scale(np.array([1.0, 2.0]), T=0.0)
