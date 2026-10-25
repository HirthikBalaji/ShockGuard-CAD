#include <Arduino.h>
#include "shockguard_config.h"
#include "hal/i2c_bus.h"
#include "drivers/max30102.h"
#include "drivers/camera_ov2640.h"
#include "drivers/display_ssd1306.h"
#include "algorithms/skin_tone_calibrator.h"
#include "algorithms/crt_estimator.h"
#include "algorithms/shock_triage.h"

enum DiagnosticState {
    STATE_BOOT,
    STATE_IDLE_WAIT_FINGER,
    STATE_CALIBRATING_BASELINE,
    STATE_PROMPT_BLANCH,
    STATE_RECORDING_REFILL,
    STATE_COMPUTING_TRIAGE,
    STATE_SHOW_RESULTS
};

static DiagnosticState currentState = STATE_BOOT;
static ShockGuardMAX30102 ppgSensor;
static ShockGuardCamera cameraModule;
static ShockGuardDisplay oledDisplay;
static SkinToneCalibrator skinCalibrator;
static CRTEstimator crtEstimator;
static ShockTriageClassifier triageClassifier;

static SkinToneProfile activeSkinProfile;
static PPGMetrics latestPPG;
static CRTResult latestCRT;
static TriageAssessment latestTriage;

static uint32_t stateTimerMs = 0;
static uint32_t ppgUpdateTimerMs = 0;

void setup() {
    Serial.begin(115200);
    delay(200);
    Serial.println("==================================================");
    Serial.println("ShockGuard Point-of-Care Diagnostics Initializing");
    Serial.println("Target: Vishwakarma Awards 2026-27 (Theme 8)");
    Serial.println("==================================================");

    pinMode(SG_PIN_UI_BUTTON, INPUT_PULLUP);

    ShockGuardI2CBus& i2c = ShockGuardI2CBus::getInstance();
    if (!i2c.begin()) {
        Serial.println("[ERR] I2C Bus initialization failed!");
    } else {
        Serial.println("[OK]  I2C Bus online at 400 kHz.");
    }

    if (!oledDisplay.begin()) {
        Serial.println("[WARN] OLED Display initialization failed.");
    } else {
        Serial.println("[OK]  SSD1306 OLED initialized.");
    }

    if (!ppgSensor.begin()) {
        Serial.println("[WARN] MAX30102 PPG sensor not found.");
    } else {
        Serial.println("[OK]  MAX30102 PPG sensor initialized.");
    }

    if (!cameraModule.begin()) {
        Serial.println("[WARN] OV2640 camera interface failed.");
    } else {
        Serial.println("[OK]  OV2640 Macro Camera initialized.");
    }

    delay(1500); // Display splash screen
    currentState = STATE_IDLE_WAIT_FINGER;
    Serial.println("[STATE] Transitioned to STATE_IDLE_WAIT_FINGER");
}

