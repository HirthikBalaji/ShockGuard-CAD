# -*- coding: utf-8 -*-
"""
ShockGuard parametric CAD generator (FreeCAD 1.1, PartDesign + Sketcher + Spreadsheet).

Run headless:
    /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd build_shockguard.py

Creates  ../CAD/ShockGuard_Assembly.FCStd

Modelling conventions
  * Global frame: X = finger axis (finger enters from +X, fingertip stop at x_tip),
    Y = width (+Y = cocking-knob side, -Y = release-button side), Z = up, origin at the
    rear-bottom-centre of the housing.
  * Every part is a PartDesign Body built in assembly coordinates at the COCKED position.
    All feature dimensions and positions are expressions bound to the `Params` spreadsheet.
  * Motion and exploded configurations are Body/Link Placement expressions driven by
    Params.state (1..4) and Params.explode (0/1).
"""
import math
import os
import re
import sys

import FreeCAD as App
import Part  # noqa: F401  (loads OCC types)
import Sketcher

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sg_params  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OUT_FCSTD = os.path.join(ROOT, "CAD", "ShockGuard_Assembly.FCStd")

Vec, Rot, Plc = App.Vector, App.Rotation, App.Placement
V = sg_params.python_eval_all()
_ENV = {"sin": lambda d: math.sin(math.radians(d)), "cos": lambda d: math.cos(math.radians(d))}
_TOK = re.compile(r"\$([A-Za-z_]\w*)")


def fc(e):
    """'$name' -> 'Params.name' for FreeCAD expressions."""
    return _TOK.sub(r"Params.\1", str(e))


def pv(e):
    """Evaluate a '$name' expression in Python (seed values for sketches)."""
    return float(eval(_TOK.sub(r'V["\1"]', str(e)), dict(_ENV, V=V)))


def bind(obj, prop, e):
    obj.setExpression(prop, fc(e))


doc = App.newDocument("ShockGuard_Assembly")
doc.Label = "ShockGuard_Assembly"

# ------------------------------------------------------------------------------------
# Master parameter spreadsheet
# ------------------------------------------------------------------------------------
ss = doc.addObject("Spreadsheet::Sheet", "Params")
ss.Label = "Params"
for col, h in zip("ABCDE", ["Parameter", "Value", "Unit", "Status", "Notes"]):
    ss.set(f"{col}1", h)
row = 2
for alias, val, unit, status, note in sg_params.INPUTS:
    ss.set(f"A{row}", alias)
    ss.set(f"B{row}", str(val))
    ss.set(f"C{row}", unit)
    ss.set(f"D{row}", status)
    ss.set(f"E{row}", note)
    ss.setAlias(f"B{row}", alias)
    row += 1
for alias, formula, note in sg_params.DERIVED:
    ss.set(f"A{row}", alias)
    ss.set(f"B{row}", "=" + formula)
    ss.set(f"C{row}", "deg" if alias == "latch_angle" else "mm")
    ss.set(f"D{row}", "DERIVED")
    ss.set(f"E{row}", note)
    ss.setAlias(f"B{row}", alias)
    row += 1
doc.recompute()

# ------------------------------------------------------------------------------------
# Feature helpers (all dimensions are expressions)
# ------------------------------------------------------------------------------------
AX_ROT = {"z": Rot(), "x": Rot(Vec(0, 1, 0), 90), "y": Rot(Vec(1, 0, 0), -90)}


def _place(f, x, y, z, rot=None):
    f.Placement = Plc(Vec(pv(x), pv(y), pv(z)), rot or Rot())
    bind(f, ".Placement.Base.x", x)
    bind(f, ".Placement.Base.y", y)
    bind(f, ".Placement.Base.z", z)


def box(body, name, x0, x1, y0, y1, z0, z1, sub=False):
    f = body.newObject("PartDesign::%sBox" % ("Subtractive" if sub else "Additive"), name)
    bind(f, "Length", f"({x1}) - ({x0})")
    bind(f, "Width", f"({y1}) - ({y0})")
    bind(f, "Height", f"({z1}) - ({z0})")
    _place(f, x0, y0, z0)
    return f


def cbox(body, name, cx, cy, z0, lx, ly, z1, sub=False):
    """Box centred in XY."""
    return box(body, name, f"({cx}) - ({lx}) / 2", f"({cx}) + ({lx}) / 2",
               f"({cy}) - ({ly}) / 2", f"({cy}) + ({ly}) / 2", z0, z1, sub)


def cyl(body, name, axis, x, y, z, r, h, sub=False):
    f = body.newObject("PartDesign::%sCylinder" % ("Subtractive" if sub else "Additive"), name)
    bind(f, "Radius", r)
    bind(f, "Height", h)
    _place(f, x, y, z, AX_ROT[axis])
    return f


def sphere(body, name, x, y, z, r, sub=False):
    f = body.newObject("PartDesign::%sSphere" % ("Subtractive" if sub else "Additive"), name)
    bind(f, "Radius", r)
    _place(f, x, y, z)
    return f


def cone(body, name, axis, x, y, z, r1, r2, h, sub=False):
    f = body.newObject("PartDesign::%sCone" % ("Subtractive" if sub else "Additive"), name)
    bind(f, "Radius1", r1)
    bind(f, "Radius2", r2)
    bind(f, "Height", h)
    _place(f, x, y, z, AX_ROT[axis])
    return f


def sketch(body, name, x, y, z, rot=None):
    sk = body.newObject("Sketcher::SketchObject", name)
    sk.MapMode = "Deactivated"
    _place(sk, x, y, z, rot)
    return sk


def _dist(sk, kind, geo, pos, e):
    if kind == "X":
        i = sk.addConstraint(Sketcher.Constraint("DistanceX", -1, 1, geo, pos, pv(e)))
    else:
        i = sk.addConstraint(Sketcher.Constraint("DistanceY", -1, 1, geo, pos, pv(e)))
    sk.setExpression(f"Constraints[{i}]", fc(e))


def sk_rrect(sk, w, h, r):
    """Fully constrained rounded rectangle centred on the sketch origin."""
    a, b, rr = pv(w) / 2, pv(h) / 2, pv(r)
    P = lambda u, v: Vec(u, v, 0)  # noqa: E731
    g = [
        Part.ArcOfCircle(Part.Circle(P(a - rr, b - rr), Vec(0, 0, 1), rr), 0, math.pi / 2),            # 0 TR
        Part.LineSegment(P(a - rr, b), P(-a + rr, b)),                                                  # 1 top
        Part.ArcOfCircle(Part.Circle(P(-a + rr, b - rr), Vec(0, 0, 1), rr), math.pi / 2, math.pi),      # 2 TL
        Part.LineSegment(P(-a, b - rr), P(-a, -b + rr)),                                                # 3 left
        Part.ArcOfCircle(Part.Circle(P(-a + rr, -b + rr), Vec(0, 0, 1), rr), math.pi, 1.5 * math.pi),   # 4 BL
        Part.LineSegment(P(-a + rr, -b), P(a - rr, -b)),                                                # 5 bottom
        Part.ArcOfCircle(Part.Circle(P(a - rr, -b + rr), Vec(0, 0, 1), rr), 1.5 * math.pi, 2 * math.pi),  # 6 BR
        Part.LineSegment(P(a, -b + rr), P(a, b - rr)),                                                  # 7 right
    ]
    sk.addGeometry(g, False)
    C = Sketcher.Constraint
    cons = [C("Tangent", 0, 2, 1, 1), C("Tangent", 1, 2, 2, 1), C("Tangent", 2, 2, 3, 1), C("Tangent", 3, 2, 4, 1),
            C("Tangent", 4, 2, 5, 1), C("Tangent", 5, 2, 6, 1), C("Tangent", 6, 2, 7, 1), C("Tangent", 7, 2, 0, 1),
            C("Horizontal", 1), C("Horizontal", 5), C("Vertical", 3), C("Vertical", 7),
            C("Equal", 0, 2), C("Equal", 2, 4), C("Equal", 4, 6),
            C("Symmetric", 0, 3, 4, 3, -1, 1)]
    for c in cons:
        sk.addConstraint(c)
    i = sk.addConstraint(C("Radius", 0, rr))
    sk.setExpression(f"Constraints[{i}]", fc(r))
    i = sk.addConstraint(C("DistanceX", 3, 1, 7, 1, 2 * a))
    sk.setExpression(f"Constraints[{i}]", fc(w))
    i = sk.addConstraint(C("DistanceY", 5, 1, 1, 1, 2 * b))
    sk.setExpression(f"Constraints[{i}]", fc(h))


