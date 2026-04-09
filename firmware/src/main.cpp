// ─────────────────────────────────────────────────────────────────
// VERA ESP32-S3 Firmware — Non-blocking Acquisition State Machine
//
// Scan sequence:
//   IDLE → DARK_FRAME → BROADBAND → NARROWBAND (×12) → LIF → TRANSMIT → IDLE
//
// The loop() never blocks on delay(). Sensor readouts (C12880MA) use
// delayMicroseconds() internally for clock bit-banging, which is
// acceptable: each readout is ≤4 ms and cannot be split across ticks.
//
// Trigger: send "SCAN\n" over Serial at 115200 baud.
// ─────────────────────────────────────────────────────────────────

#include <Arduino.h>
#include "Config.h"
#include "AS7265x.h"
#include "C12880MA.h"
#include "Illumination.h"
#include "Protocol.h"

using namespace vera;

// ── State machine ───────────────────────────────────────────────
enum class State : uint8_t {
    IDLE,
    DARK_FRAME,
    BROADBAND,
    MULTISPECTRAL,
    NARROWBAND,
    LIF,
    TRANSMIT,
};

static State          g_state          = State::IDLE;
static uint32_t       g_state_enter_ms = 0;  // millis() when current state began
static uint8_t        g_led_idx        = 0;  // which LED in NARROWBAND sweep

// ── Hardware drivers ────────────────────────────────────────────
static C12880MA       g_spec;
static Illumination   g_light;
static AS7265x        g_as7265x;

// ── Scan data (static allocation — no heap) ─────────────────────
static uint16_t       g_dark_raw[N_SPEC_PIXELS];
static uint16_t       g_broad_raw[N_SPEC_PIXELS];
static uint16_t       g_narrow_raw[N_LEDS][N_SPEC_PIXELS];
static uint16_t       g_lif_raw = 0;
static float          g_as7265x_data[N_AS7265X_BANDS];
static bool           g_as7265x_present = false;
static ScanFrame      g_frame;

// ── Averaging accumulators ──────────────────────────────────────
// 32-bit accumulators to hold the sum of N_AVERAGES 12-bit readings
// without overflow (5 * 4095 = 20475, fits in uint32_t easily).
static uint32_t       g_dark_acc[N_SPEC_PIXELS];
static uint32_t       g_broad_acc[N_SPEC_PIXELS];
static uint32_t       g_narrow_acc[N_LEDS][N_SPEC_PIXELS];
static uint32_t       g_lif_acc = 0;
static uint8_t        g_avg_idx = 0;  // current averaging iteration

// ── Serial command buffer ───────────────────────────────────────
static constexpr size_t CMD_BUF_SIZE = 32;
static char   g_cmd_buf[CMD_BUF_SIZE];
static size_t g_cmd_len = 0;

// ── Helpers ─────────────────────────────────────────────────────

static void enterState(State next) {
    g_state = next;
    g_state_enter_ms = millis();
}

static uint32_t stateElapsedMs() {
    return millis() - g_state_enter_ms;
}

/// Zero all averaging accumulators and reset the index counter.
static void resetAccumulators() {
    for (uint16_t i = 0; i < N_SPEC_PIXELS; i++) {
        g_dark_acc[i]  = 0;
        g_broad_acc[i] = 0;
    }
    for (uint8_t j = 0; j < N_LEDS; j++) {
        for (uint16_t i = 0; i < N_SPEC_PIXELS; i++) {
            g_narrow_acc[j][i] = 0;
        }
    }
    g_lif_acc = 0;
    g_avg_idx = 0;
}

/// Accumulate a spectrum reading into a 32-bit accumulator array.
static void accumulateSpectrum(uint32_t* acc, const uint16_t* raw) {
    for (uint16_t i = 0; i < N_SPEC_PIXELS; i++) {
        acc[i] += raw[i];
    }
}

/// Divide accumulator by N_AVERAGES and store as uint16_t.
static void finalizeSpectrum(uint16_t* dst, const uint32_t* acc) {
    for (uint16_t i = 0; i < N_SPEC_PIXELS; i++) {
        dst[i] = static_cast<uint16_t>(acc[i] / N_AVERAGES);
    }
}

/// Check Serial for a complete line. Returns true if a command
/// was received and placed in g_cmd_buf (null-terminated).
static bool pollSerialCommand() {
    while (Serial.available()) {
        char c = static_cast<char>(Serial.read());
        if (c == '\n' || c == '\r') {
            if (g_cmd_len > 0) {
                g_cmd_buf[g_cmd_len] = '\0';
                g_cmd_len = 0;
                return true;
            }
            continue;
        }
        if (g_cmd_len < CMD_BUF_SIZE - 1) {
            g_cmd_buf[g_cmd_len++] = c;
        }
    }
    return false;
}

// ── Setup ───────────────────────────────────────────────────────

void setup() {
    Serial.begin(SERIAL_BAUD);
    while (!Serial && millis() < 3000) { /* wait for USB CDC */ }

    g_spec.init();
    g_light.init();
    g_as7265x.init();

    Serial.println("{\"event\":\"boot\",\"v\":" + String(WIRE_PROTOCOL_VERSION) + "}");
}

// ── Main Loop ───────────────────────────────────────────────────

