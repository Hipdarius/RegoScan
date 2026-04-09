"""Read/write the canonical VERA measurement CSV.

Everything that touches a CSV must go through this module so the schema
contract is enforced in exactly one place.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from vera.schema import (
    ALL_COLUMNS,
    AS7265X_COLS,
    LED_COLS,
    LIF_COL,
    Measurement,
    MINERAL_CLASSES,
    N_AS7265X,
    N_LED,
    N_SPEC,
    PACKING_DENSITIES,
    SENSOR_MODES,
    SPEC_COLS,
    columns_for_mode,
)


class SchemaError(ValueError):
    """Raised when a CSV does not match the canonical VERA schema."""


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _detect_sensor_mode(df: pd.DataFrame) -> str:
    """Infer the sensor mode from the columns present in *df*.

    Returns one of ``"full"``, ``"multispectral"``, or ``"combined"``.
    If a ``sensor_mode`` column is present its first value is used;
    otherwise the mode is inferred from the presence/absence of
    spectrometer and AS7265x columns.
    """
    if "sensor_mode" in df.columns and len(df) > 0:
        mode = str(df["sensor_mode"].iloc[0])
        if mode in SENSOR_MODES:
            return mode
    has_spec = SPEC_COLS[0] in df.columns
    has_as7 = AS7265X_COLS[0] in df.columns
    if has_spec and has_as7:
        return "combined"
    if has_as7:
        return "multispectral"
    return "full"


def validate_dataframe(df: pd.DataFrame) -> None:
    """Validate a DataFrame against the canonical schema.

    Cheap structural checks (column names, dtypes, value ranges). Does NOT
    instantiate :class:`~vera.schema.Measurement` for every row -- that
    would be slow on large datasets.

    Supports both legacy v1.0 CSVs (no ``sensor_mode`` or AS7265x columns)
    and v1.1 CSVs with optional ``sensor_mode`` and ``as7_*`` columns.
    """
    # Core columns that must always be present (the v1.0 set)
    missing = [c for c in ALL_COLUMNS if c not in df.columns]
    if missing:
        raise SchemaError(f"missing required columns: {missing[:8]}...")

    # Build the set of allowed columns for this frame
    allowed = set(ALL_COLUMNS)
    allowed.add("sensor_mode")
    allowed.update(AS7265X_COLS)

    extra = [c for c in df.columns if c not in allowed]
    if extra:
        raise SchemaError(f"unexpected columns present: {extra[:8]}...")

    if len(df) == 0:
        return

    # Validate sensor_mode values if column is present
    if "sensor_mode" in df.columns:
        bad_mode = set(df["sensor_mode"].unique()) - set(SENSOR_MODES)
        if bad_mode:
            raise SchemaError(f"invalid sensor_mode values: {sorted(bad_mode)}")

    bad_class = set(df["mineral_class"].unique()) - set(MINERAL_CLASSES)
    if bad_class:
        raise SchemaError(f"invalid mineral_class values: {sorted(bad_class)}")

    bad_pack = set(df["packing_density"].unique()) - set(PACKING_DENSITIES)
    if bad_pack:
        raise SchemaError(f"invalid packing_density values: {sorted(bad_pack)}")

    if (df["ilmenite_fraction"] < 0).any() or (df["ilmenite_fraction"] > 1).any():
        raise SchemaError("ilmenite_fraction outside [0, 1]")

    if (df["integration_time_ms"] <= 0).any():
        raise SchemaError("integration_time_ms must be > 0")

    spec_block = df[list(SPEC_COLS)].to_numpy(dtype=np.float64, copy=False)
    if not np.all(np.isfinite(spec_block)):
        raise SchemaError("spec_* columns contain NaN/Inf")

    led_block = df[list(LED_COLS)].to_numpy(dtype=np.float64, copy=False)
    if not np.all(np.isfinite(led_block)):
        raise SchemaError("led_* columns contain NaN/Inf")

    lif_vals = df[LIF_COL].to_numpy(dtype=np.float64, copy=False)
    if not np.all(np.isfinite(lif_vals)):
        raise SchemaError(f"{LIF_COL} contains NaN/Inf")

    # AS7265x columns: validate if present
    if AS7265X_COLS[0] in df.columns:
        as7_present = [c for c in AS7265X_COLS if c in df.columns]
        if len(as7_present) != N_AS7265X:
            raise SchemaError(
                f"partial AS7265x columns: found {len(as7_present)} of {N_AS7265X}"
            )
        as7_block = df[list(AS7265X_COLS)].to_numpy(dtype=np.float64, copy=False)
        if not np.all(np.isfinite(as7_block)):
            raise SchemaError("as7_* columns contain NaN/Inf")


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------


def read_measurements_csv(path: str | Path) -> pd.DataFrame:
    """Read a VERA CSV from disk and validate it.

    Returns a DataFrame with canonical column ordering and correct dtypes.
    The returned frame always contains the v1.0 ``ALL_COLUMNS``. If the CSV
    also contains ``sensor_mode`` and/or AS7265x columns they are preserved.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"CSV not found: {path}")

    df = pd.read_csv(path)
    validate_dataframe(df)

    # Build ordered column list preserving optional columns
    keep: list[str] = list(ALL_COLUMNS)
    if "sensor_mode" in df.columns:
        # Insert sensor_mode right after the metadata block
        keep = list(ALL_COLUMNS[:len(ALL_COLUMNS)])
        keep.insert(len(ALL_COLUMNS) - len(SPEC_COLS) - len(LED_COLS) - 1, "sensor_mode")
    if AS7265X_COLS[0] in df.columns:
        # Insert AS7265x columns after spec columns, before LED columns
        spec_end = keep.index(SPEC_COLS[-1]) + 1
        for i, c in enumerate(AS7265X_COLS):
            keep.insert(spec_end + i, c)

    df = df[keep].copy()

    df["integration_time_ms"] = df["integration_time_ms"].astype(np.int64)
    df["ilmenite_fraction"] = df["ilmenite_fraction"].astype(np.float64)
    df["ambient_temp_c"] = df["ambient_temp_c"].astype(np.float64)
    for c in SPEC_COLS:
        df[c] = df[c].astype(np.float64)
    for c in LED_COLS:
        df[c] = df[c].astype(np.float64)
    df[LIF_COL] = df[LIF_COL].astype(np.float64)
    if AS7265X_COLS[0] in df.columns:
        for c in AS7265X_COLS:
            df[c] = df[c].astype(np.float64)
    return df


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------


