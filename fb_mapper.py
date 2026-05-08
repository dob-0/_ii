#!/usr/bin/env python3
"""fb_mapper.py — Framebuffer projection mapper for ii.

Renders ii visual modes directly to /dev/fb0 at 1366×768 with quad-warp
projection mapping. Reads mappings/fb_map.json for surface definitions.
Run alongside ii.py (which writes control.json). Does NOT need visuals.py.

Usage:
    python3 fb_mapper.py
    python3 fb_mapper.py --map mappings/split3.json   # override map file

Requires: group 'video' membership for /dev/fb0 access.
"""

import argparse
import fcntl
import json
import mmap
import os
import signal
import struct
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

from architecture import CTRL_PATH, DEFAULTS, discover_modes, load_json
from modes.base import C, PALETTES, COLOR_KEYS

# ── Screen ────────────────────────────────────────────────────────────────────
FB_W, FB_H = 1366, 768
FB_BYTES = FB_W * FB_H * 4  # BGRA32

# ── Virtual canvas ────────────────────────────────────────────────────────────
# Matches terminal char resolution so existing modes look identical.
VW, VH = 64, 36

# ── Paths ────────────────────────────────────────────────────────────────────
FB_PATH   = '/dev/fb0'
TTY_PATH  = '/dev/tty1'
MAP_FILE  = os.path.join(BASE, 'mappings', 'fb_map.json')

# ── TTY ioctl ─────────────────────────────────────────────────────────────────
KDSETMODE  = 0x4B3A
KD_TEXT    = 0
KD_GRAPHICS = 1

# ── ANSI escape → (R,G,B) ────────────────────────────────────────────────────
_ESC = '\033'
ANSI_TO_RGB = {
    f'{_ESC}[1;31m': (255,  85,  85),   # red
    f'{_ESC}[1;92m': ( 85, 255,  85),   # green
    f'{_ESC}[1;37m': (255, 255, 255),   # white
    f'{_ESC}[2;37m': ( 85,  85,  85),   # dim
    f'{_ESC}[1;96m': ( 85, 255, 255),   # cyan
    f'{_ESC}[1;93m': (255, 255,  85),   # yellow
    f'{_ESC}[1;95m': (255,  85, 255),   # magenta
    f'{_ESC}[0;31m': (170,   0,   0),   # red_d
    f'{_ESC}[0;32m': (  0, 170,   0),   # green_d
    f'{_ESC}[1;94m': ( 85,  85, 255),   # blue
}

# Build BGRA bytes for each known ANSI color key (cached once at startup)
_BGRA_CACHE = {
    col: bytes([rgb[2], rgb[1], rgb[0], 255])
    for col, rgb in ANSI_TO_RGB.items()
}
_BGRA_BLACK = b'\x00\x00\x00\xff'


# ── Geometry ─────────────────────────────────────────────────────────────────

def _fwd_bilinear(u, v, tl, tr, bl, br):
    """Forward bilinear map: normalized (u,v) → screen (x,y)."""
    x = (1-u)*(1-v)*tl[0] + u*(1-v)*tr[0] + (1-u)*v*bl[0] + u*v*br[0]
    y = (1-u)*(1-v)*tl[1] + u*(1-v)*tr[1] + (1-u)*v*bl[1] + u*v*br[1]
    return x, y


def _scanline_fill(poly, fw, fh):
    """Scanline-fill a convex polygon (list of (x,y) vertices, screen coords).

    Returns list of (fb_byte_start, byte_count, pixel_count) for each
    horizontal run, where fb_byte_start = (py*fw + px) * 4.
    """
    ys = [p[1] for p in poly]
    y_min = max(0, int(min(ys)))
    y_max = min(fh - 1, int(max(ys)) + 1)
    n = len(poly)
    runs = []
    for y in range(y_min, y_max):
        xs = []
        for i in range(n):
            ax, ay = poly[i]
            bx, by = poly[(i + 1) % n]
            if (ay <= y < by) or (by <= y < ay):
                t = (y - ay) / (by - ay)
                xs.append(ax + t * (bx - ax))
        if len(xs) >= 2:
            x0 = max(0, int(min(xs) + 0.5))
            x1 = min(fw - 1, int(max(xs) - 0.5))
            if x0 <= x1:
                pix = x1 - x0 + 1
                runs.append(((y * fw + x0) * 4, pix * 4, pix))
    return runs


