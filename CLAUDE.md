# ii — AI Context

**_ii** is a live VJ terminal visual engine. This repo is **_ii v0.1**, built for MOCT 7 (7th Anniversary, Hayfilm Studio, Yerevan 2026). v0.2 will be the same engine stripped of MOCT-specific branding — a clean generic build. The user runs this during live performances and edits it in real time via prompts.

---

## Project Purpose

Two-terminal VJ system:
- `visuals.py` — fullscreen ASCII compositor/runtime in Kitty terminal
- `modes/*.py` — individual visual modes, discovered dynamically by `architecture.py`
- `_ii.py` — live performance deck/controller in a second terminal
- `nodes.py` — live patch graph for BPM, mic, cameras, visuals, and optional Art-Net outputs
- `window.py` — stage-aware launcher: spawns visuals in a dedicated Kitty window, optionally placed on second monitor via KWin script
- IPC via `control.json` (controller→visuals) and `status.json` (visuals→controller)

The user describes changes in natural language. Edit `modes/*.py` for visuals, `nodes.py` for live patching, `_ii.py` for controller UI, and `node_lib.py` for new node types. The hot-reload system restarts visuals when `visuals.py` or a mode file changes; `_ii.py` hot-reloads `nodes.py`.

---

## Architecture

### visuals.py

Single class `Engine` that discovers mode classes from `modes/`. Key design:

```
Engine.__init__()      — loads config, initializes per-mode state
Engine.run()           — main loop: load_ctrl() → apply params → render mode → write status
Engine.modes[]         — discovered Mode objects, indexed by self.mode
Engine._bar()          — status line at bottom row (always rendered)
```

**Module-level utilities:**
- `rot3d(points, rx, ry, rz)` — 3D rotation for CUBE mode
- `bresenham(x0,y0,x1,y1)` — integer line drawing for CUBE and STORM
- `load_cfg()`, `load_ctrl()`, `write_status()` — file I/O
- `mv(x, y)` — returns ANSI cursor-move escape string

**ANSI output strategy:** All modes build a `list[str]` and emit one `sys.stdout.write(''.join(out))` per frame. Never print cell by cell in hot loops.

**Palette system:**
```python
PALETTES = [  # 6 palettes
    {'name': '...', 'p': 'color_key', 's': 'color_key', 'a': 'color_key'}
]
# p = primary, s = secondary, a = accent
# Access via self.pal (property), colors via C[self.pal['p']] etc.
```

**Color dict `C`:** keys are `'red','green','white','dim','cyan','yellow','magenta','red_d','green_d','blue'`

### ii.py

Curses TUI. Single class `NodeEngine`. Writes `control.json` every loop iteration. Reads `status.json` for live feedback display.

**control.json schema:**
```json
{
  "mode": 0-18,
  "mode_b": 0-18,
  "layer_b_enabled": bool,
  "mode_lock": bool,
  "auto_cycle": bool,
  "blackout": bool,
  "flash_active": bool,
  "bpm_sync": bool,
  "palette": 0-5,
  "primary_color": -1 to 9,
  "secondary_color": -1 to 9,
  "accent_color": -1 to 9,
  "flash_text": "string",
  "frame_delay": 0.01-0.20,
  "strobe_speed": 1-10,
  "glitch_intensity": 0.05-1.0,
  "wave_amplitude": 0.10-0.50,
  "rain_density": 0.10-1.0,
  "mode_cycle_frames": 50-600,
  "bpm": 40-240,
  "audio_level": 0.0-1.0,
  "audio_peak": 0.0-1.0,
  "camera4_motion": 0.0-1.0,
  "camera4_brightness": 0.0-1.0,
  "camera4_online": bool,
  "camera2_motion": 0.0-1.0,
  "camera2_brightness": 0.0-1.0,
  "camera2_online": bool,
  "sym_set": 0-5,
  "layer_b_alpha": 0.0-1.0
}
```

**Layer B compositing:** `layer_b_enabled` activates A/B mode blending. `mode` = layer A source, `mode_b` = layer B source. Non-space cells from B overwrite A. Toggle with `X` key.

---

## 19 Modes

