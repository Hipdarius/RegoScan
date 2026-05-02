#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────
# VERA — INT8 ONNX → TFLite Micro flatbuffer (Linux only)
#
# The vera.quantize CLI tries this conversion natively but on Windows
# + Python 3.12 the toolchain doesn't install (tensorflow-addons has
# no cp312 wheels; ai-edge-torch pulls Linux-only torch-xla). This
# script wraps the conversion for a Linux build server / Docker image
# / WSL2 — anywhere `tensorflow` and `onnx-tf` install cleanly.
#
# Usage:
#   ./scripts/build_tflite_micro.sh [run_dir]
#
# Defaults to runs/cnn_v2 if no argument given. Produces
# runs/<run>/model.tflite as a *real* TensorFlow Lite flatbuffer
# (not the stub container) plus a SHA-256 verification file.
# ─────────────────────────────────────────────────────────────────

set -euo pipefail

# ── Sanity check the environment ──────────────────────────────────
if [[ "$(uname)" != "Linux" ]]; then
    echo "ERROR: requires Linux (got $(uname))." >&2
    echo "       Run inside a container or WSL2." >&2
    exit 1
fi

# Python 3.11 is the maximum supported by tensorflow-addons cp wheels
PYTHON_BIN="${PYTHON_BIN:-python3.11}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    echo "ERROR: $PYTHON_BIN not found on PATH." >&2
    echo "       Install Python 3.11 or set PYTHON_BIN env var." >&2
    exit 1
fi

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

RUN_DIR="${1:-runs/cnn_v2}"
if [[ ! -f "$RUN_DIR/model.pt" ]]; then
    echo "ERROR: $RUN_DIR/model.pt not found." >&2
    echo "       Train first: uv run python -m vera.train --model cnn ..." >&2
    exit 1
fi

# ── Set up an isolated venv for the TF chain ──────────────────────
VENV_DIR="${VENV_DIR:-.venv-tflite}"
if [[ ! -d "$VENV_DIR" ]]; then
    echo "[setup] creating $VENV_DIR with $PYTHON_BIN"
    "$PYTHON_BIN" -m venv "$VENV_DIR"
    "$VENV_DIR/bin/pip" install --upgrade pip
    "$VENV_DIR/bin/pip" install \
        "numpy<2.0" \
        "torch>=2.2" \
        "onnx>=1.15" \
        "tensorflow==2.15.0" \
        "onnx-tf==1.10.0" \
        "tensorflow-probability==0.23.0"
    # Install vera locally so the quantize module imports cleanly
    "$VENV_DIR/bin/pip" install -e . --no-deps
fi

# ── Run the conversion via the canonical entrypoint ───────────────
# The INT8 ONNX produced earlier (via onnxruntime.quantization) is the
# source of truth for activation ranges. The TFLite path will produce
# a real flatbuffer using the same calibration data.
echo "[convert] $RUN_DIR -> $RUN_DIR/model.tflite"
"$VENV_DIR/bin/python" -m vera.quantize \
    --run "$RUN_DIR" \
    --out "$RUN_DIR/model.tflite"

# ── Verify the output is a real flatbuffer ────────────────────────
TFLITE="$RUN_DIR/model.tflite"
if [[ ! -f "$TFLITE" ]]; then
    echo "ERROR: $TFLITE was not produced." >&2
    exit 1
fi

# Real TFLite flatbuffers start with TFL3 magic at byte offset 4.
# The stub container starts with VERA_TFLITE_STUB.
HEADER="$(head -c 16 "$TFLITE" | tr -d '\0' || true)"
if [[ "$HEADER" == VERA_TFLITE_STUB* ]]; then
    echo "FAIL: got the stub container — TF tooling didn't engage." >&2
    echo "      See $RUN_DIR/quantize.json for diagnostics." >&2
    exit 1
fi

# Hash for reproducibility
SHA="$(sha256sum "$TFLITE" | awk '{print $1}')"
echo "$SHA  $(basename "$TFLITE")" > "$TFLITE.sha256"

SIZE_KB="$(($(stat -c%s "$TFLITE") / 1024))"
echo "[ok]    real TFLite ${SIZE_KB} KB  sha256=${SHA:0:16}"
echo "[next]  flash to ESP32 via PlatformIO with the model bytes"
echo "        embedded as a C array (xxd -i)."
