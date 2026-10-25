#pragma once

#include <stdint.h>
#include <stdbool.h>

enum TriageAlertTier {
    TRIAGE_TIER_NORMAL   = 0, // Green: Perfusion adequate
    TRIAGE_TIER_MODERATE = 1, // Amber: Compensated shock / hypoperfusion
    TRIAGE_TIER_CRITICAL = 2  // Red: Severe hypoperfusion / sepsis risk
};

struct TriageAssessment {
    TriageAlertTier alertTier;
    int totalRiskScore;         // 0 to 10
    float crtSeconds;
    float perfusionIndex;
    float heartRateBpm;
    const char* summaryText;
    const char* clinicalRecommendation;
};

class ShockTriageClassifier {
public:
    ShockTriageClassifier();
    TriageAssessment evaluate(float crtSec, float ppiPercent, float heartRate);
};