def sk_poly(sk, pts):
    """Closed polyline; every vertex dimensioned from the sketch origin by expressions."""
    n = len(pts)
    vals = [(pv(u), pv(v)) for u, v in pts]
    for k in range(n):
        (u0, v0), (u1, v1) = vals[k], vals[(k + 1) % n]
        sk.addGeometry(Part.LineSegment(Vec(u0, v0, 0), Vec(u1, v1, 0)), False)
    for k in range(n):
        sk.addConstraint(Sketcher.Constraint("Coincident", k, 2, (k + 1) % n, 1))
    for k, (u, v) in enumerate(pts):
        if str(u).strip() == "0":
            sk.addConstraint(Sketcher.Constraint("PointOnObject", k, 1, -2))
        else:
            _dist(sk, "X", k, 1, u)
        if str(v).strip() == "0":
            sk.addConstraint(Sketcher.Constraint("PointOnObject", k, 1, -1))
        else:
            _dist(sk, "Y", k, 1, v)


def sk_circle(sk, cu, cv, r):
    g = sk.addGeometry(Part.Circle(Vec(pv(cu), pv(cv), 0), Vec(0, 0, 1), pv(r)), False)
    _dist(sk, "X", g, 3, cu)
    _dist(sk, "Y", g, 3, cv)
    i = sk.addConstraint(Sketcher.Constraint("Radius", g, pv(r)))
    sk.setExpression(f"Constraints[{i}]", fc(r))


def pad(body, name, sk, length):
    f = body.newObject("PartDesign::Pad", name)
    f.Profile = sk
    bind(f, "Length", length)
    sk.Visibility = False
    return f


def pocket(body, name, sk, length=None, through_mid=False):
    f = body.newObject("PartDesign::Pocket", name)
    f.Profile = sk
    if through_mid:
        f.Type = "ThroughAll"
        f.SideType = "Symmetric"
    else:
        f.Type = "Length"
        bind(f, "Length", length)
    sk.Visibility = False
    return f


def revolve(body, name, sk):
    f = body.newObject("PartDesign::Revolution", name)
    f.Profile = sk
    f.ReferenceAxis = (sk, ["V_Axis"])
    f.Angle = 360.0
    sk.Visibility = False
    return f


def edge_fillet(body, name, feat, select, radius, kind="Fillet"):
    """Fillet/chamfer the edges of `feat` chosen by a geometric predicate at build time."""
    doc.recompute()
    names = [f"Edge{i + 1}" for i, e in enumerate(feat.Shape.Edges) if select(e)]
    if not names:
        print(f"[warn] {name}: no edges selected")
        return None
    f = body.newObject(f"PartDesign::{kind}", name)
    f.Base = (feat, names)
    bind(f, "Radius" if kind == "Fillet" else "Size", radius)
    return f


R_XZ = Rot(Vec(1, 0, 0), 90)          # sketch (u,v) -> global (x, z): revolve about vertical axis
R_YZ = Rot(Vec(1, 1, 1), 120)         # sketch (u,v) -> global (y, z): profile extruded along X
R_FLIP = Rot(Vec(1, 0, 0), 180)       # sketch normal -Z


# ------------------------------------------------------------------------------------
# Assembly containers
# ------------------------------------------------------------------------------------
def container(name, parent=None):
    p = doc.addObject("App::Part", name)
    if parent:
        parent.addObject(p)
    return p


ASM = container("ShockGuard_Assembly")
G_PLUNGER = container("Plunger_Assembly", ASM)
G_OPTICAL = container("Optical_Assembly", ASM)
G_PPG = container("PPG_Assembly", ASM)
G_DISPLAY = container("Display_Assembly", ASM)
G_ELEC = container("Electronics_Assembly", ASM)
G_UI = container("User_Controls", ASM)
G_FAST = container("Fasteners", ASM)

BOM = {}


def new_body(name, group, material, status, desc, printable=False, qty=1):
    b = doc.addObject("PartDesign::Body", name)
    group.addObject(b)
    for prop, val in (("Material", material), ("Status", status), ("Description", desc)):
        b.addProperty("App::PropertyString", prop, "ShockGuard")
        setattr(b, prop, val)
    b.addProperty("App::PropertyBool", "Printable", "ShockGuard")
    b.Printable = printable
    BOM[name] = dict(material=material, status=status, desc=desc, printable=printable, qty=qty,
                     group=group.Name)
    return b


def motion(obj, dx="0", dy="0", dz="0", ex=(0, 0, 0)):
    """Placement = motion offset + explode * vector."""
    ex = [str(v) for v in ex]
    bind(obj, ".Placement.Base.x", f"{dx} + $explode * {ex[0]}")
    bind(obj, ".Placement.Base.y", f"{dy} + $explode * {ex[1]}")
    bind(obj, ".Placement.Base.z", f"{dz} + $explode * {ex[2]}")


t = "$enclosure_wall_thickness"
L, W, H = "$overall_length", "$overall_width", "$overall_height"

# ====================================================================================
# A. UPPER ENCLOSURE  (roof, display window, UI button, finger tunnel + reaction ceiling)
# ====================================================================================
up = new_body("Upper_Enclosure", ASM, "PETG / ASA (FDM) - prototype only", "ASSUMED",
              "Upper shell: OLED window, UI button, finger tunnel, fingertip stop, reaction ceiling",
              printable=True)
sk = sketch(up, "Sk_Upper_Outline", f"{L} / 2", "0", "$z_split")
sk_rrect(sk, L, W, "$corner_radius")
up_pad = pad(up, "Pad_Upper_Shell", sk, f"{H} - $z_split")
edge_fillet(up, "Fillet_Upper_Top", up_pad,
            lambda e: e.BoundBox.ZMin > pv(H) - 1e-4, "$top_edge_fillet")
sk = sketch(up, "Sk_Upper_Cavity", f"({t} + $x_tip - 3) / 2", "0", "$z_split - 1", R_FLIP)
sk_rrect(sk, f"$x_tip - 3 - {t}", f"{W} - 2 * {t}", f"$corner_radius - {t}")
pocket(up, "Pocket_Upper_Cavity", sk, f"{H} - {t} - $z_split + 1")
# finger tunnel: flat-sided lower part + semicircular arch + rounded fingertip stop
fw2 = "$finger_opening_width / 2"
box(up, "Cut_Tunnel_Lower", f"$x_tip + {fw2}", f"{L} + 1", f"-{fw2}", fw2,
    "$z_split - 1", "$z_tunnel_axis", sub=True)
cyl(up, "Cut_Tunnel_Arch", "x", f"$x_tip + {fw2}", "0", "$z_tunnel_axis", fw2,
    f"{L} - $x_tip - {fw2} + 1", sub=True)
cyl(up, "Cut_Tip_Stop_Lower", "z", f"$x_tip + {fw2}", "0", "$z_split - 1", fw2,
    "$z_tunnel_axis - $z_split + 1", sub=True)
