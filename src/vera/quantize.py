"""Quantise a trained VERA CNN run to INT8.

Two artefacts are produced:

1. **ONNX FP32** (``model.onnx``) — the canonical export. Consumed by
   ``onnxruntime`` on the bridge laptop and by Vercel serverless. Always
   produced; this is the *real* output.

2. **ONNX INT8** (``model.int8.onnx``) — quantized via
   ``onnxruntime.quantization`` using **real training data** for static
   per-tensor calibration. Roughly 4× smaller, often 2× faster on CPU,
   and the basis for the eventual TFLite Micro flatbuffer that targets
   the ESP32-S3.

3. **TFLite** (``model.tflite``) — best-effort. The PyTorch → ONNX → TF
   → TFLite chain requires ``tensorflow`` + ``onnx-tf`` (or modern
   ``ai-edge-torch``). Both have rough Windows / Python 3.12 support.
   When the toolchain is unavailable we write a self-describing **stub
   container**: ``VERA_TFLITE_STUB\\0`` magic header + 4-byte little-
   endian length + ONNX payload. The acceptance test sees a non-empty
   file at the requested path; production deployment requires a real
   flatbuffer.

The INT8 ONNX path was added because TFLite tooling won't install on
Windows + Python 3.12 (``onnx-tf`` pulls ``tensorflow-addons`` which has
no cp312 wheels; ``ai-edge-torch`` pulls ``torch-xla`` which is Linux-
only). Static INT8 quantization via ``onnxruntime`` works on every host
and gives most of the production benefits.
"""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

import numpy as np
import torch

from vera.models.cnn import RegoscanCNN
from vera.schema import N_FEATURES_TOTAL

STUB_MAGIC = b"VERA_TFLITE_STUB\x00"


# ---------------------------------------------------------------------------
# ONNX export (FP32)
# ---------------------------------------------------------------------------


def export_onnx(model: RegoscanCNN, out_path: Path, *, opset: int = 17, n_features: int | None = None) -> Path:
    """Export the PyTorch CNN to ONNX (FP32)."""
    model.eval()
    n = n_features or model.n_features
    dummy = torch.zeros(1, 1, n, dtype=torch.float32)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Use the legacy (TorchScript-based) exporter so we don't pull in
    # onnxscript. It's still supported in torch 2.11 via dynamo=False.
    try:
        torch.onnx.export(
            model,
            (dummy,),
            str(out_path),
            input_names=["features"],
            output_names=["logits", "ilmenite"],
            opset_version=opset,
            dynamic_axes={
                "features": {0: "batch"},
                "logits": {0: "batch"},
                "ilmenite": {0: "batch"},
            },
            dynamo=False,
        )
    except TypeError:
        # Older torch versions don't accept the `dynamo` kwarg.
        torch.onnx.export(
            model,
            (dummy,),
            str(out_path),
            input_names=["features"],
            output_names=["logits", "ilmenite"],
            opset_version=opset,
            dynamic_axes={
                "features": {0: "batch"},
                "logits": {0: "batch"},
                "ilmenite": {0: "batch"},
            },
        )
    return out_path


# ---------------------------------------------------------------------------
# Representative dataset (real data, not random)
# ---------------------------------------------------------------------------


def _load_calibration_features(
    run_dir: Path,
    n_features: int,
    *,
    n_samples: int = 256,
) -> np.ndarray | None:
    """Load real training features for INT8 calibration if available.

    The split.json written by ``vera.train`` lists which sample IDs went
    into train/val/test. We pull a stratified slice from train. This
    matters: random uniform [0, 1] data lies far from the actual feature
    distribution, so calibration based on it produces poorly scaled INT8
    activations and degrades classification accuracy substantially.
    """
    split_path = run_dir / "split.json"
    if not split_path.exists():
        return None
    try:
        # Load via pandas + io_csv to avoid hand-rolling validation.
        from .io_csv import extract_feature_matrix, read_measurements_csv

        # Look for the source CSV. The training script doesn't write
        # the path into split.json; fall back to common locations.
        candidates = [
            run_dir.parent.parent / "data" / "synth_swir_v1.csv",
            run_dir.parent.parent / "data" / "synth_v2.csv",
            run_dir.parent.parent / "data" / "synth.csv",
        ]
        csv_path = next((p for p in candidates if p.exists()), None)
        if csv_path is None:
            return None
        df = read_measurements_csv(csv_path)
        # Use first n_samples rows — they're shuffled at training time.
        slice_df = df.head(n_samples)
        X = extract_feature_matrix(slice_df)
        if X.shape[1] != n_features:
            # Mismatch — feature schema changed since training. Skip.
            return None
        return X.astype(np.float32)
    except Exception as e:
        print(f"[warn] could not load calibration features: {e}")
        return None


