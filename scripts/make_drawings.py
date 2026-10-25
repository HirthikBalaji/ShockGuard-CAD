# -*- coding: utf-8 -*-
"""
ShockGuard engineering drawings (headless):

    /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd make_drawings.py

All linework comes from the CAD solids: orthographic views are TechDraw hidden-line
projections (TechDraw.projectEx); sections are planar slices of every solid. Dimensions
are measured from the model (bounding boxes / parameters that drive the geometry).
Output: Drawings/ShockGuard_Engineering_Drawings.pdf (A3, multi-sheet).
"""
import csv
import json
import math
import os
import time

import FreeCAD as App
import Part
import TechDraw
import matplotlib

matplotlib.use("Agg")
import matplotlib.image as mpimg  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402
from matplotlib.patches import PathPatch, Rectangle  # noqa: E402
from matplotlib.path import Path as MPath  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
Vec = App.Vector
doc = App.openDocument(os.path.join(ROOT, "CAD", "ShockGuard_Assembly.FCStd"))
P = doc.Params
REP = json.load(open(os.path.join(ROOT, "Docs", "verification_report.json")))


def g(n):
    v = P.get(n)
    return float(v.Value) if hasattr(v, "Value") else float(v)


def setp(n, v):
    P.set(n, str(v))
    doc.recompute()


setp("state", 2)
setp("explode", 0)
BODIES = [o for o in doc.Objects if o.TypeId == "PartDesign::Body" and any(p.TypeId == "App::Part" for p in o.InList)]
LINKS = [o for o in doc.Objects if o.TypeId == "App::Link"]
PARTS = BODIES + LINKS
B = {o.Name: o for o in PARTS}
FINGER = doc.getObject("Finger_Reference")
INK = "#1d2733"
SHEET_W, SHEET_H = 420.0, 297.0
DATE = time.strftime("%Y-%m-%d")

FILL = {
    "Upper_Enclosure": "#d9dde3", "Lower_Enclosure": "#aab4c0", "Finger_Support": "#eceef2",
    "Battery_Cover": "#aab4c0", "Plunger_Body": "#f0a05a", "Contact_Pad": "#bfe6ff", "Compression_Spring": "#8f949c",
    "Spring_Seat": "#555", "Guide": "#7fb2e0", "Travel_Stop": "#e07070", "Cocking_Feature": "#f2d45c",
    "Release_Trigger": "#b48ad6", "Release_Button": "#e07070", "Latch_Return_Spring": "#8f949c",
    "Optical_Mount": "#4a4a50", "Camera_Module": "#7a7a80", "Ring_LED": "#f3f0b0", "MAX30102_Module": "#a35aa3",
    "Sensor_Mount": "#86c2a0", "OLED_Module": "#4c6fa8", "Display_Window": "#cdeeff", "Electronics_Tray": "#f2c879",
    "ESP32_S3_Board": "#4f9a6a", "Charging_Board": "#5d7fc0", "Battery": "#7a83d6", "Camera_FPC": "#f0b050",
    "Push_Button": "#5fbf85", "Tactile_Switch": "#444", "Button_PCB": "#4f9a6a",
}
HATCH = {"Upper_Enclosure": "///", "Lower_Enclosure": "\\\\\\", "Finger_Support": "///", "Battery_Cover": "\\\\\\",
         "Guide": "//", "Optical_Mount": "\\\\", "Electronics_Tray": "//", "Sensor_Mount": "\\\\",
         "Plunger_Body": "//", "Travel_Stop": "xx"}


# ------------------------------------------------------------------------------------
# geometry helpers
# ------------------------------------------------------------------------------------
def cam_matrix(eye, up):
    z = Vec(*eye).normalize()
    x = Vec(*up).cross(z)
    x.normalize()
    y = z.cross(x)
    return App.Matrix(x.x, x.y, x.z, 0, y.x, y.y, y.z, 0, z.x, z.y, z.z, 0, 0, 0, 0, 1), x, y


def hlr(shapes, eye, up):
    m, _, _ = cam_matrix(eye, up)
    comp = Part.makeCompound([s.copy() for s in shapes])
    comp = comp.transformGeometry(m)
    r = TechDraw.projectEx(comp, Vec(0, 0, 1))
    vis = [r[0], r[1], r[3]]
    hid = [r[5], r[8]]
    return vis, hid


def edges_xy(compounds, defl=0.05):
    out = []
    for c in compounds:
        if c is None or c.isNull():
            continue
        for e in c.Edges:
            try:
                pts = e.discretize(Deflection=defl)
            except Exception:  # noqa: BLE001
                continue
            out.append([(p.x, p.y) for p in pts])
    return out


def section_paths(objs, normal, d, uv):
    """Slice solids by plane (normal, d); return {name: [polylines in (u,v)]}."""
    res = {}
    for o in objs:
        s = o.Shape
        try:
            wires = s.slice(Vec(*normal), d)
        except Exception:  # noqa: BLE001
            continue
        polys = []
        for w in wires:
            pts = w.discretize(Deflection=0.02)
            polys.append([uv(p) for p in pts])
        if polys:
            res[o.Name if o.TypeId != "App::Link" else "Fastener"] = res.get(
                o.Name if o.TypeId != "App::Link" else "Fastener", []) + polys
    return res


