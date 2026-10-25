#pragma once

#include <stdint.h>
#include <stdbool.h>
#include "shockguard_config.h"

class ShockGuardI2CBus {
public:
    static ShockGuardI2CBus& getInstance();
    bool begin(int sda = SG_PIN_I2C_SDA, int scl = SG_PIN_I2C_SCL, uint32_t freq = SG_I2C_FREQ_HZ);
    bool writeRegister(uint8_t devAddr, uint8_t regAddr, uint8_t data);
    bool writeBytes(uint8_t devAddr, uint8_t regAddr, const uint8_t* data, size_t len);
    bool readRegister(uint8_t devAddr, uint8_t regAddr, uint8_t* data);
    bool readBytes(uint8_t devAddr, uint8_t regAddr, uint8_t* buffer, size_t len);
    bool probe(uint8_t devAddr);

private:
    ShockGuardI2CBus();
    bool _initialized;
};
