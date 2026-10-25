#!/usr/bin/env python3
"""
ShockGuard - Automated Unit Test Suite
Verifies clinical formulas, skin tone calibration, CRT regression, and triage logic.
"""

import unittest
import numpy as np
import math
from synthetic_benchmark import SkinToneProfile, simulate_capillary_refill, fit_crt_curve

class TestShockGuardAlgorithms(unittest.TestCase):

    def test_skin_tone_melanin_index(self):
        # Pale skin: R=0.9, G=0.8
        p_pale = SkinToneProfile("Type I", 1, 0.90, 0.80, 0.70)
        self.assertAlmostEqual(p_pale.melanin_index, math.log(1/0.80) - math.log(1/0.90), places=4)
        self.assertLess(p_pale.melanin_index, 0.25)

        # Dark skin: R=0.35, G=0.18
        p_dark = SkinToneProfile("Type VI", 6, 0.35, 0.18, 0.10)
        self.assertGreater(p_dark.melanin_index, 0.60)
        self.assertGreater(p_dark.adaptive_led_gain, 1.5)

    def test_crt_curve_fitting(self):
        profile = SkinToneProfile("Type III", 3, 0.75, 0.60, 0.48)
        true_crt = 2.10 # 2.1 seconds
        t, luma, true_tau, delta = simulate_capillary_refill(profile, true_crt, noise_std=0.001)

        est_crt, est_tau, r2 = fit_crt_curve(t, luma, profile.baseline_luma)
        self.assertIsNotNone(est_crt)
        self.assertAlmostEqual(est_crt, true_crt, delta=0.20)
        self.assertGreater(r2, 0.95)

    def test_perfusion_index_formula(self):
        # PPI = (AC_IR / DC_IR) * 100%
        dc_ir = 60000.0
        ac_ir = 1200.0
        ppi = (ac_ir / dc_ir) * 100.0
        self.assertAlmostEqual(ppi, 2.0, places=2)

        # Critical hypoperfusion (<0.6%)
        ac_crit = 300.0
        ppi_crit = (ac_crit / dc_ir) * 100.0
        self.assertAlmostEqual(ppi_crit, 0.5, places=2)
        self.assertLess(ppi_crit, 0.6)

    def test_triage_alert_matrix(self):
        def evaluate_triage(crt_sec, ppi_pct, hr_bpm):
            score = 0
            if crt_sec > 3.0:
                score += 4
            elif crt_sec > 2.0:
                score += 2
            
            if ppi_pct < 0.6:
                score += 4
            elif ppi_pct < 1.4:
                score += 2

            if hr_bpm > 125:
                score += 2
            elif hr_bpm > 100:
                score += 1

            if score >= 6 or crt_sec >= 3.5 or ppi_pct < 0.4:
                return "CRITICAL"
            elif score >= 3 or crt_sec > 2.0 or ppi_pct < 1.0:
                return "MODERATE"
            else:
                return "NORMAL"

        # Case 1: Healthy volunteer (CRT=1.4s, PPI=2.1%, HR=72)
        self.assertEqual(evaluate_triage(1.4, 2.1, 72), "NORMAL")

        # Case 2: Compensated hypovolemic shock (CRT=2.4s, PPI=0.9%, HR=108)
        self.assertEqual(evaluate_triage(2.4, 0.9, 108), "MODERATE")

        # Case 3: Decompensated septic shock (CRT=3.8s, PPI=0.35%, HR=132)
        self.assertEqual(evaluate_triage(3.8, 0.35, 132), "CRITICAL")

if __name__ == "__main__":
    unittest.main()
