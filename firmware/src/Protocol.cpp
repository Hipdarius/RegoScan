// ---------------------------------------------------------------------------
// Wire Protocol Serializer - Implementation
//
// Encodes ScanFrame as a single-line JSON object and provides sensor utility
// functions (temperature reading, reflectance normalization). The serializer
// streams directly to Print, so it does not allocate a JSON document on heap or
// stack.
// ---------------------------------------------------------------------------

#include "Protocol.h"
#include <Arduino.h>
#include <math.h>

namespace vera {

namespace {

size_t printFloatArray(Print& stream, const float* values, uint16_t count) {
    size_t bytes = stream.print('[');
    for (uint16_t i = 0; i < count; i++) {
        if (i > 0) {
            bytes += stream.print(',');
        }
        bytes += stream.print(values[i], 6);
    }
    bytes += stream.print(']');
    return bytes;
}

}  // namespace

size_t transmitFrame(const ScanFrame& frame, Print& stream) {
    size_t bytes = 0;

    bytes += stream.print('{');
    bytes += stream.print("\"v\":");
    bytes += stream.print(static_cast<unsigned int>(WIRE_PROTOCOL_VERSION));
    bytes += stream.print(",\"integration_time_ms\":");
    bytes += stream.print(static_cast<unsigned int>(frame.integration_time_ms));
    bytes += stream.print(",\"ambient_temp_c\":");
    bytes += stream.print(frame.ambient_temp_c, 3);

    bytes += stream.print(",\"spec\":");
    bytes += printFloatArray(stream, frame.spec, N_SPEC_PIXELS);

    bytes += stream.print(",\"led\":");
    bytes += printFloatArray(stream, frame.led, N_LEDS);

    bytes += stream.print(",\"lif_450lp\":");
    bytes += stream.print(frame.lif_450lp, 6);

    if (frame.has_swir) {
        bytes += stream.print(",\"swir\":");
        bytes += printFloatArray(stream, frame.swir, N_SWIR_CHANNELS);
    }

    if (frame.has_as7265x) {
        bytes += stream.print(",\"as7\":");
        bytes += printFloatArray(stream, frame.as7265x, N_AS7265X_BANDS);
    }

    bytes += stream.print('}');
    bytes += stream.println();
    return bytes;
}

float readTemperatureC() {
    const int raw = analogRead(PIN_TEMP_ADC);

    // ADC voltage (12-bit, 3.3 V reference)
    const float voltage = static_cast<float>(raw) * 3.3f / 4095.0f;

    // Resistance of NTC via voltage divider:
    // Vout = Vcc * R_ntc / (R_series + R_ntc)
    // => R_ntc = R_series * Vout / (Vcc - Vout)
    //
    // Guard against division by zero when voltage is close to 3.3 V.
    if (voltage >= 3.29f) {
        return 150.0f;  // sensor shorted or disconnected - return sentinel
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
    // Guard: if white == dark, the reference is degenerate.
    if (white == dark) {
        return 0.0f;
    }

    const float numerator = static_cast<float>(raw) - static_cast<float>(dark);
    const float denominator = static_cast<float>(white) - static_cast<float>(dark);
    float result = numerator / denominator;

    // Clamp to [0.0, 1.5].
    if (result < 0.0f) {
        result = 0.0f;
    } else if (result > 1.5f) {
        result = 1.5f;
    }
    return result;
}

}  // namespace vera
