#!/usr/bin/env python3
"""ii — Node Engine"""

import curses, json, locale, math, os, subprocess, sys, time, importlib.util

from architecture import CONFIG_PATH, CTRL_PATH, DEFAULTS, NODES_PATH, STATUS_PATH, WINDOW_PATH, discover_mode_names, load_json, save_json_atomic
from map_engine import load_mappings as _load_mappings
from cues import CueList

try:
    from window import toggle_fullscreen as _toggle_fullscreen
except Exception:
    _toggle_fullscreen = None

try:
    from midi import get_router as _midi_get_router
except Exception:
    _midi_get_router = None

locale.setlocale(locale.LC_ALL, '')

MODE_NAMES = discover_mode_names()
MODE_MAX = max(0, len(MODE_NAMES) - 1)
COLOR_KEYS = ['red','green','white','dim','cyan','yellow','magenta','red_d','green_d','blue']
SYMBOL_SET_NAMES = ['BLOCK','ASCII','DIGIT','GRID','SHAPES','MATH']
PALETTE_NAMES = ['STEEL','ACID','VOID','NEON','ULTRA','DEEP']
PALETTE_ROLES = [
    ('blue',    'cyan',    'white'),
    ('cyan',    'yellow',  'white'),
    ('white',   'dim',     'blue'),
    ('magenta', 'cyan',    'white'),
    ('yellow',  'magenta', 'white'),
    ('blue',    'magenta', 'cyan'),
]
COLOR_ROLES = {'primary_color': 0, 'secondary_color': 1, 'accent_color': 2}
MODE_NODE_PARAMS = {
    0: ['rain_density'],
    1: ['wave_amplitude'],
    2: ['glitch_intensity'],
    3: ['strobe_speed'],
    11: ['rain_density'],
}

PARAM_META_ROWS = [
    ('mode',             'MODE        ', 0,    MODE_MAX,  'int'),
    ('mode_b',           'MODE B      ', 0,    MODE_MAX,  'int'),
    ('layer_b_enabled',  'LAYER B     ', 0,    1,   'bool'),
    ('mode_lock',        'MODE LOCK   ', 0,    1,   'bool'),
    ('palette',          'PALETTE     ', 0,    5,   'palette'),
    ('primary_color',    'PRIMARY     ', -1,   9,   'color'),
    ('secondary_color',  'SECONDARY   ', -1,   9,   'color'),
    ('accent_color',     'ACCENT      ', -1,   9,   'color'),
    ('bpm',              'BPM         ', 40,   240, 'int'),
    ('auto_cycle',       'AUTO CYCLE  ', 0,    1,   'bool'),
    ('mode_cycle_frames','CYCLE FRMS  ', 50,   600, 'int'),
    ('frame_delay',      'SPEED       ', 0.01, 0.20,'f3'),
    ('wave_amplitude',   'WAVE AMP    ', 0.1,  0.5, 'f3'),
    ('glitch_intensity', 'GLITCH      ', 0.0,  1.0, 'f2'),
    ('rain_density',     'DENSITY     ', 0.1,  1.0, 'f2'),
    ('strobe_speed',     'STROBE      ', 1,    10,  'int'),
    ('bpm_sync',         'BPM SYNC    ', 0,    1,   'bool'),
    ('master_dim',       'MASTER DIM  ', 0.0,  1.0, 'f2'),
    ('blackout',         'BLACKOUT    ', 0,    1,   'bool'),
    ('flash_active',     'FLASH       ', 0,    1,   'bool'),
    ('sym_set',          'SYMBOLS     ', 0,    5,   'sym_set'),
    ('layer_b_alpha',    'LAYER MIX   ', 0.0,  1.0, 'f2'),
    ('audio_level',      'MIC LEVEL   ', 0,    1,   'f2'),
    ('audio_peak',       'MIC PEAK    ', 0,    1,   'f2'),
    ('camera4_motion',   'CAM4 MOTION ', 0,    1,   'f2'),
    ('camera4_brightness','CAM4 LIGHT  ', 0,   1,   'f2'),
    ('camera4_online',   'CAM4 ONLINE ', 0,    1,   'bool'),
    ('camera2_motion',   'CAM2 MOTION ', 0,    1,   'f2'),
    ('camera2_brightness','CAM2 LIGHT  ', 0,   1,   'f2'),
    ('camera2_online',   'CAM2 ONLINE ', 0,    1,   'bool'),
]
MAIN_CONTROLS = [
    ('mode',             'MODE        ', 0,    MODE_MAX,  'int'),
    ('mode_b',           'MODE B      ', 0,    MODE_MAX,  'int'),
    ('layer_b_enabled',  'LAYER B     ', 0,    1,   'bool'),
    ('mode_lock',        'MODE LOCK   ', 0,    1,   'bool'),
    ('palette',          'PALETTE     ', 0,    5,   'palette'),
    ('primary_color',    'PRIMARY     ', -1,   9,   'color'),
    ('secondary_color',  'SECONDARY   ', -1,   9,   'color'),
    ('accent_color',     'ACCENT      ', -1,   9,   'color'),
    ('bpm',              'BPM         ', 40,   240, 'int'),
    ('bpm_sync',         'BPM SYNC    ', 0,    1,   'bool'),
    ('auto_cycle',       'AUTO CYCLE  ', 0,    1,   'bool'),
    ('mode_cycle_frames','CYCLE FRMS  ', 50,   600, 'int'),
    ('frame_delay',      'SPEED       ', 0.01, 0.20,'f3'),
    ('master_dim',       'MASTER DIM  ', 0.0,  1.0, 'f2'),
    ('blackout',         'BLACKOUT    ', 0,    1,   'bool'),
    ('flash_active',     'FLASH       ', 0,    1,   'bool'),
    ('sym_set',          'SYMBOLS     ', 0,    5,   'sym_set'),
    ('layer_b_alpha',    'LAYER MIX   ', 0.0,  1.0, 'f2'),
]
MAIN_KEYS = {key for key, _label, _mn, _mx, _kind in MAIN_CONTROLS}
PARAM_META = {key: (label, mn, mx, kind) for key, label, mn, mx, kind in PARAM_META_ROWS}