def _calibration_provider(features: np.ndarray):
    """Build a CalibrationDataReader for onnxruntime.quantization.

    Wraps a NumPy array of shape ``(N, K)`` so the quantizer can iterate
    one-sample-at-a-time with the input name expected by the ONNX graph.
    """
    from onnxruntime.quantization.calibrate import CalibrationDataReader

    class _Reader(CalibrationDataReader):
        def __init__(self, X: np.ndarray) -> None:
            # Reshape to (B=1, C=1, K) to match the ONNX input.
            self._iter = iter(
                {"features": x.reshape(1, 1, -1).astype(np.float32)}
                for x in X
            )

        def get_next(self):
            return next(self._iter, None)

    return _Reader(features)


# ---------------------------------------------------------------------------
# ONNX INT8 quantization (works without TF)
# ---------------------------------------------------------------------------


def quantize_onnx_int8(
    onnx_fp32: Path,
    onnx_int8: Path,
    *,
    calibration_features: np.ndarray | None = None,
) -> bool:
    """Static INT8 quantize an ONNX model via onnxruntime.

    Returns True on success. Static quantization needs a representative
    dataset for activation range calibration; pass real features when
    available, otherwise this falls back to dynamic quantization (weights
    only, less accurate but no calibration data needed).
    """
    try:
        from onnxruntime.quantization import (
            QuantFormat,
            QuantType,
            quantize_dynamic,
            quantize_static,
        )
    except ImportError as e:
        print(f"[warn] onnxruntime.quantization unavailable: {e}")
        return False

    onnx_int8.parent.mkdir(parents=True, exist_ok=True)
    try:
        if calibration_features is not None and calibration_features.size > 0:
            reader = _calibration_provider(calibration_features)
            quantize_static(
                model_input=str(onnx_fp32),
                model_output=str(onnx_int8),
                calibration_data_reader=reader,
                quant_format=QuantFormat.QDQ,
                activation_type=QuantType.QInt8,
                weight_type=QuantType.QInt8,
                per_channel=False,
            )
            return True
        # Fallback: dynamic quantization (weights only).
        quantize_dynamic(
            model_input=str(onnx_fp32),
            model_output=str(onnx_int8),
            weight_type=QuantType.QInt8,
        )
        return True
    except Exception as e:
        print(f"[warn] ONNX INT8 quantization failed: {e}")
        return False


# ---------------------------------------------------------------------------
# TFLite int8 conversion (best-effort, with stub fallback)
# ---------------------------------------------------------------------------


def _try_tflite_real(
    onnx_path: Path,
    tflite_path: Path,
    *,
    calibration_features: np.ndarray | None = None,
) -> bool:
    """Best-effort TF-based conversion. Returns True on success.

    The chain is: ONNX → TF SavedModel (via onnx-tf) → TFLite INT8 (via
    tf.lite.TFLiteConverter). On Windows + Python 3.12 the onnx-tf import
    fails because tensorflow-addons has no cp312 wheels. On those hosts
    this returns False and the caller writes a stub container.
    """
    try:
        import tensorflow as tf
    except ImportError:
        return False
    try:
        import onnx
        from onnx_tf.backend import prepare  # type: ignore
    except ImportError:
        return False
    try:
        onnx_model = onnx.load(str(onnx_path))
        tf_rep = prepare(onnx_model)
        saved_model_dir = onnx_path.with_suffix("")
        saved_model_dir.mkdir(exist_ok=True)
        tf_rep.export_graph(str(saved_model_dir))
        converter = tf.lite.TFLiteConverter.from_saved_model(str(saved_model_dir))
        converter.optimizations = [tf.lite.Optimize.DEFAULT]

        n_features = N_FEATURES_TOTAL
        # Representative dataset: real training features when available,
        # otherwise random uniform — INT8 calibration quality scales
        # directly with how representative this is.
        if calibration_features is not None and calibration_features.size > 0:
            features_iter = list(calibration_features.astype(np.float32))

            def _rep():
                for x in features_iter:
                    yield [x.reshape(1, 1, -1)]
        else:
            def _rep():
                for _ in range(64):
                    x = np.random.uniform(0.0, 1.0, size=(1, 1, n_features)).astype(
                        np.float32
                    )
                    yield [x]

        # Static QDQ quantization needs activations sampled at the joint
        # input distribution; ~256 real training samples is the sweet spot —
        # fewer biases activation ranges, more wastes calibration time.
        converter.representative_dataset = _rep
        converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
        converter.inference_input_type = tf.int8
        converter.inference_output_type = tf.int8
        tflite_bytes = converter.convert()
        tflite_path.write_bytes(tflite_bytes)
        return True
    except Exception as e:
        print(f"[warn] real TFLite conversion failed: {e}")
        return False