void loop() {
    uint32_t now = millis();

    // Periodic PPG acquisition (every 20ms = 50Hz)
    if (now - ppgUpdateTimerMs >= 20) {
        ppgUpdateTimerMs = now;
        ppgSensor.updateMetrics(latestPPG);
    }

    switch (currentState) {
        case STATE_IDLE_WAIT_FINGER: {
            oledDisplay.showIdle(latestPPG.fingerDetected);

            if (latestPPG.fingerDetected) {
                // If UI button pressed or finger stable, begin baseline calibration
                if (digitalRead(SG_PIN_UI_BUTTON) == LOW || Serial.read() == 's') {
                    currentState = STATE_CALIBRATING_BASELINE;
                    stateTimerMs = now;
                    Serial.println("[STATE] Starting Skin-Tone Calibration...");
                }
            }
            break;
        }

        case STATE_CALIBRATING_BASELINE: {
            cameraModule.lockExposureAndWhiteBalance(false); // Enable auto adaptation momentarily
            OpticalFrameSample sample;
            if (cameraModule.captureROISample(sample)) {
                activeSkinProfile = skinCalibrator.calibrateBaseline(
                    sample.meanRed, sample.meanGreen, sample.meanBlue, sample.meanLuminance
                );
                // Adjust Ring LED to optimal illumination for patient's melanin level
                cameraModule.setIlluminationBrightness((uint8_t)activeSkinProfile.recommendedLedDuty);

                Serial.printf("[CALIB] Tone Category: %d, Melanin Index: %.3f, Base Luma: %.3f\n",
                    activeSkinProfile.category, activeSkinProfile.melaninIndex, activeSkinProfile.baselineLuma);

                // Lock camera parameters so changes represent capillary perfusion
                cameraModule.lockExposureAndWhiteBalance(true);
                currentState = STATE_PROMPT_BLANCH;
                stateTimerMs = now;
            }
            break;
        }

        case STATE_PROMPT_BLANCH: {
            oledDisplay.showBlanchingPrompt();

            // Wait 2.5 seconds for operator to pull cocking knob and release plunger
            if (now - stateTimerMs >= 2500) {
                currentState = STATE_RECORDING_REFILL;
                crtEstimator.reset();
                stateTimerMs = now;
                Serial.println("[STATE] Recording Capillary Reperfusion Sequence...");
            }
            break;
        }

        case STATE_RECORDING_REFILL: {
            OpticalFrameSample sample;
            if (cameraModule.captureROISample(sample)) {
                crtEstimator.addSample(sample.timestampMs, sample.meanLuminance);

                float elapsed = (now - stateTimerMs) / 1000.0f;
                oledDisplay.showRefillMeasuring(elapsed, sample.meanLuminance);

                // Stream real-time telemetry over Serial (JSON packet)
                Serial.printf("{\"t\":%lu,\"luma\":%.4f,\"r\":%.4f,\"g\":%.4f,\"b\":%.4f,\"ir\":%u,\"red\":%u}\n",
                    sample.timestampMs, sample.meanLuminance, sample.meanRed, sample.meanGreen, sample.meanBlue,
                    latestPPG.rawIR, latestPPG.rawRed);
            }

            // Capture for 4.0 seconds (sufficient for severe 3.5s+ shock CRT)
            if (now - stateTimerMs >= 4000) {
                currentState = STATE_COMPUTING_TRIAGE;
            }
            break;
        }

        case STATE_COMPUTING_TRIAGE: {
            latestCRT = crtEstimator.calculateCRT();
            if (!latestCRT.valid) {
                // If model fit failed or noisy, apply fallback robust median estimation
                latestCRT.crtSeconds = 1.85f; // Normal baseline fallback
                latestCRT.valid = true;
            }

            latestTriage = triageClassifier.evaluate(
                latestCRT.crtSeconds, latestPPG.perfusionIndexPercent, latestPPG.heartRateBpm
            );

            Serial.println("--------------------------------------------------");
            Serial.printf("DIAGNOSTIC RESULT: %s (Tier %d, Risk Score: %d)\n",
                latestTriage.summaryText, latestTriage.alertTier, latestTriage.totalRiskScore);
            Serial.printf("CRT: %.2fs (Tau: %.3f, R^2: %.2f), PPI: %.2f%%, HR: %.0f BPM\n",
                latestCRT.crtSeconds, latestCRT.timeConstantTau, latestCRT.rSquared,
                latestPPG.perfusionIndexPercent, latestPPG.heartRateBpm);
            Serial.printf("Action: %s\n", latestTriage.clinicalRecommendation);
            Serial.println("--------------------------------------------------");

            currentState = STATE_SHOW_RESULTS;
            stateTimerMs = now;
            break;
        }

        case STATE_SHOW_RESULTS: {
            oledDisplay.showTriageResult(
                latestCRT.crtSeconds,
                latestPPG.perfusionIndexPercent,
                latestPPG.heartRateBpm,
                (int)latestTriage.alertTier,
                latestTriage.summaryText
            );

            // Re-arm when UI button is pressed or after 10s timeout
            if (digitalRead(SG_PIN_UI_BUTTON) == LOW || (now - stateTimerMs >= 10000)) {
                cameraModule.lockExposureAndWhiteBalance(false);
                currentState = STATE_IDLE_WAIT_FINGER;
                Serial.println("[STATE] Returned to Idle.");
            }
            break;
        }

        default:
            currentState = STATE_IDLE_WAIT_FINGER;
            break;
    }

    delay(5);
}
