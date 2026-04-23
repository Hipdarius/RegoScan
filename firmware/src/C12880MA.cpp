// ─────────────────────────────────────────────────────────────────
// Hamamatsu C12880MA Micro-Spectrometer Driver — Implementation
//
// Bit-bangs CLK/ST lines to drive the C12880MA linear image sensor.
// All timing uses delayMicroseconds(); the full readout cycle
// completes in ≤ integration_ms_ + 4 ms and must not be interrupted.
// ─────────────────────────────────────────────────────────────────

#include "C12880MA.h"

namespace vera {

void C12880MA::init() {
    pinMode(PIN_SPEC_CLK,   OUTPUT);
    pinMode(PIN_SPEC_ST,    OUTPUT);
    pinMode(PIN_SPEC_TRG,   INPUT);
    pinMode(PIN_SPEC_VIDEO, INPUT);

    digitalWrite(PIN_SPEC_CLK, LOW);
    digitalWrite(PIN_SPEC_ST,  LOW);

    analogReadResolution(12);  // 12-bit ADC: 0–4095
}

void C12880MA::setIntegrationTime(uint16_t ms) {
    if (ms < MIN_INTEGRATION_MS) {
        ms = MIN_INTEGRATION_MS;
    } else if (ms > MAX_INTEGRATION_MS) {
        ms = MAX_INTEGRATION_MS;
    }
    integration_ms_ = ms;
}

inline void C12880MA::clockPulse() {
    digitalWrite(PIN_SPEC_CLK, HIGH);
    delayMicroseconds(CLK_HALF_PERIOD_US);
    digitalWrite(PIN_SPEC_CLK, LOW);
    delayMicroseconds(CLK_HALF_PERIOD_US);
}

void C12880MA::readSpectrum(uint16_t* buffer) {
    // ── 1. Begin integration: raise ST while clocking ───────────
    // Per datasheet, ST must go HIGH during a CLK rising edge.
    digitalWrite(PIN_SPEC_CLK, LOW);
    delayMicroseconds(CLK_HALF_PERIOD_US);

    digitalWrite(PIN_SPEC_CLK, HIGH);
    delayMicroseconds(CLK_HALF_PERIOD_US);
    digitalWrite(PIN_SPEC_ST, HIGH);  // ST rises while CLK is HIGH

    digitalWrite(PIN_SPEC_CLK, LOW);
    delayMicroseconds(CLK_HALF_PERIOD_US);

    // ── 2. Continue clocking for the integration window ─────────
    // Convert integration_ms_ to microseconds for the delay loop.
    // Each clock cycle takes 2 * CLK_HALF_PERIOD_US µs.
    const uint32_t integration_us = static_cast<uint32_t>(integration_ms_) * 1000u;
    const uint32_t us_per_clock   = 2u * CLK_HALF_PERIOD_US;
    const uint32_t integration_clocks = integration_us / us_per_clock;

    for (uint32_t c = 0; c < integration_clocks; c++) {
        clockPulse();
    }

    // ── 3. Lower ST to end integration ──────────────────────────
    digitalWrite(PIN_SPEC_ST, LOW);

    // ── 4. Shift out leading dummy pixels ───────────────────────
    for (uint16_t i = 0; i < N_LEADING_DUMMY; i++) {
        clockPulse();
    }

    // ── 5. Read N_SPEC_PIXELS valid pixels ──────────────────────
    // Sample the analog VIDEO output on each clock cycle.
    for (uint16_t i = 0; i < N_SPEC_PIXELS; i++) {
        clockPulse();
        buffer[i] = static_cast<uint16_t>(analogRead(PIN_SPEC_VIDEO));
    }

    // ── 6. Shift out trailing dummy pixel(s) ────────────────────
    // Total clocks = N_LEADING_DUMMY + N_SPEC_PIXELS + trailing.
    const uint16_t trailing = N_TOTAL_CLOCKS - N_LEADING_DUMMY - N_SPEC_PIXELS;
    for (uint16_t i = 0; i < trailing; i++) {
        clockPulse();
    }
}

uint16_t C12880MA::adaptIntegrationTime(const uint16_t* scout,
                                         uint16_t target_counts) {
    // Find the 95th percentile via partial selection. We use a simple
    // counting-sort approach over the 12-bit range — O(N + 4096) is
    // faster than O(N log N) and uses zero heap. The 5% hottest pixels
    // are excluded so a single cosmic ray hit doesn't reduce the
    // exposure time across the whole array.
    constexpr uint16_t HISTOGRAM_BINS = 4096;
    static uint16_t histogram[HISTOGRAM_BINS];
    for (uint16_t i = 0; i < HISTOGRAM_BINS; i++) histogram[i] = 0;
    for (uint16_t i = 0; i < N_SPEC_PIXELS; i++) {
        uint16_t v = scout[i];
        if (v >= HISTOGRAM_BINS) v = HISTOGRAM_BINS - 1;
        histogram[v]++;
    }

    // Walk from the top of the histogram down until 5% of pixels have
    // been counted. The bin we land on is the 95th-percentile value.
    const uint16_t skip = N_SPEC_PIXELS / 20u;  // 5% = ~14 pixels for 288
    uint32_t accumulated = 0;
    uint16_t p95 = HISTOGRAM_BINS - 1;
    for (int16_t bin = HISTOGRAM_BINS - 1; bin >= 0; bin--) {
        accumulated += histogram[bin];
        if (accumulated > skip) {
            p95 = static_cast<uint16_t>(bin);
            break;
        }
    }

    // Linear rescale: new_t = old_t * target / observed.
    // Guard against p95 == 0 (totally dark frame — push to max time).
    if (p95 == 0) {
        integration_ms_ = MAX_INTEGRATION_MS;
        return integration_ms_;
    }
    const uint32_t old_ms = integration_ms_;
    uint32_t new_ms = (old_ms * static_cast<uint32_t>(target_counts)) / static_cast<uint32_t>(p95);
    if (new_ms < MIN_INTEGRATION_MS) new_ms = MIN_INTEGRATION_MS;
    if (new_ms > MAX_INTEGRATION_MS) new_ms = MAX_INTEGRATION_MS;
    integration_ms_ = static_cast<uint16_t>(new_ms);
    return integration_ms_;
}

}  // namespace vera
