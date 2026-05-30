"""Generate a synthetic VERA dataset CSV.

Wraps :func:`vera.synth.synth_dataset` with a thin CLI.

Example
-------
    python scripts/generate_synth_dataset.py \
        --n-samples 50 \
        --measurements-per-sample 8 \
        --out data/synth_v1.csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from vera.io_csv import write_measurements_csv
from vera.synth import load_endmembers, synth_dataset

DEFAULT_ENDMEMBERS = ROOT / "data" / "cache" / "usgs_endmembers.npz"
DEFAULT_OUT = ROOT / "data" / "synth_v1.csv"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-samples", type=int, default=50)
    parser.add_argument("--measurements-per-sample", type=int, default=8)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--endmembers",
        type=Path,
        default=DEFAULT_ENDMEMBERS,
        help=f"path to the endmember cache (default: {DEFAULT_ENDMEMBERS})",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help=f"output CSV path (default: {DEFAULT_OUT})",
    )
    args = parser.parse_args(argv)

    if not args.endmembers.exists():
        print(
            f"[err] endmember cache not found at {args.endmembers}\n"
            f"      run `python scripts/download_usgs.py` first",
            file=sys.stderr,
        )
        return 2

    endmembers = load_endmembers(args.endmembers)
    print(f"[ok] loaded endmembers (source={endmembers.source})")

    measurements = synth_dataset(
        endmembers,
        n_samples=args.n_samples,
        measurements_per_sample=args.measurements_per_sample,
        seed=args.seed,
    )
    print(f"[ok] generated {len(measurements)} measurements "
          f"({args.n_samples} samples × {args.measurements_per_sample} reps)")

    out = write_measurements_csv(measurements, args.out)
    print(f"[ok] wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
