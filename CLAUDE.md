# MOCT 7 — AI Context

This is a live VJ terminal visual engine for a techno event (MOCT 7th Anniversary, Hayfilm Studio, Yerevan 2026). The user runs this during live performances and edits it in real time via prompts.

---

## Project Purpose

Two-terminal VJ system:
- `visuals.py` — fullscreen ASCII visual engine in Kitty terminal
- `controller.py` — curses-based live controller in a second terminal
- IPC via `control.json` (controller→visuals) and `status.json` (visuals→controller)

The user describes changes in natural language. You edit `visuals.py`. The hot-reload system (`os.execv` on file mtime change, checked every 20 frames) restarts the engine automatically within ~1 second — no manual restart needed.

---

## Architecture

### visuals.py

Single class `Engine` with 17 visual modes. Key design:

```
Engine.__init__()      — loads config, initializes per-mode state
Engine.run()           — main loop: load_ctrl() → apply params → render mode → write status
Engine.mode_fns[]      — list of 17 method references, indexed by self.mode
Engine._bar()          — status line at bottom row (always rendered)
Engine._precompute_polar() — caches (dist, angle) per cell for TUNNEL and VORTEX on resize
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

### controller.py

Curses TUI. Single class `Controller`. Writes `control.json` every loop iteration. Reads `status.json` for live feedback display.

**control.json schema:**
```json
{
  "mode": 0-16,
  "auto_cycle": bool,
  "blackout": bool,
  "flash_active": bool,
  "bpm_sync": bool,
  "palette": 0-5,
  "flash_text": "string",
  "frame_delay": 0.01-0.20,
  "strobe_speed": 1-10,
  "glitch_intensity": 0.05-1.0,
  "wave_amplitude": 0.10-0.50,
  "rain_density": 0.10-1.0,
  "mode_cycle_frames": 50-600,
  "bpm": 40-240
}
```

---

## 17 Modes

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
```

---

## Per-mode State

Modes that maintain state between frames:
- `self.rain_y` (dict) — column head positions for RAIN
- `self.particles` (list of dicts) — active particles for PARTICLES
- `self.rings` (list of dicts) — active rings for SHOCKWAVE
- `self.storm_pts` (list of tuples) — current lightning branch points for STORM
- `self.storm_age` (int) — frames until next lightning regeneration
- `self._tcache` / `self._vcache` — precomputed polar coord grids for TUNNEL/VORTEX

---

## Performance Notes

- Full-grid modes (TUNNEL, PLASMA, VORTEX, NOISE, WAVE, PULSE): render all `w × (h-1)` cells. At 120×50 this is ~6000 cells. Use list-join output, never per-cell writes.
- TUNNEL and VORTEX: `_precompute_polar()` caches `(dist, angle)` per cell and rebuilds only on terminal resize. This avoids ~6000 atan2+sqrt calls per frame.
- Sparse modes (CUBE, SCANNER, STORM, SHOCKWAVE, PARTICLES): touch only 200–2000 cells per frame. Much faster.
- `frame_delay` default is 0.05s (20fps). User can lower it for faster modes or raise it if a mode is computationally heavy.
- `self.syms` is the character palette from config.json. Use `self._s()` to pick a random one.

---

## Hot Reload

```python
# In Engine.run(), every 20 frames:
if os.path.getmtime(__file__) != self._mtime:
    sys.stdout.write(SHOW + RESET + CLEAR)
    sys.stdout.flush()
    os.execv(sys.executable, [sys.executable] + sys.argv)
```

`os.execv` replaces the process in-place. Terminal stays open, cursor is restored, new process starts fresh. Per-mode state is lost (acceptable — modes reinitialize cleanly).

---

## How to Add a New Mode

1. Add a method `_mymode(self)` to `Engine`
2. Append it to `self.mode_fns` in `__init__`
3. Append its name string to `self.mode_labels` in `__init__`
4. Add to `MODES` list in `controller.py`
5. Save → hot-reload activates it

Accessing palette: `p = self.pal` then `C[p['p']]`, `C[p['s']]`, `C[p['a']]`  
Accessing control values: `self.ctrl.get('flash_text', '')`, `self.cfg.get('bpm', 140)`  
Drawing a cell: `self._put(x, y, char, color_string)`  
Drawing a full frame buffer: build `out = []`, `out.append(mv(0,y))` per row, cells inline, then `sys.stdout.write(''.join(out))`

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
