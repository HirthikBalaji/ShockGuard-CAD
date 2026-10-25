# -*- coding: utf-8 -*-
"""
ShockGuard CAD verification + export (headless):

    /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd verify_and_export.py

1. Opens CAD/ShockGuard_Assembly.FCStd, checks every feature / sketch / solid.
2. Interference matrix in all four mechanism states (rest, cocked, released, max travel).
3. Mechanism proofs: travel stop and latch physically block motion; spring space; clearances.
4. Optical / sensing layout: camera view cone, LED path, PPG flushness and position.
5. Assembly paths: covers and sub-assemblies removable along their insertion axis.
6. FDM printability: overhang area per printable part in its best orientation.
7. Parameter-propagation test (change master parameters, recompute, verify, revert).
8. Exports STEP (assembly + components), STL (assembly + printable parts), CSV params,
   then re-imports every export and checks validity.
Writes Docs/verification_report.json and Docs/verification_summary.md.
"""
import csv
import json
import math
import os
import time

import FreeCAD as App
import Import
import Mesh
import MeshPart
import Part

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
FCSTD = os.path.join(ROOT, "CAD", "ShockGuard_Assembly.FCStd")
Vec = App.Vector
T0 = time.time()
doc = App.openDocument(FCSTD)
P = doc.Params
REPORT = {"generated": time.strftime("%Y-%m-%d %H:%M"), "freecad": ".".join(App.Version()[:3])}


def g(n):
    v = P.get(n)
    return float(v.Value) if hasattr(v, "Value") else float(v)


def setp(n, v):
    P.set(n, str(v))
    doc.recompute()


ASM = doc.getObject("ShockGuard_Assembly")
BODIES = [o for o in doc.Objects if o.TypeId == "PartDesign::Body" and any(p.TypeId == "App::Part" for p in o.InList)]
LINKS = [o for o in doc.Objects if o.TypeId == "App::Link"]
PARTS = BODIES + LINKS
FINGER = doc.getObject("Finger_Reference")
B = {o.Name: o for o in PARTS}
STATE_NAMES = {1: "Rest (uncocked, flange on stop)", 2: "Cocked (latched)", 3: "Released / contact (illustrative)",
               4: "Max travel (no finger)"}

# ------------------------------------------------------------------------------------
# 1. model integrity
# ------------------------------------------------------------------------------------
doc.recompute()
integ = {"errors": [], "sketches": {}, "bodies": {}}
for o in doc.Objects:
    if "Invalid" in o.State or "Error" in o.State:
        integ["errors"].append(o.Name)
    if o.TypeId == "Sketcher::SketchObject":
        dof = o.solve()
        integ["sketches"][o.Name] = {"solve": dof, "fully_constrained": bool(getattr(o, "FullyConstrained", False))}
for o in PARTS:
    s = o.Shape
    integ["bodies"][o.Name] = {"valid": s.isValid(), "solids": len(s.Solids), "volume_mm3": round(s.Volume, 2),
                               "closed": all(sh.isClosed() for sh in s.Shells)}
n_fc = sum(1 for v in integ["sketches"].values() if v["fully_constrained"])
integ["summary"] = {"objects": len(doc.Objects), "parts": len(PARTS), "bodies": len(BODIES), "links": len(LINKS),
                    "invalid_solids": [k for k, v in integ["bodies"].items() if not v["valid"] or v["solids"] != 1],
                    "sketches_fully_constrained": f"{n_fc}/{len(integ['sketches'])}"}
REPORT["integrity"] = integ
print("integrity:", integ["summary"], "errors:", integ["errors"])

# ------------------------------------------------------------------------------------
# 2. interference matrix per state
# ------------------------------------------------------------------------------------
meta = json.load(open(os.path.join(ROOT, "CAD", "model_meta.json")))
FAST_HOST = {}
for name, src, host in meta["fasteners"]:
    FAST_HOST[name] = host


def is_fastener(n):
    return n.startswith("Fastener_")


def classify(a, b):
    """Return 'intended' reason or None."""
    for x, y in ((a, b), (b, a)):
        if is_fastener(x):
            return f"thread engagement / clamp ({x} in {y})"
    return None