sphere(up, "Cut_Tip_Stop_Dome", f"$x_tip + {fw2}", "0", "$z_tunnel_axis", fw2, sub=True)
cone(up, "Cut_Tunnel_Entry_Flare", "x", f"{L} - 3", "0", "$z_tunnel_axis", fw2, f"{fw2} + 2.5", "3.01",
     sub=True)
# tongue that closes the open-top USB-C slot of the lower shell above the receptacle
box(up, "Tongue_USB_C", "0", t, "-($usbc_w / 2 + 0.35)", "$usbc_w / 2 + 0.35",
    "$z_usb_mid + $usbc_h / 2 + 0.6", "$z_split + 0.01")
# shell-joining screw bosses (rear cavity) and pilot holes (all six)
SHELL_SCREWS = [("7", "15.5"), ("7", "-15.5"), ("58", "15.5"), ("58", "-15.5"),
                (f"{L} - 6", "16.5"), (f"{L} - 6", "-16.5")]
for k, (sx, sy) in enumerate(SHELL_SCREWS[:4]):
    cyl(up, f"Boss_Shell_{k + 1}", "z", sx, sy, "$z_split", "3", f"{H} - {t} - $z_split + 0.01")
for k, (sx, sy) in enumerate(SHELL_SCREWS):
    cyl(up, f"Pilot_Shell_{k + 1}", "z", sx, sy, "$z_split - 0.5", "$pilot_r", "8.5", sub=True)
# display window: lens recess + viewing opening + OLED bosses
ox = "$oled_position_x"
cbox(up, "Cut_Lens_Recess", ox, "0", f"{H} - $oled_lens_t", "$oled_glass_w + 2.1", "$oled_glass_h - 1.9",
     f"{H} + 1", sub=True)
cbox(up, "Cut_Display_Window", ox, "0", f"{H} - {t} - 1", "$oled_window_width", "$oled_window_height",
     f"{H} + 1", sub=True)
OLED_HOLES = [("11.65", "11.9"), ("-11.65", "11.9"), ("11.65", "-11.9"), ("-11.65", "-11.9")]
for k, (hx, hy) in enumerate(OLED_HOLES):
    cyl(up, f"Boss_OLED_{k + 1}", "z", f"{ox} + {hx}", hy, "$z_oled_pcb_top", "2",
        f"{H} - {t} - $z_oled_pcb_top + 0.01")
    cyl(up, f"Pilot_OLED_{k + 1}", "z", f"{ox} + {hx}", hy, "$z_oled_pcb_top - 0.5", "$pilot_r", "2.4",
        sub=True)
# UI push-button hole + switch-PCB bosses
bx = "$button_position_x"
cyl(up, "Cut_Button_Hole", "z", bx, "0", f"{H} - {t} - 1", "$button_cap_d / 2 + 0.3", f"{t} + 2", sub=True)
for k, dx in enumerate(("-9", "9")):
    cyl(up, f"Boss_BtnPCB_{k + 1}", "z", f"{bx} + {dx}", "0", "$z_switch_bot", "2",
        f"{H} - {t} - $z_switch_bot + 0.01")
    cyl(up, f"Pilot_BtnPCB_{k + 1}", "z", f"{bx} + {dx}", "0", "$z_switch_bot - 0.5", "$pilot_r", "4",
        sub=True)
motion(up, ex=(0, 0, 70))

# ====================================================================================
# B. LOWER ENCLOSURE (chassis: mechanism bay, electronics bay, battery bay)
# ====================================================================================
lo = new_body("Lower_Enclosure", ASM, "PETG / ASA (FDM) - prototype only", "ASSUMED",
              "Lower shell / chassis: mechanism, electronics and battery bays; slots for knob and release",
              printable=True)
sk = sketch(lo, "Sk_Lower_Outline", f"{L} / 2", "0", "0")
sk_rrect(sk, L, W, "$corner_radius")
lo_pad = pad(lo, "Pad_Lower_Shell", sk, "$z_split")
edge_fillet(lo, "Fillet_Lower_Bottom", lo_pad, lambda e: e.BoundBox.ZMax < 1e-4, "$bottom_edge_fillet")
sk = sketch(lo, "Sk_Lower_Cavity", f"{L} / 2", "0", "$z_split + 1")
sk_rrect(sk, f"{L} - 2 * {t}", f"{W} - 2 * {t}", f"$corner_radius - {t}")
pocket(lo, "Pocket_Lower_Cavity", sk, f"$z_split + 1 - {t}")
# bosses
for k, (sx, sy) in enumerate(SHELL_SCREWS):
    cyl(lo, f"Boss_Shell_{k + 1}", "z", sx, sy, "0.5", "3", "$z_split - 0.5")
TRAY_BOSSES = [("5", "9"), ("5", "-9"), ("61.5", "9"), ("61.5", "-9")]
for k, (sx, sy) in enumerate(TRAY_BOSSES):
    cyl(lo, f"Boss_Tray_{k + 1}", "z", sx, sy, "0.5", "2.5", "$tray_z - 0.5")
PLATE_SCREWS = [("72.5", "12"), (f"{L} - 6", "10"), (f"{L} - 6", "-10")]
for k, (sx, sy) in enumerate(PLATE_SCREWS):
    cyl(lo, f"Boss_Plate_{k + 1}", "z", sx, sy, "0.5", "2.5", "$z_stop_top - 0.5")
BATT_SCREWS = [("$battery_x_center - 22", "0"), ("$battery_x_center + 22", "0")]
for k, (sx, sy) in enumerate(BATT_SCREWS):
    cyl(lo, f"Boss_BattCover_{k + 1}", "z", sx, sy, "0.5", "2.5", "5.5")
# battery locating ribs, latch-spring post, cable-channel ribs
for k, (ya, yb) in enumerate((("$battery_width / 2 + 0.4", "$battery_width / 2 + 1.6"),
                              ("-($battery_width / 2 + 1.6)", "-($battery_width / 2 + 0.4)"))):
    box(lo, f"Rib_Battery_{k + 1}", "$battery_x_center - 16", "$battery_x_center + 16", ya, yb, "1",
        "$battery_thickness + 2")
box(lo, "Post_Latch_Spring", "$latch_spring_x - 1.5", "$latch_spring_x + 1.5", "$latch_post_y",
    "$latch_post_y + 3", "1", "$z_lever_top")
for k, y in enumerate(("0.5", "8")):
    box(lo, f"Rib_Cable_{k + 1}", "64.6", "69.6", y, f"{y} + 1", "1", "6")
# holes: shell screws (clearance + counterbore from below)
for k, (sx, sy) in enumerate(SHELL_SCREWS):
    cyl(lo, f"Hole_Shell_{k + 1}", "z", sx, sy, "-1", "$hole_r", "$z_split + 2", sub=True)
    cyl(lo, f"CBore_Shell_{k + 1}", "z", sx, sy, "-1", "2.1", "3.2", sub=True)
for k, (sx, sy) in enumerate(TRAY_BOSSES):
    cyl(lo, f"Pilot_Tray_{k + 1}", "z", sx, sy, "$tray_z - 6", "$pilot_r", "6.1", sub=True)
for k, (sx, sy) in enumerate(PLATE_SCREWS):
    cyl(lo, f"Pilot_Plate_{k + 1}", "z", sx, sy, "$z_stop_top - 8", "$pilot_r", "8.1", sub=True)
for k, (sx, sy) in enumerate(BATT_SCREWS):
    cyl(lo, f"Pilot_BattCover_{k + 1}", "z", sx, sy, "1", "$pilot_r", "5.1", sub=True)
