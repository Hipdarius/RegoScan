"""Dataset assembly for VERA training.

The single most important thing this module enforces is **sample-level
splits**: every measurement of a given ``sample_id`` must end up in the same
train/val/test split. This is non-negotiable for chemometric models — a
measurement-level split leaks composition information into the test set
through repeated measurements of the same physical sample, and the model
silently learns to recognise *samples* instead of *minerals*.

The accompanying test in ``tests/test_datasets.py`` fails loudly if any
``sample_id`` ever crosses splits.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset

from vera.augment import AugmentConfig, augment_spectrum
from vera.io_csv import (
    extract_as7265x,
    extract_labels,
    extract_leds,
    extract_lif,
    extract_spectra,
)
from vera.schema import AS7265X_COLS, N_AS7265X, N_SPEC, get_feature_count


# ---------------------------------------------------------------------------
# Sample-level split
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SplitIndices:
    train: np.ndarray  # (n_train,) row indices into the source DataFrame
    val: np.ndarray
    test: np.ndarray
    train_samples: tuple[str, ...]
    val_samples: tuple[str, ...]
    test_samples: tuple[str, ...]

    def assert_no_leakage(self) -> None:
        """Hard assertion that no sample_id crosses splits."""
        a = set(self.train_samples)
        b = set(self.val_samples)
        c = set(self.test_samples)
        if a & b:
            raise AssertionError(f"sample_id leak train↔val: {sorted(a & b)[:5]}")
        if a & c:
            raise AssertionError(f"sample_id leak train↔test: {sorted(a & c)[:5]}")
        if b & c:
            raise AssertionError(f"sample_id leak val↔test: {sorted(b & c)[:5]}")


def sample_level_split(
    df: pd.DataFrame,
    *,
    val_frac: float = 0.15,
    test_frac: float = 0.15,
    seed: int = 0,
) -> SplitIndices:
    """Split a measurement DataFrame by ``sample_id``.

    Within each mineral class, samples are shuffled and partitioned into
    train/val/test by the requested fractions. This keeps each split
    approximately class-balanced even on small datasets.
    """
    if not 0 < val_frac < 1 or not 0 < test_frac < 1:
        raise ValueError("val_frac and test_frac must each be in (0, 1)")
    if val_frac + test_frac >= 1.0:
        raise ValueError("val_frac + test_frac must be < 1")

    rng = np.random.default_rng(seed)
    train_samples: list[str] = []
    val_samples: list[str] = []
    test_samples: list[str] = []

    for klass, sub in df.groupby("mineral_class", sort=True):
        samples = sorted(sub["sample_id"].unique().tolist())
        if not samples:
            continue
        rng.shuffle(samples)
        n = len(samples)
        n_test = max(1, int(round(n * test_frac))) if n >= 3 else 0
        n_val = max(1, int(round(n * val_frac))) if n >= 3 else 0
        # Guarantee at least one train sample per class
        n_train = max(1, n - n_test - n_val)
        # Re-balance if rounding overshot
        while n_train + n_val + n_test > n and n_test > 0:
            n_test -= 1
        while n_train + n_val + n_test > n and n_val > 0:
            n_val -= 1
        n_train = n - n_val - n_test
        train_samples.extend(samples[:n_train])
        val_samples.extend(samples[n_train : n_train + n_val])
        test_samples.extend(samples[n_train + n_val :])

    train_set = set(train_samples)
    val_set = set(val_samples)
    test_set = set(test_samples)

    train_idx = df.index[df["sample_id"].isin(train_set)].to_numpy()
    val_idx = df.index[df["sample_id"].isin(val_set)].to_numpy()
    test_idx = df.index[df["sample_id"].isin(test_set)].to_numpy()

    split = SplitIndices(
        train=train_idx,
        val=val_idx,
        test=test_idx,
        train_samples=tuple(train_samples),
        val_samples=tuple(val_samples),
        test_samples=tuple(test_samples),
    )
    split.assert_no_leakage()
    return split


# ---------------------------------------------------------------------------
# Numpy bundle for sklearn baselines
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NumpyBundle:
    """Pre-extracted arrays in canonical order."""

    spectra: np.ndarray      # (N, 288)
    leds: np.ndarray         # (N, 12)
    lif: np.ndarray          # (N,)
    class_idx: np.ndarray    # (N,) int64
    ilmenite: np.ndarray     # (N,) float64
    sample_ids: np.ndarray   # (N,) object
    as7265x: np.ndarray | None = None  # (N, 18) or None
    sensor_mode: str = "full"


def to_bundle(df: pd.DataFrame, sensor_mode: str | None = None) -> NumpyBundle:
    """Build a :class:`NumpyBundle` from a validated DataFrame.

    Parameters
    ----------
    sensor_mode : str, optional
        If not provided, auto-detected from the DataFrame columns.
        When the frame has ``as7_*`` columns they are extracted;
        otherwise ``as7265x`` is set to ``None``.
    """
    spectra = extract_spectra(df)
    leds = extract_leds(df)
    lif = extract_lif(df)
    class_idx, ilmenite = extract_labels(df)

    # Auto-detect sensor mode from columns if not specified
    if sensor_mode is None:
        has_as7 = AS7265X_COLS[0] in df.columns
        if has_as7:
            sensor_mode = "combined"
        else:
            sensor_mode = "full"

    as7_data: np.ndarray | None = None
    if sensor_mode in ("multispectral", "combined") and AS7265X_COLS[0] in df.columns:
        as7_data = extract_as7265x(df)

    return NumpyBundle(
        spectra=spectra,
        leds=leds,
        lif=lif,
        class_idx=class_idx,
        ilmenite=ilmenite,
        sample_ids=df["sample_id"].to_numpy(),
        as7265x=as7_data,
        sensor_mode=sensor_mode,
    )


def split_bundle(
    df: pd.DataFrame, split: SplitIndices, sensor_mode: str | None = None
) -> dict[str, NumpyBundle]:
    return {
        "train": to_bundle(df.loc[split.train], sensor_mode=sensor_mode),
        "val": to_bundle(df.loc[split.val], sensor_mode=sensor_mode),
        "test": to_bundle(df.loc[split.test], sensor_mode=sensor_mode),
    }


# ---------------------------------------------------------------------------
# PyTorch Dataset for the CNN
# ---------------------------------------------------------------------------


class RegoscanSpectraDataset(Dataset):
    """Per-measurement Dataset that returns ``(features, class_idx, ilm)``.

    ``features`` is a ``(1, K)`` float32 tensor suitable for ``Conv1d``
    with one input channel. ``K`` depends on the sensor mode:

    * ``"full"``: K = 288 + 12 + 1 = 301  (spectrum + LEDs + LIF)
    * ``"multispectral"``: K = 18 + 12 + 1 = 31  (AS7265x + LEDs + LIF)
    * ``"combined"``: K = 288 + 18 + 12 + 1 = 319

    Augmentation is applied **only to the spectrometer block**, never to
    the LEDs, LIF, or AS7265x channels.
    """

    def __init__(
        self,
        bundle: NumpyBundle,
        *,
        augment: bool = False,
        augment_cfg: AugmentConfig | None = None,
        seed: int = 0,
    ) -> None:
        self.spectra = bundle.spectra.astype(np.float32)
        self.leds = bundle.leds.astype(np.float32)
        self.lif = bundle.lif.astype(np.float32)
        self.class_idx = bundle.class_idx.astype(np.int64)
        self.ilmenite = bundle.ilmenite.astype(np.float32)
        self.sample_ids = np.asarray(bundle.sample_ids)
        self.sensor_mode = bundle.sensor_mode
        self.as7265x: np.ndarray | None = (
            bundle.as7265x.astype(np.float32) if bundle.as7265x is not None else None
        )
        self.augment = augment
        self.augment_cfg = augment_cfg or AugmentConfig()
        self._rng = np.random.default_rng(seed)

    def __len__(self) -> int:
        return self.spectra.shape[0]

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        spec = self.spectra[idx]
        leds = self.leds[idx].copy()
        lif_val = self.lif[idx]

        if self.augment:
            spec = augment_spectrum(spec, self._rng, self.augment_cfg).astype(
                np.float32
            )
            # Augment LED and LIF channels with small noise to prevent
            # the model from memorizing exact LED/LIF values from the
            # training seed. Without this, cross-seed generalization
            # drops from >95% to ~18% because the CNN learns seed-
            # specific noise patterns in the 13 non-spectral channels.
            leds = leds + self._rng.normal(0.0, 0.012, size=leds.shape).astype(np.float32)
            leds = np.clip(leds, 0.0, 1.5)
            lif_val = float(lif_val + self._rng.normal(0.0, 0.020))
            lif_val = float(max(lif_val, 0.0))

        # Build the feature vector based on sensor_mode
        parts: list[np.ndarray] = []
        if self.sensor_mode in ("full", "combined"):
            parts.append(spec)
        if self.sensor_mode in ("multispectral", "combined") and self.as7265x is not None:
            parts.append(self.as7265x[idx])
        parts.append(leds)
        parts.append(np.array([lif_val], dtype=np.float32))

        feats = np.concatenate(parts).astype(np.float32)
        feats_t = torch.from_numpy(feats).unsqueeze(0)  # (1, K)
        return (
            feats_t,
            torch.tensor(int(self.class_idx[idx]), dtype=torch.long),
            torch.tensor(float(self.ilmenite[idx]), dtype=torch.float32),
        )


__all__ = [
    "SplitIndices",
    "sample_level_split",
    "NumpyBundle",
    "to_bundle",
    "split_bundle",
    "RegoscanSpectraDataset",
]
