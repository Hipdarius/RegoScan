// ─────────────────────────────────────────────────────────────────
// LED Array + 405 nm LIF Laser Driver — Implementation
//
// Controls 12 narrowband LEDs and the 405 nm Class 3B laser diode.
// Every public method enforces the invariant that the laser pin is
// driven LOW unless laserOn() was explicitly called.
// ─────────────────────────────────────────────────────────────────

#include "Illumination.h"

namespace vera {

void Illumination::init() {
    for (uint8_t i = 0; i < N_LEDS; i++) {
        pinMode(LED_PINS[i], OUTPUT);
        digitalWrite(LED_PINS[i], LOW);
    }
    pinMode(PIN_LASER_405, OUTPUT);
    digitalWrite(PIN_LASER_405, LOW);
    pinMode(PIN_LED_1050, OUTPUT);
    digitalWrite(PIN_LED_1050, LOW);
}

void Illumination::selectLed(uint8_t idx) {
    // Turn all LEDs off first
    for (uint8_t i = 0; i < N_LEDS; i++) {
        digitalWrite(LED_PINS[i], LOW);
    }

    // Bounds-check before enabling the selected LED
    if (idx < N_LEDS) {
        digitalWrite(LED_PINS[idx], HIGH);
    }
}

void Illumination::allLedsOn() {
    for (uint8_t i = 0; i < N_LEDS; i++) {
        digitalWrite(LED_PINS[i], HIGH);
    }
}

void Illumination::allOff() {
    for (uint8_t i = 0; i < N_LEDS; i++) {
        digitalWrite(LED_PINS[i], LOW);
    }
    digitalWrite(PIN_LASER_405, LOW);
    digitalWrite(PIN_LED_1050, LOW);
}

void Illumination::laserOn() {
    digitalWrite(PIN_LASER_405, HIGH);
}

void Illumination::laserOff() {
    digitalWrite(PIN_LASER_405, LOW);
}

void Illumination::led1050On() {
    digitalWrite(PIN_LED_1050, HIGH);
}

void Illumination::led1050Off() {
    digitalWrite(PIN_LED_1050, LOW);
}

}  // namespace vera