# ------------------------------------------------------------------------------------
# sheet furniture
# ------------------------------------------------------------------------------------
def new_sheet(title, sheet_no, n_sheets, scale_txt):
    fig = plt.figure(figsize=(SHEET_W / 25.4, SHEET_H / 25.4))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, SHEET_W)
    ax.set_ylim(0, SHEET_H)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.add_patch(Rectangle((10, 10), SHEET_W - 20, SHEET_H - 20, fill=False, lw=0.8, ec=INK))
    # title block
    x0, y0, w, h = SHEET_W - 190, 10, 180, 34
    ax.add_patch(Rectangle((x0, y0), w, h, fill=False, lw=0.8, ec=INK))
    for yy in (y0 + 11, y0 + 22):
        ax.plot([x0, x0 + w], [yy, yy], lw=0.4, color=INK)
    ax.plot([x0 + 110, x0 + 110], [y0, y0 + 22], lw=0.4, color=INK)
    ax.text(x0 + 3, y0 + 28, "ShockGuard - CRT / PPI fingertip triage device", fontsize=10, weight="bold", color=INK,
            va="center")
    ax.text(x0 + 3, y0 + 16.5, title, fontsize=8.5, color=INK, va="center")
    ax.text(x0 + 3, y0 + 5.5, f"Scale {scale_txt}   Units: mm   Third-angle projection   {DATE}", fontsize=6.5,
            color=INK, va="center")
    ax.text(x0 + 113, y0 + 16.5, f"Sheet {sheet_no} / {n_sheets}   Rev A (concept)", fontsize=6.8, color=INK,
            va="center")
    ax.text(x0 + 113, y0 + 5.5, "Source: ShockGuard_Assembly.FCStd", fontsize=6.2, color=INK, va="center")
    ax.text(SHEET_W / 2 - 95, 16, "PROPOSED ENGINEERING CONCEPT - NOT VALIDATED - NOT FOR CLINICAL USE",
            fontsize=8, color="#b03a2e", weight="bold", ha="center", va="center")
    return fig, ax


def draw_lines(ax, polys, ox, oy, s, lw=0.35, color=INK, ls="-"):
    for pl in polys:
        xs = [ox + p[0] * s for p in pl]
        ys = [oy + p[1] * s for p in pl]
        ax.plot(xs, ys, lw=lw, color=color, ls=ls, solid_capstyle="round")


def draw_view(ax, shapes, eye, up, ox, oy, s, hidden=False, label=None):
    vis, hid = hlr(shapes, eye, up)
    pv, ph = edges_xy(vis), (edges_xy(hid) if hidden else [])
    allp = [p for pl in pv for p in pl]
    minx, miny = min(p[0] for p in allp), min(p[1] for p in allp)
    maxx, maxy = max(p[0] for p in allp), max(p[1] for p in allp)
    # place view so that its min corner sits at (ox, oy)
    dx, dy = ox - minx * s, oy - miny * s
    draw_lines(ax, ph, dx, dy, s, lw=0.2, color="#8a93a0", ls=(0, (2, 1.2)))
    draw_lines(ax, pv, dx, dy, s, lw=0.4)
    if label:
        ax.text(dx + (minx + maxx) / 2 * s, oy - 7, label, ha="center", fontsize=7.5, color=INK, weight="bold")
    return dict(dx=dx, dy=dy, minx=minx, maxx=maxx, miny=miny, maxy=maxy, s=s)


def draw_section(ax, sec, ox, oy, s, show_names=False):
    for name, polys in sec.items():
        verts, codes = [], []
        for pl in polys:
            if len(pl) < 3:
                continue
            verts += [(ox + u * s, oy + v * s) for u, v in pl]
            codes += [MPath.MOVETO] + [MPath.LINETO] * (len(pl) - 2) + [MPath.CLOSEPOLY]
        if not verts:
            continue
        path = MPath(verts, codes)
        ax.add_patch(PathPatch(path, fc=FILL.get(name, "#b8bcc4"), ec=INK, lw=0.35,
                               hatch=HATCH.get(name), alpha=0.95))


def dim(ax, p1, p2, off, text, horizontal=True, fs=6.5, color=INK):
    (x1, y1), (x2, y2) = p1, p2
    if horizontal:
        y = off
        ax.plot([x1, x1], [y1, y], lw=0.25, color=color)
        ax.plot([x2, x2], [y2, y], lw=0.25, color=color)
        ax.annotate("", xy=(x1, y), xytext=(x2, y), arrowprops=dict(arrowstyle="<|-|>", lw=0.4, color=color,
                                                                     mutation_scale=5))
        ax.text((x1 + x2) / 2, y + 1.2, text, ha="center", va="bottom", fontsize=fs, color=color)
    else:
        x = off
        ax.plot([x1, x], [y1, y1], lw=0.25, color=color)
        ax.plot([x2, x], [y2, y2], lw=0.25, color=color)
        ax.annotate("", xy=(x, y1), xytext=(x, y2), arrowprops=dict(arrowstyle="<|-|>", lw=0.4, color=color,
                                                                     mutation_scale=5))
        ax.text(x + 1.2, (y1 + y2) / 2, text, ha="left", va="center", fontsize=fs, color=color, rotation=90)


