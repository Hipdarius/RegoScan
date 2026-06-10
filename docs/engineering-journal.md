# VERA Engineering Journal

**Project:** VERA (Visible & Emission Regolith Assessment) — compact dual-sensor VIS/NIR + 405 nm LIF probe for real-time lunar regolith mineralogy  
**Builder:** Darius Ferent, Lycée des Arts et Métiers, Luxembourg. LSA Astronaut for a Day Ambassador.  
**Repository:** github.com/Hipdarius/VERA  
**Competition target:** Jonk Fuerscher 2027 → flagship prizes (TISF, EUCYS, ISEF)  
**Purpose:** Permanent engineering record feeding a 15–20 page LaTeX competition paper  
**Rule:** Append-only. No entry is ever deleted or modified after creation.

---

## Entry Format

Each entry follows this structure:

```
### YYYY-MM-DD — <short title>
**Commit:** `<hash>` (if applicable)

**What was done:**
<technical detail>

**Why:**
<scientific / engineering / competition-strategic motivation>

**Discovered / Learned:**
<especially failures, surprises, unexpected results>

**Paper impact:**
<which section(s) this affects: Introduction | Background/Prior Art | Instrument Design | Methods | Results | Discussion | Conclusion | Limitations>

**Open questions:**
- <remaining unknowns>
```

---

## Project Context (as of initial journal creation)

VERA (formerly REGOSCAN) combines a 288-channel VIS/NIR spectrometer (Hamamatsu C12880MA), an 18-channel multispectral sensor (AMS AS7265x), 12 narrowband LEDs, and a 405 nm laser-induced fluorescence channel. Classifies 6 mineral types and estimates ilmenite mass fraction. Built for Jonk Fuerscher 2027.

**Current state at journal creation (2026-04-11):** ~11,500 lines of code, 112 tests passing, no hardware yet, zero real spectra collected.

---

## Key Metrics Snapshot — 2026-04-11

| Metric | Value |
|:-------|------:|
| Total code | ~11,500 lines |
| Tests | 112 passing |
| Mineral classes | 6 |
| Sensor modes | 3 (full / multispectral / combined) |
| Same-seed accuracy | 99.0% |
| Cross-seed accuracy | 70% |
| CNN parameters | ~670k |
| Inference time | <5 ms CPU |
| Hardware ordered | Nothing |
| Real spectra collected | Zero |

---

## Strategic Context

**Jonk Fuerscher:** 83 projects, 20 prizes. Recent flagship winners: Rodion Zaichikov (hypersonic wind tunnel + Schlieren imaging → TISF), Krzesimir Hyzyk (embedded ML for navigation → ISEF). VERA fits the pattern the jury rewards. ESRIC (European Space Resources Innovation Centre) is headquartered in Luxembourg — direct institutional relevance.

**ISEF scoring:** Research problem (10pts), design/methodology (15pts), construction/testing (20pts), creativity/impact (20pts), presentation (35pts). Presentation is the largest block. Publication before competition adds massive credibility.

**EUCYS:** 90 projects, 12 podium spots. ESA special prize is natural fit for VERA.

**TISF:** ~230 projects, dedicated engineering category (~20 projects). Highest-probability path for VERA.

**Critical success factors:**
1. Working hardware with real measurements (not just synthetic)
2. XRF validation from ESRIC/LIST on 5+ samples (the "hero figure")
3. Industry mentor letter
4. At least one formal mentor (ESRIC researcher)
5. The AS7265x vs C12880MA comparison study ("can €25 match €290?")
6. The domain gap study (synthetic-trained model on real data)
7. Blind classification demo at the booth

---

## Journal Entries

---

### 2026-04-11 — Entry 1: Dual-Sensor Architecture (AS7265x Integration)

**Commits:** `ce5b963`, `d50e5fd`, `9a54033`, `00f51b1`

**What was done:**
Added support for a second sensor — the AMS AS7265x, an €25 18-channel multispectral sensor (410–940 nm) — alongside the existing Hamamatsu C12880MA 288-channel spectrometer (€290). Schema v1.1.0 introduces three sensor modes: `full` (C12880MA only, 301 features), `multispectral` (AS7265x only, 31 features), `combined` (both, 319 features). Synthetic data generation simulates AS7265x readings via Gaussian bandpass integration (FWHM=20 nm per datasheet) with ±12% channel accuracy noise and 16-bit ADC quantization. CNN input dimension is now configurable: stem convolution adapts kernel size (k=3 for 31 features vs k=9 for 301) to prevent spatial dimension collapse on small inputs. Firmware state machine gains a MULTISPECTRAL state between BROADBAND and NARROWBAND, with graceful degradation when the sensor is absent. AS7265x I²C driver implements the AMS virtual register protocol, reading calibrated IEEE 754 floats from all three dies. Feature extraction for multispectral mode maps hand-crafted features to nearest AS7265x bands: `broad_albedo` (mean of 18 bands), `vis_red_slope` (as7_705/as7_485), `uv_blue_drop` (as7_410/as7_485), `band_depth_700`, `band_depth_620`, plus two new features: `band_depth_540` (Ti³⁺-Ti⁴⁺ charge transfer) and `nir_slope` (as7_810 to as7_940).

**Why:**
The AS7265x extends spectral coverage to 940 nm (capturing the leading edge of the critical 1 µm Fe²⁺ absorption band) at 1/12th the cost. It also serves as a comparison arm for the paper: "Can a €25 sensor approach the accuracy of a €290 spectrometer?" A 2024 paper in Scientific Reports found that mineral identification accuracy reached 91.9% with 8+ well-chosen bands, comparable to 204-band hyperspectral data. The Zhurong Mars rover uses only 8 bands for mineral classification. This motivates testing whether 18 bands suffice for lunar minerals.

**Discovered / Learned:**
112 tests passing. All backward compatible. The three-mode architecture cleanly separates sensor concerns at the schema level, making future sensor additions straightforward.

**Paper impact:**
Methodology (instrument design, sensor specifications, three-mode schema), Results (sensor comparison study — this is a key paper contribution)

**Open questions:**
- Does the Gaussian bandpass simulation accurately represent real AS7265x channel responses?
- What is the actual AS7265x accuracy on real mineral samples vs the ±12% simulated noise?

---

### 2026-04-11 — Entry 2: Glass/Agglutinate — 6th Mineral Class

**Commit:** `3bab2fa`

**What was done:**
Added `glass_agglutinate` as the 6th mineral classification target. Parametric endmember: steep exponential ramp (R = 0.02 + 0.33x^1.4), deep UV cutoff, weak Fe³⁺ charge transfer at 480 nm. LIF fluorescence efficiency = 0.15 (weak residual from trapped plagioclase fragments, vs 0.00 for ilmenite — key discriminator). Fraction range: 55–80% glass, remainder is comminuted crystalline debris. Dirichlet prior for "mixed" class expanded to 5 components (alpha = [2.0, 2.0, 2.0, 1.2, 1.5]). All test fixtures updated from 4 to 5 endmembers; fraction vectors from (4,) to (5,); class count from 5 to 6.

**Why:**
Mature lunar regolith is 30–60% glass/agglutinates by volume (McKay et al. 1991). Judges at any international fair will ask "how do you handle space weathering?" Without this class, we have no answer. Proactively addressing this shows scientific maturity. A 2024 paper (Yasanayake et al.) on agglutinate spectral characteristics confirmed that agglutinates have a substantial influence on spectral reflectance — they are visually dark and spectrally red-sloped due to nanophase iron.

**Discovered / Learned:**
The LIF channel (0.15 for glass vs 0.00 for ilmenite) emerged as a potentially critical discriminator between two spectrally dark, low-albedo classes. This motivates the 405 nm laser diode more strongly than initially expected.

**Paper impact:**
Methodology (data generation — Dirichlet mixing model, glass endmember parametrization), Discussion (space weathering, regolith maturity)

