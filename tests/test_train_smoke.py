"""1-epoch smoke tests for both training paths.

These do not check accuracy — only that the train CLI runs without error,
emits the expected artefacts, and that those artefacts are loadable for
inference. They are the canary that the wiring still flows when something
upstream changes (schema, augmentation, etc.).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import torch

from vera.io_csv import write_measurements_csv
from vera.models.cnn import RegoscanCNN, count_params
from vera.models.plsr import build_baseline_features, load_baseline
from vera.schema import N_FEATURES_TOTAL, WAVELENGTHS
from vera.synth import Endmembers, synth_dataset
from vera.train import main as train_main


def _toy_endmembers() -> Endmembers:
    lam = WAVELENGTHS
    x = (lam - lam.min()) / (lam.max() - lam.min())
    olivine = 0.20 + 0.60 * x
    pyroxene = 0.15 + 0.50 * x
    anorthite = 0.55 + 0.30 * x
    ilmenite = 0.05 + 0.05 * x
    glass = 0.04 + 0.22 * x
    spectra = np.stack([olivine, pyroxene, anorthite, ilmenite, glass], axis=0)
    swir = np.array([
        [0.75, 0.68],
        [0.55, 0.50],
        [0.82, 0.80],
        [0.09, 0.08],
        [0.28, 0.32],
    ])
    return Endmembers(wavelengths_nm=lam, spectra=spectra, swir=swir, source="toy")


@pytest.fixture
def synth_csv(tmp_path: Path) -> Path:
    measurements = synth_dataset(
        _toy_endmembers(),
        n_samples=20,
        measurements_per_sample=4,
        seed=0,
    )
    p = tmp_path / "smoke.csv"
    write_measurements_csv(measurements, p)
    return p


# ---------------------------------------------------------------------------
# Architecture sanity
# ---------------------------------------------------------------------------


def test_cnn_forward_shapes_and_param_count():
    model = RegoscanCNN()
    n = count_params(model)
    # 1D ResNet target envelope: 500k – 1M params
    assert 500_000 <= n <= 1_000_000, f"unexpected param count: {n}"
    x = torch.zeros(2, 1, N_FEATURES_TOTAL)
    logits, ilm = model(x)
    assert logits.shape == (2, 6)
    assert ilm.shape == (2,)
    # head_reg uses sigmoid → outputs in (0, 1)
    assert (ilm >= 0).all() and (ilm <= 1).all()


# ---------------------------------------------------------------------------
# PLSR smoke
# ---------------------------------------------------------------------------


def test_plsr_smoke_trains_and_persists(synth_csv: Path, tmp_path: Path):
    out = tmp_path / "plsr_run"
    rc = train_main([
        "--model", "plsr",
        "--data", str(synth_csv),
        "--out", str(out),
        "--seed", "0",
        "--val-frac", "0.2",
        "--test-frac", "0.2",
    ])
    assert rc == 0
    assert (out / "model.pkl").exists()
    assert (out / "run.json").exists()
    assert (out / "split.json").exists()

    manifest = json.loads((out / "run.json").read_text())
    assert manifest["model"] == "plsr"
    for split in ("train", "val", "test"):
        assert split in manifest["metrics"]

    # The pickled bundle must be loadable and infer cleanly.
    bb = load_baseline(out / "model.pkl")
    from vera.datasets import to_bundle
    from vera.io_csv import read_measurements_csv
    df = read_measurements_csv(synth_csv)
    bundle = to_bundle(df.head(8))
    X = build_baseline_features(bundle)
    pred_cls, pred_ilm = bb.predict(X)
    assert pred_cls.shape == (8,)
    assert pred_ilm.shape == (8,)
    assert ((pred_ilm >= 0) & (pred_ilm <= 1)).all()


# ---------------------------------------------------------------------------
# CNN smoke
# ---------------------------------------------------------------------------


def test_cnn_smoke_one_epoch(synth_csv: Path, tmp_path: Path):
    out = tmp_path / "cnn_run"
    rc = train_main([
        "--model", "cnn",
        "--data", str(synth_csv),
        "--out", str(out),
        "--seed", "0",
        "--val-frac", "0.2",
        "--test-frac", "0.2",
        "--epochs", "1",
        "--batch-size", "8",
        "--lr", "1e-3",
    ])
    assert rc == 0
    assert (out / "model.pt").exists()
    assert (out / "run.json").exists()
    assert (out / "meta.json").exists()
    assert (out / "split.json").exists()

    manifest = json.loads((out / "run.json").read_text())
    assert manifest["model"] == "cnn"
    assert manifest["epochs_completed"] == 1
    # 1-epoch accuracy is unconstrained — only require it's a real number.
    assert isinstance(manifest["metrics"]["test"]["top1_acc"], float)

    # Reload weights into a fresh model and run a single forward pass.
    model = RegoscanCNN()
    model.load_state_dict(torch.load(out / "model.pt"))
    model.eval()
    x = torch.zeros(1, 1, N_FEATURES_TOTAL)
    logits, ilm = model(x)
    assert logits.shape == (1, 6)
    assert ilm.shape == (1,)


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_cnn_training_is_deterministic_at_fixed_seed(synth_csv: Path, tmp_path: Path):
    out_a = tmp_path / "run_a"
    out_b = tmp_path / "run_b"
    common = [
        "--model", "cnn",
        "--data", str(synth_csv),
        "--seed", "7",
        "--val-frac", "0.2",
        "--test-frac", "0.2",
        "--epochs", "2",
        "--batch-size", "8",
        "--lr", "1e-3",
    ]
    assert train_main(common + ["--out", str(out_a)]) == 0
    assert train_main(common + ["--out", str(out_b)]) == 0

    sa = torch.load(out_a / "model.pt")
    sb = torch.load(out_b / "model.pt")
    assert set(sa.keys()) == set(sb.keys())
    for k in sa:
        assert torch.allclose(sa[k], sb[k]), f"weight {k} not reproducible"


# ---------------------------------------------------------------------------
# AS7265x dual-sensor support (v1.1)
# ---------------------------------------------------------------------------

from vera.schema import get_feature_count


def test_cnn_forward_multispectral_33_features():
    """CNN with n_features=33 (multispectral) produces correct output shapes."""
    n_feat = get_feature_count("multispectral")  # 33
    model = RegoscanCNN(n_features=n_feat)
    x = torch.zeros(2, 1, n_feat)
    logits, ilm = model(x)
    assert logits.shape == (2, 6)
    assert ilm.shape == (2,)
    assert (ilm >= 0).all() and (ilm <= 1).all()


def test_cnn_forward_combined_321_features():
    """CNN with n_features=321 (combined) produces correct output shapes."""
    n_feat = get_feature_count("combined")  # 321
    model = RegoscanCNN(n_features=n_feat)
    x = torch.zeros(2, 1, n_feat)
    logits, ilm = model(x)
    assert logits.shape == (2, 6)
    assert ilm.shape == (2,)
    assert (ilm >= 0).all() and (ilm <= 1).all()


def test_cnn_multispectral_uses_smaller_kernel():
    """When n_features < 64, the stem should use kernel_size=3 instead of 9
    to prevent the spatial dimension from collapsing too fast."""
    n_feat = get_feature_count("multispectral")  # 31
    model = RegoscanCNN(n_features=n_feat)
    # The stem's first layer is a Conv1d
    first_conv = model.stem[0]
    assert first_conv.kernel_size == (3,), (
        f"expected kernel_size=(3,) for small input, got {first_conv.kernel_size}"
    )