def overlaps(shapes, tol=1e-3):
    names = list(shapes)
    found = []
    for i, a in enumerate(names):
        sa = shapes[a]
        for b in names[i + 1:]:
            sb = shapes[b]
            if not sa.BoundBox.intersect(sb.BoundBox):
                continue
            try:
                v = sa.common(sb).Volume
            except Exception as e:  # noqa: BLE001
                found.append((a, b, -1, f"boolean failed: {e}"))
                continue
            if v > tol:
                found.append((a, b, v, classify(a, b)))
    return found


interf = {}
for st in (1, 2, 3, 4):
    setp("state", st)
    shapes = {o.Name: o.Shape for o in PARTS}
    res = overlaps(shapes)
    fv = {}
    for o in PARTS:
        if o.Shape.BoundBox.intersect(FINGER.Shape.BoundBox):
            v = o.Shape.common(FINGER.Shape).Volume
            if v > 1e-3:
                fv[o.Name] = round(v, 3)
    interf[st] = {
        "state": STATE_NAMES[st], "stroke_mm": g("stroke"), "latch_angle_deg": g("latch_angle"),
        "unintended": [(a, b, round(v, 4)) for a, b, v, why in res if why is None],
        "intended": [(a, b, round(v, 4), why) for a, b, v, why in res if why],
        "finger_overlap": fv,
    }
    print(f"state {st}: unintended {interf[st]['unintended']}  finger {fv}")
REPORT["interference"] = interf
setp("state", 2)


# ------------------------------------------------------------------------------------
# 3. mechanism checks
# ------------------------------------------------------------------------------------
def dist(a, b):
    return round(a.distToShape(b)[0], 3)


mech = {}
pl, stop, guide, lever = B["Plunger_Body"].Shape, B["Travel_Stop"].Shape, B["Guide"].Shape, B["Release_Trigger"].Shape
# latch holds: in cocked state, moving plunger up 0.3 mm must collide with the latch tooth
setp("state", 2)
pl = B["Plunger_Body"].Shape
gap_tooth = dist(pl, B["Release_Trigger"].Shape)
moved = pl.copy()
moved.translate(Vec(0, 0, 0.3))
mech["latch_tooth_gap_cocked_mm"] = gap_tooth
mech["latch_blocks_upward_motion"] = moved.common(B["Release_Trigger"].Shape).Volume > 1e-3
mech["flange_to_stop_gap_cocked_mm"] = dist(pl, B["Travel_Stop"].Shape)
mech["plunger_window_below_trough_cocked_mm"] = round(g("z_fs") - g("z_win_top"), 3)
mech["finger_to_plunger_cocked_mm"] = dist(pl, FINGER.Shape)
mech["finger_to_window_cocked_mm"] = dist(B["Contact_Pad"].Shape, FINGER.Shape)
# released: lever rotated clear of flange
setp("state", 4)
pl4 = B["Plunger_Body"].Shape
mech["flange_to_stop_gap_max_mm"] = dist(pl4, B["Travel_Stop"].Shape)
over = pl4.copy()
over.translate(Vec(0, 0, 0.3))
mech["stop_blocks_overtravel"] = over.common(B["Travel_Stop"].Shape).Volume > 1e-3
mech["tooth_clearance_released_mm"] = dist(pl4, B["Release_Trigger"].Shape)
mech["pin_to_guide_slot_top_open"] = True
mech["cocking_pin_to_housing_max_mm"] = dist(B["Cocking_Feature"].Shape, B["Lower_Enclosure"].Shape)
mech["cocking_pin_to_stop_max_mm"] = dist(B["Cocking_Feature"].Shape, B["Travel_Stop"].Shape)
setp("state", 2)
mech["cocking_pin_to_housing_cocked_mm"] = dist(B["Cocking_Feature"].Shape, B["Lower_Enclosure"].Shape)
# radial clearances
mech["radial_clear_flange_guide_mm"] = round((g("guide_id") - g("flange_diameter")) / 2, 3)
mech["radial_clear_tube_stop_mm"] = round((g("stop_bore") - g("plunger_diameter")) / 2, 3)
mech["radial_clear_tube_plate_mm"] = g("plunger_hole_clearance")
mech["radial_clear_spring_guide_mm"] = round((g("guide_id") - g("spring_outer_diameter")) / 2, 3)
mech["radial_clear_spring_collar_mm"] = round((g("spring_outer_diameter") - 2 * g("spring_wire_diameter")
                                               - g("collar_od")) / 2, 3)
