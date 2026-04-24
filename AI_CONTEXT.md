# MOCT 7 — Project Context for AI Assistants

Paste this file into any AI chat to get full project context instantly.

---

## What This Is

A live VJ (video jockey) terminal visual engine built in Python for a techno music event — MOCT 7th Anniversary at Hayfilm Studio, Yerevan 2026. It runs in a Kitty GPU-accelerated terminal and outputs pure ASCII/Unicode art using ANSI escape codes. No libraries beyond Python stdlib.

Two terminals run simultaneously:
- **Fullscreen terminal** → `python3 visuals.py` (the visuals, fullscreen Kitty)
- **Control terminal** → `python3 ii.py` (live parameter control, curses TUI)

The user describes changes in natural language and the AI edits `visuals.py`. A hot-reload system detects file saves and restarts the engine automatically in ~1 second — the performance never stops.

---

## File Map

```
mct7/
├── visuals.py      — MAIN FILE. Visual engine. 17 modes. Edit this for visual changes.
├── ii.py   — Curses TUI controller. Edit for new controls/UI.
├── config.json     — Startup defaults (symbols, frame_delay, etc.)
├── control.json    — Live IPC: controller writes this, visuals reads it every frame
├── status.json     — Live IPC: visuals writes this (fps, frame, mode), controller reads it
├── README.md       — Human documentation
├── CLAUDE.md       — Claude Code specific context
├── AI_CONTEXT.md   — This file (universal AI context)
└── innux/          — Old prototypes. Ignore unless user asks.
```

---

## visuals.py — Architecture

### Core structure

```python
class Engine:
    def __init__(self):
        # loads config.json
        # initializes per-mode state (self.rain_y, self.particles, etc.)
        # builds self.mode_fns = [self._rain, self._wave, ...]  # 17 methods
        # builds self.mode_labels = ['RAIN', 'WAVE', ...]

    def run(self):
        # main loop every frame:
        # 1. load control.json → apply params
        # 2. check file mtime → hot-reload if changed
        # 3. write status.json every 10 frames
        # 4. handle blackout
        # 5. select mode
        # 6. call self.mode_fns[self.mode]()
        # 7. draw flash overlay if active
        # 8. draw status bar
        # 9. sys.stdout.flush()
        # 10. sleep(frame_delay)
```

### Key properties and helpers

```python
self.w, self.h      # terminal width and height (updated every frame)
self.frame          # frame counter (int, increments every frame)
self.ctrl           # dict loaded from control.json each frame
self.cfg            # dict loaded from config.json at startup, overridden by ctrl each frame
self.syms           # list of symbols e.g. ['█','▓','▒','░','▚','◈','7','M','O','C','T']
self.pal            # property → current palette dict {'name','p','s','a'}

self._s()           # returns random symbol from self.syms
self._put(x,y,ch,col)  # writes one char at terminal position x,y
self._beat_phase()  # float 0..1 position within current BPM beat (wall-clock)
self._bar(label)    # draws status bar at bottom row
self._precompute_polar()  # caches (dist, angle) per cell for TUNNEL and VORTEX
mv(x, y)            # returns ANSI cursor-move escape string '\033[{y+1};{x+1}H'
```

### ANSI color constants

```python
C = {
    'red','green','white','dim','cyan','yellow','magenta','red_d','green_d','blue'
}
# Usage: C['red'] → '\033[1;31m'
# Always append RESET = '\033[0m' after colored text
```

### Palette system

```python
PALETTES = [
    {'name': 'INDUSTRIAL', 'p': 'red',     's': 'green',   'a': 'white'},
    {'name': 'ACID',       'p': 'cyan',    's': 'yellow',  'a': 'white'},
    {'name': 'VOID',       'p': 'white',   's': 'dim',     'a': 'red'},
    {'name': 'BLOOD',      'p': 'red',     's': 'red_d',   'a': 'white'},
    {'name': 'MATRIX',     'p': 'green',   's': 'green_d', 'a': 'white'},
    {'name': 'NEON',       'p': 'magenta', 's': 'cyan',    'a': 'white'},
]
# p = primary color, s = secondary, a = accent (brightest)
# Use: p = self.pal; col = C[p['p']]
```

### Module-level utilities

```python
rot3d(points, rx, ry, rz)     # 3D rotation, returns list of (x,y,z)
bresenham(x0, y0, x1, y1)     # integer line drawing, returns list of (x,y)
```

---

## 17 Visual Modes

```
0  RAIN       self.rain_y dict — columnar falling chars, phosphor trails
1  WAVE       grid buffer — 3 overlapping sine waves
2  GLITCH     random scanline corruption, occasional LOGO flash at frame%53
3  STROBE     fill/blank alternation, BPM-syncable via self._beat_phase()
4  LOGO       MOCT 7 box-drawing text, noise background
5  PULSE      BPM-synced expanding ring, polar distance per cell
6  TEXT       self.ctrl['flash_text'] in scrolling bands + centered
7  TUNNEL     self._tcache — precomputed (dist, angle) per cell, inverse radial
8  PLASMA     4-sine superposition normalized to 0..1, char+color by value
9  VORTEX     self._vcache — precomputed polar, 3-arm twist spiral
10 GRID       synthwave perspective grid, horizontal + vertical convergence
11 PARTICLES  self.particles list of dicts — fountain physics, gravity+drag
12 SCANNER    rotating radar angle, draw beam + trail per radius
13 STORM      self.storm_pts from self._lightning() — recursive midpoint displacement
14 CUBE       CUBE_V/CUBE_E constants, rot3d() + bresenham() per edge
15 SHOCKWAVE  self.rings list of dicts — expanding circumference per ring
16 NOISE      smooth multi-sine field, char+color by normalized value
```

