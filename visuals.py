#!/usr/bin/env python3
"""ii — Terminal Visual Engine"""

import os
import pkgutil
import random
import shutil
import signal
import sys
import time

from architecture import CONFIG_PATH, CTRL_PATH, STATUS_PATH, DEFAULTS, discover_modes, load_json, save_json_atomic
from map_engine import load_mappings, render_zones
from modes.base import C, ESC, HIDE, Mode, PALETTES, RESET, SHOW, color_key, mv

BASE = os.path.dirname(__file__)
MODES_DIR = os.path.join(BASE, 'modes')

CLEAR = f'{ESC}[2J{ESC}[H'


def load_cfg():
    cfg = dict(DEFAULTS)
    cfg.update(load_json(CONFIG_PATH, {}))
    return cfg


def load_ctrl():
    return load_json(CTRL_PATH, {})


def write_status(data):
    save_json_atomic(STATUS_PATH, data)


def tsize():
    try:
        s = os.get_terminal_size()
    except OSError:
        s = shutil.get_terminal_size(fallback=(80, 24))
    return s.columns, s.lines


class Engine:
    def __init__(self):
        self.cfg = load_cfg()
        self.ctrl = {}
        self.frame = 0
        self.t0 = time.time()
        self._fps_t = time.time()
        self._fps = 0.0
        self._pal_idx = 0

        self.modes = discover_modes()
        if not self.modes:
            raise RuntimeError('No modes discovered under modes/*.py')
        self.mode_labels = [m.NAME for m in self.modes]
        self.mode = 0
        self.mode_b = 1 if len(self.modes) > 1 else 0
        self.layer_b_enabled = False

        self.w, self.h = tsize()
        self.render_h = max(1, self.h - 1)
        self.buf = [[None] * self.w for _ in range(self.render_h)]
        self.buf_a = [[None] * self.w for _ in range(self.render_h)]
        self.buf_b = [[None] * self.w for _ in range(self.render_h)]

        self._watch_paths = self._collect_watch_paths()
        self._mtimes = self._snapshot_mtimes()
        self._trans_frames = 0
        self._zoom_tmp = [[None] * self.w for _ in range(self.render_h)]

        self._mappings = load_mappings()
        self._map_reload_frame = 0

    def _collect_watch_paths(self):
        paths = [os.path.abspath(__file__)]
        for module_info in pkgutil.iter_modules([MODES_DIR]):
            if module_info.name.startswith('__'):
                continue
            paths.append(os.path.join(MODES_DIR, f'{module_info.name}.py'))
        return paths

    def _snapshot_mtimes(self):
        mtimes = {}
        for path in self._watch_paths:
            try:
                mtimes[path] = os.path.getmtime(path)
            except OSError:
                mtimes[path] = None
        return mtimes

    def _hot_reload_if_needed(self):
        if self.frame % 20 != 0:
            return
        for path, old_mtime in self._mtimes.items():
            try:
                now = os.path.getmtime(path)
            except OSError:
                now = None
            if now != old_mtime:
                sys.stdout.write(SHOW + RESET + CLEAR)
                sys.stdout.flush()
                os.execv(sys.executable, [sys.executable] + sys.argv)

    def _resize_if_needed(self):
        nw, nh = tsize()
        if nw == self.w and nh == self.h:
            return
        self.w, self.h = nw, nh
        self.render_h = max(1, self.h - 1)
        self.buf = [[None] * self.w for _ in range(self.render_h)]
        self.buf_a = [[None] * self.w for _ in range(self.render_h)]
        self.buf_b = [[None] * self.w for _ in range(self.render_h)]
        self._zoom_tmp = [[None] * self.w for _ in range(self.render_h)]
        sys.stdout.write(CLEAR)

    @property
    def pal(self):
        pal = dict(PALETTES[self._pal_idx % len(PALETTES)])
        base = dict(pal)
        pal['p'] = color_key(self.ctrl.get('primary_color', -1), pal['p'])
        pal['s'] = color_key(self.ctrl.get('secondary_color', -1), pal['s'])
        pal['a'] = color_key(self.ctrl.get('accent_color', -1), pal['a'])
        if (pal['p'], pal['s'], pal['a']) != (base['p'], base['s'], base['a']):
            pal['name'] = f'{base["name"]}*'
        return pal

    def _active_mapping(self):
        if not self._mappings:
            return None
        idx = int(self.ctrl.get('mapping', 0) or 0) % len(self._mappings)
        return self._mappings[idx]

    def _bar(self):
        bpm = int(self.cfg.get('bpm', 140))
        sync = ' SYNC' if self.cfg.get('bpm_sync') else ''
        label = self.mode_labels[self.mode]
        layer = ' A+B' if self.layer_b_enabled else ' A'
        if self.layer_b_enabled:
            label = f'{label}+{self.mode_labels[self.mode_b]}'
        map_part = ''
        if self._mappings:
            idx = int(self.ctrl.get('mapping', 0) or 0) % len(self._mappings)
            m = self._mappings[idx]
            mname = m.get('name', '')
            if idx > 0 or mname not in ('DEFAULT', 'default', ''):
                map_part = f' | MAP:{mname}'
        txt = (
            f' ii{layer} | {label} | {self.pal["name"]} | '
            f'{bpm}BPM{sync}{map_part} | {self._fps:.0f}fps | {time.time() - self.t0:06.1f}s '
        )
        return C['dim'] + txt[: self.w].ljust(self.w) + RESET

    @staticmethod
    def _is_non_space(cell):
        return cell is not None and cell[0] != ' '

    def _clear_buf(self, buf):
        for row in buf:
            row[:] = [None] * self.w

    def _composite_ab(self):
        alpha = float(self.ctrl.get('layer_b_alpha', 1.0))
        for y in range(self.render_h):
            row_a = self.buf_a[y]
            row_b = self.buf_b[y]
            row_out = self.buf[y]
            for x in range(self.w):
                b = row_b[x]
                if self._is_non_space(b) and (alpha >= 0.999 or random.random() < alpha):
                    row_out[x] = b
                else:
                    row_out[x] = row_a[x]

    def _render_buffer(self):
        dim = getattr(self, '_master_dim', 1.0)
        apply_dim = dim < 0.999
        out = []
        prev_col = None
        for y in range(self.render_h):
            out.append(mv(0, y))
            for x in range(self.w):
                cell = self.buf[y][x]
                if cell is None or (apply_dim and random.random() > dim):
                    if prev_col is not None:
                        out.append(RESET)
                        prev_col = None
                    out.append(' ')
                else:
                    ch, col = cell
                    if col != prev_col:
                        out.append(col)
                        prev_col = col
                    out.append(ch)
        if prev_col is not None:
            out.append(RESET)
        out.append(mv(0, self.h - 1))
        out.append(self._bar())
        return ''.join(out)

    def _zoom_buf(self, zoom):
        """Resample buf to simulate zoom-in. zoom > 1 magnifies toward center."""
        cx = self.w // 2
        cy = self.render_h // 2
        tmp = self._zoom_tmp
        for y in range(self.render_h):
            sy = int(cy + (y - cy) / zoom)
            row_t = tmp[y]
            if 0 <= sy < self.render_h:
                src = self.buf[sy]
                for x in range(self.w):
                    sx = int(cx + (x - cx) / zoom)
                    row_t[x] = src[sx] if 0 <= sx < self.w else None
            else:
                row_t[:] = [None] * self.w
        for y in range(self.render_h):
            self.buf[y][:] = tmp[y]

    def _apply_transition_overlay(self):
        """Flash burst effect on mode switch."""
        if self._trans_frames <= 0:
            return
        f = self._trans_frames
        pal = self.pal
        if f >= 5:
            for y in range(self.render_h):
                for x in range(self.w):
                    self.buf[y][x] = (random.choice(['█', '▓']), C['white'])
        elif f >= 3:
            for y in range(0, self.render_h, 2):
                for x in range(self.w):
                    if random.random() < 0.75:
                        self.buf[y][x] = (random.choice(['█', '▒']), C[pal['a']])
        else:
            n = self.w * self.render_h // 10
            for _ in range(n):
                x = random.randint(0, self.w - 1)
                y = random.randint(0, self.render_h - 1)
                self.buf[y][x] = ('▓', C['white'])
        self._trans_frames -= 1

    def _flash(self, text):
        if not text:
            return
        cy = self.render_h // 2
        cx = max(0, (self.w - len(text)) // 2)
        col = C[self.pal['a']] if self.frame % 4 < 2 else C[self.pal['p']]
        for x, ch in enumerate(text[: self.w - cx]):
            if ch != ' ':
                self.buf[cy][cx + x] = (ch, col)

    def run(self):
        sys.stdout.write(HIDE + CLEAR)
        prev_mode = self.mode
        try:
            while True:
                self._resize_if_needed()
                self._hot_reload_if_needed()

                self.ctrl = load_ctrl()
                c = self.ctrl

                for key in (
                    'frame_delay', 'strobe_speed', 'glitch_intensity', 'wave_amplitude',
                    'rain_density', 'mode_cycle_frames', 'bpm', 'bpm_sync',
                ):
                    if key in c:
                        self.cfg[key] = c[key]

                self._pal_idx = c.get('palette', 0)
                self.layer_b_enabled = bool(c.get('layer_b_enabled', False))
                merged = dict(self.cfg)
                merged.update(c)
                sym_set = int(merged.get('sym_set', 0) or 0)
                symbol_sets = self.cfg.get('symbol_sets', [])
                if symbol_sets and 0 <= sym_set < len(symbol_sets):
                    syms = symbol_sets[sym_set]
                else:
                    syms = self.cfg.get('symbols', ['#'])
                self._master_dim = float(merged.get('master_dim', 1.0))

                if self.frame % 10 == 0:
                    now = time.time()
                    self._fps = 10 / max(0.001, now - self._fps_t)
                    self._fps_t = now
                    write_status({
                        'frame': self.frame,
                        'fps': round(self._fps, 1),
                        'mode': self.mode,
                        'mode_b': self.mode_b,
                        'layer_b_enabled': self.layer_b_enabled,
                        'mode_label': self.mode_labels[self.mode],
                        'palette': self.pal['name'],
                        'ts': now,
                    })

                if c.get('blackout'):
                    out = []
                    for y in range(self.render_h):
                        out.append(mv(0, y) + ' ' * self.w)
                    out.append(mv(0, self.h - 1) + C['dim'] + ' BLACKOUT '.ljust(self.w) + RESET)
                    sys.stdout.write(''.join(out))
                    sys.stdout.flush()
                    self.frame += 1
                    time.sleep(self.cfg.get('frame_delay', 0.05))
                    continue

                if c.get('auto_cycle', False):
                    cycle = int(self.cfg.get('mode_cycle_frames', 250))
                    if self.frame > 0 and cycle > 0 and self.frame % cycle == 0:
                        self.mode = (self.mode + 1) % len(self.modes)
                else:
                    try:
                        m = int(c.get('mode', self.mode))
                    except Exception:
                        m = self.mode
                    self.mode = max(0, min(len(self.modes) - 1, m))

                try:
                    mb = int(c.get('mode_b', self.mode_b))
                except Exception:
                    mb = self.mode_b
                self.mode_b = max(0, min(len(self.modes) - 1, mb))

                if self.mode != prev_mode:
                    self._clear_buf(self.buf)
                    self._clear_buf(self.buf_a)
                    self._clear_buf(self.buf_b)
                    sys.stdout.write(CLEAR)
                    prev_mode = self.mode
                    self._trans_frames = 6

                # Reload mapping configs every 60 frames
                if self.frame - self._map_reload_frame >= 60:
                    self._mappings = load_mappings()
                    self._map_reload_frame = self.frame

                t_now = time.time() - self.t0
                mapping = self._active_mapping()
                if mapping and render_zones(self.buf, self.w, self.render_h, self.modes, self.mode, mapping, merged, self.pal, syms, t_now, self.frame):
                    pass  # zones rendered directly into self.buf
                else:
                    self.modes[self.mode].render(self.buf_a, self.w, self.render_h, t_now, self.frame, merged, self.pal, syms)
                    if self.layer_b_enabled:
                        self._clear_buf(self.buf_b)
                        self.modes[self.mode_b].render(self.buf_b, self.w, self.render_h, t_now, self.frame, merged, self.pal, syms)
                        self._composite_ab()
                    else:
                        for y in range(self.render_h):
                            self.buf[y][:] = self.buf_a[y][:]
                bpm_val = float(merged.get('bpm', 140))
                beat_phase = (t_now * bpm_val / 60.0) % 1.0
                audio_peak = float(merged.get('audio_peak', 0.0) or 0.0)
                beat_kick = max(0.0, 1.0 - beat_phase * 5.0) if beat_phase < 0.2 else 0.0
                zoom = 1.0 + beat_kick * 0.07 + audio_peak * 0.09
                if zoom > 1.005:
                    self._zoom_buf(zoom)

                if self._trans_frames > 0:
                    self._apply_transition_overlay()

                flash_text = c.get('flash_text', '')
                if c.get('flash_active') and flash_text:
                    self._flash(flash_text)

                sys.stdout.write(self._render_buffer())
                sys.stdout.flush()
                self.frame += 1
                time.sleep(self.cfg.get('frame_delay', 0.05))
        finally:
            sys.stdout.write(SHOW + RESET + CLEAR)
            sys.stdout.flush()


def _quit(sig, frame):
    sys.stdout.write(SHOW + RESET + CLEAR)
    sys.stdout.flush()
    print('[ ii VISUAL ENGINE STOPPED ]')
    sys.exit(0)


if __name__ == '__main__':
    signal.signal(signal.SIGINT, _quit)
    signal.signal(signal.SIGTERM, _quit)
    Engine().run()
