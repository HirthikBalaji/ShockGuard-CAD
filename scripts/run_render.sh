#!/bin/zsh
# usage: SG_VIEWS=a,b SG_SAVE=0 ./run_render.sh
cd "$(dirname "$0")"
R=../Renders; rm -f $R/_render.done
/Applications/FreeCAD.app/Contents/MacOS/FreeCAD render_views.py > $R/_render.log 2>&1 &
PID=$!
for i in $(seq 1 180); do
  [ -f $R/_render.done ] && break
  grep -q "Exception while processing" $R/_render.log && break
  /bin/sleep 3
done
/bin/sleep 1; kill $PID 2>/dev/null; pkill -f "Resources/bin/freecad render_views" 2>/dev/null
cat $R/_render_progress.txt; grep -E "Exception while" $R/_render.log
