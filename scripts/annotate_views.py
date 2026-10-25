# -*- coding: utf-8 -*-
"""
Annotate the raw FreeCAD renders (Renders/_raw/*.png) with titles and leader-line labels.
Label anchor points are the 3-D model points projected by render_views.py, so every
leader lands on the real geometry.

    /Applications/FreeCAD.app/Contents/Resources/bin/python annotate_views.py
"""
import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.image as mpimg  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
RAW = os.path.join(ROOT, "Renders", "_raw")
OUT = os.path.join(ROOT, "Renders")
LABELS = json.load(open(os.path.join(OUT, "_labels.json")))
FOOT = ("Generated from ShockGuard_Assembly.FCStd (FreeCAD 1.1.4, parametric).  PROPOSED ENGINEERING CONCEPT - "
        "dimensions, forces, optics and safety not validated.")
INK, ACCENT = "#1d2733", "#c0392b"

VIEWS = {
    "iso": ("ShockGuard_Isometric_View", "Isometric view - assembled (cocked state)"),
    "iso_rear": ("ShockGuard_Isometric_Rear_View", "Isometric view - rear / release-button side"),
    "iso_bottom": ("ShockGuard_Isometric_Bottom_View", "Isometric view - underside (battery cover, shell screws)"),
    "iso_finger": ("ShockGuard_Isometric_With_Finger", "Isometric view with reference fingertip (D14 mm, assumed)"),
    "exploded": ("ShockGuard_Exploded_View", "Exploded assembly view"),
    "section": ("ShockGuard_Section_View", "Longitudinal section A-A (y = 0) - released / contact state"),
    "electronics": ("ShockGuard_Electronics_Compartment", "Electronics compartment - upper shell removed"),
    "electronics_display": ("ShockGuard_Display_and_UI_Underside", "Upper shell from below - OLED and UI switch"),
    "plunger_closeup": ("ShockGuard_Plunger_Mechanism_Closeup",
                        "Plunger mechanism close-up - section B-B through plunger axis (cocked)"),
    "measurement_zone": ("ShockGuard_Measurement_Zone_Closeup",
                         "Measurement zone - finger position and sensor locations (section A-A, contact)"),
}


def crop(img, pts, margin=60):
    rgb = img[..., :3]
    mask = rgb.mean(axis=2) < 0.985
    ys, xs = np.where(mask)
    if len(xs) == 0:
        return img, pts, (0, 0)
    x0, x1 = max(xs.min() - margin, 0), min(xs.max() + margin, img.shape[1])
    y0, y1 = max(ys.min() - margin, 0), min(ys.max() + margin, img.shape[0])
    return img[y0:y1, x0:x1], {k: [v[0] - x0, v[1] - y0] for k, v in pts.items()}, (x0, y0)


def annotate(key, fname, title, label_side_pad=0.30):
    path = os.path.join(RAW, key + ".png")
    if not os.path.exists(path):
        print("missing", key)
        return
    img = mpimg.imread(path)
    pts = {k: v[:2] for k, v in LABELS.get(key, {}).get("points", {}).items()}
    img, pts, _ = crop(img, pts)
    h, w = img.shape[:2]
    pad = int(w * label_side_pad) if pts else 0
    W, H = w + 2 * pad, h + 170
    fig = plt.figure(figsize=(W / 200, H / 200), dpi=200)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W)
    ax.set_ylim(H, 0)
    ax.axis("off")
    ax.imshow(img, extent=(pad, pad + w, 110 + h, 110))
    ax.text(30, 55, "ShockGuard", fontsize=17, weight="bold", color=INK, va="center")
    ax.text(30 + 345, 57, title, fontsize=12.5, color=INK, va="center")
    ax.plot([30, W - 30], [92, 92], color=INK, lw=1)
    ax.text(30, H - 28, FOOT, fontsize=7.2, color="#5a6470", va="center")
    if pts:
        cx = pad + w / 2
        left = sorted([(k, v) for k, v in pts.items() if v[0] + pad < cx], key=lambda kv: kv[1][1])
        right = sorted([(k, v) for k, v in pts.items() if v[0] + pad >= cx], key=lambda kv: kv[1][1])
        for side, items in (("L", left), ("R", right)):
            n = len(items)
            if not n:
                continue
            top, bot = 150, 110 + h - 40
            ys = [top + (bot - top) * (i + 0.5) / n for i in range(n)]
            for (lab, (px, py)), ty in zip(items, ys):
                px, py = px + pad, py + 110
                if side == "L":
                    tx, ha, lx = pad - 20, "right", pad - 12
                else:
                    tx, ha, lx = pad + w + 20, "left", pad + w + 12
                ax.plot([lx, px], [ty, py], color=ACCENT, lw=0.9)
                ax.plot([px], [py], "o", ms=3.5, color=ACCENT)
                ax.text(tx, ty, lab, fontsize=9.5, ha=ha, va="center", color=INK,
                        bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="#c9ced6", lw=0.6))
    out = os.path.join(OUT, fname + ".png")
    fig.savefig(out, dpi=200)
    plt.close(fig)
    print("wrote", out)


def composite(fname, title, tiles, ncol):
    imgs = []
    for key, cap in tiles:
        p = os.path.join(RAW, key + ".png")
        if os.path.exists(p):
            im, _, _ = crop(mpimg.imread(p), {}, 30)
            imgs.append((im, cap))
    if not imgs:
        return
    nrow = (len(imgs) + ncol - 1) // ncol
    fig = plt.figure(figsize=(16, 4.6 * nrow + 1.0), dpi=150)
    fig.text(0.02, 0.985, "ShockGuard", fontsize=17, weight="bold", color=INK, va="top")
    fig.text(0.16, 0.982, title, fontsize=12.5, color=INK, va="top")
    for i, (im, cap) in enumerate(imgs):
        ax = fig.add_subplot(nrow, ncol, i + 1)
        ax.imshow(im)
        ax.set_title(cap, fontsize=10.5, color=INK)
        ax.axis("off")
    fig.text(0.02, 0.008, FOOT, fontsize=7.2, color="#5a6470")
    fig.tight_layout(rect=(0, 0.02, 1, 0.96))
    out = os.path.join(OUT, fname + ".png")
    fig.savefig(out)
    plt.close(fig)
    print("wrote", out)


if __name__ == "__main__":
    for key, (fname, title) in VIEWS.items():
        annotate(key, fname, title)
    composite("ShockGuard_Mechanism_States",
              "Plunger sequence - section B-B through plunger axis (CAD configurations, NOT a force simulation)",
              [("mech_state_2", "1. Cocked: spring compressed, tooth over flange, window 0.8 mm below trough"),
               ("mech_state_3", "2. Released: window blanches pulp (indent illustrative)"),
               ("mech_state_4", "3. Max travel: flange on travel stop (no finger)"),
               ("mech_state_1", "4. Rest / reset: on stop, re-cock by pulling knob down")], 2)
    composite("ShockGuard_Orthographic_Views", "Orthographic views (third-angle arrangement on drawing sheet 1)",
              [("ortho_front", "Front (finger entry, +X)"), ("ortho_rear", "Rear (USB-C, -X)"),
               ("ortho_side", "Side (-Y, release button)"), ("ortho_top", "Top (display, UI button)"),
               ("ortho_bottom", "Bottom (battery cover, screws)")], 3)
