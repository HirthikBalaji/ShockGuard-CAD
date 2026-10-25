# -*- coding: utf-8 -*-
"""ShockGuard master parameter table.

Single source of truth for the spreadsheet `Params` inside ShockGuard_Assembly.FCStd.
Every geometric feature in the FreeCAD model is bound to these aliases through
expressions, so editing a value in the spreadsheet and recomputing propagates through
the whole assembly.

Status codes
  ASSUMED      initial modelling assumption (engineering judgement, not validated)
  VERIFY       must be confirmed by test / analysis before human use
  PLACEHOLDER  component envelope; replace with the selected part's datasheet drawing
  DERIVED      computed from other parameters (spreadsheet formula)
  CONFIG       configuration switch (mechanism state, explode factor)

Formulas are written so that they are valid both as FreeCAD spreadsheet expressions and
as Python expressions (the build script evaluates them in Python to seed sketch geometry
and cross-checks against the spreadsheet after recompute).
"""

# (alias, value-or-formula, unit, status, note)
INPUTS = [
    # --- overall envelope -------------------------------------------------------------
    ("overall_length", 125.0, "mm", "ASSUMED", "Housing length along X (finger axis)"),
    ("overall_width", 42.0, "mm", "ASSUMED", "Housing width along Y"),
    ("overall_height", 42.0, "mm", "ASSUMED",
     "Housing height along Z; 2 mm above the 25-40 mm guide because the coaxial camera/plunger stack sits under the finger tunnel"),
    ("corner_radius", 6.0, "mm", "ASSUMED", "Plan-view corner radius"),
    ("top_edge_fillet", 2.0, "mm", "ASSUMED", "Fillet on upper-shell top perimeter"),
    ("bottom_edge_fillet", 1.5, "mm", "ASSUMED", "Fillet on lower-shell bottom perimeter"),
    ("enclosure_wall_thickness", 2.0, "mm", "VERIFY", "FDM wall / floor / roof thickness (5 perimeters @0.4 mm)"),
    # --- finger interface ---------------------------------------------------------------
    ("finger_opening_width", 22.0, "mm", "VERIFY", "Tunnel width; ergonomic test across adult finger sizes required"),
    ("finger_opening_height", 16.0, "mm", "VERIFY", "Tunnel height from trough bottom to reaction ceiling"),
    ("finger_support_length", 45.0, "mm", "ASSUMED", "Tunnel length from fingertip stop to entry face"),
    ("trough_radius", 14.0, "mm", "ASSUMED", "Concave centring trough radius in finger support"),
    ("trough_depth", 1.5, "mm", "ASSUMED", "Trough depth below support-plate top"),
    ("camera_mount_position", 9.0, "mm", "VERIFY", "Fingertip stop -> plunger/camera axis (pulp centre)"),
    ("ppg_mount_position", 21.0, "mm", "VERIFY", "Plunger axis -> MAX30102 centre (proximal on finger)"),
    ("plate_half_width", 13.0, "mm", "ASSUMED", "Half-width of the finger-support plate"),
    # --- plunger mechanism -----------------------------------------------------------
    ("plunger_diameter", 16.5, "mm", "ASSUMED", "Plunger tube OD"),
    ("plunger_bore", 13.0, "mm", "ASSUMED", "Plunger optical bore ID (camera/LED path)"),
    ("flange_diameter", 20.0, "mm", "ASSUMED", "Plunger flange OD (spring seat + latch face)"),
    ("flange_thickness", 3.0, "mm", "ASSUMED", "Plunger flange thickness"),
    ("flange_chamfer", 0.6, "mm", "ASSUMED", "Lead-in chamfer on flange top (cams latch tooth when cocking)"),
    ("plunger_travel", 4.0, "mm", "VERIFY", "Max stroke from cocked position to travel stop"),
    ("plunger_rest_gap", 0.8, "mm", "ASSUMED", "Contact window below trough surface when cocked (insertion clearance)"),
    ("contact_indent_nominal", 2.0, "mm", "VERIFY", "ILLUSTRATIVE pulp indentation used only for the 'released' configuration"),
    ("contact_pad_diameter", 14.0, "mm", "ASSUMED", "Transparent contact window OD"),
    ("contact_pad_thickness", 1.5, "mm", "ASSUMED", "Transparent contact window thickness"),
    ("spring_outer_diameter", 20.0, "mm", "PLACEHOLDER", "Compression spring OD - select stock spring, measure k"),
    ("spring_wire_diameter", 0.8, "mm", "PLACEHOLDER", "Spring wire diameter"),
    ("spring_free_length", 14.0, "mm", "PLACEHOLDER", "Spring free length"),
    ("spring_installed_length", 8.0, "mm", "VERIFY", "Spring length in the cocked state"),
    ("spring_total_coils", 6.0, "-", "PLACEHOLDER", "Total coils (geometry only; no rate assigned)"),
    ("guide_wall", 2.0, "mm", "ASSUMED", "Guide tube wall"),
    ("spring_seat_thickness", 1.0, "mm", "ASSUMED", "Spring seat washer thickness"),
    ("stop_thickness", 2.0, "mm", "VERIFY", "Travel-stop ring thickness (shim-adjustable stroke)"),
    ("support_plate_thickness", 3.0, "mm", "ASSUMED", "Finger-support plate thickness"),
    ("moving_part_clearance", 0.3, "mm", "VERIFY", "Radial clearance on sliding fits (FDM: tune 0.2-0.4)"),
    ("plunger_hole_clearance", 0.5, "mm", "ASSUMED", "Radial clearance plunger <-> finger-support hole"),
    ("cocking_pin_diameter", 2.5, "mm", "ASSUMED", "Radial cocking pin (steel dowel) diameter"),
    ("knob_diameter", 8.0, "mm", "ASSUMED", "Cocking knob diameter"),
    ("knob_length", 6.0, "mm", "ASSUMED", "Cocking knob length"),
    ("latch_overlap", 1.2, "mm", "VERIFY", "Radial engagement of latch tooth over flange rim"),
    ("latch_thickness", 2.0, "mm", "ASSUMED", "Latch lever thickness"),
    ("latch_release_angle", 8.6, "deg", "DERIVED",
     "Lever rotation that clears the tooth (overlap+0.3 mm over 10 mm arm)"),
    ("release_button_x_offset", 23.0, "mm", "ASSUMED", "Plunger axis -> release button (on -Y side)"),
    # --- optics -------------------------------------------------------------------------
    ("optical_mount_thickness", 2.5, "mm", "ASSUMED", "Optical bracket base thickness"),
    ("optical_mount_size", 26.0, "mm", "ASSUMED", "Optical bracket square size"),
    ("collar_od", 17.0, "mm", "ASSUMED", "Ring-LED collar OD (also centres the spring)"),
    ("collar_id", 12.4, "mm", "ASSUMED", "Ring-LED collar ID"),
    ("cam_board_size", 9.0, "mm", "PLACEHOLDER", "Camera stiffener square (OV2640-class module envelope)"),
    ("cam_board_t", 0.5, "mm", "PLACEHOLDER", "Camera stiffener thickness"),
    ("cam_holder", 8.5, "mm", "PLACEHOLDER", "Lens holder square"),
    ("cam_holder_h", 4.5, "mm", "PLACEHOLDER", "Lens holder height (= collar height)"),
    ("cam_barrel_d", 7.0, "mm", "PLACEHOLDER", "Lens barrel diameter"),
    ("cam_barrel_h", 2.0, "mm", "PLACEHOLDER", "Lens barrel height"),
    ("ring_light_diameter", 14.0, "mm", "PLACEHOLDER", "Ring-LED PCB OD"),
    ("ring_light_inner", 9.0, "mm", "PLACEHOLDER", "Ring-LED PCB ID"),
    ("ring_light_thickness", 0.8, "mm", "PLACEHOLDER", "Ring-LED PCB thickness"),
    ("ring_led_radius", 5.5, "mm", "PLACEHOLDER", "LED pitch radius (inside plunger bore)"),
    # --- PPG ------------------------------------------------------------------------------
    ("max_pcb", 14.0, "mm", "PLACEHOLDER", "MAX30102 breakout PCB square"),
    ("max_pcb_t", 1.0, "mm", "PLACEHOLDER", "MAX30102 breakout PCB thickness"),
    ("max_sensor_l", 5.6, "mm", "PLACEHOLDER", "MAX30102 package length (datasheet 5.6 mm - verify)"),
    ("max_sensor_w", 3.3, "mm", "PLACEHOLDER", "MAX30102 package width (datasheet 3.3 mm - verify)"),
    ("max_sensor_h", 1.55, "mm", "PLACEHOLDER", "MAX30102 package height (datasheet 1.55 mm - verify)"),
    # --- display / UI ---------------------------------------------------------------------
    ("oled_pcb_w", 27.3, "mm", "PLACEHOLDER", "0.96in OLED module PCB (X)"),
    ("oled_pcb_h", 27.8, "mm", "PLACEHOLDER", "0.96in OLED module PCB (Y)"),
    ("oled_pcb_t", 1.2, "mm", "PLACEHOLDER", "OLED PCB thickness"),
    ("oled_glass_w", 26.7, "mm", "PLACEHOLDER", "OLED glass (X)"),
    ("oled_glass_h", 19.3, "mm", "PLACEHOLDER", "OLED glass (Y)"),
    ("oled_glass_t", 1.4, "mm", "PLACEHOLDER", "OLED glass thickness"),
    ("oled_window_width", 24.0, "mm", "ASSUMED", "Display window opening (X)"),
    ("oled_window_height", 13.0, "mm", "ASSUMED", "Display window opening (Y)"),
    ("oled_position_x", 40.0, "mm", "ASSUMED", "Display centre X"),
    ("oled_lens_t", 1.0, "mm", "ASSUMED", "Clear display lens thickness"),
    ("button_position_x", 14.0, "mm", "ASSUMED", "UI push-button centre X"),
    ("button_cap_d", 8.0, "mm", "ASSUMED", "UI button cap diameter"),
    # --- electronics ---------------------------------------------------------------------
    ("esp_x0", 33.0, "mm", "ASSUMED", "ESP32-S3 carrier PCB start X"),
    ("esp_pcb_l", 30.0, "mm", "PLACEHOLDER", "ESP32-S3 carrier PCB length (custom carrier, TBD)"),
    ("esp_pcb_w", 22.0, "mm", "PLACEHOLDER", "ESP32-S3 carrier PCB width"),
    ("pcb_t", 1.6, "mm", "ASSUMED", "Standard PCB thickness"),
    ("wroom_l", 25.5, "mm", "PLACEHOLDER", "ESP32-S3-WROOM-1 length (datasheet 25.5 - verify)"),
    ("wroom_w", 18.0, "mm", "PLACEHOLDER", "ESP32-S3-WROOM-1 width (datasheet 18.0 - verify)"),
    ("wroom_h", 3.1, "mm", "PLACEHOLDER", "ESP32-S3-WROOM-1 height (datasheet 3.1 - verify)"),
    ("chg_pcb_l", 28.0, "mm", "PLACEHOLDER", "Li-ion charger board length (TP4056-class, TBD)"),
    ("chg_pcb_w", 17.0, "mm", "PLACEHOLDER", "Charger board width"),
    ("usbc_w", 8.94, "mm", "PLACEHOLDER", "USB-C receptacle width"),
    ("usbc_l", 7.35, "mm", "PLACEHOLDER", "USB-C receptacle depth"),
    ("usbc_h", 3.26, "mm", "PLACEHOLDER", "USB-C receptacle height"),
    ("battery_length", 38.0, "mm", "PLACEHOLDER", "Battery envelope (chemistry/capacity NOT selected)"),
    ("battery_width", 22.0, "mm", "PLACEHOLDER", "Battery envelope width"),
    ("battery_thickness", 6.0, "mm", "PLACEHOLDER", "Battery envelope thickness"),
    ("battery_x_center", 33.0, "mm", "ASSUMED", "Battery centre X"),
    ("tray_z", 10.0, "mm", "ASSUMED", "Electronics tray underside Z"),
    ("tray_thickness", 1.6, "mm", "ASSUMED", "Electronics tray thickness"),
    ("standoff_h", 3.0, "mm", "ASSUMED", "PCB standoff height on tray"),
    ("electronics_clearance", 1.0, "mm", "VERIFY", "Minimum air gap PCB/battery <-> moving parts"),
    # --- fasteners -----------------------------------------------------------------------
    ("screw_d", 2.0, "mm", "ASSUMED", "M2 screws throughout"),
    ("fastener_clearance", 0.2, "mm", "VERIFY", "Radial clearance on screw holes (2.4 mm hole)"),
    ("pilot_d", 1.7, "mm", "VERIFY", "Pilot for self-tapping M2 (or replace with heat-set inserts)"),
    # --- configuration -----------------------------------------------------------------
    ("state", 2.0, "-", "CONFIG", "1=Rest(uncocked, on stop) 2=Cocked 3=Released/contact 4=Max travel"),
    ("explode", 0.0, "-", "CONFIG", "0 = assembled, 1 = exploded"),
]

