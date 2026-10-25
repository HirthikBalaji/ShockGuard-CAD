#pragma once

#include <stdint.h>
#include <stddef.h>

// ============================================================================
// ShockGuard Hardware Pin Assignment (ESP32-S3-WROOM-1)
// ============================================================================

// I2C Bus Pins (MAX30102 & SSD1306 OLED)
#define SG_PIN_I2C_SDA         8
#define SG_PIN_I2C_SCL         9
#define SG_I2C_FREQ_HZ         400000

// MAX30102 Interrupt
#define SG_PIN_MAX30102_INT    10

// User Interface
#define SG_PIN_UI_BUTTON       0
#define SG_PIN_BATTERY_ADC     47

// Optical Illumination (PWM Driven Ring LED)
#define SG_PIN_RING_LED_PWM    4
#define SG_RING_PWM_FREQ       20000
#define SG_RING_PWM_RES_BITS   8
#define SG_RING_PWM_CHANNEL    0

// Camera DVP Interface (OV2640 Macro Lens)
#define SG_PIN_CAM_D0          1
#define SG_PIN_CAM_D1          2
#define SG_PIN_CAM_D2          3
#define SG_PIN_CAM_D3          5
#define SG_PIN_CAM_D4          6
#define SG_PIN_CAM_D5          7
#define SG_PIN_CAM_D6          11
#define SG_PIN_CAM_D7          12
#define SG_PIN_CAM_XCLK        13
#define SG_PIN_CAM_PCLK        14
#define SG_PIN_CAM_VSYNC       15
#define SG_PIN_CAM_HREF        16
#define SG_PIN_CAM_SIOD        17
#define SG_PIN_CAM_SIOC        18
#define SG_PIN_CAM_RESET       21
#define SG_PIN_CAM_PWDN        38

// ============================================================================
// Clinical Diagnostic & Algorithm Parameters
// ============================================================================

// Capillary Refill Time (CRT) Thresholds (Seconds)
#define SG_CRT_NORMAL_MAX      2.0f   // Normal CRT < 2.0s
#define SG_CRT_DELAYED_MAX     3.0f   // Delayed CRT 2.0 - 3.0s (Mild Shock/Compensated)
                                      // Severe CRT > 3.0s (Decompensated Shock)

// Peripheral Perfusion Index (PPI) Thresholds (%)
#define SG_PPI_CRITICAL_MIN    0.6f   // Critical Hypoperfusion < 0.6%
#define SG_PPI_NORMAL_MIN      1.4f   // Normal Peripheral Perfusion >= 1.4%

// Sampling Rates
#define SG_CAM_SAMPLING_FPS    30     // Camera frame rate for refill curve
#define SG_MAX_BUFFER_SAMPLES  150    // 5 seconds at 30 fps
#define SG_PPG_SAMPLING_RATE   100    // MAX30102 sample rate in Hz
