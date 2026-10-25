#include "display_ssd1306.h"
#include "shockguard_config.h"
#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET -1
#define SCREEN_ADDRESS 0x3C

static Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

ShockGuardDisplay::ShockGuardDisplay() : _initialized(false) {}

bool ShockGuardDisplay::begin() {
    if (!display.begin(SSD1306_SWITCHCAPVCC, SCREEN_ADDRESS)) {
        return false;
    }
    _initialized = true;
    display.clearDisplay();
    display.setTextColor(SSD1306_WHITE);
    showSplash();
    return true;
}

void ShockGuardDisplay::showSplash() {
    if (!_initialized) return;
    display.clearDisplay();
    display.setTextSize(2);
    display.setCursor(4, 10);
    display.print("SHOCKGUARD");
    display.setTextSize(1);
    display.setCursor(14, 34);
    display.print("Frontier Diagnostics");
    display.setCursor(20, 48);
    display.print("CRT + PPI Triage");
    display.display();
}

void ShockGuardDisplay::showIdle(bool fingerPresent) {
    if (!_initialized) return;
    display.clearDisplay();
    display.setTextSize(1);
    display.setCursor(0, 0);
    display.print("STATUS: READY");
    display.drawFastHLine(0, 10, 128, SSD1306_WHITE);

    display.setCursor(0, 20);
    if (fingerPresent) {
        display.print("FINGER DETECTED");
        display.setCursor(0, 36);
        display.print("1. Cock side knob");
        display.setCursor(0, 48);
        display.print("2. Press release button");
    } else {
        display.print("INSERT FINGER");
        display.setCursor(0, 34);
        display.print("Place fingertip fully");
        display.setCursor(0, 46);
        display.print("into tunnel against stop");
    }
    display.display();
}

void ShockGuardDisplay::showBlanchingPrompt() {
    if (!_initialized) return;
    display.clearDisplay();
    display.setTextSize(1);
    display.setCursor(0, 0);
    display.print("BLANCHING PULP...");
    display.drawFastHLine(0, 10, 128, SSD1306_WHITE);

    display.setTextSize(2);
    display.setCursor(18, 24);
    display.print("HOLDING");
    display.setTextSize(1);
    display.setCursor(10, 48);
    display.print("Dwell: 3s blanch...");
    display.display();
}

void ShockGuardDisplay::showRefillMeasuring(float elapsedSec, float currentY) {
    if (!_initialized) return;
    display.clearDisplay();
    display.setTextSize(1);
    display.setCursor(0, 0);
    display.print("RECORDING REFILL");
    display.drawFastHLine(0, 10, 128, SSD1306_WHITE);

    display.setCursor(0, 18);
    display.printf("Time:  %.2f s", elapsedSec);
    display.setCursor(0, 32);
    display.printf("Luma:  %.3f", currentY);

    // Progress bar for 4.0s measurement window
    int w = (int)((elapsedSec / 4.0f) * 120);
    if (w > 120) w = 120;
    display.drawRect(4, 48, 120, 10, SSD1306_WHITE);
    display.fillRect(6, 50, w, 6, SSD1306_WHITE);
    display.display();
}

void ShockGuardDisplay::showTriageResult(float crtSec, float ppiVal, float heartRate, int triageCode, const char* statusMsg) {
    if (!_initialized) return;
    display.clearDisplay();
    display.setTextSize(1);
    display.setCursor(0, 0);
    display.printf("CRT:%.2fs  PPI:%.2f%%", crtSec, ppiVal);
    display.drawFastHLine(0, 10, 128, SSD1306_WHITE);

    display.setCursor(0, 14);
    display.printf("HR: %.0f BPM", heartRate);

    display.setTextSize(2);
    display.setCursor(4, 28);
    if (triageCode == 0) {
        display.print("[ NORMAL ]");
    } else if (triageCode == 1) {
        display.print("[ DELAYED ]");
    } else {
        display.print("[ CRITICAL ]");
    }

    display.setTextSize(1);
    display.setCursor(0, 52);
    display.print(statusMsg);
    display.display();
}

void ShockGuardDisplay::showError(const char* errCode) {
    if (!_initialized) return;
    display.clearDisplay();
    display.setTextSize(1);
    display.setCursor(0, 0);
    display.print("DIAGNOSTIC ERROR");
    display.drawFastHLine(0, 10, 128, SSD1306_WHITE);
    display.setCursor(0, 24);
    display.print("Code:");
    display.setCursor(40, 24);
    display.print(errCode);
    display.setCursor(0, 44);
    display.print("Re-cock and retry test");
    display.display();
}
