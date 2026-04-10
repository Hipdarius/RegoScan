"""Fetch / build the four USGS-derived mineral endmember spectra.

We need reflectance spectra for olivine, pyroxene, anorthite, and ilmenite,
resampled to the Hamamatsu C12880MA grid (340–850 nm, 288 points), so the
synthetic dataset generator can linear-mix them.

This script tries (briefly) to fetch real spectra from the USGS Spectral
Library; if that fails — which it routinely will in air-gapped or offline
contexts — it falls back to a **physically motivated parametric model** of
each mineral built from documented absorption-band positions and depths.

Either way, the output is a single ``.npz`` cached at
``data/cache/usgs_endmembers.npz`` with arrays:

    wavelengths_nm   (288,)  float64
    olivine          (288,)  float64  reflectance in [0, 1]
    pyroxene         (288,)  float64
    anorthite        (288,)  float64
    ilmenite         (288,)  float64
    source           ()      str     "usgs" or "parametric"

Downstream code never touches this script — it loads the .npz directly from
:mod:`vera.synth`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

# Make sure ``vera`` resolves when this script is invoked from the repo
# root without ``uv run``.
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from vera.schema import N_SPEC, WAVELENGTHS  # noqa: E402

DEFAULT_OUT = ROOT / "data" / "cache" / "usgs_endmembers.npz"


# ---------------------------------------------------------------------------
# Parametric endmember model
# ---------------------------------------------------------------------------
#
# Each mineral is modelled as:
#     R(λ) = continuum(λ) * Π_b (1 - depth_b * gaussian(λ; center_b, σ_b))
#
# clipped to [0, 1]. Continuum and absorption parameters are chosen to
# reproduce the qualitative shape of USGS Spectral Library spectra in the
# 340–850 nm window. They are NOT exact USGS values — but for a synthetic
# pipeline whose purpose is wiring validation, that is what we want.
#
# References (positions/widths only):
#   Adams 1974, Burns 1993 (Fe2+ crystal-field bands in olivine, pyroxene)
#   Pieters & Englert 1993 (Remote Geochemical Analysis)
#   Cloutis 2002 (pyroxene VNIR review)
# ---------------------------------------------------------------------------


def _gauss(lam: np.ndarray, center: float, sigma: float) -> np.ndarray:
    return np.exp(-0.5 * ((lam - center) / sigma) ** 2)


def _apply_bands(
    lam: np.ndarray,
    continuum: np.ndarray,
    bands: list[tuple[float, float, float]],
) -> np.ndarray:
    out = continuum.copy()
    for center, sigma, depth in bands:
        out *= 1.0 - depth * _gauss(lam, center, sigma)
    return np.clip(out, 0.0, 1.0)


def parametric_olivine(lam: np.ndarray) -> np.ndarray:
    """Olivine: broad Fe2+ band centred ~1050 nm; we see its rising edge.

    Continuum is reddish (rises with wavelength). UV drop below ~400 nm.
    """
    continuum = 0.18 + 0.55 * (lam - 340.0) / (850.0 - 340.0)
    bands = [
        (320.0, 60.0, 0.90),   # UV drop
        (1050.0, 220.0, 0.55), # main Fe2+ band — only its rising edge in 340–850
        (650.0, 70.0, 0.08),   # subtle Fe shoulder
    ]
    return _apply_bands(lam, continuum, bands)


def parametric_pyroxene(lam: np.ndarray) -> np.ndarray:
    """Pyroxene: ~900 and ~1900 nm Fe2+ bands; we see edge of the 900 nm band.

    Slightly darker continuum than olivine, sharper red edge.
    """
    continuum = 0.12 + 0.50 * (lam - 340.0) / (850.0 - 340.0)
    bands = [
        (320.0, 55.0, 0.95),
        (920.0, 150.0, 0.65),  # main Fe2+ band centre just above our window
        (505.0, 55.0, 0.10),
    ]
    return _apply_bands(lam, continuum, bands)


def parametric_anorthite(lam: np.ndarray) -> np.ndarray:
    """Anorthite (Ca-plagioclase): high, fairly featureless reflectance.

    Slight UV drop and a very weak ~650 nm Fe2+ feature when impure.
    """
    continuum = 0.55 + 0.30 * (lam - 340.0) / (850.0 - 340.0)
    bands = [
        (300.0, 50.0, 0.60),
        (660.0, 90.0, 0.04),
    ]
    return _apply_bands(lam, continuum, bands)


def parametric_ilmenite(lam: np.ndarray) -> np.ndarray:
    """Ilmenite (FeTiO3): very dark, nearly flat, weak red brightening.

    Reflectance ~0.05–0.13 across the visible. The dominant signature is
    *darkness*, which is exactly why it shows up cleanly in linear mixtures.
    """
    continuum = 0.05 + 0.06 * (lam - 340.0) / (850.0 - 340.0)
    bands = [
        (300.0, 60.0, 0.30),
        (560.0, 200.0, 0.10),  # very shallow broad absorption
    ]
    return _apply_bands(lam, continuum, bands)


def parametric_glass_agglutinate(lam: np.ndarray) -> np.ndarray:
    """Impact-melt glass + agglutinates: dark, red-sloped, featureless.

    Space weathering produces nanophase iron (npFe0) in glass rims on
    regolith grains. The optical effect is twofold: overall darkening
    (lower albedo than any crystalline mineral except ilmenite) and
    strong reddening (reflectance rises steeply toward NIR).

    Unlike ilmenite, glass has moderate albedo in the NIR (>700 nm)
    and no Ti charge-transfer absorption — this is the key spectral
    discriminator between the two dark endmembers.

    Refs: Hapke 2001, Noble et al. 2007 (npFe0 optical model)
    """
    # Steep red slope with low UV reflectance — hallmark of npFe0
    continuum = 0.04 + 0.22 * (lam - 340.0) / (850.0 - 340.0)
    bands = [
        (320.0, 50.0, 0.85),   # deep UV cutoff from Fe charge transfer
        (500.0, 150.0, 0.06),  # very subtle broad suppression in visible
    ]
    return _apply_bands(lam, continuum, bands)


def build_parametric_endmembers() -> dict[str, np.ndarray]:
    lam = WAVELENGTHS.astype(np.float64)
    return {
        "wavelengths_nm": lam,
        "olivine": parametric_olivine(lam),
        "pyroxene": parametric_pyroxene(lam),
        "anorthite": parametric_anorthite(lam),
        "ilmenite": parametric_ilmenite(lam),
        "glass_agglutinate": parametric_glass_agglutinate(lam),
    }


# ---------------------------------------------------------------------------
# Optional online fetch (best-effort)
# ---------------------------------------------------------------------------
#
# We deliberately keep this very small. The USGS Spectral Library serves
# spectra as ASCII or .sli files behind a query interface that is not stable
# enough to script reliably. Rather than embed brittle URLs that may rot, we
# provide a hook for a future, hardware-aware session to plug in real
# spectra. For now, the parametric path is the source of truth.
# ---------------------------------------------------------------------------


def try_fetch_usgs() -> dict[str, np.ndarray] | None:
    """Stub for a future real USGS fetch. Always returns None today.

    When real spectra are available, this function should return a dict
    with the same keys as :func:`build_parametric_endmembers`. The rest of
    the pipeline does not care which path was taken.
    """
    return None


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help=f"output .npz path (default: {DEFAULT_OUT})",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="rebuild even if the cache file already exists",
    )
    args = parser.parse_args(argv)

    out: Path = args.out
    if out.exists() and not args.force:
        cached = np.load(out, allow_pickle=False)
        print(f"[ok] cache already present: {out}")
        print(f"     source = {str(cached['source'])}")
        print(f"     keys   = {sorted(cached.files)}")
        return 0

    fetched = try_fetch_usgs()
    if fetched is not None:
        endmembers = fetched
        source = "usgs"
        print("[ok] fetched real USGS spectra")
    else:
        endmembers = build_parametric_endmembers()
        source = "parametric"
        print("[warn] USGS fetch unavailable — using parametric endmembers")

    # sanity-check shapes
    for name in ("olivine", "pyroxene", "anorthite", "ilmenite", "glass_agglutinate"):
        arr = endmembers[name]
        assert arr.shape == (N_SPEC,), f"{name} has wrong shape {arr.shape}"
        assert np.all(np.isfinite(arr)), f"{name} contains NaN/Inf"
        assert (arr >= 0).all() and (arr <= 1).all(), f"{name} outside [0, 1]"

    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        out,
        wavelengths_nm=endmembers["wavelengths_nm"],
        olivine=endmembers["olivine"],
        pyroxene=endmembers["pyroxene"],
        anorthite=endmembers["anorthite"],
        ilmenite=endmembers["ilmenite"],
        glass_agglutinate=endmembers["glass_agglutinate"],
        source=np.asarray(source),
    )
    print(f"[ok] wrote {out}")
    print(f"     source = {source}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
