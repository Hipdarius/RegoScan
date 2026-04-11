// ─────────────────────────────────────────────────────────────────
// Wire Protocol Serializer — Implementation
//
// Encodes ScanFrame as a single-line JSON object and provides
// sensor utility functions (temperature reading, reflectance
// normalization). Zero heap allocation throughout.
// ─────────────────────────────────────────────────────────────────

#include "Protocol.h"
#include <Arduino.h>
#include <math.h>

namespace vera {

size_t transmitFrame(const ScanFrame& frame, Print& stream) {
    JsonDocument doc;

    doc["v"]                   = WIRE_PROTOCOL_VERSION;
    doc["integration_time_ms"] = frame.integration_time_ms;
    doc["ambient_temp_c"]      = frame.ambient_temp_c;

    // Spectral array — 288 floats
    JsonArray spec = doc["spec"].to<JsonArray>();
    for (uint16_t i = 0; i < N_SPEC_PIXELS; i++) {
        spec.add(frame.spec[i]);
    }

    // Per-LED reflectance — 12 floats
    JsonArray led = doc["led"].to<JsonArray>();
    for (uint8_t j = 0; j < N_LEDS; j++) {
        led.add(frame.led[j]);
    }

    // LIF fluorescence channel
    doc["lif_450lp"] = frame.lif_450lp;

    // SWIR InGaAs photodiode (only when ADS1115 is present)
    if (frame.has_swir) {
        JsonArray swir = doc["swir"].to<JsonArray>();
        for (uint8_t k = 0; k < N_SWIR_CHANNELS; k++) {
            swir.add(frame.swir[k]);
        }
    }

    // AS7265x 18-band multispectral (only when sensor is present)
    if (frame.has_as7265x) {
        JsonArray as7 = doc["as7"].to<JsonArray>();
        for (uint8_t k = 0; k < N_AS7265X_BANDS; k++) {
            as7.add(frame.as7265x[k]);
        }
    }

    // Serialize as a single line
    size_t bytes = serializeJson(doc, stream);
    if (bytes == 0) {
        return 0;  // serialization failure (buffer overflow)
    }
    stream.println();
    return bytes + 2;  // +2 for \r\n from println()
}

float readTemperatureC() {
    const int raw = analogRead(PIN_TEMP_ADC);

    // ADC voltage (12-bit, 3.3 V reference)
    const float voltage = static_cast<float>(raw) * 3.3f / 4095.0f;

    // Resistance of NTC via voltage divider:
    // Vout = Vcc * R_ntc / (R_series + R_ntc)
    // => R_ntc = R_series * Vout / (Vcc - Vout)
    //
    // Guard against division by zero when voltage ≈ 3.3 V
    if (voltage >= 3.29f) {
        return 150.0f;  // sensor shorted or disconnected — return sentinel
    }
    const float r_ntc = static_cast<float>(THERM_SERIES_OHM) * voltage / (3.3f - voltage);

    // Steinhart-Hart equation:
    //   1/T = A + B*ln(R) + C*(ln(R))^3
    const float ln_r = logf(r_ntc);
    const float inv_t = THERM_A + THERM_B * ln_r + THERM_C * ln_r * ln_r * ln_r;

    // Convert Kelvin to Celsius
    return (1.0f / inv_t) - 273.15f;
}

float normalizeReflectance(uint16_t raw, uint16_t dark, uint16_t white) {
    // Guard: if white == dark, the reference is degenerate
    if (white == dark) {
        return 0.0f;
    }

    const float numerator   = static_cast<float>(raw)   - static_cast<float>(dark);
    const float denominator = static_cast<float>(white)  - static_cast<float>(dark);
    float result = numerator / denominator;

    // Clamp to [0.0, 1.5]
    if (result < 0.0f) {
        result = 0.0f;
    } else if (result > 1.5f) {
        result = 1.5f;
    }
    return result;
}

}  // namespace vera
