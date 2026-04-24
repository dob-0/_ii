#!/usr/bin/env python3
"""MOCT 7 | ii — Node Engine"""

import curses, json, locale, os, time, importlib.util

locale.setlocale(locale.LC_ALL, '')

BASE        = os.path.dirname(__file__)
CTRL_PATH   = os.path.join(BASE, 'control.json')
STATUS_PATH = os.path.join(BASE, 'status.json')
NODES_PATH  = os.path.join(BASE, 'nodes.py')

DEFAULTS = {
    'mode':0, 'auto_cycle':False, 'blackout':False,
    'flash_active':False, 'bpm_sync':True, 'palette':0,
    'flash_text':'MOCT 7',
    'frame_delay':0.05, 'strobe_speed':2, 'glitch_intensity':0.4,
    'wave_amplitude':0.35, 'rain_density':0.7,
    'mode_cycle_frames':250, 'bpm':140,
}

MODE_NAMES = [
    'RAIN','WAVE','GLITCH','STROBE','LOGO','PULSE','TEXT',
    'TUNNEL','PLASMA','VORTEX','GRID','PARTICLES',
    'SCANNER','STORM','CUBE','SHOCKWAVE','NOISE',
]

PARAMS_DISPLAY = [
    ('mode',             'MODE        ', 0,    16,  'int'),
    ('palette',          'PALETTE     ', 0,    5,   'int'),
    ('bpm',              'BPM         ', 40,   240, 'int'),
    ('frame_delay',      'SPEED       ', 0.01, 0.20,'f3'),
    ('wave_amplitude',   'WAVE AMP    ', 0.1,  0.5, 'f3'),
    ('glitch_intensity', 'GLITCH      ', 0.0,  1.0, 'f2'),
    ('rain_density',     'DENSITY     ', 0.1,  1.0, 'f2'),
    ('strobe_speed',     'STROBE      ', 1,    10,  'int'),
    ('bpm_sync',         'BPM SYNC    ', 0,    1,   'bool'),
    ('blackout',         'BLACKOUT    ', 0,    1,   'bool'),
    ('flash_active',     'FLASH       ', 0,    1,   'bool'),
]


def write_ctrl(state):
    tmp = CTRL_PATH + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(state, f)
    os.replace(tmp, CTRL_PATH)


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


def fmt(val, kind):
    try:
        if kind == 'int':  return str(int(val))
        if kind == 'f3':   return f'{float(val):.3f}'
        if kind == 'f2':   return f'{float(val):.2f}'
        if kind == 'bool': return 'ON' if val else 'OFF'
    except Exception:
        pass
    return str(val)