PRESETS = {
    # F1-F10: quick scene launches — mode + palette + params
    curses.KEY_F1:  {'mode': 0,  'palette': 2, 'rain_density': 0.95, 'frame_delay': 0.04,  'layer_b_enabled': False},
    curses.KEY_F2:  {'mode': 3,  'palette': 4, 'strobe_speed': 1,    'bpm_sync': True,     'layer_b_enabled': False},
    curses.KEY_F3:  {'mode': 7,  'palette': 0, 'frame_delay': 0.03,  'layer_b_enabled': False},
    curses.KEY_F4:  {'mode': 13, 'palette': 3, 'glitch_intensity': 0.75},
    curses.KEY_F5:  {'mode': 8,  'palette': 5, 'wave_amplitude': 0.45},
    curses.KEY_F6:  {'mode': 9,  'palette': 3, 'frame_delay': 0.035},
    curses.KEY_F7:  {'mode': 10, 'palette': 0, 'frame_delay': 0.04},
    curses.KEY_F8:  {'mode': 2,  'palette': 4, 'glitch_intensity': 1.0},
    curses.KEY_F9:  {'mode': 14, 'palette': 1, 'frame_delay': 0.03},
    curses.KEY_F10: {'mode': 17, 'palette': 5, 'layer_b_enabled': True, 'mode_b': 8, 'layer_b_alpha': 0.6},
}


def write_ctrl(state):
    save_json_atomic(CTRL_PATH, state)


