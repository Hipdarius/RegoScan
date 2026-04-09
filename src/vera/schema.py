"""Canonical measurement schema for VERA.

This module is the **contract** between the (future) hardware acquisition
layer and the entire software stack. Every other module that touches a
measurement reads or writes through this schema.

Locked. Do not change column names without bumping ``SCHEMA_VERSION``.

The 288 spectrometer channels span 340–850 nm on a Hamamatsu C12880MA
(~1.78 nm/px). Because that step is non-integer, columns are named by index
(``spec_000 .. spec_287``) and the actual wavelength grid is exposed as
:data:`WAVELENGTHS`.
"""

from __future__ import annotations

from typing import Final, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_validator

# ---------------------------------------------------------------------------
# Versioning
# ---------------------------------------------------------------------------

SCHEMA_VERSION: Final[str] = "1.1.0"

# ---------------------------------------------------------------------------
# Spectrometer grid (Hamamatsu C12880MA)
# ---------------------------------------------------------------------------

N_SPEC: Final[int] = 288
SPEC_LAMBDA_MIN_NM: Final[float] = 340.0
SPEC_LAMBDA_MAX_NM: Final[float] = 850.0
WAVELENGTHS: Final[np.ndarray] = np.linspace(
    SPEC_LAMBDA_MIN_NM, SPEC_LAMBDA_MAX_NM, N_SPEC, dtype=np.float64
)
SPEC_COLS: Final[tuple[str, ...]] = tuple(f"spec_{i:03d}" for i in range(N_SPEC))

# ---------------------------------------------------------------------------
# LED narrowband channels (one reflectance value per LED)
# ---------------------------------------------------------------------------

LED_WAVELENGTHS_NM: Final[tuple[int, ...]] = (
    385, 405, 450, 500, 525, 590, 625, 660, 730, 780, 850, 940,
)
LED_COLS: Final[tuple[str, ...]] = tuple(f"led_{w}" for w in LED_WAVELENGTHS_NM)
N_LED: Final[int] = len(LED_COLS)

# ---------------------------------------------------------------------------
# LIF channel
# ---------------------------------------------------------------------------

LIF_COL: Final[str] = "lif_450lp"  # 405 nm excitation, 450 nm longpass

# ---------------------------------------------------------------------------
# AS7265x 18-band multispectral sensor
# ---------------------------------------------------------------------------

AS7265X_BANDS: Final[tuple[int, ...]] = (
    410, 435, 460, 485, 510, 535, 560, 585, 610, 645, 680, 705, 730, 760, 810, 860, 900, 940,
)
N_AS7265X: Final[int] = 18
AS7265X_COLS: Final[tuple[str, ...]] = tuple(f"as7_{w}" for w in AS7265X_BANDS)

# ---------------------------------------------------------------------------
# Sensor mode determines which channels are active
# ---------------------------------------------------------------------------

SensorMode = Literal["full", "multispectral", "combined"]
SENSOR_MODES: Final[tuple[str, ...]] = ("full", "multispectral", "combined")

# Feature counts per sensor mode
_FEATURE_COUNTS: Final[dict[str, int]] = {
    "full": N_SPEC + N_LED + 1,              # 288 + 12 + 1 = 301
    "multispectral": N_AS7265X + N_LED + 1,  # 18 + 12 + 1 = 31
    "combined": N_SPEC + N_AS7265X + N_LED + 1,  # 288 + 18 + 12 + 1 = 319
}


def get_feature_count(sensor_mode: str = "full") -> int:
    """Return the number of ML input features for a given sensor configuration."""
    if sensor_mode not in _FEATURE_COUNTS:
        raise ValueError(f"Unknown sensor_mode: {sensor_mode!r}; expected one of {SENSOR_MODES}")
    return _FEATURE_COUNTS[sensor_mode]

# ---------------------------------------------------------------------------
# Metadata columns
# ---------------------------------------------------------------------------

