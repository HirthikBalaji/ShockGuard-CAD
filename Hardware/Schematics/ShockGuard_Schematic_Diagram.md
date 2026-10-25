# ShockGuard – Electrical Schematic & Hardware Architecture

## 1. System Architecture Overview

The ShockGuard electronics system provides a self-contained, low-noise diagnostic platform for non-invasive, skin-tone-calibrated capillary refill time (CRT) and peripheral perfusion index (PPI) measurement.

```mermaid
flowchart TD
    subgraph Power Management
        USBC["USB-C (5V In)"] --> TP4056["TP4056 1S Li-Ion Charger"]
        TP4056 --> DW01["DW01A + FS8205A Protection"]
        DW01 --> BATT["1S LiPo (3.7V 450mAh)"]
        DW01 --> LDO["AP2112K-3.3 (600mA LDO)"]
        LDO --> V33["3.3V System Rail"]
    end

    subgraph Core Processing
        V33 --> ESP32["ESP32-S3-WROOM-1 (N16R8)\nDual-Core Xtensa LX7 @ 240MHz\n16MB Flash + 8MB PSRAM"]
    end

    subgraph Optical Sensing Subsystem
        V33 --> OV2640["OV2640 Macro Camera (DVP 8-bit)"]
        OV2640 <-->|DVP Bus + SCCB| ESP32
        V33 --> RING["6x High-CRI 4000K Ring LEDs"]
        ESP32 -->|PWM / GPIO4| MOSFET["DMG2302 N-MOSFET"]
        MOSFET --> RING
    end

    subgraph PPG & Hemodynamics Subsystem
        V33 --> MAX30102["MAX30102 PPG & Pulse Oximeter"]
        MAX30102 <-->|I2C Bus (SDA: GPIO8, SCL: GPIO9)| ESP32
        MAX30102 -->|INT: GPIO10| ESP32
    end

    subgraph User Interface
        V33 --> OLED["0.96 inch 128x64 I2C OLED (SSD1306)"]
        OLED <-->|I2C Bus| ESP32
        ESP32 -->|GPIO0 / Debounce| BUTTON["Tactile UI Button"]
    end
```

---

## 2. Detailed Pinout Mapping (ESP32-S3-WROOM-1)

| ESP32-S3 Pin | Function / Net | Signal Direction | Description / Connection |
|---|---|---|---|
| **GPIO1** | `CAM_D0` | Input | Camera DVP Data Bit 0 |
| **GPIO2** | `CAM_D1` | Input | Camera DVP Data Bit 1 |
| **GPIO3** | `CAM_D2` | Input | Camera DVP Data Bit 2 |
| **GPIO4** | `LED_RING_PWM` | Output | Ring LED PWM Illumination Control (LEDC Channel 0, 20kHz) |
| **GPIO5** | `CAM_D3` | Input | Camera DVP Data Bit 3 |
| **GPIO6** | `CAM_D4` | Input | Camera DVP Data Bit 4 |
| **GPIO7** | `CAM_D5` | Input | Camera DVP Data Bit 5 |
| **GPIO8** | `I2C_SDA` | Bidirectional | Shared I2C Data (MAX30102 & SSD1306 OLED, 4.7kΩ pull-up) |
| **GPIO9** | `I2C_SCL` | Output | Shared I2C Clock (400 kHz Fast-Mode) |
| **GPIO10** | `MAX_INT` | Input | MAX30102 FIFO Almost Full / New Data Interrupt |
| **GPIO11** | `CAM_D6` | Input | Camera DVP Data Bit 6 |
| **GPIO12** | `CAM_D7` | Input | Camera DVP Data Bit 7 |
| **GPIO13** | `CAM_XCLK` | Output | Camera Master Clock (20 MHz output from ESP32 LEDC/I2S) |
| **GPIO14** | `CAM_PCLK` | Input | Camera Pixel Clock |
| **GPIO15** | `CAM_VSYNC`| Input | Camera Vertical Sync |
| **GPIO16** | `CAM_HREF` | Input | Camera Horizontal Reference |
| **GPIO17** | `CAM_SIOD` | Bidirectional | Camera SCCB Data (I2C-compatible) |
| **GPIO18** | `CAM_SIOC` | Output | Camera SCCB Clock |
| **GPIO19** | `USB_D-` | Bidirectional | Native USB 2.0 Full-Speed D- |
| **GPIO20** | `USB_D+` | Bidirectional | Native USB 2.0 Full-Speed D+ |
| **GPIO21** | `CAM_RESET`| Output | Camera Active-Low Hardware Reset |
| **GPIO38** | `CAM_PWDN` | Output | Camera Power Down Control (Low = Active) |
| **GPIO0**  | `UI_BUTTON`| Input | UI Navigation / Test Trigger (Active Low, 10kΩ pull-up, 100nF debounce) |
| **GPIO47** | `BATT_SENSE`| Analog Input | Battery Voltage Divider (100kΩ / 100kΩ to VBAT) |

