#include "crt_estimator.h"
#include <math.h>

CRTEstimator::CRTEstimator() : _sampleCount(0) {
    reset();
}

void CRTEstimator::reset() {
    _sampleCount = 0;
}

bool CRTEstimator::addSample(uint32_t timestampMs, float opticalLuma) {
    if (_sampleCount >= SG_MAX_BUFFER_SAMPLES) {
        return false;
    }
    _timeBuffer[_sampleCount] = timestampMs;
    _lumaBuffer[_sampleCount] = opticalLuma;
    _sampleCount++;
    return true;
}

CRTResult CRTEstimator::calculateCRT() {
    CRTResult res;
    res.valid = false;
    res.crtSeconds = 0.0f;
    res.timeConstantTau = 0.0f;
    res.rSquared = 0.0f;
    res.blanchDelta = 0.0f;
    res.totalSamples = _sampleCount;

    if (_sampleCount < 15) { // Need at least 0.5s of data
        return res;
    }

    // Step 1: Find peak blanching luminance (maximum optical reflectance during blanching)
    float peakLuma = _lumaBuffer[0];
    size_t peakIdx = 0;
    for (size_t i = 1; i < _sampleCount / 2; ++i) {
        if (_lumaBuffer[i] > peakLuma) {
            peakLuma = _lumaBuffer[i];
            peakIdx = i;
        }
    }

    // Step 2: Establish the reperfusion baseline from the tail end of the capture (last 20%)
    size_t tailStart = (_sampleCount * 4) / 5;
    float baselineLuma = 0.0f;
    for (size_t i = tailStart; i < _sampleCount; ++i) {
        baselineLuma += _lumaBuffer[i];
    }
    baselineLuma /= (_sampleCount - tailStart);

    float deltaLuma = peakLuma - baselineLuma;
    res.blanchDelta = deltaLuma;

    // Minimum blanching threshold to confirm valid physical compression
    if (deltaLuma < 0.015f) {
        return res; // Blanching too faint to reliably fit
    }

    // Step 3: Least-squares linear regression on linearized exponential decay:
    // (y(t) - baseline) / delta = exp(-(t - t0) / tau)
    // ln((y(t) - baseline) / delta) = - slope * dt
    // where slope = 1 / tau

    uint32_t t0 = _timeBuffer[peakIdx];
    float sumX = 0.0f, sumY = 0.0f, sumXY = 0.0f, sumX2 = 0.0f, sumY2 = 0.0f;
    size_t fitPoints = 0;

    for (size_t i = peakIdx + 1; i < tailStart; ++i) {
        float remainingFraction = (_lumaBuffer[i] - baselineLuma) / deltaLuma;
        // Bound to valid log domain [0.05, 0.95]
        if (remainingFraction > 0.05f && remainingFraction < 0.95f) {
            float dt = (float)(_timeBuffer[i] - t0) / 1000.0f; // in seconds
            float lnVal = logf(remainingFraction);

            sumX += dt;
            sumY += lnVal;
            sumXY += dt * lnVal;
            sumX2 += dt * dt;
            sumY2 += lnVal * lnVal;
            fitPoints++;
        }
    }

    if (fitPoints < 5) {
        return res;
    }

    float denom = (fitPoints * sumX2 - sumX * sumX);
    if (fabsf(denom) < 1e-6f) {
        return res;
    }

    float slope = (fitPoints * sumXY - sumX * sumY) / denom;
    // For a decreasing curve, slope must be negative
    if (slope >= 0.0f) {
        return res;
    }

    float tau = -1.0f / slope; // tau = -1 / slope
    res.timeConstantTau = tau;

    // Standard clinical 90% refill: CRT_90 = -ln(0.10) * tau = 2.3026 * tau
    res.crtSeconds = 2.3026f * tau;

    // Calculate Pearson R^2 correlation
    float nomR = (fitPoints * sumXY - sumX * sumY);
    float denomR = (fitPoints * sumX2 - sumX * sumX) * (fitPoints * sumY2 - sumY * sumY);
    if (denomR > 0.0f) {
        res.rSquared = (nomR * nomR) / denomR;
    }

    // Plausible physiological boundaries: 0.3s <= CRT <= 8.0s, R^2 >= 0.65
    if (res.crtSeconds >= 0.3f && res.crtSeconds <= 8.0f && res.rSquared >= 0.60f) {
        res.valid = true;
    }

    return res;
}