# battery bay: recess for flush cover + through opening
cbox(lo, "Cut_Battery_Recess", "$battery_x_center", "0", "-1", "48", "$battery_width + 2.8", "1.2", sub=True)
cbox(lo, "Cut_Battery_Opening", "$battery_x_center", "0", "-1", "$battery_length + 0.8",
     "$battery_width + 0.8", f"{t} + 0.5", sub=True)
# optical mount + sensor mount countersunk screw holes from below
OPT_SCREWS = [("$x_m + 10", "10"), ("$x_m - 10", "10"), ("$x_m + 10", "-10"), ("$x_m - 10", "-10")]
SENS_SCREWS = [("$x_ppg - 5", "0"), ("$x_ppg + 5", "0")]
for k, (sx, sy) in enumerate(OPT_SCREWS + SENS_SCREWS):
    cyl(lo, f"Hole_Mount_{k + 1}", "z", sx, sy, "-1", "$hole_r", f"{t} + 2", sub=True)
    cone(lo, f"CSink_Mount_{k + 1}", "z", sx, sy, "-0.01", "1.95", "$hole_r", "0.9", sub=True)
# wall openings: USB-C (rear), cocking-knob slot (+Y), release-button hole (-Y)
box(lo, "Cut_USB_C_Slot", "-1", f"{t} + 1", "-($usbc_w / 2 + 0.5)", "$usbc_w / 2 + 0.5",
    "$z_usb_mid - $usbc_h / 2 - 0.6", "$z_split + 1", sub=True)
# trough continues through the front wall so the finger never rides over a ridge
cyl(lo, "Cut_Trough_FrontWall", "x", "$plate_x1 - 0.5", "0", "$z_fs + $trough_radius", "$trough_radius",
    f"{L} - $plate_x1 + 1.5", sub=True)
pin_lo = "$z_pin - $cocking_pin_diameter / 2 - $moving_part_clearance"
pin_hi = "$z_pin + $plunger_travel + $cocking_pin_diameter / 2 + $moving_part_clearance"
box(lo, "Cut_Cocking_Slot", "$x_m - $cocking_pin_diameter / 2 - 0.5", "$x_m + $cocking_pin_diameter / 2 + 0.5",
    f"{W} / 2 - {t} - 1", f"{W} / 2 + 1", pin_lo, pin_hi, sub=True)
cyl(lo, "Cut_Release_Button", "y", "$release_button_x", f"-{W} / 2 - 1", "$z_lever_mid", "3", f"{t} + 2",
    sub=True)
lo.addProperty("App::PropertyString", "Role", "ShockGuard")
lo.Role = "Assembly reference (grounded)"

# ====================================================================================
# C. FINGER SUPPORT (centring trough, plunger opening, PPG window)
# ====================================================================================
fs = new_body("Finger_Support", ASM, "PETG (FDM) prototype; skin-contact material TBD (biocompatibility)",
              "VERIFY", "Finger-support plate: trough, plunger aperture, MAX30102 window; clamps the plunger stack",
              printable=True)
box(fs, "Plate", "$plate_x0", "$plate_x1", "-$plate_half_width", "$plate_half_width", "$z_stop_top", "$z_split")
cyl(fs, "Cut_Trough", "x", "$x_tip", "0", "$z_fs + $trough_radius", "$trough_radius",
    "$plate_x1 - $x_tip + 1", sub=True)
cyl(fs, "Cut_Plunger_Aperture", "z", "$x_m", "0", "$z_stop_top - 1", "$plunger_diameter / 2 + $plunger_hole_clearance",
    "$support_plate_thickness + 2", sub=True)
cbox(fs, "Cut_PPG_Window", "$x_ppg", "0", "$z_stop_top - 1", "$max_sensor_l + 2", "$max_sensor_w + 2",
     "$z_split + 1", sub=True)
for k, (sx, sy) in enumerate(PLATE_SCREWS):
    cyl(fs, f"Hole_Plate_{k + 1}", "z", sx, sy, "$z_stop_top - 1", "$hole_r", "$support_plate_thickness + 2",
        sub=True)
    cone(fs, f"CSink_Plate_{k + 1}", "z", sx, sy, "$z_split - 0.9", "$hole_r", "1.95", "0.91", sub=True)
motion(fs, ex=(0, 0, 55))

# ====================================================================================
# D/E. PLUNGER ASSEMBLY
# ====================================================================================
pb = new_body("Plunger_Body", G_PLUNGER, "Acetal (POM) or SLA resin; machined for repeatability", "VERIFY",
              "Hollow plunger: optical bore, spring flange with latch lead-in chamfer, window counterbore",
              printable=True)
sk = sketch(pb, "Sk_Plunger_Profile", "$x_m", "0", "0", R_XZ)
pr, fr, br = "$plunger_diameter / 2", "$flange_diameter / 2", "$plunger_bore / 2"
cb = "$contact_pad_diameter / 2 + 0.1"
sk_poly(sk, [(br, "$z_flange_bot"), (fr, "$z_flange_bot"), (fr, "$z_flange_top - $flange_chamfer"),
             (f"{fr} - $flange_chamfer", "$z_flange_top"), (pr, "$z_flange_top"), (pr, "$z_win_top"),
             (cb, "$z_win_top"), (cb, "$z_win_top - $contact_pad_thickness"),
             (br, "$z_win_top - $contact_pad_thickness")])
revolve(pb, "Rev_Plunger", sk)
cyl(pb, "Cut_Pin_Bore", "y", "$x_m", f"{pr} - 1.2", "$z_pin", "$cocking_pin_diameter / 2", f"{fr} - {pr} + 1.5",
    sub=True)
motion(pb, dz="$stroke", ex=(0, 0, 40))

cp = new_body("Contact_Pad", G_PLUNGER, "Optically clear PC / PMMA / glass (TBD; skin-contact + optical test)",
              "VERIFY", "Transparent contact window: blanches the pulp while the camera views through it")
sk = sketch(cp, "Sk_Pad_Profile", "$x_m", "0", "0", R_XZ)
pr_ = "$contact_pad_diameter / 2"
sk_poly(sk, [("0", "$z_win_top - $contact_pad_thickness"), (pr_, "$z_win_top - $contact_pad_thickness"),
             (pr_, "$z_win_top - 0.4"), (f"{pr_} - 0.4", "$z_win_top"), ("0.001", "$z_win_top")])
revolve(cp, "Rev_Pad", sk)
motion(cp, dz="$stroke", ex=(0, 0, 46))

sp = new_body("Compression_Spring", G_PLUNGER, "Music wire / 302 SS (stock spring TBD)", "PLACEHOLDER",
              "Compression spring; length follows mechanism state; rate NOT assigned")
sk = sketch(sp, "Sk_Spring_Wire", "$x_m", "0", "0", R_XZ)
sk_circle(sk, "$spring_outer_diameter / 2 - $spring_wire_diameter / 2",
          "$z_seat_top + $spring_wire_diameter / 2", "$spring_wire_diameter / 2")
hx = sp.newObject("PartDesign::AdditiveHelix", "Helix_Spring")
hx.Profile = sk
hx.ReferenceAxis = (sk, ["V_Axis"])
hx.Mode = "height-turns-angle"
bind(hx, "Height", "$spring_len_current - $spring_wire_diameter")
bind(hx, "Turns", "$spring_total_coils")
sk.Visibility = False
motion(sp, ex=(0, 0, 19))

ss_ = new_body("Spring_Seat", G_PLUNGER, "Acetal / printed PETG", "ASSUMED", "Spring seat washer on optical bracket",
               printable=True)
sk = sketch(ss_, "Sk_Seat_Profile", "$x_m", "0", "0", R_XZ)
sk_poly(sk, [("$collar_od / 2 + 0.2", "$z_mount_top"), ("$guide_id / 2 - 0.2", "$z_mount_top"),
             ("$guide_id / 2 - 0.2", "$z_seat_top"), ("$collar_od / 2 + 0.2", "$z_seat_top")])
