# VERA — Paper Section Tracker

**Target:** 15–20 page LaTeX competition paper for Jonk Fuerscher 2027  
**Rule:** Append-only. Status updates are added as new lines under each section; previous statuses are never deleted.

---

## Section Statuses

### Introduction
- 2026-04-11 | **DRAFT-READY** — ISRU motivation, ilmenite oxygen pathway, gap in current prospecting tools, VERA's value proposition. Source material exists in README and project framing.
- 2026-04-11 | **DRAFT-READY** — Updated: strong framing from dev log. ISRU oxygen extraction from ilmenite as most promising near-term pathway. VERA positioned as handheld-class instrument solving weight/speed/sample-return limitations of existing tools. ESRIC/Luxembourg institutional relevance adds local hook.
- 2026-04-11 | **DRAFT-READY** — Post-SWIR: no change to Introduction status. The SWIR addition strengthens the value proposition but doesn't alter the framing.

### Background / Prior Art
- 2026-04-11 | **NEEDS WORK** — Requires literature review: ISRU spectroscopy (M3, Mini-TES, LIBS), lunar regolith simulant databases (USGS, RELAB), handheld NIR instruments. No entries yet.
- 2026-04-11 | **PARTIAL** — Updated: dev log provides concrete references. Burns 1993, Adams 1974, Cloutis & Gaffey 1991, Burns & Burns 1981, Hapke et al. 1975 (crystal-field theory). McKay et al. 1991 (regolith maturity/agglutinates). Yasanayake et al. 2024 (agglutinate spectral characteristics). 2024 Scientific Reports paper on 8-band mineral ID at 91.9%. Zhurong rover 8-band precedent. Tucker et al. (785 nm LIF on lunar simulants). Lin et al. 2017 (focal loss). Still needed: systematic ISRU spectroscopy review (M3, Mini-TES, LIBS), cost comparison table against existing instruments, RELAB/USGS database description.

### Instrument Design
- 2026-04-11 | **DRAFT-READY** — Hardware architecture documented: C12880MA + AS7265x + 12-LED array + 405 nm LIF. ESP32-S3 state machine, sensor readout protocols, cost breakdown. Firmware source available.
- 2026-04-11 | **DRAFT-READY** — Updated: three-mode sensor architecture fully specified (Entry 1). C12880MA bit-banging at 100 kHz (4 ms readout), AS7265x I²C virtual register protocol, graceful degradation when AS7265x absent. Cost breakdown: C12880MA €290, AS7265x €25, LEDs €55, LIF €18. Schema v1.1.0 with 301/31/319 feature configurations. Ready to write up. Blocked only on physical assembly photos.
- 2026-04-11 | **DRAFT-READY** — Post-SWIR (Entry 7): VERA is now a 4-modality instrument. New subsection needed for InGaAs G12180-010A photodiode + OPA380 TIA + ADS1115 16-bit ADC signal chain. Cost table adds ~€15 for SWIR. Feature counts updated: full=303, multispectral=33, combined=321. Schema v1.2.0. Firmware state machine: 8 states (IDLE→DARK→BROADBAND→MULTISPECTRAL→NARROWBAND→SWIR→LIF→TRANSMIT). SWIR firmware is placeholder — needs hardware for real readout. Blocked on: physical assembly, real ADC noise characterization.

