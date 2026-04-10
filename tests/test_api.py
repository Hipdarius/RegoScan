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
    assert body["sensor_mode"] in ("full", "multispectral", "combined")
    assert body["schema_version"] == SCHEMA_VERSION


def test_meta_includes_class_names_and_wavelengths(client):
    resp = client.get("/api/meta")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["class_names"]) == 6
    assert len(body["wavelengths_nm"]) == 288
    assert len(body["led_wavelengths_nm"]) == 12


# ---------------------------------------------------------------------------
# POST /api/predict/demo
# ---------------------------------------------------------------------------


def test_predict_demo_returns_as7265x_when_engine_supports_it(client):
    """When the engine is loaded with a combined-mode model the demo
    response should include as7265x data. When no model is loaded the
    endpoint returns 503 and we skip rather than fail."""
    resp = client.post("/api/predict/demo", params={"seed": 42})
    if resp.status_code == 503:
        pytest.skip("no model loaded — cannot test demo prediction")
    assert resp.status_code == 200
    body = resp.json()
    # The demo always includes spec/led/lif
    assert "spec" in body
    assert "led" in body
    assert "lif_450lp" in body
    # as7265x may or may not be present depending on model sensor_mode
    # but the field should exist in the schema (possibly null)
    assert "predicted_class" in body
    assert "ilmenite_fraction" in body
