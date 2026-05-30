"""Evaluation report for a trained VERA run.

Reads a run directory produced by ``vera.train`` and writes a complete
JSON+text report next to it:

  - confusion matrix (5×5)
  - per-class precision / recall / F1
  - top-1 accuracy with bootstrap 95% CI
  - ilmenite_fraction R² and RMSE with bootstrap 95% CI
  - failure analysis: per-class top mis-prediction targets
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless — never pop a window, even in CI / on Vercel builds
import matplotlib.pyplot as plt
import numpy as np
import torch

from vera.datasets import (
    NumpyBundle,
    RegoscanSpectraDataset,
    sample_level_split,
    split_bundle,
)
from vera.io_csv import read_measurements_csv
from vera.models.cnn import RegoscanCNN
from vera.models.plsr import build_baseline_features, load_baseline
from vera.schema import INDEX_TO_CLASS, MINERAL_CLASSES, N_CLASSES

# ---------------------------------------------------------------------------
# Pure-numpy metrics
# ---------------------------------------------------------------------------


def confusion_matrix(true: np.ndarray, pred: np.ndarray, n_classes: int) -> np.ndarray:
    cm = np.zeros((n_classes, n_classes), dtype=np.int64)
    for t, p in zip(true, pred):
        cm[int(t), int(p)] += 1
    return cm


def per_class_prf(cm: np.ndarray) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for i in range(cm.shape[0]):
        tp = cm[i, i]
        fp = cm[:, i].sum() - tp
        fn = cm[i, :].sum() - tp
        precision = float(tp / (tp + fp)) if (tp + fp) else 0.0
        recall = float(tp / (tp + fn)) if (tp + fn) else 0.0
        f1 = (
            float(2 * precision * recall / (precision + recall))
            if (precision + recall)
            else 0.0
        )
        out[INDEX_TO_CLASS[i]] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": int(cm[i, :].sum()),
        }
    return out


def bootstrap_ci(values: np.ndarray, fn, *, n: int = 500, seed: int = 0) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    if values.size == 0:
        return (float("nan"), float("nan"))
    n_obs = values.shape[0]
    samples = []
    for _ in range(n):
        idx = rng.integers(0, n_obs, size=n_obs)
        samples.append(fn(values[idx]))
    arr = np.asarray(samples)
    return float(np.percentile(arr, 2.5)), float(np.percentile(arr, 97.5))


def accuracy_ci(true: np.ndarray, pred: np.ndarray, seed: int = 0) -> tuple[float, float]:
    correct = (true == pred).astype(np.float64)
    return bootstrap_ci(correct, np.mean, seed=seed)


def rmse(true: np.ndarray, pred: np.ndarray) -> float:
    return float(np.sqrt(np.mean((true - pred) ** 2)))


def r2(true: np.ndarray, pred: np.ndarray) -> float:
    var = float(np.var(true))
    return float(1.0 - np.var(pred - true) / var) if var > 0 else float("nan")


def regression_ci(true: np.ndarray, pred: np.ndarray, seed: int = 0) -> dict[str, tuple[float, float]]:
    pairs = np.stack([true, pred], axis=1)

    def _rmse(x):
        return float(np.sqrt(np.mean((x[:, 0] - x[:, 1]) ** 2)))

    def _r2(x):
        v = float(np.var(x[:, 0]))
        return float(1.0 - np.var(x[:, 1] - x[:, 0]) / v) if v > 0 else float("nan")

    return {
        "rmse_ci95": bootstrap_ci(pairs, _rmse, seed=seed),
        "r2_ci95": bootstrap_ci(pairs, _r2, seed=seed),
    }


# ---------------------------------------------------------------------------
# Inference dispatch
# ---------------------------------------------------------------------------


@dataclass
class Predictions:
    pred_cls: np.ndarray
    pred_ilm: np.ndarray
    true_cls: np.ndarray
    true_ilm: np.ndarray
    sample_ids: np.ndarray


def predict_baseline(run_dir: Path, bundle: NumpyBundle) -> Predictions:
    bb = load_baseline(run_dir / "model.pkl")
    X = build_baseline_features(bundle)
    pred_cls, pred_ilm = bb.predict(X)
    return Predictions(
        pred_cls=pred_cls,
        pred_ilm=pred_ilm,
        true_cls=bundle.class_idx,
        true_ilm=bundle.ilmenite,
        sample_ids=bundle.sample_ids,
    )


def predict_cnn(run_dir: Path, bundle: NumpyBundle) -> Predictions:
    model = RegoscanCNN()
    model.load_state_dict(torch.load(run_dir / "model.pt"))
    model.eval()
    ds = RegoscanSpectraDataset(bundle, augment=False)
    pred_cls: list[int] = []
    pred_ilm: list[float] = []
    with torch.no_grad():
        for i in range(len(ds)):
            x, _, _ = ds[i]
            logits, ilm = model(x.unsqueeze(0))
            pred_cls.append(int(logits.argmax(dim=1).item()))
            pred_ilm.append(float(ilm.item()))
    return Predictions(
        pred_cls=np.asarray(pred_cls, dtype=np.int64),
        pred_ilm=np.asarray(pred_ilm, dtype=np.float64),
        true_cls=bundle.class_idx,
        true_ilm=bundle.ilmenite,
        sample_ids=bundle.sample_ids,
    )


# ---------------------------------------------------------------------------
# Report builder
# ---------------------------------------------------------------------------


def build_report(preds: Predictions, *, model_name: str) -> dict:
    cm = confusion_matrix(preds.true_cls, preds.pred_cls, N_CLASSES)
    prf = per_class_prf(cm)
    acc = float((preds.true_cls == preds.pred_cls).mean()) if preds.true_cls.size else float("nan")
    acc_lo, acc_hi = accuracy_ci(preds.true_cls, preds.pred_cls)
    reg_ci = regression_ci(preds.true_ilm, preds.pred_ilm)

    # failure analysis: most common confused-pair per true class
    confusions: dict[str, list[tuple[str, int]]] = {}
    for i in range(N_CLASSES):
        row = cm[i, :].copy()
        row[i] = 0  # exclude correct
        order = np.argsort(-row)
        confusions[INDEX_TO_CLASS[i]] = [
            (INDEX_TO_CLASS[int(j)], int(row[j])) for j in order if row[j] > 0
        ]

    return {
        "model": model_name,
        "n_test": int(preds.true_cls.size),
        "top1_accuracy": acc,
        "top1_accuracy_ci95": [acc_lo, acc_hi],
        "ilm_rmse": rmse(preds.true_ilm, preds.pred_ilm),
        "ilm_r2": r2(preds.true_ilm, preds.pred_ilm),
        "ilm_rmse_ci95": list(reg_ci["rmse_ci95"]),
        "ilm_r2_ci95": list(reg_ci["r2_ci95"]),
        "confusion_matrix": cm.tolist(),
        "class_names": list(MINERAL_CLASSES),
        "per_class": prf,
        "failure_analysis": confusions,
    }


def plot_confusion_matrix(
    cm: np.ndarray, class_names: list[str], out_path: Path
) -> Path:
    """Save a labelled confusion-matrix PNG to ``out_path``."""
    fig, ax = plt.subplots(figsize=(6.4, 5.2), dpi=140)
    cm_norm = cm.astype(np.float64) / np.maximum(cm.sum(axis=1, keepdims=True), 1)
    im = ax.imshow(cm_norm, cmap="magma", vmin=0.0, vmax=1.0)
    ax.set_xticks(np.arange(len(class_names)))
    ax.set_yticks(np.arange(len(class_names)))
    ax.set_xticklabels(class_names, rotation=40, ha="right")
    ax.set_yticklabels(class_names)
    ax.set_xlabel("predicted")
    ax.set_ylabel("true")
    ax.set_title("Confusion matrix (row-normalised)")
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            txt_color = "white" if cm_norm[i, j] < 0.55 else "black"
            ax.text(
                j, i, f"{cm[i, j]}",
                ha="center", va="center", color=txt_color, fontsize=9,
            )
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="row-normalised")
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path)
    plt.close(fig)
    return out_path


def plot_ilmenite_scatter(
    true_ilm: np.ndarray, pred_ilm: np.ndarray, out_path: Path
) -> Path:
    """Save a true-vs-predicted scatter for the ilmenite regression target."""
    fig, ax = plt.subplots(figsize=(5.6, 5.2), dpi=140)
    ax.scatter(true_ilm, pred_ilm, c="#00d1ff", s=22, alpha=0.75, edgecolor="#0a3b4a")
    lims = [0.0, 1.0]
    ax.plot(lims, lims, "--", color="#f5a623", linewidth=1.2, label="y = x")
    ax.set_xlim(lims)
    ax.set_ylim(lims)
    ax.set_xlabel("true ilmenite_fraction")
    ax.set_ylabel("predicted ilmenite_fraction")
    ax.set_title("Ilmenite regression — true vs predicted")
    ax.grid(alpha=0.25)
    ax.legend(loc="upper left")
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path)
    plt.close(fig)
    return out_path


def render_text(report: dict) -> str:
    lines: list[str] = []
    lines.append("# VERA evaluation report")
    lines.append(f"model: {report['model']}")
    lines.append(f"n_test: {report['n_test']}")
    lines.append("")
    lo, hi = report["top1_accuracy_ci95"]
    lines.append(
        f"top-1 accuracy: {report['top1_accuracy']:.3f}  (95% CI [{lo:.3f}, {hi:.3f}])"
    )
    rlo, rhi = report["ilm_rmse_ci95"]
    lines.append(
        f"ilmenite RMSE:  {report['ilm_rmse']:.3f}  (95% CI [{rlo:.3f}, {rhi:.3f}])"
    )
    r2lo, r2hi = report["ilm_r2_ci95"]
    lines.append(
        f"ilmenite R²:    {report['ilm_r2']:.3f}  (95% CI [{r2lo:.3f}, {r2hi:.3f}])"
    )
    lines.append("")
    lines.append("# per-class precision / recall / F1")
    lines.append(f"{'class':<16}{'P':>8}{'R':>8}{'F1':>8}{'support':>10}")
    for cname, m in report["per_class"].items():
        lines.append(
            f"{cname:<16}{m['precision']:>8.3f}{m['recall']:>8.3f}{m['f1']:>8.3f}{m['support']:>10d}"
        )
    lines.append("")
    lines.append("# confusion matrix (rows=true, cols=pred)")
    header = "        " + "".join(f"{n[:8]:>10s}" for n in report["class_names"])
    lines.append(header)
    for i, row in enumerate(report["confusion_matrix"]):
        cells = "".join(f"{v:>10d}" for v in row)
        lines.append(f"{report['class_names'][i][:8]:<8}{cells}")
    lines.append("")
    lines.append("# failure analysis (top mis-predicted targets)")
    for cname, confs in report["failure_analysis"].items():
        if not confs:
            continue
        text = ", ".join(f"{c}({n})" for c, n in confs[:3])
        lines.append(f"  {cname:<16} -> {text}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, help="run directory from vera.train")
    parser.add_argument("--data", required=True, help="path to a VERA CSV")
    parser.add_argument("--split", choices=["test", "val", "train"], default="test")
    args = parser.parse_args(argv)

    run_dir = Path(args.run)
    manifest = json.loads((run_dir / "run.json").read_text())
    model_name = manifest["model"]
    print(f"[ok] evaluating {model_name} run at {run_dir}")

    df = read_measurements_csv(args.data)
    split = sample_level_split(
        df,
        val_frac=manifest.get("val_frac", 0.15),
        test_frac=manifest.get("test_frac", 0.15),
        seed=manifest.get("seed", 0),
    )
    bundles = split_bundle(df, split)
    bundle = bundles[args.split]
    print(f"[ok] split={args.split}  n={len(bundle.class_idx)}")

    if model_name == "plsr":
        preds = predict_baseline(run_dir, bundle)
    elif model_name == "cnn":
        preds = predict_cnn(run_dir, bundle)
    else:
        raise ValueError(f"unknown model in manifest: {model_name}")

    report = build_report(preds, model_name=model_name)
    (run_dir / "eval.json").write_text(json.dumps(report, indent=2))
    text = render_text(report)
    (run_dir / "eval.txt").write_text(text)
    print(text)

    # plots
    cm_path = plot_confusion_matrix(
        np.asarray(report["confusion_matrix"], dtype=np.int64),
        list(MINERAL_CLASSES),
        run_dir / "confusion_matrix.png",
    )
    scat_path = plot_ilmenite_scatter(
        preds.true_ilm, preds.pred_ilm, run_dir / "ilmenite_scatter.png"
    )
    print(f"[ok] wrote plot: {cm_path}")
    print(f"[ok] wrote plot: {scat_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
