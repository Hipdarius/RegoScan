"""
Synthetic VERA spectral generator.

This is the physics-motivated engine that builds our training data.
It mixes mineral endmembers (olivine, pyroxene, etc) and adds realistic 
sensor noise (shot noise, baseline drift, cosmic rays). 

Once we get real hardware data from the Hamamatsu, it should drop into 
the same CSV schema and just work.
"""

import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from vera.schema import (
    AS7265X_BANDS,
    LED_WAVELENGTHS_NM,
    MINERAL_CLASSES,
    N_LED,
    N_SPEC,
    N_SWIR,
    PACKING_DENSITIES,
    SENSOR_MODES,
    WAVELENGTHS,
    Measurement,
)

ENDMEMBER_NAMES: tuple[str, ...] = (
    "olivine", "pyroxene", "anorthite", "ilmenite", "glass_agglutinate",
)
ENDMEMBER_INDEX: dict[str, int] = {n: i for i, n in enumerate(ENDMEMBER_NAMES)}

# Fluorescence efficiency @ 450nm under 405 nm excitation.
# Anorthite is the strongest emitter; ilmenite is opaque.
# Glass/agglutinate has weak residual fluorescence from trapped
# plagioclase fragments — suppressed by npFe0 darkening.
LIF_EFFICIENCY: dict[str, float] = {
    "olivine":           0.30,
    "pyroxene":          0.40,
    "anorthite":         0.85,
    "ilmenite":          0.00,
    "glass_agglutinate": 0.15,
}

LED_FWHM_NM: float = 25.0


@dataclass(frozen=True)
class Endmembers:
    """Ref spectra on the 288-px grid + SWIR reflectance points."""
    wavelengths_nm: np.ndarray
    spectra: np.ndarray      # (5, 288) — one row per endmember
    swir: np.ndarray         # (5, 2)  — reflectance at 940 & 1050 nm
    source: str

    @property
    def n_endmembers(self) -> int:
        return self.spectra.shape[0]


def load_endmembers(path: str | Path) -> Endmembers:
    """Loads the .npz from scripts/download_usgs.py"""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Missing endmember cache: {path}")

    data = np.load(path, allow_pickle=False)
    lam = data["wavelengths_nm"].astype(np.float64)

    # Validation
    if lam.shape != (N_SPEC,):
        raise ValueError(f"Bad wavelength grid shape: {lam.shape}")
    if not np.allclose(lam, WAVELENGTHS):
        raise ValueError("Grid mismatch with schema.WAVELENGTHS")

    rows = np.stack([data[n].astype(np.float64) for n in ENDMEMBER_NAMES], axis=0)

    # SWIR endmember reflectance (v1.2+); backward compat with old caches
    if f"{ENDMEMBER_NAMES[0]}_swir" in data.files:
        swir_rows = np.stack(
            [data[f"{n}_swir"].astype(np.float64) for n in ENDMEMBER_NAMES],
            axis=0,
        )
    else:
        # Fallback: linearly extrapolate from the last two spec channels
        # (rough but keeps old caches working until regenerated)
        swir_rows = np.column_stack([
            rows[:, -1] * 0.95,   # approximate 940 nm
            rows[:, -1] * 0.88,   # approximate 1050 nm
        ])

    source = str(data["source"]) if "source" in data.files else "unknown"
    return Endmembers(wavelengths_nm=lam, spectra=rows, swir=swir_rows, source=source)