---

## 3. Subsystem Circuit Analysis

### 3.1 Power Supply & Battery Management
- **Charging Path**: The TP4056 manages 1S 3.7V Lithium-Polymer charging up to 500mA–1000mA (set by $R_{PROG} = 1.2\,\text{k}\Omega$). Dual indicator LEDs (`CHRG` red, `STDBY` green) signal status.
- **Protection Circuit**: The DW01A-G monitors cell overcharge ($V_{OVP} = 4.30\,\text{V}$), overdischarge ($V_{UVP} = 2.40\,\text{V}$), and overcurrent. It controls back-to-back N-MOSFETs in the FS8205A package.
- **Voltage Regulation**: AP2112K-3.3 provides a stable 3.3V rail with 600mA output capability, ultra-low dropout (250mV at 600mA), and low noise output ($<50\,\mu\text{V}_{RMS}$), ensuring clean power for optical sensing.
- **Decoupling Strategy**: Each active IC features 100nF high-frequency ceramic decoupling placed within 2mm of the power pins, backed by bulk 10µF X5R MLCC capacitors.

### 3.2 Optical Imaging & Ring Illumination
- **Camera Module**: OV2640 with a custom fixed-focus macro barrel focused at 13mm working distance. High-speed 8-bit parallel DVP interface routed with length-matched traces ($< 35\,\text{mm}$ trace length, $< 1\,\text{mm}$ skew).
- **Constant White Balance**: In software, auto-exposure (AEC) and auto-white-balance (AWB) are explicitly disabled after baseline acquisition to ensure that skin color changes during blanching and refill reflect true vascular hemodynamics rather than camera AGC artifacts.
- **Ring LED Driver**: 6 high-CRI (Color Rendering Index $\ge 90$) 4000K neutral-white LEDs configured in 3 parallel strings of 2 series LEDs. Driven through a DMG2302UK N-MOSFET by a 20kHz PWM signal to eliminate stroboscopic optical flicker during high-speed image capture.

### 3.3 Hemodynamics & Perfusion Sensor (MAX30102)
- **Sensor Alignment**: Located in the finger trough at $X = 30\,\text{mm}$, flush with the resting surface.
- **Optical Dual-Wavelength Measurement**: Alternates Red (660nm) and Infrared (880nm) LEDs into the digital photodetector.
- **Peripheral Perfusion Index (PPI)**:
  $$\text{PPI} = \frac{\text{AC}_{\text{IR}}}{\text{DC}_{\text{IR}}} \times 100\%$$
- **SpO2 Ratio-of-Ratios**:
  $$R = \frac{\text{AC}_{\text{Red}} / \text{DC}_{\text{Red}}}{\text{AC}_{\text{IR}} / \text{DC}_{\text{IR}}}$$

### 3.4 Display & User Feedback (SSD1306 OLED)
- **Interface**: 4-pin I2C connection sharing the bus with MAX30102 at standard Fast-Mode speed (400kHz).
- **Physical Position**: Mounted in the upper enclosure roof with an anti-glare PMMA window for direct readability by field triage personnel.
