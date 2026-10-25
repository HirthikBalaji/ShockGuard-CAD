#pragma once

#include <stdint.h>
#include <stdbool.h>

class ShockGuardDisplay {
public:
    ShockGuardDisplay();
    bool begin();
    void showSplash();
    void showIdle(bool fingerPresent);
    void showBlanchingPrompt();
    void showRefillMeasuring(float elapsedSec, float currentY);
    void showTriageResult(float crtSec, float ppiVal, float heartRate, int triageCode, const char* statusMsg);
    void showError(const char* errCode);

private:
    bool _initialized;
};