def read_status():
    try:
        with open(STATUS_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def load_graph():
    spec = importlib.util.spec_from_file_location('nodes', NODES_PATH)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return getattr(mod, 'GRAPH', [])


def pbar(val, mn, mx, width=12):
    try:
        filled = max(0, min(width, round((float(val)-float(mn)) / (float(mx)-float(mn)) * width)))
    except Exception:
        filled = 0
    return '█'*filled + '░'*(width-filled)


def palette_name(val):
    try:
        idx = int(val) % len(PALETTE_NAMES)
        return f'{idx}:{PALETTE_NAMES[idx]}'
    except Exception:
        return str(val)


def color_key_for(value, palette=0, role=None):
    if isinstance(value, str) and value in COLOR_KEYS:
        return value
    try:
        idx = int(value)
    except Exception:
        idx = -1
    if idx < 0:
        role_idx = COLOR_ROLES.get(role)
        if role_idx is None:
            return None
        try:
            pal_idx = int(palette) % len(PALETTE_ROLES)
        except Exception:
            pal_idx = 0
        return PALETTE_ROLES[pal_idx][role_idx]
    return COLOR_KEYS[idx % len(COLOR_KEYS)]


def color_label(value, palette=0, role=None):
    key = color_key_for(value, palette, role)
    if key is None:
        return 'PAL'
    try:
        prefix = 'PAL:' if not isinstance(value, str) and int(value) < 0 else ''
    except Exception:
        prefix = ''
    return prefix + key.upper()


def fmt(val, kind):
    try:
        if kind == 'int':     return str(int(val))
        if kind == 'palette': return palette_name(val)
        if kind == 'color':   return color_label(val)
        if kind == 'sym_set': return SYMBOL_SET_NAMES[int(val) % len(SYMBOL_SET_NAMES)]
        if kind == 'f3':      return f'{float(val):.3f}'
        if kind == 'f2':      return f'{float(val):.2f}'
        if kind == 'bool':    return 'ON' if val else 'OFF'
    except Exception:
        pass
    return str(val)


class NodeEngine:
    def __init__(self, stdscr):
        self.scr       = stdscr
        self.cfg       = load_json(CONFIG_PATH, {})
        self.t0        = time.time()
        self.frame     = 0
        self.state     = dict(DEFAULTS)
        self.overrides = {}
        self.graph     = []
        self.graph_err = None
        self.focus     = 0
        self.tap_times = []
        self._visuals_launch_msg = ''
        self._visuals_launch_attempted = False
        self._mode_lock_forced_auto_cycle = False
        self._nmtime   = 0.0
        self._mappings = _load_mappings()
        self._map_idx  = int(load_json(CTRL_PATH, {}).get('mapping', 0))
        self.cues      = CueList()
        self.midi      = None
        self.midi_values = {}
        if _midi_get_router is not None:
            try:
                self.midi = _midi_get_router()
            except Exception:
                pass
        self._reload()
        self._init_colors()

    def _visuals_alive(self):
        st = read_status()
        return bool(st and (time.time() - st.get('ts', 0)) < 2.0)

    def _visuals_launch_command(self):
        return [sys.executable, WINDOW_PATH]

    def _ensure_visuals_running(self):
        if self._visuals_alive() or self._visuals_launch_attempted:
            return
        self._visuals_launch_attempted = True
        if self.cfg.get('autostart_visuals', True) is False:
            self._visuals_launch_msg = 'autostart disabled in config.json'
            return
        cmd = self._visuals_launch_command()
        if not cmd:
            self._visuals_launch_msg = 'window launcher unavailable'
            return
        try:
            subprocess.Popen(cmd, cwd=os.path.dirname(WINDOW_PATH))
            self._visuals_launch_msg = 'launching visuals window...'
        except Exception as exc:
            self._visuals_launch_msg = f'launch failed: {exc}'

    def _init_colors(self):
        curses.start_color(); curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_RED,    -1)
        curses.init_pair(2, curses.COLOR_GREEN,  -1)
        curses.init_pair(3, curses.COLOR_WHITE,  -1)
        curses.init_pair(4, curses.COLOR_BLACK,  curses.COLOR_WHITE)
        curses.init_pair(5, curses.COLOR_YELLOW, -1)
        curses.init_pair(6, curses.COLOR_CYAN,   -1)
        curses.init_pair(7, curses.COLOR_MAGENTA,-1)
        curses.init_pair(8, curses.COLOR_BLUE,   -1)

    def _reload(self):
        try:
            self.graph     = load_graph()
            self.graph_err = None
            self._nmtime   = os.path.getmtime(NODES_PATH)
        except Exception as e:
            self.graph_err = str(e)[:80]

    def run(self):
        curses.curs_set(0)
        self.scr.nodelay(True)
        self.scr.timeout(50)
        self._ensure_visuals_running()

        while True:
            key = self.scr.getch()
            if not self._handle(key):
                break

            # Hot-reload nodes.py on save
            try:
                if os.path.getmtime(NODES_PATH) != self._nmtime:
                    self._reload()
                    self.focus = min(self.focus, max(0, self._total_selectable()-1))
            except Exception:
                pass

            # Evaluate graph
            t          = time.time() - self.t0
            bpm        = float(self.state.get('bpm', 140))
            node_state = {}

            if self.graph and not self.graph_err:
                for node in self.graph:
                    try:
                        bpm = float(node_state.get('bpm', self.state.get('bpm', 140)))
                        node.evaluate(t, bpm, self.frame, node_state)
                    except Exception as e:
                        self.graph_err = str(e)[:80]
                        break

            # Pull MIDI values (non-blocking)
            if self.midi:
                self.midi_values = dict(self.midi.values)

            # Merge: DEFAULTS < node_state < MIDI < manual overrides
            merged = dict(DEFAULTS)
            merged.update(node_state)
            merged.update(self.midi_values)
            merged.update(self.overrides)
            if 'mode' in self.overrides:
                merged['mode_lock'] = True
            self.state = merged

            write_ctrl(self.state)
            self._draw(t, node_state)
            self.frame += 1

    def _handle(self, key):
        if key == -1:
            return True

        ov = self.overrides
        n  = len(MODE_NAMES)

        if   key in (ord('q'), ord('Q')): return False
        elif key == ord('!'):  self.overrides = {'blackout': True}
        elif key in (ord('b'), ord('B')):
            ov['blackout'] = not ov.get('blackout', self.state.get('blackout', False))
        elif key == ord(' '):
            ov['flash_active'] = not ov.get('flash_active', self.state.get('flash_active', False))
        elif key in (ord('s'), ord('S')):
            ov['bpm_sync'] = not ov.get('bpm_sync', self.state.get('bpm_sync', True))
        elif key in (ord('a'), ord('A')):
            ov['auto_cycle'] = not ov.get('auto_cycle', self.state.get('auto_cycle', False))
        elif key in (ord('x'), ord('X')):
            ov['layer_b_enabled'] = not ov.get('layer_b_enabled', self.state.get('layer_b_enabled', False))
        elif key in (ord('m'), ord('M')):
            self._toggle_mode_lock()
        elif key in (ord('g'), ord('G')):
            self._cycle_mapping()
        elif key in (ord('p'), ord('P')):
            ov['palette'] = (int(self.state.get('palette', 0)) + 1) % 6
        elif key in (ord('f'), ord('F')):
            ov['sym_set'] = (int(self.state.get('sym_set', 0)) + 1) % len(SYMBOL_SET_NAMES)
        elif key in (ord('t'), ord('T')):
            self._tap_bpm()
        elif key in (9, ord('v'), ord('V')):
            self._jump_focus_area()
        elif key in (10, 13, curses.KEY_ENTER):
            self._edit_flash_text()
        elif key == ord('['):  self._set_manual_mode(int(self.state.get('mode', 0)) - 1)
        elif key == ord(']'):  self._set_manual_mode(int(self.state.get('mode', 0)) + 1)
        elif key == curses.KEY_UP:
            self.focus = (self.focus - 1) % self._total_selectable()
        elif key == curses.KEY_DOWN:
            self.focus = (self.focus + 1) % self._total_selectable()
        elif key == curses.KEY_LEFT:
            self._adjust_selected(-1)
        elif key == curses.KEY_RIGHT:
            self._adjust_selected(1)
        elif key in (ord('w'), ord('W')):
            if _toggle_fullscreen:
                _toggle_fullscreen()
        elif key == ord(','):
            self.cues.prev()
            self.overrides.update(self.cues.current_params())
        elif key == ord('.'):
            self.cues.advance()
            self.overrides.update(self.cues.current_params())
        elif key in (ord('z'), ord('Z')):
            self._store_cue()
        elif key in (ord('c'), ord('C')):
            self._clear_selected_override()
        elif key in PRESETS:
            self._apply_preset(PRESETS[key])
        elif key == curses.KEY_RESIZE: self.scr.clear()
        elif ord('0') <= key <= ord('9'):
            m = key - ord('0')
            if m < n: self._set_manual_mode(m)
        return True

    def _set_manual_mode(self, mode):
        self.overrides['mode'] = int(mode) % len(MODE_NAMES)
        self.overrides['mode_lock'] = True
        if self.overrides.get('auto_cycle', self.state.get('auto_cycle', False)):
            self.overrides['auto_cycle'] = False
            self._mode_lock_forced_auto_cycle = True

    def _toggle_mode_lock(self):
        if 'mode' in self.overrides or self.overrides.get('mode_lock'):
            self.overrides.pop('mode', None)
            self.overrides.pop('mode_lock', None)
            if getattr(self, '_mode_lock_forced_auto_cycle', False):
                self.overrides.pop('auto_cycle', None)
                self._mode_lock_forced_auto_cycle = False
        else:
            self._set_manual_mode(self.state.get('mode', 0))

    def _cycle_mapping(self):
        self._mappings = _load_mappings()
        if not self._mappings:
            return
        self._map_idx = (self._map_idx + 1) % len(self._mappings)
        self.overrides['mapping'] = self._map_idx

    def _apply_preset(self, preset):
        self.overrides.update(preset)
        if 'mode' in preset:
            self.overrides['mode'] = int(preset['mode']) % len(MODE_NAMES)
            self.overrides['mode_lock'] = True
            if self.overrides.get('auto_cycle', self.state.get('auto_cycle', False)):
                self.overrides['auto_cycle'] = False
                self._mode_lock_forced_auto_cycle = True

    def _tap_bpm(self):
        now = time.time()
        self.tap_times = [t for t in self.tap_times if now - t < 4.0]
        self.tap_times.append(now)
        self.tap_times = self.tap_times[-8:]
        if len(self.tap_times) >= 2:
            intervals = [b - a for a, b in zip(self.tap_times, self.tap_times[1:])]
            avg = sum(intervals) / len(intervals)
            if avg > 0:
                self.overrides['bpm'] = max(40, min(240, round(60 / avg)))
                self.overrides['bpm_sync'] = True

    def _adjust_selected(self, direction):
        key = self._selected_key()
        if not key:
            return
        _label, mn, mx, kind = PARAM_META.get(key, (key, 0, 1, 'f2'))
        current = self.overrides.get(key, self.state.get(key, DEFAULTS.get(key, mn)))

        if key == 'mode_lock':
            self._toggle_mode_lock()
            return
        if kind == 'bool':
            self.overrides[key] = not bool(current)
            return
        if kind == 'sym_set':
            self.overrides[key] = (int(float(current) + 0.5) + direction) % len(SYMBOL_SET_NAMES)
            return
        if kind == 'color':
            if isinstance(current, str) and current in COLOR_KEYS:
                value = COLOR_KEYS.index(current) + direction
            else:
                value = int(current) + direction
            if value < -1:
                value = len(COLOR_KEYS) - 1
            elif value >= len(COLOR_KEYS):
                value = -1
            self.overrides[key] = value
            return

        step = 1
        if kind == 'f3':
            step = 0.005
        elif kind == 'f2':
            step = 0.05
        elif key == 'mode_cycle_frames':
            step = 25

        value = float(current) + direction * step
        if key == 'mode':
            self._set_manual_mode(value)
            return
        if key == 'mode_b':
            self.overrides['mode_b'] = int(value) % len(MODE_NAMES)
            return
        if key == 'palette':
            value = int(value) % (len(MODE_NAMES) if key == 'mode' else 6)
        else:
            value = max(mn, min(mx, value))
            if kind == 'int':
                value = int(round(value))

        self.overrides[key] = value

    def _selected_key(self):
        if self.focus < len(MAIN_CONTROLS):
            return MAIN_CONTROLS[self.focus][0]

        node_idx = self.focus - len(MAIN_CONTROLS)
        nodes = self._node_items()
        if 0 <= node_idx < len(nodes):
            _graph_idx, node = nodes[node_idx]
            return getattr(node, 'param', None)
        return None

    def _node_items(self):
        return [
            (idx, node)
            for idx, node in enumerate(self.graph)
            if getattr(node, 'param', None) not in MAIN_KEYS
        ]

    def _total_selectable(self):
        return max(1, len(MAIN_CONTROLS) + len(self._node_items()))

    def _jump_focus_area(self):
        nodes = self._node_items()
        if self.focus < len(MAIN_CONTROLS) and nodes:
            active_idx = self._active_node_index(nodes, self.state)
            self.focus = len(MAIN_CONTROLS) + (active_idx if active_idx is not None else 0)
        else:
            self.focus = 0

    def _clear_selected_override(self):
        key = self._selected_key()
        if key == 'mode':
            self.overrides.pop('mode', None)
            self.overrides.pop('mode_lock', None)
        elif key == 'mode_lock':
            self.overrides.pop('mode', None)
            self.overrides.pop('mode_lock', None)
        elif key:
            self.overrides.pop(key, None)

    def _node_desc(self, node):
        name = node.__class__.__name__
        inner = getattr(node, 'node', None)
        if inner is not None and name in ('Out', 'IntOut', 'BoolOut'):
            return self._node_desc(inner)

        data = getattr(node, '__dict__', {})
        parts = []
        for key, val in data.items():
            if key.startswith('_') or key in ('node', 'nodes', 'trigger', 'gate', 'a', 'b', 'alpha'):
                continue
            if isinstance(val, float):
                parts.append(f'{key}={val:.3g}')
            elif isinstance(val, (int, str, bool)):
                parts.append(f'{key}={val}')
            elif isinstance(val, list):
                shown = ','.join(str(v) for v in val[:6])
                suffix = ',...' if len(val) > 6 else ''
                parts.append(f'{key}=[{shown}{suffix}]')
        return name + (f"({', '.join(parts)})" if parts else '')

    def _fmt_value(self, key, val, kind, state):
        if kind == 'color':
            return color_label(val, state.get('palette', 0), key)
        return fmt(val, kind)

    def _color_attr(self, key, val, state, fallback):
        color = color_key_for(val, state.get('palette', 0), key)
        attrs = {
            'red': curses.color_pair(1)|curses.A_BOLD,
            'green': curses.color_pair(2)|curses.A_BOLD,
            'white': curses.color_pair(3)|curses.A_BOLD,
            'dim': curses.A_DIM,
            'cyan': curses.color_pair(6)|curses.A_BOLD,
            'yellow': curses.color_pair(5)|curses.A_BOLD,
            'magenta': curses.color_pair(7)|curses.A_BOLD,
            'red_d': curses.color_pair(1),
            'green_d': curses.color_pair(2),
            'blue': curses.color_pair(8)|curses.A_BOLD,
        }
        return attrs.get(color, fallback)

    def _bar_text(self, key, val, mn, mx, kind):
        if kind == 'color':
            return '████████████'
        return pbar(val, mn, mx)

    def _active_node_index(self, nodes, state):
        try:
            mode = int(state.get('mode', 0)) % len(MODE_NAMES)
        except Exception:
            mode = 0
        for param in MODE_NODE_PARAMS.get(mode, []):
            for idx, (_graph_idx, node) in enumerate(nodes):
                if getattr(node, 'param', None) == param:
                    return idx
        return None

    def _edit_flash_text(self):
        h, w = self.scr.getmaxyx()
        prompt = ' FLASH TEXT > '
        current = str(self.state.get('flash_text', 'MOCT 7'))
        curses.echo()
        curses.curs_set(1)
        self.scr.nodelay(False)
        self.scr.timeout(-1)
        try:
            self.scr.move(max(0, h-2), 0)
            self.scr.clrtoeol()
            self.scr.addstr(max(0, h-2), 0, prompt + current)
            self.scr.move(max(0, h-2), min(w-1, len(prompt)))
            raw = self.scr.getstr(max(0, h-2), len(prompt), max(1, w-len(prompt)-1))
            text = raw.decode(errors='ignore').strip()
            if text:
                self.overrides['flash_text'] = text
                self.overrides['flash_active'] = True
        except curses.error:
            pass
        finally:
            curses.noecho()
            curses.curs_set(0)
            self.scr.nodelay(True)
            self.scr.timeout(50)

    def _store_cue(self):
        h, w = self.scr.getmaxyx()
        prompt = ' CUE NAME > '
        default = self.cues.name()
        curses.echo()
        curses.curs_set(1)
        self.scr.nodelay(False)
        self.scr.timeout(-1)
        try:
            self.scr.move(max(0, h - 2), 0)
            self.scr.clrtoeol()
            self.scr.addstr(max(0, h - 2), 0, prompt + default)
            self.scr.move(max(0, h - 2), min(w - 1, len(prompt)))
            raw = self.scr.getstr(max(0, h - 2), len(prompt), max(1, w - len(prompt) - 1))
            name = raw.decode(errors='ignore').strip() or default
            self.cues.store(name, self.overrides)
        except curses.error:
            pass
        finally:
            curses.noecho()
            curses.curs_set(0)
            self.scr.nodelay(True)
            self.scr.timeout(50)

    def _draw(self, t, node_state):
        scr = self.scr
        h, w = scr.getmaxyx()
        s    = self.state

        R   = curses.color_pair(1)|curses.A_BOLD
        G   = curses.color_pair(2)|curses.A_BOLD
        N   = curses.color_pair(3)
        Y   = curses.color_pair(5)|curses.A_BOLD
        CY  = curses.color_pair(6)|curses.A_BOLD
        D   = curses.A_DIM
        MG  = curses.color_pair(7)|curses.A_BOLD
        BL  = curses.color_pair(8)|curses.A_BOLD
        BOLD = curses.A_BOLD
        REV  = curses.color_pair(4)|curses.A_BOLD

        scr.erase()

        def put(y, x, text, attr=N):
            if 0 <= y < h-1 and 0 <= x < w-1:
                try: scr.addstr(y, x, str(text)[:w-x-1], attr)
                except curses.error: pass

        def div(y, attr=D):
            if 0 <= y < h-1:
                put(y, 0, '─' * max(0, w - 1), attr)

        def meter(value, width=16):
            try: v = max(0.0, min(1.0, float(value)))
            except Exception: v = 0.0
            filled = int(round(v * width))
            return '█' * filled + '░' * (width - filled)

        st    = read_status()
        alive = st and (time.time() - st.get('ts', 0)) < 2.0
        elapsed    = f'{int(t//60):02d}:{int(t%60):02d}'
        mode_idx   = int(s.get('mode',   0)) % len(MODE_NAMES)
        mode_b_idx = int(s.get('mode_b', 0)) % len(MODE_NAMES)
        layer      = bool(s.get('layer_b_enabled', False))
        alpha      = float(s.get('layer_b_alpha', 1.0))
        n_ov       = len(self.overrides)
        sym_idx    = int(s.get('sym_set', 0)) % len(SYMBOL_SET_NAMES)

        # ── Row 0: header ────────────────────────────────────────
        put(0, 1, 'ii  VJ DECK', R|BOLD)
        if alive:
            put(0, 18, f'● {st.get("fps",0):.0f}fps', G)
        else:
            msg = self._visuals_launch_msg or 'OFFLINE'
            put(0, 18, msg[:max(6, w - 38)], R)
        put(0, max(1, w - 18), f'{len(self.graph)} nodes  {elapsed}', CY)
        div(1)

        # ── Row 2: Mode A / crossfader / Mode B ─────────────────
        a_name = f'{mode_idx}:{MODE_NAMES[mode_idx]}'
        put(2, 1, 'A', BL|BOLD)
        put(2, 3, a_name, G|BOLD)

        if layer:
            b_name = f'{mode_b_idx}:{MODE_NAMES[mode_b_idx]}'
            a_len  = len(a_name) + 4
            b_len  = len(b_name) + 4
            cf_w   = max(8, min(20, w - a_len - b_len - 8))
            cf_x   = a_len + 2
            pos    = max(0, min(cf_w, int(alpha * cf_w)))
            bar    = '█' * pos + '░' * (cf_w - pos)
            put(2, cf_x,             '╡', D)
            put(2, cf_x + 1,         bar, CY)
            put(2, cf_x + 1 + cf_w, '╞', D)
            put(2, cf_x + cf_w + 3, 'B', BL|BOLD)
            put(2, cf_x + cf_w + 5, b_name, CY)

        rinfo = f'{palette_name(s.get("palette",0))}  {int(s.get("bpm",140))}BPM  {SYMBOL_SET_NAMES[sym_idx]}'
        put(2, max(2, w - len(rinfo) - 1), rinfo, Y)

        # ── Row 3: status flags ──────────────────────────────────
        flags = []
        if s.get('bpm_sync'):     flags.append('SYNC')
        if s.get('mode_lock'):    flags.append('LOCK')
        if s.get('auto_cycle'):   flags.append('CYCLE')
        if layer:                 flags.append(f'MIX {alpha:.0%}')
        if s.get('flash_active'): flags.append('FLASH')
        if s.get('blackout'):     flags.append('■ BLACKOUT')
        if n_ov:                  flags.append(f'OVR:{n_ov}')
        if self._mappings:
            midx = self._map_idx % len(self._mappings)
            mname = self._mappings[midx].get('name', f'MAP{midx}')
            if midx > 0 or mname not in ('DEFAULT', 'default', ''):
                flags.append(f'MAP:{mname}')
        midi = self.midi
        if midi and midi.port_label:
            flags.append(f'MIDI:{midi.port_label[:16]}')
        elif midi and midi.error:
            flags.append(f'MIDI:ERR')
        if self.graph_err:
            put(3, 1, f'NODE ERR: {self.graph_err[:w-12]}', R)
        else:
            put(3, 1, '  '.join(flags) if flags else '', D)
        div(4)

        # ── Rows 5-8: sources ────────────────────────────────────
        put(5, 1, 'SOURCES', N|BOLD)
        src_rows = [
            ('MIC  ', 'audio_level',     'audio_peak',          None),
            ('CAM4 ', 'camera4_motion',  'camera4_brightness',  'camera4_online'),
            ('CAM2 ', 'camera2_motion',  'camera2_brightness',  'camera2_online'),
        ]
        for si, (lbl, ak, bk, ok_k) in enumerate(src_rows):
            y  = 6 + si
            av = float(s.get(ak, 0))
            bv = float(s.get(bk, 0))
            ok = True if ok_k is None else bool(s.get(ok_k))
            put(y, 1,  lbl, N)
            put(y, 7,  meter(av, 14), G if ok else D)
            put(y, 22, f'{av:.2f}', CY if ok else D)
            put(y, 27, meter(bv, 10), Y if ok else D)
            put(y, 38, f'{bv:.2f}', CY if ok else D)
            if ok_k:
                put(y, 43, 'ON' if ok else 'OFF', G if ok else R)
        div(9)

        # ── Layout for controls + node panel ────────────────────
        left_x  = 1
        right_x = max(42, w // 2 + 2)
        top     = 10

        # Reserve bottom for mode matrix + footer
        slot_w  = 8
        per_row = max(5, (w - 2) // slot_w)
        n_mat   = max(1, math.ceil(len(MODE_NAMES) / per_row))
        # Bottom rows (fixed): footer=h-2, div=h-3, matrix=h-3-n_mat..h-4, div=h-4-n_mat
        ctrl_bot   = h - 4 - n_mat   # exclusive upper bound for controls
        max_rows   = max(4, ctrl_bot - top - 2)

        put(top, left_x,  'CONTROLS', N|BOLD)
        put(top, right_x, 'NODE CHAIN', N|BOLD)

        # Controls column (scrollable)
        if self.focus < len(MAIN_CONTROLS):
            start = max(0, min(self.focus - max_rows + 1, len(MAIN_CONTROLS) - max_rows))
        else:
            start = 0
        for ri, (key, label, mn, mx, kind) in enumerate(MAIN_CONTROLS[start:start + max_rows]):
            idx = start + ri
            y   = top + 2 + ri
            if y >= ctrl_bot:
                break
            sel   = self.focus == idx
            final = s.get(key, DEFAULTS.get(key, 0))
            is_ov = key in self.overrides
            src   = 'OVR' if is_ov else ('NODE' if key in node_state else 'AUTO')
            attr  = REV if sel else (Y if is_ov else N)
            value = self._fmt_value(key, final, kind, s)
            if key in ('mode', 'mode_b'):
                m = int(final) % len(MODE_NAMES)
                value = f'{m}:{MODE_NAMES[m]}'
            put(y, left_x,      '>' if sel else ' ', attr)
            put(y, left_x + 2,  label.strip().ljust(12), attr)
            put(y, left_x + 16, value[:16].ljust(16), Y if is_ov else G)
            if kind not in ('bool', 'palette', 'color', 'sym_set'):
                put(y, left_x + 34, pbar(final, mn, mx, 10), D)
            put(y, left_x + 46, src, Y if is_ov else D)

        # Node panel (right column)
        nodes = self._node_items()
        nr    = top + 2
        if nodes:
            if self.focus >= len(MAIN_CONTROLS):
                sel_n = min(self.focus - len(MAIN_CONTROLS), len(nodes) - 1)
            else:
                sel_n = self._active_node_index(nodes, s) or 0
            gi, node = nodes[sel_n]
            param    = getattr(node, 'param', f'node_{gi}')
            _lbl, mn, mx, kind = PARAM_META.get(param, (param, 0, 1, 'f2'))
            final    = s.get(param, DEFAULTS.get(param, node_state.get(param, 0)))
            node_val = node_state.get(param)
            is_sel   = self.focus >= len(MAIN_CONTROLS)
            put(nr,     right_x, f'{sel_n+1}/{len(nodes)}  #{gi:02d}', REV if is_sel else CY)
            put(nr + 2, right_x, 'TARGET', D)
            put(nr + 2, right_x + 8, param[:max(8, w - right_x - 10)], G)
            put(nr + 3, right_x, 'VALUE ', D)
            put(nr + 3, right_x + 8, self._fmt_value(param, final, kind, s), Y if param in self.overrides else G)
            if node_val is not None:
                put(nr + 4, right_x, 'NODE  ', D)
                put(nr + 4, right_x + 8, self._fmt_value(param, node_val, kind, s), CY)
            put(nr + 5, right_x, 'PATCH ', D)
            put(nr + 5, right_x + 8, self._node_desc(node)[:max(8, w - right_x - 10)], N)
            if kind not in ('bool', 'color', 'sym_set'):
                bw = min(20, max(8, w - right_x - 2))
                put(nr + 7, right_x, pbar(final, mn, mx, bw), D)
        else:
            put(nr, right_x, 'No node controls in GRAPH', D)

        # ── Cue panel (right column, below node panel) ───────────
        cue_top = nr + 9
        if cue_top < ctrl_bot - 2 and self.cues.cues:
            put(cue_top, right_x, f'CUES  {self.cues.idx+1}/{len(self.cues.cues)}', N | BOLD)
            visible = min(5, ctrl_bot - cue_top - 2)
            start_c = max(0, self.cues.idx - visible // 2)
            start_c = min(start_c, max(0, len(self.cues.cues) - visible))
            for ci in range(visible):
                qi = start_c + ci
                if qi >= len(self.cues.cues):
                    break
                cname = self.cues.cues[qi].get('name', f'CUE{qi+1}')[:max(8, w - right_x - 4)]
                marker = '>' if qi == self.cues.idx else ' '
                attr = REV if qi == self.cues.idx else D
                put(cue_top + 1 + ci, right_x, f'{marker}{qi+1:2d} {cname}', attr)

        # ── Mode matrix ──────────────────────────────────────────
        mat_div_y = h - 4 - n_mat
        div(mat_div_y)
        for mi, name in enumerate(MODE_NAMES):
            gy = mat_div_y + 1 + mi // per_row
            gx = 1 + (mi % per_row) * slot_w
            if gy >= h - 3:
                break
            label = f'{mi}:{name[:4]}'.ljust(slot_w - 1)
            if mi == mode_idx:
                mattr = REV
            elif mi == mode_b_idx and layer:
                mattr = CY
            else:
                mattr = D
            put(gy, gx, label, mattr)

        # ── Footer ───────────────────────────────────────────────
        div(h - 3)
        put(h - 2, 1,
            '[]mode  P pal  F font  T tap  X layer  M lock  G map  A cycle  B black  ENTER text  TAB node  C clear  W full  ,/. cue  Z store  Q quit'[:w-2],
            D)

        scr.refresh()


def main(stdscr):
    NodeEngine(stdscr).run()


if __name__ == '__main__':
    curses.wrapper(main)
