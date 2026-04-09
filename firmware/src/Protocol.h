#pragma once
// ─────────────────────────────────────────────────────────────────
// Wire Protocol Serializer
//
// Encodes one scan frame as a single-line JSON object matching the
// SensorFrame Pydantic model in scripts/bridge.py:
//
//   {
//     "v": 1,
//     "integration_time_ms": 10,
//     "ambient_temp_c": 22.3,
//     "spec": [0.123, 0.456, ...],   // 288 floats
//     "led":  [0.789, 0.012, ...],   // 12 floats
//     "lif_450lp": 0.567
//   }
//
// Uses ArduinoJson's StaticJsonDocument to avoid heap allocation.
// The entire payload (≈3 KB compact) is written in one
// Serial.println() call so the bridge sees a complete line per frame.
// ─────────────────────────────────────────────────────────────────

#include <ArduinoJson.h>
#include "Config.h"

namespace vera {

/// Raw data collected during one scan cycle.
/// All arrays are statically sized — no heap.
struct ScanFrame {
    uint16_t integration_time_ms;
    float    ambient_temp_c;
    float    spec[N_SPEC_PIXELS];       // reflectance-normalised spectra
    float    led[N_LEDS];               // per-LED reflectance
    float    lif_450lp;                 // fluorescence channel
    float    as7265x[N_AS7265X_BANDS];  // AS7265x 18-band multispectral
    bool     has_as7265x;               // true if sensor was present
};

/// Serialize a ScanFrame to JSON on Serial.
///
/// Writes one newline-terminated JSON line. Returns the number of
/// bytes written, or 0 on serialization failure (buffer overflow).
///
/// @param frame  Fully populated scan data.
/// @param stream Output stream (normally Serial).
size_t transmitFrame(const ScanFrame& frame, Print& stream);

/// Read the on-board NTC thermistor and return degrees Celsius.
/// Uses the Steinhart-Hart coefficients in Config.h.
float readTemperatureC();

/// Convert a raw 12-bit ADC count to a [0.0, 1.5] reflectance
/// value. Normalization uses the dark frame as zero and the
/// broadband frame as the white reference.
///
/// @param raw       ADC count for this pixel.
/// @param dark      Dark-frame ADC count (all lights off).
/// @param white     Broadband-frame ADC count (all LEDs on).
float normalizeReflectance(uint16_t raw, uint16_t dark, uint16_t white);

}  // namespace vera
