#pragma once
// ─────────────────────────────────────────────────────────────────
// Hamamatsu C12880MA Micro-Spectrometer Driver
//
// The C12880MA is a CMOS linear image sensor with 288 active pixels
// covering 340–850 nm. It is read by bit-banging three digital lines
// (CLK, ST, TRG) and sampling the analog VIDEO output once per clock.
//
// Timing (from datasheet):
//   1. Raise ST high while clocking CLK to begin integration.
//   2. After the desired integration window, lower ST.
//   3. Continue clocking: 87 dummy pixels are shifted out first,
//      then 288 valid pixels, then 1 trailing dummy.
//   4. TRG goes high when valid pixel data begins — we use this
//      as the "start sampling" signal in readSpectrum().
//
// All timing-critical sections use delayMicroseconds() which is
// acceptable: the entire readout is ≤4 ms at 100 kHz and runs
// inside a single state-machine tick, not across loop() iterations.
// ─────────────────────────────────────────────────────────────────

#include <Arduino.h>
#include "Config.h"

namespace vera {

class C12880MA {
public:
    /// Configure GPIO pin modes and set CLK/ST to idle-low.
    void init();

    /// Set the integration window in milliseconds.
    /// Clamped to [MIN_INTEGRATION_MS, MAX_INTEGRATION_MS].
    void setIntegrationTime(uint16_t ms);

    /// Current integration time setting.
    uint16_t integrationTimeMs() const { return integration_ms_; }

    /// Execute a full read cycle: integrate → shift out → sample.
    ///
    /// @param buffer  Must point to at least N_SPEC_PIXELS uint16_t.
    ///                Filled with 12-bit ADC counts (0–4095) for
    ///                pixels 0..287 (340–850 nm).
    ///
    /// Blocks for approximately integration_ms_ + 4 ms (shift-out
    /// at 100 kHz × 376 clocks). This is intentional: the sensor
    /// requires continuous clocking during readout, so we cannot
    /// yield to loop() mid-read.
    void readSpectrum(uint16_t* buffer);

    /// Pick a new integration time that targets the upper third of the
    /// ADC range without saturating. Call after a "scout" read with the
    /// previous integration time. Returns the new setting.
    ///
    /// Algorithm: find the 95th-percentile pixel value and rescale
    /// integration time linearly so it lands at ``target_counts``.
    /// Bounded by [MIN_INTEGRATION_MS, MAX_INTEGRATION_MS]. The 5%
    /// hottest pixels are excluded so a single cosmic ray hit doesn't
    /// crater the exposure.
    ///
    /// @param scout       Last buffer read with integrationTimeMs().
    /// @param target_counts  Desired 95th-percentile count (default 2800
    ///                    of 4095 → ~70%, leaving headroom).
    /// @return New integration time in ms (also stored internally).
    uint16_t adaptIntegrationTime(const uint16_t* scout,
                                   uint16_t target_counts = 2800);

private:
    uint16_t integration_ms_ = DEFAULT_INTEGRATION_MS;

    /// One CLK cycle: drive high, hold, drive low, hold.
    /// Total period = 2 × CLK_HALF_PERIOD_US microseconds.
    inline void clockPulse();
};

}  // namespace vera
