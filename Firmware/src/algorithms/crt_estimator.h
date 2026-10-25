#pragma once

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include "shockguard_config.h"

struct CRTResult {
    bool valid;
    float crtSeconds;       // Time to 90% refill (s)
    float timeConstantTau;  // Exponential time constant tau (s)
    float rSquared;         // Goodness of fit (0.0 - 1.0)
    float blanchDelta;      // Measured blanching amplitude
    uint32_t totalSamples;
};

class CRTEstimator {
public:
    CRTEstimator();
    void reset();
    bool addSample(uint32_t timestampMs, float opticalLuma);
    CRTResult calculateCRT();

private:
    uint32_t _timeBuffer[SG_MAX_BUFFER_SAMPLES];
    float _lumaBuffer[SG_MAX_BUFFER_SAMPLES];
    size_t _sampleCount;
};
