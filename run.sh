#!/usr/bin/env bash
# ii — start visuals on projector (TTY1) + control deck
# Usage: run on the Debian machine console, or via SSH
set -e

cd "$(dirname "$0")"

# If already on TTY1 (physical console), run visuals directly
if [ "$(tty)" = "/dev/tty1" ]; then
    exec python3 visuals.py
fi

# From SSH: launch visuals on TTY1 via openvt, keep ii here
echo "[ii] starting visuals on TTY1..."
openvt -c 1 -s -- python3 "$(pwd)/visuals.py" &
sleep 0.5
echo "[ii] starting controller..."
exec python3 _ii.py
