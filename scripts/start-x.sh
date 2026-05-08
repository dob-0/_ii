#!/bin/bash
# _ii X session — controller on LVDS-1, visuals on HDMI-1
export DISPLAY=:0
export XAUTHORITY=/home/dob/.Xauthority

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
           --output "$HDMI"   --auto --right-of "$LAPTOP" 2>/dev/null
else
    xrandr --output "$LAPTOP" --auto --primary 2>/dev/null
fi
sleep 0.3

_geom() {
    xrandr --query | awk -v d="$1" '
        $1==d && / connected /{
            match($0,/[0-9]+x[0-9]+\+[0-9]+\+[0-9]+/)
            print substr($0,RSTART,RLENGTH)
        }'
}
LG=$(_geom "$LAPTOP"); HG=$(_geom "$HDMI")
LW=$(echo "${LG:-1366x768+0+0}" | cut -dx -f1)
LH=$(echo "${LG:-1366x768+0+0}" | cut -d+ -f1 | cut -dx -f2)
LX=$(echo "${LG:-1366x768+0+0}" | cut -d+ -f2)
LY=$(echo "${LG:-1366x768+0+0}" | cut -d+ -f3)
HW=$(echo "${HG:-1920x1080+1366+0}" | cut -dx -f1)
HH=$(echo "${HG:-1920x1080+1366+0}" | cut -d+ -f1 | cut -dx -f2)
HX=$(echo "${HG:-1920x1080+1366+0}" | cut -d+ -f2)
HY=$(echo "${HG:-1920x1080+1366+0}" | cut -d+ -f3)

kitty \
  --title '_ii controller' \
  --override background=black \
  --override foreground=white \
  --override font_size=10.0 \
  -e /usr/bin/python3 /home/dob/_ii/_ii.py &
CTRL_PID=$!

sleep 1.5
wmctrl -r '_ii controller' -e "0,${LX},${LY},${LW},${LH}" 2>/dev/null || true
wmctrl -r '_ii controller' -b add,maximized_vert,maximized_horz 2>/dev/null || true

VIS_TITLE='ii-VISUALS'
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

wait $CTRL_PID