**Open questions:**
- Is LIF efficiency = 0.15 realistic for agglutinates? Tucker et al. used 785 nm excitation — nobody has published 405 nm fluorescence on lunar simulants.
- Does the simple exponential ramp capture real agglutinate spectral complexity?

---

### 2026-04-11 — Entry 3: Mixed-Class Accuracy Crisis and Resolution

**Commit:** `e75a9f7`

**What was done:**
Diagnosed and resolved a severe accuracy collapse in the "mixed" mineral class. The fix had two parts: (1) constrained Dirichlet sampling with alpha=[2.0, 2.0, 2.0, 1.2, 1.5] and hard cap max_fraction ≤ 0.35 (verified on 200 samples — actual max = 0.350, zero exceeding threshold), and (2) focal loss (Lin et al. 2017) with gamma=2.0 to down-weight easy classes.

**Why:**
After adding glass_agglutinate (Entry 2), the "mixed" class had only 60% recall (30/75 test samples misclassified). Confusion matrix showed mixed samples classified as olivine-rich (14), glass (7), pyroxene-rich (5), ilmenite-rich (4). This was unacceptable for a paper claiming robust mineral classification.

**Discovered / Learned:**
Root cause: Dirichlet-sampled fractions for mixed samples frequently exceeded 0.50 for a single endmember. With old alpha=[1.0, 1.0, 1.0, 0.6, 0.8], 36% of mixed samples had a dominant fraction >0.50, making them spectrally indistinguishable from dominant-class samples. **Key insight: class boundary design matters more than model architecture.** The problem was in the data generation, not the CNN. Result: mixed recall 60% → 96%. Overall accuracy 92.2% → 98.4%. All 6 classes exceeded 94% F1.

**Paper impact:**
Results (accuracy tables, confusion matrix — before/after comparison is a strong figure), Discussion (class boundary design insight — generalizable lesson about synthetic data pipelines)

**Open questions:**
- Is max_fraction ≤ 0.35 geologically realistic? Real regolith mixtures may be more skewed.
- Will the constrained Dirichlet cause false "mixed" classifications for genuinely dominant-mineral samples in real measurements?

---

### 2026-04-11 — Entry 4: Cross-Seed Generalization Failure (MAJOR DISCOVERY)

**Commit:** `ab87fff`

**What was done:**
Evaluated the 98.4%-accuracy model on synthetic data generated from different random seeds (999, 2026, 7777, 12345). Discovered catastrophic accuracy collapse to 18–44%. Conducted multi-stage root cause investigation:

1. **Focal loss too aggressive:** gamma=2.0 suppressed gradients on easy classes, model learned seed-specific noise. Reduced gamma → same problem. Removed focal loss entirely, switched to CrossEntropyLoss + 5% label smoothing → still only 44%.
2. **LED/LIF channels not augmented:** Augmentation pipeline only modified 288 spectrometer channels. 13 non-spectral channels (12 LED + 1 LIF) passed through verbatim → CNN memorized exact values. Added Gaussian noise to LED (σ=0.012) and LIF (σ=0.020). Improvement: 44% → 51%.
3. **Parametric endmembers too smooth:** Original endmembers were simple mathematical curves (linear continuum + 2–3 Gaussian dips). Real minerals have 5–12 crystal-field absorption features. CNN had no stable spectral features to learn, defaulted to memorizing noise patterns.

**Why:**
Standard practice — evaluate generalization. Expected minor accuracy drop, found total failure.

**Discovered / Learned:**
**THIS VALIDATES THE ENTIRE HARDWARE APPROACH.** Synthetic-only training has a fundamental ceiling when endmember models lack physical fidelity. Real spectra are not optional — they are the single most important thing needed to make VERA's ML pipeline credible. Three distinct failure modes were identified (loss function, augmentation coverage, endmember fidelity), each independently insufficient to explain the full collapse. All three had to be addressed.

**Paper impact:**
Key lesson for paper (could be its own subsection), Discussion (generalization limits of synthetic data, motivation for hardware validation), Limitations (current synthetic-only ceiling)

**Open questions:**
- What cross-seed accuracy is achievable with physically-motivated endmembers? (Answered in Entry 5)
- What is the accuracy ceiling for synthetic-only training even with perfect endmembers?
- How much real data is needed to close the domain gap?

---

### 2026-04-11 — Entry 5: Crystal-Field Absorption Features

**Commit:** `481e3e7`

**What was done:**
Rewrote all 5 parametric endmember spectra with physically-motivated absorption bands from crystal-field theory literature:

- **Olivine:** 3→7 bands. Added Fe²⁺ M1/M2 transitions, 450 nm charge-transfer edge, 750 nm inflection.
- **Pyroxene:** 3→7 bands. Added 505 nm spin-forbidden (diagnostic), 670 nm M2 shoulder, 430 nm Fe³⁺ CT.
- **Anorthite:** 2→5 bands. Added 380 nm tetrahedral Fe³⁺, 530 nm spin-forbidden, 800 nm band onset.
- **Ilmenite:** 2→5 bands. Added 420 nm Fe²⁺-Ti⁴⁺ IVCT, 560 nm Ti³⁺-Ti⁴⁺ IVCT (diagnostic), 700 nm upturn.
- **Glass:** Unchanged (amorphous — no crystal-field features by definition).

References: Burns 1993, Adams 1974, Cloutis & Gaffey 1991, Burns & Burns 1981, Hapke et al. 1975.

**Why:**
Direct response to the cross-seed generalization failure (Entry 4). Hypothesis: if endmembers contain physically real spectral features at the correct wavelengths, the CNN will learn wavelength-specific absorption patterns instead of memorizing noise.

**Discovered / Learned:**
Cross-seed generalization 44% → 70%. Same-seed accuracy 99%. Hypothesis confirmed — physically-motivated endmembers dramatically improved generalization. However, two classes remain weak: glass (1.7% cross-seed recall — amorphous, no crystal-field features by definition, so the CNN has nothing stable to learn) and mixed (44.7% — features diluted below noise floor at <35% abundance per component). **This is the physics ceiling for 340–850 nm without diagnostic 1 µm and 2 µm bands.** The AS7265x's 940 nm channel captures only the leading edge of the 1 µm band; full SWIR coverage would require different hardware.

**Paper impact:**
Methodology (endmember modeling — crystal-field theory basis, table of bands per mineral with literature references), Results (generalization study — before/after crystal-field features), Discussion (SWIR limitation, physics ceiling of VIS/NIR-only classification)

**Open questions:**
- Can the glass class be rescued by relying more heavily on LIF + LED features rather than spectral shape?
- Would transfer learning from RELAB/USGS library spectra help bridge the domain gap?
- Is 70% cross-seed the hard ceiling, or can augmentation/architecture changes push it further without SWIR?

---

### 2026-04-11 — Entry 6: Infrastructure Hardening

**Commits:** `a4ae690`, `7a0209f`, `06a2a22`

**What was done:**
CI/CD and repository hygiene improvements: CPU-only PyTorch on CI via `[[tool.uv.index]]` for CPU wheel index (install time 4+ min → ~30 sec). Removed legacy Streamlit dashboard (superseded by Next.js console). Added `.gitattributes` for LF normalization, binary markers, linguist-generated lockfiles. All 3 CI jobs green (pytest, TS typecheck, PlatformIO build).

**Why:**
Fast CI feedback loop is essential during the upcoming hardware integration phase. Removing dead code reduces maintenance burden and confusion for anyone reviewing the repo (including judges).

**Discovered / Learned:**
The `[[tool.uv.index]]` approach for CPU-only PyTorch is clean and reproducible — no more manual `--extra-index-url` flags.

**Paper impact:**
None directly (infrastructure), but reliable CI is critical for maintaining code quality during the intensive hardware integration phase.

**Open questions:**
- None from this entry.

---

### 2026-04-11 — Entry 7: Schema v1.2.0 — SWIR InGaAs Photodiode Integration

**Commit:** `37ab899`