DERIVED = [
    ("x_tip", "overall_length - finger_support_length", "Fingertip stop X"),
    ("x_m", "x_tip + camera_mount_position", "Measurement axis X (plunger + camera)"),
    ("x_ppg", "x_m + ppg_mount_position", "MAX30102 centre X"),
    ("z_mount_top", "enclosure_wall_thickness + optical_mount_thickness", "Optical bracket top"),
    ("z_seat_top", "z_mount_top + spring_seat_thickness", "Spring seat top"),
    ("z_flange_bot", "z_seat_top + spring_installed_length", "Flange underside (cocked)"),
    ("z_flange_top", "z_flange_bot + flange_thickness", "Flange top (cocked)"),
    ("z_guide_top", "z_flange_top + plunger_travel", "Guide top = travel-stop face"),
    ("z_stop_top", "z_guide_top + stop_thickness", "Travel stop top"),
    ("z_split", "z_stop_top + support_plate_thickness", "Shell split plane = support plate top"),
    ("z_fs", "z_split - trough_depth", "Finger contact surface (trough bottom)"),
    ("z_win_top", "z_fs - plunger_rest_gap", "Contact window top (cocked)"),
    ("z_ceiling", "z_fs + finger_opening_height", "Tunnel reaction ceiling"),
    ("z_tunnel_axis", "z_ceiling - finger_opening_width / 2", "Tunnel arch axis"),
    ("top_over_tunnel", "overall_height - z_ceiling", "Roof thickness over tunnel (check >= 1.5)"),
    ("z_lens_top", "z_mount_top + cam_holder_h + cam_barrel_h", "Camera lens front"),
    ("working_distance", "z_fs - z_lens_top", "Lens front -> skin (macro lens needed)"),
    ("z_pin", "z_flange_bot + flange_thickness / 2", "Cocking pin axis (cocked)"),
    ("guide_id", "flange_diameter + 2 * moving_part_clearance", "Guide bore"),
    ("guide_od", "guide_id + 2 * guide_wall", "Guide OD"),
    ("stop_bore", "plunger_diameter + 2 * moving_part_clearance", "Travel-stop bore"),
    ("z_lever_bot", "z_flange_top + 0.1", "Latch lever underside"),
    ("z_lever_top", "z_lever_bot + latch_thickness", "Latch lever top"),
    ("z_lever_mid", "z_lever_bot + latch_thickness / 2", "Latch lever mid-plane / release button axis"),
    ("latch_pivot_x", "x_m - 10", "Latch pivot X"),
    ("latch_pivot_y", "-(flange_diameter / 2 + 1)", "Latch pivot Y"),
    ("latch_tooth_y", "-(flange_diameter / 2 - latch_overlap)", "Latch tooth tip Y"),
    ("release_button_x", "x_m - release_button_x_offset", "Release button X"),
    ("latch_spring_x", "latch_pivot_x - 12", "Latch return-spring X"),
    ("latch_post_y", "-5", "Latch spring post face Y"),
    ("stroke", "state == 2 ? 0 : (state == 3 ? plunger_rest_gap + contact_indent_nominal : plunger_travel)",
     "Current plunger stroke from cocked position"),
    ("latch_angle", "state == 2 ? 0 : -latch_release_angle", "Current latch lever angle"),
    ("spring_len_current", "spring_installed_length + stroke", "Current spring length"),
    ("latch_spring_len", "(latch_post_y - latch_pivot_y) - (latch_spring_x - latch_pivot_x) * sin(latch_angle)",
     "Current latch-spring length"),
    ("z_tray_top", "tray_z + tray_thickness", "Tray top"),
    ("z_pcb_bot", "z_tray_top + standoff_h", "Carrier / charger PCB underside"),
    ("z_pcb_top", "z_pcb_bot + pcb_t", "Carrier / charger PCB top"),
    ("z_usb_mid", "z_pcb_top + usbc_h / 2", "USB-C axis Z"),
    ("z_oled_pcb_top", "overall_height - enclosure_wall_thickness - oled_glass_t", "OLED PCB top"),
    ("z_max_pcb_top", "z_stop_top - 0.05", "MAX30102 PCB top"),
    ("plate_x0", "x_m - 20", "Finger-support plate rear edge"),
    ("plate_x1", "overall_length - enclosure_wall_thickness - 1.5", "Finger-support plate front edge"),
    ("z_button_cap_bot", "overall_height - enclosure_wall_thickness - 1", "UI button flange underside"),
    ("z_switch_bot", "z_button_cap_bot - 1 - 3.5", "Tactile switch body underside"),
    ("hole_r", "screw_d / 2 + fastener_clearance", "M2 clearance hole radius"),
    ("pilot_r", "pilot_d / 2", "M2 pilot radius"),
    ("spring_preload_at_stop", "spring_free_length - spring_installed_length - plunger_travel",
     "Spring deflection with plunger on stop (must be > 0 for retention)"),
]


def python_eval_all():
    """Evaluate the whole table in Python (mirrors the spreadsheet)."""
    import math
    env = {"sin": lambda d: math.sin(math.radians(d)), "cos": lambda d: math.cos(math.radians(d))}
    vals = {a: float(v) for a, v, *_ in INPUTS}
    for a, f, _ in DERIVED:
        if a == "stroke":
            s = vals["state"]
            vals[a] = 0.0 if s == 2 else (vals["plunger_rest_gap"] + vals["contact_indent_nominal"] if s == 3
                                          else vals["plunger_travel"])
        elif a == "latch_angle":
            vals[a] = 0.0 if vals["state"] == 2 else -vals["latch_release_angle"]
        else:
            vals[a] = float(eval(f, dict(env), dict(vals)))
    return vals