### Per-mode state (initialized in __init__, persists between frames)

```python
self.rain_y    = {}       # {x: head_y}
self.particles = []       # [{x,y,vx,vy,life,max,char,col}, ...]
self.rings     = []       # [{x,y,r,max}, ...]
self.storm_pts = []       # [(x,y), ...]
self.storm_age = 0        # frames until next bolt
self._tcache   = None     # [[row_r, row_a], ...] — precomputed for TUNNEL
self._vcache   = None     # [[row_rn, row_a], ...] — precomputed for VORTEX
```

---

## control.json — All Controllable Parameters

```json
{
  "mode": 0,
  "auto_cycle": false,
  "blackout": false,
  "flash_active": false,
  "bpm_sync": false,
  "palette": 0,
  "flash_text": "MOCT 7",
  "frame_delay": 0.05,
  "strobe_speed": 2,
  "glitch_intensity": 0.4,
  "wave_amplitude": 0.35,
  "rain_density": 0.7,
  "mode_cycle_frames": 250,
  "bpm": 140
}
```

These are all live — visuals.py reads and applies them every frame. Accessed in modes via `self.cfg.get('key', default)`.

---

## Output Pattern — Critical for Performance

**Always** build a list and emit one write per frame for full-grid modes:

```python
def _mymode(self):
    p   = self.pal
    H   = self.h - 1
    out = []
    for y in range(H):
        out.append(mv(0, y))        # cursor to start of row
        for x in range(self.w):
            # compute char and color
            out.append(C[col] + ch + RESET)
    sys.stdout.write(''.join(out))  # one write per frame
```

**Never** call `sys.stdout.write()` or `self._put()` per cell in a full-grid loop — too slow.

Use `self._put()` only for sparse modes (CUBE, SCANNER, STORM, PARTICLES, SHOCKWAVE) where you touch <2000 cells per frame.

---

## Hot Reload — How It Works

```python
# In Engine.run(), every 20 frames:
if os.path.getmtime(__file__) != self._mtime:
    sys.stdout.write(SHOW + RESET + CLEAR)
    sys.stdout.flush()
    os.execv(sys.executable, [sys.executable] + sys.argv)
```

`os.execv` replaces the process in-place. Terminal window stays open. Per-mode state is lost and re-initialized cleanly. Engine restarts within ~1 second of file save.

**This means: edit and save visuals.py → user sees the change live. No restart needed.**

---

## How to Add a New Mode

```python
# 1. Add method to Engine class:
def _mymode(self):
    p = self.pal          # current palette
    H = self.h - 1        # usable height (bottom row is status bar)
    t = self.frame        # frame counter for animation
    # ... render ...

# 2. Register in __init__:
self.mode_fns.append(self._mymode)
self.mode_labels.append('MYMODE')

# 3. In ii.py, add to MODES list:
MODES = [..., 'MYMODE']
```

---

## How to Add a New Parameter

```python
# 1. Add to DEFAULTS in ii.py and use in a mode:
self.cfg.get('my_param', 0.5)   # in visuals.py

# 2. Add to PARAMS list in ii.py:
('my_param', 'MY PARAM    ', 0.0, 1.0, 0.05, '{:.2f}')
# (key, display_label, min, max, step, format_string)

# 3. Add to the param sync loop in Engine.run():
for key in (..., 'my_param'):
    if key in c: self.cfg[key] = c[key]
```

---

## Aesthetic Guidelines

- **Industrial/techno**: heavy block characters, high contrast, stroboscopic
- **Color**: bold ANSI colors only — no 256-color or truecolor (keeps it sharp on any terminal)
- **Motion**: math-driven (sin/cos), not random drift — rhythmic, BPM-aware where possible
- **Characters**: `█ ▓ ▒ ░ ▚ ◈ 7 M O C T` — defined in config.json `symbols` array
- **Palette**: always use `self.pal['p']`, `['s']`, `['a']` — never hardcode colors in modes

---

## Common Mistakes to Avoid

- Don't call `os.system('clear')` — use `sys.stdout.write(CLEAR)` or `mv(0,y) + ' '*self.w`
- Don't use `print()` during run — it conflicts with cursor positioning
- Don't forget `+ RESET` after colored text
- Don't read `self.h - 1` as the last drawable row — the bottom row is the status bar, so usable height is `H = self.h - 1` and valid y range is `0 <= y < H`
- Don't write past `self.w` — always clip: `text[:self.w - x]`
- Don't keep more than ~700 particles or ~14 rings — cap with `self.particles = alive[-700:]`

---

## innux/ — Ignore Unless Asked

Old standalone scripts from before the main engine was built. Separate codebase, not part of the VJ system.

---

*MOCT 7 | Hayfilm Studio | Yerevan 2026*
