"""Tests for the SWIR-aware wire protocol in scripts/bridge.py.

These exercise the round-trip from mock_esp32-style frames through the
SensorFrame validation and into a feature vector. We keep this module
in tests/ rather than scripts/ so it gets picked up by the regular
pytest run.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

# scripts/ is not a package; add it to sys.path explicitly.
ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import bridge  # type: ignore  # noqa: E402

from vera.schema import N_AS7265X, N_LED, N_SPEC, N_SWIR


def _base_payload(*, with_as7=False, with_swir=False) -> dict:
    p = {
        "v": 1,
        "integration_time_ms": 100,
        "ambient_temp_c": 22.5,
        "spec": [0.1] * N_SPEC,
        "led": [0.5] * N_LED,
        "lif_450lp": 0.42,
    }
    if with_as7:
        p["as7"] = [0.3] * N_AS7265X
    if with_swir:
        p["swir"] = [0.4, 0.5]
    return p


# ---------------------------------------------------------------------------
# SensorFrame validation
# ---------------------------------------------------------------------------


def test_validate_frame_legacy_no_swir_no_as7():
    payload = _base_payload()
    frame, truth = bridge.validate_frame(json.dumps(payload))
    assert frame.swir is None
    assert frame.as7 is None
    assert truth is None


def test_validate_frame_with_swir_only():
    payload = _base_payload(with_swir=True)
    frame, _ = bridge.validate_frame(json.dumps(payload))
    assert frame.swir is not None
    assert len(frame.swir) == N_SWIR


def test_validate_frame_with_swir_and_as7():
    payload = _base_payload(with_as7=True, with_swir=True)
    frame, _ = bridge.validate_frame(json.dumps(payload))
    assert frame.swir is not None
    assert frame.as7 is not None


def test_validate_frame_rejects_wrong_swir_length():
    from pydantic import ValidationError

    payload = _base_payload(with_swir=True)
    payload["swir"] = [0.4, 0.5, 0.6]  # 3 values, expected 2
    with pytest.raises(ValidationError):
        bridge.validate_frame(json.dumps(payload))


# ---------------------------------------------------------------------------
# Feature vector construction
# ---------------------------------------------------------------------------


def test_feature_vector_legacy_full_mode():
    """spec + led + lif → 301 features."""
    payload = _base_payload()
    frame, _ = bridge.validate_frame(json.dumps(payload))
    feat = bridge.build_feature_vector(frame)
    assert feat.shape == (N_SPEC + N_LED + 1,)


def test_feature_vector_legacy_combined_mode():
    """spec + as7 + led + lif → 319 features."""
    payload = _base_payload(with_as7=True)
    frame, _ = bridge.validate_frame(json.dumps(payload))
    feat = bridge.build_feature_vector(frame)
    assert feat.shape == (N_SPEC + N_AS7265X + N_LED + 1,)


def test_feature_vector_swir_full_mode():
    """spec + swir + led + lif → 303 features (v1.2 full)."""
    payload = _base_payload(with_swir=True)
    frame, _ = bridge.validate_frame(json.dumps(payload))
    feat = bridge.build_feature_vector(frame)
    assert feat.shape == (N_SPEC + N_SWIR + N_LED + 1,)


def test_feature_vector_swir_combined_mode():
    """spec + as7 + swir + led + lif → 321 features (v1.2 combined)."""
    payload = _base_payload(with_as7=True, with_swir=True)
    frame, _ = bridge.validate_frame(json.dumps(payload))
    feat = bridge.build_feature_vector(frame)
    assert feat.shape == (N_SPEC + N_AS7265X + N_SWIR + N_LED + 1,)


def test_feature_vector_canonical_order():
    """Verify [spec | as7 | swir | led | lif] order."""
    payload = _base_payload(with_as7=True, with_swir=True)
    payload["spec"] = [0.1] * N_SPEC
    payload["as7"] = [0.2] * N_AS7265X
    payload["swir"] = [0.3, 0.31]
    payload["led"] = [0.4] * N_LED
    payload["lif_450lp"] = 0.5
    frame, _ = bridge.validate_frame(json.dumps(payload))
    feat = bridge.build_feature_vector(frame)
    # Spec block
    np.testing.assert_allclose(feat[:N_SPEC], 0.1)
    # AS7 block
    np.testing.assert_allclose(
        feat[N_SPEC : N_SPEC + N_AS7265X], 0.2
    )
    # SWIR block
    swir_start = N_SPEC + N_AS7265X
    np.testing.assert_allclose(feat[swir_start : swir_start + N_SWIR], [0.3, 0.31])
    # LED block
    led_start = swir_start + N_SWIR
    np.testing.assert_allclose(feat[led_start : led_start + N_LED], 0.4)
    # LIF
    assert feat[-1] == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Measurement assembly carries SWIR through
# ---------------------------------------------------------------------------


def test_frame_to_measurement_preserves_swir():
    payload = _base_payload(with_as7=True, with_swir=True)
    frame, _ = bridge.validate_frame(json.dumps(payload))
    m = bridge.frame_to_measurement(
        frame,
        sample_id="TEST",
        packing_density="medium",
        predicted_class="mixed",
        predicted_ilmenite=0.1,
    )
    assert m.swir == [0.4, 0.5]
    assert m.as7265x == [0.3] * N_AS7265X
    assert m.sensor_mode == "combined"