revolve(ss_, "Rev_Seat", sk)
motion(ss_, ex=(0, 0, 17))

gd = new_body("Guide", G_PLUNGER, "Acetal / PETG (bore reamed or sleeved)", "VERIFY",
              "Plunger guide tube: flange bore, cocking-pin slot, latch window, integral latch pivot lug",
              printable=True)
sk = sketch(gd, "Sk_Guide_Profile", "$x_m", "0", "0", R_XZ)
sk_poly(sk, [("$guide_id / 2", "$z_mount_top"), ("$guide_od / 2", "$z_mount_top"),
             ("$guide_od / 2", "$z_guide_top"), ("$guide_id / 2", "$z_guide_top")])
revolve(gd, "Rev_Guide", sk)
cyl(gd, "Lug_Latch_Pivot", "z", "$latch_pivot_x", "$latch_pivot_y", "$z_lever_bot - 3.3", "3", "3")
box(gd, "Cut_Pin_Slot", "$x_m - $cocking_pin_diameter / 2 - $moving_part_clearance",
    "$x_m + $cocking_pin_diameter / 2 + $moving_part_clearance", "$guide_id / 2 - 1", "$guide_od / 2 + 1",
    pin_lo, "$z_guide_top + 1", sub=True)
box(gd, "Cut_Latch_Window", "$x_m - 14", "$x_m + 4", "-$guide_od / 2 - 1.2", "-$guide_id / 2 + 2.8",
    "$z_lever_bot - 0.3", "$z_lever_top + 0.4", sub=True)
cyl(gd, "Pilot_Pivot", "z", "$latch_pivot_x", "$latch_pivot_y", "$z_lever_bot - 3.4", "$pilot_r", "3.5", sub=True)
motion(gd, ex=(0, 0, 30))

ts = new_body("Travel_Stop", G_PLUNGER, "Acetal / PETG; shim stack for stroke calibration", "VERIFY",
              "Travel-stop ring: hard upper limit for the flange; retains plunger and spring", printable=True)
sk = sketch(ts, "Sk_Stop_Profile", "$x_m", "0", "0", R_XZ)
sk_poly(sk, [("$stop_bore / 2", "$z_guide_top"), ("$guide_od / 2", "$z_guide_top"),
             ("$guide_od / 2", "$z_stop_top"), ("$stop_bore / 2", "$z_stop_top")])
revolve(ts, "Rev_Stop", sk)
motion(ts, ex=(0, 0, 50))

ck = new_body("Cocking_Feature", G_PLUNGER, "Steel dowel pin pressed into printed knob", "ASSUMED",
              "Radial cocking pin + knob (+Y side). Pull down to cock; pin also keys plunger rotation",
              printable=True)
sk = sketch(ck, "Sk_Knob_Profile", "$x_m", "0", "$z_pin")
kr, yk = "$knob_diameter / 2", f"{W} / 2 + 0.5"
sk_poly(sk, [("0", f"$plunger_diameter / 2 - 1.2"), ("$cocking_pin_diameter / 2", "$plunger_diameter / 2 - 1.2"),
             ("$cocking_pin_diameter / 2", yk), (kr, yk), (kr, f"{yk} + $knob_length - 0.6"),
             (f"{kr} - 0.6", f"{yk} + $knob_length"), ("0", f"{yk} + $knob_length")])
revolve(ck, "Rev_Knob", sk)
motion(ck, dz="$stroke", ex=(0, 14, 40))

lv = new_body("Release_Trigger", G_PLUNGER, "Acetal / PETG (FDM fine layer) - fatigue test", "VERIFY",
              "Pivoting latch lever: tooth holds flange when cocked; release button rotates it clear",
              printable=True)
cyl(lv, "Hub", "z", "$latch_pivot_x", "$latch_pivot_y", "$z_lever_bot", "3", "$latch_thickness")
box(lv, "Arm_Button", "$release_button_x - 3", "$latch_pivot_x", "$latch_pivot_y - 3", "$latch_pivot_y",
    "$z_lever_bot", "$z_lever_top")
box(lv, "Arm_Tooth", "$latch_pivot_x", "$x_m + 1", "$latch_pivot_y - 1.6", "$latch_tooth_y", "$z_lever_bot",
    "$z_lever_top")
cyl(lv, "Cut_Pivot_Hole", "z", "$latch_pivot_x", "$latch_pivot_y", "$z_lever_bot - 1", "$screw_d / 2 + 0.15",
    "$latch_thickness + 2", sub=True)
sk = sketch(lv, "Sk_Tooth_LeadIn", "$latch_pivot_x", "0", "0", R_YZ)
sk_poly(sk, [("$latch_tooth_y + 0.01", "$z_lever_top - 0.9"), ("$latch_tooth_y + 0.01", "$z_lever_top + 0.01"),
             ("$latch_tooth_y - 0.9", "$z_lever_top + 0.01")])
pk = pocket(lv, "Cut_Tooth_LeadIn", sk, through_mid=True)
# rotation about the pivot axis (Z) by latch_angle
lv.Placement = Plc(Vec(), Rot(Vec(0, 0, 1), 0))
bind(lv, ".Placement.Rotation.Angle", "$latch_angle")
motion(lv, dx="$latch_pivot_x - ($latch_pivot_x * cos($latch_angle) - $latch_pivot_y * sin($latch_angle))",
       dy="$latch_pivot_y - ($latch_pivot_x * sin($latch_angle) + $latch_pivot_y * cos($latch_angle))",
       ex=(0, -12, 30))

rb = new_body("Release_Button", G_PLUNGER, "PETG / ASA (FDM)", "ASSUMED",
              "Mechanical release button (-Y side) - separate from the electronic UI button", printable=True)
sk = sketch(rb, "Sk_RelBtn_Profile", "$release_button_x", "0", "$z_lever_mid")
yo = f"-{W} / 2 - 2.5"
sk_poly(sk, [("0", "$latch_pivot_y - 3.2"), ("2.7", "$latch_pivot_y - 3.2"), ("2.7", f"-{W} / 2 + {t} + 1.1"),
             ("4", f"-{W} / 2 + {t} + 1.1"), ("4", f"-{W} / 2 + {t} + 0.1"), ("2.7", f"-{W} / 2 + {t} + 0.1"),
             ("2.7", f"{yo} + 0.5"), ("2.2", yo), ("0", yo)])
revolve(rb, "Rev_RelBtn", sk)
motion(rb, ex=(0, -25, 30))

ls = new_body("Latch_Return_Spring", G_PLUNGER, "Stainless spring wire (stock, TBD)", "PLACEHOLDER",
              "Latch return spring: biases tooth into engagement; length follows lever angle")
sk = sketch(ls, "Sk_LatchSpring_Wire", "$latch_spring_x", "0", "$z_lever_mid")
sk_circle(sk, "0.85", "$latch_post_y - $latch_spring_len + 0.15", "0.15")
hx2 = ls.newObject("PartDesign::AdditiveHelix", "Helix_LatchSpring")
hx2.Profile = sk
hx2.ReferenceAxis = (sk, ["V_Axis"])
hx2.Mode = "height-turns-angle"
bind(hx2, "Height", "$latch_spring_len - 0.3")
hx2.Turns = 5
sk.Visibility = False
motion(ls, ex=(0, -6, 30))

# ====================================================================================
# F. OPTICAL ASSEMBLY
# ====================================================================================
om = new_body("Optical_Mount", G_OPTICAL, "PETG (FDM) / SLA black resin", "ASSUMED",
              "Removable optical bracket: camera pocket, ring-LED collar (centres spring), FPC groove",
              printable=True)