def fractions_for_class(klass: str, rng: np.random.Generator) -> np.ndarray:
    """Draws mineral mass fractions for a target class.

    Returns a length-5 array indexed by ENDMEMBER_INDEX:
    [olivine, pyroxene, anorthite, ilmenite, glass_agglutinate].
    """
    n = len(ENDMEMBER_NAMES)
    f = np.zeros(n, dtype=np.float64)

    if klass == "olivine_rich":
        f[ENDMEMBER_INDEX["olivine"]] = rng.uniform(0.55, 0.85)
        f[ENDMEMBER_INDEX["pyroxene"]] = rng.uniform(0.05, 0.20)
        f[ENDMEMBER_INDEX["anorthite"]] = rng.uniform(0.05, 0.20)
        f[ENDMEMBER_INDEX["ilmenite"]] = rng.uniform(0.00, 0.05)
        f[ENDMEMBER_INDEX["glass_agglutinate"]] = rng.uniform(0.00, 0.08)
    elif klass == "pyroxene_rich":
        f[ENDMEMBER_INDEX["pyroxene"]] = rng.uniform(0.55, 0.85)
        f[ENDMEMBER_INDEX["olivine"]] = rng.uniform(0.05, 0.20)
        f[ENDMEMBER_INDEX["anorthite"]] = rng.uniform(0.05, 0.20)
        f[ENDMEMBER_INDEX["ilmenite"]] = rng.uniform(0.00, 0.05)
        f[ENDMEMBER_INDEX["glass_agglutinate"]] = rng.uniform(0.00, 0.08)
    elif klass == "anorthositic":
        f[ENDMEMBER_INDEX["anorthite"]] = rng.uniform(0.65, 0.92)
        f[ENDMEMBER_INDEX["olivine"]] = rng.uniform(0.02, 0.15)
        f[ENDMEMBER_INDEX["pyroxene"]] = rng.uniform(0.02, 0.15)
        f[ENDMEMBER_INDEX["ilmenite"]] = rng.uniform(0.00, 0.03)
        f[ENDMEMBER_INDEX["glass_agglutinate"]] = rng.uniform(0.00, 0.05)
    elif klass == "ilmenite_rich":
        f[ENDMEMBER_INDEX["ilmenite"]] = rng.uniform(0.35, 0.65)
        f[ENDMEMBER_INDEX["pyroxene"]] = rng.uniform(0.10, 0.30)
        f[ENDMEMBER_INDEX["olivine"]] = rng.uniform(0.05, 0.20)
        f[ENDMEMBER_INDEX["anorthite"]] = rng.uniform(0.05, 0.25)
        f[ENDMEMBER_INDEX["glass_agglutinate"]] = rng.uniform(0.00, 0.05)
    elif klass == "glass_agglutinate":
        # Mature regolith: 30–60% glass by volume (McKay et al. 1991).
        # The glass fraction must dominate clearly (>50%) to produce
        # the characteristic steep red slope that separates it from
        # ilmenite (flat-dark) and mixed (moderate albedo). Below 50%,
        # the glass signal is diluted by crystalline debris and the
        # spectrum becomes indistinguishable from mixed/ilmenite.
        f[ENDMEMBER_INDEX["glass_agglutinate"]] = rng.uniform(0.55, 0.80)
        f[ENDMEMBER_INDEX["anorthite"]] = rng.uniform(0.05, 0.18)
        f[ENDMEMBER_INDEX["pyroxene"]] = rng.uniform(0.03, 0.15)
        f[ENDMEMBER_INDEX["olivine"]] = rng.uniform(0.02, 0.08)
        f[ENDMEMBER_INDEX["ilmenite"]] = rng.uniform(0.00, 0.05)
    elif klass == "mixed":
        # Dirichlet prior gives a natural spread for unclassified soils.
        # The symmetric alpha (2.0) concentrates mass toward the center
        # of the simplex, producing more evenly-distributed compositions.
        # We cap the maximum single-endmember fraction at 0.35 so mixed
        # samples never overlap with dominant-class boundaries (which
        # start at 0.40+). Without this cap, ~36% of mixed samples had
        # a dominant fraction >0.5 and were indistinguishable from the
        # corresponding dominant class, causing 40% misclassification.
        for _attempt in range(50):
            f = rng.dirichlet(alpha=np.array([2.0, 2.0, 2.0, 1.2, 1.5]))
            f[ENDMEMBER_INDEX["ilmenite"]] = min(f[ENDMEMBER_INDEX["ilmenite"]], 0.20)
            f /= f.sum()
            if f.max() <= 0.35:
                break
        else:
            # Fallback: force near-uniform if Dirichlet keeps generating
            # dominant samples (astronomically unlikely with alpha=2.0)
            f = np.array([0.22, 0.22, 0.22, 0.14, 0.20])
            f /= f.sum()
    else:
        raise ValueError(f"Unknown class: {klass}")

    f = np.clip(f, 0.0, None)
    f /= f.sum()
    return f


