#include "i2c_bus.h"
#include <Arduino.h>
#include <Wire.h>

ShockGuardI2CBus::ShockGuardI2CBus() : _initialized(false) {}

ShockGuardI2CBus& ShockGuardI2CBus::getInstance() {
    static ShockGuardI2CBus instance;
    return instance;
}

bool ShockGuardI2CBus::begin(int sda, int scl, uint32_t freq) {
    if (_initialized) return true;
    bool success = Wire.begin(sda, scl, freq);
    Wire.setTimeOut(50); // 50ms timeout to avoid bus lockup
    _initialized = success;
    return success;
}

bool ShockGuardI2CBus::writeRegister(uint8_t devAddr, uint8_t regAddr, uint8_t data) {
    Wire.beginTransmission(devAddr);
    Wire.write(regAddr);
    Wire.write(data);
    return (Wire.endTransmission() == 0);
}

bool ShockGuardI2CBus::writeBytes(uint8_t devAddr, uint8_t regAddr, const uint8_t* data, size_t len) {
    Wire.beginTransmission(devAddr);
    Wire.write(regAddr);
    for (size_t i = 0; i < len; ++i) {
        Wire.write(data[i]);
    }
    return (Wire.endTransmission() == 0);
}

bool ShockGuardI2CBus::readRegister(uint8_t devAddr, uint8_t regAddr, uint8_t* data) {
    return readBytes(devAddr, regAddr, data, 1);
}

bool ShockGuardI2CBus::readBytes(uint8_t devAddr, uint8_t regAddr, uint8_t* buffer, size_t len) {
    Wire.beginTransmission(devAddr);
    Wire.write(regAddr);
    if (Wire.endTransmission(false) != 0) { // repeated start
        return false;
    }
    size_t count = Wire.requestFrom(devAddr, len);
    if (count != len) {
        return false;
    }
    for (size_t i = 0; i < len; ++i) {
        buffer[i] = Wire.read();
    }
    return true;
}

bool ShockGuardI2CBus::probe(uint8_t devAddr) {
    Wire.beginTransmission(devAddr);
    return (Wire.endTransmission() == 0);
}
