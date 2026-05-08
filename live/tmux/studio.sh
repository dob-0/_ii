#!/usr/bin/env bash
set -euo pipefail

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
SESSION=${II_SESSION:-ii}
QROOT=$(printf '%q' "$ROOT")

if ! command -v tmux >/dev/null 2>&1; then
    printf '_ii: missing command: tmux\n' >&2
    exit 1
fi

if tmux has-session -t "$SESSION" 2>/dev/null; then
    exec tmux attach-session -t "$SESSION"
fi

tmux new-session -d -s "$SESSION" -n ansi "cd $QROOT && ./bin/_ii ansi"
tmux split-window -h -t "$SESSION:ansi" "cd $QROOT && ./bin/ii audio"
tmux select-layout -t "$SESSION:ansi" even-horizontal
tmux new-window -t "$SESSION" -n shell "cd $QROOT && exec bash"
tmux new-window -t "$SESSION" -n render "cd $QROOT && printf 'render example: ./bin/ii render out/ritual.mkv 60\n'; exec bash"
tmux select-window -t "$SESSION:ansi"
exec tmux attach-session -t "$SESSION"