sk = sketch(om, "Sk_OptMount_Outline", "$x_m", "0", t)
sk_rrect(sk, "$optical_mount_size", "$optical_mount_size", "3")
pad(om, "Pad_OptMount", sk, "$optical_mount_thickness")
cyl(om, "Collar", "z", "$x_m", "0", "$z_mount_top - 0.01", "$collar_od / 2", "$cam_holder_h + 0.01")
cyl(om, "Cut_Collar_Bore", "z", "$x_m", "0", "$z_mount_top", "$collar_id / 2", "$cam_holder_h + 1", sub=True)
cbox(om, "Cut_Camera_Pocket", "$x_m", "0", "$z_mount_top - $cam_board_t - 0.1", "$cam_board_size + 0.4",
     "$cam_board_size + 0.4", "$z_mount_top + 0.01", sub=True)
box(om, "Cut_FPC_Groove", "$x_m - $optical_mount_size / 2 - 1", "$x_m", "1", "7", "$z_mount_top - 0.8",
    "$z_mount_top + 0.01", sub=True)
cyl(om, "Cut_LED_Wire_Hole", "x", "$x_m - $collar_od / 2 - 1", "-2", "$z_mount_top + 2.5", "0.8", "3", sub=True)
for k, (sx, sy) in enumerate(OPT_SCREWS):
    cyl(om, f"Pilot_OptMount_{k + 1}", "z", sx, sy, f"{t} - 0.01", "$pilot_r", "$optical_mount_thickness - 0.4",
        sub=True)

cam = new_body("Camera_Module", G_OPTICAL, "OV2640-class camera + macro lens (TBD)", "PLACEHOLDER",
               "Camera envelope (stiffener + lens holder + barrel); replace with selected module drawing")
cbox(cam, "Stiffener", "$x_m", "0", "$z_mount_top - $cam_board_t", "$cam_board_size", "$cam_board_size",
     "$z_mount_top")
cbox(cam, "Lens_Holder", "$x_m", "0", "$z_mount_top", "$cam_holder", "$cam_holder", "$z_mount_top + $cam_holder_h")
cyl(cam, "Lens_Barrel", "z", "$x_m", "0", "$z_mount_top + $cam_holder_h", "$cam_barrel_d / 2", "$cam_barrel_h")
motion(cam, ex=(0, 0, 8))

rl = new_body("Ring_LED", G_OPTICAL, "Ring PCB with white/RGB LEDs (colour-consistent, TBD)", "PLACEHOLDER",
              "Ring-LED illumination around lens; LEDs inside plunger bore")
zr = "$z_mount_top + $cam_holder_h"
cyl(rl, "Ring_PCB", "z", "$x_m", "0", zr, "$ring_light_diameter / 2", "$ring_light_thickness")
cyl(rl, "Cut_Ring_ID", "z", "$x_m", "0", f"{zr} - 1", "$ring_light_inner / 2", "$ring_light_thickness + 2", sub=True)
for k in range(6):
    a = 60 * k + 30
    cyl(rl, f"LED_{k + 1}", "z", f"$x_m + $ring_led_radius * cos({a})", f"$ring_led_radius * sin({a})",
        f"{zr} + $ring_light_thickness - 0.01", "0.8", "0.61")
motion(rl, ex=(0, 0, 13))

# ====================================================================================
# G. PPG ASSEMBLY
# ====================================================================================
mx = new_body("MAX30102_Module", G_PPG, "MAX30102 breakout (TBD)", "PLACEHOLDER",
              "PPG module; sensor face flush with trough through the support-plate window")
zpt = "$z_max_pcb_top"
cbox(mx, "PCB", "$x_ppg", "0", f"{zpt} - $max_pcb_t", "$max_pcb", "$max_pcb", zpt)
cbox(mx, "Sensor", "$x_ppg", "0", f"{zpt} - 0.01", "$max_sensor_l", "$max_sensor_w", f"{zpt} + $max_sensor_h")
cbox(mx, "Bottom_Components", "$x_ppg", "0", f"{zpt} - $max_pcb_t - 1.2", "10", "10", f"{zpt} - $max_pcb_t + 0.01")
motion(mx, ex=(0, 0, 45))

sm = new_body("Sensor_Mount", G_PPG, "PETG (FDM)", "VERIFY", "MAX30102 pedestal; position set by ppg_mount_position",
              printable=True)
cbox(sm, "Pedestal", "$x_ppg", "0", t, "$max_pcb + 1", "14.4", f"{zpt} - $max_pcb_t")
cbox(sm, "Cut_Component_Recess", "$x_ppg", "0", f"{zpt} - $max_pcb_t - 1.5", "10.6", "10.6", f"{zpt}", sub=True)
box(sm, "Cut_Wire_Slot", "$x_ppg - 3", "$x_ppg + 3", "-8", "-4", f"{zpt} - $max_pcb_t - 4",
    f"{zpt} - $max_pcb_t - 1.4", sub=True)
for k, (sx, sy) in enumerate(SENS_SCREWS):
    cyl(sm, f"Pilot_SensMount_{k + 1}", "z", sx, sy, f"{t} - 0.01", "$pilot_r", "4", sub=True)
motion(sm, ex=(0, 0, 20))

# ====================================================================================
# H. DISPLAY ASSEMBLY
# ====================================================================================
ol = new_body("OLED_Module", G_DISPLAY, "0.96in 128x64 I2C OLED (SSD1306-class, TBD)", "PLACEHOLDER",
              "OLED module envelope: PCB, glass, header")
zo = "$z_oled_pcb_top"
cbox(ol, "PCB", ox, "0", f"{zo} - $oled_pcb_t", "$oled_pcb_w", "$oled_pcb_h", zo)
cbox(ol, "Glass", ox, "0", f"{zo} - 0.01", "$oled_glass_w", "$oled_glass_h", f"{zo} + $oled_glass_t")
box(ol, "Header", f"{ox} - 5.08", f"{ox} + 5.08", "11.5", "13.5", f"{zo} - $oled_pcb_t - 6",
    f"{zo} - $oled_pcb_t + 0.01")
for k, (hx_, hy_) in enumerate(OLED_HOLES):
    cyl(ol, f"Hole_{k + 1}", "z", f"{ox} + {hx_}", hy_, f"{zo} - 2", "1.1", "3", sub=True)
motion(ol, ex=(0, 0, 50))

dw = new_body("Display_Window", G_DISPLAY, "Clear PMMA / PC 1 mm (laser cut)", "ASSUMED",
              "Replaceable clear display lens bonded into roof recess")
cbox(dw, "Lens", ox, "0", f"{H} - $oled_lens_t", "$oled_glass_w + 1.7", "$oled_glass_h - 2.3", H)
motion(dw, ex=(0, 0, 85))

# ====================================================================================
# J/K. ELECTRONICS ASSEMBLY
# ====================================================================================
tr = new_body("Electronics_Tray", G_ELEC, "PETG (FDM)", "ASSUMED",
              "Removable electronics carrier: PCB standoffs, charger rails, cable notches; retains battery",
              printable=True)
sk = sketch(tr, "Sk_Tray_Outline", "33.75", "0", "$tray_z")
sk_rrect(sk, "61.5", "24", "2")
pad(tr, "Pad_Tray", sk, "$tray_thickness")
for k, (ya, yb) in enumerate((("5.75", "7.25"), ("-7.25", "-5.75"))):
    box(tr, f"Rail_Charger_{k + 1}", "4", "30", ya, yb, "$z_tray_top - 0.01", "$z_pcb_bot")
ESP_HOLES = [("$esp_x0 + 2.5", "8.5"), ("$esp_x0 + 2.5", "-8.5"), ("$esp_x0 + 23", "8.5"), ("$esp_x0 + 23", "-8.5")]
for k, (sx, sy) in enumerate(ESP_HOLES):
    cyl(tr, f"Standoff_{k + 1}", "z", sx, sy, "$z_tray_top - 0.01", "2.25", "$standoff_h + 0.01")
