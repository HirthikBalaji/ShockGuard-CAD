# -*- coding: utf-8 -*-
"""
ShockGuard view renderer - runs inside the FreeCAD GUI (needs an OpenGL context):

    /Applications/FreeCAD.app/Contents/MacOS/FreeCAD render_views.py

Opens CAD/ShockGuard_Assembly.FCStd, applies presentation colours (saved back into the
FCStd), renders every engineering view from the actual CAD geometry and writes label
anchor points (projected 3-D points) to Renders/_labels.json for annotate_views.py.
Env SG_VIEWS=name1,name2 renders a subset.
"""
import json
import math
import os
import sys
import traceback

import FreeCAD as App
import FreeCADGui as Gui

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
FCSTD = os.path.join(ROOT, "CAD", "ShockGuard_Assembly.FCStd")
OUT = os.path.join(ROOT, "Renders")
RAW = os.path.join(OUT, "_raw")
os.makedirs(RAW, exist_ok=True)
Vec = App.Vector

COLORS = {
    "Upper_Enclosure": (0.86, 0.87, 0.89), "Lower_Enclosure": (0.36, 0.42, 0.50),
    "Finger_Support": (0.93, 0.93, 0.95), "Battery_Cover": (0.36, 0.42, 0.50),
    "Plunger_Body": (0.95, 0.55, 0.15), "Contact_Pad": (0.55, 0.85, 1.00),
    "Compression_Spring": (0.75, 0.75, 0.78), "Spring_Seat": (0.25, 0.25, 0.28),
    "Guide": (0.20, 0.55, 0.85), "Travel_Stop": (0.85, 0.20, 0.20),
    "Cocking_Feature": (0.95, 0.80, 0.10), "Release_Trigger": (0.60, 0.30, 0.80),
    "Release_Button": (0.85, 0.20, 0.20), "Latch_Return_Spring": (0.75, 0.75, 0.78),
    "Optical_Mount": (0.15, 0.15, 0.17), "Camera_Module": (0.35, 0.35, 0.38),
    "Ring_LED": (0.95, 0.95, 0.70), "MAX30102_Module": (0.55, 0.20, 0.55),
    "Sensor_Mount": (0.30, 0.65, 0.45), "OLED_Module": (0.10, 0.25, 0.55),
    "Display_Window": (0.70, 0.90, 1.00), "Electronics_Tray": (0.95, 0.75, 0.35),
    "ESP32_S3_Board": (0.10, 0.50, 0.25), "Charging_Board": (0.15, 0.35, 0.70),
    "Battery": (0.25, 0.30, 0.75), "Camera_FPC": (0.90, 0.60, 0.10),
    "Push_Button": (0.15, 0.65, 0.35), "Tactile_Switch": (0.20, 0.20, 0.20),
    "Button_PCB": (0.10, 0.50, 0.25), "Finger_Reference": (0.96, 0.76, 0.62),
}
TRANSP = {"Contact_Pad": 50, "Display_Window": 60, "Finger_Reference": 45}
SCREW = (0.65, 0.66, 0.70)

doc = App.openDocument(FCSTD)
Gui.showMainWindow() if not Gui.getMainWindow() else None
Gui.getMainWindow().resize(1600, 1100)
gdoc = Gui.getDocument(doc.Name)
Gui.updateGui()
view = gdoc.ActiveView

BODIES = [o for o in doc.Objects if o.TypeId == "PartDesign::Body" and o.InList and
          any(p.TypeId == "App::Part" for p in o.InList)]
LINKS = [o for o in doc.Objects if o.TypeId == "App::Link"]
FINGER = doc.getObject("Finger_Reference")
PARTS = BODIES + LINKS


def style_all():
    for o in doc.Objects:
        vo = o.ViewObject
        if vo is None:
            continue
        if o in BODIES or o is FINGER:
            vo.ShapeColor = COLORS.get(o.Name, (0.7, 0.7, 0.7))
            vo.Transparency = TRANSP.get(o.Name, 0)
            if hasattr(vo, "LineColor"):
                vo.LineColor = (0.12, 0.12, 0.14)
                vo.LineWidth = 1.0
    for b in doc.Objects:
        if b.TypeId == "PartDesign::Body" and b.Name.startswith("Screw_"):
            b.ViewObject.ShapeColor = SCREW


