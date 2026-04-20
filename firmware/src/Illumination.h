#pragma once
// ─────────────────────────────────────────────────────────────────
// LED Array + 405 nm LIF Laser Driver
//
// Controls 12 narrowband LEDs (385–940 nm) driven through N-channel
// MOSFETs, plus the 405 nm Class 3B laser diode for fluorescence.
//
// Safety: the laser pin is forced LOW in init() and allOff().
// A hardware interlock on the enclosure lid switch should be wired
// in series with the laser MOSFET gate — this driver does not
// replace that physical safeguard.
// ─────────────────────────────────────────────────────────────────

#include <Arduino.h>
#include "Config.h"

namespace vera {

class Illumination {
public:
    /// Configure all LED and laser pins as OUTPUT, drive LOW.
    void init();

    /// Turn a single LED on by index (0..11). All others OFF.
    /// Index maps to LED_WAVELENGTHS_NM[idx].
    void selectLed(uint8_t idx);

    /// Turn ALL 12 LEDs on simultaneously (broadband flood).
    void allLedsOn();

    /// Turn all LEDs and the laser OFF. Safe state.
    void allOff();

    /// Arm the 405 nm laser. Caller must wait LASER_WARMUP_MS
    /// before reading the LIF photodiode.
    void laserOn();

    /// Disarm the laser immediately.
    void laserOff();

    /// Enable the dedicated 1050 nm NIR LED for SWIR channel 2.
    /// This LED is wired to PIN_LED_1050 (separate from the 12-band
    /// narrowband array) because the InGaAs photodiode requires a
    /// distinct emitter beyond the C12880MA cutoff.
    void led1050On();

    /// Disable the 1050 nm NIR LED.
    void led1050Off();
};

}  // namespace vera
