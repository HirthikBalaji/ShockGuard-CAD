# Regenerating the package

The FCStd, exports, renders and drawings are all generated from the scripts in [`scripts/`](../scripts).

## Toolchain
- **FreeCAD 1.1.4.** On macOS: `brew install --cask freecad`. The scripts use the bundled `freecadcmd` and Python (3.11, which includes matplotlib).
- The renderer needs the FreeCAD **GUI** (an OpenGL context), so a window opens for a short time while it runs.

The paths in `run_all.sh` / `run_render.sh` point to `/Applications/FreeCAD.app`. Edit `FC` and `PY` for other platforms; on Linux these are `freecadcmd` and FreeCAD's Python.

## One command
```sh
./scripts/run_all.sh
```

## Pipeline
| Step | Script | Runs in | Produces |
|---|---|---|---|
| 1 | `sg_params.py` | (imported) | Master parameter table: inputs plus derived formulas, valid both as Python and as FreeCAD expressions |
| 2 | `build_shockguard.py` | `freecadcmd` | `CAD/ShockGuard_Assembly.FCStd`, `CAD/model_meta.json` |
| 3 | `verify_and_export.py` | `freecadcmd` | Checks, `STEP/`, `STL/`, `Docs/*.csv`, `Docs/verification_report.json` |
| 4 | `render_views.py` (via `run_render.sh`) | FreeCAD GUI | `Renders/_raw/*.png`, label anchors; saves colours into the FCStd |
| 5 | `annotate_views.py` | FreeCAD Python | `Renders/ShockGuard_*.png` |
| 6 | `make_drawings.py` | `freecadcmd` | `Drawings/ShockGuard_Engineering_Drawings.pdf` and sheet previews |

## How the model is parametric
- Every PartDesign feature dimension, sketch constraint and placement is a FreeCAD **expression** referencing `Params.<alias>`.
- Derived quantities, such as the vertical stack `z_*` and the mechanism `stroke` and `latch_angle`, are spreadsheet formulas.
- Mechanism configurations are Body placement expressions driven by `Params.state`. The exploded view uses `Params.explode`.
- Fasteners are four parametric screw bodies, placed by `App::Link` objects whose placements are also expressions.

To change one design value, edit the spreadsheet in FreeCAD and recompute; no rebuild is needed. To change the design rules themselves (feature topology), edit `build_shockguard.py` and rerun the pipeline.