def cam_rot(eye, up=(0, 0, 1)):
    z = Vec(*eye).normalize()
    u = Vec(*up)
    x = u.cross(z)
    if x.Length < 1e-9:
        x = Vec(1, 0, 0)
    x.normalize()
    y = z.cross(x)
    m = App.Matrix(x.x, y.x, z.x, 0, x.y, y.y, z.y, 0, x.z, y.z, z.z, 0, 0, 0, 0, 1)
    return App.Rotation(m)


def set_param(name, val):
    doc.Params.set(name, str(val))
    doc.recompute()


TEMP = []


def clear_temp():
    for o in TEMP:
        try:
            doc.removeObject(o.Name)
        except Exception:
            pass
    TEMP.clear()


def section_copy(objs, keep_box):
    """Create cut copies (common with keep_box) of objs for section views."""
    out = []
    import Part
    kb = Part.makeBox(*keep_box[1], keep_box[0])
    for o in objs:
        try:
            shp = o.Shape.copy()
            if shp.isNull():
                continue
            c = shp.common(kb)
            if c.isNull() or c.Volume < 1e-6:
                continue
            f = doc.addObject("Part::Feature", "Sec_" + o.Name)
            f.Shape = c
            src = o.LinkedObject.Name if o.TypeId == "App::Link" else o.Name
            f.ViewObject.ShapeColor = COLORS.get(src, SCREW)
            f.ViewObject.Transparency = TRANSP.get(src, 0)
            f.ViewObject.LineColor = (0.1, 0.1, 0.1)
            TEMP.append(f)
            out.append(f)
        except Exception:
            traceback.print_exc()
    return out


def show_only(objs):
    keep = set(id(o) for o in objs)
    for o in doc.Objects:
        vo = o.ViewObject
        if vo is None:
            continue
        if o.TypeId in ("App::Part", "App::DocumentObjectGroup", "Spreadsheet::Sheet"):
            vo.Visibility = True
            continue
        par = o.getParentGeoFeatureGroup() if hasattr(o, "getParentGeoFeatureGroup") else None
        if par is not None and par.TypeId == "PartDesign::Body":
            continue  # body features: leave alone (Tip drives body display)
        vo.Visibility = id(o) in keep
        if o.TypeId == "PartDesign::Body" and id(o) in keep and o.Tip is not None:
            o.Tip.ViewObject.Visibility = True
    Gui.updateGui()


def settle(n=6):
    import time
    for _ in range(n):
        Gui.updateGui()
        time.sleep(0.05)


def snap(name, eye, up=(0, 0, 1), objs=None, fit=None, zoom=1.0, labels=None, size=(2400, 1650), ortho=True):
    show_only(objs)
    settle()
    view.setCameraType("Orthographic" if ortho else "Perspective")
    view.setCameraOrientation(cam_rot(eye, up))
    settle()
    if fit is None:
        view.fitAll()
    else:
        # fit to a bounding box by temporarily showing a helper
        import Part
        bb = fit
        hb = doc.addObject("Part::Feature", "FitHelper")
        hb.Shape = Part.makeBox(bb[3] - bb[0], bb[4] - bb[1], bb[5] - bb[2], Vec(bb[0], bb[1], bb[2]))
        hb.ViewObject.Visibility = True
        others = [o for o in doc.Objects if o.ViewObject and o.ViewObject.Visibility and o is not hb
                  and o.TypeId not in ("App::Part", "App::DocumentObjectGroup")]
        for o in others:
            o.ViewObject.Visibility = False
        Gui.updateGui()
        view.fitAll()
        for o in others:
            o.ViewObject.Visibility = True
        doc.removeObject(hb.Name)
        Gui.updateGui()
    Gui.updateGui()
    vw, vh = view.getSize()
    W, H = size
    # keep the viewport aspect so projected label points map linearly
    H = int(round(W * vh / float(vw)))
    path = os.path.join(RAW, name + ".png")
    import matplotlib.image as mpimg
    for attempt in range(5):
        settle(10)
        view.fitAll() if fit is None and attempt else None
        settle(4)
        view.saveImage(path, W, H, "White")
        if float(mpimg.imread(path)[..., :3].std()) > 0.01:
            break
        LOGF.write("  blank frame, retry %s %d\n" % (name, attempt)); LOGF.flush()
    pts = {}
    for lab, p in (labels or {}).items():
        sx, sy = view.getPointOnScreen(Vec(*p))
        pts[lab] = [sx * W / float(vw), H - sy * H / float(vh), p]
    LABELS[name] = {"size": [W, H], "points": pts}
    LOGF.write("rendered %s\n" % name); LOGF.flush()


