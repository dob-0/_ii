# _ii

`_ii` is a live visual and projection-control system. It runs a controller on
the laptop screen, sends visuals to a projector or second display, and exposes a
browser portal for mapping, live controls, media, and display management.

The usual live setup is:

- Debian machine connected to the projector by HDMI.
- Laptop display used for the controller.
- Phone, tablet, or laptop on the same network opened to the web portal.
- Optional SSH session for maintenance.

## Quick Operator Start

Use this when the machine is already installed and you just need to run a show.

1. Connect projector or LED processor to HDMI.
2. Connect the control device to the same network as the `_ii` machine.
3. SSH into the machine:

   ```bash
   ssh dob@192.168.88.136
   ```

4. Start the full X11 show layout:

   ```bash
   ii xstart
   ```

5. Open the web portal from any browser on the same network:

   ```text
   http://192.168.88.136:7777
   ```

6. In the portal, open `OUTPUTS` and build the stage output plan:

   - choose the laptop panel as `CONTROLLER SCREEN`
   - choose HDMI/projector as `PROJECTOR SCREEN`
   - choose the mapping preset
   - click `PREVIEW PLAN`
   - click `APPLY TO STAGE`

7. Open `CTRL` for live performance controls.

8. If the projector is black or windows land on the wrong screen:

   ```bash
   ii restart x
   ```

## Web Portal

Run the portal on the `_ii` machine:

```bash
python3 map_server.py
```

Open it from the machine itself:

```text
http://localhost:7777
```

Open it from another device on the network:

```text
http://192.168.88.136:7777
```

Portal tabs:

| Tab | Use |
| --- | --- |
| `MAP` | Create and edit projection surfaces. Drag corners to warp zones. |
| `ZONES` | Quickly enable/disable zones and assign modes per surface. |
| `CTRL` | Live VJ controls: mode, palette, BPM, layer B, flash, blackout. |
| `MEDIA` | Upload video/image files and play video through the output stack. |
| `OUTPUTS` | Build and apply the stage output plan: controller screen, projector screen, mapping preset. |
| `HELP` | Shows portal URL, SSH command, IP addresses, display state, rescue commands, and one-click restart buttons (`VIS`, `CTRL`, `WEB`, `X`, `ALL`). |

The portal writes to `control.json`, mapping files in `mappings/`, and runtime
state files. These runtime files are intentionally ignored by git.

## Display And Connection Guide

Recommended live display layout:

| Screen | Purpose | Typical connector |
| --- | --- | --- |
| Laptop panel | `_ii.py` controller | built-in `LVDS-1` or `eDP-1` |
| Projector | `ii-VISUALS` terminal visuals | `HDMI-1`, `HDMI-A-1`, or similar |

The project now uses `visuals_monitor: "auto-second"` in `config.json`, so it
prefers the non-primary connected display instead of depending on a single HDMI
name.

Useful display checks:

```bash
DISPLAY=:0 xrandr --query
DISPLAY=:0 wmctrl -lG
ii status
```

The `OUTPUTS` tab follows the same practical idea as professional mapper tools:
choose a screen, choose which content goes to it, choose a mapping preset, then
apply deliberately. It avoids one-click mirror/projector-only changes during a
show because those can hide the controller or strand the visuals on the wrong
display.

Projection mapping workflow (recommended):

1. Open `OUTPUTS`.
2. Pick controller screen, projector screen, and mapping preset.
3. Click `PREVIEW PLAN`.
4. Click `OPEN MAP EDITOR` to inspect or edit the selected mapping geometry.
5. In `MAP`, drag corners for each surface and save.
6. In `ZONES`, set mode per surface if needed.
7. Return to `OUTPUTS` and click `APPLY TO STAGE`.

If the projector is connected but black:

1. Check `OUTPUTS` in the web portal.
2. Choose the laptop panel for `CONTROLLER SCREEN`.
3. Choose the HDMI output for `PROJECTOR SCREEN`.
4. Choose the correct mapping preset.
5. Click `PREVIEW PLAN`, then `APPLY TO STAGE`.
6. If still wrong, restart X mode:

   ```bash
   ii restart x
   ```

## Remote Management

The `ii` command at `~/bin/ii` manages the live engine.

```bash
ii start                   # start tmux controller + TTY visuals
ii stop                    # stop visuals and controller
ii status                  # show running pieces
ii attach                  # attach to tmux controller
ii logs vis                # follow terminal visual logs
ii logs web                # follow portal logs
ii logs x                  # follow X11 startup logs
ii update                  # git pull latest code
ii watch 10                # auto-pull every 10 seconds
ii xstart                  # start laptop-controller/projector-visuals X11 mode
ii xstop                   # stop X11 mode and return to TTY visuals
ii restart x               # restart the X11 show layout
ii restart vis             # restart only visuals
ii restart ctrl            # restart only controller
ii restart web             # restart only web portal
```

Attach to the controller directly:

```bash
ssh dob@192.168.88.136 -t "tmux attach -t ii"
```

## Normal Show Workflow

Before doors:

