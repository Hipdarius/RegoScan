#!/usr/bin/env python3
"""Simulate ESP32-S3 sensor output for the VERA ingestion pipeline.

This script acts as a **software stand-in** for the real hardware:
an ESP32-S3 driving a Hamamatsu C12880MA spectrometer, 12 narrowband
LEDs, and a 405 nm laser diode for fluorescence measurements.

It uses the synthetic physics engine (:mod:`vera.synth`) to produce
realistic 301-feature sensor readings, then emits them as newline-
delimited JSON on stdout — the same framing the real firmware will use
over UART at 115200 baud.

Wire Protocol
-------------
Each line is a self-contained JSON object (no multi-line payloads) with
exactly these fields::

    {
      "v":                  1,          # protocol version
      "integration_time_ms": 200,       # sensor integration window
      "ambient_temp_c":      22.3,      # on-board thermistor reading
      "spec":               [...288],   # C12880MA pixel values
      "led":                [...12],    # narrowband reflectances
      "lif_450lp":           0.42       # 450 nm longpass fluorescence
    }

An optional ``_truth`` key carries ground-truth labels so the bridge
can track prediction accuracy during validation runs::

      "_truth": {
        "mineral_class":     "ilmenite_rich",
        "ilmenite_fraction": 0.48
      }

Usage
-----
::

    # Default: 2-second cadence, ground truth included, round-robin classes
    python scripts/mock_esp32.py

    # Fast burst of 10 frames, then exit
    python scripts/mock_esp32.py --count 10 --interval 0.0

    # Fixed mineral class, no ground truth (mimics real hardware)
    python scripts/mock_esp32.py --mineral-class ilmenite_rich --no-truth

    # Pipe directly into the bridge
    python scripts/mock_esp32.py | python scripts/bridge.py --sample-id FIELD_01
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# Path bootstrap — allow running from repo root without ``uv run``
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from vera.inference import resolve_endmembers
from vera.schema import AS7265X_BANDS, MINERAL_CLASSES, WAVELENGTHS
from vera.synth import (
    NoiseConfig,
    fractions_for_class,
    load_endmembers,
    synth_measurement,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WIRE_PROTOCOL_VERSION = 1
DEFAULT_INTERVAL_S = 2.0
DEFAULT_COUNT = 0  # 0 = infinite

logger = logging.getLogger("mock_esp32")


# ---------------------------------------------------------------------------
# Frame generation
# ---------------------------------------------------------------------------


def _synth_as7265x(
    spec: list[float],
    rng: np.random.Generator,
) -> list[float]:
    """Synthesize fake AS7265x 18-band readings from a C12880MA spectrum.

    Samples the continuous spectrum at the 18 AS7265x band wavelengths
    using nearest-neighbor interpolation and adds a small amount of
    Gaussian noise to simulate the discrete sensor's lower resolution.
    """
    spec_arr = np.asarray(spec, dtype=np.float64)
    wl_arr = np.asarray(WAVELENGTHS, dtype=np.float64)
    as7_values = []
    for band_nm in AS7265X_BANDS:
        # Find nearest C12880MA pixel to this AS7265x band wavelength
        idx = int(np.argmin(np.abs(wl_arr - band_nm)))
        # Average a small window around the nearest pixel (+/- 2 pixels)
        lo = max(0, idx - 2)
        hi = min(len(spec_arr), idx + 3)
        val = float(np.mean(spec_arr[lo:hi]))
        # Add sensor noise (AS7265x is noisier than C12880MA)
        val += float(rng.normal(0.0, 0.005))
        val = max(0.0, val)
        as7_values.append(round(val, 6))
    return as7_values


def build_sensor_frame(
    mineral_class: str,
    rng: np.random.Generator,
    endmembers: object,
    *,
    emit_truth: bool = True,
    noise: NoiseConfig | None = None,
    sensor_mode: str = "combined",
) -> dict:
    """Synthesise one sensor reading and format it as a wire-protocol dict.

    Parameters
    ----------
    mineral_class
        Target mineral class — drives composition sampling in synth.
    rng
        NumPy random generator for reproducibility.
    endmembers
        Loaded endmember spectra from :func:`load_endmembers`.
    emit_truth
        If True, attach ``_truth`` with the known mineral class and
        ilmenite fraction. Set False to mimic real hardware output.
    noise
        Optional noise configuration override.
    sensor_mode
        Which sensor channels to include: "full" (spec only),
        "combined" (spec + as7265x), or "multispectral" (as7265x only,
        but spec is still emitted for reference).
    """
    fracs = fractions_for_class(mineral_class, rng)
    measurement = synth_measurement(
        sample_id="mock",
        mineral_class=mineral_class,
        fractions=fracs,
        endmembers=endmembers,
        rng=rng,
        noise=noise,
    )

    frame: dict = {
        "v": WIRE_PROTOCOL_VERSION,
        "integration_time_ms": measurement.integration_time_ms,
        "ambient_temp_c": round(measurement.ambient_temp_c, 2),
        "spec": [round(float(x), 6) for x in measurement.spec],
        "led": [round(float(x), 6) for x in measurement.led],
        "lif_450lp": round(measurement.lif_450lp, 6),
    }

    # Include AS7265x data when sensor_mode requests it
    if sensor_mode in ("combined", "multispectral"):
        frame["as7"] = _synth_as7265x(measurement.spec, rng)

    # Include SWIR (940/1050 nm) when the synth_measurement produced it.
    # synth.py always emits SWIR for v1.2+ endmember caches. The bridge
    # treats this field as optional so older firmware/mock without SWIR
    # remains valid.
    if measurement.swir is not None:
        frame["swir"] = [round(float(x), 6) for x in measurement.swir]

    if emit_truth:
        frame["_truth"] = {
            "mineral_class": measurement.mineral_class,
            "ilmenite_fraction": round(measurement.ilmenite_fraction, 6),
        }

    return frame


def emit_frames(
    *,
    interval_s: float,
    count: int,
    mineral_class: str | None,
    seed: int,
    emit_truth: bool,
    sensor_mode: str = "combined",
) -> None:
    """Main generation loop — writes newline-delimited JSON to stdout.

    Parameters
    ----------
    interval_s
        Seconds between frames. Set to 0 for a burst with no delay.
    count
        Number of frames to emit. 0 means infinite (Ctrl-C to stop).
    mineral_class
        If set, every frame uses this class. Otherwise, classes cycle
        round-robin through the 5 canonical mineral classes — useful
        for validating that the bridge handles all categories.
    seed
        RNG seed for reproducibility across test runs.
    emit_truth
        Forward to :func:`build_sensor_frame`.
    sensor_mode
        Which sensor channels to simulate: "full", "combined", or
        "multispectral". Forwarded to :func:`build_sensor_frame`.
    """
    rng = np.random.default_rng(seed)

    em_path = resolve_endmembers()
    em = load_endmembers(em_path)
    logger.info("Endmembers loaded from %s (source: %s)", em_path, em.source)

    classes = list(MINERAL_CLASSES)
    frame_idx = 0

    try:
        while count == 0 or frame_idx < count:
            klass = mineral_class or classes[frame_idx % len(classes)]
            frame = build_sensor_frame(
                klass, rng, em, emit_truth=emit_truth,
                sensor_mode=sensor_mode,
            )

            line = json.dumps(frame, separators=(",", ":"))
            sys.stdout.write(line + "\n")
            sys.stdout.flush()

            frame_idx += 1
            logger.debug(
                "frame %d  class=%-16s  int=%d ms  temp=%.1f°C",
                frame_idx,
                klass,
                frame["integration_time_ms"],
                frame["ambient_temp_c"],
            )

            if interval_s > 0 and (count == 0 or frame_idx < count):
                time.sleep(interval_s)

    except (KeyboardInterrupt, BrokenPipeError):
        logger.info("Stopped after %d frames", frame_idx)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Simulate ESP32-S3 sensor output for VERA",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python scripts/mock_esp32.py\n"
            "  python scripts/mock_esp32.py --count 5 --interval 0\n"
            "  python scripts/mock_esp32.py | python scripts/bridge.py --sample-id TEST\n"
        ),
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=DEFAULT_INTERVAL_S,
        help=f"seconds between frames (default: {DEFAULT_INTERVAL_S})",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=DEFAULT_COUNT,
        help="number of frames to emit; 0 = infinite (default: 0)",
    )
    parser.add_argument(
        "--mineral-class",
        choices=list(MINERAL_CLASSES),
        default=None,
        help="fix all frames to one mineral class (default: round-robin)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="RNG seed for reproducibility (default: 42)",
    )
    parser.add_argument(
        "--no-truth",
        action="store_true",
        help="omit _truth labels (simulate real hardware)",
    )
    parser.add_argument(
        "--sensor-mode",
        choices=["full", "combined", "multispectral"],
        default="combined",
        help=(
            "which sensor channels to simulate: "
            '"full" = C12880MA only, '
            '"combined" = C12880MA + AS7265x (default), '
            '"multispectral" = AS7265x only'
        ),
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="enable DEBUG logging to stderr",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        stream=sys.stderr,
    )

    logger.info(
        "Starting mock ESP32 — interval=%.1fs, count=%s, class=%s, seed=%d, sensor_mode=%s",
        args.interval,
        args.count or "inf",
        args.mineral_class or "round-robin",
        args.seed,
        args.sensor_mode,
    )

    emit_frames(
        interval_s=args.interval,
        count=args.count,
        mineral_class=args.mineral_class,
        seed=args.seed,
        emit_truth=not args.no_truth,
        sensor_mode=args.sensor_mode,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
