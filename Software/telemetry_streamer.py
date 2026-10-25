#!/usr/bin/env python3
"""
ShockGuard - Real-Time Telemetry Streamer & Diagnostic Monitor
Connects to ShockGuard ESP32-S3 via USB Serial and parses real-time
CRT optical waveforms, photoplethysmography (PPG), and triage risk alerts.
"""

import sys
import json
import time
import argparse

def parse_telemetry_line(line: str):
    line = line.strip()
    if not line.startswith("{") or not line.endswith("}"):
        return None
    try:
        data = json.loads(line)
        return data
    except json.JSONDecodeError:
        return None

def main():
    parser = argparse.ArgumentParser(description="ShockGuard Telemetry Streamer")
    parser.add_argument("--port", type=str, default=None, help="Serial port (e.g., /dev/tty.usbmodem1101)")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate (default: 115200)")
    parser.add_argument("--mock", action="store_true", help="Run with simulated mock stream")
    args = parser.parse_args()

    print("==================================================")
    print("ShockGuard Medical Telemetry Interface")
    print("Capillary Refill (CRT) & Perfusion Index (PPI)")
    print("==================================================")

    if args.mock or args.port is None:
        print("[INFO] Operating in simulation mode. Emulating ESP32-S3 data stream...")
        import math
        t0 = time.time()
        tau = 1.9 / 2.3026
        try:
            while True:
                dt = time.time() - t0
                # Simulate blanching release at t = 1.0s
                if dt < 1.0:
                    luma = 0.45
                else:
                    luma = 0.45 + 0.12 * math.exp(-(dt - 1.0) / tau)
                
                # Cardiac pulse simulation (75 BPM)
                hr_phase = dt * (75.0 / 60.0) * 2 * math.pi
                ir_raw = int(65000 + 1200 * math.sin(hr_phase))
                red_raw = int(58000 + 800 * math.sin(hr_phase))

                packet = {
                    "t": int(dt * 1000),
                    "luma": round(luma, 4),
                    "r": round(0.55 * luma, 4),
                    "g": round(0.35 * luma, 4),
                    "b": round(0.20 * luma, 4),
                    "ir": ir_raw,
                    "red": red_raw
                }
                print(f"[STREAM] {json.dumps(packet)}")
                time.sleep(0.05)
                if dt > 6.0:
                    print("\n[RESULT] Triage: PERFUSION ADEQUATE | CRT: 1.88s | PPI: 1.84% | HR: 75 BPM")
                    break
        except KeyboardInterrupt:
            print("\nStream stopped.")
    else:
        try:
            import serial
            ser = serial.Serial(args.port, args.baud, timeout=1)
            print(f"[OK] Connected to {args.port} at {args.baud} baud.")
            while True:
                line = ser.readline().decode('utf-8', errors='replace')
                if line:
                    data = parse_telemetry_line(line)
                    if data:
                        print(f"[DATA] t={data.get('t')}ms | Luma={data.get('luma')} | IR={data.get('ir')}")
                    else:
                        print(line.strip())
        except ImportError:
            print("[ERR] pyserial not installed. Install via: pip install pyserial")
        except Exception as e:
            print(f"[ERR] Serial communication failed: {e}")

if __name__ == "__main__":
    main()
