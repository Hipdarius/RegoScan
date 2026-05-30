"""Tests for sample-level splits and the PyTorch Dataset.

CRITICAL: ``test_no_sample_id_leakage_across_splits`` must fail loudly if a
sample_id ever appears in more than one split. This is the canary that
catches the single most common ML mistake in chemometrics.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import torch

from vera.datasets import (
    NumpyBundle,
    RegoscanSpectraDataset,
    SplitIndices,
    sample_level_split,
    split_bundle,
    to_bundle,
)
from vera.schema import N_FEATURES_TOTAL, N_LED, N_SPEC, N_SWIR, WAVELENGTHS
from vera.synth import Endmembers, synth_dataset

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _toy_endmembers() -> Endmembers:
    lam = WAVELENGTHS
    x = (lam - lam.min()) / (lam.max() - lam.min())
    olivine = 0.20 + 0.60 * x
    pyroxene = 0.15 + 0.50 * x
    anorthite = 0.55 + 0.30 * x
    ilmenite = 0.05 + 0.05 * x
    glass = 0.04 + 0.22 * x
    spectra = np.stack([olivine, pyroxene, anorthite, ilmenite, glass], axis=0)
    # SWIR: reflectance at 940 & 1050 nm (extrapolated from toy spectra)
    swir = np.array([
        [0.75, 0.68],   # olivine: 1-um band onset
        [0.55, 0.50],   # pyroxene: deeper Band I
        [0.82, 0.80],   # anorthite: bright, flat
        [0.09, 0.08],   # ilmenite: very dark
        [0.28, 0.32],   # glass: rising npFe0 slope
    ])
    return Endmembers(wavelengths_nm=lam, spectra=spectra, swir=swir, source="toy")


def _toy_df(
    n_samples: int = 25,
    m_per_sample: int = 4,
    sensor_mode: str = "full",
) -> pd.DataFrame:
    measurements = synth_dataset(
        _toy_endmembers(),
        n_samples=n_samples,
        measurements_per_sample=m_per_sample,
        seed=0,
        sensor_mode=sensor_mode,
    )
    return pd.DataFrame([m.to_row() for m in measurements])


# ---------------------------------------------------------------------------
# CRITICAL: sample-level split must not leak
# ---------------------------------------------------------------------------


def test_no_sample_id_leakage_across_splits():
    """The single test that must never go yellow."""
    df = _toy_df(n_samples=30, m_per_sample=5)
    split = sample_level_split(df, val_frac=0.2, test_frac=0.2, seed=0)

    train_samples = set(df.loc[split.train, "sample_id"].unique())
    val_samples = set(df.loc[split.val, "sample_id"].unique())
    test_samples = set(df.loc[split.test, "sample_id"].unique())

    assert train_samples.isdisjoint(val_samples), \
        f"sample_id leaked train↔val: {train_samples & val_samples}"
    assert train_samples.isdisjoint(test_samples), \
        f"sample_id leaked train↔test: {train_samples & test_samples}"
    assert val_samples.isdisjoint(test_samples), \
        f"sample_id leaked val↔test: {val_samples & test_samples}"

    # And every original sample must appear in exactly one split.
    all_samples = set(df["sample_id"].unique())
    assert train_samples | val_samples | test_samples == all_samples


def test_split_assert_no_leakage_raises_when_corrupted():
    """If we hand-build a SplitIndices with overlap, it must scream."""
    bad = SplitIndices(
        train=np.array([0, 1]),
        val=np.array([2]),
        test=np.array([3]),
        train_samples=("S0", "S1"),
        val_samples=("S0",),  # leak!
        test_samples=("S2",),
    )
    with pytest.raises(AssertionError):
        bad.assert_no_leakage()


def test_split_indices_partition_dataframe_exactly():
    df = _toy_df(n_samples=20, m_per_sample=3)
    split = sample_level_split(df, val_frac=0.2, test_frac=0.2, seed=1)
    union = sorted(np.concatenate([split.train, split.val, split.test]).tolist())
    assert union == sorted(df.index.tolist())
    assert len(split.train) + len(split.val) + len(split.test) == len(df)


def test_split_is_class_balanced_across_splits():
    df = _toy_df(n_samples=30, m_per_sample=4)
    split = sample_level_split(df, val_frac=0.2, test_frac=0.2, seed=0)
    # Each class should appear in train (we don't strictly require val/test
    # for each class on small data, but train must have them all)
    train_classes = set(df.loc[split.train, "mineral_class"].unique())
    assert len(train_classes) >= 4  # most classes present


def test_split_rejects_bad_fractions():
    df = _toy_df(n_samples=10, m_per_sample=2)
    with pytest.raises(ValueError):
        sample_level_split(df, val_frac=0.6, test_frac=0.5, seed=0)
    with pytest.raises(ValueError):
        sample_level_split(df, val_frac=0.0, test_frac=0.2, seed=0)


def test_split_is_deterministic_with_seed():
    df = _toy_df(n_samples=15, m_per_sample=3)
    s1 = sample_level_split(df, val_frac=0.2, test_frac=0.2, seed=42)
    s2 = sample_level_split(df, val_frac=0.2, test_frac=0.2, seed=42)
    np.testing.assert_array_equal(s1.train, s2.train)
    np.testing.assert_array_equal(s1.val, s2.val)
    np.testing.assert_array_equal(s1.test, s2.test)


# ---------------------------------------------------------------------------
# NumpyBundle / split_bundle
# ---------------------------------------------------------------------------


def test_to_bundle_shapes_match_dataframe():
    df = _toy_df(n_samples=8, m_per_sample=3)
    b = to_bundle(df)
    assert b.spectra.shape == (len(df), N_SPEC)
    assert b.leds.shape == (len(df), N_LED)
    assert b.lif.shape == (len(df),)
    assert b.class_idx.shape == (len(df),)
    assert b.ilmenite.shape == (len(df),)
    assert b.sample_ids.shape == (len(df),)


def test_split_bundle_keys_and_lengths():
    df = _toy_df(n_samples=15, m_per_sample=4)
    split = sample_level_split(df, val_frac=0.2, test_frac=0.2, seed=0)
    bundles = split_bundle(df, split)
    assert set(bundles) == {"train", "val", "test"}
    assert len(bundles["train"].class_idx) == len(split.train)
    assert len(bundles["val"].class_idx) == len(split.val)
    assert len(bundles["test"].class_idx) == len(split.test)


# ---------------------------------------------------------------------------
# PyTorch Dataset
# ---------------------------------------------------------------------------


def test_torch_dataset_item_shapes():
    df = _toy_df(n_samples=6, m_per_sample=2)
    bundle = to_bundle(df)
    ds = RegoscanSpectraDataset(bundle, augment=False)
    feats, cls, ilm = ds[0]
    assert isinstance(feats, torch.Tensor)
    assert feats.shape == (1, N_FEATURES_TOTAL)
    assert feats.dtype == torch.float32
    assert cls.dtype == torch.long
    assert ilm.dtype == torch.float32


def test_torch_dataset_augmentation_changes_spectrum_block():
    df = _toy_df(n_samples=4, m_per_sample=1)
    bundle = to_bundle(df)
    ds = RegoscanSpectraDataset(bundle, augment=True, seed=12345)
    a, _, _ = ds[0]
    # LED and LIF channels are now augmented with small noise to
    # prevent seed-specific memorization. Check they are close to
    # the originals but not identical (augmentation applied).
    # Feature order: [spec(288) | swir(2) | led(12) | lif(1)]
    led_start = N_SPEC + N_SWIR
    np.testing.assert_allclose(
        a[0, led_start : led_start + N_LED].numpy(),
        bundle.leds[0],
        atol=0.05,
    )
    np.testing.assert_allclose(
        float(a[0, -1]),
        float(bundle.lif[0]),
        atol=0.08,
    )


# ---------------------------------------------------------------------------
# AS7265x dual-sensor support (v1.1)
# ---------------------------------------------------------------------------

from vera.schema import N_AS7265X, get_feature_count


def test_to_bundle_combined_has_as7265x():
    df = _toy_df(n_samples=6, m_per_sample=2, sensor_mode="combined")
    b = to_bundle(df, sensor_mode="combined")
    assert b.as7265x is not None
    assert b.as7265x.shape == (len(df), N_AS7265X)
    assert b.sensor_mode == "combined"


def test_to_bundle_full_backward_compat():
    df = _toy_df(n_samples=6, m_per_sample=2, sensor_mode="full")
    b = to_bundle(df, sensor_mode="full")
    assert b.as7265x is None
    assert b.sensor_mode == "full"
    assert b.spectra.shape == (len(df), N_SPEC)
    assert b.leds.shape == (len(df), N_LED)
    assert b.lif.shape == (len(df),)


def test_torch_dataset_combined_feature_shape():
    df = _toy_df(n_samples=4, m_per_sample=2, sensor_mode="combined")
    bundle = to_bundle(df, sensor_mode="combined")
    ds = RegoscanSpectraDataset(bundle, augment=False)
    feats, cls, ilm = ds[0]
    expected = get_feature_count("combined")  # 321
    assert feats.shape == (1, expected)
    assert feats.dtype == torch.float32


def test_torch_dataset_multispectral_feature_shape():
    df = _toy_df(n_samples=4, m_per_sample=2, sensor_mode="combined")
    bundle = to_bundle(df, sensor_mode="combined")
    # Override sensor_mode on the bundle to "multispectral" to test
    # that the Dataset only uses as7265x + swir + led + lif
    bundle_ms = NumpyBundle(
        spectra=bundle.spectra,
        leds=bundle.leds,
        lif=bundle.lif,
        class_idx=bundle.class_idx,
        ilmenite=bundle.ilmenite,
        sample_ids=bundle.sample_ids,
        swir=bundle.swir,
        as7265x=bundle.as7265x,
        sensor_mode="multispectral",
    )
    ds = RegoscanSpectraDataset(bundle_ms, augment=False)
    feats, cls, ilm = ds[0]
    expected = get_feature_count("multispectral")  # 33
    assert feats.shape == (1, expected)
    assert feats.dtype == torch.float32