def write_measurements_csv(
    measurements: Iterable[Measurement] | pd.DataFrame,
    path: str | Path,
) -> Path:
    """Write measurements to disk as a canonical CSV.

    Accepts either an iterable of :class:`Measurement` instances or an
    already-built DataFrame. In both cases the output is validated before
    being written. AS7265x and sensor_mode columns are preserved when
    present.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if isinstance(measurements, pd.DataFrame):
        df = measurements.copy()
    else:
        rows = [m.to_row() for m in measurements]
        if rows:
            df = pd.DataFrame(rows)
        else:
            df = pd.DataFrame(columns=list(ALL_COLUMNS))

    # Keep only allowed columns in a canonical order
    ordered: list[str] = []
    for c in ALL_COLUMNS:
        if c in df.columns:
            ordered.append(c)
    # sensor_mode goes right after metadata
    if "sensor_mode" in df.columns and "sensor_mode" not in ordered:
        ordered.insert(len(ordered), "sensor_mode")
    # Insert sensor_mode after packing_density if present
    if "sensor_mode" in df.columns:
        if "sensor_mode" in ordered:
            ordered.remove("sensor_mode")
        pd_idx = ordered.index("packing_density") + 1
        ordered.insert(pd_idx, "sensor_mode")
    # AS7265x columns after spec block
    if AS7265X_COLS[0] in df.columns:
        spec_end = ordered.index(SPEC_COLS[-1]) + 1
        for i, c in enumerate(AS7265X_COLS):
            if c not in ordered:
                ordered.insert(spec_end + i, c)
    df = df[ordered]

    validate_dataframe(df)
    df.to_csv(path, index=False)
    return path


# ---------------------------------------------------------------------------
# Convenience extraction helpers
# ---------------------------------------------------------------------------


def extract_spectra(df: pd.DataFrame) -> np.ndarray:
    """Return the (N, 288) spectrometer block as a contiguous float64 array."""
    return np.ascontiguousarray(
        df[list(SPEC_COLS)].to_numpy(dtype=np.float64, copy=True)
    )


def extract_leds(df: pd.DataFrame) -> np.ndarray:
    """Return the (N, 12) LED narrowband block."""
    return np.ascontiguousarray(
        df[list(LED_COLS)].to_numpy(dtype=np.float64, copy=True)
    )


def extract_lif(df: pd.DataFrame) -> np.ndarray:
    """Return the (N,) LIF photodiode column."""
    return np.ascontiguousarray(df[LIF_COL].to_numpy(dtype=np.float64, copy=True))


def extract_as7265x(df: pd.DataFrame) -> np.ndarray:
    """Return the (N, 18) AS7265x multispectral block.

    Raises ``KeyError`` if the AS7265x columns are not present.
    """
    return np.ascontiguousarray(
        df[list(AS7265X_COLS)].to_numpy(dtype=np.float64, copy=True)
    )


def extract_feature_matrix(df: pd.DataFrame, sensor_mode: str | None = None) -> np.ndarray:
    """Return the raw feature matrix for the given sensor mode.

    When *sensor_mode* is ``None`` the mode is auto-detected from the
    DataFrame columns (backward compatible: defaults to ``"full"`` for
    legacy data).

    =================  ====================================================
    Mode               Shape
    =================  ====================================================
    ``"full"``         ``(N, 301)`` -- ``[spec | led | lif]``
    ``"multispectral"````(N, 31)``  -- ``[as7 | led | lif]``
    ``"combined"``     ``(N, 319)`` -- ``[spec | as7 | led | lif]``
    =================  ====================================================
    """
    if sensor_mode is None:
        sensor_mode = _detect_sensor_mode(df)

    led = extract_leds(df)
    lif = extract_lif(df).reshape(-1, 1)

    if sensor_mode == "full":
        spec = extract_spectra(df)
        return np.concatenate([spec, led, lif], axis=1)
    elif sensor_mode == "multispectral":
        as7 = extract_as7265x(df)
        return np.concatenate([as7, led, lif], axis=1)
    elif sensor_mode == "combined":
        spec = extract_spectra(df)
        as7 = extract_as7265x(df)
        return np.concatenate([spec, as7, led, lif], axis=1)
    else:
        raise ValueError(f"Unknown sensor_mode: {sensor_mode!r}")


def extract_labels(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Return ``(class_indices, ilmenite_fraction)`` arrays."""
    from vera.schema import CLASS_TO_INDEX

    class_idx = df["mineral_class"].map(CLASS_TO_INDEX).to_numpy(dtype=np.int64)
    ilm = df["ilmenite_fraction"].to_numpy(dtype=np.float64)
    return class_idx, ilm


__all__ = [
    "SchemaError",
    "validate_dataframe",
    "read_measurements_csv",
    "write_measurements_csv",
    "extract_spectra",
    "extract_leds",
    "extract_lif",
    "extract_as7265x",
    "extract_feature_matrix",
    "extract_labels",
]
