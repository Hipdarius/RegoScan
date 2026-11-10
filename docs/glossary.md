# Glossary

Terms specific to VERA and lunar regolith spectroscopy. The web pages
inline-define most acronyms on first use; this is the long version.

| Term | Expansion / definition |
|---|---|
| **VERA** | Visible & Emission Regolith Assessment — the project name. |
| **VIS/NIR** | Visible (380–700 nm) + Near-Infrared (700–1100 nm) — the spectral range covered by the C12880MA. |
| **SWIR** | Short-Wave Infrared (1000–2500 nm) — VERA samples this with a single InGaAs photodiode at 940 / 1050 nm. |
| **LIF** | Laser-Induced Fluorescence — emission from the sample under 405 nm excitation, captured through a 450 nm long-pass filter. |
| **ISRU** | In-Situ Resource Utilization — using lunar materials (water, oxygen, regolith) instead of shipping them from Earth. |
| **Ilmenite** | FeTiO₃ — iron-titanium oxide. The primary lunar candidate for ISRU oxygen extraction via H₂ reduction at ≈ 900 °C. |
| **Olivine** | (Mg,Fe)₂SiO₄ — abundant in lunar mare basalts. Diagnostic 1-µm Fe²⁺ band. |
| **Pyroxene** | (Mg,Fe,Ca)₂Si₂O₆ — also abundant in mare basalts. Two diagnostic Fe²⁺ bands (1-µm and 2-µm). |
| **Anorthite** | CaAl₂Si₂O₈ — the dominant feldspar in the lunar highlands. Plagioclase. |
| **Glass / agglutinate** | Amorphous fused regolith from impact gardening. Spectrally darker, weaker bands. |
| **Endmember** | A pure mineral spectrum, used as a building block in mixing models. |
| **Hapke model** | Bidirectional-reflectance theory for intimate mixtures (Hapke 1981). VERA uses the closed-form IMSA roundtrip. |
| **IMSA** | Inverse Multiple Scattering Approximation — algebraic Hapke roundtrip exact to machine ε. |
| **SAM** | Spectral Angle Mapper — classical hyperspectral baseline (Kruse et al. 1993). VERA uses it as both an ablation and an OOD-disagreement signal. |
| **SNV** | Standard Normal Variate — per-spectrum normalisation removing additive offset and multiplicative scale differences. |
| **ALS** | Asymmetric Least Squares — baseline subtraction for the continuum slope. |
| **ECE** | Expected Calibration Error — Guo et al. 2017's 15-bin estimator. |
| **OOD** | Out-of-distribution — sample outside the training distribution. VERA flags via calibrated entropy + SAM/CNN disagreement. |
| **TTA** | Test-Time Augmentation — averaging predictions over noisy copies of the same input. |
| **QDQ** | Quantize-Dequantize — INT8 ONNX quantization format (`onnxruntime.quantization`). |
| **TRL** | Technology Readiness Level — NASA scale 1 (concept) → 9 (flight-proven). VERA: TRL 4 sw, TRL 3 hw. |
| **BOM** | Bill Of Materials — the parts list for assembling the probe. See `docs/bom.csv`. |
| **C12880MA** | Hamamatsu mini-spectrometer module. 288 channels, 340–850 nm. Single-source — no drop-in replacement. |
| **AS7265x** | AMS multi-spectral sensor triad (AS72651 + AS72652 + AS72653). 18 channels, 410–940 nm. |
| **ADS1115** | TI 16-bit ADC with I²C interface. Used for the SWIR signal chain. |
| **OPA380** | TI transimpedance amplifier. Converts the InGaAs photodiode current to voltage for the ADC. |
| **G12180-010A** | Hamamatsu InGaAs photodiode. 1 mm active area. SWIR 940 / 1050 nm sensing. |
| **C12880MA "dark frame"** | Spectrum captured with all illumination off — subtracted from each measurement to remove dark-current bias. |
| **Spectralon / BaSO₄** | Near-ideal-Lambertian white reference puck (≥ 99 % reflectance). The white-reference division anchor. |