@dataclass
class NoiseConfig:
    """Config for the hardware noise model."""
    gain_sigma: float = 0.015           # pixel responsivity jitter
    baseline_amp: float = 0.020         # peak drift
    intensity_sigma: float = 0.05       # overall brightness jitter
    shot_noise_scale: float = 1.0       # multiplier for Poisson noise
    led_noise_sigma: float = 0.010      # extra LED noise
    lif_noise_sigma: float = 0.020      # LIF channel noise
    intensity_by_packing: dict[str, float] = field(
        default_factory=lambda: {"loose": 0.85, "medium": 1.00, "packed": 1.10}
    )
    # Hardware degradation params
    cosmic_ray_prob: float = 0.02
    cosmic_ray_amp_range: tuple[float, float] = (0.15, 0.45)
    degradation_pct_hot: float = 0.005
    degradation_hot_range: tuple[float, float] = (0.40, 0.85)
    degradation_mild_sigma: float = 0.008


def _polynomial_baseline(rng: np.random.Generator, amp: float) -> np.ndarray:
    """Smooth degree-3 baseline drift (e.g. ambient light leak)."""
    x = np.linspace(-1.0, 1.0, N_SPEC)
    coeffs = rng.uniform(-1.0, 1.0, size=4) 
    poly = coeffs[0] + coeffs[1] * x + coeffs[2] * x**2 + coeffs[3] * x**3
    poly = poly / np.max(np.abs(poly) + 1e-12)
    return amp * poly


def _shot_noise(spectrum: np.ndarray, rng: np.random.Generator,
                integration_time_ms: int, scale: float) -> np.ndarray:
    """Standard shot noise model."""
    const = 5_000.0 * (integration_time_ms / 200.0)
    counts = np.maximum(spectrum, 1e-6) * const
    noisy_counts = rng.poisson(counts).astype(np.float64)
    noisy = noisy_counts / const
    return spectrum + scale * (noisy - spectrum)


def sensor_degradation_mask(rng: np.random.Generator, cfg: "NoiseConfig") -> np.ndarray:
    """Fixed responsivity mask per sample (models aging/radiation damage)."""
    mask = 1.0 + rng.normal(0.0, cfg.degradation_mild_sigma, size=N_SPEC)
    n_hot = max(0, int(round(cfg.degradation_pct_hot * N_SPEC)))
    if n_hot > 0:
        hot_idx = rng.choice(N_SPEC, size=n_hot, replace=False)
        lo, hi = cfg.degradation_hot_range
        mask[hot_idx] = 1.0 - rng.uniform(lo, hi, size=n_hot)
    return np.clip(mask, 0.0, 1.2)


def _apply_cosmic_rays(spectrum: np.ndarray, rng: np.random.Generator, cfg: "NoiseConfig") -> np.ndarray:
    """Rare spikes—probe will see these in high-cadence lunar environments."""
    if rng.uniform(0.0, 1.0) >= cfg.cosmic_ray_prob:
        return spectrum
    n_hits = int(rng.integers(1, 4))
    out = spectrum.copy()
    lo, hi = cfg.cosmic_ray_amp_range
    for _ in range(n_hits):
        idx = int(rng.integers(0, N_SPEC))
        amp = float(rng.uniform(lo, hi))
        out[idx] = min(1.5, out[idx] + amp)
        if idx > 0:
            out[idx - 1] = min(1.5, out[idx - 1] + 0.4 * amp)
        if idx + 1 < N_SPEC:
            out[idx + 1] = min(1.5, out[idx + 1] + 0.4 * amp)
    return out


def _led_response(spectrum: np.ndarray) -> np.ndarray:
    """Gaussian integration for LED channels."""
    sigma = LED_FWHM_NM / (2.0 * np.sqrt(2.0 * np.log(2.0)))
    out = np.empty(N_LED, dtype=np.float64)
    lam = WAVELENGTHS
    for i, center in enumerate(LED_WAVELENGTHS_NM):
        w = np.exp(-0.5 * ((lam - center) / sigma) ** 2)
        wsum = w.sum()
        if wsum < 1e-9:
            # Fallback for LEDs outside spectrometer range
            out[i] = float(spectrum[-1]) * 0.85
        else:
            out[i] = float((w * spectrum).sum() / wsum)
    return out


