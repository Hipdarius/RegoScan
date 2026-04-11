#pragma once
// ─────────────────────────────────────────────────────────────────
// ADS1115 16-bit ADC Driver (I²C)
//
// Reads the SWIR InGaAs photodiode (Hamamatsu G12180-010A) through
// a transimpedance amplifier (OPA380). The ADS1115 provides 16-bit
// resolution at up to 860 SPS — far better than the ESP32-S3's
// noisy 12-bit SAR ADC for the nanoamp-level photocurrents from
// the InGaAs photodiode.
//
// Default config: single-shot, AIN0, PGA ±4.096 V, 128 SPS.
// ─────────────────────────────────────────────────────────────────

#include <Wire.h>
#include "Config.h"

namespace vera {

class ADS1115 {
public:
    /// Initialize I²C communication (shares bus with AS7265x + OLED).
    void init();

    /// Returns true if the ADS1115 responds on the I²C bus.
    bool isConnected() const { return m_connected; }

    /// Read a single-ended voltage from AIN0 (photodiode TIA output).
    /// Returns the raw 16-bit signed value, or 0 if not connected.
    int16_t readRaw();

    /// Read voltage in millivolts (with PGA ±4.096 V → 0.125 mV/LSB).
    float readMillivolts();

    /// Read and normalize to [0.0, 1.0] assuming full-scale = 3300 mV.
    float readNormalized();

private:
    bool m_connected = false;

    /// Write a 16-bit value to a register.
    void writeReg(uint8_t reg, uint16_t value);

    /// Read a 16-bit value from a register.
    uint16_t readReg(uint8_t reg);
};

}  // namespace vera
