# _ii

Terminal-first VJ and projection toolkit for live club use. `_ii` combines a
curses control deck, ANSI terminal visuals, pygame/KMS output, projection
mapping, audio/camera automation, MIDI/OSC input, and optional Art-Net output.

The repo grew out of the MOCT 7 show system, but the current project name and
runtime entrypoint are `_ii`.

## Quick Start

Controller plus autostarted terminal visuals:

```bash
python3 _ii.py
```

Manual terminal visuals:

```bash
python3 window.py
python3 visuals.py
```

Pygame fullscreen/windowed output:

```bash
python3 output.py --display 0
python3 output.py --windowed 1280 720
python3 output.py --map mappings/quad.json --vw 128 --vh 72
```

Projection mapper and browser control panel:

```bash
python3 map_server.py
# open http://localhost:7777
```

Framebuffer mapper for direct `/dev/fb0` output:

```bash
python3 fb_mapper.py --map mappings/split3.json
```

Audio and OSC helpers:

```bash
python3 audio.py --list
python3 audio.py --sensitivity 1.5
python3 osc_server.py --port 7000
```

Commit and push all repo changes:

```bash
scripts/git-sync.sh "describe the change"
```

## Install Notes

Core terminal visuals use the Python standard library. Extra outputs and inputs
need optional packages:

```bash
pip install pygame numpy sounddevice opencv-python python-osc
```

Useful system tools for stage placement:

```bash
sudo apt install wmctrl x11-xserver-utils
```

For `fb_mapper.py`, the user running it needs access to `/dev/fb0`, usually via
the `video` group or root on a console TTY.

## Runtime Pieces

| File | Role |
| --- | --- |
| `_ii.py` | live curses deck, node graph evaluator, manual overrides |
| `visuals.py` | ANSI terminal renderer with A/B layers and zone mapping |
| `window.py` | launches and places the terminal visuals window |
| `output.py` | pygame output with fullscreen/windowed modes and quad mapping |
| `map_server.py` | browser mapping editor plus web control panel on port `7777` |
| `fb_mapper.py` | direct framebuffer renderer for projector/KMS setups |
| `audio.py` | microphone level, peak, and BPM writer for `control.json` |
| `osc_server.py` | OSC receiver mapping messages into `control.json` |
| `nodes.py` | live automation graph; `_ii.py` hot-reloads it |
| `node_lib.py` | signal nodes, camera/audio inputs, Art-Net outputs |
| `modes/` | visual mode implementations |
| `mappings/` | projection and zone layouts |
| `live/` | headless GLSL, ANSI, SuperCollider, ffmpeg, and tmux tools |

## Control Flow

`_ii.py` evaluates `nodes.py`, merges node output, MIDI state, OSC/audio writes,
and manual overrides, then writes `control.json`.

Renderers read `control.json`:

- `visuals.py` renders ANSI terminal output and writes `status.json`.
- `output.py` renders through pygame and writes `status.json`.
- `fb_mapper.py` renders directly to `/dev/fb0`.
- `map_server.py` edits mapping files and can update live controls.

`status.json` feeds liveness and FPS back into the deck/control panel.

## Git Sync

Use `scripts/git-sync.sh` after edits that should land on GitHub:

```bash
scripts/git-sync.sh "short commit message"
```

The script stages all repo changes with `git add -A`, commits them, pushes the
current branch, then prints the latest commit and final branch status. Runtime
files such as `control.json`, `status.json`, temp files, and Python caches stay
ignored by `.gitignore`.

## Controller Keys

| Key | Action |
| --- | --- |
| `0`-`9` | jump to mode by number |
| `[` / `]` | previous / next mode |
| `Up` / `Down` | move selected control |
| `Left` / `Right` | adjust selected control |
| `Tab` / `V` | jump between main controls and node controls |
| `P` | next palette |
| `F` | next symbol set |
| `T` | tap BPM |
| `S` | toggle BPM sync |
| `X` | toggle layer B |
| `M` | lock / release current mode |
| `G` | cycle projection mapping |
| `A` | toggle auto-cycle |
| `B` | blackout |
| `Space` | toggle flash text |
| `Enter` | edit flash text |
| `C` | clear selected override |
| `W` | toggle visuals fullscreen |
| `,` / `.` | previous / next cue |
| `Z` | store current cue |
| `F1`-`F10` | performance presets |
| `!` | panic reset + blackout |
| `Q` | quit |