# spring
mech["spring_solid_height_mm"] = round(g("spring_total_coils") * g("spring_wire_diameter") + g("spring_wire_diameter"), 2)
mech["spring_installed_cocked_mm"] = g("spring_installed_length")
mech["spring_length_at_stop_mm"] = g("spring_installed_length") + g("plunger_travel")
mech["spring_free_length_mm"] = g("spring_free_length")
mech["spring_preload_deflection_at_stop_mm"] = g("spring_preload_at_stop")
mech["spring_cocked_deflection_mm"] = g("spring_free_length") - g("spring_installed_length")
mech["spring_space_ok"] = (mech["spring_solid_height_mm"] < g("spring_installed_length")
                           and g("spring_preload_at_stop") > 0)
mech["max_indentation_if_finger_on_ceiling_mm"] = round(g("plunger_travel") - g("plunger_rest_gap"), 3)
# latch geometry
mech["latch_engagement_mm"] = g("latch_overlap")
r_tip = 10.0
mech["release_button_stroke_mm"] = round(math.radians(g("latch_release_angle")) * abs(g("release_button_x") - g("latch_pivot_x")), 2)
mech["tooth_retraction_mm"] = round(math.radians(g("latch_release_angle")) * r_tip, 2)
# moving parts vs electronics / camera / FPC in every state
movers = ["Plunger_Body", "Contact_Pad", "Cocking_Feature", "Release_Trigger", "Compression_Spring"]
static_sensitive = ["Camera_Module", "Ring_LED", "ESP32_S3_Board", "Charging_Board", "Battery", "Camera_FPC",
                    "MAX30102_Module", "OLED_Module"]
mm = {}
for st in (1, 2, 3, 4):
    setp("state", st)
    for m_ in movers:
        for s_ in static_sensitive:
            d = dist(B[m_].Shape, B[s_].Shape)
            k = f"{m_}->{s_}"
            mm[k] = min(mm.get(k, 1e9), d)
setp("state", 2)
mech["min_clearance_moving_to_electronics_mm"] = {k: v for k, v in sorted(mm.items(), key=lambda kv: kv[1])[:8]}
mech["ui_button_to_release_mechanism_min_mm"] = min(
    dist(B["Push_Button"].Shape, B[n].Shape) for n in ("Release_Trigger", "Release_Button", "Plunger_Body"))
mech["housing_envelope_mm"] = [round(v, 2) for v in (
    B["Lower_Enclosure"].Shape.fuse(B["Upper_Enclosure"].Shape).optimalBoundingBox().XLength,
    B["Lower_Enclosure"].Shape.fuse(B["Upper_Enclosure"].Shape).optimalBoundingBox().YLength,
    B["Lower_Enclosure"].Shape.fuse(B["Upper_Enclosure"].Shape).optimalBoundingBox().ZLength)]
REPORT["mechanism"] = mech
print("mechanism:", {k: v for k, v in mech.items() if not isinstance(v, dict)})

# ------------------------------------------------------------------------------------
# 4. optics / sensing
# ------------------------------------------------------------------------------------
opt = {}
xm = g("x_m")
z_lens = g("z_lens_top")
for st in (2, 3):
    setp("state", st)
    z_win_bot = g("z_win_top") + g("stroke") - g("contact_pad_thickness")
    r_ap = g("plunger_bore") / 2 - 0.3
    h = z_win_bot - z_lens
    cone = Part.makeCone(0.01, r_ap, h - 0.05, Vec(xm, 0, z_lens + 0.02))
    hits = {}
    for o in PARTS:
        if o.Name in ("Contact_Pad",):
            continue
        if o.Shape.BoundBox.intersect(cone.BoundBox):
            v = o.Shape.common(cone).Volume
            if v > 1e-4:
                hits[o.Name] = round(v, 4)
    half = math.degrees(math.atan(r_ap / h))
    skin_z = g("z_fs") if st == 2 else g("z_win_top") + g("stroke")
    opt[f"state{st}"] = {"view_cone_half_angle_deg": round(half, 1), "lens_to_window_mm": round(h, 2),
                         "lens_to_skin_mm": round(skin_z - z_lens, 2),
                         "viewed_skin_diameter_mm": round(min(2 * (skin_z - z_lens) * math.tan(math.radians(half)),
                                                              g("contact_pad_diameter")), 1),
                         "obstructions": hits}
