# Verification

All checks run in `scripts/verify_and_export.py` on the live FreeCAD model. The raw results are in [`Docs/verification_report.json`](../Docs/verification_report.json) and the log in [`Docs/logs/verify_log.txt`](../Docs/logs/verify_log.txt).

> These are **CAD-level geometric checks only**. They do not validate force, contact pressure, impact, optical performance, fatigue or safety.

## 1. Model integrity
| Check | Method | Result |
|---|---|---|
| Feature errors | Document object state after recompute | none |
| Solid validity | `Shape.isValid()`, solid count, closed shells for all 61 parts | 61/61 valid, 1 solid each |
| Sketches | `solve()` and `FullyConstrained` | 17/17 fully constrained |

## 2. Interference (4 mechanism states)
Pairwise boolean `common()` between every pair of the 61 parts whose bounding boxes overlap. The threshold is 0.001 mm³.

| State | Unintended overlaps | Intended |
|---|---|---|
| 1 Rest | 0 | M2 threads in pilot holes |
| 2 Cocked | 0 | " |
| 3 Released / contact | 0 | " |
| 4 Max travel | 0 | " |

The D14 reference finger touches nothing in the cocked state; the window is 0.8 mm below the skin. In states 1, 3 and 4 it overlaps only the plunger and window, which is the intended indentation.

## 3. Mechanism
| Check | Result |
|---|---|
| Latch blocks upward motion when cocked (plunger moved +0.3 mm collides with tooth) | ✅ (gap 0.1 mm) |
| Travel stop blocks over-travel (+0.3 mm beyond max collides) | ✅ (contact 0.0 mm) |
| Tooth clearance to flange OD when released | 0.17 mm |
| Spring: solid ≈ 5.6 / cocked 8 / on stop 12 / free 14 mm | space OK, 2 mm preload keeps it captive |
| Radial sliding fits | flange/guide 0.3, tube/stop 0.3, tube/plate 0.5, spring/guide 0.3, spring/collar 0.7 mm |
| Latch geometry | 1.2 mm engagement; tooth retracts 1.5 mm for a 1.95 mm button stroke |
| Moving parts → electronics (minimum over all states) | 0.4 mm (lever tip to carrier edge); spring → FPC 2.0; plunger → camera 3.9 mm |
| UI button → release mechanism | 49 mm (no mechanical coupling) |

## 4. Optics and sensing
| Check | Result |
|---|---|
| Camera view cone (lens to window, bore radius − 0.3 mm) vs all parts | no obstruction (cocked and released) |
| Cone half-angle / lens-to-skin / viewed skin diameter | 30° / 13 mm / ≈ 14 mm |
| Ring-LED outer edge inside plunger bore | r 6.3 < 6.5 mm ✅ |
| MAX30102 face relative to trough | 0.00 mm (flush) |
| PPG distance from fingertip stop / nearest moving part | 30 mm / 5.75 mm |

## 5. Assembly and service paths
Each part or group is translated in steps up to 60 mm. A step counts as blocked only if its overlap grows beyond its assembled value.

| # | Operation | Result |
|---|---|---|
| 1 | Remove 6 × M2 × 30 shell screws (down) | clear |
| 2 | Lift upper shell with display and UI button | clear |
| 3 | Remove 3 plate screws (up) | clear |
| 4 | Lift finger-support plate | clear |
| 5 | Lift travel stop | clear |
| 6 | Remove battery cover (down) | clear |
| 7 | Remove battery through floor opening | clear |
| 8 | Lift electronics tray with both PCBs | clear |
| 9 | Withdraw cocking pin and knob radially (+Y) | clear |
| 10 | Lift plunger and window from guide | clear |
| – | Plunger cannot lift with the knob fitted | confirmed: pin is fitted last |

## 6. Design rules (13/13 pass)
Roof over tunnel ≥ 1.5 · preload > 0 · solid height < cocked length · guide ≥ spring OD + 0.2 · spring/collar ≥ 0.2 · LEDs inside bore · tooth/tube ≥ 0.3 · lever below guide top · sensor mount clears guide · plate covers PPG · working distance > 0 · OLED header clears ESP32 · battery below tray.

## 7. Parameter propagation
Six inputs were changed together: length 125→135, height 42→44, tunnel width 22→20, travel 4→5, PPG offset 21→23, spring 8/14→9/16.
- Recompute gave no errors, no invalid solids, 0 interferences and 0 design-rule failures.
- Upper-shell length became 135.0 mm, height 44.0 mm and the roof 2.0 mm.
- After reverting, the maximum volume difference is **0.000 mm³**.

## 8. Exports
| Export | Re-import result |
|---|---|
| `ShockGuard_Assembly.step` | valid, 61/61 solids |
| 33 component STEPs | all valid single solids |
| 15 printable STLs | all closed solids, no non-manifold edges |
| `ShockGuard_Assembly.stl` | visualisation only (61 touching bodies) |

## 9. FDM overhang (> 45°, recommended orientation)
| Part | Orientation | Overhang area |
|---|---|---|
| Upper_Enclosure | roof on bed | 189 mm² (lens-recess ledge and roof fillet) |
| Lower_Enclosure | floor on bed | 364 mm² (counterbored boss heads, battery recess) |
| Guide / Optical_Mount / Sensor_Mount | as modelled | 52 / 38 / 16 mm² |
| All other printable parts | as modelled | 0 |

## Problems found and fixed during modelling
1. The finger rode over a 1.5 mm ridge at the front wall. The trough now continues through the wall.
2. The USB-C receptacle trapped the tray. Fixed with an open-top slot and a tongue on the upper shell.
3. The battery cable tab blocked removal. Moved onto the top of the cell.
4. Bosses exactly tangent to walls gave a non-manifold STL. They now overlap the wall.
5. The OLED PCB corner clipped the shell bosses. Display moved to x = 40.
6. A cable rib was tangent to a tray boss. Moved 0.6 mm clear.
7. The knob passes through the wall slot, so the plunger cannot be lifted out with it fitted. Assembly order is now documented: the pin goes in last.
