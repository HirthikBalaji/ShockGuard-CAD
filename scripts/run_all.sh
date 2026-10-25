#!/bin/zsh
# Regenerate the complete ShockGuard CAD package from source.
#   1. build parametric FreeCAD model      (headless)
#   2. verify + export STEP / STL / CSV    (headless)
#   3. render views + save colours         (FreeCAD GUI - a window opens briefly)
#   4. annotate renders                    (FreeCAD's bundled Python + matplotlib)
#   5. engineering drawings PDF            (headless)
set -e
cd "$(dirname "$0")"
FC=/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd
PY=/Applications/FreeCAD.app/Contents/Resources/bin/python
$FC build_shockguard.py
$FC verify_and_export.py
rm -f ../Renders/_labels.json
SG_SAVE=1 ./run_render.sh || true
$PY annotate_views.py
$FC make_drawings.py
echo "done - see ../Docs/verification_report.json"