def _as7265x_response(spectrum: np.ndarray) -> np.ndarray:
    """Simulate AS7265x 18-band readings via Gaussian bandpass integration.

    Each AS7265x channel integrates the continuous spectrum through a
    Gaussian filter centered on its band wavelength. FWHM = 20 nm per
    the AS7265x datasheet, giving sigma = 20 / 2.355 ~= 8.49 nm.
    """
    sigma = 20.0 / (2.0 * np.sqrt(2.0 * np.log(2.0)))  # ~8.49 nm
    out = np.empty(len(AS7265X_BANDS), dtype=np.float64)
    lam = WAVELENGTHS
    for i, center in enumerate(AS7265X_BANDS):
        w = np.exp(-0.5 * ((lam - center) / sigma) ** 2)
        wsum = w.sum()
        if wsum < 1e-9:
            out[i] = float(spectrum[-1]) * 0.85
        else:
            out[i] = float((w * spectrum).sum() / wsum)
    return out


def _perturb_endmembers_swir(
    swir: np.ndarray, rng: np.random.Generator
) -> np.ndarray:
    """Apply matching perturbation to SWIR endmember values.

    Uses the same perturbation model as the spectral endmembers:
    multiplicative gain (±8%) and per-channel noise (sigma=0.005).
    Spectral tilt is adapted for the 2-point SWIR grid.
    """
    out = swir.copy()
    n_em, n_pts = out.shape
    gain = 1.0 + rng.normal(0.0, 0.08, size=(n_em, 1))
    out = out * gain
    out = out + rng.normal(0.0, 0.005, size=out.shape)
    return np.clip(out, 0.0, 1.5)


def _perturb_endmembers(
    endmembers: Endmembers, rng: np.random.Generator
) -> np.ndarray:
    """Apply per-sample endmember perturbation to simulate natural
    mineralogical variation.

    Real olivine from different rocks has slightly different Fe/Mg
    ratios, grain sizes, and crystal orientations — all of which shift
    the reflectance spectrum. Without this perturbation, the CNN
    memorizes the exact parametric endmember shapes and fails to
    generalize across random seeds (~18% cross-seed accuracy).

    The perturbation model:
    - Multiplicative gain per endmember (±8%): simulates grain size
      and Fe/Mg ratio variations that scale overall reflectance
    - Additive spectral tilt (±0.02/500nm): simulates orientation-
      dependent scattering slope changes
    - Per-channel noise (sigma=0.005): simulates micro-scale
      compositional heterogeneity within a single mineral grain
    """
    spectra = endmembers.spectra.copy()
    n_em, n_pix = spectra.shape

    # Multiplicative gain (grain size / Fe-Mg ratio effect)
    gain = 1.0 + rng.normal(0.0, 0.08, size=(n_em, 1))
    spectra = spectra * gain

    # Spectral tilt (orientation-dependent scattering)
    tilt = rng.normal(0.0, 0.02, size=(n_em, 1))
    ramp = np.linspace(-0.5, 0.5, n_pix).reshape(1, -1)
    spectra = spectra + tilt * ramp

    # Per-channel compositional noise
    spectra = spectra + rng.normal(0.0, 0.005, size=spectra.shape)

    return np.clip(spectra, 0.0, 1.5)


def mixture_spectrum(fractions: np.ndarray, endmembers: Endmembers) -> np.ndarray:
    """Linear mixture of pure endmember spectra by mass fraction.

    Valid for **macroscopic** (areal) mixing — e.g. a checkerboard of
    mineral grains illuminated as separate scenes. For intimate mixing
    (intra-grain or fine powder), use :func:`mixture_spectrum_hapke`
    instead.
    """
    return fractions @ endmembers.spectra


