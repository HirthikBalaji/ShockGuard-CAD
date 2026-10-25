#pragma once

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

struct PPGMetrics {
    float heartRateBpm;
    float spO2Percent;
    float perfusionIndexPercent; // PPI
    bool fingerDetected;
    uint32_t rawRed;
    uint32_t rawIR;
};

class ShockGuardMAX30102 {
public:
    ShockGuardMAX30102();
    bool begin();
    bool isFingerPresent();
    bool updateMetrics(PPGMetrics& outMetrics);
    void resetFIFO();

private:
    bool readFIFO(uint32_t* red, uint32_t* ir);
    void computePerfusionMetrics(uint32_t red, uint32_t ir, PPGMetrics& outMetrics);

    static constexpr uint8_t I2C_ADDR = 0x57;

    // Moving average and peak detection filters
    float _irDcAvg;
    float _redDcAvg;
    float _irAcMin;
    float _irAcMax;
    uint32_t _sampleCount;
    uint32_t _lastPeakTimeMs;
    float _currentBpm;
};
