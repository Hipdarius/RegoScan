"""
Synthetic VERA spectral generator.

This is the physics-motivated engine that builds our training data.
It mixes mineral endmembers (olivine, pyroxene, etc) and adds realistic 
sensor noise (shot noise, baseline drift, cosmic rays). 

Once we get real hardware data from the Hamamatsu, it should drop into 
the same CSV schema and just work.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import numpy as np

from vera.schema import (
    AS7265X_BANDS,
    LED_WAVELENGTHS_NM,
    MINERAL_CLASSES,
    Measurement,
    N_LED,
    N_SPEC,
    PACKING_DENSITIES,
    SENSOR_MODES,
    WAVELENGTHS,
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
    "glass_agglutinate": 0.12,
}

LED_FWHM_NM: float = 25.0


@dataclass(frozen=True)
class Endmembers:
    """Ref spectra on the 288-px grid."""
    wavelengths_nm: np.ndarray
    spectra: np.ndarray  # (5, 288) — one row per endmember
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
    source = str(data["source"]) if "source" in data.files else "unknown"
    return Endmembers(wavelengths_nm=lam, spectra=rows, source=source)


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
        # The remainder is comminuted crystalline debris — mostly
        # plagioclase and pyroxene fragments trapped in the melt.
        f[ENDMEMBER_INDEX["glass_agglutinate"]] = rng.uniform(0.40, 0.70)
        f[ENDMEMBER_INDEX["anorthite"]] = rng.uniform(0.10, 0.25)
        f[ENDMEMBER_INDEX["pyroxene"]] = rng.uniform(0.05, 0.20)
        f[ENDMEMBER_INDEX["olivine"]] = rng.uniform(0.02, 0.10)
        f[ENDMEMBER_INDEX["ilmenite"]] = rng.uniform(0.00, 0.08)
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


def mixture_spectrum(fractions: np.ndarray, endmembers: Endmembers) -> np.ndarray:
    return fractions @ endmembers.spectra 


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
        timestamp = datetime.now(timezone.utc).isoformat()

    # Pipeline
    base = mixture_spectrum(fractions, endmembers)

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
) -> list[Measurement]:
    """Generate a complete synthetic dataset.

    Classes are dealt round-robin so the dataset is approximately balanced.
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
            )
        )
    return out


__all__ = [
    "ENDMEMBER_NAMES",
    "ENDMEMBER_INDEX",
    "LIF_EFFICIENCY",
    "Endmembers",
    "NoiseConfig",
    "load_endmembers",
    "fractions_for_class",
    "mixture_spectrum",
    "_as7265x_response",
    "synth_measurement",
    "synth_sample",
    "synth_dataset",
]