1. Power the projector or processor first.
2. Boot the `_ii` machine.
3. Start X mode with `ii xstart`.
4. Open `http://192.168.88.136:7777`.
5. Use `OUTPUTS` to apply the controller/projector/mapping stage plan.
6. Use `MAP` or `ZONES` to confirm the projection surfaces.
7. Use `CTRL` to pick a starting mode and palette.
8. Keep `BLACKOUT` available in the CTRL tab for emergencies.

During the show:

- Use `CTRL` for mode, palette, BPM, layer, flash, and blackout.
- Use `ZONES` if each mapped surface should show a different mode.
- Use `MEDIA` only when you intentionally want video playback.
- Use `HELP` restart buttons first (`VIS`, `CTRL`, `WEB`, `X`) before considering a full machine reboot.

After the show:

```bash
ii stop
```

## Local Development

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

## Installation Notes

Core terminal visuals use the Python standard library. Optional outputs and
inputs need packages:

```bash
pip install pygame numpy sounddevice opencv-python python-osc
```

Useful system tools:

```bash
sudo apt install wmctrl x11-xserver-utils tmux kitty openbox unclutter mpv
```

Install system services from the repo:

```bash
sudo ./install-services.sh
```

Services:

| Service | Role |
| --- | --- |
| `ii-visuals.service` | `visuals.py` on TTY1 |
| `ii-web.service` | `map_server.py` on port `7777` |
| `ii-ctrl.service` | `_ii.py` deck in tmux session `ii` |
| `ii-boot.service` | optional wrapper around `~/bin/ii start` |

Service commands:

```bash
sudo systemctl restart ii-visuals
sudo systemctl restart ii-web
sudo systemctl restart ii-ctrl
sudo journalctl -fu ii-visuals
```

## Runtime Pieces

| File | Role |
| --- | --- |
| `_ii.py` | curses controller, node graph evaluator, manual overrides |
| `visuals.py` | ANSI terminal visual renderer |
| `window.py` | launches and places the visuals terminal window |
| `map_server.py` | web portal for mapping, controls, media, outputs, help |
| `output.py` | pygame output with fullscreen/windowed modes |
| `fb_mapper.py` | direct framebuffer renderer |
| `audio.py` | microphone level, peak, and BPM writer |
| `osc_server.py` | OSC receiver writing to `control.json` |
| `nodes.py` | live automation graph, hot-reloaded by `_ii.py` |
| `node_lib.py` | signal nodes, camera/audio inputs, Art-Net outputs |
| `modes/` | visual modes |
| `mappings/` | projection surface layouts |
| `media/` | uploaded media files, ignored by git |
| `live/` | headless GLSL, ANSI, SuperCollider, ffmpeg, tmux helpers |

## Control Flow

`_ii.py` evaluates `nodes.py`, merges node output, MIDI state, OSC/audio writes,
and manual overrides, then writes `control.json`.

Renderers read `control.json`:

- `visuals.py` renders terminal visuals and writes `status.json`.
- `output.py` renders through pygame and writes `status.json`.
- `fb_mapper.py` renders directly to `/dev/fb0`.
- `map_server.py` edits mapping files and updates live controls.

`status.json` feeds liveness and FPS back into the controller and portal.

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

`MAPTST` is the safest mode for checking projection surfaces.

## Palettes And Symbols

Palettes: `STEEL`, `ACID`, `VOID`, `NEON`, `ULTRA`, `DEEP`, `BLOOD`, `EMBER`.

Symbol sets: `BLOCK`, `ASCII`, `DIGIT`, `GRID`, `SHAPES`, `MATH`.

Primary, secondary, and accent colors can follow the active palette or be
overridden manually from the controller.

## Mapping

Bundled mapping presets:

- `mappings/default.json` full screen
- `mappings/split2.json` two vertical zones
- `mappings/quad.json` four zones
- `mappings/split3.json` three vertical zones

Use `MAP` in the portal for geometry. Use `ZONES` for fast mode assignment and
surface enable/disable during a show.

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

`osc_server.py` listens on `0.0.0.0:7000` by default.

Native addresses:

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

## Troubleshooting

Projector black, controller visible:

```bash
ii status
DISPLAY=:0 wmctrl -lG
ii restart x
```

Portal does not open:

```bash
ii status
ii restart web
curl http://localhost:7777
```

Wrong display names:

```bash
DISPLAY=:0 xrandr --query
```

Visuals are running but frozen:

```bash
ii restart x
```

Need a clean blank screen:

- Press `B` in the controller.
- Or click `BLACKOUT` in the portal `CTRL` tab.

## Live Update Workflow

Edit on laptop, push, then pull on the Debian machine:

```bash
# laptop
scripts/git-sync.sh "describe the change"

# debian
ii update
```

During development or rehearsal:

```bash
ii watch 10
```

## Git Sync

Use the repository sync script after intentional changes:

```bash
scripts/git-sync.sh "short commit message"
```

The script stages repo changes, commits, pushes the current branch, and prints
the final git status. Runtime files such as `control.json`, `status.json`,
`display_assign.json`, `cues.json`, media uploads, temp files, and Python caches
should stay ignored by `.gitignore`.

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
├── media/
├── live/
├── innux/
├── docs/
├── config.json
└── README.md
```
