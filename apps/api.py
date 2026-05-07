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
    N_LED,
    N_SPEC,
    N_SWIR,
    SCHEMA_VERSION,
    SWIR_WAVELENGTHS_NM,
    WAVELENGTHS,
    get_feature_count,
)

N_FEATURES_FULL = get_feature_count("full")
N_FEATURES_MULTISPECTRAL = get_feature_count("multispectral")
N_FEATURES_COMBINED = get_feature_count("combined")
N_FEATURES_LEGACY_FULL = N_SPEC + N_LED + 1
N_FEATURES_LEGACY_COMBINED = N_SPEC + N_AS7265X + N_LED + 1
_SUPPORTED_MODEL_FEATURE_COUNTS = {
    N_FEATURES_FULL,
    N_FEATURES_MULTISPECTRAL,
    N_FEATURES_COMBINED,
    N_FEATURES_LEGACY_FULL,
    N_FEATURES_LEGACY_COMBINED,
}

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

def _cors_origins() -> list[str]:
    """Return configured browser origins for local API access.

    The hosted Next.js app uses same-origin rewrites, so CORS is only needed
    for local development or a separately hosted console. Keep the default
    tight and let deployments opt in via VERA_CORS_ORIGINS.
    """
    raw = os.environ.get("VERA_CORS_ORIGINS")
    if raw:
        return [origin.strip() for origin in raw.split(",") if origin.strip()]
    return [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ]


def _sensor_mode_for_features(n_features: int, fallback: str) -> str:
    if n_features == N_FEATURES_COMBINED:
        return "combined"
    if n_features == N_FEATURES_MULTISPECTRAL:
        return "multispectral"
    if n_features == N_FEATURES_FULL:
        return "full"
    if n_features == N_FEATURES_LEGACY_COMBINED:
        return "legacy_combined"
    if n_features == N_FEATURES_LEGACY_FULL:
        return "legacy_full"
    return fallback


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
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
    swir: list[float] | None = Field(default=None, min_length=N_SWIR, max_length=N_SWIR)
    as7265x: list[float] | None = Field(
        default=None,
        min_length=N_AS7265X,
        max_length=N_AS7265X,
    )


class ClassProbability(BaseModel):
    name: str
    probability: float


class PredictionResponse(BaseModel):
    predicted_class: str
    predicted_class_index: int
    probabilities: list[ClassProbability]
    ilmenite_fraction: float
    confidence: float
    entropy: float = 0.0
    margin: float = 0.0
    status: str = "nominal"
    model_version: str


class DemoResponse(PredictionResponse):
    spec: list[float]
    led: list[float]
    lif_450lp: float
    swir: list[float] | None = None
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
    swir_wavelengths_nm: list[int] | None = None
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
        "confidence": float(
            result.get("confidence", result["probabilities"][result["class_index"]])
        ),
        "entropy": float(result.get("entropy", 0.0)),
        "margin": float(result.get("margin", 0.0)),
        "status": str(result.get("status", "nominal")),
        "model_version": engine.version,
    }
    if extras is not None:
        payload.update(extras)
    return payload


