#!/usr/bin/env python3
"""output.py — pygame fullscreen/windowed output for the ii VJ engine.

Reads control.json, renders virtual modes into a VW×VH buffer, maps cells
through quad-warp surfaces from fb_map.json, and blits to screen via pygame.

Usage:
    python3 output.py --display 1
    python3 output.py --display 0
    python3 output.py --windowed 1280 720
    python3 output.py --map mappings/quad.json --vw 128 --vh 72
"""

import argparse
import json
import os
import random
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

import pygame

from architecture import CTRL_PATH, DEFAULTS, STATUS_PATH, discover_modes, load_json, save_json_atomic
from modes.base import PALETTES, color_key

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False

try:
    import cv2 as _cv2
    _HAS_CV2 = True
except ImportError:
    _HAS_CV2 = False

MEDIA_DIR = os.path.join(BASE, 'media')

ESC = '\033'
ANSI_TO_RGB = {
    f'{ESC}[1;31m': (255,  85,  85),
    f'{ESC}[1;92m': ( 85, 255,  85),
    f'{ESC}[1;37m': (255, 255, 255),
    f'{ESC}[2;37m': ( 85,  85,  85),
    f'{ESC}[1;96m': ( 85, 255, 255),
    f'{ESC}[1;93m': (255, 255,  85),
    f'{ESC}[1;95m': (255,  85, 255),
    f'{ESC}[0;31m': (170,   0,   0),
    f'{ESC}[0;32m': (  0, 170,   0),
    f'{ESC}[1;94m': ( 85,  85, 255),
}
_RGB_BLACK = (0, 0, 0)
DEFAULT_MAP = os.path.join(BASE, 'mappings', 'fb_map.json')


# ── Video player ──────────────────────────────────────────────────────────────