for k, (sx, sy) in enumerate(ESP_HOLES):
    cyl(tr, f"Pilot_Standoff_{k + 1}", "z", sx, sy, "$tray_z - 0.5", "$pilot_r", "$tray_thickness + $standoff_h + 1",
        sub=True)
for k, (sx, sy) in enumerate(TRAY_BOSSES):
    cyl(tr, f"Hole_Tray_{k + 1}", "z", sx, sy, "$tray_z - 1", "$hole_r", "$tray_thickness + 2", sub=True)
for k, (x0, y0, y1) in enumerate((("40", "10", "13"), ("40", "-13", "-10"))):
    box(tr, f"Cut_Cable_Notch_{k + 1}", x0, f"{x0} + 8", y0, y1, "$tray_z - 1", "$z_tray_top + 1", sub=True)
motion(tr, ex=(0, 0, 20))

es = new_body("ESP32_S3_Board", G_ELEC, "Custom carrier PCB + ESP32-S3-WROOM-1 (N16R8 suggested, TBD)",
              "PLACEHOLDER", "ESP32-S3 carrier envelope incl. camera FPC connector")
box(es, "PCB", "$esp_x0", "$esp_x0 + $esp_pcb_l", "-$esp_pcb_w / 2", "$esp_pcb_w / 2", "$z_pcb_bot", "$z_pcb_top")
box(es, "WROOM_Module", "$esp_x0 + 2", "$esp_x0 + 2 + $wroom_l", "-$wroom_w / 2", "$wroom_w / 2",
    "$z_pcb_top - 0.01", "$z_pcb_top + $wroom_h")
box(es, "FPC_Connector", "$esp_x0 + $esp_pcb_l - 2.2", "$esp_x0 + $esp_pcb_l - 0.2", "0", "8", "$z_pcb_top - 0.01",
    "$z_pcb_top + 1.2")
for k, (sx, sy) in enumerate(ESP_HOLES):
    cyl(es, f"Hole_{k + 1}", "z", sx, sy, "$z_pcb_bot - 1", "1.1", "$pcb_t + 2", sub=True)
motion(es, ex=(0, 0, 30))

cg = new_body("Charging_Board", G_ELEC, "1S Li-ion charger + protection, USB-C (TBD)", "PLACEHOLDER",
              "Charger board envelope with USB-C receptacle at rear wall")
box(cg, "PCB", "3", "3 + $chg_pcb_l", "-$chg_pcb_w / 2", "$chg_pcb_w / 2", "$z_pcb_bot", "$z_pcb_top")
box(cg, "USB_C", f"{t} - 0.2", f"{t} - 0.2 + $usbc_l", "-$usbc_w / 2", "$usbc_w / 2", "$z_pcb_top - 0.01",
    "$z_pcb_top + $usbc_h")
motion(cg, ex=(0, 0, 30))

bt = new_body("Battery", G_ELEC, "1S Li-ion/LiPo - chemistry, capacity, protection NOT selected", "PLACEHOLDER",
              "Configurable battery envelope with cable-exit tab")
cbox(bt, "Cell", "$battery_x_center", "0", "1.2", "$battery_length", "$battery_width", "1.2 + $battery_thickness")
box(bt, "Cable_Exit", "$battery_x_center + $battery_length / 2 - 5", "$battery_x_center + $battery_length / 2 - 1",
    "3", "8", "1.2 + $battery_thickness - 0.01", "1.2 + $battery_thickness + 1")
motion(bt, ex=(0, 0, -15))

bc = new_body("Battery_Cover", G_ELEC, "PETG (FDM)", "ASSUMED", "Flush battery access cover (2x M2 countersunk)",
              printable=True)
cbox(bc, "Cover", "$battery_x_center", "0", "0", "47.6", "$battery_width + 2.4", "1.2")
for k, (sx, sy) in enumerate(BATT_SCREWS):
    cyl(bc, f"Hole_{k + 1}", "z", sx, sy, "-1", "$hole_r", "3", sub=True)
    cone(bc, f"CSink_{k + 1}", "z", sx, sy, "-0.01", "1.95", "$hole_r", "0.91", sub=True)
motion(bc, ex=(0, 0, -26))

fpc = new_body("Camera_FPC", G_ELEC, "Camera flex (length TBD by module)", "PLACEHOLDER",
               "Camera FPC route: optical-mount groove -> rear bay -> ESP32 connector (clear of moving parts)")
zf = "$z_mount_top - 0.7"
box(fpc, "Seg_Groove", "70", "$x_m - $cam_board_size / 2", "1.5", "6.5", zf, f"{zf} + 0.15")
box(fpc, "Seg_Riser", "70", "70.15", "1.5", "6.5", zf, "$z_pcb_top + 0.2")
box(fpc, "Seg_To_Connector", "$esp_x0 + $esp_pcb_l - 0.2", "70.15", "1.5", "6.5", "$z_pcb_top + 0.05",
    "$z_pcb_top + 0.2")
motion(fpc, ex=(0, 0, 10))

# ====================================================================================
# I. USER CONTROLS
# ====================================================================================
pbn = new_body("Push_Button", G_UI, "PETG / TPU cap", "ASSUMED", "Electronic UI push-button cap (start / menu)",
               printable=True)
sk = sketch(pbn, "Sk_Button_Profile", bx, "0", "0", R_XZ)
br_ = "$button_cap_d / 2"
sk_poly(sk, [("0", "$z_button_cap_bot"), (f"{br_} + 1.5", "$z_button_cap_bot"),
             (f"{br_} + 1.5", "$z_button_cap_bot + 0.99"), (br_, "$z_button_cap_bot + 0.99"),
             (br_, f"{H} + 0.4"), (f"{br_} - 0.4", f"{H} + 0.8"), ("0", f"{H} + 0.8")])
revolve(pbn, "Rev_Button", sk)
motion(pbn, ex=(0, 0, 85))

sw = new_body("Tactile_Switch", G_UI, "6x6 mm tactile switch (TBD)", "PLACEHOLDER", "UI switch envelope")
cbox(sw, "Body", bx, "0", "$z_switch_bot", "6", "6", "$z_switch_bot + 3.5")
cyl(sw, "Actuator", "z", bx, "0", "$z_switch_bot + 3.49", "1.75", "$z_button_cap_bot - $z_switch_bot - 3.49")
motion(sw, ex=(0, 0, 52))

bp = new_body("Button_PCB", G_UI, "FR4 1.2 mm", "PLACEHOLDER", "Small switch PCB on two roof bosses")
cbox(bp, "PCB", bx, "0", "$z_switch_bot - 1.2", "23", "10", "$z_switch_bot")
for k, dx in enumerate(("-9", "9")):
    cyl(bp, f"Hole_{k + 1}", "z", f"{bx} + {dx}", "0", "$z_switch_bot - 2", "1.1", "3", sub=True)
motion(bp, ex=(0, 0, 50))

# ====================================================================================
# Fasteners: one parametric Body per screw type, placed by App::Link with expressions
# ====================================================================================
FAST_LIB = doc.addObject("App::DocumentObjectGroup", "Fastener_Library")