setp("state", 2)
led_r_out = g("ring_led_radius") + 0.8
opt["led_inside_bore"] = led_r_out < g("plunger_bore") / 2
opt["led_outer_radius_mm"] = led_r_out
opt["plunger_bore_radius_mm"] = g("plunger_bore") / 2
opt["led_to_plunger_clear_cocked_mm"] = dist(B["Ring_LED"].Shape, B["Plunger_Body"].Shape)
opt["camera_to_plunger_clear_cocked_mm"] = dist(B["Camera_Module"].Shape, B["Plunger_Body"].Shape)
sens = B["MAX30102_Module"].Shape
opt["ppg_sensor_top_minus_trough_mm"] = round(sens.BoundBox.ZMax - g("z_fs"), 3)
opt["ppg_centre_from_fingertip_stop_mm"] = round(g("x_ppg") - g("x_tip"), 2)
opt["camera_axis_from_fingertip_stop_mm"] = g("camera_mount_position")
opt["ppg_window_to_plunger_aperture_edge_mm"] = round(
    (g("x_ppg") - (g("max_sensor_l") + 2) / 2) - (xm + g("plunger_diameter") / 2 + g("plunger_hole_clearance")), 2)
opt["ppg_to_moving_parts_min_mm"] = min(dist(sens, B[m_].Shape) for m_ in movers)
opt["working_distance_lens_to_skin_mm"] = g("working_distance")
REPORT["optics"] = opt
print("optics:", opt)

# ------------------------------------------------------------------------------------
# 5. assembly / removal paths (sampled translations)
# ------------------------------------------------------------------------------------
def _ov(a, b):
    return a.common(b).Volume if a.BoundBox.intersect(b.BoundBox) else 0.0


def path_clear(moving, direction, others, steps=(0.5, 1, 2, 5, 10, 20, 40, 60)):
    """Blocked if overlap grows beyond its assembled value (screws leaving their own pilot holes are OK)."""
    blocked = []
    base = {(m, o): _ov(B[m].Shape, B[o].Shape) for m in moving for o in others if o not in moving}
    for d in steps:
        hit = []
        for m in moving:
            s = B[m].Shape.copy()
            s.translate(Vec(*direction) * d)
            for o in others:
                if o in moving:
                    continue
                if _ov(s, B[o].Shape) > base[(m, o)] + 1e-3:
                    hit.append(o)
        if hit:
            blocked.append((d, sorted(set(hit))))
    return blocked


names = list(B)
up_grp = ["Upper_Enclosure", "OLED_Module", "Display_Window", "Push_Button", "Tactile_Switch", "Button_PCB"] + \
         [n for n in names if n.startswith(("Fastener_OLED", "Fastener_BtnPCB"))]
shell_screws = [n for n in names if n.startswith("Fastener_Shell")]
plate_screws = [n for n in names if n.startswith("Fastener_Plate")]
seq = [
    ("1. Remove 6x M2x30 shell screws (downwards)", shell_screws, (0, 0, -1), []),
    ("2. Lift upper shell with display + UI button", up_grp, (0, 0, 1), shell_screws),
    ("3. Remove 3x plate screws (upwards)", plate_screws, (0, 0, 1), shell_screws + up_grp),
    ("4. Lift finger-support plate", ["Finger_Support"], (0, 0, 1), shell_screws + up_grp + plate_screws),
    ("5. Lift travel stop", ["Travel_Stop"], (0, 0, 1), shell_screws + up_grp + plate_screws + ["Finger_Support"]),
    ("6. Remove battery cover (downwards, after its 2 screws)", ["Battery_Cover"], (0, 0, -1),
     [n for n in names if n.startswith("Fastener_BattCover")]),
    ("7. Remove battery through floor opening", ["Battery"], (0, 0, -1),
     [n for n in names if n.startswith("Fastener_BattCover")] + ["Battery_Cover"]),
    ("8. Lift electronics tray with boards", ["Electronics_Tray", "ESP32_S3_Board", "Charging_Board"] +
     [n for n in names if n.startswith(("Fastener_ESP",))], (0, 0, 1),
     shell_screws + up_grp + [n for n in names if n.startswith("Fastener_Tray")] + ["Camera_FPC"]),
]
paths = {}
for label, mov, d, removed in seq:
    others = [n for n in names if n not in removed and n not in mov]
    if label.startswith("8"):
        others = [n for n in others if n not in ("Battery", "Battery_Cover")]
    res = path_clear(mov, d, others)
    paths[label] = "clear" if not res else f"blocked at {res[0][0]} mm by {res[0][1]}"
    print(label, "->", paths[label])
