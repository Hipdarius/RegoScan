#!/usr/bin/env python3
"""VERA ingestion bridge — serial listener → validate → infer → CSV.

Reads newline-delimited JSON sensor frames from stdin (piped from
``mock_esp32.py`` or a real UART-to-pipe adapter), validates them
against the wire protocol, runs the ONNX inference engine to classify
the mineral content, and appends each measurement to the canonical
CSV at ``data/real_v1.csv``.

Architecture
------------
::

    ESP32 / mock  ─── JSON lines ───>  bridge.py
                                         │
                                    validate_frame()
                                         │
                                    build_feature_vector()
                                         │
                                    InferenceEngine.predict()
                                         │
                                    append_to_csv()
                                         │
                                    data/real_v1.csv

The bridge is the **single entry point** for real or simulated hardware
data into the VERA ML pipeline. It enforces the schema contract and
ensures that every row in ``real_v1.csv`` has been through Pydantic
validation and ONNX inference.

Usage
-----
::

    # Pipe from mock (default: data/real_v1.csv)
    python scripts/mock_esp32.py --count 10 --interval 0 | \\
        python scripts/bridge.py --sample-id BENCH_01

    # With explicit model and output paths
    python scripts/mock_esp32.py | \\
        python scripts/bridge.py \\
            --sample-id FIELD_RUN_03 \\
            --model-dir runs/cnn_v2 \\
            --out data/field_run_03.csv

    # Dry-run mode (validate frames, skip inference)
    python scripts/mock_esp32.py --count 5 --interval 0 | \\
        python scripts/bridge.py --sample-id DRY --dry-run
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from pydantic import BaseModel, Field, ValidationError

# ---------------------------------------------------------------------------
# Path bootstrap
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from vera.schema import (
    ALL_COLUMNS,
    INDEX_TO_CLASS,
    LED_COLS,
    LIF_COL,
    MINERAL_CLASSES,
    Measurement,
    N_AS7265X,
    N_FEATURES_TOTAL,
    N_LED,
    N_SPEC,
    N_SWIR,
    PACKING_DENSITIES,
    SPEC_COLS,
    SWIR_COLS,
    get_feature_count,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WIRE_PROTOCOL_VERSION = 1
DEFAULT_CSV_PATH = ROOT / "data" / "real_v1.csv"
DEFAULT_MODEL_CANDIDATES = [
    ROOT / "runs" / "cnn_v2",
    ROOT / "runs" / "cnn_run",
]

logger = logging.getLogger("bridge")


# ---------------------------------------------------------------------------
# Wire-protocol validation model
# ---------------------------------------------------------------------------
# This is intentionally a SUBSET of schema.Measurement — the ESP32
# cannot know the mineral class (that is what the model predicts) or
# the sample ID (that is operator metadata).


class SensorFrame(BaseModel):
    """Wire protocol from ESP32 → Bridge.

    Contains only fields the hardware can physically measure. Everything
    else (sample_id, mineral_class, ilmenite_fraction) is filled in by
    the bridge after inference.

    Optional fields:
    - ``as7``: AS7265x 18-band triad sensor (may be absent on dev boards
      without the I²C breakout populated)
    - ``swir``: Hamamatsu G12180-010A InGaAs photodiode at 940/1050 nm,
      read through the ADS1115 16-bit ADC (absent until the SWIR daughter
      board is installed). Frames without these fields remain fully
      backward-compatible with v1.0/v1.1 firmware.
    """

    v: int = Field(ge=1, le=1, description="Wire protocol version")
    integration_time_ms: int = Field(gt=0)
    ambient_temp_c: float
    spec: list[float] = Field(min_length=N_SPEC, max_length=N_SPEC)
    led: list[float] = Field(min_length=N_LED, max_length=N_LED)
    lif_450lp: float
    as7: list[float] | None = None
    swir: list[float] | None = Field(
        default=None,
        min_length=N_SWIR,
        max_length=N_SWIR,
        description="SWIR reflectance at 940 nm and 1050 nm",
    )


class GroundTruth(BaseModel):
    """Optional ground-truth labels attached by the mock simulator."""

    mineral_class: str
    ilmenite_fraction: float = Field(ge=0.0, le=1.0)


# ---------------------------------------------------------------------------
# Frame processing
# ---------------------------------------------------------------------------


def validate_frame(raw_json: str) -> tuple[SensorFrame, GroundTruth | None]:
    """Parse and validate a single JSON line from the serial stream.

    Parameters
    ----------
    raw_json
        One line of text from stdin.

    Returns
    -------
    tuple
        ``(frame, truth)`` where ``truth`` is None if the ``_truth``
        key was absent (real hardware mode).

    Raises
    ------
    json.JSONDecodeError
        Malformed JSON.
    pydantic.ValidationError
        Valid JSON but fields don't match the wire protocol.
    """
    payload = json.loads(raw_json)

    truth_data = payload.pop("_truth", None)
    truth = GroundTruth(**truth_data) if truth_data else None

    frame = SensorFrame(**payload)
    return frame, truth


def build_feature_vector(frame: SensorFrame) -> np.ndarray:
    """Concatenate sensor channels into a feature vector.

    The order is canonical: ``[spec | as7265x? | swir? | led | lif]``.
    Returned shape depends on which optional channels are present:

    ===========================  ===========  ============================
    Channels present              Shape         Sensor mode
    ===========================  ===========  ============================
    spec + led + lif              ``(301,)``   ``"full"`` (legacy)
    spec + swir + led + lif       ``(303,)``   ``"full"`` (v1.2+)
    spec + as7 + led + lif        ``(319,)``   ``"combined"`` (legacy)
    spec + as7 + swir + led + lif ``(321,)``   ``"combined"`` (v1.2+)
    ===========================  ===========  ============================

    Column order matches the sensor_mode conventions in :mod:`vera.schema`.
    """
    parts: list[np.ndarray] = [
        np.asarray(frame.spec, dtype=np.float32),
    ]
    if frame.as7 is not None:
        parts.append(np.asarray(frame.as7, dtype=np.float32))
    if frame.swir is not None:
        parts.append(np.asarray(frame.swir, dtype=np.float32))
    parts.extend([
        np.asarray(frame.led, dtype=np.float32),
        np.asarray([frame.lif_450lp], dtype=np.float32),
    ])
    return np.concatenate(parts)


def frame_to_measurement(
    frame: SensorFrame,
    *,
    sample_id: str,
    packing_density: str,
    predicted_class: str,
    predicted_ilmenite: float,
) -> Measurement:
    """Merge sensor data with bridge-provided metadata into a full Measurement.

    This is the canonical path from raw hardware readings to a validated
    schema row.  The mineral_class and ilmenite_fraction fields are
    filled from the ONNX model prediction, NOT from ground truth.
    """
    sensor_mode = "combined" if frame.as7 is not None else "full"
    return Measurement(
        sample_id=sample_id,
        measurement_id=str(uuid.uuid4()),
        timestamp=datetime.now(timezone.utc).isoformat(),
        mineral_class=predicted_class,  # type: ignore[arg-type]
        ilmenite_fraction=predicted_ilmenite,
        integration_time_ms=frame.integration_time_ms,
        ambient_temp_c=frame.ambient_temp_c,
        packing_density=packing_density,  # type: ignore[arg-type]
        sensor_mode=sensor_mode,  # type: ignore[arg-type]
        spec=frame.spec,
        led=frame.led,
        lif_450lp=frame.lif_450lp,
        swir=frame.swir,
        as7265x=frame.as7,
    )


# ---------------------------------------------------------------------------
# CSV append (crash-safe line-by-line writes)
# ---------------------------------------------------------------------------


def _ensure_csv_header(path: Path) -> None:
    """Write the CSV header if the file doesn't exist or is empty."""
    if path.exists() and path.stat().st_size > 0:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(list(ALL_COLUMNS))
    logger.info("Created CSV with header: %s", path)


