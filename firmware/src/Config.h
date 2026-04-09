#pragma once
// ─────────────────────────────────────────────────────────────────
// VERA Hardware Configuration
//
// Every pin assignment, timing constant, and array dimension lives
// here. The rest of the codebase references these symbols — never
// a bare literal.
//
// Pin assignments are for the ESP32-S3-DevKitC-1 dev board.
// Re-map when the custom PCB is laid out.
// ─────────────────────────────────────────────────────────────────

#include <cstdint>

namespace vera {

// ── Wire protocol version (must match bridge.py SensorFrame.v) ──
constexpr uint8_t WIRE_PROTOCOL_VERSION = 1;

// ── Serial ──────────────────────────────────────────────────────
constexpr uint32_t SERIAL_BAUD = 115200;

// ── Hamamatsu C12880MA Spectrometer ─────────────────────────────
// Directly drives the CMOS linear image sensor via three digital
// lines. The pixel clock (CLK) must toggle at ≥200 kHz for valid
// readout; the start pulse (ST) gates the integration window.
constexpr uint8_t PIN_SPEC_CLK = 4;   // pixel readout clock
constexpr uint8_t PIN_SPEC_ST  = 5;   // integration start pulse
constexpr uint8_t PIN_SPEC_TRG = 6;   // trigger / video sync
constexpr uint8_t PIN_SPEC_VIDEO = 7;  // analog video output (ADC1)

constexpr uint16_t N_SPEC_PIXELS    = 288;
// Datasheet: 87 dummy + 288 valid + 1 dummy = 376 total clock cycles
constexpr uint16_t N_TOTAL_CLOCKS   = 376;
constexpr uint16_t N_LEADING_DUMMY  = 87;

// CLK half-period in microseconds. 5 µs → 100 kHz pixel rate.
// The C12880MA specifies ≥200 kHz max; 100 kHz is conservative
// and gives the ADC more settling time per pixel.
constexpr uint16_t CLK_HALF_PERIOD_US = 5;

// Default integration time. Tunable at runtime via serial command.
// Range constrained to avoid ADC saturation and dark-current drift.
constexpr uint16_t DEFAULT_INTEGRATION_MS = 10;
constexpr uint16_t MIN_INTEGRATION_MS     = 1;
constexpr uint16_t MAX_INTEGRATION_MS     = 500;

// ── LED Illumination Array ──────────────────────────────────────
// 12 narrowband LEDs driven through MOSFETs. Each GPIO sinks the
// LED current; HIGH = on. Wavelengths match schema.LED_WAVELENGTHS_NM.
constexpr uint8_t N_LEDS = 12;
constexpr uint8_t LED_PINS[N_LEDS] = {
    15, 16, 17, 18,   // 385, 405, 450, 500 nm
     8, 36, 37, 38,   // 525, 590, 625, 660 nm
    39, 40, 41, 42,   // 730, 780, 850, 940 nm
};

// LED wavelengths in nm — indexed identically to LED_PINS.
// Logged in the JSON payload for human readability; the bridge
// relies on array position, not these labels.
constexpr uint16_t LED_WAVELENGTHS_NM[N_LEDS] = {
    385, 405, 450, 500, 525, 590, 625, 660, 730, 780, 850, 940,
};

// Settling time after switching an LED before reading the sensor.
// LEDs reach >95 % radiant flux within 1 ms; 5 ms gives margin
// for phosphor-converted emitters at 450/500 nm.
constexpr uint16_t LED_SETTLE_MS = 5;

// ── 405 nm LIF Laser ───────────────────────────────────────────
// Class 3B diode — interlock logic must disable the pin if the
// enclosure open switch is triggered (not wired on dev board).
constexpr uint8_t  PIN_LASER_405   = 10;
constexpr uint8_t  PIN_LIF_ADC     = 11;  // photodiode (ADC1)
constexpr uint16_t LASER_WARMUP_MS = 20;  // lasing threshold stabilization

// ── On-board thermistor (NTC via voltage divider) ───────────────
constexpr uint8_t PIN_TEMP_ADC = 14;

// Steinhart-Hart coefficients for a standard 10 kΩ NTC.
// Replace with measured values after bench calibration.
constexpr float THERM_A = 1.009249e-3f;
constexpr float THERM_B = 2.378405e-4f;
constexpr float THERM_C = 2.019202e-7f;
constexpr uint32_t THERM_SERIES_OHM = 10000;

// ── JSON serialization budget ───────────────────────────────────
// 288 spec floats × ~8 chars + 18 as7265x floats × ~8 chars +
// 12 led × ~8 chars + overhead ≈ 3.2 KB.
// 4480 bytes accommodates the optional AS7265x array (~150 extra
// bytes) while staying within a single Serial.write() call.
constexpr size_t JSON_BUFFER_BYTES = 4480;

// ── Measurement averaging ──────────────────────────────────────
// Number of readings to accumulate and average per measurement
// state. Improves SNR at the cost of proportionally longer scans.
constexpr uint8_t N_AVERAGES = 5;

// ── LED Temperature Compensation ────────────────────────────
// Peak wavelength shift coefficients (nm/°C) for each LED.
// Typical InGaN LEDs shift ~0.04 nm/°C; AlGaInP ~0.15 nm/°C.
// Values from datasheets; update after bench characterization.
constexpr float LED_TEMP_COEFF_NM_PER_C[N_LEDS] = {
    0.04f, 0.04f, 0.04f, 0.04f,   // 385–500 nm (InGaN)
    0.04f, 0.15f, 0.15f, 0.15f,   // 525–660 nm (AlGaInP)
    0.15f, 0.15f, 0.10f, 0.10f,   // 730–940 nm (AlGaAs/GaAs)
};
constexpr float LED_REF_TEMP_C = 25.0f;  // Reference temperature

// ── AS7265x Triad Spectral Sensor (I²C) ─────────────────────
// 18-band sensor covering 410–940 nm as secondary comparison arm.
constexpr uint8_t PIN_AS7265X_SDA   = 47;
constexpr uint8_t PIN_AS7265X_SCL   = 48;
constexpr uint8_t AS7265X_I2C_ADDR  = 0x49;
constexpr uint8_t N_AS7265X_BANDS   = 18;

// ── SD Card (SPI) ──────────────────────────────────────────────
constexpr uint8_t PIN_SD_CS = 13;

// ── OLED Display (I²C, shared bus with AS7265x) ───────────────
constexpr uint8_t PIN_OLED_SDA = 47;  // shared with AS7265x
constexpr uint8_t PIN_OLED_SCL = 48;
constexpr uint8_t OLED_WIDTH   = 128;
constexpr uint8_t OLED_HEIGHT  = 64;

// ── Scan state machine ─────────────────────────────────────────
// Minimum time the main loop idles between full scan sequences
// when running in continuous mode (0 = one-shot triggered by SCAN).
constexpr uint32_t SCAN_INTERVAL_MS = 0;

}  // namespace vera