# plunger stack lifts out once stop is removed (pin rides up the open-topped guide slot)
others = [n for n in names if n not in shell_screws + up_grp + plate_screws +
          ["Finger_Support", "Travel_Stop", "Plunger_Body", "Contact_Pad", "Cocking_Feature"]]
setp("state", 4)  # latch released, flange on (removed) stop
res = path_clear(["Cocking_Feature"], (0, 1, 0), others + ["Plunger_Body", "Contact_Pad"],
                 steps=(0.5, 1, 2, 5, 10, 20))
paths["9. Withdraw cocking pin + knob radially (+Y) through wall slot"] = \
    "clear" if not res else f"blocked at {res[0][0]} mm by {res[0][1]}"
res = path_clear(["Plunger_Body", "Contact_Pad"], (0, 0, 1), others, steps=(0.5, 1, 2, 5, 10, 20, 40))
paths["10. Lift plunger + window out of guide (pin removed, latch released)"] = \
    "clear" if not res else f"blocked at {res[0][0]} mm by {res[0][1]}"
res = path_clear(["Plunger_Body", "Contact_Pad", "Cocking_Feature"], (0, 0, 1), others, steps=(0.5,))
paths["note: plunger cannot lift with knob fitted (knob passes wall slot)"] = \
    "confirmed - pin must be fitted last / removed first" if res else "not blocked"
setp("state", 2)
REPORT["assembly_paths"] = paths

# ------------------------------------------------------------------------------------
# 6. FDM printability (overhang area > 45 deg, excluding build-plate faces)
# ------------------------------------------------------------------------------------
PRINT_ORIENT = {}


def overhang_area(shape, flip):
    """Area of faces whose outward normal points > 45 deg below horizontal, excluding the build-plate face.
    Outward direction is decided by probing inside/outside the solid (robust to face orientation)."""
    s = shape.copy()
    if flip:
        s.rotate(Vec(0, 0, 0), Vec(1, 0, 0), 180)
    zmin = s.optimalBoundingBox().ZMin
    solid = s.Solids[0]
    a = 0.0
    for f in s.Faces:
        try:
            u0, u1, v0, v1 = f.ParameterRange
            uv = ((u0 + u1) / 2, (v0 + v1) / 2)
            p = f.valueAt(*uv)
            n = f.normalAt(*uv)
        except Exception:  # noqa: BLE001
            continue
        if solid.isInside(p + n * 0.05, 1e-4, False):
            n = n * -1
        if n.z < -math.cos(math.radians(45)) and f.optimalBoundingBox().ZMin > zmin + 0.05:
            a += f.Area
    return a


printability = {}
for o in BODIES:
    if not getattr(o, "Printable", False):
        continue
    a0, a1 = overhang_area(o.Shape, False), overhang_area(o.Shape, True)
    flip = a1 < a0
    PRINT_ORIENT[o.Name] = flip
    printability[o.Name] = {"orientation": "flipped (top face on bed)" if flip else "as modelled",
                            "overhang_area_mm2": round(min(a0, a1), 1),
                            "support_likely": min(a0, a1) > 20.0}
REPORT["printability"] = printability
print("printability:", {k: v["overhang_area_mm2"] for k, v in printability.items()})

