"""Vercel Python serverless function for VERA inference.

This module is intentionally self-contained because Vercel deploys the
``web/`` subtree, not the repo-root Python package. Keep the constants here
in lockstep with ``src/vera/schema.py`` and prefer adding compatibility at
the edge over reviving the older schema contract.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import onnxruntime as ort
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

SCHEMA_VERSION = "1.2.0"
N_SPEC = 288
N_AS7265X = 18
N_SWIR = 2
N_LED = 12

N_FEATURES_FULL = N_SPEC + N_SWIR + N_LED + 1
N_FEATURES_MULTISPECTRAL = N_AS7265X + N_SWIR + N_LED + 1
N_FEATURES_COMBINED = N_SPEC + N_AS7265X + N_SWIR + N_LED + 1

# Older Vercel artifacts were exported before schema v1.2 added SWIR.
N_FEATURES_LEGACY_FULL = N_SPEC + N_LED + 1
N_FEATURES_LEGACY_COMBINED = N_SPEC + N_AS7265X + N_LED + 1

WAVELENGTHS_NM: list[float] = list(np.linspace(340.0, 850.0, N_SPEC))
LED_WAVELENGTHS_NM: list[int] = [
    385, 405, 450, 500, 525, 590, 625, 660, 730, 780, 850, 940,
]
SWIR_WAVELENGTHS_NM: list[int] = [940, 1050]
AS7265X_BANDS_NM: list[int] = [
    410, 435, 460, 485, 510, 535, 560, 585, 610,
    645, 680, 705, 730, 760, 810, 860, 900, 940,
]

MINERAL_CLASSES: list[str] = [
    "ilmenite_rich",
    "olivine_rich",
    "pyroxene_rich",
    "anorthositic",
    "glass_agglutinate",
    "mixed",
]
LEGACY_MINERAL_CLASSES: list[str] = [
    "ilmenite_rich",
    "olivine_rich",
    "pyroxene_rich",
    "anorthositic",
    "mixed",
]

_MODEL_PATH = Path(__file__).parent / "model.onnx"
_MODEL_META_PATH = Path(__file__).parent / "meta.json"
_SESSION: ort.InferenceSession | None = None
_TEMPERATURE: float | None = None


def _get_session() -> ort.InferenceSession:
    global _SESSION
    if _SESSION is None:
        if not _MODEL_PATH.exists():
            raise HTTPException(
                status_code=503,
                detail=(
                    f"model.onnx missing at {_MODEL_PATH}; export it with "
                    "`uv run python -m vera.quantize --run runs/cnn_v2 "
                    "--out web/api/model.onnx` and redeploy"
                ),
            )
        _SESSION = ort.InferenceSession(
            str(_MODEL_PATH), providers=["CPUExecutionProvider"]
        )
    return _SESSION


def _shape_int(value: Any) -> int | None:
    return int(value) if isinstance(value, int) and value > 0 else None


def _model_input_features(sess: ort.InferenceSession) -> int:
    shape = sess.get_inputs()[0].shape
    n = _shape_int(shape[-1]) if shape else None
    if n is None:
        raise HTTPException(
            status_code=503,
            detail=f"model input shape must expose final feature dimension, got {shape}",
        )
    return n


def _model_class_names(sess: ort.InferenceSession) -> list[str]:
    shape = sess.get_outputs()[0].shape
    n_classes = _shape_int(shape[-1]) if shape else None
    if n_classes == len(MINERAL_CLASSES):
        return MINERAL_CLASSES
    if n_classes == len(LEGACY_MINERAL_CLASSES):
        return LEGACY_MINERAL_CLASSES
    if n_classes is not None:
        return [f"class_{i}" for i in range(n_classes)]
    return MINERAL_CLASSES


def _sensor_mode_for_features(n_features: int) -> str:
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
    return f"unknown_{n_features}"


def _model_sha256() -> str | None:
    if not _MODEL_PATH.exists():
        return None
    h = hashlib.sha256()
    with open(_MODEL_PATH, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def _model_temperature() -> float:
    global _TEMPERATURE
    if _TEMPERATURE is None:
        if _MODEL_META_PATH.exists():
            meta = json.loads(_MODEL_META_PATH.read_text())
            _TEMPERATURE = float(meta.get("temperature", 1.0))
        else:
            _TEMPERATURE = 1.0
        if _TEMPERATURE <= 0:
            raise HTTPException(
                status_code=503,
                detail=f"model temperature must be positive, got {_TEMPERATURE}",
            )
    return _TEMPERATURE


def _softmax(logits: np.ndarray) -> np.ndarray:
    z = logits.astype(np.float64) - logits.max()
    e = np.exp(z)
    return e / e.sum()


def _uncertainty(probs: np.ndarray) -> dict[str, float | str]:
    p = np.clip(np.asarray(probs, dtype=np.float64), 1e-12, 1.0)
    confidence = float(p.max())
    entropy = float(-np.sum(p * np.log(p)))
    top = np.sort(p)[::-1]
    margin = float(top[0] - top[1]) if top.size > 1 else 1.0
    if confidence < 0.40 or entropy > 1.20:
        status = "likely_ood"
    elif margin < 0.15:
        status = "borderline"
    elif confidence < 0.70:
        status = "low_confidence"
    else:
        status = "nominal"
    return {
        "confidence": confidence,
        "entropy": entropy,
        "margin": margin,
        "status": status,
    }


class SpectrumRequest(BaseModel):
    spec: list[float] = Field(min_length=N_SPEC, max_length=N_SPEC)
    led: list[float] = Field(min_length=N_LED, max_length=N_LED)
    lif_450lp: float
    swir: list[float] | None = Field(default=None, min_length=N_SWIR, max_length=N_SWIR)
    as7265x: list[float] | None = Field(
        default=None,
        min_length=N_AS7265X,
        max_length=N_AS7265X,
    )


def _features_from_request(req: SpectrumRequest, n_features: int) -> np.ndarray:
    parts: list[np.ndarray] = []
    if n_features in (N_FEATURES_FULL, N_FEATURES_COMBINED, N_FEATURES_LEGACY_FULL, N_FEATURES_LEGACY_COMBINED):
        parts.append(np.asarray(req.spec, dtype=np.float32))
    if n_features in (N_FEATURES_MULTISPECTRAL, N_FEATURES_COMBINED, N_FEATURES_LEGACY_COMBINED):
        if req.as7265x is None:
            raise HTTPException(status_code=400, detail="model requires as7265x values")
        parts.append(np.asarray(req.as7265x, dtype=np.float32))
    if n_features in (N_FEATURES_FULL, N_FEATURES_MULTISPECTRAL, N_FEATURES_COMBINED):
        if req.swir is None:
            raise HTTPException(status_code=400, detail="model requires swir values")
        parts.append(np.asarray(req.swir, dtype=np.float32))

    parts.extend([
        np.asarray(req.led, dtype=np.float32),
        np.asarray([req.lif_450lp], dtype=np.float32),
    ])
    features = np.concatenate(parts)
    if features.shape[0] != n_features:
        raise HTTPException(
            status_code=400,
            detail=f"expected {n_features} model features, got {features.shape[0]}",
        )
    if not np.all(np.isfinite(features)):
        raise HTTPException(status_code=400, detail="all feature values must be finite")
    return features


def _run_inference(features: np.ndarray) -> dict[str, Any]:
    sess = _get_session()
    n_features = _model_input_features(sess)
    if features.size != n_features:
        raise HTTPException(
            status_code=400,
            detail=f"expected {n_features} model features, got {features.size}",
        )
    x = features.astype(np.float32).reshape(1, 1, n_features)
    input_name = sess.get_inputs()[0].name
    out_names = [o.name for o in sess.get_outputs()]
    logits, ilm = sess.run(out_names, {input_name: x})
    scaled_logits = np.asarray(logits)[0] / _model_temperature()
    probs = _softmax(scaled_logits)
    class_names = _model_class_names(sess)
    cls_idx = int(np.argmax(probs))
    u = _uncertainty(probs)
    return {
        "predicted_class": class_names[cls_idx],
        "predicted_class_index": cls_idx,
        "probabilities": [
            {"name": class_names[i], "probability": float(p)}
            for i, p in enumerate(probs)
        ],
        "ilmenite_fraction": float(np.clip(np.asarray(ilm).flat[0], 0.0, 1.0)),
        "confidence": float(u["confidence"]),
        "entropy": float(u["entropy"]),
        "margin": float(u["margin"]),
        "status": str(u["status"]),
        "model_version": f"vercel:{_MODEL_PATH.name}",
    }


_LAM = np.linspace(340.0, 850.0, N_SPEC)
_LAM_NORM = (_LAM - _LAM.min()) / (_LAM.max() - _LAM.min())
_ENDMEMBERS = np.stack([
    0.05 + 0.05 * _LAM_NORM,
    0.20 + 0.60 * _LAM_NORM,
    0.15 + 0.50 * _LAM_NORM,
    0.55 + 0.30 * _LAM_NORM,
    0.04 + 0.22 * _LAM_NORM,
])


def _fractions_for_class(klass: str, rng: np.random.Generator) -> np.ndarray:
    f = np.zeros(5, dtype=np.float64)
    if klass == "ilmenite_rich":
        f[0] = rng.uniform(0.35, 0.65)
        f[1:] = rng.uniform(0.05, 0.20, size=4)
    elif klass == "olivine_rich":
        f[1] = rng.uniform(0.55, 0.85)
        f[[0, 2, 3, 4]] = rng.uniform(0.0, 0.15, size=4)
    elif klass == "pyroxene_rich":
        f[2] = rng.uniform(0.55, 0.85)
        f[[0, 1, 3, 4]] = rng.uniform(0.0, 0.15, size=4)
    elif klass == "anorthositic":
        f[3] = rng.uniform(0.65, 0.90)
        f[[0, 1, 2, 4]] = rng.uniform(0.0, 0.12, size=4)
    elif klass == "glass_agglutinate":
        f[4] = rng.uniform(0.55, 0.85)
        f[:4] = rng.uniform(0.0, 0.15, size=4)
    else:
        f = rng.uniform(0.1, 0.4, size=5)
    return f / f.sum()


def _synth_demo(seed: int | None = None, class_names: list[str] | None = None) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    names = class_names or MINERAL_CLASSES
    klass = str(rng.choice(names))
    fractions = _fractions_for_class(klass, rng)

    spec = (fractions[:, None] * _ENDMEMBERS).sum(axis=0)
    spec *= 1.0 + rng.normal(0.0, 0.01, size=N_SPEC)
    spec += np.polyval(rng.normal(0.0, 0.01, size=3), _LAM_NORM)
    spec = np.clip(spec + rng.normal(0.0, 0.005, size=N_SPEC), 0.0, 1.5)

    led = np.array([
        spec[int(np.argmin(np.abs(_LAM - lw)))] for lw in LED_WAVELENGTHS_NM
    ]) + rng.normal(0.0, 0.005, size=N_LED)
    led = np.clip(led, 0.0, 1.5)
    swir = np.array([
        max(spec[-1] + rng.normal(0.0, 0.01), 0.0),
        max(spec[-1] * (0.80 + 0.35 * fractions[3]) + rng.normal(0.0, 0.01), 0.0),
    ], dtype=np.float32)
    indices = np.linspace(0, N_SPEC - 1, N_AS7265X, dtype=int)
    as7265x = spec[indices] + rng.normal(0.0, 0.005, size=N_AS7265X)
    lif = float(max((fractions[3] * 0.85 + fractions[1] * 0.30) * (1.0 - fractions[0]) + rng.normal(0.0, 0.01), 0.0))
    return {
        "spec": spec.astype(np.float32),
        "led": led.astype(np.float32),
        "swir": swir.astype(np.float32),
        "as7265x": as7265x.astype(np.float32),
        "lif_450lp": lif,
        "true_class": klass,
        "true_ilmenite_fraction": float(fractions[0]),
    }


app = FastAPI(title="VERA API (Vercel)", version="0.3.0")


@app.get("/healthz")
@app.get("/api/predict/healthz")
def healthz() -> dict[str, Any]:
    return {
        "status": "ok" if _MODEL_PATH.exists() else "degraded",
        "model_loaded": _MODEL_PATH.exists(),
        "schema_version": SCHEMA_VERSION,
    }


@app.get("/api/meta")
def meta() -> dict[str, Any]:
    sess = _get_session()
    n_features = _model_input_features(sess)
    sensor_mode = _sensor_mode_for_features(n_features)
    return {
        "schema_version": SCHEMA_VERSION,
        "class_names": _model_class_names(sess),
        "wavelengths_nm": WAVELENGTHS_NM,
        "led_wavelengths_nm": LED_WAVELENGTHS_NM,
        "swir_wavelengths_nm": SWIR_WAVELENGTHS_NM,
        "as7265x_bands_nm": (
            AS7265X_BANDS_NM
            if "combined" in sensor_mode or "multispectral" in sensor_mode
            else None
        ),
        "n_features_total": n_features,
        "model_loaded": _MODEL_PATH.exists(),
        "model_sha256": _model_sha256(),
        "model_run_dir": "vercel:/api",
        "sensor_mode": sensor_mode,
        "temperature": _model_temperature(),
    }


@app.post("/api/predict")
def predict(req: SpectrumRequest) -> dict[str, Any]:
    sess = _get_session()
    features = _features_from_request(req, _model_input_features(sess))
    return _run_inference(features)


@app.post("/api/predict/demo")
def predict_demo(seed: int | None = None) -> dict[str, Any]:
    sess = _get_session()
    demo = _synth_demo(seed=seed, class_names=_model_class_names(sess))
    req = SpectrumRequest(
        spec=demo["spec"].tolist(),
        led=demo["led"].tolist(),
        swir=demo["swir"].tolist(),
        as7265x=demo["as7265x"].tolist(),
        lif_450lp=demo["lif_450lp"],
    )
    features = _features_from_request(req, _model_input_features(sess))
    result = _run_inference(features)
    result.update({
        "spec": demo["spec"].tolist(),
        "led": demo["led"].tolist(),
        "swir": demo["swir"].tolist(),
        "as7265x": demo["as7265x"].tolist(),
        "lif_450lp": demo["lif_450lp"],
        "true_class": demo["true_class"],
        "true_ilmenite_fraction": demo["true_ilmenite_fraction"],
    })
    return result


@app.get("/api/endmembers")
def endmembers() -> dict[str, Any]:
    return {
        "wavelengths_nm": WAVELENGTHS_NM,
        "source": "vercel:parametric",
        "endmembers": {
            name: [float(v) for v in spectrum]
            for name, spectrum in zip(
                ["ilmenite", "olivine", "pyroxene", "anorthite", "glass_agglutinate"],
                _ENDMEMBERS,
            )
        },
    }
