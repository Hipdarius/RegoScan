<div align="center">

# VERA

### Visible & Emission Regolith Assessment

**Compact Dual-Sensor VIS/NIR + 405 nm LIF Probe for Real-Time Lunar Regolith Mineralogy**

[![CI](https://github.com/Hipdarius/VERA/actions/workflows/ci.yml/badge.svg)](https://github.com/Hipdarius/VERA/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776ab?logo=python&logoColor=white)](https://python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-22d3ee)](LICENSE)
[![Tests: 111](https://img.shields.io/badge/tests-111_passing-34d399)]()
[![ONNX Runtime](https://img.shields.io/badge/inference-ONNX_Runtime-8b5cf6)]()

---

*A full-stack lunar prospecting instrument — from embedded firmware through*
*machine learning to real-time web telemetry — designed and built by*
**Darius Ferent** *for the Jonk Fuerscher 2027 competition.*

</div>

---

## Why VERA?

Lunar In-Situ Resource Utilization (ISRU) depends on knowing **what minerals are beneath the regolith**. Oxygen extraction from ilmenite (FeTiO3) is the most promising near-term ISRU pathway, but current prospecting tools are either too heavy, too slow, or require sample return.

VERA solves this with a **handheld-class optical probe** that combines three sensing modalities into a single measurement, classifies the mineral phase in <5 ms on CPU, and estimates ilmenite mass fraction continuously.

---

## Sensor Architecture

VERA supports **three sensor configurations** via the `sensor_mode` parameter:

| Mode | Sensors | Features | Use Case |
|:-----|:--------|:--------:|:---------|
| **full** | C12880MA only | 301 | High-resolution spectroscopy |
| **multispectral** | AS7265x only | 31 | Low-cost scout mode |
| **combined** | Both sensors | 319 | Maximum classification accuracy |

| Modality | Hardware | Channels | Range | Cost |
|:---------|:---------|:--------:|:------|-----:|
| **VIS/NIR Spectrometer** | Hamamatsu C12880MA | 288 | 340 -- 850 nm | ~€290 |
| **Multispectral Sensor** | AMS AS7265x Triad | 18 | 410 -- 940 nm | ~€25 |
| **Narrowband LED Array** | 12x discrete LEDs | 12 | 385 -- 940 nm | ~€55 |
| **405 nm LIF** | Laser diode + 450 LP filter | 1 | Fluorescence | ~€18 |

---

## Hardware

The probe is driven by an **ESP32-S3** microcontroller running a non-blocking acquisition state machine:

```
IDLE → DARK_FRAME → BROADBAND → MULTISPECTRAL → NARROWBAND (×12) → LIF → TRANSMIT
```

**Design constraints:**
- **No `delay()`** in the main loop — only `delayMicroseconds()` for sensor clock bit-banging
- **No heap allocation** — all buffers are statically sized (`constexpr` arrays, `StaticJsonDocument`)
- **5x averaging** per measurement state for improved SNR
- **Graceful degradation** — if the AS7265x is absent, the `MULTISPECTRAL` state is skipped automatically
- **Wire protocol** — single-line JSON frames over USB serial at 115200 baud

**Spectrometer readout:** The C12880MA requires precise bit-banging of the CLK/ST/TRG pins at 100 kHz. Each readout takes ~4 ms (376 clock cycles: 87 dummy + 288 valid + 1 trailing). The 12-bit ADC samples the analog video output on each falling clock edge.

**AS7265x readout:** The triad sensor communicates over I2C at 400 kHz using a virtual register protocol. Each of the 3 dies (AS72651/52/53) provides 6 calibrated IEEE 754 floating-point channels, read sequentially.

---

## System Architecture

```
+---------------------------------------------------------------------+
|                        VERA SYSTEM ARCHITECTURE                     |
+---------------------------------------------------------------------+
|                                                                     |
|  HARDWARE LAYER              INFERENCE LAYER        INTERFACE LAYER |
|  +-----------------+    +--------------------+    +---------------+ |
|  | ESP32-S3 MCU    |    | ONNX Runtime       |    | Next.js 14    | |
|  | C12880MA (288ch)|--->| 1D ResNet (~670k)  |--->| Recharts      | |
|  | AS7265x (18ch)  |    | Softmax + Regress  |    | Framer Motion | |
|  | 12x LED array   |    | <5 ms / inference  |    | Tailwind CSS  | |
|  | 405 nm LIF laser|    +--------------------+    +---------------+ |
|  +-----------------+             |                        |         |
|          |                       v                        v         |
|          |               +--------------------+    +---------------+|
|          +-------------->| FastAPI REST API    |--->| Theme system  ||
|           JSON/Serial    | 5 endpoints         |    | Scan history  ||
|                          | ONNX session pool   |    | CSV upload    ||
|                          +--------------------+    +---------------+|
|                                                                     |
|  ML TRAINING PIPELINE                                               |
|  +---------------------------------------------------------------+  |
|  | Synthetic spectra (USGS/RELAB endmembers, 3 sensor modes)     |  |
|  | StratifiedGroupKFold CV | Spectral mixing augmentation        |  |
|  | 1D ResNet (classification) + PLSR (regression) dual heads     |  |
|  | Bootstrap CI | Permutation feature importance | ONNX export   |  |
|  +---------------------------------------------------------------+  |
+---------------------------------------------------------------------+
```

---

## Performance

Benchmarked on a held-out test set of 3,000 synthetic lunar regolith samples:

| Model | Task | Metric | Score |
|:------|:-----|:-------|------:|
| **1D ResNet** | 5-class mineral ID | Top-1 Accuracy | **93.2 %** |
| **1D ResNet** | 5-class mineral ID | Macro F1 | **0.91** |
| **PLSR** | Ilmenite regression | R2 | **0.967** |
| **PLSR** | Ilmenite regression | RMSE | **0.037** |

---

## Project Structure

```
vera/
├── src/vera/               Core Python library
│   ├── schema.py               Data contract (v1.1.0, 3 sensor modes)
│   ├── synth.py                Spectral mixing + AS7265x Gaussian bandpass
│   ├── datasets.py             PyTorch dataset + StratifiedGroupKFold splits
│   ├── augment.py              Spectral mixing, noise injection, baseline drift
│   ├── train.py                CNN + PLSR training (--sensor-mode CLI flag)
│   ├── evaluate.py             Confusion matrices, ROC/PR curves, CI intervals
│   ├── inference.py            ONNX Runtime engine (sensor-mode aware)
│   ├── quantize.py             ONNX export + INT8 quantization
│   ├── features.py             Full + multispectral feature extraction
│   ├── io_csv.py               Schema-validated CSV I/O (auto-detect mode)
│   ├── preprocess.py           SNV, Savitzky-Golay, ALS baseline
│   └── models/
│       ├── cnn.py                  1D ResNet (configurable input dim)
│       └── plsr.py                 PLS Regression + Random Forest baseline
│
├── apps/
│   └── api.py                  FastAPI REST backend (5 endpoints)
│
├── web/                    Next.js 14 mission console
│   ├── app/                    App router, layout, global styles
│   ├── components/             React components (charts, gauges, panels)
│   └── lib/                    API client, TypeScript types
│
├── firmware/               ESP32-S3 embedded firmware
│   └── src/
│       ├── main.cpp                Non-blocking state machine (7 states)
│       ├── C12880MA.cpp/h          Bit-banged spectrometer driver (100 kHz)
│       ├── AS7265x.cpp/h           18-band I2C multispectral driver
│       ├── Illumination.cpp/h      LED array + laser GPIO control
│       ├── Protocol.cpp/h          ArduinoJson serialization + thermistor
│       └── Config.h                Pin assignments, calibration constants
│
├── tests/                  111 tests across 8 test modules
├── scripts/                CLI utilities (mock ESP32, bridge, data gen)
├── .github/workflows/      CI: pytest + tsc + PlatformIO
├── pyproject.toml          Project config (uv / hatch)
├── Makefile                8 automation targets
└── CONTRIBUTING.md         Developer guide and conventions
```

---

## Quick Start

```bash
# Clone and install
git clone https://github.com/Hipdarius/VERA.git
cd VERA
uv sync --all-extras

# Generate synthetic training data
make data-gen

# Train the CNN
make train

# Run the full test suite (111 tests)
make test

# Launch API + web dashboard
make serve-api   # terminal 1 — port 8000
make serve-web   # terminal 2 — port 3001
```

---

## API Reference

| Method | Endpoint | Description |
|:-------|:---------|:------------|
| `GET` | `/healthz` | Liveness check + model status |
| `GET` | `/api/meta` | Schema version, sensor mode, feature count, ONNX hash |
| `POST` | `/api/predict` | Classify a feature vector (31, 301, or 319 features) |
| `POST` | `/api/predict/demo` | Synthesize + classify a random regolith spectrum |
| `GET` | `/api/endmembers` | Reference mineral spectra for overlay |

---

<div align="center">

**Developed by Darius Ferent for the Jonk Fuerscher 2027 competition.**

</div>