def spread_row(ax, items, y, xmin, xmax, fs=6.3, below=False):
    """Place labels on one row (y) in the x-order of their anchor points, without overlaps."""
    items = sorted(items, key=lambda it: it[0][0])
    wid = [len(t) * 1.13 * fs / 6.3 + 3 for _, t in items]
    xs = []
    for (p, _), w in zip(items, wid):
        x = max(p[0], xmin + w / 2)
        if xs:
            x = max(x, xs[-1] + wid[len(xs) - 1] / 2 + w / 2 + 1.5)
        xs.append(x)
    over = xs[-1] + wid[-1] / 2 - xmax if xs else 0
    if over > 0:
        for i in range(len(xs) - 1, -1, -1):
            xs[i] -= over
            if i and xs[i] - wid[i] / 2 - 1.5 >= xs[i - 1] + wid[i - 1] / 2:
                break
            if i:
                over = xs[i - 1] + wid[i - 1] / 2 + wid[i] / 2 + 1.5 - xs[i]
                over = max(over, 0)
    for (p, t), x in zip(items, xs):
        ax.annotate(t, xy=p, xytext=(x, y), fontsize=fs, color=INK, ha="center", va="top" if below else "bottom",
                    arrowprops=dict(arrowstyle="-", lw=0.3, color="#b03a2e"),
                    bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="#c9ced6", lw=0.4))
        ax.plot([p[0]], [p[1]], "o", ms=1.6, color="#b03a2e")


def leader(ax, p, t, text, fs=6.3, ha=None):
    ax.annotate(text, xy=p, xytext=t, fontsize=fs, color=INK, ha=ha or ("left" if t[0] >= p[0] else "right"),
                va="center",
                arrowprops=dict(arrowstyle="-", lw=0.3, color="#b03a2e"),
                bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="#c9ced6", lw=0.4))
    ax.plot([p[0]], [p[1]], "o", ms=1.6, color="#b03a2e")


def notes(ax, x, y, lines, fs=6.3, title="NOTES"):
    ax.text(x, y, title, fontsize=fs + 1, weight="bold", color=INK, va="top")
    for i, ln in enumerate(lines):
        ax.text(x, y - 4.2 * (i + 1), ln, fontsize=fs, color=INK, va="top")


def fmt(v):
    return f"{v:.1f}".rstrip("0").rstrip(".") if abs(v - round(v)) > 1e-6 else f"{int(round(v))}"


# envelope measured from the model
shell = B["Lower_Enclosure"].Shape.fuse(B["Upper_Enclosure"].Shape)
ebb = shell.optimalBoundingBox()
abb = Part.makeCompound([o.Shape for o in PARTS]).optimalBoundingBox()
L_, W_, H_ = ebb.XLength, ebb.YLength, ebb.ZLength
pdf_path = os.path.join(ROOT, "Drawings", "ShockGuard_Engineering_Drawings.pdf")
NS = 7
shapes_all = [o.Shape for o in PARTS]

os.makedirs(os.path.join(ROOT, "Drawings", "sheet_previews"), exist_ok=True)


class _Pdf:
    """PdfPages wrapper that also writes a PNG preview of each sheet."""

    def __init__(self, pp):
        self.pp, self.n = pp, 0

    def savefig(self, fig):
        self.n += 1
        self.pp.savefig(fig)
        fig.savefig(os.path.join(ROOT, "Drawings", "sheet_previews", f"Sheet_{self.n}.png"), dpi=110)