def is_rect(surf):
    """True if surface corners form an axis-aligned rectangle (tolerance 2px)."""
    c = surf['corners']
    tl, tr, bl, br = c[0], c[1], c[2], c[3]
    return (abs(tl[1] - tr[1]) < 2 and abs(bl[1] - br[1]) < 2 and
            abs(tl[0] - bl[0]) < 2 and abs(tr[0] - br[0]) < 2)


def build_rect_data(surf):
    """For rectangular surfaces: precompute per-cell pixel grids.

    Returns (col_px, row_py) where col_px[vx] is the left pixel of cell vx,
    row_py[vy] is the top pixel of cell vy (length VW+1 and VH+1).
    """
    c = surf['corners']
    tl, tr, bl = c[0], c[1], c[2]
    px0, py0 = int(round(tl[0])), int(round(tl[1]))
    pw = int(round(tr[0])) - px0
    ph = int(round(bl[1])) - py0
    col_px = [max(0, min(FB_W, px0 + round(vx * pw / VW))) for vx in range(VW + 1)]
    row_py = [max(0, min(FB_H, py0 + round(vy * ph / VH))) for vy in range(VH + 1)]
    return col_px, row_py


def build_lut(surf):
    """Precompute per-cell scanline run tables for warped surfaces.

    Returns lut[vy][vx] = list of (fb_byte_start, byte_count, pixel_count).
    """
    corners = surf['corners']
    tl = tuple(corners[0])
    tr = tuple(corners[1])
    bl = tuple(corners[2])
    br = tuple(corners[3])

    lut = [[None] * VW for _ in range(VH)]
    for vy in range(VH):
        v0, v1 = vy / VH, (vy + 1) / VH
        for vx in range(VW):
            u0, u1 = vx / VW, (vx + 1) / VW
            c_tl = _fwd_bilinear(u0, v0, tl, tr, bl, br)
            c_tr = _fwd_bilinear(u1, v0, tl, tr, bl, br)
            c_br = _fwd_bilinear(u1, v1, tl, tr, bl, br)
            c_bl = _fwd_bilinear(u0, v1, tl, tr, bl, br)
            lut[vy][vx] = _scanline_fill([c_tl, c_tr, c_br, c_bl], FB_W, FB_H)
    return lut


# ── Surface loading ───────────────────────────────────────────────────────────

def _default_surface():
    # corners in pixel coords, order [TL, TR, BL, BR]
    return [{
        'id': 'FULL',
        'mode': None,
        'phase': 0.0,
        'enabled': True,
        'corners': [[0, 0], [FB_W - 1, 0], [0, FB_H - 1], [FB_W - 1, FB_H - 1]],
    }]


def _normalize_corners(raw):
    """Convert map_server.py corners to internal pixel [TL, TR, BL, BR].

    map_server.py stores normalized 0..1 coords in order [TL, TR, BR, BL].
    We scale to pixels and swap the last two to get [TL, TR, BL, BR].
    """
    tl, tr, br, bl = [list(c) for c in raw]
    return [
        [tl[0] * FB_W, tl[1] * FB_H],
        [tr[0] * FB_W, tr[1] * FB_H],
        [bl[0] * FB_W, bl[1] * FB_H],
        [br[0] * FB_W, br[1] * FB_H],
    ]


def load_surfaces(path):
    try:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f'[fb_mapper] Cannot load {path}: {e} — using full-screen', flush=True)
        return _default_surface()

    # map_server.py format: {"surfaces": [...]} with normalized 0..1 corners
    surfs = []
    for s in data.get('surfaces', []):
        raw = s.get('corners', [])
        if len(raw) == 4:
            corners = _normalize_corners(raw)
        else:
            corners = _default_surface()[0]['corners']
        surfs.append({
            'id': s.get('id', 'surf'),
            'mode': s.get('mode'),
            'phase': float(s.get('phase', 0.0)),
            'enabled': bool(s.get('enabled', True)),
            'corners': corners,
        })

    if not surfs:
        # Fallback: old zone format {"zones": [...]} with x/y/w/h fractions
        for z in data.get('zones', []):
            x = z.get('x', 0.0) * FB_W
            y = z.get('y', 0.0) * FB_H
            w = z.get('w', 1.0) * FB_W
            h = z.get('h', 1.0) * FB_H
            surfs.append({
                'id': z.get('id', 'zone'),
                'mode': z.get('mode'),
                'phase': float(z.get('phase', 0.0)),
                'enabled': bool(z.get('enabled', True)),
                'corners': [[x, y], [x + w, y], [x, y + h], [x + w, y + h]],
            })

    active = [s for s in surfs if s.get('enabled', True)]
    return active if active else _default_surface()


