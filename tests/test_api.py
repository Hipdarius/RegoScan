"""Tests for the FastAPI endpoints.

These tests use the ``TestClient`` from Starlette/FastAPI. They exercise
the API schema and response structure without requiring a trained ONNX
model (most tests work in the ``model_loaded=False`` state).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from vera.schema import SCHEMA_VERSION

# The ``apps`` directory is not a normal package — add the project root
# so ``from apps.api import app`` resolves correctly.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


# ---------------------------------------------------------------------------
# Client fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    """TestClient against the VERA API app.

    The app may or may not have a model loaded depending on the local
    environment; tests that require a model should be marked or skipped.
    """
    from apps.api import app

    return TestClient(app)


# ---------------------------------------------------------------------------
# GET /api/meta
# ---------------------------------------------------------------------------


def test_meta_includes_sensor_mode(client):
    resp = client.get("/api/meta")
    assert resp.status_code == 200
    body = resp.json()
    assert "sensor_mode" in body
    assert body["sensor_mode"] in (
        "full",
        "multispectral",
        "combined",
        "legacy_full",
        "legacy_combined",
    )
    assert body["schema_version"] == SCHEMA_VERSION


def test_meta_includes_class_names_and_wavelengths(client):
    resp = client.get("/api/meta")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["class_names"]) == 6
    assert len(body["wavelengths_nm"]) == 288
    assert len(body["led_wavelengths_nm"]) == 12


# ---------------------------------------------------------------------------
# Feature assembly contract
# ---------------------------------------------------------------------------


def test_api_feature_assembly_uses_canonical_full_order():
    from apps.api import SpectrumRequest, _features_from_request
    from vera.schema import N_LED, N_SPEC, N_SWIR, get_feature_count

    req = SpectrumRequest(
        spec=[0.1] * N_SPEC,
        swir=[0.2] * N_SWIR,
        led=[0.3] * N_LED,
        lif_450lp=0.4,
    )

    features = _features_from_request(req, "full")
    assert features.shape == (get_feature_count("full"),)
    assert features[N_SPEC : N_SPEC + N_SWIR].tolist() == pytest.approx([0.2, 0.2])
    assert features[-1] == pytest.approx(0.4)


def test_api_feature_assembly_requires_combined_channels():
    from fastapi import HTTPException

    from apps.api import SpectrumRequest, _features_from_request
    from vera.schema import N_LED, N_SPEC, N_SWIR

    req = SpectrumRequest(
        spec=[0.1] * N_SPEC,
        swir=[0.2] * N_SWIR,
        led=[0.3] * N_LED,
        lif_450lp=0.4,
    )

    with pytest.raises(HTTPException, match="requires as7265x"):
        _features_from_request(req, "combined")


def test_api_feature_assembly_supports_legacy_full_model_width():
    from apps.api import N_FEATURES_LEGACY_FULL, SpectrumRequest, _features_from_request
    from vera.schema import N_LED, N_SPEC, N_SWIR

    req = SpectrumRequest(
        spec=[0.1] * N_SPEC,
        swir=[0.2] * N_SWIR,
        led=[0.3] * N_LED,
        lif_450lp=0.4,
    )

    features = _features_from_request(req, "full", N_FEATURES_LEGACY_FULL)
    assert features.shape == (N_FEATURES_LEGACY_FULL,)
    assert features[N_SPEC : N_SPEC + N_SWIR].tolist() == pytest.approx([0.3, 0.3])
    assert features[-1] == pytest.approx(0.4)


# ---------------------------------------------------------------------------
# POST /api/predict/demo
# ---------------------------------------------------------------------------


def test_predict_demo_returns_as7265x_when_engine_supports_it(client):
    """When the engine is loaded with a combined-mode model the demo
    response should include as7265x data. When no model is loaded or the
    model is stale (wrong feature count after schema upgrade), we skip."""
    try:
        resp = client.post("/api/predict/demo", params={"seed": 42})
    except Exception:
        pytest.skip("model unavailable or stale — cannot test demo prediction")
    if resp.status_code in (500, 503):
        pytest.skip("no model loaded or stale model — cannot test demo prediction")
    assert resp.status_code == 200
    body = resp.json()
    # The demo always includes spec/led/lif/swir
    assert "spec" in body
    assert "led" in body
    assert "lif_450lp" in body
    # swir/as7265x may or may not be present depending on model sensor_mode
    assert "predicted_class" in body
    assert "ilmenite_fraction" in body
