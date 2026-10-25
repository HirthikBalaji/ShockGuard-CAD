#pragma once

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include "esp_camera.h"

struct OpticalFrameSample {
    uint32_t timestampMs;
    float meanLuminance;   // Y channel / Greyscale
    float meanRed;         // Normalized red channel (0.0 - 1.0)
    float meanGreen;       // Normalized green channel (0.0 - 1.0)
    float meanBlue;        // Normalized blue channel (0.0 - 1.0)
};

class ShockGuardCamera {
public:
    ShockGuardCamera();
    bool begin();
    void setIlluminationBrightness(uint8_t duty);
    void lockExposureAndWhiteBalance(bool lock);
    bool captureROISample(OpticalFrameSample& sample);

private:
    bool _initialized;
    camera_config_t _config;
};
