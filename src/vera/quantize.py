"""Quantise a trained VERA CNN run to int8 TFLite.

Strategy
--------
The full PyTorch -> ONNX -> TF -> TFLite int8 conversion chain requires
``tensorflow``, ``onnx-tf`` (or ``ai-edge-torch``), and a calibration
dataset — all heavy dependencies that don't pull cleanly on every host.
We follow the spec in the brief:

  > stub OK if tooling missing, but must run end-to-end on CPU and
  > emit a .tflite file

So this step always:

1. Loads ``runs/<run>/model.pt`` and the meta.json the trainer wrote.
2. Exports the model to ``runs/<run>/model.onnx`` via ``torch.onnx.export``
   (vanilla torch — no extras needed). This is the **real** artefact a
   downstream embedded toolchain will consume.
3. Tries to use ``tensorflow`` / ``ai_edge_litert`` to do a real INT8
   TFLite conversion. If unavailable, writes a small **stub TFLite file**
   that wraps the ONNX bytes inside a clearly-marked container so the
   acceptance test sees a non-empty file at the requested path.

The stub container starts with the magic header ``VERA_TFLITE_STUB\\0``
followed by a 4-byte little-endian length and the ONNX payload. Real
embedded code will of course require a real flatbuffer file produced by
the conversion path; for the scaffolding session this is enough to prove
the wiring is in place.
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
# ONNX export
# ---------------------------------------------------------------------------


def export_onnx(model: RegoscanCNN, out_path: Path, *, opset: int = 17, n_features: int | None = None) -> Path:
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
# TFLite int8 conversion (best-effort, with stub fallback)
# ---------------------------------------------------------------------------


def _try_tflite_real(onnx_path: Path, tflite_path: Path) -> bool:
    """Best-effort TF-based conversion. Returns True on success."""
    try:
        import tensorflow as tf  # noqa: F401
    except ImportError:
        return False
    try:
        from onnx_tf.backend import prepare  # type: ignore
        import onnx
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
        # Representative dataset for int8 calibration: random spectra in [0, 1]
        def _rep():
            for _ in range(64):
                x = np.random.uniform(0.0, 1.0, size=(1, 1, N_FEATURES_TOTAL)).astype(np.float32)
                yield [x]
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
    print(f"[ok] exported ONNX -> {onnx_path}  ({onnx_path.stat().st_size} bytes)")

    tflite_path.parent.mkdir(parents=True, exist_ok=True)
    used_stub = False
    if not _try_tflite_real(onnx_path, tflite_path):
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
        "tflite": str(tflite_path),
        "tflite_is_stub": used_stub,
        "tflite_size_bytes": int(tflite_path.stat().st_size),
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
