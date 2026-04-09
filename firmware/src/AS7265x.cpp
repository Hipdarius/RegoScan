// -----------------------------------------------------------------
// AS7265x Triad Spectral Sensor Driver -- Implementation
//
// Implements the virtual-register I2C interface for the AMS AS7265x
// 18-channel spectral sensor. Reads calibrated floating-point data
// (IEEE 754, big-endian) from all three dies sequentially.
//
// The virtual register protocol requires polling status bits before
// every read/write -- this is inherent to the sensor design and
// cannot be avoided without risking bus errors.
// -----------------------------------------------------------------

#include "AS7265x.h"
#include <Wire.h>

namespace vera {

// AS7265x virtual register interface constants
static constexpr uint8_t STATUS_REG = 0x00;
static constexpr uint8_t WRITE_REG  = 0x01;
static constexpr uint8_t READ_REG   = 0x02;

// Device select register
static constexpr uint8_t DEV_SELECT_REG = 0x4F;

// Calibrated data start registers for each device
// AS72651 (UV): 0x14-0x2B, AS72652 (VIS): 0x14-0x2B, AS72653 (NIR): 0x14-0x2B
static constexpr uint8_t CAL_DATA_START = 0x14;

void AS7265x::init() {
    Wire.begin(PIN_AS7265X_SDA, PIN_AS7265X_SCL);
    Wire.setClock(400000);  // 400 kHz I2C fast mode
}

bool AS7265x::isConnected() {
    Wire.beginTransmission(AS7265X_I2C_ADDR);
    return Wire.endTransmission() == 0;
}

// Read a virtual register from the AS7265x
static uint8_t readVirtualReg(uint8_t reg) {
    // Wait for WRITE bit to clear (sensor ready to accept command)
    uint8_t status;
    do {
        Wire.beginTransmission(AS7265X_I2C_ADDR);
        Wire.write(STATUS_REG);
        Wire.endTransmission();
        Wire.requestFrom(AS7265X_I2C_ADDR, (uint8_t)1);
        status = Wire.read();
    } while (status & 0x02);  // bit 1 = TX_VALID (write pending)

    // Write the register address to read
    Wire.beginTransmission(AS7265X_I2C_ADDR);
    Wire.write(WRITE_REG);
    Wire.write(reg);
    Wire.endTransmission();

    // Wait for READ bit to set (data available)
    do {
        Wire.beginTransmission(AS7265X_I2C_ADDR);
        Wire.write(STATUS_REG);
        Wire.endTransmission();
        Wire.requestFrom(AS7265X_I2C_ADDR, (uint8_t)1);
        status = Wire.read();
    } while (!(status & 0x01));  // bit 0 = RX_VALID (data ready)

    // Read the data byte
    Wire.beginTransmission(AS7265X_I2C_ADDR);
    Wire.write(READ_REG);
    Wire.endTransmission();
    Wire.requestFrom(AS7265X_I2C_ADDR, (uint8_t)1);
    return Wire.read();
}

// Write a virtual register on the AS7265x
static void writeVirtualReg(uint8_t reg, uint8_t value) {
    uint8_t status;
    do {
        Wire.beginTransmission(AS7265X_I2C_ADDR);
        Wire.write(STATUS_REG);
        Wire.endTransmission();
        Wire.requestFrom(AS7265X_I2C_ADDR, (uint8_t)1);
        status = Wire.read();
    } while (status & 0x02);

    // Set write bit (bit 7) and register address
    Wire.beginTransmission(AS7265X_I2C_ADDR);
    Wire.write(WRITE_REG);
    Wire.write(reg | 0x80);
    Wire.endTransmission();

    // Wait for write to complete
    do {
        Wire.beginTransmission(AS7265X_I2C_ADDR);
        Wire.write(STATUS_REG);
        Wire.endTransmission();
        Wire.requestFrom(AS7265X_I2C_ADDR, (uint8_t)1);
        status = Wire.read();
    } while (status & 0x02);

    Wire.beginTransmission(AS7265X_I2C_ADDR);
    Wire.write(WRITE_REG);
    Wire.write(value);
    Wire.endTransmission();
}

// Read a calibrated float (IEEE 754, big-endian) from 4 consecutive registers
static float readCalibratedFloat(uint8_t startReg) {
    uint8_t bytes[4];
    for (uint8_t i = 0; i < 4; i++) {
        bytes[i] = readVirtualReg(startReg + i);
    }
    // Big-endian IEEE 754 to float
    uint32_t raw = ((uint32_t)bytes[0] << 24) | ((uint32_t)bytes[1] << 16) |
                   ((uint32_t)bytes[2] << 8)  | (uint32_t)bytes[3];
    float result;
    memcpy(&result, &raw, sizeof(float));
    return result;
}

void AS7265x::readAllBands(float* buffer) {
    // Read 6 channels from each of the 3 devices
    // Device 0 (AS72651): bands 0-5, Device 1 (AS72652): bands 6-11, Device 2 (AS72653): bands 12-17
    for (uint8_t dev = 0; dev < 3; dev++) {
        writeVirtualReg(DEV_SELECT_REG, dev);
        for (uint8_t ch = 0; ch < 6; ch++) {
            uint8_t reg = CAL_DATA_START + (ch * 4);
            buffer[dev * 6 + ch] = readCalibratedFloat(reg);
        }
    }
}

}  // namespace vera
