#!/usr/bin/env python3
"""Linear vs. Hapke mixing-model ablation.

Trains two CNNs on identically-seeded synthetic datasets that differ
only in mixing model (linear vs Hapke), then evaluates each on the
*opposite* mixing model. The cross-mixing accuracy is a proxy for the
synthetic-to-real domain gap: if the real world is intimate-mixing
(fine regolith, < 100 µm) and we train on linear, how badly do we
generalise?

Output is a single CSV ``runs/ablate_mixing/results.csv``:

    train_model,test_model,top1_acc,ilm_rmse,ilm_r2

Plus the four trained run directories (``runs/ablate_mixing/{linear,
hapke}/`` with the standard ``model.pt`` / ``meta.json`` / etc.).

Run on a small budget (n_samples=200, epochs=5) for a smoke test:

    uv run python scripts/ablate_mixing.py --quick

Or full budget for a paper-grade ablation:

    uv run python scripts/ablate_mixing.py --n-samples 1000 --epochs 30

Note this trains twice and evaluates four-way, so a "full" run takes
~2× the normal training time. The synthetic CSV files are written to
``data/ablate_mixing_{linear,hapke}.csv`` and reused on subsequent
invocations to skip data regeneration.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from vera.inference import resolve_endmembers
from vera.io_csv import (
    extract_feature_matrix,
    extract_labels,
    read_measurements_csv,
    write_measurements_csv,
)
from vera.synth import load_endmembers, synth_dataset

# ---------------------------------------------------------------------------
# Dataset generation
# ---------------------------------------------------------------------------


def generate_dataset(
    out_csv: Path,
    *,
    mixing_model: str,
    n_samples: int,
    measurements_per_sample: int,
    seeds: list[int],
) -> Path:
    """Generate (or reuse) a synthetic CSV using the given mixing model."""
    if out_csv.exists():
        print(f"[reuse] {out_csv} already exists")
        return out_csv

    em = load_endmembers(resolve_endmembers())
    measurements = []
    per_seed = max(1, n_samples // len(seeds))
    for seed in seeds:
        measurements.extend(
            synth_dataset(
                em,
                n_samples=per_seed,
                measurements_per_sample=measurements_per_sample,
                seed=seed,
                mixing_model=mixing_model,
            )
        )
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    write_measurements_csv(measurements, out_csv)
    print(f"[ok] wrote {len(measurements)} rows ({mixing_model}) -> {out_csv}")
    return out_csv


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------


def evaluate_run_on_csv(run_dir: Path, csv_path: Path) -> dict[str, float]:
    """Load the run's ONNX and score against the given CSV.

    We use ONNX rather than reloading PyTorch so we don't need the
    training import path active.
    """
    import onnxruntime as ort

    onnx_path = run_dir / "model.int8.onnx"
    if not onnx_path.exists():
        onnx_path = run_dir / "model.onnx"

    session = ort.InferenceSession(str(onnx_path))
    input_name = session.get_inputs()[0].name

    df = read_measurements_csv(csv_path)
    X = extract_feature_matrix(df).astype(np.float32)
    y_cls, y_ilm = extract_labels(df)

    correct = 0
    ilm_residuals = []
    for i in range(X.shape[0]):
        x = X[i].reshape(1, 1, -1)
        outs = session.run(None, {input_name: x})
        logits, ilm = outs[0][0], float(outs[1].flat[0])
        pred = int(np.argmax(logits))
        correct += int(pred == int(y_cls[i]))
        ilm_residuals.append(ilm - float(y_ilm[i]))

    n = X.shape[0]
    acc = correct / n
    rmse = float(np.sqrt(np.mean(np.asarray(ilm_residuals) ** 2)))
    var_truth = float(np.var(y_ilm))
    r2 = float(1.0 - np.var(ilm_residuals) / var_truth) if var_truth > 0 else float("nan")
    return {"top1_acc": acc, "ilm_rmse": rmse, "ilm_r2": r2, "n_samples": n}


# ---------------------------------------------------------------------------
# Train helper (subprocess to keep memory clean between models)
# ---------------------------------------------------------------------------


def train_run(
    csv_path: Path,
    run_out: Path,
    *,
    epochs: int,
    seed: int,
) -> Path:
    """Invoke vera.train as a subprocess so each run starts fresh."""
    if (run_out / "model.onnx").exists():
        print(f"[reuse] {run_out} already trained")
        return run_out
    cmd = [
        "uv", "run", "python", "-m", "vera.train",
        "--model", "cnn",
        "--data", str(csv_path),
        "--out", str(run_out),
        "--seed", str(seed),
        "--epochs", str(epochs),
        "--batch-size", "64",
        "--lr", "2e-3",
        "--early-stopping", "10",
    ]
    print(f"[train] {' '.join(cmd)}")
    subprocess.run(cmd, check=True, cwd=ROOT)

    # Quantize so evaluate_run_on_csv can prefer model.int8.onnx
    cmd_q = [
        "uv", "run", "python", "-m", "vera.quantize",
        "--run", str(run_out),
        "--out", str(run_out / "model.tflite"),
    ]
    subprocess.run(cmd_q, check=True, cwd=ROOT)
    return run_out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--quick",
        action="store_true",
        help="Smoke test: 200 samples × 5 epochs (under 1 minute)",
    )
    p.add_argument("--n-samples", type=int, default=1000)
    p.add_argument("--measurements-per-sample", type=int, default=20)
    p.add_argument("--epochs", type=int, default=30)
    p.add_argument(
        "--seeds",
        type=int,
        nargs="+",
        default=[0, 1, 2, 3, 42],
        help="Per-class seeds for synthetic generation",
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "runs" / "ablate_mixing",
    )
    args = p.parse_args(argv)

    if args.quick:
        n_samples = 200
        epochs = 5
        meas_per = 4
    else:
        n_samples = args.n_samples
        epochs = args.epochs
        meas_per = args.measurements_per_sample

    args.out_dir.mkdir(parents=True, exist_ok=True)
    data_dir = ROOT / "data"

    # Generate two datasets
    linear_csv = generate_dataset(
        data_dir / "ablate_mixing_linear.csv",
        mixing_model="linear",
        n_samples=n_samples,
        measurements_per_sample=meas_per,
        seeds=args.seeds,
    )
    hapke_csv = generate_dataset(
        data_dir / "ablate_mixing_hapke.csv",
        mixing_model="hapke",
        n_samples=n_samples,
        measurements_per_sample=meas_per,
        seeds=args.seeds,
    )

    # Train two CNNs
    linear_run = train_run(
        linear_csv, args.out_dir / "linear", epochs=epochs, seed=0
    )
    hapke_run = train_run(
        hapke_csv, args.out_dir / "hapke", epochs=epochs, seed=0
    )

    # Four-way evaluation: each model on each test set
    rows: list[dict[str, Any]] = []
    for train_name, run in [("linear", linear_run), ("hapke", hapke_run)]:
        for test_name, csv_path in [("linear", linear_csv), ("hapke", hapke_csv)]:
            metrics = evaluate_run_on_csv(run, csv_path)
            metrics.update(train_model=train_name, test_model=test_name)
            rows.append(metrics)
            print(
                f"  train={train_name:6s} test={test_name:6s}  "
                f"acc={metrics['top1_acc']*100:5.1f}%  "
                f"ilm_rmse={metrics['ilm_rmse']:.3f}  "
                f"R²={metrics['ilm_r2']:.3f}  "
                f"(n={metrics['n_samples']})"
            )

    # Persist to CSV
    out_csv = args.out_dir / "results.csv"
    with open(out_csv, "w", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["train_model", "test_model", "top1_acc", "ilm_rmse", "ilm_r2", "n_samples"],
        )
        writer.writeheader()
        writer.writerows(rows)
    (args.out_dir / "results.json").write_text(json.dumps(rows, indent=2))
    print(f"\n[ok] wrote {out_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