META_COLS: Final[tuple[str, ...]] = (
    "sample_id",
    "measurement_id",
    "timestamp",
    "mineral_class",
    "ilmenite_fraction",
    "integration_time_ms",
    "ambient_temp_c",
    "packing_density",
)

# ---------------------------------------------------------------------------
# Mineral class label space
# ---------------------------------------------------------------------------

MINERAL_CLASSES: Final[tuple[str, ...]] = (
    "ilmenite_rich",
    "olivine_rich",
    "pyroxene_rich",
    "anorthositic",
    "mixed",
)
N_CLASSES: Final[int] = len(MINERAL_CLASSES)
CLASS_TO_INDEX: Final[dict[str, int]] = {c: i for i, c in enumerate(MINERAL_CLASSES)}
INDEX_TO_CLASS: Final[dict[int, str]] = {i: c for c, i in CLASS_TO_INDEX.items()}

PACKING_DENSITIES: Final[tuple[str, ...]] = ("loose", "medium", "packed")

# ---------------------------------------------------------------------------
# Full ordered column list
# ---------------------------------------------------------------------------

ALL_COLUMNS: Final[tuple[str, ...]] = (
    *META_COLS,
    *SPEC_COLS,
    *LED_COLS,
    LIF_COL,
)

N_FEATURES_TOTAL: Final[int] = N_SPEC + N_LED + 1  # 288 + 12 + 1 = 301


def columns_for_mode(sensor_mode: str = "full") -> tuple[str, ...]:
    """Return the ordered column tuple for a given sensor mode.

    This determines which columns appear in a CSV for a given sensor
    configuration. ``ALL_COLUMNS`` remains the v1.0 "full" set for
    backward compatibility.
    """
    if sensor_mode == "full":
        return (*META_COLS, "sensor_mode", *SPEC_COLS, *LED_COLS, LIF_COL)
    elif sensor_mode == "multispectral":
        return (*META_COLS, "sensor_mode", *AS7265X_COLS, *LED_COLS, LIF_COL)
    elif sensor_mode == "combined":
        return (*META_COLS, "sensor_mode", *SPEC_COLS, *AS7265X_COLS, *LED_COLS, LIF_COL)
    raise ValueError(f"Unknown sensor_mode: {sensor_mode!r}")


# ---------------------------------------------------------------------------
# Pydantic model for a single measurement row
# ---------------------------------------------------------------------------


PackingDensity = Literal["loose", "medium", "packed"]
MineralClass = Literal[
    "ilmenite_rich", "olivine_rich", "pyroxene_rich", "anorthositic", "mixed"
]


