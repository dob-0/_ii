# ii

Terminal-first visual system for club use. This is **ii v0.1**, built for MOCT 7 (Hayfilm Studio, Yerevan 2026). v0.2 will be the same engine without event-specific branding.

This repo is built for live VJ performance: fast startup, hot reload, simple control flow, audio-reactive visuals, camera interaction, and a colder white / blue / cyan / magenta palette direction.

The controller is a live deck, not a settings page. It shows output state, mic energy, camera motion/brightness, automation nodes, and manual overrides in one place.

## Start

Main entrypoint:

```bash
python3 ii.py
```

What happens:

1. `ii.py` opens the controller UI.
2. It tries to autostart the visuals window through `window.py`.
3. `window.py` spawns the visuals terminal and hands off to `visuals.py`.

Manual alternatives:

```bash
python3 window.py
python3 visuals.py
```

## Optional Sensor Inputs

Install these only if you want mic and camera nodes:

```bash
pip install numpy sounddevice opencv-python
```

Available first-hand nodes in `nodes.py` via `node_lib.py`:

- `AudioLevel()`
- `AudioPeak()`
- `AudioTrigger()`
- `CameraMotion(source='/dev/video4')`
- `CameraBrightness(source='/dev/video4')`
- `CameraPresence(source='/dev/video4')`
- `CameraMotion(source='/dev/video2')`
- `CameraBrightness(source='/dev/video2')`
- `CameraPresence(source='/dev/video2')`
- `ArtNetOut(channel, node, host='2.0.0.10', universe=0, enabled=True)`
- `ArtNetRGB(start_channel, red, green, blue, host='2.0.0.10', universe=0, enabled=True)`

Example:

```python
from node_lib import *

GRAPH = [
    Out('glitch_intensity', Scale(CameraMotion(source='/dev/video4', gain=7.0), out_min=0.05, out_max=1.0)),
    BoolOut('flash_active', AudioTrigger(threshold=0.55, cooldown=8, gain=10.0)),
    BoolOut('layer_b_enabled', AudioLevel(gain=7.0), threshold=0.28),
    # ArtNetOut(1, AudioLevel(gain=8.0), host='2.0.0.10', universe=0, enabled=True),
]
```

## Controller Keys

| Key | Action |
| --- | --- |
| `Tab` / `V` | Jump between global controls and node controls |
| `0`-`9` | Jump to mode by number |
| `[` / `]` | Previous / next mode |
| `Up` / `Down` | Move selection |
| `Left` / `Right` | Adjust selected control |
| `X` | Toggle Layer B compositing |
| `C` | Clear selected override |
| `M` | Lock / release current mode |
| `P` | Next palette |
| `T` | Tap BPM |
| `S` | Toggle BPM sync |
| `Space` | Toggle flash text |
| `Enter` | Edit flash text |
| `A` | Toggle auto-cycle |
| `B` | Blackout |
| `F1`-`F10` | Presets |
| `!` | Panic reset + blackout |
| `Q` | Quit |

## Palettes

Default palette direction is now cleaner and more club-minimal:

| Name | Roles |
| --- | --- |
| `MONO` | white / dim / blue |
| `ICE` | cyan / blue / white |
| `STROBE` | white / cyan / dim |
| `SODIUM` | yellow / white / dim |
| `ULTRA` | magenta / blue / white |
| `NIGHTSHIFT` | blue / magenta / cyan |

Manual color overrides are still available in the controller.

## Modes

There are 19 visual modes:

| # | Name |
| --- | --- |
| 0 | `RAIN` |
| 1 | `WAVE` |
| 2 | `GLITCH` |
| 3 | `STROBE` |
| 4 | `LOGO` |
| 5 | `PULSE` |
| 6 | `TEXT` |
| 7 | `TUNNEL` |
| 8 | `PLASMA` |
| 9 | `VORTEX` |
| 10 | `GRID` |
| 11 | `PARTICLES` |
| 12 | `SCANNER` |
| 13 | `STORM` |
| 14 | `CUBE` |
| 15 | `SHOCKWAVE` |
| 16 | `NOISE` |
| 17 | `LIQUID` |
| 18 | `POSTER` |

`LIQUID` is the poster-inspired MOCT look: white type over blue/magenta fluid forms, with mic and camera energy changing the movement.
`POSTER` is the harder MOCT flyer system: stacked oversized type, stage labels, arcs, crosses, block artifacts, and scrolling metadata.

## Layer System

The renderer supports A/B mode compositing.

- `MODE` = layer A source
- `MODE B` = layer B source
- `LAYER B` = enable layer B
- blend rule = non-space cells from B overwrite A

This is intentionally simple and performance-friendly for live play.

## Window Launcher

`window.py` is the stage launcher.

It is responsible for:

- choosing a terminal backend
- assigning a stable window title
- requesting fullscreen
- optional monitor / geometry placement
- running `visuals.py`

Relevant `config.json` keys:

- `autostart_visuals`
- `visuals_launch_cmd`
- `visuals_terminal`
- `visuals_fullscreen`
- `visuals_window_title`
- `visuals_force_x11`
- `visuals_monitor`
- `visuals_geometry`

`visuals_monitor` can be an exact monitor name from `xrandr --query`; this setup currently targets `HDMI-A-1`. `auto-second` is also supported. On KDE Wayland, `window.py` installs a temporary KWin placement rule for `MOCT7-VISUALS`; on X11 it falls back to `wmctrl`.

## Hot Reload

- edit `visuals.py` -> visuals restart in place
- edit `nodes.py` -> controller reloads the graph
- edit mode files in `modes/` -> visuals restart in place
- edit `window.py` -> restart `ii.py`

## Structure

```text
mct7/
├── architecture.py
├── window.py
├── visuals.py
├── ii.py
├── node_lib.py
├── nodes.py
├── modes/
├── config.json
├── control.json
├── status.json
├── README.md
├── CLAUDE.md
└── innux/
```

## Runtime Contract

- `ii.py` writes `control.json`
- `visuals.py` reads `control.json`
- `visuals.py` writes `status.json`
- `ii.py` reads `status.json`
- `architecture.py` is the shared source of truth for paths, defaults, mode discovery, and atomic JSON writes
- `nodes.py` is the live patch: mic, cameras, visuals, and optional Art-Net outputs are all evaluated from one graph

No sockets. No server process. Keep it direct.

Exception: Art-Net output nodes use UDP directly when enabled, because lighting control needs the network.