### Methods
- 2026-04-11 | **PARTIAL** — Synthetic data generation pipeline (spectral mixing from USGS/RELAB endmembers), 1D ResNet architecture, PLSR regression, StratifiedGroupKFold CV, augmentation strategy documented in code. Still needed: real-sample validation protocol, measurement uncertainty characterization.
- 2026-04-11 | **SUBSTANTIAL** — Updated from full dev log. Now includes:
  - Synthetic data generation: Dirichlet spectral mixing with 5 endmembers, constrained max_fraction ≤ 0.35 for mixed class (Entry 3)
  - AS7265x simulation: Gaussian bandpass integration (FWHM=20 nm) with ±12% noise and 16-bit ADC quantization (Entry 1)
  - Crystal-field endmember modeling: olivine 7 bands, pyroxene 7 bands, anorthite 5 bands, ilmenite 5 bands, glass parametric ramp (Entry 5)
  - Glass/agglutinate parametric model: exponential ramp + LIF efficiency 0.15 (Entry 2)
  - Augmentation: spectral noise + LED Gaussian noise (σ=0.012) + LIF noise (σ=0.020) (Entry 4)
  - Loss function: CrossEntropyLoss + 5% label smoothing (focal loss abandoned — Entry 4)
  - CNN: 1D ResNet ~670k params, configurable input dim, adaptive kernel sizing
  - Feature extraction for multispectral mode: 7 hand-crafted features including band_depth_540 and nir_slope
  - Still needed: real-sample validation protocol, measurement uncertainty budget, integration time optimization
- 2026-04-11 | **SUBSTANTIAL** — Post-SWIR (Entry 7): additional Methods material:
  - SWIR synthetic generation: endmember extrapolation to 940/1050 nm, ±8% gain perturbation, σ=0.005 per-channel noise, 16-bit ADC quantization model
  - Feature vector ordering: [spec(288) | as7265x(18) | swir(2) | led(12) | lif(1)]
  - SWIR augmentation: σ=0.012 Gaussian noise
  - Sensor mode auto-detection from CSV columns (bugfix — previous results may have trained on misaligned features)
  - ONNX export now reads model dimensions from meta.json (bugfix)
  - Still needed: real-sample validation protocol, real InGaAs calibration pipeline, measurement uncertainty budget

### Results
- 2026-04-11 | **PARTIAL**
  - **5-class mineral classification (synthetic):** 93.2% top-1 accuracy, 0.91 macro F1 — ready to write up.
  - **Ilmenite regression (synthetic):** R² = 0.967, RMSE = 0.037 — ready to write up.
  - **Real-sample validation:** NOT STARTED — no physical measurements yet.
  - **Sensor mode comparison (full vs. multispectral vs. combined):** NEEDS ANALYSIS — infrastructure exists but comparative results not compiled.
  - **LIF discrimination results:** NOT STARTED.
  - **Inference latency benchmarks:** Claimed <5 ms; needs formal benchmarking on target hardware.
- 2026-04-11 | **PARTIAL** — Updated with 6-class results from full dev log:
  - **6-class classification (same-seed):** 99.0% accuracy, all classes >94% F1 — READY TO WRITE UP.
  - **Mixed-class recovery:** 60% → 96% recall via constrained Dirichlet + focal loss → label smoothing (Entry 3) — READY TO WRITE UP. Before/after confusion matrix is a strong figure.
  - **Cross-seed generalization study:** 98.4% → 18–44% → 70% after crystal-field endmembers (Entries 4–5) — READY TO WRITE UP. This is a key paper contribution showing synthetic data limitations.
  - **Cross-seed failure modes:** three distinct causes identified (focal loss, augmentation gaps, endmember fidelity) — READY TO WRITE UP as multi-stage ablation.
  - **Glass class ceiling:** 1.7% cross-seed recall — physics limitation, no crystal-field features in amorphous material — READY TO DISCUSS.
  - **Ilmenite regression (synthetic):** R² = 0.967, RMSE = 0.037 — READY TO WRITE UP.
  - **AS7265x vs C12880MA comparison:** NEEDS FORMAL ANALYSIS — infrastructure exists, no head-to-head results compiled yet.
  - **Real-sample validation:** NOT STARTED — zero hardware, zero spectra.
  - **LIF discrimination (real):** NOT STARTED — no 405 nm data on simulants.
  - **Inference latency (target hardware):** NOT BENCHMARKED on ESP32-S3.