def append_measurement(measurement: Measurement, path: Path) -> None:
    """Append a single measurement row to the CSV.

    Writing one row at a time (rather than buffering) ensures that
    data survives a crash — critical for field deployments where the
    probe may lose power mid-run.
    """
    row = measurement.to_row()
    values = [row[col] for col in ALL_COLUMNS]
    with open(path, "a", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(values)


# ---------------------------------------------------------------------------
# Inference wrapper
# ---------------------------------------------------------------------------


def load_engine(model_dir: Path | None) -> Any | None:
    """Attempt to load the ONNX inference engine.

    Returns None if no model is found (dry-run mode will proceed
    without it).
    """
    from vera.inference import InferenceEngine

    candidates = [model_dir] if model_dir else DEFAULT_MODEL_CANDIDATES
    for candidate in candidates:
        if candidate is None:
            continue
        onnx_path = candidate / "model.onnx"
        if onnx_path.exists():
            engine = InferenceEngine(onnx_path)
            logger.info(
                "Loaded ONNX model: %s (sha256: %s)",
                onnx_path, engine.sha256_short,
            )
            return engine

    logger.warning(
        "No ONNX model found. Searched: %s",
        [str(c) for c in candidates if c],
    )
    return None


def run_inference(engine: Any, features: np.ndarray) -> tuple[str, float, float]:
    """Run the ONNX model and return (class_name, ilmenite_fraction, confidence).

    Parameters
    ----------
    engine
        An :class:`~vera.inference.InferenceEngine` instance.
    features
        Shape ``(301,)`` feature vector.

    Returns
    -------
    tuple
        ``(predicted_class, ilmenite_fraction, confidence)``
    """
    result = engine.predict(features)
    class_name = INDEX_TO_CLASS[result["class_index"]]
    confidence = float(result["probabilities"][result["class_index"]])
    return class_name, result["ilmenite_fraction"], confidence


# ---------------------------------------------------------------------------
# Main ingestion loop
# ---------------------------------------------------------------------------


class BridgeStats:
    """Accumulates runtime statistics for the ingestion session."""

    def __init__(self) -> None:
        self.frames_received: int = 0
        self.frames_valid: int = 0
        self.frames_malformed: int = 0
        self.truth_matches: int = 0
        self.truth_total: int = 0

    @property
    def accuracy(self) -> float | None:
        if self.truth_total == 0:
            return None
        return self.truth_matches / self.truth_total

    def summary(self) -> str:
        parts = [
            f"received={self.frames_received}",
            f"valid={self.frames_valid}",
            f"malformed={self.frames_malformed}",
        ]
        if self.truth_total > 0:
            parts.append(
                f"accuracy={self.truth_matches}/{self.truth_total} "
                f"({self.accuracy:.1%})"
            )
        return "  ".join(parts)


def run_bridge(
    *,
    sample_id: str,
    packing_density: str,
    csv_path: Path,
    model_dir: Path | None,
    dry_run: bool,
) -> BridgeStats:
    """Read sensor frames from stdin, validate, infer, and log to CSV.

    Parameters
    ----------
    sample_id
        Human-assigned sample identifier (e.g. ``FIELD_RUN_03``).
    packing_density
        Regolith packing state — one of ``loose``, ``medium``, ``packed``.
    csv_path
        Output CSV path. Created with header if absent.
    model_dir
        Directory containing ``model.onnx``. If None, searches defaults.
    dry_run
        If True, validate frames but skip inference and CSV writes.
    """
    stats = BridgeStats()

    engine = None
    if not dry_run:
        engine = load_engine(model_dir)
        if engine is None:
            logger.error(
                "No ONNX model available and --dry-run not set. "
                "Train a model first:\n"
                "  uv run vera-train --model cnn --data <csv> --out runs/cnn_v2\n"
                "  uv run vera-quantize --run runs/cnn_v2 --out runs/cnn_v2/model_int8.tflite\n"
                "Or use --dry-run to validate frames without inference."
            )
            return stats
        _ensure_csv_header(csv_path)

    logger.info(
        "Bridge ready — sample_id=%s, packing=%s, dry_run=%s, csv=%s",
        sample_id, packing_density, dry_run, csv_path,
    )

    try:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue

            stats.frames_received += 1

            # --- Parse & validate ---
            try:
                frame, truth = validate_frame(line)
            except json.JSONDecodeError as exc:
                stats.frames_malformed += 1
                logger.error(
                    "Malformed JSON (frame %d): %s | raw: %.80s...",
                    stats.frames_received, exc, line,
                )
                continue
            except ValidationError as exc:
                stats.frames_malformed += 1
                logger.error(
                    "Schema violation (frame %d): %s",
                    stats.frames_received, exc.error_count(),
                )
                logger.debug("Validation detail: %s", exc)
                continue

            stats.frames_valid += 1

            if dry_run:
                logger.info(
                    "frame %d  VALID  int=%d ms  temp=%.1f°C",
                    stats.frames_valid,
                    frame.integration_time_ms,
                    frame.ambient_temp_c,
                )
                continue

            # --- Inference ---
            features = build_feature_vector(frame)
            pred_class, pred_ilm, confidence = run_inference(engine, features)

            # --- Accuracy tracking (when mock provides ground truth) ---
            truth_tag = ""
            if truth is not None:
                stats.truth_total += 1
                match = pred_class == truth.mineral_class
                if match:
                    stats.truth_matches += 1
                truth_tag = (
                    f"  truth={truth.mineral_class} "
                    f"{'✓' if match else '✗'}"
                )

            logger.info(
                "frame %d  pred=%-16s  ilm=%.3f  conf=%.1f%%%s",
                stats.frames_valid,
                pred_class,
                pred_ilm,
                confidence * 100,
                truth_tag,
            )

            # --- Persist ---
            measurement = frame_to_measurement(
                frame,
                sample_id=sample_id,
                packing_density=packing_density,
                predicted_class=pred_class,
                predicted_ilmenite=pred_ilm,
            )
            append_measurement(measurement, csv_path)

    except KeyboardInterrupt:
        logger.info("Interrupted by user")

    return stats


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="VERA ingestion bridge: serial → validate → infer → CSV",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python scripts/mock_esp32.py --count 10 --interval 0 | \\\n"
            "      python scripts/bridge.py --sample-id BENCH_01\n\n"
            "  python scripts/mock_esp32.py | \\\n"
            "      python scripts/bridge.py --sample-id FIELD_03 "
            "--model-dir runs/cnn_v2\n"
        ),
    )
    parser.add_argument(
        "--sample-id",
        required=True,
        help="human-assigned sample identifier (e.g. FIELD_RUN_03)",
    )
    parser.add_argument(
        "--packing-density",
        choices=list(PACKING_DENSITIES),
        default="medium",
        help="regolith packing state (default: medium)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_CSV_PATH,
        help=f"output CSV path (default: {DEFAULT_CSV_PATH})",
    )
    parser.add_argument(
        "--model-dir",
        type=Path,
        default=None,
        help="directory containing model.onnx (default: auto-detect in runs/)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="validate frames only — skip inference and CSV writes",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="enable DEBUG logging",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        stream=sys.stderr,
    )

    stats = run_bridge(
        sample_id=args.sample_id,
        packing_density=args.packing_density,
        csv_path=args.out,
        model_dir=args.model_dir,
        dry_run=args.dry_run,
    )

    logger.info("Session complete — %s", stats.summary())

    if stats.frames_malformed > 0:
        logger.warning(
            "%d/%d frames were malformed",
            stats.frames_malformed, stats.frames_received,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
