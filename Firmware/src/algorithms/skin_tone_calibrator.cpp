#include "skin_tone_calibrator.h"
#include <math.h>

SkinToneCalibrator::SkinToneCalibrator() {}

SkinToneProfile SkinToneCalibrator::calibrateBaseline(float r, float g, float b, float luma) {
    SkinToneProfile profile;
    profile.baselineLuma = luma;

    // Prevent division by zero
    if (r < 0.01f) r = 0.01f;
    if (g < 0.01f) g = 0.01f;

    // Melanin Index approximation based on optical attenuation in red vs green
    // Melanin absorbs green much more strongly than red compared to hemoglobin
    float mIndex = logf(1.0f / g) - logf(1.0f / r);
    if (mIndex < 0.0f) mIndex = 0.0f;
    profile.melaninIndex = mIndex;
    profile.chromaticityRatioRG = r / g;

    // Classify into Fitzpatrick / Monk corresponding categories
    if (luma > 0.65f && mIndex < 0.25f) {
        profile.category = SKIN_TONE_VERY_LIGHT;
        profile.recommendedLedDuty = 140.0f;          // ~55% PWM
        profile.adaptiveBlanchThreshold = 0.12f;      // 12% luma drop during blanching
    } else if (luma > 0.50f && mIndex < 0.45f) {
        profile.category = SKIN_TONE_LIGHT;
        profile.recommendedLedDuty = 165.0f;          // ~65% PWM
        profile.adaptiveBlanchThreshold = 0.10f;      // 10% luma drop
    } else if (luma > 0.35f && mIndex < 0.70f) {
        profile.category = SKIN_TONE_MEDIUM;
        profile.recommendedLedDuty = 190.0f;          // ~75% PWM
        profile.adaptiveBlanchThreshold = 0.075f;     // 7.5% luma drop
    } else if (luma > 0.20f && mIndex < 1.00f) {
        profile.category = SKIN_TONE_DARK;
        profile.recommendedLedDuty = 220.0f;          // ~86% PWM
        profile.adaptiveBlanchThreshold = 0.050f;     // 5.0% luma drop
    } else {
        profile.category = SKIN_TONE_VERY_DARK;
        profile.recommendedLedDuty = 250.0f;          // ~98% PWM
        profile.adaptiveBlanchThreshold = 0.035f;     // 3.5% luma drop
    }

    return profile;
}

float SkinToneCalibrator::normalizeRefillSignal(float rawLuma, const SkinToneProfile& profile) {
    if (profile.baselineLuma < 0.01f) return 0.0f;
    // Normalized optical contrast relative to uncompressed baseline
    return (profile.baselineLuma - rawLuma) / profile.baselineLuma;
}