# ---------------------------------------------------------------------------
# Hapke nonlinear mixing (intimate mixtures)
# ---------------------------------------------------------------------------
#
# Linear mixing assumes each photon interacts with exactly one mineral grain.
# That holds for *areal* mixtures (a mosaic) but breaks for *intimate*
# mixtures, where a photon scatters off multiple grains before exiting.
#
# Hapke's bidirectional reflectance theory (Hapke 1981, 1993) operates on
# single-scattering albedo ``w`` instead of reflectance ``R``. For an
# intimate mixture you average single-scattering albedos linearly, then
# convert back to reflectance.
#
# The closed-form simplification of the IMSA (isotropic multiple
# scattering, hemispherical reflectance at normal incidence) gives
#
#     R(w) = w / (1 + sqrt(1 - w))^2
#
# Inverting:
#
#     w(R) = 1 - ((1 - R) / (1 + R))^2
#
# Algorithm:
#     1. R_i  -> w_i   (per mineral, per channel)
#     2. w_mix = sum_i (f_i * w_i)
#     3. R_mix = w_mix / (1 + sqrt(1 - w_mix))^2
#
# This is the simplest physically grounded nonlinear mixing model. For
# bench-scale fine regolith analogues it's a much better approximation
# than linear mixing, especially when one mineral is very dark (ilmenite)
# and another is very bright (anorthite).
#
# References:
#   Hapke (1981) "Bidirectional reflectance spectroscopy. 1. Theory",
#       J. Geophys. Res. 86, 3039-3054.
#   Mustard & Pieters (1989) "Photometric phase functions of common
#       geologic minerals and applications to quantitative analysis",
#       J. Geophys. Res. 94, 13619-13634.


def reflectance_to_ssa(R: np.ndarray) -> np.ndarray:
    """Closed-form reflectance → single-scattering albedo (IMSA approximation).

    R must be in ``[0, 1]``. Values >= 1 are clipped to (1 - 1e-9) to keep
    the formula numerically stable.
    """
    R_clip = np.clip(np.asarray(R, dtype=np.float64), 0.0, 1.0 - 1e-9)
    s = (1.0 - R_clip) / (1.0 + R_clip)
    return 1.0 - s * s


def ssa_to_reflectance(w: np.ndarray) -> np.ndarray:
    """Closed-form single-scattering albedo → reflectance (IMSA approximation)."""
    w_clip = np.clip(np.asarray(w, dtype=np.float64), 0.0, 1.0 - 1e-9)
    return w_clip / (1.0 + np.sqrt(1.0 - w_clip)) ** 2


def mixture_spectrum_hapke(
    fractions: np.ndarray,
    endmember_spectra: np.ndarray,
) -> np.ndarray:
    """Hapke intimate-mixture reflectance from pure endmember spectra.

    Parameters
    ----------
    fractions
        Mass-fraction vector summing to 1. Shape: ``(N_endmembers,)``.
    endmember_spectra
        Pure mineral reflectance curves. Shape: ``(N_endmembers, N_channels)``.
        Values must lie in ``[0, 1]``.

    Returns
    -------
    Mixed reflectance, shape ``(N_channels,)``.

    Notes
    -----
    Assumes equal grain size across endmembers. For grain-size-aware
    Hapke, the SSA average becomes ``(M_i / (rho_i * D_i))``-weighted —
    we don't model that here because the synthesizer doesn't carry
    per-mineral density.
    """
    fractions = np.asarray(fractions, dtype=np.float64).ravel()
    spectra = np.asarray(endmember_spectra, dtype=np.float64)
    if spectra.ndim != 2 or spectra.shape[0] != fractions.shape[0]:
        raise ValueError(
            f"endmember_spectra shape {spectra.shape} doesn't match "
            f"fractions length {fractions.shape[0]}"
        )
    # Step 1: per-mineral, per-channel single-scattering albedo
    ssa = reflectance_to_ssa(spectra)            # (N_em, N_ch)
    # Step 2: linearly mix SSAs
    ssa_mix = fractions @ ssa                    # (N_ch,)
    # Step 3: back to reflectance
    return ssa_to_reflectance(ssa_mix)


def mix_spectra(
    fractions: np.ndarray,
    endmember_spectra: np.ndarray,
    *,
    model: str = "linear",
) -> np.ndarray:
    """Dispatch wrapper: linear or Hapke intimate mixing.

    Parameters
    ----------
    fractions, endmember_spectra
        See :func:`mixture_spectrum_hapke`.
    model
        ``"linear"`` (default, fast, areal mixing) or
        ``"hapke"`` (nonlinear, intimate mixing).
    """
    if model == "linear":
        return np.asarray(fractions, dtype=np.float64) @ np.asarray(
            endmember_spectra, dtype=np.float64
        )
    if model == "hapke":
        return mixture_spectrum_hapke(fractions, endmember_spectra)
    raise ValueError(f"unknown mixing model: {model!r}")


