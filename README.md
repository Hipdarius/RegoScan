<div align="center">

<img src="web/public/logo/vera-readme.svg" width="120" alt="VERA logo" />

# VERA

### Visible & Emission Regolith Assessment

**A handheld VIS/NIR + SWIR + LIF probe for real-time lunar regolith mineralogy**

[![CI](https://github.com/Hipdarius/VERA/actions/workflows/ci.yml/badge.svg)](https://github.com/Hipdarius/VERA/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776ab?logo=python&logoColor=white)](pyproject.toml)
[![Next.js 14](https://img.shields.io/badge/web-Next.js_14-000?logo=nextdotjs&logoColor=white)](web)
[![ESP32](https://img.shields.io/badge/firmware-ESP32--S3-e7352c?logo=espressif&logoColor=white)](firmware)
[![ONNX Runtime](https://img.shields.io/badge/inference-ONNX_Runtime-8b5cf6)](https://onnxruntime.ai)
[![License: MIT](https://img.shields.io/badge/license-MIT-22d3ee)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-214_passing-34d399)](tests)

---

*A full-stack lunar prospecting instrument — from non-blocking ESP32 firmware*
*through an ONNX Runtime inference service to a Next.js mission console.*
*Designed and built by* **Darius Ferent** *for the Jonk Fuerscher 2027 competition.*

[**Console**](#-quick-start) ·
[**Architecture**](#-system-architecture) ·
[**Methods**](#-methods) ·
[**API**](#-api-reference) ·
[**Hardware BOM**](#-hardware-bom)

</div>

---

## Why VERA?

Lunar In-Situ Resource Utilization (ISRU) depends on knowing **what minerals are
beneath the regolith**. Oxygen extraction from ilmenite (FeTiO₃) is the most
credible near-term ISRU pathway, but the existing prospecting tools are either
too heavy, too slow, or require sample return.

VERA solves this with a **handheld-class optical probe** that fuses three sensing
modalities — a 288-channel VIS/NIR spectrometer, an InGaAs SWIR pair targeting
the 1-µm Fe²⁺ band, and a 405 nm laser-induced-fluorescence channel — into a
single measurement, classifies the mineral phase in **&lt; 5 ms** on CPU, and
estimates ilmenite mass fraction continuously. The same JSON schema flows from
the ESP32 firmware to the React console, so there is one source of truth from
photons to pixels.

---

## ✨ Highlights

- **Three sensors, one probe.** C12880MA + AS7265x + InGaAs SWIR pair + 405 nm LIF
  laser, fused into a 321-channel feature vector with the same canonical ordering
  in firmware, bridge, training, and inference.
- **Calibrated uncertainty.** Posterior, runner-up margin, normalised entropy and
  a four-state OOD detector (`nominal` / `borderline` / `low_confidence` /
  `likely_ood`), with temperature scaling fitted on a held-out split.
- **Lossless INT8 quantization.** 707 KB ONNX model with **0.0 pp** accuracy
  drop vs. FP32. Calibrated on 256 real training samples.
- **Hapke intimate-mixture synthesis.** Closed-form IMSA roundtrip exact to
  machine epsilon, alongside a linear baseline for ablation studies.
- **Active learning.** Acquisition score combining entropy, top-1 margin, and
  SAM/CNN disagreement. ~2× annotation efficiency vs. random on synthetic
  benchmarks.
- **Non-blocking firmware.** No `delay()`, no heap, all buffers `constexpr`.
  Adaptive integration time targets the 95th-percentile pixel via a
  counting-sort histogram (O(N + 4096), zero heap).
- **214 tests.** Unit, property, end-to-end. Includes the firmware bridge,
  Hapke roundtrip, calibration math, OOD thresholds, and active learning.

---

## 📊 Headline metrics

| Metric | Value | Notes |
|:--|:--|:--|
| Cross-seed classification accuracy | **99.3 %** | 5 seeds, synthetic |
| ECE (15-bin, post-T-scaling) | **≤ 1.5 %** | Guo et al. 2017 estimator |
| Inference (FP32 / CPU) | **&lt; 5 ms** | ONNX Runtime |
| Model size (FP32 / INT8) | **2.6 MB / 707 KB** | static QDQ |
| INT8 accuracy drop | **0.0 pp** | lossless |
| SAM baseline | **16.8 %** | ≈ chance for k = 6 |
| CNN improvement over SAM | **+82.8 pp** | multimodal vs. spec-only |
| Active-learning lift | **≈ 2× labels-to-target** | vs. random sampling |
| Tests | **214 passing** | 0 skipped |

---

## 📑 Table of contents

1. [Sensor architecture](#-sensor-architecture)
2. [System architecture](#-system-architecture)
3. [Methods](#-methods)
4. [Quick start](#-quick-start)
5. [API reference](#-api-reference)
6. [Project layout](#-project-layout)
7. [Hardware BOM](#-hardware-bom)
8. [Roadmap](#-roadmap)
9. [Citing & references](#-citing--references)

---

## 🔬 Sensor architecture

VERA supports **three sensor configurations** via the `sensor_mode` parameter:

| Mode | Sensors | Features | Use case |
|:--|:--|:--:|:--|
| `full` | C12880MA + SWIR | 303 | High-resolution VIS/NIR + diagnostic SWIR |
| `multispectral` | AS7265x + SWIR | 33 | Low-cost scout mode |
| **`combined`** | **All four sensors** | **321** | **Maximum classification accuracy (deployed)** |

| Modality | Hardware | Channels | Range | BOM |
|:--|:--|:--:|:--|--:|
| VIS/NIR spectrometer | Hamamatsu C12880MA | 288 | 340–850 nm | ~€290 |
| Multispectral triad | AMS AS7265x | 18 | 410–940 nm | ~€60 |
| SWIR photodiode | Hamamatsu G12180-010A + ADS1115 + OPA380 | 2 | 940 / 1050 nm | ~€85 |
| Narrowband illumination | 12× discrete LEDs + 1050 nm | 13 | 385–1050 nm | ~€60 |
| 405 nm LIF | Laser diode + 450 LP filter | 1 | Fluorescence | ~€18 |

The 940 / 1050 nm SWIR pair targets the **1-µm Fe²⁺ crystal-field band**
(Burns 1993) — the most diagnostic feature for olivine vs. pyroxene vs.
ilmenite discrimination. Adding it lifted cross-seed generalisation from
~70 % to 99.3 %.

---

## 🏗 System architecture

```
┌───────────────────────────────────────────────────────────────────────┐
│                         VERA SYSTEM ARCHITECTURE                      │
├───────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  HARDWARE LAYER             INFERENCE LAYER         INTERFACE LAYER   │
│  ┌────────────────┐    ┌─────────────────────┐  ┌──────────────────┐  │
│  │ ESP32-S3 MCU   │    │ ONNX Runtime        │  │ Next.js 14       │  │
│  │ C12880MA  ×288 │───►│ 1D ResNet  ~280 K   │─►│ Recharts         │  │
│  │ AS7265x   ×18  │    │ Softmax + Regression│  │ Framer Motion    │  │
│  │ InGaAs    ×2   │    │ < 5 ms / inference  │  │ Tailwind CSS     │  │
│  │ 12× LEDs       │    │ INT8: 707 KB        │  │ App Router       │  │
│  │ 405 nm LIF     │    └─────────────────────┘  └──────────────────┘  │
│  └────────────────┘             │                       │             │
│         │                       ▼                       ▼             │
│         │              ┌─────────────────────┐  ┌──────────────────┐  │
│         └─────────────►│ FastAPI service     │─►│ Theme + history  │  │
│        USB-CDC JSON    │ /api/{predict,...}  │  │ CSV upload + log │  │
│                        │ Schema v1.2.0       │  │ Multi-page docs  │  │
│                        └─────────────────────┘  └──────────────────┘  │
│                                                                       │
│  ML PIPELINE                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │ Synth (linear + Hapke IMSA)  →  StratifiedGroupKFold CV         │  │
│  │ 1D ResNet (cls) + sigmoid (regr)  →  Temperature scaling        │  │
│  │ SAM baseline + OOD detector  →  ONNX FP32 + INT8 export         │  │
│  └─────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────────┘
```

### Firmware state machine

```
IDLE  →  DARK  →  ACQUIRE_VIS  →  ACQUIRE_AS7  →  ACQUIRE_SWIR  →  ACQUIRE_LIF  →  EMIT  →  IDLE
                                                       │
                                                       ▼
                              ┌──────────────────────────────────────────┐
                              │ SWIR sub-state machine (non-blocking)    │
                              │ DARK_REF → LED_940_ON → SETTLE → READ    │
                              │ → LED_OFF → LED_1050_ON → SETTLE → READ  │
                              │ → DONE                                    │
                              └──────────────────────────────────────────┘
```

**Design constraints**
- **No `delay()`** in the main loop — only `delayMicroseconds()` for sensor clock bit-banging
- **No heap allocation** — all buffers are statically sized (`constexpr`, `StaticJsonDocument`)
- **N=8 averaging** per SWIR LED step for SNR
- **Graceful degradation** — if the AS7265x is absent, the multispectral state is skipped
- **Adaptive integration** — targets the 95th-percentile pixel at ~50 % of ADC range
- **Wire protocol** — single-line JSON over USB-CDC, schema v1.2.0

---

## 🧠 Methods

### Synthetic data
Endmembers from parameterised crystal-field band models (Burns 1993). Two
mixing models: **linear additive** and **Hapke (1981) intimate** via the
closed-form Inverse Multiple Scattering Approximation. The
`r → w → mix → w → r` Hapke roundtrip is exact to machine epsilon. Augmentation
mimics realistic noise: Poisson-like on the spectrometer, Gaussian on the
triad, slope/bias drift for temperature, calibration error on the SWIR pair,
fluorescence baseline shift on LIF.

### Training
1D ResNet on the 321-channel concatenated input. Three residual stages with
(32, 64, 128) channels, stride-2 downsampling, global average pooling, ~280 K
parameters total. AdamW @ 1e-3, cosine schedule over 60 epochs, batch 128.
Two heads: a six-way softmax for class and a sigmoid for ilmenite mass-fraction
regression. Cross-seed validation across 5 seeds: **99.3 ± 0.4 %** accuracy.

### Calibration (`src/vera/calibrate.py`)
1. **Dark subtraction** at the frame level
2. **Per-pixel temperature correction** via vectorised least-squares fit of dark slope
3. **Integration-time normalisation** (counts → counts/ms)
4. **White-reference division** (BaSO₄ puck under same illumination)
5. **Photometric correction** (Lommel-Seeliger or Lambertian)

A `CalibrationProfile` dataclass persists everything in a single JSON next
to the model artefacts, so deployments cannot drift from training.

### Uncertainty (`src/vera/uncertainty.py`)
Calibrated posterior + runner-up margin + normalised entropy + four-state
status: `nominal` / `borderline` / `low_confidence` / `likely_ood`. Thresholds
fitted on held-out, not guessed. Temperature scaling minimises NLL via
1-D grid over T ∈ [0.5, 5.0]; ECE estimator follows Guo et al. 2017.

### OOD detection
Two signals: (1) calibrated entropy threshold above the 95th-percentile of
in-distribution held-out, (2) SAM/CNN disagreement at high confidence. SAM
on synthetic spec-only is near chance (16.8 %), but its **disagreements**
with the CNN reliably indicate distribution shift.

### Active learning (`src/vera/active_learning.py`)
Acquisition score = `α · entropy + β · (1 − margin) + γ · sam_disagreement`.
Returns top-K candidate indices for annotation. ~2× efficiency vs. random.

### Embedded deployment
**FP32 ONNX** is canonical (2.6 MB). **INT8** via
`onnxruntime.quantization` (static QDQ, calibrated on 256 real training
samples) compresses to **707 KB at zero accuracy loss**. The TFLite Micro
path for ESP32 is wrapped in `scripts/build_tflite_micro.sh` and requires
a Linux build host (tensorflow + onnx-tf are not co-installable on Windows
with Python 3.12).

---

## 🚀 Quick start

```bash
# Clone and install
git clone https://github.com/Hipdarius/VERA.git
cd VERA
uv sync --all-extras

# Generate synthetic training data
make data-gen

# Train (writes runs/<run-id>/{model.onnx, meta.json})
make train

# Or run the one-shot bring-up
bash scripts/setup-bench.sh

# Run the full test suite (214 tests)
make test

# Launch API + console
make serve-api    # terminal 1 — http://127.0.0.1:8000
make serve-web    # terminal 2 — http://localhost:3001
```

To exercise the firmware → bridge → API → console pipeline without
hardware:

```bash
# Synthesise frames and pipe them through the bridge
python scripts/mock_esp32.py | python scripts/bridge.py --csv stream.csv --post
```

---

## 📡 API reference

| Method | Endpoint | Description |
|:--|:--|:--|
| `GET` | `/healthz` | Liveness check + model status |
| `GET` | `/api/meta` | Schema version, sensor mode, feature count, ONNX hash |
| `POST` | `/api/predict` | Classify a feature vector (33, 303, or 321 features depending on mode) |
| `POST` | `/api/predict/demo` | Synthesize + classify a random regolith spectrum |
| `GET` | `/api/endmembers` | Reference mineral spectra for overlay |

`PredictionResponse` carries the full uncertainty tuple — calibrated
posterior, top-1 margin, normalised entropy, and a `status` enum — so
the console can render `treat as advisory` warnings without recomputing
anything client-side.

---

## 📁 Project layout

```
vera/
├─ src/vera/                 Core Python library
│  ├─ schema.py              Data contract (v1.2.0, 3 sensor modes)
│  ├─ synth.py               Linear + Hapke spectral mixing, augmentation
│  ├─ datasets.py            PyTorch dataset + StratifiedGroupKFold splits
│  ├─ augment.py             Noise injection, baseline drift
│  ├─ train.py               1D ResNet trainer with --sensor-mode flag
│  ├─ evaluate.py            Confusion matrices, bootstrap CIs, ROC/PR
│  ├─ calibrate.py           Dark, white, integration, temperature, photometry
│  ├─ uncertainty.py         Entropy, margin, OOD classifier, T-scaling
│  ├─ inference.py           ONNX Runtime engine (sensor-mode aware)
│  ├─ inference_robust.py    TTA, sample fusion, temperature fitting, ECE
│  ├─ sam.py                 Spectral Angle Mapper baseline
│  ├─ active_learning.py     Acquisition-score ranker for sample budgeting
│  ├─ quantize.py            ONNX FP32 export + static INT8 quantization
│  └─ models/cnn.py          1D ResNet implementation
│
├─ apps/api.py               FastAPI service (5 endpoints)
│
├─ web/                      Next.js 14 mission console
│  ├─ app/                   Routes: /, /about, /architecture, /methods
│  ├─ components/            Hero, MissionPanel, gauge, chart, NavBar, DocPage
│  └─ lib/                   API client + TypeScript types
│
├─ firmware/src/             ESP32-S3 embedded firmware
│  ├─ main.cpp               Non-blocking state machine (7 states)
│  ├─ C12880MA.{h,cpp}       Bit-banged spectrometer driver, adaptive integration
│  ├─ AS7265x.{h,cpp}        18-band I2C multispectral driver
│  ├─ ADS1115.{h,cpp}        16-bit ADC for InGaAs SWIR readout
│  ├─ Illumination.{h,cpp}   LED array + laser + 1050 nm GPIO control
│  ├─ Protocol.{h,cpp}       ArduinoJson serialization + thermistor
│  └─ Config.h               Pin assignments, calibration constants
│
├─ tests/                    214 tests across 15 modules
├─ scripts/                  mock_esp32, bridge, ablate_mixing, build_tflite_micro
├─ docs/                     engineering-journal.md, paper-notes.md
├─ runs/                     Trained artefacts (model.onnx, meta.json)
├─ .github/workflows/        CI: pytest + tsc + PlatformIO native
└─ pyproject.toml            uv / hatch project config
```

---

## 🛠 Hardware BOM

| # | Component | Qty | Unit € | Subtotal |
|--:|:--|--:|--:|--:|
| 1 | Hamamatsu C12880MA mini-spectrometer | 1 | 290 | 290 |
| 2 | AMS AS7265x triad breakout | 1 | 60 | 60 |
| 3 | Hamamatsu G12180-010A InGaAs photodiode | 1 | 50 | 50 |
| 4 | TI ADS1115 16-bit ADC breakout | 1 | 12 | 12 |
| 5 | TI OPA380 transimpedance amp | 1 | 8 | 8 |
| 6 | Narrowband LEDs (385, 405, 455, 470, 525, 590, 630, 700, 760, 810, 850, 940 nm) | 12 | 2.5 | 30 |
| 7 | 1050 nm LED (SWIR) | 1 | 14 | 14 |
| 8 | 405 nm laser diode + 450 nm LP filter | 1 | 18 | 18 |
| 9 | Espressif ESP32-S3 DevKit | 1 | 22 | 22 |
| 10 | NTC 10k thermistor + 0.1 % resistors | 1 | 4 | 4 |
| 11 | Custom PCB + connectors + enclosure | 1 | 90 | 90 |
| 12 | Misc. (BaSO₄ puck, cabling, mounts) | 1 | 60 | 60 |
| | | | **≈ €658** | |

(Full BOM with vendor part numbers in [docs/bom.csv](docs/bom.csv). Indicative single-quantity hobbyist pricing / single-quantity. Bulk pricing or substituting the C12880MA with a lower-cost CMOS spectrometer cuts the BOM by ~40 %.)

---

## 🗺 Roadmap

- [x] Synthetic-data pipeline with linear + Hapke mixing
- [x] 1D ResNet trainer with cross-seed CV at 99.3 %
- [x] FastAPI inference service with full uncertainty
- [x] Next.js console (Console / About / Architecture / Methods)
- [x] Calibration + uncertainty + OOD modules
- [x] SAM baseline + active-learning loop
- [x] INT8 lossless quantization
- [x] Non-blocking ESP32 firmware with adaptive integration
- [x] mock_esp32 → bridge → API → console end-to-end
- [ ] Order BOM (≈ €658, see docs/bom.csv)
- [ ] Solder & assemble the C12880MA + ADS1115 daughterboard
- [ ] Capture BaSO₄ white reference + reference minerals
- [ ] Fit temperature scale on real spectra
- [ ] Linear-vs-Hapke domain transfer ablation on real intimate mixtures
- [ ] TFLite Micro flatbuffer for on-MCU inference

---

## 📚 Citing & references

Key papers underpinning the design choices, with full annotations in
`docs/paper-notes.md`:

- **Burns (1993)** — *Mineralogical Applications of Crystal Field Theory* (band positions)
- **Hapke (1981)** — *Bidirectional reflectance spectroscopy* (intimate mixing)
- **Pieters et al. (2009)** — *Moon Mineralogy Mapper (M³)* (spectral coverage choices)
- **He et al. (2016)** — *Deep residual learning* (1D ResNet adaptation)
- **Guo et al. (2017)** — *On calibration of modern neural networks* (temperature scaling, ECE)

```bibtex
@misc{ferent2027vera,
  author       = {Ferent, Darius},
  title        = {VERA: A Handheld VIS/NIR + SWIR + LIF Probe for Real-Time Lunar Regolith Mineralogy},
  year         = {2027},
  howpublished = {Jonk Fuerscher 2027},
  url          = {https://github.com/Hipdarius/VERA}
}
```

---

## 🛡️ Compatibility

| Component | Versions tested |
|:--|:--|
| Python | 3.11 · 3.12 |
| Node | 20 LTS · 22 |
| OS | Ubuntu 22.04 · macOS 14 · Windows 11 |
| ESP32-S3 | DevKitC-1 N8R8, Arduino-ESP32 v3 |
| Browsers | Chrome 120+ · Safari 17+ · Firefox 120+ |

The CI matrix runs Ubuntu only; macOS / Windows are validated manually
at each major polish pass.

---

## 🤝 Contributing & community

- **[CONTRIBUTING.md](CONTRIBUTING.md)** — dev setup, branch & commit conventions, schema-version rules
- **[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)** — expectations for issues, PRs, and discussion
- **[SECURITY.md](SECURITY.md)** — how to report a security issue privately
- **[CHANGELOG.md](CHANGELOG.md)** — week-by-week feature and fix log
- **[Brand guide](docs/brand-guide.md)** — palette, typography, sizing, clearspace
- **[Glossary](docs/glossary.md)** — terms used across the docs and codebase
- **[Data format](docs/data-format.md)** — canonical CSV column order + sensor modes
- **[Release checklist](docs/release-checklist.md)** — pre-tag verification steps
- **[Engineering journal](docs/engineering-journal.md)** — append-only lab notebook (30+ entries)
- **[Paper notes](docs/paper-notes.md)** — section tracker + reference library for the eventual writeup

---

<div align="center">

**Built by [Darius Ferent](https://github.com/Hipdarius)** ·
**Jonk Fuerscher 2027**

*From photons to a class label, in five layers — open-source under MIT.*

</div>
