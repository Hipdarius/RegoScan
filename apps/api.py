"""FastAPI backend for the VERA web UI.

Exposes a thin JSON API wrapped around the trained 1D ResNet. Inference
uses ``onnxruntime`` rather than torch so this module stays lightweight
enough to run on Vercel serverless (torch is too large for the Python
runtime size budget).

Endpoints
---------
GET  /healthz                       liveness probe + model checksum
GET  /api/meta                      class names, wavelengths, schema info
POST /api/predict                   full-feature inference from JSON
POST /api/predict/demo              synthesize a random spectrum + predict
GET  /api/endmembers                USGS-style endmember spectra for display

Run locally:

    uv run uvicorn apps.api:app --reload --port 8000

The same ``predict_from_features`` helper is imported by the Vercel
serverless handler at ``web/api/predict.py`` so there is exactly one
code path for inference regardless of deployment target.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Ensure the in-repo src/ is importable when running from the project root.
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from vera.inference import (  # noqa: E402
    InferenceEngine,
    load_endmembers_payload,
    synth_demo_features,
)
from vera.schema import (  # noqa: E402
    AS7265X_BANDS,
    LED_WAVELENGTHS_NM,
    MINERAL_CLASSES,
    N_AS7265X,
    N_FEATURES_TOTAL,
    N_LED,
    N_SPEC,
    SCHEMA_VERSION,
    SENSOR_MODES,
    SensorMode,
    WAVELENGTHS,
    get_feature_count,
)


# ---------------------------------------------------------------------------
# Model location resolution
# ---------------------------------------------------------------------------
#
# Priority: VERA_MODEL_DIR env var > runs/cnn_v2 > runs/cnn_run
# A warning is printed (not raised) at import time so the API can still
# boot for docs/health even if the model is missing.

_DEFAULT_RUN_CANDIDATES = [
    ROOT / "runs" / "cnn_v2",
    ROOT / "runs" / "cnn_run",
]


def _resolve_run_dir() -> Path | None:
    env = os.environ.get("VERA_MODEL_DIR")
    if env:
        p = Path(env)
        if (p / "model.onnx").exists():
            return p
        print(f"[warn] VERA_MODEL_DIR={env} does not contain model.onnx")
    for candidate in _DEFAULT_RUN_CANDIDATES:
        if (candidate / "model.onnx").exists():
            return candidate
    return None


_RUN_DIR = _resolve_run_dir()
_ENGINE: InferenceEngine | None = None
if _RUN_DIR is not None:
    try:
        _ENGINE = InferenceEngine(_RUN_DIR / "model.onnx")
        print(f"[ok] loaded ONNX model from {_RUN_DIR / 'model.onnx'}")
    except Exception as e:  # pragma: no cover — surfaced via /healthz
        print(f"[err] failed to init inference engine: {e}")
else:
    print("[warn] no trained run directory found — /api/predict will 503")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------


app = FastAPI(
    title="VERA API",
    version="0.2.0",
    description="Mineral classification + ilmenite regression from VIS/NIR spectra",
)

# CORS: permissive in dev. The Next.js frontend on Vercel uses a same-origin
# rewrite (see vercel.json), so in prod the browser won't hit this directly.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class SpectrumRequest(BaseModel):
    """One VIS/NIR measurement, in the canonical feature order.

    ``spec`` is 288 floats on the C12880MA grid (340–850 nm). ``led`` is
    12 narrow-band reflectance values. ``lif_450lp`` is the 450 nm
    longpass fluorescence channel under 405 nm excitation.  ``as7265x``
    is an optional 18-float array from the AS7265x triad sensor.
    """

    spec: list[float] = Field(min_length=N_SPEC, max_length=N_SPEC)
    led: list[float] = Field(min_length=N_LED, max_length=N_LED)
    lif_450lp: float
    as7265x: list[float] | None = None


class ClassProbability(BaseModel):
    name: str
    probability: float


class PredictionResponse(BaseModel):
    predicted_class: str
    predicted_class_index: int
    probabilities: list[ClassProbability]
    ilmenite_fraction: float
    confidence: float
    model_version: str


class DemoResponse(PredictionResponse):
    spec: list[float]
    led: list[float]
    lif_450lp: float
    as7265x: list[float] | None = None
    true_class: str
    true_ilmenite_fraction: float


class MetaResponse(BaseModel):
    schema_version: str
    class_names: list[str]
    wavelengths_nm: list[float]
    led_wavelengths_nm: list[int]
    n_features_total: int
    model_loaded: bool
    model_sha256: str | None
    model_run_dir: str | None
    sensor_mode: str
    as7265x_bands_nm: list[int] | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _require_engine() -> InferenceEngine:
    if _ENGINE is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "no model loaded; train one with "
                "`uv run python -m vera.train --model cnn --data <csv> --out runs/cnn_v2` "
                "and export ONNX with `vera.quantize`"
            ),
        )
    return _ENGINE


def _model_sha256() -> str | None:
    if _RUN_DIR is None:
        return None
    onnx_path = _RUN_DIR / "model.onnx"
    if not onnx_path.exists():
        return None
    h = hashlib.sha256()
    with open(onnx_path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def _to_prediction(
    features: np.ndarray, *, extras: dict[str, Any] | None = None
) -> dict[str, Any]:
    engine = _require_engine()
    result = engine.predict(features)
    payload = {
        "predicted_class": MINERAL_CLASSES[result["class_index"]],
        "predicted_class_index": int(result["class_index"]),
        "probabilities": [
            {"name": MINERAL_CLASSES[i], "probability": float(p)}
            for i, p in enumerate(result["probabilities"])
        ],
        "ilmenite_fraction": float(result["ilmenite_fraction"]),
        "confidence": float(result["probabilities"][result["class_index"]]),
        "model_version": engine.version,
    }
    if extras is not None:
        payload.update(extras)
    return payload


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    return {
        "status": "ok" if _ENGINE is not None else "degraded",
        "model_loaded": _ENGINE is not None,
        "schema_version": SCHEMA_VERSION,
    }


@app.get("/api/meta", response_model=MetaResponse)
def meta() -> MetaResponse:
    # Determine the sensor mode from the loaded engine's metadata,
    # defaulting to "full" if no model is loaded.
    sensor_mode = "full"
    as7265x_bands: list[int] | None = None

    # If a model is loaded and exposes a sensor_mode attribute, use it
    if _ENGINE is not None and hasattr(_ENGINE, "sensor_mode"):
        sensor_mode = _ENGINE.sensor_mode  # type: ignore[attr-defined]

    # Include AS7265x band wavelengths when the mode uses the triad sensor
    if sensor_mode in ("multispectral", "combined"):
        as7265x_bands = list(AS7265X_BANDS)

    return MetaResponse(
        schema_version=SCHEMA_VERSION,
        class_names=list(MINERAL_CLASSES),
        wavelengths_nm=[float(w) for w in WAVELENGTHS],
        led_wavelengths_nm=list(LED_WAVELENGTHS_NM),
        n_features_total=get_feature_count(sensor_mode),
        model_loaded=_ENGINE is not None,
        model_sha256=_model_sha256(),
        model_run_dir=str(_RUN_DIR) if _RUN_DIR is not None else None,
        sensor_mode=sensor_mode,
        as7265x_bands_nm=as7265x_bands,
    )


@app.post("/api/predict", response_model=PredictionResponse)
def predict(req: SpectrumRequest) -> dict[str, Any]:
    # Build the feature vector based on which channels are present.
    # The order must match the training schema: [spec, as7265x, led, lif].
    parts: list[np.ndarray] = [
        np.asarray(req.spec, dtype=np.float32),
    ]
    if req.as7265x is not None:
        if len(req.as7265x) != N_AS7265X:
            raise HTTPException(
                status_code=400,
                detail=f"as7265x must have exactly {N_AS7265X} values, got {len(req.as7265x)}",
            )
        parts.append(np.asarray(req.as7265x, dtype=np.float32))
    parts.extend([
        np.asarray(req.led, dtype=np.float32),
        np.asarray([req.lif_450lp], dtype=np.float32),
    ])
    features = np.concatenate(parts)

    # Determine expected feature count based on what was provided
    expected_mode = "combined" if req.as7265x is not None else "full"
    expected_count = get_feature_count(expected_mode)
    if features.shape[0] != expected_count:
        raise HTTPException(
            status_code=400,
            detail=f"expected {expected_count} features (mode={expected_mode}), got {features.shape[0]}",
        )
    return _to_prediction(features)


@app.post("/api/predict/demo", response_model=DemoResponse)
def predict_demo(seed: int | None = None) -> dict[str, Any]:
    """Synthesize a random measurement and return the prediction alongside.

    Used by the frontend's "Scan another sample" button so the UI can
    demo full-stack behaviour without requiring a real CSV upload.
    """
    demo = synth_demo_features(seed=seed)
    extras: dict[str, Any] = {
        "spec": demo["spec"].tolist(),
        "led": demo["led"].tolist(),
        "lif_450lp": float(demo["lif_450lp"]),
        "true_class": demo["true_class"],
        "true_ilmenite_fraction": float(demo["true_ilmenite_fraction"]),
    }
    # Include AS7265x data when available from the demo synthesizer
    if "as7265x" in demo and demo["as7265x"] is not None:
        extras["as7265x"] = demo["as7265x"].tolist()

    return _to_prediction(demo["features"], extras=extras)


@app.get("/api/endmembers")
def endmembers() -> dict[str, Any]:
    """Return USGS endmember spectra for the frontend's reference plot."""
    try:
        return load_endmembers_payload()
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------------------------------------------------------------------------
# Dev entry point
# ---------------------------------------------------------------------------


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run("apps.api:app", host="127.0.0.1", port=8000, reload=True)