def synth_measurement(
    sample_id: str,
    mineral_class: str,
    fractions: np.ndarray,
    endmembers: Endmembers,
    rng: np.random.Generator,
    *,
    integration_time_ms: int | None = None,
    ambient_temp_c: float | None = None,
    packing_density: str | None = None,
    noise: NoiseConfig | None = None,
    timestamp: str | None = None,
    degradation_mask: np.ndarray | None = None,
    sensor_mode: str = "combined",
    mixing_model: str = "linear",
) -> Measurement:
    """Builds one fake measurement.

    Parameters
    ----------
    sensor_mode : str
        One of ``"full"``, ``"multispectral"``, or ``"combined"``.
        Controls whether AS7265x data is synthesised. The C12880MA
        spectrum (``spec``) is always populated (the Measurement model
        requires it). ``sensor_mode`` is stored on the output so
        downstream code knows which channels to use for ML features.
    mixing_model : str
        ``"linear"`` (default) — areal mixing. Each photon hits one
        grain. Fast, valid for macroscopic mixtures or coarse grains.
        ``"hapke"`` — nonlinear intimate mixing. Each photon scatters
        off multiple grains. Required for fine regolith powder where a
        small fraction of dark mineral (ilmenite) suppresses the bright
        mineral signal disproportionately.
    """
    if sensor_mode not in SENSOR_MODES:
        raise ValueError(
            f"Unknown sensor_mode: {sensor_mode!r}; expected one of {SENSOR_MODES}"
        )
    if noise is None:
        noise = NoiseConfig()
    if integration_time_ms is None:
        integration_time_ms = int(rng.integers(80, 400))
    if ambient_temp_c is None:
        ambient_temp_c = float(rng.normal(20.0, 3.0))
    if packing_density is None:
        packing_density = str(rng.choice(PACKING_DENSITIES))
    if timestamp is None:
        timestamp = datetime.now(UTC).isoformat()

    # Pipeline: perturb endmember spectra to simulate natural
    # mineralogical variation, then mix with the target fractions.
    # The mixing model controls whether linear (areal) or Hapke
    # (intimate) mixing is used; see module docstring for details.
    perturbed = _perturb_endmembers(endmembers, rng)
    perturbed_swir = _perturb_endmembers_swir(endmembers.swir, rng)
    base = mix_spectra(fractions, perturbed, model=mixing_model)
    base_swir = mix_spectra(fractions, perturbed_swir, model=mixing_model)

    # Noise model
    gain = 1.0 + rng.normal(0.0, noise.gain_sigma, size=N_SPEC)
    spec = base * gain
    spec = spec + _polynomial_baseline(rng, noise.baseline_amp)

    intensity = noise.intensity_by_packing.get(packing_density, 1.0)
    intensity *= 1.0 + rng.normal(0.0, noise.intensity_sigma)
    spec = spec * intensity

    if degradation_mask is not None:
        spec = spec * degradation_mask

    spec = _shot_noise(spec, rng, integration_time_ms, noise.shot_noise_scale)
    spec = _apply_cosmic_rays(spec, rng, noise)

    # Clip but keep a bit of noise visible above 1.0
    spec = np.clip(spec, 0.0, 1.5)

    # LED and LIF logic
    led_clean = _led_response(base * intensity)
    led = led_clean + rng.normal(0.0, noise.led_noise_sigma, size=N_LED)
    led = np.clip(led, 0.0, 1.5)

    ilm_frac = float(fractions[ENDMEMBER_INDEX["ilmenite"]])
    eff = sum(
        float(fractions[ENDMEMBER_INDEX[name]]) * LIF_EFFICIENCY[name]
        for name in ENDMEMBER_NAMES
    )
    # Quenching model: 1.5 power might be too sharp? Check Hapke refs.
    quench = (1.0 - ilm_frac) ** 1.5
    lif = eff * quench * intensity
    lif += rng.normal(0.0, noise.lif_noise_sigma)
    lif = float(max(lif, 0.0))

    # --- SWIR InGaAs photodiode channels ---
    # Apply matching intensity/noise pipeline to the SWIR reflectance
    swir_clean = base_swir * intensity
    swir = swir_clean + rng.normal(0.0, noise.led_noise_sigma, size=N_SWIR)
    # 16-bit ADC quantization (ADS1115)
    swir = np.round(swir * 65535.0) / 65535.0
    swir = np.clip(swir, 0.0, 1.5)
    swir_data: list[float] = [float(x) for x in swir]

    # --- AS7265x channels (when requested) ---
    as7265x_data: list[float] | None = None
    if sensor_mode in ("multispectral", "combined"):
        # 20 nm FWHM Gaussian bandpass integration
        as7_clean = _as7265x_response(base * intensity)
        # +/-12% multiplicative uniform noise (AS7265x datasheet accuracy spec)
        as7_noise = rng.uniform(0.88, 1.12, size=len(AS7265X_BANDS))
        as7 = as7_clean * as7_noise
        # 16-bit ADC quantization
        as7 = np.round(as7 * 65535.0) / 65535.0
        as7 = np.clip(as7, 0.0, 1.5)
        as7265x_data = [float(x) for x in as7]

    return Measurement(
        sample_id=sample_id,
        measurement_id=str(uuid.UUID(bytes=bytes(rng.bytes(16)))),
        timestamp=timestamp,
        mineral_class=mineral_class,  # type: ignore
        ilmenite_fraction=ilm_frac,
        integration_time_ms=int(integration_time_ms),
        ambient_temp_c=float(ambient_temp_c),
        packing_density=packing_density,  # type: ignore
        sensor_mode=sensor_mode,  # type: ignore
        spec=[float(x) for x in spec],
        led=[float(x) for x in led],
        lif_450lp=lif,
        swir=swir_data,
        as7265x=as7265x_data,
    )


