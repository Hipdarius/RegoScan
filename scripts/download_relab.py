"""Fetch / build the RELAB lunar validation endmember set.

RELAB (Reflectance Experiment Laboratory, Brown University) hosts real
lunar soil and Apollo sample reflectance spectra. The canonical interface
is at http://www.planetary.brown.edu/relabdata/ and files are shipped as
ASCII tables under stable-ish but authenticated download pages.

Goal
----
Produce a **validation-only** bundle at
``data/cache/relab_lunar.npz`` with real lunar spectra resampled to the
C12880MA grid (340–850 nm, 288 points). This bundle is NOT used for
training — it exists so ``vera.evaluate`` can run an out-of-training
sanity check on data the model has never seen and that was NOT generated
by our own synth pipeline.

Strategy
--------
1. Try to fetch a small, explicitly listed set of RELAB sample IDs over
   HTTPS with a short timeout. If any fetch fails the whole batch is
   abandoned — we never want a partially populated "real lunar" cache.
2. On failure, fall back to a **labelled parametric set** built from
   lunar-literature-informed shape modifiers on top of the USGS endmembers
   we already have. The bundle is tagged ``source="parametric_lunar"``
   so downstream code can clearly distinguish "real RELAB" from "lunar-
   flavoured synthetic" in reports.

If you have a local RELAB dump (e.g., a .csv exported from the RELAB
browser), point ``--local-dir`` at it and the fetch step is skipped
entirely. That is the path the next hardware-aware session should use.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import requests

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from vera.schema import N_SPEC, WAVELENGTHS

DEFAULT_OUT = ROOT / "data" / "cache" / "relab_lunar.npz"
DEFAULT_USGS = ROOT / "data" / "cache" / "usgs_endmembers.npz"

# Intentionally not hard-coding URLs that may rot. If you have a stable
# mirror, add entries here — each must resolve to a two-column ASCII table
# (wavelength_nm, reflectance) or a .npz the script can parse.
RELAB_CANDIDATE_URLS: dict[str, str] = {
    # "lunar_highland_soil":   "https://example.internal/relab/highland_62231.txt",
    # "lunar_mare_soil":       "https://example.internal/relab/mare_10084.txt",
    # "lunar_pyroxene_grain":  "https://example.internal/relab/pyx_72415.txt",
    # "lunar_olivine_grain":   "https://example.internal/relab/ol_70035.txt",
}


# ---------------------------------------------------------------------------
# Parametric fallback informed by lunar-specific effects
# ---------------------------------------------------------------------------
#
# Apollo regolith samples differ from laboratory mineral spectra in a few
# systematic ways (Pieters 1983, Hapke 1986):
#   - a reddening ("space-weathering") continuum slope
#   - an overall darkening from sub-micron metallic Fe coatings
#   - shallower Fe2+ absorption bands
#
# We apply those modifiers to the USGS parametric endmembers. This is
# still *synthetic*, but it is clearly tagged so no one mistakes it for
# real RELAB data.


def _apply_space_weathering(
    spectrum: np.ndarray,
    lam: np.ndarray,
    *,
    reddening: float = 0.25,
    darkening: float = 0.25,
    band_shallowing: float = 0.5,
) -> np.ndarray:
    """Apply reddening + darkening + band-shallowing to a lab spectrum."""
    x = (lam - lam.min()) / (lam.max() - lam.min())
    red_curve = 1.0 + reddening * x
    dark = 1.0 - darkening
    out = spectrum * red_curve * dark
    # Shallow bands: pull values toward the smooth running mean.
    k = 15
    cumsum = np.concatenate([[0.0], np.cumsum(out)])
    smooth = (cumsum[k:] - cumsum[:-k]) / k
    pad = (spectrum.size - smooth.size) // 2
    smooth_full = np.concatenate(
        [np.full(pad, smooth[0]), smooth, np.full(spectrum.size - smooth.size - pad, smooth[-1])]
    )
    out = (1 - band_shallowing) * out + band_shallowing * smooth_full
    return np.clip(out, 0.0, 1.0)


def build_parametric_lunar(usgs_npz: Path) -> dict[str, np.ndarray]:
    if not usgs_npz.exists():
        raise FileNotFoundError(
            f"USGS cache missing at {usgs_npz}; "
            f"run `python scripts/download_usgs.py` first"
        )
    usgs = np.load(usgs_npz, allow_pickle=False)
    lam = usgs["wavelengths_nm"].astype(np.float64)
    out: dict[str, np.ndarray] = {"wavelengths_nm": lam}
    out["lunar_highland_soil"] = _apply_space_weathering(
        usgs["anorthite"], lam, reddening=0.15, darkening=0.30, band_shallowing=0.6
    )
    out["lunar_mare_soil"] = _apply_space_weathering(
        0.55 * usgs["pyroxene"] + 0.25 * usgs["olivine"] + 0.15 * usgs["ilmenite"]
        + 0.05 * usgs["anorthite"],
        lam,
        reddening=0.30,
        darkening=0.35,
        band_shallowing=0.65,
    )
    out["lunar_pyroxene_grain"] = _apply_space_weathering(
        usgs["pyroxene"], lam, reddening=0.20, darkening=0.20, band_shallowing=0.4
    )
    out["lunar_olivine_grain"] = _apply_space_weathering(
        usgs["olivine"], lam, reddening=0.20, darkening=0.20, band_shallowing=0.4
    )
    return out


# ---------------------------------------------------------------------------
# Optional real fetch
# ---------------------------------------------------------------------------


def try_fetch_relab(timeout: float = 6.0) -> dict[str, np.ndarray] | None:
    if not RELAB_CANDIDATE_URLS:
        return None
    result: dict[str, np.ndarray] = {"wavelengths_nm": WAVELENGTHS.copy()}
    for name, url in RELAB_CANDIDATE_URLS.items():
        try:
            r = requests.get(url, timeout=timeout)
            r.raise_for_status()
        except Exception as e:
            print(f"[warn] RELAB fetch failed for {name}: {e}")
            return None
        try:
            arr = np.loadtxt(r.text.splitlines())
            if arr.ndim != 2 or arr.shape[1] < 2:
                raise ValueError("expected 2-column ascii table")
            lam = arr[:, 0]
            refl = arr[:, 1]
            refl_resampled = np.interp(WAVELENGTHS, lam, refl)
            result[name] = np.clip(refl_resampled, 0.0, 1.0)
        except Exception as e:
            print(f"[warn] RELAB parse failed for {name}: {e}")
            return None
    return result


# ---------------------------------------------------------------------------
# Local-directory path (for users who already have a RELAB export)
# ---------------------------------------------------------------------------


def load_local_dir(local_dir: Path) -> dict[str, np.ndarray] | None:
    if not local_dir.exists() or not local_dir.is_dir():
        return None
    result: dict[str, np.ndarray] = {"wavelengths_nm": WAVELENGTHS.copy()}
    for path in sorted(local_dir.glob("*.txt")):
        try:
            arr = np.loadtxt(path)
            lam = arr[:, 0]
            refl = arr[:, 1]
            result[path.stem] = np.interp(WAVELENGTHS, lam, refl).clip(0.0, 1.0)
        except Exception as e:
            print(f"[warn] skipping {path.name}: {e}")
    return result if len(result) > 1 else None


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--usgs", type=Path, default=DEFAULT_USGS)
    parser.add_argument(
        "--local-dir",
        type=Path,
        default=None,
        help="skip the HTTP fetch and load 2-column ASCII files from this dir",
    )
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    if args.out.exists() and not args.force:
        print(f"[ok] cache already present: {args.out}")
        return 0

    bundle: dict[str, np.ndarray] | None = None
    source = "unknown"
    if args.local_dir is not None:
        bundle = load_local_dir(args.local_dir)
        if bundle is not None:
            source = f"local:{args.local_dir.name}"
            print(f"[ok] loaded {len(bundle) - 1} spectra from {args.local_dir}")

    if bundle is None:
        bundle = try_fetch_relab()
        if bundle is not None:
            source = "relab_http"
            print(f"[ok] fetched {len(bundle) - 1} spectra from RELAB")

    if bundle is None:
        bundle = build_parametric_lunar(args.usgs)
        source = "parametric_lunar"
        print(
            "[warn] no RELAB source available — falling back to "
            "parametric lunar spectra (tagged source=parametric_lunar)"
        )

    # sanity-check shapes
    for k, v in bundle.items():
        if k == "wavelengths_nm":
            continue
        if v.shape != (N_SPEC,):
            raise RuntimeError(f"{k} has wrong shape {v.shape}")
        if not np.all(np.isfinite(v)):
            raise RuntimeError(f"{k} contains NaN/Inf")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    np.savez(args.out, source=np.asarray(source), **bundle)
    print(f"[ok] wrote {args.out}  (source={source})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
