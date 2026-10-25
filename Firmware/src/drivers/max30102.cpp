#include "max30102.h"
#include "../hal/i2c_bus.h"
#include <Arduino.h>
#include <math.h>

// MAX30102 Internal Registers
#define REG_INTR_STATUS_1    0x00
#define REG_INTR_STATUS_2    0x01
#define REG_INTR_ENABLE_1    0x02
#define REG_INTR_ENABLE_2    0x03
#define REG_FIFO_WR_PTR      0x04
#define REG_OVF_COUNTER      0x05
#define REG_FIFO_RD_PTR      0x06
#define REG_FIFO_DATA        0x07
#define REG_FIFO_CONFIG      0x08
#define REG_MODE_CONFIG      0x09
#define REG_SPO2_CONFIG      0x0A
#define REG_LED1_PA          0x0C // Red LED Current
#define REG_LED2_PA          0x0D // IR LED Current
#define REG_PILOT_PA         0x10 // Proximity LED Current
#define REG_PART_ID          0xFF

ShockGuardMAX30102::ShockGuardMAX30102()
    : _irDcAvg(0), _redDcAvg(0), _irAcMin(1e6), _irAcMax(0),
      _sampleCount(0), _lastPeakTimeMs(0), _currentBpm(72.0f) {}

bool ShockGuardMAX30102::begin() {
    ShockGuardI2CBus& bus = ShockGuardI2CBus::getInstance();
    
    uint8_t partId = 0;
    if (!bus.readRegister(I2C_ADDR, REG_PART_ID, &partId) || partId != 0x15) {
        return false;
    }

    // Reset sensor
    bus.writeRegister(I2C_ADDR, REG_MODE_CONFIG, 0x40);
    delay(10);

    // FIFO Config: Sample avg = 4, rollover enable, almost full = 17
    bus.writeRegister(I2C_ADDR, REG_FIFO_CONFIG, 0x5F);

    // Mode Config: SpO2 mode (Red + IR)
    bus.writeRegister(I2C_ADDR, REG_MODE_CONFIG, 0x03);

    // SpO2 Config: ADC range 4096nA, 100 Hz sample rate, 411us pulse width (18-bit resolution)
    bus.writeRegister(I2C_ADDR, REG_SPO2_CONFIG, 0x27);

    // LED Currents: ~7.2mA for Red and IR to balance battery life and optical SNR
    bus.writeRegister(I2C_ADDR, REG_LED1_PA, 0x24);
    bus.writeRegister(I2C_ADDR, REG_LED2_PA, 0x24);
    bus.writeRegister(I2C_ADDR, REG_PILOT_PA, 0x7F);

    resetFIFO();
    return true;
}

void ShockGuardMAX30102::resetFIFO() {
    ShockGuardI2CBus& bus = ShockGuardI2CBus::getInstance();
    bus.writeRegister(I2C_ADDR, REG_FIFO_WR_PTR, 0x00);
    bus.writeRegister(I2C_ADDR, REG_OVF_COUNTER, 0x00);
    bus.writeRegister(I2C_ADDR, REG_FIFO_RD_PTR, 0x00);
    _irAcMin = 1e6;
    _irAcMax = 0;
}

bool ShockGuardMAX30102::readFIFO(uint32_t* red, uint32_t* ir) {
    ShockGuardI2CBus& bus = ShockGuardI2CBus::getInstance();
    uint8_t buffer[6];
    if (!bus.readBytes(I2C_ADDR, REG_FIFO_DATA, buffer, 6)) {
        return false;
    }
    *red = ((uint32_t)(buffer[0] & 0x03) << 16) | ((uint32_t)buffer[1] << 8) | buffer[2];
    *ir  = ((uint32_t)(buffer[3] & 0x03) << 16) | ((uint32_t)buffer[4] << 8) | buffer[5];
    return true;
}

bool ShockGuardMAX30102::isFingerPresent() {
    uint32_t red = 0, ir = 0;
    if (readFIFO(&red, &ir)) {
        return (ir > 50000); // Threshold for finger skin tissue optical coupling
    }
    return false;
}

bool ShockGuardMAX30102::updateMetrics(PPGMetrics& outMetrics) {
    uint32_t red = 0, ir = 0;
    if (!readFIFO(&red, &ir)) {
        outMetrics.fingerDetected = false;
        return false;
    }

    outMetrics.rawRed = red;
    outMetrics.rawIR = ir;

    if (ir < 50000) {
        outMetrics.fingerDetected = false;
        outMetrics.perfusionIndexPercent = 0.0f;
        outMetrics.heartRateBpm = 0.0f;
        outMetrics.spO2Percent = 0.0f;
        return true;
    }

    outMetrics.fingerDetected = true;
    computePerfusionMetrics(red, ir, outMetrics);
    return true;
}

void ShockGuardMAX30102::computePerfusionMetrics(uint32_t red, uint32_t ir, PPGMetrics& outMetrics) {
    // Low-pass exponential filter to extract DC baseline
    float alpha = 0.02f;
    if (_sampleCount == 0) {
        _irDcAvg = ir;
        _redDcAvg = red;
    } else {
        _irDcAvg = (1.0f - alpha) * _irDcAvg + alpha * ir;
        _redDcAvg = (1.0f - alpha) * _redDcAvg + alpha * red;
    }
    _sampleCount++;

    // Track AC peak-to-peak amplitude over heart cycle
    float irAc = ir - _irDcAvg;
    if (irAc < _irAcMin) _irAcMin = irAc;
    if (irAc > _irAcMax) _irAcMax = irAc;

    // Perfusion Index: (AC_IR_pp / DC_IR) * 100%
    float acPeakToPeak = _irAcMax - _irAcMin;
    if (_irDcAvg > 0 && acPeakToPeak > 0) {
        outMetrics.perfusionIndexPercent = (acPeakToPeak / _irDcAvg) * 100.0f;
    } else {
        outMetrics.perfusionIndexPercent = 1.0f;
    }

    // Peak detection for Heart Rate
    uint32_t now = millis();
    if (irAc > 300.0f && (now - _lastPeakTimeMs) > 350) { // refractory period > 350ms (max 170 BPM)
        uint32_t interval = now - _lastPeakTimeMs;
        if (interval < 2000) { // valid interval < 2.0s (> 30 BPM)
            float instantBpm = 60000.0f / interval;
            _currentBpm = 0.8f * _currentBpm + 0.2f * instantBpm;
        }
        _lastPeakTimeMs = now;
        // Reset AC window for next cardiac pulse
        _irAcMin = 1e6;
        _irAcMax = 0;
    }

    outMetrics.heartRateBpm = _currentBpm;

    // Standard SpO2 calibration curve (ratio-of-ratios)
    float redAc = fabsf(red - _redDcAvg);
    float irAcAbs = fabsf(irAc);
    if (irAcAbs > 1.0f && _redDcAvg > 0.0f && _irDcAvg > 0.0f) {
        float rVal = (redAc / _redDcAvg) / (irAcAbs / _irDcAvg);
        float spo2 = 110.0f - 25.0f * rVal;
        if (spo2 > 100.0f) spo2 = 100.0f;
        if (spo2 < 70.0f) spo2 = 70.0f;
        outMetrics.spO2Percent = spo2;
    } else {
        outMetrics.spO2Percent = 98.0f;
    }
}