def synth_sample(
    sample_id: str,
    mineral_class: str,
    endmembers: Endmembers,
    *,
    n_measurements: int,
    rng: np.random.Generator,
    noise: NoiseConfig | None = None,
    sensor_mode: str = "combined",
    mixing_model: str = "linear",
) -> list[Measurement]:
    """Generate ``n_measurements`` measurements for one (sample, class) pair.

    Composition is fixed once per sample so that all measurements of the
    same sample share the same ilmenite fraction (modulo measurement noise).
    A sensor degradation mask is also fixed per sample, so the same dead/
    hot pixels persist across a sample's measurements -- matching real
    hardware where pixel aging is slow compared to measurement cadence.
    """
    cfg = noise or NoiseConfig()
    fractions = fractions_for_class(mineral_class, rng)
    degradation_mask = sensor_degradation_mask(rng, cfg)
    out: list[Measurement] = []
    for _ in range(n_measurements):
        out.append(
            synth_measurement(
                sample_id=sample_id,
                mineral_class=mineral_class,
                fractions=fractions,
                endmembers=endmembers,
                rng=rng,
                noise=cfg,
                degradation_mask=degradation_mask,
                sensor_mode=sensor_mode,
                mixing_model=mixing_model,
            )
        )
    return out


def synth_dataset(
    endmembers: Endmembers,
    *,
    n_samples: int,
    measurements_per_sample: int,
    seed: int = 0,
    classes: Iterable[str] = MINERAL_CLASSES,
    noise: NoiseConfig | None = None,
    sensor_mode: str = "combined",
    mixing_model: str = "linear",
) -> list[Measurement]:
    """Generate a complete synthetic dataset.

    Classes are dealt round-robin so the dataset is approximately balanced.

    Parameters
    ----------
    mixing_model : str
        ``"linear"`` (default) or ``"hapke"``. See
        :func:`synth_measurement` for details.
    """
    rng = np.random.default_rng(seed)
    classes = tuple(classes)
    out: list[Measurement] = []
    for i in range(n_samples):
        klass = classes[i % len(classes)]
        sample_id = f"S{i:04d}_{klass}"
        out.extend(
            synth_sample(
                sample_id=sample_id,
                mineral_class=klass,
                endmembers=endmembers,
                n_measurements=measurements_per_sample,
                rng=rng,
                noise=noise,
                sensor_mode=sensor_mode,
                mixing_model=mixing_model,
            )
        )
    return out


__all__ = [
    "ENDMEMBER_INDEX",
    "ENDMEMBER_NAMES",
    "LIF_EFFICIENCY",
    "Endmembers",
    "NoiseConfig",
    "_as7265x_response",
    "fractions_for_class",
    "load_endmembers",
    "mix_spectra",
    "mixture_spectrum",
    "mixture_spectrum_hapke",
    "reflectance_to_ssa",
    "ssa_to_reflectance",
    "synth_dataset",
    "synth_measurement",
    "synth_sample",
]