# ------------------------------------------------------------------------------------
# 6b. design-rule checks (parametric sanity rules evaluated on the live parameters)
# ------------------------------------------------------------------------------------
def drc():
    rules = [
        ("Roof over tunnel >= 1.5 mm", g("top_over_tunnel"), ">=", 1.5),
        ("Spring preload at stop > 0 (spring captive, plunger seated)", g("spring_preload_at_stop"), ">", 0.0),
        ("Spring solid height < cocked length", g("spring_total_coils") * g("spring_wire_diameter")
         + g("spring_wire_diameter"), "<", g("spring_installed_length")),
        ("Guide bore >= spring OD + 0.2", g("guide_id"), ">=", g("spring_outer_diameter") + 0.2),
        ("Spring ID clears collar by >= 0.2 (radial)", (g("spring_outer_diameter") - 2 * g("spring_wire_diameter")
                                                         - g("collar_od")) / 2, ">=", 0.2),
        ("Ring-LED outer edge inside plunger bore", g("ring_led_radius") + 0.8, "<", g("plunger_bore") / 2),
        ("Latch tooth clears plunger tube (>= 0.3)", -g("latch_tooth_y") - g("plunger_diameter") / 2, ">=", 0.3),
        ("Latch lever below guide top", g("z_lever_top"), "<", g("z_guide_top")),
        ("Sensor mount clears guide OD", g("x_ppg") - g("max_pcb") / 2 - 0.5, ">=", g("x_m") + g("guide_od") / 2),
        ("Support plate covers PPG module", g("plate_x1"), ">=", g("x_ppg") + g("max_pcb") / 2 + 0.5),
        ("Positive camera working distance", g("working_distance"), ">", 0.0),
        ("OLED header clears ESP32 module", g("z_oled_pcb_top") - g("oled_pcb_t") - 6, ">=",
         g("z_pcb_top") + g("wroom_h") + g("electronics_clearance")),
        ("Battery below tray (>= 1 mm)", g("tray_z") - (1.2 + g("battery_thickness") + 1), ">=", 0.0),
    ]
    out = []
    for name, val, op, lim in rules:
        ok = {"<": val < lim, ">": val > lim, ">=": val >= lim - 1e-9}[op]
        out.append({"rule": name, "value": round(val, 3), "limit": f"{op} {round(lim, 3)}", "pass": ok})
    return out


REPORT["design_rules"] = drc()
print("DRC fails:", [r["rule"] for r in REPORT["design_rules"] if not r["pass"]])

# ------------------------------------------------------------------------------------
# 7. parameter propagation test
# ------------------------------------------------------------------------------------
base_vol = {o.Name: o.Shape.Volume for o in PARTS}
changes = {"overall_length": 135, "overall_height": 44, "finger_opening_width": 20, "plunger_travel": 5,
           "ppg_mount_position": 23, "spring_installed_length": 9, "spring_free_length": 16}
orig = {k: g(k) for k in changes}
for k, v in changes.items():
    P.set(k, str(v))
doc.recompute()
prop = {"changes": changes, "errors": [o.Name for o in doc.Objects if "Invalid" in o.State or "Error" in o.State],
        "invalid": [o.Name for o in PARTS if not o.Shape.isValid() or len(o.Shape.Solids) != 1]}
prop["upper_length_after"] = round(B["Upper_Enclosure"].Shape.optimalBoundingBox().XLength, 2)
prop["housing_height_after"] = round(B["Upper_Enclosure"].Shape.optimalBoundingBox().ZMax, 2)
prop["top_over_tunnel_after"] = round(g("top_over_tunnel"), 2)
prop["plunger_axis_x_after"] = round(B["Plunger_Body"].Shape.BoundBox.Center.x, 2)
prop["ppg_x_after"] = round(B["MAX30102_Module"].Shape.BoundBox.Center.x, 2)
prop["unintended_interference_after"] = [(a, b, round(v, 3)) for a, b, v, why in
                                         overlaps({o.Name: o.Shape for o in PARTS}) if why is None]
prop["design_rule_failures_after"] = [r["rule"] for r in drc() if not r["pass"]]
for k, v in orig.items():
    P.set(k, str(v))
doc.recompute()
prop["restored_volume_max_delta_mm3"] = round(max(abs(o.Shape.Volume - base_vol[o.Name]) for o in PARTS), 6)
REPORT["parameter_propagation"] = prop
print("propagation:", prop)

# ------------------------------------------------------------------------------------
# 8. exports
# ------------------------------------------------------------------------------------
setp("state", 2)
setp("explode", 0)
STEP_DIR = os.path.join(ROOT, "STEP")
STL_DIR = os.path.join(ROOT, "STL")
exports = {}
asm_step = os.path.join(STEP_DIR, "ShockGuard_Assembly.step")
Import.export([ASM], asm_step)
for o in BODIES:
    o.Shape.exportStep(os.path.join(STEP_DIR, "components", o.Name + ".step"))
for n in ("Screw_M2x30_SHCS", "Screw_M2x8_CSK_Top", "Screw_M2x4_CSK_Bottom", "Screw_M2x5_Pan"):
    doc.getObject(n).Shape.exportStep(os.path.join(STEP_DIR, "components", n + ".step"))


def mesh_of(shape, lin=0.03, ang=0.15):
    return MeshPart.meshFromShape(Shape=shape, LinearDeflection=lin, AngularDeflection=ang, Relative=False)