```
0  RAIN       — columnar falling chars with phosphor trail
1  WAVE       — 3 overlapping sine waves (grid buffer approach)
2  GLITCH     — random scanline corruption + occasional logo flash
3  STROBE     — full-fill / blank alternation, BPM-syncable
4  LOGO       — MOCT 7 big box-drawing text centered on noise bg
5  PULSE      — BPM-synced expanding ring (polar distance per cell)
6  TEXT       — flash_text in scrolling bands + centered big text
7  TUNNEL     — inverse radial projection, precomputed polar cache
8  PLASMA     — 4-sine superposition, normalized, char+color by value
9  VORTEX     — 3-arm spiral with time-varying twist, precomputed polar
10 GRID       — synthwave perspective grid (horizontal + vertical lines)
11 PARTICLES  — particle fountain from center, gravity+drag physics
12 SCANNER    — rotating radar beam with trail, static rings overlay
13 STORM      — recursive midpoint-displacement lightning + flash
14 CUBE       — rotating 3D wireframe cube via rot3d + bresenham
15 SHOCKWAVE  — multiple expanding ring objects, BPM-syncable spawn
16 NOISE      — smooth multi-sine noise field, char+color by value
17 LIQUID     — MOCT poster look: white block-type over blue/magenta fluid forms, mic+camera reactive
18 POSTER     — hard flyer system: stacked oversized type, arcs, stage labels, block glitch background
```

---

## Per-mode State

Modes that maintain state between frames:

- `self.col_y` (dict) — column head positions for RAIN (`Rain.__init__`)
- `self.particles` (list of dicts) — active particles for PARTICLES (`Particles.__init__`)
- `self.rings` (list of dicts) — active rings for SHOCKWAVE (`Shockwave.__init__`)
- `self.storm_pts` (list of tuples) — current lightning branch points for STORM (`Storm.__init__`)
- `self.storm_age` (int) — frames until next lightning regeneration
- `self.cache` / `self.cache_sz` — precomputed polar coord grids for TUNNEL and VORTEX, rebuilt on resize

---

## Performance Notes

- Full-grid modes (TUNNEL, PLASMA, VORTEX, NOISE, WAVE, PULSE): render all `w × (h-1)` cells. At 120×50 this is ~6000 cells. Use list-join output, never per-cell writes.
- TUNNEL and VORTEX: `_precompute_polar()` caches `(dist, angle)` per cell and rebuilds only on terminal resize. This avoids ~6000 atan2+sqrt calls per frame.
- Sparse modes (CUBE, SCANNER, STORM, SHOCKWAVE, PARTICLES): touch only 200–2000 cells per frame. Much faster.
- `frame_delay` default is 0.05s (20fps). User can lower it for faster modes or raise it if a mode is computationally heavy.
- `syms` is the character list passed into `render()`. Use `random.choice(syms)` to pick a random symbol.

---

## Hot Reload

Every 20 frames, `Engine._hot_reload_if_needed()` snapshots mtimes of `visuals.py` and all `modes/*.py`. If any file changed, it calls `os.execv` to replace the process in-place. Terminal stays open, cursor is restored, new process starts fresh. Per-mode state is lost (acceptable — modes reinitialize cleanly).

---

## How to Add a New Mode

1. Create `modes/mymode.py` with a class subclassing `Mode`:

   ```python
   from modes.base import C, Mode

   class MyMode(Mode):
       NAME = 'MYMODE'
       ORDER = 19  # controls sort order in the mode list

       def render(self, buf, w, h, t, frame, cfg, pal, syms):
           p = pal
           # write to buf[y][x] = (char, color_str) or None
   ```

2. Save → `architecture.discover_modes()` picks it up automatically on next hot-reload.
3. Optionally add it to `nodes.py` GRAPH `Seq([...])` to include it in auto-cycle.

Modes with internal state add `__init__`:

```python
def __init__(self):
    self.mystate = []
```

Accessing palette: `p = pal` then `C[p['p']]`, `C[p['s']]`, `C[p['a']]`
Accessing control values: `cfg.get('flash_text', '')`, `cfg.get('bpm', 140)`
Drawing a cell: `self.put(buf, x, y, char, color_str, w, h)`
Clearing the buffer: `self.clear(buf, w, h)`

---

## innux/ Subdirectory

Earlier prototype scripts, standalone tools:
- `visuals.py` — simple scrolling glitch (line-by-line, no cursor control)
- `matrix.sh` — bash script, random char placement
- `glitch.js` — node.js, random colored lines
- `black.py` — blackout utility (useful between sets)

These are not part of the main engine. Don't modify them unless asked.

---

## User Workflow

User describes a change in natural language → you edit `visuals.py` → save → engine hot-reloads within ~1s → user sees the result live. This is a real-time live-coding VJ session. Keep edits focused and surgical. The user may ask for:
- New visual modes
- Tweaks to existing mode math/behavior
- New parameters or palette colors
- Performance fixes (if a mode runs slowly)
- New controller features
