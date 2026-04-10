"""ONNX-based inference engine for VERA models.

Wraps ``onnxruntime`` to provide a minimal, torch-free prediction path
suitable for deployment on Vercel serverless, Raspberry Pi, or any
environment where PyTorch is too heavy.  The same engine is consumed by
the FastAPI backend (``apps/api.py``), the ingestion bridge
(``scripts/bridge.py``), and the Vercel serverless handler.

Public API
----------
- :class:`InferenceEngine`         — load ONNX, predict class + ilmenite
- :func:`synth_demo_features`      — one-shot synthetic spectrum for demos
- :func:`load_endmembers_payload`  — endmember spectra formatted for the frontend
- :func:`resolve_endmembers`       — find or generate endmember .npz
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from vera.schema import (
    MINERAL_CLASSES,
    N_AS7265X,
    N_FEATURES_TOTAL,
    N_LED,
    N_SPEC,
    WAVELENGTHS,
    get_feature_count,
)

# ---------------------------------------------------------------------------
# Endmember resolution
# ---------------------------------------------------------------------------

ENDMEMBER_CACHE_PATH = ROOT / "data" / "cache" / "usgs_endmembers.npz"


def resolve_endmembers(cache_path: Path | None = None) -> Path:
    """Return a valid endmember ``.npz`` path, generating it if absent.

    Uses the parametric fallback from ``scripts/download_usgs.py`` so
    the pipeline works without network access or pre-cached data.
    """
    path = cache_path or ENDMEMBER_CACHE_PATH
    if path.exists():
        return path

    # Import the parametric builder from the download script
    scripts_dir = ROOT / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))

    from download_usgs import build_parametric_endmembers  # type: ignore[import-untyped]

    endmembers = build_parametric_endmembers()
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        path,
        wavelengths_nm=endmembers["wavelengths_nm"],
        olivine=endmembers["olivine"],
        pyroxene=endmembers["pyroxene"],
        anorthite=endmembers["anorthite"],
        ilmenite=endmembers["ilmenite"],
        glass_agglutinate=endmembers["glass_agglutinate"],
        source=np.asarray("parametric"),
    )
    return path


# ---------------------------------------------------------------------------
# Inference engine
# ---------------------------------------------------------------------------


def _softmax(x: np.ndarray) -> np.ndarray:
    """Numerically stable softmax over a 1-D logit vector."""
    e = np.exp(x - np.max(x))
    return e / e.sum()


class InferenceEngine:
    """Lightweight ONNX predictor for the 1D ResNet.

    Parameters
    ----------
    onnx_path : Path | str
        Location of the exported ``model.onnx`` file.

    Attributes
    ----------
    version : str
        Human-readable model identifier (parent directory name).
    sha256_short : str
        First 16 hex digits of the model file's SHA-256 — useful for
        verifying that the bridge and API see the same artefact.
    """

    def __init__(self, onnx_path: Path | str) -> None:
        import json as _json

        try:
            import onnxruntime as ort
        except ImportError as exc:
            raise ImportError(
                "onnxruntime is required for inference. "
                "Install it via: uv pip install onnxruntime"
            ) from exc

        self._path = Path(onnx_path)
        if not self._path.exists():
            raise FileNotFoundError(f"ONNX model not found: {self._path}")

        # Read sensor_mode from meta.json if it exists (backward compat: default "full")
        meta_path = self._path.parent / "meta.json"
        if meta_path.exists():
            meta = _json.loads(meta_path.read_text())
            self._sensor_mode: str = meta.get("sensor_mode", "full")
        else:
            self._sensor_mode = "full"
        self._n_features: int = get_feature_count(self._sensor_mode)

        self._session = ort.InferenceSession(
            str(self._path),
            providers=["CPUExecutionProvider"],
        )
        self._input_name: str = self._session.get_inputs()[0].name

        h = hashlib.sha256(self._path.read_bytes())
        self._sha256 = h.hexdigest()[:16]

    @property
    def version(self) -> str:
        return self._path.parent.name

    @property
    def sha256_short(self) -> str:
        return self._sha256

    @property
    def sensor_mode(self) -> str:
        """Sensor configuration this model was trained with."""
        return self._sensor_mode

    @property
    def expected_features(self) -> int:
        """Number of input features this model expects."""
        return self._n_features

    def predict(self, features: np.ndarray) -> dict[str, Any]:
        """Run inference on a single feature vector.

        Parameters
        ----------
        features : np.ndarray
            Shape ``(expected_features,)``.  The exact size depends on
            the ``sensor_mode`` stored in ``meta.json``:

            * ``"full"``          — 301 features (spec_288 + led_12 + lif_1)
            * ``"multispectral"`` —  31 features (as7265x_18 + led_12 + lif_1)
            * ``"combined"``      — 319 features (spec_288 + as7265x_18 + led_12 + lif_1)

        Returns
        -------
        dict
            ``class_index`` (int), ``probabilities`` (ndarray of shape
            ``(5,)``), ``ilmenite_fraction`` (float clamped to [0, 1]).
        """
        n = self._n_features
        if features.size != n:
            raise ValueError(
                f"Feature vector has {features.size} elements, but this "
                f"model (sensor_mode={self._sensor_mode!r}) expects {n}"
            )
        x = features.astype(np.float32).reshape(1, 1, n)
        logits, ilmenite = self._session.run(None, {self._input_name: x})

        probs = _softmax(logits[0])
        class_idx = int(np.argmax(probs))

        # ilmenite head output shape varies: (B,1) or (B,) depending
        # on whether squeeze was applied during ONNX export.
        ilm_val = float(ilmenite.flat[0])

        return {
            "class_index": class_idx,
            "probabilities": probs,
            "ilmenite_fraction": float(np.clip(ilm_val, 0.0, 1.0)),
        }


# ---------------------------------------------------------------------------
# Demo / frontend helpers
# ---------------------------------------------------------------------------


def synth_demo_features(
    seed: int | None = None,
    sensor_mode: str = "full",
) -> dict[str, Any]:
    """Generate one synthetic measurement and return its feature vector.

    Used by the ``POST /api/predict/demo`` endpoint so the frontend can
    exercise the full inference pipeline without uploading a CSV.

    Parameters
    ----------
    seed : int | None
        RNG seed for reproducibility.
    sensor_mode : str
        ``"full"``          — 301 features (spec + led + lif).
        ``"multispectral"`` —  31 features (as7265x + led + lif).
        ``"combined"``      — 319 features (spec + as7265x + led + lif).
    """
    from vera.synth import (
        Endmembers,
        fractions_for_class,
        load_endmembers,
        synth_measurement,
    )

    rng = np.random.default_rng(seed)
    klass = str(rng.choice(list(MINERAL_CLASSES)))

    em_path = resolve_endmembers()
    em = load_endmembers(em_path)
    fracs = fractions_for_class(klass, rng)
    m = synth_measurement(
        sample_id="demo",
        mineral_class=klass,
        fractions=fracs,
        endmembers=em,
        rng=rng,
    )

    spec = np.asarray(m.spec, dtype=np.float32)
    led = np.asarray(m.led, dtype=np.float32)
    lif = np.float32(m.lif_450lp)

    result: dict[str, Any] = {
        "spec": spec,
        "led": led,
        "lif_450lp": lif,
        "true_class": klass,
        "true_ilmenite_fraction": m.ilmenite_fraction,
    }

    if sensor_mode == "full":
        features = np.concatenate([spec, led, [lif]])
    elif sensor_mode in ("multispectral", "combined"):
        # Generate synthetic AS7265x 18-channel data by subsampling the
        # spectrum at representative wavelengths.  The AS7265x covers
        # 410–940 nm with 18 discrete channels; we approximate by picking
        # evenly spaced indices from the C12880MA spectrum and adding a
        # small amount of noise to simulate the different sensor.
        indices = np.linspace(0, N_SPEC - 1, N_AS7265X, dtype=int)
        as7265x = spec[indices] + rng.normal(0, 0.005, size=N_AS7265X).astype(np.float32)
        result["as7265x"] = as7265x

        if sensor_mode == "multispectral":
            features = np.concatenate([as7265x, led, [lif]])
        else:  # combined
            features = np.concatenate([spec, as7265x, led, [lif]])
    else:
        raise ValueError(f"Unknown sensor_mode: {sensor_mode!r}")

    result["features"] = features
    return result


def load_endmembers_payload() -> dict[str, Any]:
    """Return endmember spectra formatted for the frontend reference plot.

    Raises :class:`FileNotFoundError` if no cache exists and parametric
    generation fails.
    """
    em_path = resolve_endmembers()
    data = np.load(em_path, allow_pickle=False)
    return {
        "wavelengths_nm": [float(w) for w in WAVELENGTHS],
        "endmembers": {
            name: [float(v) for v in data[name]]
            for name in ("olivine", "pyroxene", "anorthite", "ilmenite", "glass_agglutinate")
            if name in data.files
        },
        "source": str(data["source"]),
    }


__all__ = [
    "InferenceEngine",
    "resolve_endmembers",
    "synth_demo_features",
    "load_endmembers_payload",
    "ENDMEMBER_CACHE_PATH",
]
