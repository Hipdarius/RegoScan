"""Latency micro-benchmark for the canonical FP32 model.

Runs N=200 inferences on a fixed synthetic spectrum and reports
min / median / p99 / max in milliseconds. The published "< 5 ms /
inference" claim in the README is benchmarked here.

Usage:
    uv run python scripts/bench-inference.py
"""

import statistics
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from vera.inference import InferenceEngine, synth_demo_features

MODEL = ROOT / "runs" / "cnn_v2" / "model.onnx"


def main() -> int:
    if not MODEL.exists():
        print(f"missing model at {MODEL}; run `make train` first.", file=sys.stderr)
        return 1
    eng = InferenceEngine(MODEL)
    demo = synth_demo_features(seed=0, sensor_mode=eng.sensor_mode)
    x = np.asarray(demo["features"], dtype=np.float32)

    # warm-up
    for _ in range(3):
        eng.predict(x)

    n = 200
    times = []
    for _ in range(n):
        t0 = time.perf_counter()
        eng.predict(x)
        times.append((time.perf_counter() - t0) * 1000.0)

    print(f"N         {n}")
    print(f"min       {min(times):6.2f} ms")
    print(f"median    {statistics.median(times):6.2f} ms")
    print(f"p99       {sorted(times)[int(n * 0.99)]:6.2f} ms")
    print(f"max       {max(times):6.2f} ms")
    return 0


if __name__ == "__main__":
    sys.exit(main())