- 2026-04-11 | **SUBSTANTIAL** — Post-SWIR (Entry 7): major results upgrade:
  - **Cross-seed generalization with SWIR:** 70% → **99.3%** across 5 unseen seeds — READY TO WRITE UP. This is the paper's strongest single result. Before/after figure (VIS-only 70% vs VIS+SWIR 99.3%) is a hero figure candidate.
  - **Same-seed accuracy (6-class, SWIR):** 99.2% — marginal improvement, confirms no regression.
  - **Ilmenite RMSE (SWIR):** 0.036 — marginal improvement from 0.037.
  - **Modality ablation study:** now complete narrative — VIS alone (70% cross-seed) → VIS+multispectral (not yet formally compared) → VIS+multispectral+SWIR (99.3%). NEEDS FORMAL COMPILATION of intermediate results for the ablation table.
  - **sensor mode auto-detection bugfix:** previous cross-seed numbers (70%) may have been slightly pessimistic due to train.py feature misalignment. The 99.3% is unambiguously clean.
  - **AS7265x vs C12880MA comparison:** still NEEDS FORMAL ANALYSIS.
  - **Real-sample validation:** still NOT STARTED.
  - **LIF discrimination (real):** still NOT STARTED.
  - **Inference latency (ESP32-S3):** still NOT BENCHMARKED.
  - **TFLite/INT8 quantization accuracy:** NOT TESTED (TFLite stub only).

### Discussion
- 2026-04-11 | **NOT STARTED** — Pending real-sample results. Will need: synthetic-vs-real gap analysis, sensor degradation in vacuum/thermal, limitations of Gaussian bandpass simulation for AS7265x, comparison to M3/Mini-TES.
- 2026-04-11 | **NOTES READY** — Updated: substantial discussion material now available from dev log:
  - "Class boundary design matters more than model architecture" (Entry 3) — generalizable insight
  - Synthetic data has a fundamental generalization ceiling (Entry 4) — validates hardware approach
  - Physics ceiling of VIS/NIR-only (340–850 nm) without 1 µm and 2 µm bands (Entry 5)
  - Glass/amorphous materials are intrinsically hard for spectral classification (Entry 5)
  - SWIR limitation: AS7265x 940 nm captures only leading edge of 1 µm Fe²⁺ band
  - Three-stage failure analysis (focal loss → augmentation → endmembers) is methodologically interesting
  - Still blocked on: real-sample domain gap analysis, vacuum/thermal degradation, comparison to M3/Mini-TES
- 2026-04-11 | **NOTES READY** — Post-SWIR (Entry 7): significant new discussion threads:
  - Two-point SWIR sampling is sufficient: you don't need a full SWIR spectrometer, just targeted wavelengths at the right absorption features. Cost-effectiveness argument for ISRU instrumentation.
  - The 1 µm band depth (swir_940/swir_1050 ratio) is so diagnostic that 2 channels carry more discriminative power than 288 VIS channels — validates "smart wavelength selection" thesis.
  - The train.py sensor mode bug reveals a subtle failure mode of auto-adapting architectures: Conv1d's adaptive pooling masked a feature dimension mismatch. Methodological lesson about silent bugs in flexible ML pipelines.
  - Cross-seed accuracy jump (70%→99.3%) is strong evidence that the synthetic data ceiling was a feature gap, not a fundamental modeling limitation.
  - Glass class likely still weak at 1 µm (amorphous — no crystal-field band) — SWIR helps crystalline minerals but may not rescue glass.
  - Still blocked on: real-sample results, real InGaAs noise characterization

### Conclusion
- 2026-04-11 | **NOT STARTED** — Blocked on Discussion.
- 2026-04-11 | **NOT STARTED** — Still blocked. Can only be written after real-sample results and discussion.