## Modes

Current mode order:

| # | Mode |
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
| 19 | `MAPTST` |

`LIQUID` and `POSTER` keep the MOCT visual language. `MAPTST` is for checking
projection surfaces and zone layout.

## Palettes And Symbols

Palettes:

- `STEEL`
- `ACID`
- `VOID`
- `NEON`
- `ULTRA`
- `DEEP`
- `BLOOD`
- `EMBER`

Symbol sets:

- `BLOCK`
- `ASCII`
- `DIGIT`
- `GRID`
- `SHAPES`
- `MATH`

Primary, secondary, and accent colors can follow the active palette or be
overridden manually from the controller.

## Mapping

Bundled mapping presets:

- `mappings/default.json` full screen
- `mappings/split2.json` two vertical zones
- `mappings/quad.json` four zones
- `mappings/split3.json` three cube-style vertical zones

`G` cycles mappings from the deck. `map_server.py` edits surface mappings in a
browser and exposes a second control surface for mode, layer, palette, BPM,
flash, and blackout.

## Automation Graph

Edit `nodes.py` during a session. `_ii.py` hot-reloads it automatically.

Available node families include:

- clocks and generators: `Const`, `LFO`, `BeatLFO`, `Seq`, `Ramp`, `Noise`
- shaping: `Math`, `Clamp`, `Mix`, `Select`, `Hold`, `Scale`, `Gate`
- triggers: `BeatPulse`, `AudioTrigger`
- inputs: `AudioLevel`, `AudioPeak`, `CameraMotion`, `CameraBrightness`, `CameraPresence`
- outputs: `Out`, `IntOut`, `BoolOut`, `ArtNetOut`, `ArtNetRGB`

Example:

```python
from node_lib import *

MIC = AudioLevel(gain=9.0, smoothing=0.78)
CAM = CameraMotion(source='/dev/video4', fps=15, gain=7.0)

GRAPH = [
    Out('bpm', Const(140)),
    IntOut('mode', Seq([17, 18, 7, 8, 3, 9], beats=8)),
    Out('glitch_intensity', Scale(CAM, out_min=0.08, out_max=1.0)),
    BoolOut('flash_active', AudioTrigger(threshold=0.55, cooldown=8, gain=10.0)),
    BoolOut('layer_b_enabled', MIC, threshold=0.28),
]
```

## OSC

`osc_server.py` listens on `0.0.0.0:7000` by default. Native addresses include:

- `/_ii/mode`
- `/_ii/mode_b`
- `/_ii/palette`
- `/_ii/bpm`
- `/_ii/blackout`
- `/_ii/master_dim`
- `/_ii/glitch`
- `/_ii/rain`
- `/_ii/wave`
- `/_ii/strobe`
- `/_ii/layer_b`
- `/_ii/layer_b_alpha`
- `/_ii/flash_text`
- `/_ii/flash`
- `/_ii/auto_cycle`

Create `osc_map.json` in the project root to add or override address mappings.

## Hot Reload

- edit `nodes.py` and `_ii.py` reloads the graph
- edit `visuals.py` or files in `modes/` and terminal visuals restart in place
- edit mapping JSON and `output.py` / `fb_mapper.py` reload the map on a timer
- edit `window.py` and restart `_ii.py`

## Repository Layout

```text
_ii/
├── _ii.py
├── visuals.py
├── output.py
├── window.py
├── map_server.py
├── fb_mapper.py
├── audio.py
├── osc_server.py
├── architecture.py
├── node_lib.py
├── nodes.py
├── modes/
├── mappings/
├── live/
├── innux/
├── docs/
├── config.json
└── README.md
```