class VideoPlayer:
    """Wraps cv2.VideoCapture for a single looping video source."""

    def __init__(self, path):
        self._cap = None
        if _HAS_CV2:
            cap = _cv2.VideoCapture(path)
            if cap.isOpened():
                self._cap = cap

    def read_frame(self, vw, vh):
        """Return an (vh, vw, 3) uint8 RGB numpy array, or None."""
        if self._cap is None:
            return None
        ok, frame = self._cap.read()
        if not ok:
            self._cap.set(_cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = self._cap.read()
            if not ok:
                return None
        frame = _cv2.cvtColor(frame, _cv2.COLOR_BGR2RGB)
        return _cv2.resize(frame, (vw, vh))

    def close(self):
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def __del__(self):
        self.close()


# ── Map geometry ──────────────────────────────────────────────────────────────

def _fwd(u, v, tl, tr, bl, br):
    x = (1-u)*(1-v)*tl[0] + u*(1-v)*tr[0] + (1-u)*v*bl[0] + u*v*br[0]
    y = (1-u)*(1-v)*tl[1] + u*(1-v)*tr[1] + (1-u)*v*bl[1] + u*v*br[1]
    return x, y


def _pixel_corners(s, sw, sh):
    """Return (tl, tr, bl, br) in pixel coords from a surface dict."""
    raw = s.get('corners', [])
    if len(raw) == 4 and all(-2.0 <= raw[i][j] <= 2.0 for i in range(4) for j in range(2)):
        tl, tr, br, bl = raw   # normalized [TL,TR,BR,BL] from map_server.py
        return ((tl[0]*sw, tl[1]*sh), (tr[0]*sw, tr[1]*sh),
                (bl[0]*sw, bl[1]*sh), (br[0]*sw, br[1]*sh))
    if len(raw) == 4:           # already pixel coords
        tl, tr, br, bl = raw
        return (tuple(tl), tuple(tr), tuple(bl), tuple(br))
    return ((0, 0), (sw, 0), (0, sh), (sw, sh))


def load_surfaces(path, sw, sh):
    try:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        data = {}

    surfs = []
    for s in data.get('surfaces', []):
        if not s.get('enabled', True):
            continue
        surfs.append({'id': s.get('id', 'surf'), 'mode': s.get('mode'),
                      'video': s.get('video') or '',
                      'phase': float(s.get('phase', 0.0)),
                      'corners': _pixel_corners(s, sw, sh)})

    if not surfs:
        for z in data.get('zones', []):
            if not z.get('enabled', True):
                continue
            x, y = z.get('x', 0.0)*sw, z.get('y', 0.0)*sh
            w, h = z.get('w', 1.0)*sw, z.get('h', 1.0)*sh
            surfs.append({'id': z.get('id', 'zone'), 'mode': z.get('mode'),
                          'phase': float(z.get('phase', 0.0)),
                          'corners': ((x, y), (x+w, y), (x, y+h), (x+w, y+h))})

    if not surfs:
        surfs.append({'id': 'FULL', 'mode': None, 'phase': 0.0,
                      'corners': ((0, 0), (sw, 0), (0, sh), (sw, sh))})
    return surfs


def build_lut_numpy(surf, vw, vh, sw, sh):
    tl, tr, bl, br = surf['corners']
    lut_vy = np.full((sh, sw), -1, dtype=np.int16)
    lut_vx = np.full((sh, sw), -1, dtype=np.int16)
    for vy in range(vh):
        for vx in range(vw):
            u0, u1 = vx/vw, (vx+1)/vw
            v0, v1 = vy/vh, (vy+1)/vh
            xs = [_fwd(u, v, tl, tr, bl, br)[0] for u, v in ((u0,v0),(u1,v0),(u0,v1),(u1,v1))]
            ys = [_fwd(u, v, tl, tr, bl, br)[1] for u, v in ((u0,v0),(u1,v0),(u0,v1),(u1,v1))]
            px0 = max(0, int(min(xs)));     px1 = min(sw, int(max(xs)) + 1)
            py0 = max(0, int(min(ys)));     py1 = min(sh, int(max(ys)) + 1)
            if px1 > px0 and py1 > py0:
                lut_vy[py0:py1, px0:px1] = vy
                lut_vx[py0:py1, px0:px1] = vx
    valid = lut_vy >= 0
    return lut_vy, lut_vx, valid


def build_lut_poly(surf, vw, vh):
    tl, tr, bl, br = surf['corners']
    return [[
        (_fwd(vx/vw, vy/vh, tl, tr, bl, br),
         _fwd((vx+1)/vw, vy/vh, tl, tr, bl, br),
         _fwd((vx+1)/vw, (vy+1)/vh, tl, tr, bl, br),
         _fwd(vx/vw, (vy+1)/vh, tl, tr, bl, br))
        for vx in range(vw)] for vy in range(vh)]


# ── Engine ────────────────────────────────────────────────────────────────────

class OutputEngine:
    def __init__(self, args):
        self.args        = args
        self.vw          = args.vw
        self.vh          = args.vh
        self.map_path    = args.map
        self.frame       = 0
        self.t0          = time.time()
        self._fps_t      = time.time()
        self._fps        = 0.0
        self._kb_blackout = False

        self.modes       = discover_modes()
        if not self.modes:
            raise RuntimeError('No modes found under modes/')
        self.mode_labels = [m.NAME for m in self.modes]

        self._buf   = [[None]*self.vw for _ in range(self.vh)]
        self._buf_a = [[None]*self.vw for _ in range(self.vh)]
        self._buf_b = [[None]*self.vw for _ in range(self.vh)]

        self._map_mtime = None
        self.surfaces   = []
        self.luts       = []
        self._video_players = {}   # surf_id → VideoPlayer

        pygame.init()
        self._init_display()
        self._load_map()

    def _init_display(self):
        args = self.args
        if args.windowed:
            self.sw, self.sh = args.windowed
            self.screen = pygame.display.set_mode(
                (self.sw, self.sh), pygame.NOFRAME)
        else:
            try:
                sizes = pygame.display.get_desktop_sizes()
                idx = args.display
                if idx < len(sizes):
                    self.sw, self.sh = sizes[idx]
                    self.screen = pygame.display.set_mode(
                        (self.sw, self.sh), pygame.FULLSCREEN | pygame.NOFRAME,
                        display=idx)
                else:
                    raise ValueError('display index out of range')
            except Exception:
                info = pygame.display.Info()
                self.sw, self.sh = info.current_w, info.current_h
                self.screen = pygame.display.set_mode(
                    (self.sw, self.sh), pygame.FULLSCREEN | pygame.NOFRAME)

        pygame.display.set_caption('ii output')
        pygame.mouse.set_visible(False)
        if _HAS_NUMPY:
            self._np_surf = pygame.Surface((self.sw, self.sh))

    def _load_map(self):
        try:
            mtime = os.path.getmtime(self.map_path)
        except OSError:
            mtime = -1
        if mtime == self._map_mtime:
            return
        self.surfaces = load_surfaces(self.map_path, self.sw, self.sh)
        self.luts = []
        for s in self.surfaces:
            if _HAS_NUMPY:
                self.luts.append(build_lut_numpy(s, self.vw, self.vh, self.sw, self.sh))
            else:
                self.luts.append(build_lut_poly(s, self.vw, self.vh))
        self._update_video_players()
        self._map_mtime = mtime

    def _clear(self, buf):
        for row in buf:
            row[:] = [None] * self.vw

    def _composite(self, alpha):
        for y in range(self.vh):
            ra, rb, ro = self._buf_a[y], self._buf_b[y], self._buf[y]
            for x in range(self.vw):
                b = rb[x]
                if b is not None and b[0] != ' ' and (alpha >= 0.999 or random.random() < alpha):
                    ro[x] = b
                else:
                    ro[x] = ra[x]

    def _fill_vbuf(self, mode_idx, mode_b_idx, layer_b, alpha, t_surf, merged, pal, syms):
        if layer_b:
            self._clear(self._buf_a)
            self._clear(self._buf_b)
            self.modes[mode_idx].render(
                self._buf_a, self.vw, self.vh, t_surf, self.frame, merged, pal, syms)
            self.modes[mode_b_idx].render(
                self._buf_b, self.vw, self.vh, t_surf, self.frame, merged, pal, syms)
            self._composite(alpha)
        else:
            self._clear(self._buf)
            self.modes[mode_idx].render(
                self._buf, self.vw, self.vh, t_surf, self.frame, merged, pal, syms)

    def _blit_numpy(self, lut_data, master_dim):
        lut_vy, lut_vx, valid = lut_data
        color_arr = np.zeros((self.vh, self.vw, 3), dtype=np.uint8)
        for vy in range(self.vh):
            row = self._buf[vy]
            for vx in range(self.vw):
                cell = row[vx]
                if cell is not None and cell[0] != ' ':
                    rgb = ANSI_TO_RGB.get(cell[1], _RGB_BLACK)
                    color_arr[vy, vx] = rgb

        arr = pygame.surfarray.pixels3d(self._np_surf)  # (sw, sh, 3)
        vy_t, vx_t, valid_t = lut_vy.T, lut_vx.T, valid.T
        if master_dim < 0.999:
            mask = np.random.random((self.sw, self.sh)) < master_dim
            active = valid_t & mask
        else:
            active = valid_t
        arr[active] = color_arr[vy_t[active], vx_t[active]]
        del arr

    def _update_video_players(self):
        needed = {s['id']: s['video'] for s in self.surfaces if s.get('video')}
        for sid in list(self._video_players):
            if sid not in needed:
                self._video_players[sid].close()
                del self._video_players[sid]
        for sid, fname in needed.items():
            if sid not in self._video_players:
                path = os.path.join(MEDIA_DIR, os.path.basename(fname))
                if os.path.isfile(path):
                    self._video_players[sid] = VideoPlayer(path)

    def _blit_video(self, lut_data, video_frame, master_dim):
        lut_vy, lut_vx, valid = lut_data
        arr = pygame.surfarray.pixels3d(self._np_surf)
        vy_t, vx_t, valid_t = lut_vy.T, lut_vx.T, valid.T
        active = valid_t & (np.random.random((self.sw, self.sh)) < master_dim) if master_dim < 0.999 else valid_t
        arr[active] = video_frame[vy_t[active], vx_t[active]]
        del arr

    def _blit_poly(self, quads, master_dim):
        scr = self.screen
        for vy in range(self.vh):
            row = self._buf[vy]
            row_q = quads[vy]
            for vx in range(self.vw):
                cell = row[vx]
                if cell is None or cell[0] == ' ':
                    continue
                if master_dim < 0.999 and random.random() > master_dim:
                    continue
                rgb = ANSI_TO_RGB.get(cell[1], _RGB_BLACK)
                if rgb != _RGB_BLACK:
                    pygame.draw.polygon(scr, rgb, row_q[vx])

    def _render_frame(self, merged, pal, syms):
        t_now = time.time() - self.t0
        mode_idx   = max(0, min(len(self.modes)-1, int(merged.get('mode', 0))))
        mode_b_idx = max(0, min(len(self.modes)-1, int(merged.get('mode_b', 1))))
        layer_b    = bool(merged.get('layer_b_enabled', False))
        alpha      = float(merged.get('layer_b_alpha', 1.0))
        master_dim = float(merged.get('master_dim', 1.0))

        if _HAS_NUMPY:
            self._np_surf.fill((0, 0, 0))
            for surf, lut_data in zip(self.surfaces, self.luts):
                player = self._video_players.get(surf['id']) if surf.get('video') else None
                if player is not None:
                    vf = player.read_frame(self.vw, self.vh)
                    if vf is not None:
                        self._blit_video(lut_data, vf, master_dim)
                        continue
                spec = surf['mode']
                midx = max(0, min(len(self.modes)-1, int(spec))) if spec is not None else mode_idx
                self._fill_vbuf(midx, mode_b_idx, layer_b, alpha,
                                 t_now + surf['phase'], merged, pal, syms)
                self._blit_numpy(lut_data, master_dim)
            self.screen.blit(self._np_surf, (0, 0))
        else:
            self.screen.fill((0, 0, 0))
            for surf, quads in zip(self.surfaces, self.luts):
                spec = surf['mode']
                midx = max(0, min(len(self.modes)-1, int(spec))) if spec is not None else mode_idx
                self._fill_vbuf(midx, mode_b_idx, layer_b, alpha,
                                 t_now + surf['phase'], merged, pal, syms)
                self._blit_poly(quads, master_dim)

    def _write_status(self, merged, mode_idx, pal):
        save_json_atomic(STATUS_PATH, {
            'frame':      self.frame,
            'fps':        round(self._fps, 1),
            'mode':       mode_idx,
            'mode_label': self.mode_labels[mode_idx],
            'palette':    pal.get('name', ''),
            'ts':         time.time(),
        })

    def run(self):
        clock = pygame.time.Clock()
        fullscreen = not bool(self.args.windowed)

        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_ESCAPE, pygame.K_q):
                        return
                    elif event.key == pygame.K_f:
                        fullscreen = not fullscreen
                        flags = (pygame.FULLSCREEN | pygame.NOFRAME) if fullscreen else pygame.NOFRAME
                        pygame.display.set_mode((self.sw, self.sh), flags)
                    elif event.key == pygame.K_b:
                        self._kb_blackout = not self._kb_blackout
                    elif event.key == pygame.K_SPACE:
                        ctrl = load_json(CTRL_PATH, {})
                        ctrl['mode'] = (int(ctrl.get('mode', 0)) + 1) % len(self.modes)
                        save_json_atomic(CTRL_PATH, ctrl)

            ctrl   = load_json(CTRL_PATH, {})
            merged = dict(DEFAULTS)
            merged.update(ctrl)

            pal_idx = int(merged.get('palette', 0)) % len(PALETTES)
            pal = dict(PALETTES[pal_idx])
            pal['p'] = color_key(ctrl.get('primary_color', -1), pal['p'])
            pal['s'] = color_key(ctrl.get('secondary_color', -1), pal['s'])
            pal['a'] = color_key(ctrl.get('accent_color', -1), pal['a'])

            syms    = merged.get('symbols', ['#', '*', '.'])
            mode_idx = max(0, min(len(self.modes)-1, int(merged.get('mode', 0))))

            if self.frame % 10 == 0:
                now = time.time()
                self._fps = 10 / max(0.001, now - self._fps_t)
                self._fps_t = now
                self._write_status(merged, mode_idx, pal)

            if self.frame % 60 == 0:
                self._load_map()

            if self._kb_blackout or ctrl.get('blackout'):
                self.screen.fill((0, 0, 0))
                pygame.display.flip()
                self.frame += 1
                clock.tick(60)
                continue

            self._render_frame(merged, pal, syms)
            pygame.display.flip()
            self.frame += 1
            clock.tick(max(1, int(1.0 / max(0.001, float(merged.get('frame_delay', 0.05))))))


# ── Entry ─────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description='ii pygame output')
    ap.add_argument('--display',  type=int,  default=0,
                    help='Display index for fullscreen')
    ap.add_argument('--windowed', type=int, nargs=2, metavar=('W', 'H'),
                    help='Run windowed at given size')
    ap.add_argument('--map',      default=DEFAULT_MAP,
                    help='Path to mapping JSON')
    ap.add_argument('--vw',       type=int, default=128,
                    help='Virtual canvas width (default 128)')
    ap.add_argument('--vh',       type=int, default=72,
                    help='Virtual canvas height (default 72)')
    args = ap.parse_args()

    engine = OutputEngine(args)
    try:
        engine.run()
    finally:
        pygame.quit()


if __name__ == '__main__':
    main()