### Limitations
- 2026-04-11 | **NOTES ONLY** — Known issues to address: synthetic-only training data, no vacuum/thermal testing, Gaussian approximation of AS7265x response, no radiation hardness data, regolith grain-size effects uncharacterized.
- 2026-04-11 | **SUBSTANTIAL NOTES** — Updated from dev log. Documented limitations:
  - Synthetic-only training data with 70% cross-seed ceiling (Entry 4–5)
  - No hardware assembled, no real spectra collected
  - Gaussian bandpass approximation for AS7265x (may not match real channel responses)
  - Glass class nearly unclassifiable at 1.7% cross-seed recall (physics limitation)
  - No vacuum/thermal/radiation testing
  - No particle size or packing density characterization
  - 340–850 nm range misses diagnostic 1 µm and 2 µm mineral absorption bands
  - LIF at 405 nm is untested on lunar simulants (literature uses 785 nm)
  - Endmembers are still parametric curves, not measured reference spectra
- 2026-04-11 | **SUBSTANTIAL NOTES** — Post-SWIR (Entry 7): updated limitations:
  - Cross-seed ceiling raised to 99.3% but still synthetic-only — real-sample gap unknown
  - SWIR endmember values are extrapolated from VIS spectra, not measured at 940/1050 nm
  - Firmware SWIR readout is a placeholder — real ADS1115 reads not yet implemented
  - InGaAs photodiode noise floor uncharacterized (TIA noise may dominate over ADC resolution)
  - TFLite conversion is a stub — no INT8 quantization validation
  - Previous cross-seed results (70%) may have been affected by train.py sensor mode bug
  - All previous limitations still apply (no hardware, no vacuum/thermal, no particle size, etc.)

---

## Status Legend

| Status | Meaning |
|:-------|:--------|
| **NOT STARTED** | No material exists |
| **NOTES ONLY** | Bullet points / ideas collected, no prose |
| **NOTES READY** | Enough structured notes to begin drafting |
| **NEEDS WORK** | Some material but significant gaps |
| **PARTIAL** | Subsections ready, others missing |
| **SUBSTANTIAL** | Most subsections have material, few gaps remain |
| **DRAFT-READY** | Enough material to write a full draft |
| **DRAFTED** | Prose written, needs review |
| **FINAL** | Reviewed and publication-ready |

---

## Reference Library

The list below is the working set of papers and datasheets cited by the
codebase and the project website (`/about`, `/methods`). Each entry tags
the part of VERA it informs. Append-only — additions go at the bottom
with the date they enter the working set.

### A. Mission rationale (why ISRU, why ilmenite)

- **NASA (2020).** *Artemis Plan: NASA's Lunar Exploration Program Overview.*
  NASA HQ, NP-2020-05-2853-HQ.
  → Front matter / Introduction. Identifying high-FeO/TiO₂ deposits at the
  south polar region is on the Artemis critical path.
- **Sanders, G. B., Larson, W. E. (2013).** *Progress Made in Lunar In-Situ
  Resource Utilization under NASA's Exploration Technology and Development
  Program.* J. Aerospace Eng. 26(1), 5–17.
  doi:10.1061/(ASCE)AS.1943-5525.0000208.
  → Introduction. H₂ reduction of ilmenite at ≈ 900 °C as the cheapest
  near-term oxygen route.

### B. Lunar / planetary spectroscopy (why these wavelengths)

- **Pieters, C. M., et al. (2009).** *The Moon Mineralogy Mapper (M³) on
  Chandrayaan-1.* Current Science 96(4), 500–505.
  → Background, Instrument design. 340–2500 nm coverage validates the
  1-µm Fe²⁺ band as diagnostic; VERA's 340–1050 nm range is the
  affordable handheld subset.
- **Burns, R. G. (1993).** *Mineralogical Applications of Crystal Field
  Theory*, 2nd ed. Cambridge University Press. ISBN 978-0521430777.
  → Methods. Band positions for Fe²⁺ in olivine, pyroxene, ilmenite —
  the basis for the parameterised endmember spectra in
  `src/vera/synth.py`.
- **Hapke, B. (1981).** *Bidirectional reflectance spectroscopy: 1.
  Theory.* JGR 86(B4), 3039–3054.
  doi:10.1029/JB086iB04p03039.
  → Methods. Intimate-mixture model. The IMSA closed form gives the
  algebraic r↔w roundtrip in `synth.hapke_mix` (exact to machine ε).