void loop() {
    switch (g_state) {

    // ── IDLE: wait for "SCAN" command ───────────────────────────
    case State::IDLE:
        if (pollSerialCommand()) {
            if (strncmp(g_cmd_buf, "SCAN", 4) == 0) {
                resetAccumulators();
                enterState(State::DARK_FRAME);
            }
            // Unknown commands silently ignored — no crash path.
        }
        break;

    // ── DARK FRAME: all lights off, read baseline ───────────────
    // Accumulate N_AVERAGES readings then average.
    case State::DARK_FRAME: {
        g_light.allOff();
        uint16_t tmp[N_SPEC_PIXELS];
        g_spec.readSpectrum(tmp);
        accumulateSpectrum(g_dark_acc, tmp);
        g_avg_idx++;

        if (g_avg_idx >= N_AVERAGES) {
            finalizeSpectrum(g_dark_raw, g_dark_acc);
            g_avg_idx = 0;
            enterState(State::BROADBAND);
        }
        break;
    }

    // ── BROADBAND: all LEDs on, read white reference ────────────
    // Accumulate N_AVERAGES readings then average.
    case State::BROADBAND: {
        if (stateElapsedMs() < LED_SETTLE_MS) break;  // wait for LEDs
        if (g_avg_idx == 0 && stateElapsedMs() >= LED_SETTLE_MS) {
            // First entry after settle: turn LEDs on and come back
            g_light.allLedsOn();
            // Small re-enter to ensure LEDs are stable before first read
            if (stateElapsedMs() < LED_SETTLE_MS + 1) break;
        }

        uint16_t tmp[N_SPEC_PIXELS];
        g_spec.readSpectrum(tmp);
        accumulateSpectrum(g_broad_acc, tmp);
        g_avg_idx++;

        if (g_avg_idx >= N_AVERAGES) {
            finalizeSpectrum(g_broad_raw, g_broad_acc);
            g_light.allOff();
            g_led_idx = 0;
            g_avg_idx = 0;
            enterState(State::MULTISPECTRAL);
        }
        break;
    }

    // ── MULTISPECTRAL: read AS7265x 18-band sensor if present ───
    case State::MULTISPECTRAL: {
        if (g_as7265x.isConnected()) {
            g_as7265x.readAllBands(g_as7265x_data);
            g_as7265x_present = true;
        } else {
            // Sensor absent — zero the buffer and flag it
            for (uint8_t i = 0; i < N_AS7265X_BANDS; i++) {
                g_as7265x_data[i] = 0.0f;
            }
            g_as7265x_present = false;
        }
        enterState(State::NARROWBAND);
        break;
    }

    // ── NARROWBAND: cycle through 12 LEDs one at a time ─────────
    // For each LED, accumulate N_AVERAGES readings then average.
    case State::NARROWBAND: {
        if (stateElapsedMs() < LED_SETTLE_MS) break;

        // On first averaging iteration for this LED, turn it on
        if (g_avg_idx == 0) {
            g_light.selectLed(g_led_idx);
            // Re-enter to allow settle time after selecting LED
            enterState(State::NARROWBAND);
            break;
        }

        uint16_t tmp[N_SPEC_PIXELS];
        g_spec.readSpectrum(tmp);
        accumulateSpectrum(g_narrow_acc[g_led_idx], tmp);
        g_avg_idx++;

        if (g_avg_idx > N_AVERAGES) {
            // g_avg_idx started at 1 after LED select, so > not >=
            finalizeSpectrum(g_narrow_raw[g_led_idx], g_narrow_acc[g_led_idx]);
            g_light.allOff();
            g_led_idx++;
            g_avg_idx = 0;

            if (g_led_idx < N_LEDS) {
                enterState(State::NARROWBAND);
            } else {
                enterState(State::LIF);
            }
        }
        break;
    }

    // ── LIF: 405 nm laser → photodiode ──────────────────────────
    // Accumulate N_AVERAGES readings then average.
    case State::LIF:
        if (stateElapsedMs() == 0) {
            g_light.laserOn();
            g_avg_idx = 0;
            g_lif_acc = 0;
            break;
        }
        if (stateElapsedMs() < LASER_WARMUP_MS) break;

        g_lif_acc += static_cast<uint32_t>(analogRead(PIN_LIF_ADC));
        g_avg_idx++;

        if (g_avg_idx >= N_AVERAGES) {
            g_lif_raw = static_cast<uint16_t>(g_lif_acc / N_AVERAGES);
            g_light.laserOff();
            enterState(State::TRANSMIT);
        }
        break;

    // ── TRANSMIT: normalize, pack, serialize ────────────────────
    case State::TRANSMIT: {
        g_frame.integration_time_ms = g_spec.integrationTimeMs();
        g_frame.ambient_temp_c      = readTemperatureC();

        // Dark-subtract and normalize each spectral channel
        for (uint16_t i = 0; i < N_SPEC_PIXELS; i++) {
            g_frame.spec[i] = normalizeReflectance(
                g_broad_raw[i], g_dark_raw[i], g_broad_raw[i]
            );
        }

        // Per-LED reflectance: average over a narrow window around
        // the LED's center wavelength. For now, use the full-spectrum
        // average as a placeholder until we identify the exact pixel
        // indices for each LED band from the calibration sheet.
        for (uint8_t j = 0; j < N_LEDS; j++) {
            float sum = 0.0f;
            for (uint16_t i = 0; i < N_SPEC_PIXELS; i++) {
                sum += normalizeReflectance(
                    g_narrow_raw[j][i], g_dark_raw[i], g_broad_raw[i]
                );
            }
            g_frame.led[j] = sum / static_cast<float>(N_SPEC_PIXELS);
        }

        // LIF: normalize against dark baseline on the photodiode
        g_frame.lif_450lp = static_cast<float>(g_lif_raw) / 4095.0f;

        // AS7265x multispectral data
        g_frame.has_as7265x = g_as7265x_present;
        if (g_as7265x_present) {
            for (uint8_t k = 0; k < N_AS7265X_BANDS; k++) {
                g_frame.as7265x[k] = g_as7265x_data[k];
            }
        }

        transmitFrame(g_frame, Serial);
        enterState(State::IDLE);
        break;
    }

    }  // switch
}
