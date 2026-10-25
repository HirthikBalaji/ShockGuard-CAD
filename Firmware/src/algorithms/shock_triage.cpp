#include "shock_triage.h"
#include "shockguard_config.h"

ShockTriageClassifier::ShockTriageClassifier() {}

TriageAssessment ShockTriageClassifier::evaluate(float crtSec, float ppiPercent, float heartRate) {
    TriageAssessment a;
    a.crtSeconds = crtSec;
    a.perfusionIndex = ppiPercent;
    a.heartRateBpm = heartRate;
    a.totalRiskScore = 0;

    // 1. Capillary Refill Evaluation
    if (crtSec > SG_CRT_DELAYED_MAX) { // > 3.0s
        a.totalRiskScore += 4;
    } else if (crtSec > SG_CRT_NORMAL_MAX) { // 2.0 - 3.0s
        a.totalRiskScore += 2;
    }

    // 2. Peripheral Perfusion Index (PPI) Evaluation
    if (ppiPercent < SG_PPI_CRITICAL_MIN) { // < 0.6%
        a.totalRiskScore += 4;
    } else if (ppiPercent < SG_PPI_NORMAL_MIN) { // 0.6% - 1.4%
        a.totalRiskScore += 2;
    }

    // 3. Heart Rate / Compensatory Tachycardia Evaluation
    if (heartRate > 125.0f || (heartRate < 45.0f && heartRate > 0.0f)) {
        a.totalRiskScore += 2;
    } else if (heartRate > 100.0f) {
        a.totalRiskScore += 1;
    }

    // Determine Final Alert Tier
    if (a.totalRiskScore >= 6 || crtSec >= 3.5f || (ppiPercent < 0.4f && ppiPercent > 0.0f)) {
        a.alertTier = TRIAGE_TIER_CRITICAL;
        a.summaryText = "CRITICAL SHOCK RISK";
        a.clinicalRecommendation = "Urgent IV resuscitation & lactate test";
    } else if (a.totalRiskScore >= 3 || crtSec > 2.0f || ppiPercent < 1.0f) {
        a.alertTier = TRIAGE_TIER_MODERATE;
        a.summaryText = "COMPENSATED SHOCK";
        a.clinicalRecommendation = "Monitor closely; fluid challenge protocol";
    } else {
        a.alertTier = TRIAGE_TIER_NORMAL;
        a.summaryText = "PERFUSION ADEQUATE";
        a.clinicalRecommendation = "Routine observation; vitals normal";
    }

    return a;
}
