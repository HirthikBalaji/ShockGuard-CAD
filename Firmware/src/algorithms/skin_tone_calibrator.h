#pragma once

#include <stdint.h>
#include <stdbool.h>

enum SkinToneCategory {
    SKIN_TONE_VERY_LIGHT = 1, // Fitzpatrick I-II / Monk 1-2
    SKIN_TONE_LIGHT      = 2, // Fitzpatrick III / Monk 3-4
    SKIN_TONE_MEDIUM     = 3, // Fitzpatrick IV / Monk 5-6
    SKIN_TONE_DARK       = 4, // Fitzpatrick V / Monk 7-8
    SKIN_TONE_VERY_DARK  = 5  // Fitzpatrick VI / Monk 9-10
};

struct SkinToneProfile {
    SkinToneCategory category;
    float melaninIndex;
    float baselineLuma;
    float recommendedLedDuty;
    float adaptiveBlanchThreshold;
    float chromaticityRatioRG;
};

class SkinToneCalibrator {
public:
    SkinToneCalibrator();
    SkinToneProfile calibrateBaseline(float r, float g, float b, float luma);
    float normalizeRefillSignal(float rawLuma, const SkinToneProfile& profile);
};