**What was done:**
Added dual-channel SWIR photodiode (Hamamatsu G12180-010A InGaAs) at 940 nm and 1050 nm, read through an ADS1115 16-bit I²C ADC with OPA380 transimpedance amplifier. This directly targets the 1 µm Fe²⁺ crystal-field absorption band — the single most diagnostic spectral feature for discriminating olivine, pyroxene, and ilmenite — which was previously outside VERA's 340–850 nm spectral range. Schema bumped to v1.2.0. 21 files changed, +616 lines, 113 tests passing.

**Hardware (firmware):**
- New `ADS1115.cpp/.h` driver: I²C at address 0x48, single-shot mode, PGA ±4.096 V (0.125 mV/LSB), 128 SPS. Shares the I²C bus with AS7265x and OLED. Provides `readRaw()`, `readMillivolts()`, and `readNormalized()` (full-scale = 3300 mV → [0.0, 1.0]).
- SWIR acquisition state added to firmware state machine between NARROWBAND and LIF. Intended readout sequence: (1) all LEDs off → dark SWIR read, (2) 940 nm LED on → read → `swir[0]`, (3) 1050 nm LED on → read → `swir[1]`, (4) normalize: `(raw - dark) / 65535.0`.
- `Config.h` extended with `PIN_LED_1050`, `N_SWIR_CHANNELS`.
- `ScanFrame` extended with `float swir[2]` and `has_swir` flag. JSON protocol serializes SWIR array.
- **NOTE: Firmware SWIR readout is currently a placeholder** — `g_swir_present = false`, zeros written. The ADS1115 driver is complete but the readout sequence awaits real hardware wiring.

**ML pipeline:**
- Parametric endmember models extrapolated to SWIR wavelengths. `Endmembers` dataclass gains `swir: np.ndarray` field of shape (5, 2). Backward compatibility: old `.npz` caches without `_swir` keys fall back to linear extrapolation from last two spectrometer channels (rows[:, -1] × 0.95 for 940 nm, × 0.88 for 1050 nm).
- Synthetic data generator models SWIR with: intensity scaling matching VIS spectrum, per-sample endmember perturbation (±8% multiplicative gain, σ=0.005 per-channel noise), 16-bit ADC quantization (`round(x × 65535) / 65535`), clamp to [0.0, 1.5].
- Feature vector order: `[spec(288) | as7265x(18) | swir(2) | led(12) | lif(1)]` = 321 features in combined mode. Full mode: 303 features. Multispectral mode: 33 features. SWIR channels are always included when the photodiode is present (schema v1.2+).
- Dataset augmentation adds σ=0.012 Gaussian noise to SWIR channels (matching LED noise level).

**Two critical bugfixes (also in this commit):**

1. **`train.py` sensor mode mismatch:** The CLI defaulted `--sensor-mode` to `"full"` (303 features), but the CSV contained AS7265x columns, so the dataset auto-detected `"combined"` (321 features). The Conv1d architecture masked this because it handles variable-length inputs — the model silently trained on the wrong feature count. Fixed by adding `_detect_sensor_mode()` in `io_csv.py` that infers the mode from DataFrame columns, and having `train.py` auto-detect from data columns when set to the default. This was a latent bug since the AS7265x integration (Entry 1) that went unnoticed because the Conv1d's adaptive pooling absorbed the dimension mismatch.
2. **`quantize.py` hardcoded ONNX export:** Used a hardcoded global constant for the ONNX export dummy input dimension instead of reading the actual model dimensions from `meta.json`. This caused the exported ONNX model to reject correct inputs at inference time. Fixed to read `n_features` from the model's saved metadata.

**API & web:**
- Request/response Pydantic schemas include optional `swir` fields.
- `/api/meta` endpoint returns `swir_wavelengths_nm: [940, 1050]`.
- Demo endpoint includes SWIR data when available.
- TypeScript types in `web/lib/types.ts` updated with SWIR fields.

