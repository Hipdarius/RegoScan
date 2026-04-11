// ─────────────────────────────────────────────────────────────────
// ADS1115 16-bit ADC — Implementation
//
// Single-shot, single-ended reads on AIN0. The conversion takes
// ~8 ms at 128 SPS (default). We poll the OS bit in the config
// register to detect conversion completion.
//
// Register map (datasheet SBAS444C, Table 7):
//   0x00  Conversion register (16-bit, read-only)
//   0x01  Config register     (16-bit, read/write)
//
// Config register bits (default 0x8583):
//   [15]    OS        1 = start single conversion
//   [14:12] MUX       100 = AIN0 vs GND (single-ended)
//   [11:9]  PGA       001 = ±4.096 V (0.125 mV/LSB)
//   [8]     MODE      1 = single-shot
//   [7:5]   DR        100 = 128 SPS
//   [4:0]   COMP      11111 = comparator disabled
// ─────────────────────────────────────────────────────────────────

#include "ADS1115.h"
#include <Arduino.h>

namespace vera {

// Register addresses
static constexpr uint8_t REG_CONVERSION = 0x00;
static constexpr uint8_t REG_CONFIG     = 0x01;

// Config word: OS=1, MUX=100 (AIN0), PGA=001 (±4.096V), MODE=1,
//              DR=100 (128 SPS), COMP=11111 (disabled)
static constexpr uint16_t CONFIG_SINGLE_AIN0 = 0xC383;

// PGA scale factor: ±4.096 V / 32768 = 0.125 mV/LSB
static constexpr float MV_PER_LSB = 0.125f;

void ADS1115::init() {
    // I²C bus is already initialized by AS7265x or OLED — just probe
    Wire.beginTransmission(ADS1115_I2C_ADDR);
    m_connected = (Wire.endTransmission() == 0);

    if (m_connected) {
        Serial.println("{\"event\":\"ads1115_ok\"}");
    } else {
        Serial.println("{\"event\":\"ads1115_absent\"}");
    }
}

void ADS1115::writeReg(uint8_t reg, uint16_t value) {
    Wire.beginTransmission(ADS1115_I2C_ADDR);
    Wire.write(reg);
    Wire.write(static_cast<uint8_t>(value >> 8));
    Wire.write(static_cast<uint8_t>(value & 0xFF));
    Wire.endTransmission();
}

uint16_t ADS1115::readReg(uint8_t reg) {
    Wire.beginTransmission(ADS1115_I2C_ADDR);
    Wire.write(reg);
    Wire.endTransmission(false);
    Wire.requestFrom(ADS1115_I2C_ADDR, static_cast<uint8_t>(2));

    uint16_t result = 0;
    if (Wire.available() >= 2) {
        result = static_cast<uint16_t>(Wire.read()) << 8;
        result |= static_cast<uint16_t>(Wire.read());
    }
    return result;
}

int16_t ADS1115::readRaw() {
    if (!m_connected) return 0;

    // Start single-shot conversion
    writeReg(REG_CONFIG, CONFIG_SINGLE_AIN0);

    // Poll until conversion complete (OS bit = 1 in config register)
    // Timeout after 20 ms (conversion takes ~8 ms at 128 SPS)
    uint32_t start = millis();
    while (millis() - start < 20) {
        uint16_t cfg = readReg(REG_CONFIG);
        if (cfg & 0x8000) break;  // OS bit set = conversion done
        delayMicroseconds(500);
    }

    return static_cast<int16_t>(readReg(REG_CONVERSION));
}

float ADS1115::readMillivolts() {
    return static_cast<float>(readRaw()) * MV_PER_LSB;
}

float ADS1115::readNormalized() {
    float mv = readMillivolts();
    float normalized = mv / 3300.0f;
    // Clamp to [0.0, 1.5] to match the reflectance range
    if (normalized < 0.0f) normalized = 0.0f;
    if (normalized > 1.5f) normalized = 1.5f;
    return normalized;
}

}  // namespace vera