class NodeEngine:
    def __init__(self, stdscr):
        self.scr       = stdscr
        self.t0        = time.time()
        self.frame     = 0
        self.state     = dict(DEFAULTS)
        self.overrides = {}
        self.graph     = []
        self.graph_err = None
        self._nmtime   = 0.0
        self._reload()
        self._init_colors()

    def _init_colors(self):
        curses.start_color(); curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_RED,    -1)
        curses.init_pair(2, curses.COLOR_GREEN,  -1)
        curses.init_pair(3, curses.COLOR_WHITE,  -1)
        curses.init_pair(4, curses.COLOR_BLACK,  curses.COLOR_WHITE)
        curses.init_pair(5, curses.COLOR_YELLOW, -1)
        curses.init_pair(6, curses.COLOR_CYAN,   -1)

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

        while True:
            key = self.scr.getch()
            if not self._handle(key):
                break

            # Hot-reload nodes.py on save
            try:
                if os.path.getmtime(NODES_PATH) != self._nmtime:
                    self._reload()
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

            # Merge: DEFAULTS < node_state < manual overrides
            merged = dict(DEFAULTS)
            merged.update(node_state)
            merged.update(self.overrides)
            self.state = merged

            write_ctrl(self.state)
            self._draw(t, node_state)
            self.frame += 1

    def _handle(self, key):
        ov = self.overrides
        n  = len(MODE_NAMES)

        if   key == ord('q'):  return False
        elif key == ord('!'):  self.overrides = {}
        elif key == ord('b'):  ov['blackout']     = not ov.get('blackout', False)
        elif key == ord(' '):  ov['flash_active']  = not ov.get('flash_active', False)
        elif key == ord('s'):  ov['bpm_sync']      = not ov.get('bpm_sync',
                                                      self.state.get('bpm_sync', True))
        elif key == ord('['):  ov['mode'] = (self.state.get('mode', 0) - 1) % n
        elif key == ord(']'):  ov['mode'] = (self.state.get('mode', 0) + 1) % n
        elif key == curses.KEY_RESIZE: self.scr.clear()
        elif ord('0') <= key <= ord('9'):
            m = key - ord('0')
            if m < n: ov['mode'] = m
        return True

    def _draw(self, t, node_state):
        scr = self.scr
        h, w = scr.getmaxyx()
        s    = self.state

        R  = curses.color_pair(1)|curses.A_BOLD
        G  = curses.color_pair(2)|curses.A_BOLD
        N  = curses.color_pair(3)
        Y  = curses.color_pair(5)|curses.A_BOLD
        CY = curses.color_pair(6)
        D  = curses.A_DIM

        scr.erase()

        def put(y, x, text, attr=N):
            if 0 <= y < h-1 and 0 <= x < w-1:
                try: scr.addstr(y, x, str(text)[:w-x-1], attr)
                except curses.error: pass

        def hline(y, l='╠', r='╣', fill='═'):
            if 0 <= y < h-1:
                try: scr.addstr(y, 0, l+fill*(w-2)+r, R)
                except curses.error: pass

        def brow(y):
            put(y, 0, '║', R); put(y, w-1, '║', R)

        # ── header ──────────────────────────────────────────────────────────
        row = 0
        try: scr.addstr(0, 0, '╔'+'═'*(w-2)+'╗', R)
        except curses.error: pass
        row = 1; brow(row)
        title = 'MOCT 7  ·  ii  NODE ENGINE'
        put(row, (w-len(title))//2, title, R)
        row = 2; hline(row)

        # ── visuals.py status ────────────────────────────────────────────────
        row = 3; brow(row)
        st    = read_status()
        alive = st and (time.time()-st.get('ts', 0)) < 2.0
        if alive:
            put(row, 2, '● LIVE', G)
            put(row, 10,
                f" F:{st.get('frame',0):>7}  {st.get('fps',0):.0f}fps"
                f"  {st.get('mode_label','?'):<10}  {st.get('palette','')}", CY)
        else:
            put(row, 2, '○ visuals.py not running  →  python3 visuals.py', R)
        row = 4; hline(row)

        # ── nodes.py status ──────────────────────────────────────────────────
        row = 5; brow(row)
        elapsed = f'{int(t//60):02d}:{int(t%60):02d}'
        if self.graph_err:
            put(row, 2, f'● ERR  {self.graph_err[:w-10]}', R)
        else:
            put(row, 2, '● NODES', G)
            put(row, 11, f" {len(self.graph)} nodes   t {elapsed}", CY)
        n_ov = len(self.overrides)
        if n_ov:
            tag = f' OVERRIDE:{n_ov}  ! to clear '
            put(row, w-len(tag)-2, tag, Y)
        row = 6; hline(row)

        # ── column headers ───────────────────────────────────────────────────
        row = 7; brow(row)
        put(row, 2,  'PARAM',      N|curses.A_BOLD)
        put(row, 18, 'NODE VALUE', D)
        put(row, 30, 'BAR',        D)
        put(row, 45, 'FINAL',      N|curses.A_BOLD)
        put(row, w-10, 'SOURCE',   D)

        # ── param rows ───────────────────────────────────────────────────────
        for k, label, mn, mx, kind in PARAMS_DISPLAY:
            row += 1
            if row >= h-4: break
            brow(row)

            node_val = node_state.get(k)
            final    = s.get(k, DEFAULTS.get(k, 0))
            is_ov    = k in self.overrides

            bar     = pbar(final, mn, mx)
            nv_str  = fmt(node_val, kind) if node_val is not None else '·'
            fv_str  = fmt(final, kind)

            if kind == 'int' and k == 'mode' and isinstance(final, (int, float)):
                idx    = int(final) % len(MODE_NAMES)
                fv_str = f'{int(final)}:{MODE_NAMES[idx]}'

            src_str = 'OVERRIDE' if is_ov else ('NODE' if node_val is not None else 'DEFAULT')
            src_col = Y if is_ov else (G if node_val is not None else D)

            put(row, 2,      label,             N)
            put(row, 18,     nv_str[:10],       CY if node_val is not None else D)
            put(row, 30,     bar,               D)
            put(row, 45,     fv_str[:w-56],     Y if is_ov else G)
            put(row, w-10,   src_str,           src_col)

        row += 1; hline(row)

        # ── footer ───────────────────────────────────────────────────────────
        row += 1
        if row < h-1:
            brow(row)
            put(row, 2,
                '0-9/[/] mode override   B black   SPC flash   '
                'S sync   ! clear overrides   Q quit', D)
            row += 1
            if row < h:
                try: scr.addstr(row, 0, '╚'+'═'*(w-2)+'╝', R)
                except curses.error: pass

        scr.refresh()


def main(stdscr):
    NodeEngine(stdscr).run()


if __name__ == '__main__':
    curses.wrapper(main)