def screw_body(name, desc, kind, length):
    b = doc.addObject("PartDesign::Body", name)
    FAST_LIB.addObject(b)
    b.addProperty("App::PropertyString", "Description", "ShockGuard")
    b.Description = desc
    if kind == "shcs":        # head below z=0, shank +Z
        cyl(b, "Head", "z", "0", "0", "-2", "1.9", "2")
        cyl(b, "Shank", "z", "0", "0", "-0.01", "$screw_d / 2", f"{length} + 0.01")
    elif kind == "csk_up":    # flat head flush at z=0, shank +Z
        cone(b, "Head", "z", "0", "0", "0", "1.9", "$screw_d / 2", "0.9")
        cyl(b, "Shank", "z", "0", "0", "0.89", "$screw_d / 2", f"{length} - 0.89")
    elif kind == "csk_down":  # flat head flush at z=0, shank -Z
        cone(b, "Head", "z", "0", "0", "-0.9", "$screw_d / 2", "1.9", "0.9")
        cyl(b, "Shank", "z", "0", "0", f"-{length}", "$screw_d / 2", f"{length} - 0.89")
    elif kind == "pan_down":  # pan head above z=0, shank -Z
        cyl(b, "Head", "z", "0", "0", "0", "1.9", "1.3")
        cyl(b, "Shank", "z", "0", "0", f"-{length}", "$screw_d / 2", f"{length} + 0.01")
    b.Visibility = False
    return b


S30 = screw_body("Screw_M2x30_SHCS", "ISO 4762 M2x30 socket head (shell joining, from below)", "shcs", "28")
S8 = screw_body("Screw_M2x8_CSK_Top", "ISO 10642 M2x8 countersunk (finger-support plate, from above)", "csk_down", "8")
S4 = screw_body("Screw_M2x4_CSK_Bottom", "ISO 10642 M2x4 countersunk (mounts / battery cover, from below)",
                "csk_up", "4")
S5 = screw_body("Screw_M2x5_Pan", "ISO 7045 M2x5 pan head (tray, PCBs, latch pivot)", "pan_down", "5")

FASTENERS = []


def place_link(src, name, x, y, z, ex, flip=False, host=None):
    lk = doc.addObject("App::Link", name)
    lk.LinkedObject = src
    G_FAST.addObject(lk)
    lk.Placement = Plc(Vec(), Rot(Vec(1, 0, 0), 180) if flip else Rot())
    motion(lk, dx=x, dy=y, dz=z, ex=ex)
    FASTENERS.append((name, src.Name, host))
    return lk


for k, (sx, sy) in enumerate(SHELL_SCREWS):
    place_link(S30, f"Fastener_Shell_{k + 1}", sx, sy, "2.2", (0, 0, -35), host="Lower/Upper_Enclosure")
for k, (sx, sy) in enumerate(PLATE_SCREWS):
    place_link(S8, f"Fastener_Plate_{k + 1}", sx, sy, "$z_split", (0, 0, 64), host="Finger_Support")
for k, (sx, sy) in enumerate(OPT_SCREWS):
    place_link(S4, f"Fastener_OptMount_{k + 1}", sx, sy, "0", (0, 0, -12), host="Optical_Mount")
for k, (sx, sy) in enumerate(SENS_SCREWS):
    place_link(S4, f"Fastener_SensMount_{k + 1}", sx, sy, "0", (0, 0, -12), host="Sensor_Mount")
for k, (sx, sy) in enumerate(BATT_SCREWS):
    place_link(S4, f"Fastener_BattCover_{k + 1}", sx, sy, "0", (0, 0, -34), host="Battery_Cover")
for k, (sx, sy) in enumerate(TRAY_BOSSES):
    place_link(S5, f"Fastener_Tray_{k + 1}", sx, sy, "$z_tray_top", (0, 0, 26), host="Electronics_Tray")
for k, (sx, sy) in enumerate(ESP_HOLES):
    place_link(S5, f"Fastener_ESP_{k + 1}", sx, sy, "$z_pcb_top", (0, 0, 36), host="ESP32_S3_Board")
for k, (hx_, hy_) in enumerate(OLED_HOLES):
    place_link(S5, f"Fastener_OLED_{k + 1}", f"{ox} + {hx_}", hy_, "$z_oled_pcb_top - $oled_pcb_t", (0, 0, 44),
               flip=True, host="OLED_Module")
for k, dx in enumerate(("-9", "9")):
    place_link(S5, f"Fastener_BtnPCB_{k + 1}", f"{bx} + {dx}", "0", "$z_switch_bot - 1.2", (0, 0, 44), flip=True,
               host="Button_PCB")
place_link(S5, "Fastener_Latch_Pivot", "$latch_pivot_x", "$latch_pivot_y", "$z_lever_top", (0, -12, 38),
           host="Release_Trigger (pivot)")

# ====================================================================================
# Reference geometry (not part of the product BOM or exports)
# ====================================================================================
REF = doc.addObject("App::DocumentObjectGroup", "Reference_Geometry")
fr_r = 7.0
fcyl = doc.addObject("Part::Cylinder", "Finger_Ref_Shaft")
fsph = doc.addObject("Part::Sphere", "Finger_Ref_Tip")
fcyl.Radius = fr_r
fsph.Radius = fr_r
fcyl.Placement = Plc(Vec(), Rot(Vec(0, 1, 0), 90))
bind(fcyl, ".Placement.Base.x", f"$x_tip + 1.0 + {fr_r}")
bind(fcyl, ".Placement.Base.z", f"$z_fs + {fr_r}")
bind(fcyl, "Height", f"{L} + 25 - $x_tip")
bind(fsph, ".Placement.Base.x", f"$x_tip + 1.0 + {fr_r}")
bind(fsph, ".Placement.Base.z", f"$z_fs + {fr_r}")
fref = doc.addObject("Part::MultiFuse", "Finger_Reference")
fref.Shapes = [fcyl, fsph]
fref.addProperty("App::PropertyString", "Description", "ShockGuard")
fref.Description = "Reference adult fingertip, D14 mm (ASSUMED, for clearance checks only - not anthropometric data)"
REF.addObject(fref)
for o in (fcyl, fsph):
    o.Visibility = False

# measurement / optical datums
for name, (x, z), note in (("Datum_Measurement_Axis", ("$x_m", "0"), "Plunger / camera optical axis"),
                           ("Datum_PPG_Axis", ("$x_ppg", "0"), "MAX30102 centre normal")):
    dl = doc.addObject("Part::Line", name)
    dl.X1, dl.Y1, dl.Z1, dl.X2, dl.Y2, dl.Z2 = pv(x), 0, 0, pv(x), 0, pv(H) + 5
    bind(dl, "X1", x)
    bind(dl, "X2", x)
    bind(dl, "Z2", f"{H} + 5")
    dl.addProperty("App::PropertyString", "Description", "ShockGuard")
    dl.Description = note
    REF.addObject(dl)

doc.recompute()

# ------------------------------------------------------------------------------------
# Self-check: spreadsheet vs Python mirror, feature errors
# ------------------------------------------------------------------------------------
bad = []
for a in V:
    sv = ss.get(a)
    sv = float(sv.Value) if hasattr(sv, "Value") else float(sv)
    if abs(sv - V[a]) > 1e-6:
        bad.append((a, sv, V[a]))
if bad:
    print("[ERROR] spreadsheet / python mismatch:", bad)

errs = [o.Name for o in doc.Objects if "Invalid" in o.State or "Error" in o.State]
print("Objects in error:", errs if errs else "none")
for o in doc.Objects:
    if o.TypeId == "PartDesign::Body" and o.Shape.isNull():
        print("[ERROR] empty body", o.Name)

# Store BOM / fastener metadata for downstream scripts
import json  # noqa: E402
meta = {"bom": BOM, "fasteners": FASTENERS,
        "screw_lib": {S30.Name: S30.Description, S8.Name: S8.Description, S4.Name: S4.Description,
                      S5.Name: S5.Description}}
with open(os.path.join(ROOT, "CAD", "model_meta.json"), "w") as fh:
    json.dump(meta, fh, indent=1)

doc.saveAs(OUT_FCSTD)
print("Saved", OUT_FCSTD)
