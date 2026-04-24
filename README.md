# MOCT 7 | HAYFILM CLUSTER
### Terminal Visual Engine — Yerevan, 2026

Live-stream ASCII visual system for Kitty terminal, built for MOCT's 7th Anniversary at Hayfilm Studio. Two-terminal VJ setup: one screen runs the visuals fullscreen, the other runs the controller.

---

## Quick Start

**Terminal 1 — fullscreen visuals (Kitty, F11):**
```bash
python3 visuals.py
```

**Terminal 2 — controller:**
```bash
python3 ii.py
```

**Requirements:** Python 3.6+, Kitty terminal (GPU-accelerated), black background, monospace bold font 16pt+.

---

## Controller Keys

| Key | Action |
|-----|--------|
| `0`–`9` | Jump to mode by number |
| `[` / `]` | Cycle prev / next mode (all 17) |
| `↑` `↓` | Select parameter |
| `←` `→` | Adjust selected parameter |
| `P` | Next color palette |
| `T` | Tap tempo (up to 8 taps averaged) |
| `S` | Toggle BPM sync (strobe + pulse + shockwave lock to BPM) |
| `Space` | Toggle flash text overlay |
| `Enter` | Edit flash text (type, Enter to confirm, Esc to cancel) |
| `A` | Toggle auto-cycle (steps through all modes automatically) |
| `B` | Blackout — instant blank screen |
| `F1`–`F10` | Presets (RAIN / RAVE / TUNNEL / STORM / PLASMA / VORTEX / GRID / CHAOS / CUBE / NOISE) |
| `!` | PANIC — reset everything + blackout |
| `Q` | Quit controller |

---

## Modes (17 total)

| # | Name | Description |
|---|------|-------------|
| 0 | RAIN | Matrix-style falling characters with phosphor trails |
| 1 | WAVE | Three overlapping math-driven sine waves |
| 2 | GLITCH | Scanline corruption with horizontal displacement |
| 3 | STROBE | Stroboscopic fill/clear, BPM-syncable |
| 4 | LOGO | MOCT 7 big-font centered on animated noise |
| 5 | PULSE | BPM-synced expanding rings from center |
| 6 | TEXT | Custom text in animated scrolling bands |
| 7 | TUNNEL | Infinite zooming ASCII tunnel, inverse radial projection |
| 8 | PLASMA | Demo-scene plasma via superimposed sine waves |
| 9 | VORTEX | 3-arm rotating spiral with depth twist |
| 10 | GRID | Synthwave perspective grid with scrolling depth |
| 11 | PARTICLES | Particle fountain with physics (gravity, drag) |
| 12 | SCANNER | Rotating radar sweep with phosphor afterglow |
| 13 | STORM | Recursive branching lightning with flash |
| 14 | CUBE | Rotating 3D wireframe cube, perspective projected |
| 15 | SHOCKWAVE | Multiple expanding shockwave rings, BPM-syncable |
| 16 | NOISE | Smooth multi-sine noise field |

---

## Parameters

All parameters are live — change takes effect on the next frame.

| Parameter | What it controls |
|-----------|-----------------|
| SPEED | Frame delay (0.01 = fastest, 0.20 = slowest) |
| STROBE SPEED | Strobe on/off frame count (lower = faster flash) |
| GLITCH | Scanline corruption intensity in GLITCH mode |
| WAVE AMP | Wave height in WAVE mode |
| DENSITY | Particle spawn rate / rain drop density |
| CYCLE FRAMES | Frames per mode when auto-cycle is on |
| BPM | Beats per minute for sync modes |

---

## Color Palettes (6)

| Name | Feel |
|------|------|
| INDUSTRIAL | Red + green + white — default techno |
| ACID | Cyan + yellow — rave |
| VOID | White + dim + red — minimal dark |
| BLOOD | Red on red — brutal |
| MATRIX | Green on green — classic |
| NEON | Magenta + cyan — synthwave |

---

## Files

```
mct7/
├── visuals.py      — main visual engine (run fullscreen)
├── ii.py           — live controller TUI (run in second terminal)
├── config.json     — startup defaults for visual parameters
├── control.json    — live IPC: controller → visuals (auto-generated)
├── status.json     — live IPC: visuals → controller (auto-generated)
├── README.md       — this file
├── CLAUDE.md       — AI assistant context
└── innux/          — earlier prototype scripts (standalone tools)
    ├── visuals.py  — simple scrolling glitch
    ├── matrix.sh   — bash rain (standalone)
    ├── glitch.js   — node.js glitch (standalone)
    ├── black.py    — blackout utility
    └── README.md
```

---

## Hot Reload

Edit `visuals.py` and save — the engine detects the file change and restarts itself within ~1 second. The fullscreen terminal window stays open. This enables live coding during a performance.

---

## IPC Architecture

`controller.py` writes `control.json` atomically (write-to-temp + rename) every 50ms.  
`visuals.py` reads `control.json` every frame and applies all values.  
`visuals.py` writes `status.json` every 10 frames — controller reads it to show live FPS and frame count.

No sockets, no pipes. Works reliably even if one process restarts.

---

*Developed for MOCT 7th Anniversary — Hayfilm Studio, Yerevan 2026*