with PdfPages(pdf_path) as _pp:
    pdf = _Pdf(_pp)
    # ================================================================================
    # Sheet 1 - assembly drawing: four orthographic views + overall dims + notes
    # ================================================================================
    fig, ax = new_sheet("Assembly drawing - orthographic views, overall dimensions", 1, NS, "1:1")
    s = 1.0
    elev = draw_view(ax, shapes_all, (0, -1, 0), (0, 0, 1), 35, 150, s, hidden=False, label="SIDE ELEVATION (from -Y)")
    top = draw_view(ax, shapes_all, (0, 0, 1), (0, 1, 0), 35, 215, s, label="PLAN (from +Z)")
    bot = draw_view(ax, shapes_all, (0, 0, -1), (0, -1, 0), 35, 58, s, label="UNDERSIDE (from -Z)")
    right = draw_view(ax, shapes_all, (1, 0, 0), (0, 0, 1), 185, 150, s, label="END VIEW - finger entry (+X)")
    rear = draw_view(ax, shapes_all, (-1, 0, 0), (0, 0, 1), 250, 150, s, label="END VIEW - rear, USB-C (-X)")
    # overall dimensions (housing envelope measured from the CAD shells)
    ex0 = elev["dx"] + ebb.XMin * s
    ex1 = elev["dx"] + ebb.XMax * s
    ez0 = elev["dy"] + ebb.ZMin * s
    ez1 = elev["dy"] + ebb.ZMax * s
    dim(ax, (ex0, ez0), (ex1, ez0), ez0 - 15, f"{fmt(L_)} (housing)")
    dim(ax, (ex0, ez0), (ex0, ez1), ex0 - 8, f"{fmt(H_)}", horizontal=False)
    ty0 = top["dy"] + ebb.YMin * s
    ty1 = top["dy"] + ebb.YMax * s
    dim(ax, (top["dx"] + ebb.XMax * s, ty0), (top["dx"] + ebb.XMax * s, ty1), top["dx"] + ebb.XMax * s + 6,
        f"{fmt(W_)}", horizontal=False)
    tyk0, tyk1 = top["dy"] + abb.YMin * s, top["dy"] + abb.YMax * s
    dim(ax, (top["dx"] + g("x_m") * s, tyk0), (top["dx"] + g("x_m") * s, tyk1), top["dx"] + ebb.XMax * s + 14,
        f"{fmt(abb.YLength)} over knob/button", horizontal=False)
    # interface positions in plan
    xt = top["dx"] + g("x_tip") * s
    xm_ = top["dx"] + g("x_m") * s
    xp_ = top["dx"] + g("x_ppg") * s
    ytop = top["dy"] + top["maxy"] * s + 4
    dim(ax, (top["dx"] + ebb.XMin * s, ytop), (xt, ytop), ytop + 4, f"{fmt(g('x_tip'))} to fingertip stop")
    dim(ax, (xt, ytop), (xm_, ytop), ytop + 11, f"{fmt(g('camera_mount_position'))}")
    dim(ax, (xm_, ytop), (xp_, ytop), ytop + 11, f"{fmt(g('ppg_mount_position'))}")
    # tunnel on end view
    rv_y = lambda y: right["dx"] + y * s  # noqa: E731  (end view: screen x = +Y)
    rz = lambda z: right["dy"] + z * s  # noqa: E731
    fw = g("finger_opening_width")
    dim(ax, (rv_y(-fw / 2), rz(g("z_ceiling"))), (rv_y(fw / 2), rz(g("z_ceiling"))), rz(H_) + 6,
        f"tunnel {fmt(fw)}")
    dim(ax, (rv_y(fw / 2), rz(g("z_fs"))), (rv_y(fw / 2), rz(g("z_ceiling"))), rv_y(W_ / 2) + 14,
        f"{fmt(g('finger_opening_height'))}", horizontal=False)
    # leaders
    leader(ax, (elev["dx"] + g("x_m") * s, elev["dy"] + g("z_pin") * s), (150, 205), "Cocking knob (+Y, behind)")
    leader(ax, (elev["dx"] + g("release_button_x") * s, elev["dy"] + g("z_lever_mid") * s), (40, 126),
           "Mechanical release button (-Y)", ha="left")
    leader(ax, (top["dx"] + g("oled_position_x") * s, top["dy"] + 0), (190, 250), "OLED display window", ha="left")
    leader(ax, (top["dx"] + g("button_position_x") * s, top["dy"] + 0), (190, 240), "UI push-button (electronic)",
           ha="left")
    leader(ax, (rear["dx"] + 0, rear["dy"] + g("z_usb_mid") * s), (320, 200), "USB-C charge port")
    leader(ax, (bot["dx"] + g("battery_x_center") * s, bot["dy"] + 0), (185, 95), "Battery access cover", ha="left")
    notes(ax, 238, 125, [
        f"1. Housing envelope {fmt(L_)} x {fmt(W_)} x {fmt(H_)} mm measured from CAD shells;",
        f"   overall incl. knob / buttons {fmt(abb.XLength)} x {fmt(abb.YLength)} x {fmt(abb.ZLength)} mm.",
        "2. All dimensions are parametric (Params spreadsheet) and provisional.",
        "3. Finger enters from +X, palm-side down; pulp rests in centring trough.",
        "4. Split shell: lower = chassis/mechanism/electronics, upper = roof,",
        "   display, UI button, finger tunnel and reaction ceiling. 6x M2x30 from below.",
        "5. Mechanical release (-Y) is separate from the electronic UI button (top).",
        "6. Tolerances: none specified. FDM prototype; sliding fits set by",
        f"   moving_part_clearance = {g('moving_part_clearance')} mm radial - tune by test print.",
        "7. Materials are provisional assumptions; no part is validated for skin contact.",
        "8. Force, contact pressure and dwell time NOT specified - load-cell calibration required.",
    ])
    pdf.savefig(fig)
    plt.close(fig)
    print("sheet 1")

    # ================================================================================
    # Sheet 2 - longitudinal section A-A (y = 0), cocked state, with finger reference
    # ================================================================================
    fig, ax = new_sheet("Section A-A (y = 0) - cocked, reference finger", 2, NS, "2:1")
    s = 2.0
    ox, oy = 25, 138
    sec = section_paths(PARTS, (0, 1, 0), 0.0, lambda p: (p.x, p.z))
    draw_section(ax, sec, ox, oy, s)
    fs_ = FINGER.Shape.slice(Vec(0, 1, 0), 0.0)
    for w in fs_:
        pts = w.discretize(Deflection=0.05)
        ax.plot([ox + p.x * s for p in pts], [oy + p.z * s for p in pts], ls=(0, (4, 2)), lw=0.6, color="#c0703a")
    X = lambda x: ox + x * s  # noqa: E731
    Z = lambda z: oy + z * s  # noqa: E731
    ax.plot([X(g("x_m"))] * 2, [Z(-4), Z(H_ + 6)], lw=0.4, color="#2a6fb0", ls=(0, (8, 2, 1, 2)))
    ax.plot([X(g("x_ppg"))] * 2, [Z(-4), Z(H_ + 6)], lw=0.4, color="#7b3f99", ls=(0, (8, 2, 1, 2)))
    ax.text(X(g("x_m")), Z(H_ + 8), "Optical / plunger axis", fontsize=6.3, ha="center", color="#2a6fb0")
    ax.text(X(g("x_ppg")), Z(H_ + 8), "PPG axis", fontsize=6.3, ha="center", color="#7b3f99")
    # view cone (cocked)
    zl, zw = g("z_lens_top"), g("z_win_top") - g("contact_pad_thickness")
    rr = g("plunger_bore") / 2 - 0.3
    ax.plot([X(g("x_m")), X(g("x_m") - rr)], [Z(zl), Z(zw)], lw=0.5, color="#2a6fb0")
    ax.plot([X(g("x_m")), X(g("x_m") + rr)], [Z(zl), Z(zw)], lw=0.5, color="#2a6fb0")
    yb = Z(-9)
    dim(ax, (X(0), Z(0)), (X(g("x_tip")), Z(0)), yb, f"{fmt(g('x_tip'))}")
    dim(ax, (X(g("x_tip")), Z(0)), (X(g("x_m")), Z(0)), yb, f"{fmt(g('camera_mount_position'))}")
    dim(ax, (X(g("x_m")), Z(0)), (X(g("x_ppg")), Z(0)), yb, f"{fmt(g('ppg_mount_position'))}")
    dim(ax, (X(g("x_ppg")), Z(0)), (X(L_), Z(0)), yb, f"{fmt(L_ - g('x_ppg'))}")
    dim(ax, (X(0), Z(0)), (X(L_), Z(0)), Z(-20), f"{fmt(L_)}")
    xr = X(L_) + 8
    dim(ax, (X(L_), Z(0)), (X(L_), Z(g("z_split"))), xr, f"split {fmt(g('z_split'))}", horizontal=False)
    dim(ax, (X(L_), Z(g("z_fs"))), (X(L_), Z(g("z_ceiling"))), xr + 9, f"tunnel {fmt(g('finger_opening_height'))}",
        horizontal=False)
    dim(ax, (X(L_), Z(0)), (X(L_), Z(H_)), xr + 18, f"{fmt(H_)}", horizontal=False)
    xd = X(g("x_m") - 16)
    dim(ax, (xd, Z(zl)), (xd, Z(g("z_fs"))), xd, f"lens-skin {fmt(g('working_distance'))}", horizontal=False, fs=5.8)
    spread_row(ax, [((X(g("esp_x0") + 14), Z(g("z_pcb_top") + 2)), "ESP32-S3 carrier (placeholder)"),
                    ((X(g("oled_position_x")), Z(g("z_oled_pcb_top") + 0.7)), "OLED"),
                    ((X(g("x_tip")), Z(g("z_tunnel_axis"))), "Fingertip stop"),
                    ((X(g("x_m")), Z(g("z_win_top") - 0.7)), "Transparent contact window"),
                    ((X(g("x_m") + 15), Z(g("z_ceiling"))), "Reaction ceiling"),
                    ((X(g("x_ppg")), Z(g("z_fs") - 0.7)), "MAX30102 flush in trough")],
               Z(H_ + 14), 20, 400)
    spread_row(ax, [((X(g("battery_x_center")), Z(4)), "Battery envelope (TBD)"),
                    ((X(g("x_m") - 9.6), Z(g("z_seat_top") + 4)), "Compression spring"),
                    ((X(g("x_m")), Z(g("z_lens_top") - 2)), "Camera + macro lens (placeholder)"),
                    ((X(g("x_m") + 5.5), Z(g("z_mount_top") + g("cam_holder_h") + 0.9)), "Ring LED"),
                    ((X(g("x_m") + 11), Z(g("z_guide_top") + 1)), "Travel stop (shim-adjustable)")],
               Z(-27), 20, 400, below=True)
    notes(ax, 25, 70, [
        "Cocked state: spring at installed length, latch tooth over flange, window "
        f"{fmt(g('plunger_rest_gap'))} mm below trough so the finger inserts without contact.",
        f"Release: spring drives plunger up to {fmt(g('plunger_travel'))} mm; travel stop limits stroke. "
        f"Max indentation if finger is already on the ceiling = {fmt(g('plunger_travel') - g('plunger_rest_gap'))} mm.",
        "Re-cocking (pull knob down) lifts the window off the pulp - this is the refill-start event the camera times.",
        f"Camera views the pulp through the plunger bore (cone half-angle {REP['optics']['state2']['view_cone_half_angle_deg']} deg, "
        "no obstruction found in CAD check). Macro / close-focus lens required.",
        "Dashed outline = D14 mm reference fingertip (assumed, not anthropometric data).",
        "Section hatching: printed housing parts. Component envelopes are placeholders.",
    ])
    pdf.savefig(fig)
    plt.close(fig)
    print("sheet 2")

    # ================================================================================
    # Sheet 3 - section B-B through plunger axis: cocked vs max travel, mechanism dims
    # ================================================================================
    fig, ax = new_sheet("Section B-B - plunger mechanism, cocked / max travel", 3, NS, "3:1")
    s = 3.0
    mech_names = ["Plunger_Body", "Contact_Pad", "Compression_Spring", "Spring_Seat", "Guide", "Travel_Stop",
                  "Cocking_Feature", "Release_Trigger", "Release_Button", "Latch_Return_Spring", "Optical_Mount",
                  "Camera_Module", "Ring_LED", "Finger_Support", "Lower_Enclosure", "Upper_Enclosure"]
    xm = g("x_m")
    for k, (st, ox, ttl) in enumerate(((2, 45, "COCKED (latched)"), (4, 230, "MAX TRAVEL (on stop)"))):
        setp("state", st)
        objs = [B[n] for n in mech_names] + [l for l in LINKS if l.Name == "Fastener_Latch_Pivot"]
        sec = section_paths(objs, (1, 0, 0), xm, lambda p: (p.y, p.z))
        oy = 70
        draw_section(ax, sec, ox + 30 * s - 5, oy, s)
        Y = lambda y, ox=ox: ox + 30 * s - 5 + y * s  # noqa: E731
        Zs = lambda z: oy + z * s  # noqa: E731
        ax.text(Y(0), Zs(48), ttl, ha="center", fontsize=8, weight="bold", color=INK)
        ax.plot([Y(0)] * 2, [Zs(0), Zs(45)], lw=0.4, ls=(0, (8, 2, 1, 2)), color="#2a6fb0")
        if st == 2:
            dim(ax, (Y(-g("flange_diameter") / 2), Zs(g("z_flange_bot"))), (Y(g("flange_diameter") / 2),
                Zs(g("z_flange_bot"))), Zs(g("z_flange_bot")) - 8, f"flange D{fmt(g('flange_diameter'))}", fs=5.8)
            dim(ax, (Y(-g("plunger_diameter") / 2), Zs(g("z_win_top"))), (Y(g("plunger_diameter") / 2),
                Zs(g("z_win_top"))), Zs(g("z_win_top")) + 5, f"plunger D{fmt(g('plunger_diameter'))} / bore "
                f"D{fmt(g('plunger_bore'))}", fs=5.8)
            dim(ax, (Y(-12), Zs(g("z_seat_top"))), (Y(-12), Zs(g("z_flange_bot"))), Y(-17),
                f"spring {fmt(g('spring_installed_length'))} (cocked)", horizontal=False, fs=5.8)
            dim(ax, (Y(-12), Zs(g("z_flange_top"))), (Y(-12), Zs(g("z_guide_top"))), Y(-25),
                f"travel {fmt(g('plunger_travel'))}", horizontal=False, fs=5.8)
            leader(ax, (Y(g("latch_tooth_y") - 0.5), Zs(g("z_lever_mid"))), (20, Zs(52)),
                   f"Latch tooth, {fmt(g('latch_overlap'))} mm over flange rim", ha="left")
            leader(ax, (Y(15), Zs(g("z_pin"))), (Y(15), Zs(-8)), "Cocking pin + knob")
        else:
            dim(ax, (Y(12), Zs(g("z_seat_top"))), (Y(12), Zs(g("z_seat_top") + g("spring_len_current"))), Y(30),
                f"spring {fmt(g('spring_len_current'))} (preload {fmt(g('spring_preload_at_stop'))})",
                horizontal=False, fs=5.8)
            leader(ax, (Y(-10), Zs(g("z_guide_top"))), (Y(-29), Zs(36)), "Flange on travel stop")
            leader(ax, (Y(-10.4), Zs(g("z_lever_mid"))), (Y(-29), Zs(2)), "Tooth rotated clear (button pressed)")
    setp("state", 2)
    m = REP["mechanism"]
    notes(ax, 25, 58, [
        f"Sliding fits (radial): flange/guide {m['radial_clear_flange_guide_mm']}, tube/stop {m['radial_clear_tube_stop_mm']}, "
        f"tube/plate {m['radial_clear_tube_plate_mm']}, spring/guide {m['radial_clear_spring_guide_mm']}, "
        f"spring/collar {m['radial_clear_spring_collar_mm']} mm - FLAG: measure and tune after test print.",
        f"Spring: free {m['spring_free_length_mm']}, cocked {m['spring_installed_cocked_mm']}, on stop {m['spring_length_at_stop_mm']} mm, "
        f"solid ~{m['spring_solid_height_mm']} mm. Rate (k) NOT assigned - select stock spring, calibrate with load cell.",
        f"Latch: engagement {m['latch_engagement_mm']} mm; tooth retracts {m['tooth_retraction_mm']} mm for "
        f"{m['release_button_stroke_mm']} mm button stroke; flange lead-in chamfer cams the tooth when cocking.",
        "CAD checks: latch blocks upward motion when cocked; travel stop blocks over-travel; no unintended interference "
        "in any state.",
        "A fixed stroke does NOT guarantee a fixed force across fingers of different size / stiffness - see notes.",
        "Review before human testing: pinch points at window/aperture and knob slot, accidental release, spring retention.",
    ], fs=5.9)
    pdf.savefig(fig)
    plt.close(fig)
    print("sheet 3")

    # ================================================================================
    # Sheet 4 - electronics layout (plan, shells removed) + section through bays
    # ================================================================================
    fig, ax = new_sheet("Electronics compartment layout - plan with shells removed", 4, NS, "1.5:1")
    s = 1.5
    inner = [o.Shape for o in PARTS if o.Name not in ("Upper_Enclosure", "Display_Window", "Push_Button")
             and not o.Name.startswith(("Fastener_Shell", "Fastener_Plate"))]
    pl = draw_view(ax, inner, (0, 0, 1), (0, 1, 0), 30, 150, s, label="PLAN - internals (upper shell removed)")
    X4 = lambda x: pl["dx"] + x * s  # noqa: E731
    Y4 = lambda y: pl["dy"] + y * s  # noqa: E731
    lab4 = [((g("esp_x0") + 14, 0), "ESP32-S3-WROOM-1 on carrier (placeholder)"),
            ((15, -7), "USB-C charger board (placeholder)"),
            ((g("oled_position_x"), 12), "OLED module (above, roof bosses)"),
            ((g("latch_pivot_x") - 8, g("latch_pivot_y") - 1.5), "Latch lever + pivot"),
            ((g("x_m"), g("overall_width") / 2 + 4), "Cocking knob"),
            ((70, 4), "Camera FPC route"),
            ((g("x_ppg"), 0), "MAX30102"),
            ((g("x_m") + 10, 9), "Finger-support plate")]
    spread_row(ax, [((X4(x), Y4(y)), t) for (x, y), t in lab4 if y >= 0], Y4(30), 20, 400)
    spread_row(ax, [((X4(x), Y4(y)), t) for (x, y), t in lab4 if y < 0], 136, 20, 400, below=True)
    # elevation section through electronics bay, y = 0
    sec = section_paths([o for o in PARTS if o.Name != "Upper_Enclosure"], (0, 1, 0), 2.0, lambda p: (p.x, p.z))
    draw_section(ax, sec, 30, 45, s)
    ax.text(30 + 62 * s, 45 + 45 * s + 3, "SECTION C-C (y = 2) - stack-up, upper shell omitted", fontsize=7.5,
            weight="bold", ha="center", color=INK)
    mmc = REP["mechanism"]["min_clearance_moving_to_electronics_mm"]
    lines = [f"{k.replace('->', ' -> ')}: {v} mm" for k, v in list(mmc.items())[:6]]
    notes(ax, 245, 128, ["Minimum clearance, moving parts -> electronics (all 4 states):"] + lines + [
        "Battery: configurable envelope; chemistry, capacity and protection NOT selected.",
        "Battery removable downward through floor door; tray lifts out with both PCBs",
        "(USB-C slot is open-topped; upper-shell tongue closes it).",
        "Board outlines are PLACEHOLDERS - replace with verified vendor drawings.",
        "Keep WROOM antenna clear of screws/latch pivot (RF keep-out to be checked).",
    ], fs=5.9)
    pdf.savefig(fig)
    plt.close(fig)
    print("sheet 4")

    # ================================================================================
    # Sheet 5 - measurement zone detail (section A-A, released / contact) 4:1
    # ================================================================================
    fig, ax = new_sheet("Detail - measurement zone (released / contact)", 5, NS, "4:1")
    setp("state", 3)
    s = 4.0
    x0w = g("x_tip") - 6
    keepbox = Part.makeBox(g("overall_length") - x0w + 2, 60, 60, Vec(x0w, -30, -5))
    objs = [o for o in PARTS]
    sec = {}
    for o in objs:
        try:
            c = o.Shape.common(keepbox)
        except Exception:  # noqa: BLE001
            continue
        if c.isNull() or c.Volume < 1e-6:
            continue
        wires = c.slice(Vec(0, 1, 0), 0.0)
        polys = [[(p.x, p.z) for p in w.discretize(Deflection=0.01)] for w in wires]
        if polys:
            sec[o.Name if o.TypeId != "App::Link" else "Fastener"] = polys
    ox, oy = 25 - x0w * s, 75
    draw_section(ax, sec, ox, oy, s)
    fc = FINGER.Shape.common(keepbox).slice(Vec(0, 1, 0), 0.0)
    for w in fc:
        pts = w.discretize(Deflection=0.02)
        ax.plot([ox + p.x * s for p in pts], [oy + p.z * s for p in pts], ls=(0, (4, 2)), lw=0.7, color="#c0703a")
    X5 = lambda x: ox + x * s  # noqa: E731
    Z5 = lambda z: oy + z * s  # noqa: E731
    dim(ax, (X5(g("x_tip")), Z5(g("z_fs"))), (X5(g("x_m")), Z5(g("z_fs"))), Z5(g("z_ceiling")) + 10,
        f"stop -> camera axis {fmt(g('camera_mount_position'))}")
    dim(ax, (X5(g("x_m")), Z5(g("z_fs"))), (X5(g("x_ppg")), Z5(g("z_fs"))), Z5(g("z_ceiling")) + 10,
        f"camera -> PPG {fmt(g('ppg_mount_position'))}")
    dim(ax, (X5(g("x_m") + 9), Z5(g("z_fs"))), (X5(g("x_m") + 9), Z5(g("z_ceiling"))), X5(g("x_m") + 9),
        f"{fmt(g('finger_opening_height'))}", horizontal=False)
    dim(ax, (X5(g("x_m") - 9), Z5(g("z_lens_top"))), (X5(g("x_m") - 9), Z5(g("z_fs"))), X5(g("x_m") - 9),
        f"{fmt(g('working_distance'))}", horizontal=False)
    spread_row(ax, [((X5(g("x_m")), Z5(g("z_win_top") + g("stroke") - 0.5)), "Window indents pulp (blanch zone, illustrative)"),
                    ((X5(g("x_ppg")), Z5(g("z_fs"))), "MAX30102 face flush with trough"),
                    ((X5(g("x_tip")), Z5(g("z_tunnel_axis"))), "Fingertip stop (repeatable X datum)")],
               Z5(g("z_ceiling")) + 22, 20, 400)
    notes(ax, 25, 62, [
        "The camera, ring LED and contact window share one axis, so the same pulp region is imaged every cycle "
        "(subject to optical validation).",
        "PPG sits proximal to the blanch zone so it is not under the plunger; whether PPI is affected by distal compression "
        "must be tested.",
        f"Viewed skin diameter ~{REP['optics']['state2']['viewed_skin_diameter_mm']} mm (limited by window D"
        f"{fmt(g('contact_pad_diameter'))}). Window glare/reflection, colour calibration and focus are unverified.",
        "Indentation in this configuration is ILLUSTRATIVE (contact_indent_nominal) - real indentation depends on spring "
        "force and tissue stiffness.",
        "Fingertip interface requires ergonomic and safety testing across finger sizes before any human use.",
    ], fs=6.0)
    setp("state", 2)
    pdf.savefig(fig)
    plt.close(fig)
    print("sheet 5")

    # ================================================================================
    # Sheet 6 - exploded view + BOM
    # ================================================================================
    fig, ax = new_sheet("Exploded assembly + bill of materials", 6, NS, "NTS")
    ex = os.path.join(ROOT, "Renders", "_raw", "exploded.png")
    if os.path.exists(ex):
        im = mpimg.imread(ex)
        import numpy as np
        msk = im[..., :3].mean(axis=2) < 0.985
        ys, xs = np.where(msk)
        im = im[ys.min():ys.max(), xs.min():xs.max()]
        hh, ww = im.shape[:2]
        wmm = 190
        hmm = wmm * hh / ww
        if hmm > 222:
            hmm, wmm = 222, 222 * ww / hh
        ax.imshow(im, extent=(18, 18 + wmm, 50, 50 + hmm))
        ax.text(18, 50 + hmm + 4, "EXPLODED VIEW (rendered from CAD, explode = 1)", fontsize=7.5, weight="bold",
                color=INK)
    rows = list(csv.reader(open(os.path.join(ROOT, "Docs", "ShockGuard_BOM.csv"))))
    hdr, rows = rows[0], rows[1:]
    tx, ty = 222, 280
    ax.text(tx, ty, "BILL OF MATERIALS", fontsize=8, weight="bold", color=INK)
    cols = [(0, 6), (1, 34), (3, 6), (4, 78), (5, 22)]
    xx = tx
    for ci, wcol in cols:
        ax.text(xx, ty - 5, hdr[ci].upper(), fontsize=5.4, weight="bold", color=INK)
        xx += wcol
    for r, row in enumerate(rows):
        yy = ty - 9 - r * 5.6
        xx = tx
        for ci, wcol in cols:
            txt = row[ci]
            lim = int(wcol * 0.62) if ci == 4 else int(wcol * 0.75)
            txt = txt if len(txt) <= lim else txt[:lim - 1] + "."
            ax.text(xx, yy, txt, fontsize=5.0, color=INK)
            xx += wcol
        ax.plot([tx, tx + 146], [yy - 1.6, yy - 1.6], lw=0.15, color="#c9ced6")
    pdf.savefig(fig)
    plt.close(fig)
    print("sheet 6")

    # ================================================================================
    # Sheet 7 - master parameter table
    # ================================================================================
    fig, ax = new_sheet("Master parameters (Params spreadsheet) - status flags", 7, NS, "-")
    prow = list(csv.reader(open(os.path.join(ROOT, "Docs", "ShockGuard_Parameters.csv"))))[1:]
    ncol = 3
    per = math.ceil(len(prow) / ncol)
    colw = 132
    for c in range(ncol):
        x = 16 + c * colw
        ax.text(x, 282, "PARAMETER", fontsize=5.4, weight="bold", color=INK)
        ax.text(x + 52, 282, "VALUE", fontsize=5.4, weight="bold", color=INK)
        ax.text(x + 72, 282, "STATUS", fontsize=5.4, weight="bold", color=INK)
        for i, row in enumerate(prow[c * per:(c + 1) * per]):
            y = 277 - i * 4.05
            col = {"VERIFY": "#b03a2e", "PLACEHOLDER": "#9a6a00", "DERIVED": "#5a6470", "CONFIG": "#2a6fb0"}.get(
                row[3], INK)
            ax.text(x, y, row[0], fontsize=4.9, color=INK)
            ax.text(x + 52, y, f"{row[1]} {row[2] if row[2] not in ('-', 'mm') else ''}", fontsize=4.9, color=INK)
            ax.text(x + 72, y, row[3], fontsize=4.9, color=col)
    ax.text(16, 50, "VERIFY = must be confirmed by test/analysis;  PLACEHOLDER = replace with selected component "
                    "datasheet;  ASSUMED = modelling assumption;  DERIVED = spreadsheet formula;  CONFIG = state switch.",
            fontsize=6, color=INK)
    pdf.savefig(fig)
    plt.close(fig)
    print("sheet 7")

print("DRAWINGS_DONE", pdf_path)