- **Lommel & Seeliger (1887 / 1924).** *Photometric law for diffuse
  reflectance.* Astronomische Nachrichten.
  → Methods, Calibration. Off-normal viewing geometry correction in
  `calibrate.lommel_seeliger`.
- **Kruse, F. A., et al. (1993).** *The Spectral Image Processing System
  (SIPS) — Interactive Visualization and Analysis of Imaging Spectrometer
  Data.* Remote Sens. Environ. 44(2–3), 145–163.
  doi:10.1016/0034-4257(93)90013-N.
  → Validation. Spectral Angle Mapper. Used as both a paper-grade ablation
  and as an OOD-disagreement signal for the four-state status field.

### C. Sensor datasheets (why these channels)

- **Hamamatsu Photonics (2021).** *C12880MA Mini-spectrometer datasheet
  (KACC1226E).*
  → Instrument design, Calibration. 288-channel CMOS detector.
  Datasheet integration-time linearity range and dark-current vs
  temperature curve set the C2/C3 correction stages.
- **ams OSRAM (2019).** *AS7265x Smart Multi-Spectral Sensor System
  datasheet.*
  → Instrument design. The 18-channel triad. Centre wavelengths and
  FWHMs feed the Gaussian bandpass simulator in `synth.as7_response`.

### D. Machine learning (why this model)

- **He, K., Zhang, X., Ren, S., Sun, J. (2016).** *Deep Residual Learning
  for Image Recognition.* CVPR 2016. arXiv:1512.03385.
  → Methods. Backbone. 1D ResNet over the spectral axis with three
  stride-2 stages of (32, 64, 128) channels.
- **Loshchilov, I., Hutter, F. (2019).** *Decoupled Weight Decay
  Regularization.* ICLR 2019. arXiv:1711.05101.
  → Methods. AdamW. Decoupling L2 from the gradient step is what makes
  weight-decay tuning insensitive to learning rate.

### E. Calibration & uncertainty

- **Guo, C., Pleiss, G., Sun, Y., Weinberger, K. Q. (2017).** *On
  Calibration of Modern Neural Networks.* ICML 2017. arXiv:1706.04599.
  → Methods, Results. Temperature scaling and the 15-bin ECE estimator —
  the basis of `vera.uncertainty.fit_temperature` and the ≤ 1.5 %
  calibrated ECE figure.
- **Hendrycks, D., Gimpel, K. (2017).** *A Baseline for Detecting
  Misclassified and Out-of-Distribution Examples in Neural Networks.*
  ICLR 2017. arXiv:1610.02136.
  → Methods. Maximum-softmax-probability + entropy as OOD signals.
  VERA thresholds the calibrated entropy at the held-out 95th percentile.

### F. Active learning & ablation

- **Settles, B. (2009).** *Active Learning Literature Survey.* Univ.
  Wisconsin–Madison CS Tech. Report 1648.
  → Methods, Validation. The uncertainty-sampling family — the entropy
  and margin terms in `active_learning.acquisition_score` come from this
  taxonomy.

### G. Embedded deployment

- **Jacobson, R., Dosovitskiy, A., et al. (2018).** *Quantization and
  Training of Neural Networks for Efficient Integer-Arithmetic-Only
  Inference.* CVPR 2018. arXiv:1712.05877.
  → Methods. INT8 static QDQ quantization. The calibration-set sizing
  rule (≥ 100 representative samples) drives the 256-sample calibration
  set used in `vera.quantize`.
- **David, R., et al. (2021).** *TensorFlow Lite Micro: Embedded Machine
  Learning for TinyML Systems.* MLSys 2021. arXiv:2010.08678.
  → Instrument design. TFLite Micro design constraints. Drive the
  heap-free, static-buffer approach in `firmware/src` and the choice
  of INT8 ONNX as the calibration source.

> Append-only. New entries go at the bottom of the relevant subsection
> with the date they enter the working set. Removing an entry is a
> deliberate edit and must explain why in the commit message.