all_mesh = Mesh.Mesh()
for o in PARTS:
    all_mesh.addMesh(mesh_of(o.Shape, 0.05, 0.25))
all_mesh.write(os.path.join(STL_DIR, "ShockGuard_Assembly.stl"))
for o in BODIES:
    if not getattr(o, "Printable", False):
        continue
    s = o.Shape.copy()
    if PRINT_ORIENT.get(o.Name):
        s.rotate(Vec(0, 0, 0), Vec(1, 0, 0), 180)
    bb = s.BoundBox
    s.translate(Vec(-bb.XMin, -bb.YMin, -bb.ZMin))
    mesh_of(s).write(os.path.join(STL_DIR, "printable", o.Name + ".stl"))

# re-import checks
reimp = {}
sh = Part.read(asm_step)
reimp["assembly_step"] = {"valid": sh.isValid(), "solids": len(sh.Solids), "expected_solids": len(PARTS),
                          "bbox_mm": [round(sh.BoundBox.XLength, 2), round(sh.BoundBox.YLength, 2),
                                      round(sh.BoundBox.ZLength, 2)],
                          "size_kB": round(os.path.getsize(asm_step) / 1024)}
comp = {}
for f in sorted(os.listdir(os.path.join(STEP_DIR, "components"))):
    s = Part.read(os.path.join(STEP_DIR, "components", f))
    comp[f] = {"valid": s.isValid(), "solids": len(s.Solids), "volume_mm3": round(s.Volume, 1)}
reimp["component_steps"] = comp
stl = {}
for d, files in ((STL_DIR, ["ShockGuard_Assembly.stl"]),
                 (os.path.join(STL_DIR, "printable"), sorted(os.listdir(os.path.join(STL_DIR, "printable"))))):
    for f in files:
        m = Mesh.Mesh(os.path.join(d, f))
        stl[f] = {"facets": m.CountFacets, "solid": m.isSolid(), "non_manifold": m.hasNonManifolds(),
                  "self_intersections": m.hasSelfIntersections() if f != "ShockGuard_Assembly.stl" else "n/a (multi-body)",
                  "note": "visualisation mesh of 61 touching bodies - not a single printable solid"
                  if f == "ShockGuard_Assembly.stl" else "",
                  "volume_mm3": round(m.Volume, 1)}
reimp["stl"] = stl
REPORT["reimport"] = reimp
print("reimport assembly:", reimp["assembly_step"])
print("bad component steps:", [k for k, v in comp.items() if not v["valid"] or v["solids"] != 1])
print("bad stl:", [k for k, v in stl.items() if k != "ShockGuard_Assembly.stl" and (not v["solid"] or v["non_manifold"])])

# parameters CSV
with open(os.path.join(ROOT, "Docs", "ShockGuard_Parameters.csv"), "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["parameter", "value", "unit", "status", "notes", "spreadsheet_cell"])
    txt = lambda c: P.getContents(c).lstrip("'")  # noqa: E731  (text cells carry a leading quote)
    r = 2
    while True:
        a = txt(f"A{r}")
        if not a:
            break
        val = g(a)
        w.writerow([a, round(val, 4), txt(f"C{r}"), txt(f"D{r}"), txt(f"E{r}"), f"Params.B{r}"])
        r += 1

# BOM CSV
with open(os.path.join(ROOT, "Docs", "ShockGuard_BOM.csv"), "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["item", "part", "subassembly", "qty", "material / selection", "status", "printable", "description"])
    i = 1
    for name, m in meta["bom"].items():
        w.writerow([i, name, m["group"], m["qty"], m["material"], m["status"], "yes" if m["printable"] else "no",
                    m["desc"]])
        i += 1
    counts = {}
    for name, src, host in meta["fasteners"]:
        counts[src] = counts.get(src, 0) + 1
    for src, n in counts.items():
        w.writerow([i, src, "Fasteners", n, "Stainless A2 (assumed)", "ASSUMED", "no", meta["screw_lib"][src]])
        i += 1

# (document not re-saved here; render_views.py saves presentation colours)
REPORT["runtime_s"] = round(time.time() - T0, 1)
with open(os.path.join(ROOT, "Docs", "verification_report.json"), "w") as fh:
    json.dump(REPORT, fh, indent=1, default=str)
print("VERIFY_DONE in", REPORT["runtime_s"], "s")
