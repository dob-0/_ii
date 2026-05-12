#!/bin/bash
# _ii X session — controller on laptop panel, visuals on second monitor when present.
set -u

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
ROOT_DIR="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"
PY_BIN="${PY_BIN:-$(command -v python3 || echo /usr/bin/python3)}"

export DISPLAY=:0
if [ -z "${XAUTHORITY:-}" ]; then
    if [ -f "$HOME/.Xauthority" ]; then
        export XAUTHORITY="$HOME/.Xauthority"
    else
        export XAUTHORITY="/home/dob/.Xauthority"
    fi
fi

xset s off -dpms 2>/dev/null || true
xsetroot -solid black 2>/dev/null || true
unclutter -idle 1 -root &
openbox &
sleep 0.4

LAPTOP=$(xrandr --query 2>/dev/null | awk '/LVDS|eDP/{print $1; exit}')
HDMI=$(xrandr --query 2>/dev/null | awk '/HDMI|^DP-/{print $1; exit}')
LAPTOP=${LAPTOP:-LVDS-1}
HDMI=${HDMI:-HDMI-1}

if xrandr --query | grep -q "^$HDMI connected"; then
    xrandr --output "$LAPTOP" --auto --primary \
           --output "$HDMI" --auto --right-of "$LAPTOP" 2>/dev/null || true
else
    xrandr --output "$LAPTOP" --auto --primary 2>/dev/null || true
fi
sleep 0.3

_geom() {
    xrandr --query | awk -v d="$1" '
        $1==d && / connected /{
            match($0,/[0-9]+x[0-9]+\+[0-9]+\+[0-9]+/)
            print substr($0,RSTART,RLENGTH)
        }'
}
LG=$(_geom "$LAPTOP")
HG=$(_geom "$HDMI")
LW=$(echo "${LG:-1366x768+0+0}" | cut -dx -f1)
LH=$(echo "${LG:-1366x768+0+0}" | cut -d+ -f1 | cut -dx -f2)
LX=$(echo "${LG:-1366x768+0+0}" | cut -d+ -f2)
LY=$(echo "${LG:-1366x768+0+0}" | cut -d+ -f3)
HW=$(echo "${HG:-1920x1080+1366+0}" | cut -dx -f1)
HH=$(echo "${HG:-1920x1080+1366+0}" | cut -d+ -f1 | cut -dx -f2)
HX=$(echo "${HG:-1920x1080+1366+0}" | cut -d+ -f2)
HY=$(echo "${HG:-1920x1080+1366+0}" | cut -d+ -f3)

launch_controller() {
    if command -v kitty >/dev/null 2>&1; then
        kitty \
          --title '_ii controller' \
          --override background=black \
          --override foreground=white \
          --override font_size=10.0 \
          -e "$PY_BIN" "$ROOT_DIR/_ii.py" &
        return
    fi
    if command -v x-terminal-emulator >/dev/null 2>&1; then
        x-terminal-emulator -e "$PY_BIN" "$ROOT_DIR/_ii.py" &
        return
    fi
    if command -v xterm >/dev/null 2>&1; then
        xterm -T '_ii controller' -e "$PY_BIN" "$ROOT_DIR/_ii.py" &
        return
    fi
    "$PY_BIN" "$ROOT_DIR/_ii.py" &
}

launch_controller
CTRL_PID=$!

sleep 1.5
wmctrl -r '_ii controller' -e "0,${LX},${LY},${LW},${LH}" 2>/dev/null || true
wmctrl -r '_ii controller' -b add,maximized_vert,maximized_horz 2>/dev/null || true

VIS_TITLE='ii-VISUALS'
DISPLAY=:0 XAUTHORITY="$XAUTHORITY" \
  "$PY_BIN" "$ROOT_DIR/window.py" >/tmp/ii-window.log 2>&1 &

echo "waiting for $VIS_TITLE window..."
for i in $(seq 1 30); do
    sleep 1
    if wmctrl -l | grep -q "$VIS_TITLE"; then
        echo "found $VIS_TITLE after ${i}s"
        break
    fi
done

if [ -n "$HG" ]; then
    wmctrl -r "$VIS_TITLE" -e "0,${HX},${HY},${HW},${HH}" 2>/dev/null || true
    wmctrl -r "$VIS_TITLE" -b add,fullscreen 2>/dev/null || true
    echo "visuals on $HDMI at ${HX},${HY} ${HW}x${HH}"
else
    wmctrl -r "$VIS_TITLE" -b add,fullscreen 2>/dev/null || true
    echo "single display: visuals fullscreen on $LAPTOP"
fi

wait "$CTRL_PID"
