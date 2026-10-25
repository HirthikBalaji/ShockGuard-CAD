#include "camera_ov2640.h"
#include "shockguard_config.h"
#include <Arduino.h>

ShockGuardCamera::ShockGuardCamera() : _initialized(false) {}

bool ShockGuardCamera::begin() {
    _config.ledc_channel = LEDC_CHANNEL_1;
    _config.ledc_timer = LEDC_TIMER_1;
    _config.pin_d0 = SG_PIN_CAM_D0;
    _config.pin_d1 = SG_PIN_CAM_D1;
    _config.pin_d2 = SG_PIN_CAM_D2;
    _config.pin_d3 = SG_PIN_CAM_D3;
    _config.pin_d4 = SG_PIN_CAM_D4;
    _config.pin_d5 = SG_PIN_CAM_D5;
    _config.pin_d6 = SG_PIN_CAM_D6;
    _config.pin_d7 = SG_PIN_CAM_D7;
    _config.pin_xclk = SG_PIN_CAM_XCLK;
    _config.pin_pclk = SG_PIN_CAM_PCLK;
    _config.pin_vsync = SG_PIN_CAM_VSYNC;
    _config.pin_href = SG_PIN_CAM_HREF;
    _config.pin_sccb_sda = SG_PIN_CAM_SIOD;
    _config.pin_sccb_scl = SG_PIN_CAM_SIOC;
    _config.pin_pwdn = SG_PIN_CAM_PWDN;
    _config.pin_reset = SG_PIN_CAM_RESET;
    _config.xclk_freq_hz = 20000000;
    _config.pixel_format = PIXFORMAT_RGB565;
    _config.frame_size = FRAMESIZE_QQVGA; // 160x120 for fast 30+ FPS processing
    _config.jpeg_quality = 12;
    _config.fb_count = 2;
    _config.grab_mode = CAMERA_GRAB_LATEST;

    esp_err_t err = esp_camera_init(&_config);
    if (err != ESP_OK) {
        return false;
    }

    // Configure Ring LED PWM
    ledcSetup(SG_RING_PWM_CHANNEL, SG_RING_PWM_FREQ, SG_RING_PWM_RES_BITS);
    ledcAttachPin(SG_PIN_RING_LED_PWM, SG_RING_PWM_CHANNEL);
    setIlluminationBrightness(180); // Default ~70% duty cycle

    _initialized = true;
    return true;
}

void ShockGuardCamera::setIlluminationBrightness(uint8_t duty) {
    ledcWrite(SG_RING_PWM_CHANNEL, duty);
}

void ShockGuardCamera::lockExposureAndWhiteBalance(bool lock) {
    sensor_t* s = esp_camera_sensor_get();
    if (!s) return;

    if (lock) {
        // Freeze AEC, AGC, and AWB so color variations reflect capillary perfusion
        s->set_exposure_ctrl(s, 0); // Manual exposure
        s->set_gain_ctrl(s, 0);     // Manual gain
        s->set_whitebal(s, 0);      // Manual white balance
    } else {
        s->set_exposure_ctrl(s, 1);
        s->set_gain_ctrl(s, 1);
        s->set_whitebal(s, 1);
    }
}

bool ShockGuardCamera::captureROISample(OpticalFrameSample& sample) {
    if (!_initialized) return false;

    camera_fb_t* fb = esp_camera_fb_get();
    if (!fb) return false;

    sample.timestampMs = millis();

    // Central circular Region of Interest (ROI) corresponding to the plunger contact window
    // Frame size: 160 x 120. Center: (80, 60), radius ~25 px
    const int cx = 80;
    const int cy = 60;
    const int r2 = 25 * 25;

    uint32_t totalR = 0, totalG = 0, totalB = 0;
    uint32_t count = 0;

    const uint16_t* pixels = (const uint16_t*)fb->buf;
    for (int y = cy - 25; y <= cy + 25; ++y) {
        int dy2 = (y - cy) * (y - cy);
        for (int x = cx - 25; x <= cx + 25; ++x) {
            int dx2 = (x - cx) * (x - cx);
            if (dx2 + dy2 <= r2) {
                uint16_t p = pixels[y * 160 + x];
                // RGB565 extraction
                uint8_t r = (p >> 11) & 0x1F;
                uint8_t g = (p >> 5) & 0x3F;
                uint8_t b = p & 0x1F;

                totalR += (r << 3);
                totalG += (g << 2);
                totalB += (b << 3);
                count++;
            }
        }
    }

    esp_camera_fb_return(fb);

    if (count == 0) return false;

    sample.meanRed   = (float)totalR / (count * 255.0f);
    sample.meanGreen = (float)totalG / (count * 255.0f);
    sample.meanBlue  = (float)totalB / (count * 255.0f);
    // Standard perceptual luminance: Y = 0.299 R + 0.587 G + 0.114 B
    sample.meanLuminance = 0.299f * sample.meanRed + 0.587f * sample.meanGreen + 0.114f * sample.meanBlue;

    return true;
}
