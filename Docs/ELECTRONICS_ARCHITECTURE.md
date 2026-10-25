# ShockGuard – Electronics Architecture & Hardware Specification

## 1. Executive Summary
ShockGuard integrates a multi-spectral optical reflectance engine and photoplethysmography (PPG) sensor array controlled by an ESP32-S3 dual-core microcontroller. The electronics are tailored for point-of-care capillary refill time (CRT) quantification and peripheral perfusion index (PPI) monitoring to detect early shock and sepsis.

---

## 2. Power Subsystem & Budget

| Operational State | Subsystem Loads | Typical Current @ 3.7V | Power (mW) |
|---|---|---|---|
| **Deep Sleep / Standby** | ESP32 RTC, DW01A quiescent, AP2112 quiescent | 42 µA | 0.16 mW |
| **Idle / Finger Detection** | MAX30102 proximity mode, OLED on, ESP32 @ 80MHz | 38 mA | 140.6 mW |
| **Active Blanching & Capture** | Ring LED (100% PWM), OV2640 DVP @ 30fps, ESP32 @ 240MHz | 215 mA | 795.5 mW |
| **Inference & Curve Fitting** | ESP32-S3 dual-core vector execution, OLED rendering | 110 mA | 407.0 mW |
| **Telemetry Upload (BLE/WiFi)** | Radio active burst | 185 mA | 684.5 mW |

With a 450 mAh 1S LiPo cell (LP502238):
- **Continuous measurement cycles**: > 400 complete triage evaluations on a single charge.
- **Standby battery life**: > 6 months.

---

## 3. Optical Illumination & Camera Integration

1. **High-CRI Uniform Ring LED**:
   - 6x 4000K neutral-white LEDs (CRI $\ge 90$) arranged coaxially around the macro camera lens.
   - Eliminates shadow gradients across the finger pad during plunger compression and refill.
   - High-frequency 20 kHz PWM dimming prevents optical aliasing and rolling-shutter banding on the CMOS sensor.

2. **Locked Exposure Pipeline**:
   - Camera auto-exposure (AEC) and auto-white-balance (AWB) are locked immediately prior to release.
   - This ensures intensity changes reflect capillary bed reperfusion rather than sensor gain shifts.

---

## 4. Signal Integrity & EMC Design Rules

- **4-Layer PCB Stackup**:
  - Layer 1 (Top): High-speed signals (Camera DVP, I2C, SPI)
  - Layer 2: Solid Ground Plane (`GND`) for continuous return paths
  - Layer 3: Power Distribution Plane (`+3V3`, `VBAT`)
  - Layer 4 (Bottom): Non-critical signals and thermal copper fills
- **Camera DVP Bus**: Matched track lengths to within $\pm 1\,\text{mm}$ to prevent clock-to-data skew on the 20 MHz pixel clock.
- **MAX30102 Isolation**: Guard rings and separate analog filtering on the 1.8V logic and 3.3V LED driver lines to maintain low optical noise floor.