def _features_from_request(
    req: SpectrumRequest,
    sensor_mode: str,
    n_features: int | None = None,
) -> np.ndarray:
    """Build a feature vector for the loaded model's exact ONNX input width."""
    n_features = n_features or get_feature_count(sensor_mode)
    if n_features not in _SUPPORTED_MODEL_FEATURE_COUNTS:
        raise HTTPException(
            status_code=503,
            detail=f"unsupported model feature count: {n_features}",
        )
    parts: list[np.ndarray] = []

    if n_features in (
        N_FEATURES_FULL,
        N_FEATURES_COMBINED,
        N_FEATURES_LEGACY_FULL,
        N_FEATURES_LEGACY_COMBINED,
    ):
        parts.append(np.asarray(req.spec, dtype=np.float32))

    if n_features in (
        N_FEATURES_MULTISPECTRAL,
        N_FEATURES_COMBINED,
        N_FEATURES_LEGACY_COMBINED,
    ):
        if req.as7265x is None:
            raise HTTPException(
                status_code=400,
                detail=f"model sensor_mode={sensor_mode!r} requires as7265x values",
            )
        parts.append(np.asarray(req.as7265x, dtype=np.float32))

    if n_features in (N_FEATURES_FULL, N_FEATURES_MULTISPECTRAL, N_FEATURES_COMBINED):
        if req.swir is None:
            raise HTTPException(
                status_code=400,
                detail=f"model sensor_mode={sensor_mode!r} requires swir values",
            )
        parts.append(np.asarray(req.swir, dtype=np.float32))

    parts.extend([
        np.asarray(req.led, dtype=np.float32),
        np.asarray([req.lif_450lp], dtype=np.float32),
    ])
    features = np.concatenate(parts)

    if features.shape[0] != n_features:
        raise HTTPException(
            status_code=400,
            detail=(
                f"expected {n_features} features "
                f"(model sensor_mode={sensor_mode}), got {features.shape[0]}"
            ),
        )
    if not np.all(np.isfinite(features)):
        raise HTTPException(status_code=400, detail="all feature values must be finite")
    return features


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

    n_features = get_feature_count(sensor_mode)
    if _ENGINE is not None:
        sensor_mode = _sensor_mode_for_features(
            _ENGINE.expected_features,
            _ENGINE.sensor_mode,
        )
        n_features = _ENGINE.expected_features

    # Include AS7265x band wavelengths when the mode uses the triad sensor
    if sensor_mode in ("multispectral", "combined", "legacy_combined"):
        as7265x_bands = list(AS7265X_BANDS)

    return MetaResponse(
        schema_version=SCHEMA_VERSION,
        class_names=list(MINERAL_CLASSES),
        wavelengths_nm=[float(w) for w in WAVELENGTHS],
        led_wavelengths_nm=list(LED_WAVELENGTHS_NM),
        n_features_total=n_features,
        model_loaded=_ENGINE is not None,
        model_sha256=_model_sha256(),
        model_run_dir=str(_RUN_DIR) if _RUN_DIR is not None else None,
        sensor_mode=sensor_mode,
        swir_wavelengths_nm=list(SWIR_WAVELENGTHS_NM),
        as7265x_bands_nm=as7265x_bands,
    )


@app.post("/api/predict", response_model=PredictionResponse)
def predict(req: SpectrumRequest) -> dict[str, Any]:
    engine = _require_engine()
    features = _features_from_request(req, engine.sensor_mode, engine.expected_features)
    return _to_prediction(features)


@app.post("/api/predict/demo", response_model=DemoResponse)
def predict_demo(seed: int | None = None) -> dict[str, Any]:
    """Synthesize a random measurement and return the prediction alongside.

    Used by the frontend's "Scan another sample" button so the UI can
    demo full-stack behaviour without requiring a real CSV upload.
    """
    engine = _require_engine()
    demo = synth_demo_features(seed=seed, sensor_mode=engine.sensor_mode)
    demo_req = SpectrumRequest(
        spec=demo["spec"].tolist(),
        swir=demo["swir"].tolist() if demo.get("swir") is not None else None,
        led=demo["led"].tolist(),
        lif_450lp=float(demo["lif_450lp"]),
        as7265x=(
            demo["as7265x"].tolist()
            if demo.get("as7265x") is not None
            else None
        ),
    )
    extras: dict[str, Any] = {
        "spec": demo["spec"].tolist(),
        "led": demo["led"].tolist(),
        "lif_450lp": float(demo["lif_450lp"]),
        "true_class": demo["true_class"],
        "true_ilmenite_fraction": float(demo["true_ilmenite_fraction"]),
    }
    # Include SWIR data when available
    if "swir" in demo and demo["swir"] is not None:
        extras["swir"] = demo["swir"].tolist()
    # Include AS7265x data when available from the demo synthesizer
    if "as7265x" in demo and demo["as7265x"] is not None:
        extras["as7265x"] = demo["as7265x"].tolist()

    features = _features_from_request(
        demo_req,
        engine.sensor_mode,
        engine.expected_features,
    )
    return _to_prediction(features, extras=extras)


@app.get("/api/endmembers")
def endmembers() -> dict[str, Any]:
    """Return USGS endmember spectra for the frontend's reference plot."""
    try:
        return load_endmembers_payload()
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


# ---------------------------------------------------------------------------
# Dev entry point
# ---------------------------------------------------------------------------


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run("apps.api:app", host="127.0.0.1", port=8000, reload=True)