LABELS = {}
LOGF = open(os.path.join(OUT, "_render_progress.txt"), "w")
lab_file = os.path.join(OUT, "_labels.json")
if os.path.exists(lab_file):
    LABELS.update(json.load(open(lab_file)))

try:
    style_all()
except Exception:
    traceback.print_exc()
P = doc.Params


def g(n):
    v = P.get(n)
    return float(v.Value) if hasattr(v, "Value") else float(v)


Lx, Wy, Hz = g("overall_length"), g("overall_width"), g("overall_height")
xm, xp, zfs = g("x_m"), g("x_ppg"), g("z_fs")
ISO = (1, -1.25, 0.95)
SHELLS = [doc.getObject(n) for n in ("Upper_Enclosure", "Lower_Enclosure")]
NON_SHELL = [o for o in PARTS if o not in SHELLS]
want = [s for s in os.environ.get("SG_VIEWS", "").split(",") if s]


def run(name):
    return not want or name in want


B = {n: doc.getObject(n) for n in COLORS}


def c(n):
    bb = B[n].Shape.BoundBox
    return [bb.Center.x, bb.Center.y, bb.Center.z]


try:
    set_param("state", 2)
    set_param("explode", 0)
    snap("_warmup", ISO, objs=PARTS)
    snap("_warmup", ISO, objs=PARTS)
    if run("iso"):
        snap("iso", ISO, objs=PARTS, labels={
            "Display window (OLED)": [g("oled_position_x"), 0, Hz],
            "UI push-button": [g("button_position_x"), 0, Hz + 0.8],
            "Finger entry / tunnel": [Lx, 0, g("z_tunnel_axis")],
            "Cocking knob": [xm, Wy / 2 + 6.5, g("z_pin")],
            "USB-C charging port": [0, 0, g("z_usb_mid")],
        })
    if run("iso_rear"):
        snap("iso_rear", (-1, 1.2, 0.8), objs=PARTS, labels={
            "Release button (-Y)": [g("release_button_x"), -Wy / 2 - 2.5, g("z_lever_mid")],
            "USB-C charging port": [0, 0, g("z_usb_mid")],
        })
    if run("iso_bottom"):
        snap("iso_bottom", (1, -1.2, -0.9), objs=PARTS, labels={
            "Battery access cover": [g("battery_x_center"), 0, 0],
            "Shell screws (M2x30, from below)": [7, -15.5, 0],
            "Release button": [g("release_button_x"), -Wy / 2 - 2.5, g("z_lever_mid")],
        })
    if run("iso_finger"):
        snap("iso_finger", ISO, objs=PARTS + [FINGER], labels={})
    for nm, eye, up in (("ortho_front", (1, 0, 0), (0, 0, 1)), ("ortho_side", (0, -1, 0), (0, 0, 1)),
                        ("ortho_top", (0, 0, 1), (0, 1, 0)), ("ortho_bottom", (0, 0, -1), (0, 1, 0)),
                        ("ortho_rear", (-1, 0, 0), (0, 0, 1))):
        if run(nm):
            snap(nm, eye, up, objs=PARTS)
    if run("exploded"):
        set_param("explode", 1)
        names = ["Upper_Enclosure", "Lower_Enclosure", "Finger_Support", "Plunger_Body", "Compression_Spring",
                 "Guide", "Travel_Stop", "Cocking_Feature", "Release_Trigger", "Release_Button", "Optical_Mount",
                 "Camera_Module", "Ring_LED", "MAX30102_Module", "Sensor_Mount", "OLED_Module", "Display_Window",
                 "Electronics_Tray", "ESP32_S3_Board", "Charging_Board", "Battery", "Battery_Cover",
                 "Push_Button", "Contact_Pad", "Spring_Seat"]
        snap("exploded", (1, -1.6, 0.75), objs=PARTS, labels={n.replace("_", " "): c(n) for n in names},
             size=(2400, 1650))
        set_param("explode", 0)
    # ---- longitudinal section (y = 0 plane, keep -Y half) -----------------------------
    if run("section"):
        set_param("state", 3)
        secs = section_copy(PARTS + [FINGER], (Vec(-5, -60, -40), (Lx + 40, 60, 100)))
        snap("section", (0.22, 1, 0.12), objs=secs, labels={
            "Contact window (transparent)": [xm, 0, g("z_win_top") + g("stroke")],
            "Hollow plunger": [xm - g("plunger_diameter") / 2, 0, g("z_flange_top") + g("stroke") + 3],
            "Compression spring": [xm - 9.6, 0, g("z_seat_top") + 3],
            "Camera + macro lens": [xm, 0, g("z_lens_top") - 1],
            "Ring LED": [xm - 6, 0, g("z_mount_top") + g("cam_holder_h") + 0.5],
            "Travel stop": [xm - 11, 0, g("z_guide_top") + 1],
            "MAX30102 (PPG)": [xp, 0, zfs - 0.5],
            "Fingertip stop": [g("x_tip"), 0, g("z_tunnel_axis")],
            "Reaction ceiling": [xm + 8, 0, g("z_ceiling")],
            "Reference finger": [xm + 25, 0, zfs + 7],
            "ESP32-S3": [g("esp_x0") + 14, 0, g("z_pcb_top") + 2],
            "Battery": [g("battery_x_center"), 0, 4],
            "OLED": [g("oled_position_x"), 0, g("z_oled_pcb_top")],
            "UI button": [g("button_position_x"), 0, Hz],
        })
        clear_temp()
        set_param("state", 2)
    # ---- electronics compartment (upper shell removed) -------------------------------
    if run("electronics"):
        objs = [o for o in PARTS if o.Name != "Upper_Enclosure" and not o.Name.startswith("Fastener_Shell")]
        disp = [doc.getObject(n) for n in ("OLED_Module", "Display_Window", "Push_Button", "Tactile_Switch",
                                           "Button_PCB")]
        hide = disp + [doc.getObject(n) for n in ("Finger_Support", "Travel_Stop")]
        objs = [o for o in objs if o not in hide and not o.Name.startswith(("Fastener_OLED", "Fastener_Btn",
                                                                            "Fastener_Plate"))]
        snap("electronics", (0.3, -0.55, 1.6), objs=objs, labels={
            "ESP32-S3 module + carrier": [g("esp_x0") + 14, 0, g("z_pcb_top") + g("wroom_h")],
            "Charging board + USB-C": [15, 0, g("z_pcb_top")],
            "Electronics tray": [63, -11, g("z_tray_top")],
            "Camera FPC route": [70, 4, 12], "Latch lever": [g("latch_pivot_x") - 6, g("latch_pivot_y") - 1.5,
                                                              g("z_lever_top")],
            "Release button": [g("release_button_x"), -Wy / 2 - 2.5, g("z_lever_mid")],
            "Cocking knob": [xm, Wy / 2 + 6.5, g("z_pin")],
            "Plunger + contact window": [xm, 0, g("z_win_top")],
            "MAX30102 on pedestal": [xp, 0, zfs],
            "Shell screw bosses": [7, 15.5, g("z_split")],
        })
    if run("electronics_display"):
        # display + UI side: view the upper shell from below with internals
        objs = [doc.getObject(n) for n in ("Upper_Enclosure", "OLED_Module", "Push_Button", "Tactile_Switch",
                                           "Button_PCB", "Display_Window")]
        objs += [o for o in LINKS if o.Name.startswith(("Fastener_OLED", "Fastener_Btn"))]
        snap("electronics_display", (0.8, -1.0, -1.3), objs=objs, labels={
            "OLED module": c("OLED_Module"), "Switch PCB": c("Button_PCB"),
            "Tunnel / reaction ceiling": [xm + 10, 0, g("z_ceiling")],
        })
    # ---- plunger mechanism close-up (cut along y=0, keep -Y half; shells hidden) ----
    if run("plunger_closeup"):
        mech = [doc.getObject(n) for n in ("Plunger_Body", "Contact_Pad", "Compression_Spring", "Spring_Seat",
                                           "Guide", "Travel_Stop", "Cocking_Feature", "Release_Trigger",
                                           "Release_Button", "Latch_Return_Spring", "Optical_Mount",
                                           "Camera_Module", "Ring_LED")]
        mech += [doc.getObject("Fastener_Latch_Pivot")]
        secs = section_copy(mech, (Vec(xm - 45, -60, -5), (45, 120, 50)))
        bb = (xm - 30, -26, 0, xm, 28, 26)
        snap("plunger_closeup", (1, 0.45, 0.4), objs=secs, fit=bb, zoom=1.0, labels={
            "Plunger (cocked)": [xm, -7.6, g("z_flange_top") + 4.5],
            "Spring": [xm, 9.6, g("z_seat_top") + 4],
            "Guide": [xm, 11.3, g("z_guide_top") - 2],
            "Travel stop": [xm, 10, g("z_stop_top")],
            "Latch tooth": [xm - 3, g("latch_tooth_y"), g("z_lever_top")],
            "Release button": [g("release_button_x"), -Wy / 2 - 2.5, g("z_lever_mid")],
            "Cocking knob": [xm, Wy / 2 + 6.5, g("z_pin")],
            "Contact window": [xm, 0, g("z_win_top")],
            "Camera": [xm, 0, g("z_lens_top")],
        })
        clear_temp()
        # 4-state mechanism strip
        for st in (1, 2, 3, 4):
            set_param("state", st)
            secs = section_copy(mech + [FINGER, doc.getObject("Finger_Support")],
                                (Vec(xm - 45, -60, -5), (45, 120, 50)))
            snap(f"mech_state_{st}", (1, 0.0001, 0.0), objs=secs, fit=(xm - 1, -26, 0, xm, 30, 33),
                 zoom=1.0)
            clear_temp()
        set_param("state", 2)
    # ---- measurement zone close-up --------------------------------------------------
    if run("measurement_zone"):
        set_param("state", 3)
        objs = [o for o in PARTS if o.Name not in ("Upper_Enclosure",)]
        secs = section_copy(objs + [doc.getObject("Upper_Enclosure"), FINGER],
                            (Vec(g("x_tip") - 15, -60, -5), (Lx - g("x_tip") + 30, 60.0, 60)))
        snap("measurement_zone", (0.35, 1, 0.3), objs=secs,
             fit=(g("x_tip") - 8, -22, 0, Lx + 2, 22, Hz), labels={
                 "Contact window on pulp": [xm, 0, g("z_win_top") + g("stroke")],
                 "Camera axis": [xm, 0, g("z_lens_top")],
                 "MAX30102 sensor": [xp, 0, zfs],
                 "Fingertip stop": [g("x_tip"), 0, g("z_tunnel_axis")],
                 "Reaction ceiling": [xm + 6, 0, g("z_ceiling")],
                 "Centring trough": [xp + 8, 0, zfs],
             })
        clear_temp()
        set_param("state", 2)
except Exception:
    LOGF.write(traceback.format_exc()); LOGF.flush()

with open(lab_file, "w") as fh:
    json.dump(LABELS, fh, indent=1)

if os.environ.get("SG_SAVE", "1") == "1":
    set_param("state", 2)
    set_param("explode", 0)
    show_only(PARTS)
    view.setCameraOrientation(cam_rot(ISO))
    view.fitAll()
    doc.save()
    print("saved colours into FCStd")
open(os.path.join(OUT, "_render.done"), "w").write("ok")
os._exit(0)