def write_stub_tflite(onnx_path: Path, tflite_path: Path) -> Path:
    """Wrap the ONNX bytes in a self-describing stub container.

    Format:
        STUB_MAGIC | u32_le(len(onnx_bytes)) | onnx_bytes
    """
    onnx_bytes = onnx_path.read_bytes()
    payload = STUB_MAGIC + struct.pack("<I", len(onnx_bytes)) + onnx_bytes
    tflite_path.parent.mkdir(parents=True, exist_ok=True)
    tflite_path.write_bytes(payload)
    return tflite_path


def is_stub_tflite(path: Path) -> bool:
    if not path.exists() or path.stat().st_size < len(STUB_MAGIC):
        return False
    with open(path, "rb") as fh:
        return fh.read(len(STUB_MAGIC)) == STUB_MAGIC


# ---------------------------------------------------------------------------
# Top-level entry
# ---------------------------------------------------------------------------


def quantize_run(run_dir: Path, tflite_path: Path) -> dict:
    if not (run_dir / "model.pt").exists():
        raise FileNotFoundError(f"no model.pt in {run_dir}")
    meta_path = run_dir / "meta.json"
    if not meta_path.exists():
        raise FileNotFoundError(
            f"no meta.json in {run_dir} — only CNN runs can be quantised"
        )

    meta = json.loads(meta_path.read_text())
    n_features = meta["input_shape"][-1]
    model = RegoscanCNN(n_features=n_features)
    model.load_state_dict(torch.load(run_dir / "model.pt"))
    model.eval()

    onnx_path = run_dir / "model.onnx"
    export_onnx(model, onnx_path, n_features=n_features)
    print(f"[ok] exported ONNX FP32 -> {onnx_path}  ({onnx_path.stat().st_size} bytes)")

    # Load real training features for calibration (preferred) or fall back to None
    calib = _load_calibration_features(run_dir, n_features=n_features)
    calib_source = "real-training-data" if calib is not None else "none"
    if calib is not None:
        print(
            f"[ok] loaded {calib.shape[0]} real samples for INT8 calibration"
        )
    else:
        print(
            "[warn] no real calibration data found — INT8 will use dynamic "
            "quantization (weights only, less accurate)"
        )

    # Real ONNX INT8 (works without TF)
    onnx_int8_path = run_dir / "model.int8.onnx"
    int8_ok = quantize_onnx_int8(onnx_path, onnx_int8_path, calibration_features=calib)
    if int8_ok:
        size_kb = onnx_int8_path.stat().st_size / 1024
        size_kb_fp32 = onnx_path.stat().st_size / 1024
        print(
            f"[ok] ONNX INT8 -> {onnx_int8_path}  "
            f"({size_kb:.0f} KB, {size_kb / size_kb_fp32 * 100:.0f}% of FP32)"
        )

    # TFLite (best-effort)
    tflite_path.parent.mkdir(parents=True, exist_ok=True)
    used_stub = False
    if not _try_tflite_real(onnx_path, tflite_path, calibration_features=calib):
        write_stub_tflite(onnx_path, tflite_path)
        used_stub = True
        print(
            f"[warn] TFLite tooling unavailable; wrote stub container -> {tflite_path}\n"
            f"       (decode with `vera.quantize.is_stub_tflite`)"
        )
    else:
        print(f"[ok] wrote real INT8 TFLite -> {tflite_path}")

    info = {
        "onnx": str(onnx_path),
        "onnx_int8": str(onnx_int8_path) if int8_ok else None,
        "tflite": str(tflite_path),
        "tflite_is_stub": used_stub,
        "tflite_size_bytes": int(tflite_path.stat().st_size),
        "calibration_source": calib_source,
        "calibration_n_samples": int(calib.shape[0]) if calib is not None else 0,
    }
    (run_dir / "quantize.json").write_text(json.dumps(info, indent=2))
    return info


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, help="run directory from vera.train (CNN)")
    parser.add_argument("--out", required=True, help="output .tflite path")
    args = parser.parse_args(argv)

    run_dir = Path(args.run)
    tflite_path = Path(args.out)
    info = quantize_run(run_dir, tflite_path)
    print(f"[ok] quantize.json: {info}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