# ── Mapper engine ─────────────────────────────────────────────────────────────

class FbMapper:
    def __init__(self, map_path):
        self.map_path    = map_path
        self.tty_fd      = None
        self.fb_fd       = None
        self.fb_mm       = None
        self.fb_buf      = bytearray(FB_BYTES)
        self._black_buf  = bytes(FB_BYTES)  # pre-allocated zero buffer for fast clear
        self.modes       = discover_modes()
        self.t0          = time.time()
        self.frame       = 0
        self._vbufs      = {}   # surface_idx → VH×VW char buffer
        self._map_mtime  = None
        self.surfaces    = []
        self.luts        = []
        self.rect_data   = []

        if not self.modes:
            raise RuntimeError('No modes found under modes/')

        self._open_fb()
        self._set_graphics_mode()
        self._load_map()

    # ── Setup / teardown ─────────────────────────────────────────────────────

    def _open_fb(self):
        self.fb_fd = open(FB_PATH, 'r+b')
        self.fb_mm = mmap.mmap(self.fb_fd.fileno(), FB_BYTES)
        print(f'[fb_mapper] /dev/fb0 opened ({FB_W}×{FB_H})', flush=True)

    def _set_graphics_mode(self):
        try:
            self.tty_fd = open(TTY_PATH, 'wb')
            fcntl.ioctl(self.tty_fd, KDSETMODE, struct.pack('I', KD_GRAPHICS))
            print('[fb_mapper] TTY1 → KD_GRAPHICS', flush=True)
        except Exception as e:
            print(f'[fb_mapper] Could not set KD_GRAPHICS: {e}', flush=True)

    def _restore_text_mode(self):
        if self.tty_fd:
            try:
                fcntl.ioctl(self.tty_fd, KDSETMODE, struct.pack('I', KD_TEXT))
                self.tty_fd.close()
                print('[fb_mapper] TTY1 → KD_TEXT', flush=True)
            except Exception:
                pass
            self.tty_fd = None

    def cleanup(self):
        self._restore_text_mode()
        if self.fb_mm:
            try:
                self.fb_mm.seek(0)
                self.fb_mm.write(b'\x00' * FB_BYTES)
                self.fb_mm.close()
            except Exception:
                pass
        if self.fb_fd:
            try:
                self.fb_fd.close()
            except Exception:
                pass

    # ── Map hot-reload ────────────────────────────────────────────────────────

    def _load_map(self):
        try:
            mtime = os.path.getmtime(self.map_path)
        except OSError:
            mtime = -1  # sentinel: file absent

        if mtime == self._map_mtime:
            return

        print(f'[fb_mapper] Loading map {self.map_path}…', flush=True)
        self.surfaces = load_surfaces(self.map_path)
        self._vbufs   = {}

        print(f'[fb_mapper] Building LUTs for {len(self.surfaces)} surfaces…', flush=True)
        self.luts = []
        self.rect_data = []   # None for warped, (col_px, row_py) for rectangular
        for s in self.surfaces:
            if is_rect(s):
                self.luts.append(None)
                self.rect_data.append(build_rect_data(s))
            else:
                self.luts.append(build_lut(s))
                self.rect_data.append(None)
        self._map_mtime = mtime
        n_rect = sum(1 for r in self.rect_data if r is not None)
        print(f'[fb_mapper] LUTs ready ({n_rect} rect, {len(self.surfaces)-n_rect} warped).', flush=True)

    # ── Rendering ────────────────────────────────────────────────────────────

    def _vbuf(self, idx):
        if idx not in self._vbufs:
            self._vbufs[idx] = [[None] * VW for _ in range(VH)]
        return self._vbufs[idx]

    def _mode_idx(self, surf, merged):
        spec = surf.get('mode')
        return max(0, min(len(self.modes) - 1,
                          int(merged.get('mode', 0) if spec is None else spec)))

    def _render_surface_rect(self, idx, surf, rect_data, t_now, merged, pal, syms):
        """Fast path for axis-aligned rectangular surfaces (~16x fewer iterations)."""
        mode_idx = self._mode_idx(surf, merged)
        vbuf = self._vbuf(idx)
        self.modes[mode_idx].render(vbuf, VW, VH,
                                    t_now + float(surf.get('phase', 0.0)),
                                    self.frame, merged, pal, syms)
        col_px, row_py = rect_data
        fb = self.fb_buf
        for vy in range(VH):
            py0, py1 = row_py[vy], row_py[vy + 1]
            if py0 >= py1:
                continue
            # Build one pixel row for this virtual row
            row = vbuf[vy]
            parts = []
            for vx in range(VW):
                cw = col_px[vx + 1] - col_px[vx]
                if cw > 0:
                    cell = row[vx]
                    bgra4 = _BGRA_CACHE.get(cell[1], _BGRA_BLACK) if cell else _BGRA_BLACK
                    parts.append(bgra4 * cw)
            row_bytes = b''.join(parts)
            rlen = len(row_bytes)
            x0 = col_px[0]
            for py in range(py0, min(py1, FB_H)):
                off = (py * FB_W + x0) * 4
                fb[off:off + rlen] = row_bytes

    def _render_surface(self, idx, surf, lut, t_now, merged, pal, syms):
        """Warp path for non-rectangular surfaces."""
        mode_idx = self._mode_idx(surf, merged)
        t_surf = t_now + float(surf.get('phase', 0.0))
        vbuf   = self._vbuf(idx)
        self.modes[mode_idx].render(vbuf, VW, VH, t_surf, self.frame, merged, pal, syms)
        fb = self.fb_buf
        for vy in range(VH):
            row     = vbuf[vy]
            row_lut = lut[vy]
            for vx in range(VW):
                cell = row[vx]
                bgra4 = _BGRA_CACHE.get(cell[1], _BGRA_BLACK) if cell else _BGRA_BLACK
                for start, blen, pcount in row_lut[vx]:
                    fb[start:start + blen] = bgra4 * pcount

    def render_frame(self, ctrl, cfg):
        t_now = time.time() - self.t0
        pal   = dict(PALETTES[int(ctrl.get('palette', 0)) % len(PALETTES)])
        merged = {**cfg, **ctrl}
        syms  = cfg.get('symbols', ['#', '*', '.'])

        # Black canvas
        self.fb_buf[:] = self._black_buf

        for i, (surf, lut, rdata) in enumerate(zip(self.surfaces, self.luts, self.rect_data)):
            if rdata is not None:
                self._render_surface_rect(i, surf, rdata, t_now, merged, pal, syms)
            else:
                self._render_surface(i, surf, lut, t_now, merged, pal, syms)

        self.fb_mm.seek(0)
        self.fb_mm.write(self.fb_buf)

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self):
        cfg = dict(DEFAULTS)
        try:
            with open(os.path.join(BASE, 'config.json'), encoding='utf-8') as f:
                cfg.update(json.load(f))
        except Exception:
            pass

        print('[fb_mapper] Running — Ctrl-C to stop', flush=True)

        while True:
            t_loop = time.time()

            # Hot-reload map if file changed
            if self.frame % 60 == 0:
                self._load_map()

            ctrl = load_json(CTRL_PATH, {})

            if ctrl.get('blackout'):
                self.fb_mm.seek(0)
                self.fb_mm.write(self._black_buf)
                self.frame += 1
                time.sleep(0.05)
                continue

            self.render_frame(ctrl, cfg)
            self.frame += 1

            delay = float(ctrl.get('frame_delay', cfg.get('frame_delay', 0.05)))
            elapsed = time.time() - t_loop
            time.sleep(max(0.01, delay - elapsed))  # always yield CPU


# ── Entry point ───────────────────────────────────────────────────────────────

_mapper = None


def _quit(sig, _frame):
    if _mapper:
        _mapper.cleanup()
    sys.exit(0)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--map', default=MAP_FILE, help='Path to mapping JSON')
    args = ap.parse_args()

    signal.signal(signal.SIGINT,  _quit)
    signal.signal(signal.SIGTERM, _quit)

    _mapper = FbMapper(args.map)
    try:
        _mapper.run()
    finally:
        _mapper.cleanup()