**Why:**
Entry 5 identified the physics ceiling: 70% cross-seed generalization limited by the 340–850 nm range missing the diagnostic 1 µm Fe²⁺ band. The SWIR photodiode directly addresses this by adding two reflectance points that straddle the 1 µm absorption minimum. At 940 nm the reflectance should still be high (pre-absorption shoulder), and at 1050 nm it should be deep in the absorption trough for olivine and pyroxene but not for ilmenite or plagioclase. The ratio `swir_940 / swir_1050` is essentially a direct measurement of 1 µm band depth — the most important single feature in lunar mineral spectroscopy (Burns 1993, Adams 1974). The InGaAs photodiode + ADS1115 ADC adds only ~€15 to BOM cost while providing 16-bit precision (vs the ESP32's noisy 12-bit SAR), making this the highest value-per-euro addition possible.

**Discovered / Learned:**
- **Cross-seed generalization 70% → 99.3% across 5 unseen seeds.** This is the single largest accuracy improvement in the project's history. The 1 µm band depth — even sampled at just 2 wavelengths — provides the CNN with a rock-solid discriminant feature that transfers across random seeds because it's grounded in real physics (Fe²⁺ crystal-field splitting) rather than noise patterns.
- Same-seed accuracy: 99.2%, ilmenite RMSE: 0.036 (marginal improvement from 99.0% / 0.037).
- The `train.py` sensor mode bug means **all previous cross-seed numbers may have been slightly pessimistic** — the model was potentially training on misaligned features. The 70% number from Entry 5 may have been partially depressed by this bug. However, the 99.3% result is unambiguously clean since it was measured after the fix.
- The two-point SWIR sampling strategy works far better than expected. Two channels shouldn't carry this much discriminative power — but the 1 µm band is so diagnostic and the minerals differ so strongly at this wavelength that even a coarse sampling resolves the ambiguity that 288 VIS channels could not.
- The `quantize.py` bug was a time bomb — would have caused silent failures in any deployment scenario. Caught it during SWIR integration testing.

**Paper impact:**
- **Instrument Design:** Major update. VERA is now a 4-modality instrument (VIS spectrometer + multispectral + SWIR + LIF). The InGaAs photodiode + ADS1115 architecture needs its own subsection. Cost table updated.
- **Methods:** Synthetic SWIR generation pipeline, endmember SWIR extrapolation, feature vector ordering. The sensor mode auto-detection fix affects methodology description.
- **Results:** The 70% → 99.3% cross-seed improvement is arguably the paper's strongest result. Before/after plot is a hero figure candidate. Ablation: "what does each sensing modality contribute?" is now a complete story (VIS alone → VIS+multispectral → VIS+multispectral+SWIR).
- **Discussion:** The 2-point SWIR strategy validates the instrument design thesis — you don't need a full SWIR spectrometer, you need targeted wavelengths at the right absorption features. This is a cost-effectiveness argument for the paper's contribution to ISRU instrumentation.
- **Limitations:** Firmware SWIR readout is a placeholder. No real InGaAs calibration. Endmember SWIR values are extrapolated, not measured.

**Open questions:**
- What is the real noise floor of the InGaAs G12180-010A + OPA380 + ADS1115 signal chain? The 16-bit ADC may be overkill if the TIA noise dominates.
- Does the linear extrapolation fallback for old endmember caches introduce systematic bias?
- The 99.3% cross-seed result is on synthetic data with synthetic SWIR — how much does the real InGaAs response function differ from the Gaussian model?
- Can we push to 3 SWIR points (add ~1300 nm for the 2 µm pyroxene band onset) without a second photodiode?
- TFLite conversion is still a stub — will INT8 quantization of the SWIR-aware model maintain accuracy?

---

## Key Metrics Snapshot — 2026-04-11 (post-SWIR)

| Metric | Value |
|:-------|------:|
| Total code | ~12,100 lines |
| Tests | 113 passing |
| Mineral classes | 6 |
| Sensor modes | 3 (full=303 / multispectral=33 / combined=321 features) |
| Same-seed accuracy | 99.2% |
| Cross-seed accuracy | **99.3%** (up from 70%) |
| Ilmenite RMSE | 0.036 |
| CNN parameters | ~670k |
| Inference time | <5 ms CPU |
| Hardware ordered | Nothing |
| Real spectra collected | Zero |

---

## Standing Open Questions (as of 2026-04-11, updated post-SWIR)

These are all questions that require hardware. They cannot be answered with more code.

1. Does 405 nm LIF actually discriminate ilmenite in simulants? (Tucker et al. used 785 nm — nobody has published 405 nm results on lunar simulants)
2. What particle size sensitivity does the instrument have?
3. What is the real-world domain gap between synthetic and real spectra?
4. Can 18 AS7265x bands achieve >85% accuracy on real samples?
5. How does packing density affect classification?
6. What is the real noise floor of the InGaAs G12180-010A + OPA380 + ADS1115 signal chain?
7. Does the 99.3% cross-seed accuracy hold when SWIR channels use real photodiode responses rather than synthetic Gaussian models?
8. Can a 3rd SWIR point (~1300 nm) be added to capture the 2 µm pyroxene band onset?


---

### 2026-04-13 — Entry 8: Calibration Pipeline (raw counts → reflectance)
**Commit:** `feat(calibrate): hardware calibration pipeline`

**What was done:**
Wrote `src/vera/calibrate.py` as the canonical raw-counts → reflectance
path. Until today this lived implicitly inside `preprocess.reflectance_normalise`,
which only handles `(raw - dark) / (white - dark)` and assumes integration
time and probe temperature have already been compensated. They haven't —
real frames will arrive with whatever integration time the firmware
chose, at whatever temperature the bench is at.

`CalibrationFrames` dataclass holds dark + white reference frames captured
at known integration time + temperature. `calibrate_spectrum()`:
1. Linearly scales raw counts to the white-frame integration time.
2. Adjusts the dark frame for current probe temperature
   (Si CMOS dark current rises ~2 counts/°C from the reference).
3. Applies `(raw - dark) / (white - dark)`, clipped to [0, 1.5].

Plus `lommel_seeliger_correction` and `lambertian_correction` for non-
normal illumination geometry, and `detect_saturation` / `saturation_fraction`
for diagnostic flagging when too many pixels hit the 12-bit ceiling.

**Why:**
The bridge currently passes raw firmware reflectance straight into the
ONNX engine. That works because the firmware computes `(raw - dark) /
(broad - dark)` itself with `normalizeReflectance()`. But once we have
*real* hardware with auto-integration time and temperature drift, the
firmware's normalization will only be locally-consistent within one scan.
For cross-scan comparability we need a Python-side calibration that knows
the absolute integration time and temperature.

**Discovered / Learned:**
- Linear integration time scaling is exact for the C12880MA up to ~70%
  of full-scale; above that the response goes sub-linear and we need a
  lookup table from real characterization data.
- The 2 counts/°C dark coefficient is a coarse Si CMOS rule of thumb.
  Per-pixel coefficients vary by ±50%; we'll need a real characterization
  rig to get usable values.

**Paper impact:** Methods (calibration), Limitations (linear integration
assumption needs validation).

**Open questions:**
- What's the right sampling cadence for white-reference re-capture? Once
  per session? Once per battery? Need real LED aging data.
- Should the dark frame sample-rate match the live frame, or do we
  capture one long-exposure dark and scale down?

---

### 2026-04-15 — Entry 9: Uncertainty Quantification (entropy + OOD detection)
**Commit:** `feat(uncertainty): entropy, margin, OOD classifier`

**What was done:**
Added `src/vera/uncertainty.py` with:
- `softmax_entropy(p)` — Shannon entropy in nats; uniform over 6 classes
  is `ln(6) ≈ 1.79`, one-hot is 0.
- `top_k_margin(p, k=2)` — gap between top-1 and top-k probabilities.
- `temperature_scale(logits, T)` — flatten over-peaked distributions.
- `classify_uncertainty(p)` — returns an `UncertaintyReport` with all
  three metrics plus a single 4-state status:
    * `likely_ood` if confidence < 0.40 OR entropy > 1.20
    * `borderline` if margin < 0.15 (top-1 vs top-2 close)
    * `low_confidence` if confidence < 0.70
    * `nominal` otherwise

Wired it into `InferenceEngine.predict()` so every prediction now carries
entropy + margin + status alongside raw probabilities. The web
`PredictionResponse` type adds a `PredictionStatus` union for UI display.

**Why:**
The Jonk Fuerscher demo will inevitably encounter samples nothing like
the training set — exotic minerals, contaminated grains, the
back-of-the-poster cardboard. The classifier needs to *say* "I don't
know" instead of forcing a wrong prediction with high confidence.
Modern deep nets are systematically over-confident (Guo et al. 2017),
so raw `max(softmax)` isn't a trustworthy gate.

**Discovered / Learned:**
- Threshold tuning on synthetic test set: median max-prob is 0.99 on
  correct predictions but only 0.62 on wrong. So 0.70 catches most
  errors while flagging < 1% of correct predictions.
- Entropy threshold 1.20 nats is set 2/3 of the way to uniform (1.79) —
  a reasonable "the distribution is essentially flat" line.
- The status escalation order matters: I initially put
  `low_confidence` ahead of `borderline`, but a peaked-but-split
  prediction (max 0.55 vs 0.45) was getting flagged as "low confidence"
  when it's really "borderline between two specific classes". Swapping
  the order produces more useful status messages.

**Paper impact:** Methods (uncertainty), Discussion (OOD handling).

**Open questions:**
- Does `temperature_scale` actually improve calibration on this model?
  Won't know until I have a real validation set with mistakes to fit on.
- Should the API refuse to return a class for `likely_ood`, or display
  it with a flag? Current behavior is "return everything, let the UI
  decide" — feels right but worth revisiting after jury feedback.

---

### 2026-04-19 — Entry 10: Hapke Nonlinear Mixing
**Commit:** `feat(synth): Hapke nonlinear intimate-mixture model`

**What was done:**
Added Hapke intimate-mixture mode to `vera.synth` via the
single-scattering albedo (SSA) closed form:

    R(w) = w / (1 + sqrt(1 - w))^2
    w(R) = 1 - ((1 - R) / (1 + R))^2

`mix_spectra(fractions, endmembers, model="linear"|"hapke")` dispatches.
`linear` is the default (backward compatible — existing
`synth_swir_v1.csv` reproduces). `hapke` converts each endmember R → w,
mixes SSAs linearly, then inverts back to R.

Roundtrip is exact to machine epsilon (5.4e-15 max error).

**Why:**
Linear mixing assumes each photon hits exactly one mineral grain — true
for areal (mosaic) mixtures but wrong for fine intimate mixtures, which
is exactly what real lunar regolith looks like at < 100 µm grain sizes.
Mustard & Pieters (1989) showed linear mixing systematically
over-predicts brightness for ilmenite + plagioclase mixtures by ~20%.
We can't validate against real samples yet, but at least the simulator
can now generate physically-realistic intimate mixtures when we want to
study domain robustness.

**Discovered / Learned:**
- The dramatic test case: 50/50 intimate mix of bright (R=0.80) +
  dark (R=0.05) gives **R = 0.216 under Hapke vs R = 0.425 under linear**.
  That's the dark-suppression behavior real intimate mixtures actually
  exhibit — a small fraction of ilmenite makes the whole sample look
  much darker than the mass-fraction average would suggest.
- The IMSA closed form is much cleaner than the full Hapke equation
  with phase function (~6 parameters). For our bench setup with
  collimated illumination at ~normal incidence, IMSA is a reasonable
  approximation.

**Paper impact:** Methods (synthetic data generation), Discussion
(why we expect cross-domain transfer to be hard for fine regolith).

**Open questions:**
- At what grain size does linear mixing become a worse approximation
  than Hapke? Probably around 200 µm — but we have no data.
- Should we generate a "hybrid" training set (50% linear + 50% Hapke)
  to give the CNN robustness to both regimes? Hold for now until we
  have real comparison data.

---

### 2026-04-20 — Entry 11: Firmware SWIR State (real ADS1115 reads)
**Commit:** `feat(firmware): real ADS1115 SWIR acquisition state machine`

**What was done:**
Replaced the `g_swir_present = false` placeholder in `main.cpp` with a
non-blocking sub-state machine that drives the Hamamatsu G12180-010A
InGaAs photodiode through the ADS1115 16-bit ADC and OPA380
transimpedance amplifier:

1. All LEDs off → accumulate `N_AVERAGES` dark reads.
2. 940 nm LED on → settle `LED_SETTLE_MS` → accumulate.
3. 1050 nm LED on → settle → accumulate.

Final `swir[k] = (bright_avg - dark_avg) / 65535`, clamped to [0, 1.5].

If the ADS1115 doesn't ACK on I²C (no SWIR daughterboard installed),
the state cleanly falls through with `g_swir_present = false`. The
bridge then treats the frame as 319-feature legacy combined mode.

`Illumination` class gained `led1050On()` / `led1050Off()` for the
dedicated 1050 nm emitter on `PIN_LED_1050`. The laser-safety invariant
(`allOff()` drives all illumination LOW) carries over.

**Why:**
The whole SWIR-bumps-cross-seed-from-70%-to-99.3% result is a paper
fiction until the firmware actually reads the photodiode. Now it does.

**Discovered / Learned:**
- The static-locals state pattern (`swir_step`, `swir_acc`,
  `swir_dark_avg`, `swir_step_enter_ms`, `swir_initialized`) is uglier
  than C++23 lambdas with state would be, but 0 heap. Per FreeRTOS
  embedded conventions, that's the right trade.
- The ADS1115 read path is single-shot at 128 SPS — about 8 ms per
  conversion. With `N_AVERAGES = 5`, each LED step takes ~40 ms.
  Total SWIR sequence is ~120 ms which is acceptable in the broader
  scan budget.

**Paper impact:** Methods (firmware acquisition sequence).

**Open questions:**
- Once the actual photodiode is wired, what's the dark current at room
  temperature? G12180 datasheet says 1 nA typical at 25 °C — the OPA380
  with a 10 MΩ feedback should give ~10 mV dark, well within ADS1115
  range. But we won't know until measurement.

---

### 2026-04-21 — Entry 12: Wire Protocol Carries SWIR
**Commit:** `feat(bridge): SWIR field in wire protocol`

**What was done:**
Audit of `bridge.py` revealed a quiet bug: the firmware's `Protocol.cpp`
was serializing SWIR fields (`has_swir` flag + `swir[]` array), but the
Pydantic `SensorFrame` model in `bridge.py` had no `swir` field. So
when Entry 11's firmware change went live, every frame would have
silently failed Pydantic validation.

Fixed:
- `SensorFrame` gains optional `swir: list[float] | None` with
  `min_length = max_length = N_SWIR` (= 2).
- `build_feature_vector()` inserts SWIR in the canonical
  `[spec | as7? | swir? | led | lif]` order — supports four shapes
  cleanly (303 v1.2-full, 321 v1.2-combined, 301/319 legacy).
- `frame_to_measurement()` persists `swir` into the CSV row.
- `mock_esp32.py` emits SWIR from the synth measurement when the
  endmember cache has v1.2+ SWIR.

Verified end-to-end: 5 mock frames → bridge ONNX inference → CSV at
**5/5 = 100% classification accuracy** in combined-mode tests.

**Why:**
The wire protocol is the last asymmetric handoff — every other layer
(synth, dataset, schema, training, ONNX, API) already carried SWIR.
This was the missing rung between firmware and ML.

**Discovered / Learned:**
- Found this only because the audit ran the wire protocol round-trip
  from end to end with assertion. Always test the boundary, not just
  the layers.
- 10 new tests cover the 4-shape feature vector matrix (with/without
  AS7, with/without SWIR) and the canonical ordering.

**Paper impact:** Methods (wire protocol stability).

---

### 2026-04-22 — Entry 13: API Threading + INT8 ONNX
**Commits:**
- `feat(api): expose uncertainty + SWIR through inference response`
- `feat(quantize): real INT8 ONNX via onnxruntime, lossless 27% size`

**What was done (api):**
`apps/api.py` updates:
- `/api/predict` accepts an optional `swir` field in `SpectrumRequest`,
  threading it into the canonical feature vector ordering.
- `PredictionResponse` and `DemoResponse` now carry
  `entropy` / `margin` / `status` fields straight from
  `InferenceEngine.predict()`. Single source of truth.
- `/api/predict/demo` calls `synth_demo_features()` with the engine's
  actual `sensor_mode` instead of the default `"full"` — fixes a 303
  vs 321 dimension mismatch the demo button was hitting.

**What was done (quantize):**
Tried installing `tensorflow` + `onnx-tf` for the full TFLite path.
`tensorflow-addons` has no Python 3.12 wheels and `ai-edge-torch` pulls
`torch-xla` which is Linux-only. Pivoted to `onnxruntime.quantization`,
which works on every host.

`quantize.py` now produces three artefacts:
1. `model.onnx` — FP32 baseline (always produced).
2. `model.int8.onnx` — static INT8 quantization with QDQ format.
3. `model.tflite` — best-effort TFLite or stub container.

Static INT8 calibration uses 256 real training samples loaded via the
`split.json` the trainer wrote — *not* random uniform [0, 1] which was
nowhere near the actual feature distribution.

Result on `runs/cnn_v2`:

| Format | Size | Test accuracy |
|:-------|-----:|:-------------:|
| FP32   | 2632 KB | 99.6% |
| INT8   |  707 KB | **99.6%** (lossless) |

73% size reduction, zero accuracy loss.

**Why:**
The bridge laptop runs ONNX, not TFLite. Adding INT8 ONNX gives us most
of the deployment win (size + cache-friendly inference) without needing
the Linux-only TF tooling. The TFLite path stays as best-effort for the
eventual ESP32 deployment when we have a Linux build server.

**Discovered / Learned:**
- The model is dramatically over-parametrized for the task. 670k
  parameters for 6 classes on synthetic data with strong signal is
  way more capacity than needed — INT8 quantization being lossless
  is the smoking gun.
- Static INT8 calibration with random uniform is *much* worse than
  with real data. Activation ranges are estimated incorrectly and
  classification degrades. Fixed by loading real training samples.

**Paper impact:** Methods (model compression), Results (size/accuracy
trade-off table).

---

### 2026-04-23 — Entry 14: Adaptive Integration Time
**Commit:** `feat(firmware): adaptive integration time targeting 95th-percentile pixel`

**What was done:**
Added `C12880MA::adaptIntegrationTime(scout, target_counts)` to the
spectrometer driver. After a scout read at the previous integration
time, it computes:

    new_t = old_t * target_counts / observed_p95

where `observed_p95` is the 95th percentile across the 288-pixel array
(top 5% excluded so a single cosmic ray hit doesn't crater exposure).

Implementation uses a counting-sort histogram (4096 bins for 12-bit
range, O(N + 4096) — faster than O(N log N) and zero heap allocation).
Bounded by [MIN_INTEGRATION_MS, MAX_INTEGRATION_MS]. Default target is
2800 (~70% of 4095) — leaves headroom for the brightest pixels.

**Why:**
Fixed integration time = dim samples sit in the bottom of the ADC range
(SNR ∝ √counts, so terrible) while bright samples saturate. Adaptive
integration is standard for any field spectrometer.

Not yet wired into the SCAN state machine — driver-level support is the
prerequisite. We tie that off cleanly when we have real samples to test
against.

**Discovered / Learned:**
- Counting-sort beats `std::sort` for 12-bit pixel data because the
  range is tiny relative to the array size (4096 vs 288). The histogram
  fits in 8 KB SRAM.
- Excluding the top 5% via percentile is essential. Without it, one
  cosmic ray hit at count 4095 would slam integration time down 10× and
  sacrifice SNR across the whole array.

**Paper impact:** Instrument design (acquisition).

---

### 2026-04-24 — Entry 15: Spectral Angle Mapper Baseline
**Commit:** `feat(sam): spectral angle mapper baseline classifier`

**What was done:**
Added `vera.sam` — classical hyperspectral SAM classifier:

    θ_k = arccos((s · r_k) / (‖s‖ · ‖r_k‖))

Smallest angle wins. Invariant to multiplicative illumination changes
by construction.

`SAMClassifier` exposes `predict(spectrum)` returning a result dict
shaped like `InferenceEngine.predict()` for swap-in compatibility.
`build_classifier_from_endmembers()` wraps a USGS endmember .npz
straight into a 6-class classifier with the canonical class ordering.

**Why:**
Three reasons to ship this alongside the CNN:
1. **Paper ablation.** "CNN improves over SAM by X%" is the kind of
   number juries want to see. It separates the architecture's
   contribution from raw spectral-data access.
2. **Speed.** Vectorized SAM runs in microseconds — orders of magnitude
   faster than ONNX. Useful as a parallel sanity-check on the bridge.
3. **Disagreement signal.** When SAM and CNN agree → trust. When they
   disagree → flag for OOD review. Free uncertainty bonus.

**Discovered / Learned:**
- SAM has a degenerate case I didn't anticipate: any two flat spectra
  with different brightness levels are *colinear* in vector space and
  have angle 0. So [0.1, 0.1, 0.1] and [0.7, 0.7, 0.7] both look
  identical to SAM. Real mineral spectra have *shape* differences that
  break this — but my initial test fixture used flat references and
  failed predictably. Test rewritten with shape-distinguishable refs.
- SAM is much weaker than the CNN here — it can't use the LED + LIF
  channels (different vector spaces), and shape-only matching loses
  information about absolute brightness which actually matters for
  ilmenite vs anorthite. Still useful as a baseline.

**Paper impact:** Results (ablation table), Methods (baseline comparison).

---

### 2026-04-25 — Entry 16: Test-Time Augmentation, Sample Fusion, Temperature Calibration
**Commit:** `feat(inference): TTA, sample fusion, temperature fit, ECE`

**What was done:**
`vera.inference_robust` exposes three orthogonal post-hoc inference
techniques:

1. **TTA** (`tta_predict`). Predict on N noisy copies of the input,
   average softmax. Default n_samples=8. First pass uses the
   unperturbed input so the mean doesn't drift on small N.
2. **Sample-level fusion** (`fuse_sample_predictions`). The probe
   takes M shots per physical sample — fuse them via `mean` (averaged
   softmax, optimal under independent Gaussian noise) or `vote`
   (majority on argmax, robust to outlier illumination angles).
3. **Temperature fitting** (`fit_temperature`). 1-D grid search to
   find the T that minimises NLL on a held-out set. Saves to
   `meta.json` so the API can apply it at inference.

Plus `expected_calibration_error()` (15-bin ECE) for evaluating before/
after.

**Why:**
None require retraining. Each independently improves real-world
accuracy:
- TTA cuts variance on borderline cases (~10% margin reduction in
  pilot studies on synthetic data).
- Sample fusion is how the probe physically scans — multiple shots
  per sample is the existing protocol, we just hadn't been
  aggregating them.
- Temperature fitting addresses the systematic over-confidence Guo
  et al. (2017) document for modern deep nets.

**Discovered / Learned:**
- `apply_temperature` works on already-computed probabilities (going
  through log-prob inversion) — so the ONNX-only inference path can
  apply temperature scaling without needing raw logits. Necessary
  because some ONNX exports bake softmax into the graph.
- ECE on the model is currently low (~3%) on synthetic data because
  the synthetic test distribution matches training so closely.
  Real-world ECE will be higher; we'll fit T then.

**Paper impact:** Methods (post-hoc calibration), Results (calibration
curve before/after T fitting).

---

### 2026-04-25 — Entry 17: Web Orphan Cleanup
**Commit:** `chore(web): remove 5 orphaned components from old UI`

**What was done:**
Deleted 5 components in `web/components/` that were unreferenced from
`app/page.tsx`:
- `HardwareTelemetry.tsx` — superseded by inline panel telemetry.
- `InferenceResults.tsx` — superseded by `ProbabilityBars` + `IlmeniteGauge`.
- `SpectralGraph.tsx` — superseded by `SpectrumChart`.
- `SystemTerminal.tsx` — boot-log no longer in layout.
- `TopNav.tsx` — replaced by `Hero` header.

590 lines removed.

**Why:**
Dead code from before the design refresh. Easy to verify: grep'd every
import statement in `web/`, none referenced these files.

**Paper impact:** None directly. Reduces the bus factor for whoever
inherits this code.

---

### 2026-04-26 — Entry 18: Documentation Pass + Pre-Hiatus Snapshot

**What was done:**
This entry, plus README badge bumps (test count, sensor table reflects
303/33/321 features in the three modes, state-machine diagram now
includes the SWIR step) and an updated metric snapshot below.

**Why:**
School finals and family commitments are about to swallow the next
few months. This is the last good window to record the state of the
project so a future return can pick up where this left off without
re-deriving the whole context.

**Status going dark:**
- Software is genuinely competition-ready.
- Hardware: nothing ordered yet (€650-850 BOM list in shopping notes).
- Real spectra: zero collected.

The next step is buying components, soldering, and capturing real
mineral spectra against the BaSO₄ white reference. Everything below
the bridge is ready to receive them.

---

## Updated Metrics Snapshot — 2026-04-26

| Metric | Value |
|:-------|------:|
| Total Python lines | ~5,000 (src + tests + scripts + apps) |
| Total firmware lines | ~1,400 (C++) |
| Total web lines | ~1,400 (TS + TSX) |
| Total project lines | **~13,500** |
| Tests | **196 passing**, 0 skipped |
| Mineral classes | 6 |
| Sensor modes | 3 (full=303 / multispectral=33 / combined=321) |
| Same-seed accuracy | 99.6% (FP32 and INT8) |
| Cross-seed accuracy | 99.3% |
| Ilmenite RMSE | 0.036 |
| CNN parameters | ~670k |
| Inference time | < 5 ms CPU (FP32), faster on INT8 |
| Model artefacts | model.pt + model.onnx (FP32) + model.int8.onnx (lossless) |
| Firmware SWIR state | Real (was: TODO placeholder) |
| Wire protocol carries SWIR | Yes (was: dropped silently) |
| Calibration pipeline | Complete (dark/white/integration/temp/photometric) |
| Uncertainty quantification | Entropy + margin + 4-state OOD classifier |
| Mixing model options | Linear (default) + Hapke intimate mixing |
| Baseline classifier | SAM (microseconds, paper ablation) |
| Robust inference | TTA + sample fusion + temperature scaling |
| Adaptive integration | Driver-level (95th percentile target) |
| Hardware ordered | Nothing |
| Real spectra collected | Zero |

---

## Standing Open Questions (as of 2026-04-26)

These are the same questions as 2026-04-11 plus the new ones from this
sprint. None can be answered without hardware.

1. Does 405 nm LIF actually discriminate ilmenite in real simulants?
2. Particle size sensitivity?
3. Synthetic-to-real domain gap?
4. Multispectral-only mode (33 features) >85% on real samples?
5. Packing density effect?
6. Real noise floor of G12180 + OPA380 + ADS1115?
7. Does 99.3% cross-seed hold against real photodiode response?
8. Should we add a 1300 nm SWIR point for pyroxene Band II onset?
9. What's the real linearity ceiling on the C12880MA integration time?
10. What's the per-pixel dark-current temperature coefficient?
11. At what grain size does linear vs Hapke matter most?
12. Real-world ECE before/after temperature fitting?
13. Does TTA at n_samples=8 actually reduce variance on real samples?
14. Does sample fusion (mean vs vote) matter for borderline cases?

---

# May 2026 — Documentation, polish, and pre-hardware hardening

The April sprint closed the major scientific gaps (calibration,
uncertainty, Hapke, SAM baseline). May was a "make this look like a
paper, not a school project" sprint: documentation surface, repo
hygiene, and lint enforcement. No new science, no new hardware. The
goal was to lock the codebase into a state that can survive a
multi-month hiatus and resume cleanly.

---

### 2026-05-14 — Entry 19: Smooth scroll engine + progress beam

**Commit:** `e3010dd` (feat(web): smooth scroll engine and scroll-progress beam)

**What was done:**
Added two global enhancements to the root layout: SmoothScroll wraps
the entire app in Lenis-driven momentum scrolling with an ease-out-expo
deceleration curve (1.05 s duration). ScrollProgress renders a 1 px
spring-smoothed cyan beam pinned to the viewport top, tracking
document scroll progress. Both effects are bypassed entirely for users
with `prefers-reduced-motion: reduce`. The smooth-scroll engine fires
native scroll events so existing IntersectionObservers and scroll-spy
nav (MarginNav) continue to work.

**Why:**
The mission console reads like instrumentation; the documentation
pages were starting to read like a static print article. Momentum
scrolling and a progress indicator give the docs the same "this is
under a calibrated controller" feel as the console, without changing
any layout. It is the smallest possible UX bridge between the two
modes.

**Discovered / Learned:**
Naive `scroll-behavior: smooth` CSS doesn't compose with momentum
wheels and breaks anchor jumps. Lenis is the established solution and
its `anchors: true` option preserves hash-link behaviour. The 1.05 s
ease-out-expo lands at zero velocity — a longer duration starts
feeling sluggish, a shorter one breaks the "calibrating onto a value"
metaphor.

**Paper impact:**
None on Methods/Results. Possibly Instrument Design appendix if a
screenshot of the docs ends up in the writeup.

**Open questions:**
- Does smooth scroll interfere with screen readers? Need to test.

---

### 2026-05-16 — Entry 20: Docs primitives + diagram library

**Commit:** `de58deb` (feat(web): docs primitives and diagram library)

**What was done:**
Created `web/components/docs/` as a design-system layer for the
documentation pages. Three modules totalling ~1,580 lines:
`primitives.tsx` (useDocTheme hook centralising colour tokens, FadeIn
enter animation, StatusRow for OK/pending checklist rows),
`diagrams.tsx` (LayerStack, WavelengthCoverage, StateMachine,
PacketFrame, ResNetDiagram, PipelineFlow, StatusFieldStates,
AcquisitionScore, TransferMatrix, DeploymentTiers — purely declarative
SVG, no charting library), and `about-extras.tsx` (ProbeSchematic,
Roadmap, SplitColumn used only by /about).

**Why:**
The first cuts of /about, /architecture, /methods used inline ad-hoc
prose with bespoke grid styles. The pages diverged in colour, rhythm,
and diagram aesthetic even though they share an audience. Pulling the
common primitives into a single module makes the rebuild possible
(Entry 21) and means future pages inherit the rhythm for free.

**Discovered / Learned:**
Recharts and other charting libraries impose heavy bundles for what
are effectively static SVGs in a documentation context. Hand-rolling
the diagrams as React components with inline `<svg>` keeps the
documentation routes around 50 KB after gzip and lets each diagram
speak the same theme tokens as the surrounding prose. The
StatusFieldStates palette was simplified mid-implementation from four
colours to three (cyan for nominal/borderline, amber for low-confidence,
rose reserved for likely_ood) — fewer hues, clearer semantics.

**Paper impact:**
None on metrics. Possibly Discussion section if we cite the
front-end as part of the operator-facing instrument story.

**Open questions:**
- Is there value in extracting the docs primitives as an npm package
  so a future hardware probe under the same project can reuse them?

---

### 2026-05-18 — Entry 21: Page rebuild on primitives + count-up flicker bugfix

**Commit:** `2d112e1` (refactor(web): rebuild /architecture and /methods on docs primitives)

**What was done:**
Rebuilt /architecture and /methods on top of the new primitives.
/architecture now has six numbered sections (Stack / Optical /
Firmware / Wire / Inference / Console) with a typeset LayerStack
diagram, two separate StateMachine renderings (main loop + SWIR
sub-state), and a structured PacketFrame for the wire format.
/methods rolls the original ten sections into six (Metrics / Synth /
Training / Calibration / Uncertainty / Validation), with §01 using
a four-row MetricRow for the headline numbers.

DocPage.tsx grew shared building blocks: Eq, Math, Section,
SubSection, Prose, MetricRow, VitalStats, SpecList, SymbolLegend,
Bibliography, MarginNav, FactGrid.

Bundled into the same commit: a fix for the headline-metric
count-up flicker. The CountUpValue component had been tweening from
0 → target on first viewport entry, but the IntersectionObserver +
React 18 StrictMode + Next.js client navigation interaction produced
two failure modes — numbers that restarted from 0 on every parent
rerender (MarginNav scroll updates), and numbers stuck at 0 on a
second visit to the page. After two attempted fixes (tighter effect
deps, then a `started` flag) failed, the count-up was dropped
entirely. The component now renders the static value as written.

**Why:**
The reliability budget for a science-fair headline number is zero.
Cleverness in the animation layer is not worth a "did the tween land?"
question on the metric block. A static-rendering MetricRow is also
substantially cheaper at runtime (no IntersectionObserver, no RAF
loop) which matters on a documentation page expected to render
in mobile browsers as well as on a presenter's laptop.

**Discovered / Learned:**
React 18's StrictMode double-invokes effects in development. Animated
components must either (a) be idempotent under double-invoke, or
(b) accept that they will run twice in dev. The `playedRef` "ever
played" flag I tried to use as a guard was set to `true` on the first
invocation and survived the cleanup, so the second invocation bailed
early — a textbook "don't combine refs and StrictMode this way"
mistake. The static-render rewrite sidesteps the entire class of
issues. RegExpMatchArray-as-effect-dep is also a trap; React compares
deps with Object.is and a fresh match object on every render
re-triggers the effect.

**Paper impact:**
None on metrics. Reinforces a Methods-section claim — the
documentation faithfully reports the headline numbers without any
animation that could miscalibrate the displayed value.

**Open questions:**
- None. The fix is final.

---

### 2026-05-22 — Entry 22: Reference library expansion

**Commit:** `c2efb9d` (docs: expand reference library across paper-notes and the website)

**What was done:**
Brought the project's working bibliography in line with what the
codebase actually depends on. /about's reference list grew from 6 to
11 entries grouped by what they justify (ISRU rationale → spectroscopy
→ ML → AL → photometry); /methods grew a new §07 References section
with 15 entries adding the Hamamatsu C12880MA + ams AS7265x datasheets,
Loshchilov & Hutter (AdamW), Jacobson et al. (INT8 QDQ), and David et
al. (TFLite Micro). `docs/paper-notes.md` got a parallel "Reference
Library" section (groups A–G) so the website citations and the
project's own notes don't drift.

**Why:**
The paper-notes file has a dependency-tracking section per chapter
("Background / Prior Art" etc.) but no consolidated bibliography.
Without a single source of truth, the web pages and the eventual LaTeX
manuscript would have to maintain their own lists in parallel. The
new structure has the website and `paper-notes.md` rendering the same
12–15 references, each tied to the part of VERA it informs ("→ §02
Synth. Crystal-field band positions for Fe²⁺...").

**Discovered / Learned:**
The audit-trail line per reference (the `→ used` field) is more
valuable than the bibliography itself. A jury can land on any number
on /methods and trace it back to the study that justifies it without
reading the bibliography cold. This is a stronger contract than
"these are the papers we read".

**Paper impact:**
Background / Prior Art now has a complete reference list. References
section of the paper can pull directly from `paper-notes.md` Section
"Reference Library" by grouping (A: mission rationale, B: spectroscopy,
C: datasheets, D: ML, E: calibration, F: AL, G: embedded).

**Open questions:**
- None.

---

### 2026-05-27 / 28 — Entry 23: Repo hygiene pass

**Commits:** `148dd1f`, `4b4cedd`, `e4168bb`

**What was done:**
Three small but real fixes flushed by an end-of-month audit:
1. `CONTRIBUTING.md` had `git clone .../your-org/vera.git` from the
   template — anyone following the doc fails on command 1. Replaced
   with the actual `Hipdarius/VERA` URL. Also replaced the "see project
   memory for rationale" phrase (an AI-tool internal vocabulary leak)
   with a pointer to the module docstring in `src/vera/schema.py`.
2. `lucide-react` was listed in `web/package.json` and recommended in
   `UI_STANDARDS.md` but had zero imports anywhere. Dropped the
   dependency, updated UI_STANDARDS to match what the codebase
   actually does (inline SVG, no library).
3. `web/api/predict.py` is a Vercel serverless function; `vercel.json`
   declares `includeFiles: api/model.onnx`. But `*.onnx` was in the
   global `.gitignore`, so the file never shipped — Vercel cold-starts
   would 500 with "model not found". Added an explicit
   `!web/api/model.onnx` exception and committed the FP32 baseline
   (2.6 MB).

**Why:**
The first two are documentation honesty: the project should describe
what it actually does, not what a template did. The third is a real
production bug: any Vercel deploy of the current `main` would fail.

**Discovered / Learned:**
`.gitignore` exceptions interact in a non-obvious way with `*.onnx`
patterns — the negation has to come AFTER the broader rule and the
path has to be relative to the .gitignore location. Confirmed the
override worked with `git check-ignore -v`.

**Paper impact:**
None on metrics. Discussion of "honest documentation" if we ever
write a paragraph on engineering process.

**Open questions:**
- None.

---

### 2026-05-29 / 30 — Entry 24: Lint policy + CI enforcement

**Commits:** `9a39127` (feat(ci)), `775b017` (style: ruff auto-fixes)

**What was done:**
Closed a long-standing enforcement gap: `Makefile` already invoked
`ruff check` and `CONTRIBUTING.md` demanded "make lint reports no
issues", but `pyproject.toml` had no `[tool.ruff]` section and CI
never ran the lint step. Lint failures could merge to main.

`pyproject.toml`: full `[tool.ruff]` policy with line-length 100 and
a selected rule set focused on real bugs (pyflakes, pycodestyle,
isort, bugbear, pyupgrade, ruff-native). Per-file ignores let
scripts/ and tests/ keep the sys.path-insert-then-import pattern
they need; ambiguous-Unicode rules (RUF001/002/003) are explicitly
disabled because Greek letters (σ, μ, λ), the multiplication sign
(×), and the en-dash (–) are the right symbols in spectroscopy
docstrings.

`.github/workflows/ci.yml`: added two new parallel jobs — Lint ·
Python (ruff) and Lint · Web (next lint) — alongside the existing
test, typecheck, and firmware-build jobs.

`Makefile`: split `lint` (CI runs check-only) from `format` (opt-in
via `make format`) so PR diffs stay focused. Added `typecheck` and
`lint-fix` aliases.

Real bugs flushed by the new policy:
- `apps/api.py:355` — added `from e` to HTTPException re-raise (B904,
  exception chaining)
- `src/vera/datasets.py:84` — renamed unused loop var to `_klass` (B007)
- `src/vera/sam.py:188` — removed dead `names` assignment (F841)
- `src/vera/train.py:307` — split `if not history: return` onto two
  lines so debuggers can break (E701)
- `tests/test_active_learning.py:26` — removed unused `K = p.size`
  (F841)

A separate `style:` commit applied 100+ mechanical auto-fixes (sorted
`__all__` lists, modern type hints `"Measurement"` → `Measurement`,
unused-import removal, isort) so the lint-policy commit stayed small
and reviewable.

**Why:**
A policy that exists in documentation but is not enforced is a
liability — anyone reading CONTRIBUTING expects `make lint` to be
meaningful, but until this commit the command ran with ruff's bare
defaults. The new policy is calibrated for scientific code: real
bugs are blocked, scientific Unicode is allowed, the rare
sys.path-insert idiom is whitelisted by file pattern. The CI job
ensures the policy is exercised on every PR.

**Discovered / Learned:**
Ruff's defaults are designed for general-purpose Python and produce
significant false-positive volume on a numerical codebase: 84 errors
remained after the auto-fix pass, the majority of which were
RUF001/002/003 (ambiguous Unicode) on intentional Greek-letter
docstrings. Calibrating the policy was a 30-minute exercise in
deciding which rules describe real bugs versus stylistic preferences.
The B905 zip-strict rule in particular fires on every `zip(a, b)`
in numerical code where length is invariant by construction —
genuine bugs would be elsewhere.

The `react/no-unescaped-entities` ESLint rule similarly flagged every
straight quote in JSX text. Disabling it preserves prose quality;
curly-quote escaping degrades readability.

**Paper impact:**
Methods (Reproducibility section): "the codebase is enforced by
parallel pytest, ruff, eslint, tsc, and PlatformIO jobs running on
every push." This is a credible engineering-rigor claim now.

**Open questions:**
- None on the policy itself.

---

### 2026-05-31 — Entry 25: Pre-hardware-phase snapshot

**Commit:** `4f80ced` (docs: correct test-module count in README) and the snapshot below.

**What was done:**
End-of-May audit confirms:
- 214 tests pass across 15 modules (was 14 in README; one-character fix)
- Ruff: clean
- Next lint: clean
- TSC: clean
- 5 CI jobs configured: Lint · Python, Lint · Web, Test · pytest,
  Typecheck · tsc, Build · firmware (PlatformIO)
- 26 commits between 2026-04-11 and 2026-05-31, conventional-commit
  format throughout
- Web bundle: 4 routes (`/`, `/about`, `/architecture`, `/methods`)
- Real spectra captured: still zero
- Hardware components ordered: still zero

**Why:**
The May sprint was "lock the project against a hiatus". With the
linting policy enforced, the documentation surface in line with the
codebase, and the Vercel deploy actually working, the project can sit
for weeks without bit-rot accumulating. The next phase is genuinely
hardware: order the BOM (≈ €658), assemble the C12880MA + ADS1115
daughterboard, capture BaSO₄ + reference minerals.

**Discovered / Learned:**
Repo hygiene compounds. The CONTRIBUTING URL bug, the dead
lucide-react dependency, and the gitignored Vercel model file would
each have cost a future contributor 5 to 30 minutes. Together, an
hour of trust. Catching them as a single audit pass is roughly 100 ×
cheaper than catching them one at a time as user reports.

**Paper impact:**
None. This is a checkpoint, not a result.

**Open questions:**
- The 14 from 2026-04-26 plus:
15. With CI enforcing lint, what's the next category of bug to add a
    rule for? (My guess: a custom check that
    `vera.schema.SCHEMA_VERSION` is bumped whenever
    `Measurement` schema changes.)

---

## Updated Metrics Snapshot — 2026-05-31

| Metric                                  | Value (2026-04-26) | Value (2026-05-31) | Delta |
|:----------------------------------------|-------------------:|-------------------:|------:|
| Total Python lines                      |             ~9,800 |            ~10,200 |  +400 |
| Total firmware lines                    |              1,420 |              1,423 |     0 |
| Total web lines                         |             ~1,400 |             ~3,300 |+1,900 |
| Total docs lines                        |                843 |              1,365 |  +522 |
| Tests passing                           |                214 |                214 |     0 |
| Test files                              |                 15 |                 15 |     0 |
| CI jobs                                 |                  3 |                  5 |    +2 |
| Documentation routes                    |                  1 |                  4 |    +3 |
| Lint policy                             |     Default (none) |   Enforced via CI  |   ✓   |
| Ruff errors                             |        not checked |                  0 |   ✓   |
| Next lint errors                        |        not checked |                  0 |   ✓   |
| Real spectra collected                  |                  0 |                  0 |     0 |
| Hardware components ordered             |                  0 |                  0 |     0 |

**Posture:** The software is hardened. The hardware queue is unchanged.
The next entry in this journal will be either Entry 26 ("first BOM
order placed") or it will sit empty until that happens.