class Measurement(BaseModel):
    """One row of the canonical CSV.

    Validates types, ranges, and array lengths. Use this at the boundary --
    e.g., when ingesting a new acquisition or sanity-checking a synthetic
    dataset -- not on every row of a hot inner loop.
    """

    model_config = ConfigDict(extra="forbid", frozen=False)

    sample_id: str = Field(min_length=1)
    measurement_id: str = Field(min_length=1)
    timestamp: str = Field(min_length=1)
    mineral_class: MineralClass
    ilmenite_fraction: float = Field(ge=0.0, le=1.0)
    integration_time_ms: int = Field(gt=0)
    ambient_temp_c: float
    packing_density: PackingDensity

    # Sensor mode (default "full" for backward compat with v1.0 data)
    sensor_mode: SensorMode = "full"

    spec: list[float] = Field(min_length=N_SPEC, max_length=N_SPEC)
    led: list[float] = Field(min_length=N_LED, max_length=N_LED)
    lif_450lp: float

    # AS7265x 18-band multispectral (optional; present when mode != "full")
    as7265x: list[float] | None = Field(default=None)

    @field_validator("spec", "led")
    @classmethod
    def _all_finite(cls, v: list[float]) -> list[float]:
        arr = np.asarray(v, dtype=np.float64)
        if not np.all(np.isfinite(arr)):
            raise ValueError("spectrum / LED values must all be finite")
        return v

    @field_validator("lif_450lp")
    @classmethod
    def _lif_finite(cls, v: float) -> float:
        if not np.isfinite(v):
            raise ValueError("lif_450lp must be finite")
        return v

    @field_validator("as7265x")
    @classmethod
    def _as7265x_valid(cls, v: list[float] | None) -> list[float] | None:
        if v is None:
            return v
        if len(v) != N_AS7265X:
            raise ValueError(
                f"as7265x must have exactly {N_AS7265X} values; got {len(v)}"
            )
        arr = np.asarray(v, dtype=np.float64)
        if not np.all(np.isfinite(arr)):
            raise ValueError("as7265x values must all be finite")
        return v

    def to_row(self) -> dict[str, object]:
        """Flatten this measurement to a dict.

        Always emits the core columns from :data:`ALL_COLUMNS`. When
        ``as7265x`` data is present the AS7265x columns and the
        ``sensor_mode`` column are also included.
        """
        row: dict[str, object] = {
            "sample_id": self.sample_id,
            "measurement_id": self.measurement_id,
            "timestamp": self.timestamp,
            "mineral_class": self.mineral_class,
            "ilmenite_fraction": float(self.ilmenite_fraction),
            "integration_time_ms": int(self.integration_time_ms),
            "ambient_temp_c": float(self.ambient_temp_c),
            "packing_density": self.packing_density,
            "sensor_mode": self.sensor_mode,
        }
        for col, val in zip(SPEC_COLS, self.spec):
            row[col] = float(val)
        if self.as7265x is not None:
            for col, val in zip(AS7265X_COLS, self.as7265x):
                row[col] = float(val)
        for col, val in zip(LED_COLS, self.led):
            row[col] = float(val)
        row[LIF_COL] = float(self.lif_450lp)
        return row

    @classmethod
    def from_row(cls, row: dict[str, object]) -> "Measurement":
        """Inverse of :meth:`to_row` -- build a model from a dict-shaped row."""
        spec = [float(row[c]) for c in SPEC_COLS]
        led = [float(row[c]) for c in LED_COLS]

        # AS7265x columns are optional (backward compat with v1.0 CSVs)
        as7265x: list[float] | None = None
        if AS7265X_COLS[0] in row:
            as7265x = [float(row[c]) for c in AS7265X_COLS]

        sensor_mode_val = str(row.get("sensor_mode", "full"))

        return cls(
            sample_id=str(row["sample_id"]),
            measurement_id=str(row["measurement_id"]),
            timestamp=str(row["timestamp"]),
            mineral_class=str(row["mineral_class"]),  # type: ignore[arg-type]
            ilmenite_fraction=float(row["ilmenite_fraction"]),
            integration_time_ms=int(row["integration_time_ms"]),
            ambient_temp_c=float(row["ambient_temp_c"]),
            packing_density=str(row["packing_density"]),  # type: ignore[arg-type]
            sensor_mode=sensor_mode_val,  # type: ignore[arg-type]
            spec=spec,
            led=led,
            lif_450lp=float(row[LIF_COL]),
            as7265x=as7265x,
        )


__all__ = [
    "SCHEMA_VERSION",
    "N_SPEC",
    "SPEC_LAMBDA_MIN_NM",
    "SPEC_LAMBDA_MAX_NM",
    "WAVELENGTHS",
    "SPEC_COLS",
    "LED_WAVELENGTHS_NM",
    "LED_COLS",
    "N_LED",
    "LIF_COL",
    "AS7265X_BANDS",
    "N_AS7265X",
    "AS7265X_COLS",
    "SensorMode",
    "SENSOR_MODES",
    "get_feature_count",
    "columns_for_mode",
    "META_COLS",
    "MINERAL_CLASSES",
    "N_CLASSES",
    "CLASS_TO_INDEX",
    "INDEX_TO_CLASS",
    "PACKING_DENSITIES",
    "ALL_COLUMNS",
    "N_FEATURES_TOTAL",
    "Measurement",
    "MineralClass",
    "PackingDensity",
]
