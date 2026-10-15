# VERA — data format

The canonical measurement table is a CSV with one row per probe
measurement and a fixed column order defined by `src/vera/schema.py`.

## Sensor modes

| Mode | Spectrometer | Triad | SWIR | Total feature width |
|---|:---:|:---:|:---:|:---:|
| `full` | 288 | — | 2 | 303 |
| `multispectral` | — | 18 | 2 | 33 |
| `combined` | 288 | 18 | 2 | 321 |

The CSV reader (`vera.io_csv.read_measurements_csv`) auto-detects the
mode from the column header — no `--sensor-mode` flag needed for
loading.

## Column order

| Group | Columns | Count |
|---|---|---|
| Identifier | `sample_id`, `measurement_id` | 2 |
| Labels | `mineral_class`, `ilmenite_fraction` | 2 |
| Spectrometer | `spec_000` … `spec_287` | 288 |
| Triad | `as7_410` … `as7_940` | 18 |
| SWIR | `swir_940`, `swir_1050` | 2 |
| LED duty | `led_385` … `led_1050` | 12 |
| LIF | `lif_450lp` | 1 |
| Telemetry | `temp_c`, `integ_us` | 2 |

The label columns are populated by the synth generator and by
hand-annotation passes; they're absent from frames produced by the
firmware bridge in real-time mode.

## Schema versioning

`vera.schema.SCHEMA_VERSION` is the wire-format version shared by the
firmware (`firmware/src/Protocol.cpp`), the bridge (`scripts/bridge.py`),
the trainer, and the inference engine. **Any change to the column
order, the column names, or the sensor-mode tables is a breaking
change** and requires bumping `SCHEMA_VERSION`. Layers that load a
model trained against a different `SCHEMA_VERSION` fail fast with a
clear message rather than silently mis-aligning features.

## Reflectance ranges

All spectrometer / triad / SWIR / LED / LIF values are normalised to
`[0, 1]` reflectance after the calibration pipeline
(`src/vera/calibrate.py`). Raw counts from the firmware are 12-bit
(0 – 4095); raw triad readings are IEEE 754 floats from the AS7265x
register protocol.
