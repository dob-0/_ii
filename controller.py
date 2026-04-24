#!/usr/bin/env python3
"""MOCT 7 | LIVE CONTROLLER"""

import curses, json, locale, os, time
from collections import deque

locale.setlocale(locale.LC_ALL, '')

BASE        = os.path.dirname(__file__)
CTRL_PATH   = os.path.join(BASE, 'control.json')
STATUS_PATH = os.path.join(BASE, 'status.json')

MODES = [
    'RAIN','WAVE','GLITCH','STROBE','LOGO','PULSE','TEXT',
    'TUNNEL','PLASMA','VORTEX','GRID','PARTICLES',
    'SCANNER','STORM','CUBE','SHOCKWAVE','NOISE',
]

PALETTES = ['INDUSTRIAL','ACID','VOID','BLOOD','MATRIX','NEON']

PARAMS = [
    ('frame_delay',       'SPEED       ', 0.01, 0.20, 0.005, '{:.3f}'),
    ('strobe_speed',      'STROBE SPEED', 1,    10,   1,     '{:.0f}'),
    ('glitch_intensity',  'GLITCH      ', 0.05, 1.0,  0.05,  '{:.2f}'),
    ('wave_amplitude',    'WAVE AMP    ', 0.10, 0.50, 0.025, '{:.3f}'),
    ('rain_density',      'DENSITY     ', 0.10, 1.0,  0.05,  '{:.2f}'),
    ('mode_cycle_frames', 'CYCLE FRAMES', 50,   600,  25,    '{:.0f}'),
    ('bpm',               'BPM         ', 40,   240,  1,     '{:.0f}'),
]

DEFAULTS = {
    'mode':0,'auto_cycle':False,'blackout':False,'flash_active':False,
    'bpm_sync':False,'palette':0,'flash_text':'MOCT 7',
    'frame_delay':0.05,'strobe_speed':2,'glitch_intensity':0.4,
    'wave_amplitude':0.35,'rain_density':0.7,'mode_cycle_frames':250,'bpm':140,
}

PRESETS = [
    {'name':'RAIN',    'mode':0,  'palette':4, 'frame_delay':0.05,  'bpm_sync':False},
    {'name':'RAVE',    'mode':3,  'palette':0, 'frame_delay':0.03,  'strobe_speed':1, 'bpm_sync':True},
    {'name':'TUNNEL',  'mode':7,  'palette':5, 'frame_delay':0.04},
    {'name':'STORM',   'mode':13, 'palette':2, 'glitch_intensity':0.6},
    {'name':'PLASMA',  'mode':8,  'palette':1, 'frame_delay':0.06},
    {'name':'VORTEX',  'mode':9,  'palette':0, 'frame_delay':0.05},
    {'name':'GRID',    'mode':10, 'palette':3, 'frame_delay':0.05,  'bpm_sync':True},
    {'name':'CHAOS',   'mode':2,  'palette':0, 'frame_delay':0.03,  'glitch_intensity':0.9},
    {'name':'CUBE',    'mode':14, 'palette':5, 'frame_delay':0.04},
    {'name':'NOISE',   'mode':16, 'palette':4, 'frame_delay':0.06},
]


def write_ctrl(state):
    tmp = CTRL_PATH + '.tmp'
    with open(tmp,'w') as f: json.dump(state,f)
    os.replace(tmp, CTRL_PATH)


def read_status():
    try:
        with open(STATUS_PATH) as f: return json.load(f)
    except Exception: return {}


def pbar(val, mn, mx, width=16):
    filled = max(0, min(width, round((val-mn)/(mx-mn)*width)))
    return '█'*filled + '░'*(width-filled)


class Controller:
    def __init__(self, stdscr):
        self.scr       = stdscr
        self.state     = dict(DEFAULTS)
        self.sel       = 0
        self.taps      = deque(maxlen=8)
        self.text_mode = False
        self.text_buf  = self.state['flash_text']
        self._init_colors()
        write_ctrl(self.state)

    def _init_colors(self):
        curses.start_color(); curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_RED,    -1)
        curses.init_pair(2, curses.COLOR_GREEN,  -1)
        curses.init_pair(3, curses.COLOR_WHITE,  -1)
        curses.init_pair(4, curses.COLOR_BLACK,  curses.COLOR_WHITE)
        curses.init_pair(5, curses.COLOR_YELLOW, -1)
        curses.init_pair(6, curses.COLOR_CYAN,   -1)

    def run(self):
        curses.curs_set(0)
        self.scr.nodelay(True)
        self.scr.timeout(50)
        while True:
            key = self.scr.getch()
            if not self._handle(key): break
            write_ctrl(self.state)
            self._draw()

    def _handle(self, key):
        s = self.state
        n = len(MODES)

        if self.text_mode:
            if   key == 27:                             self.text_mode = False
            elif key in (10,13):                        s['flash_text'] = self.text_buf; self.text_mode = False
            elif key in (curses.KEY_BACKSPACE,127,8):   self.text_buf = self.text_buf[:-1]
            elif 32 <= key <= 126:                      self.text_buf += chr(key)
            return True

        if   key == ord('q'):       return False
        elif key == ord('!'):       s.update(DEFAULTS); s['blackout'] = True
        elif key == ord('b'):       s['blackout']    = not s['blackout']
        elif key == ord('a'):       s['auto_cycle']  = not s['auto_cycle']
        elif key == ord(' '):       s['flash_active']= not s['flash_active']
        elif key == ord('p'):       s['palette']     = (s['palette']+1) % len(PALETTES)
        elif key == ord('s'):       s['bpm_sync']    = not s['bpm_sync']
        elif key == ord('t'):       self._tap()
        elif key in (10,13):        self.text_mode = True; self.text_buf = s.get('flash_text','')
        elif key == ord('['):       s['mode'] = (s['mode']-1) % n; s['auto_cycle'] = False
        elif key == ord(']'):       s['mode'] = (s['mode']+1) % n; s['auto_cycle'] = False
        elif ord('0') <= key <= ord('9'):
            m = key - ord('0')
            if m < n: s['mode'] = m; s['auto_cycle'] = False
        elif key == curses.KEY_UP:   self.sel = (self.sel-1) % len(PARAMS)
        elif key == curses.KEY_DOWN: self.sel = (self.sel+1) % len(PARAMS)
        elif key in (curses.KEY_LEFT, curses.KEY_RIGHT):
            k,_,mn,mx,step,_ = PARAMS[self.sel]
            delta = step if key == curses.KEY_RIGHT else -step
            s[k]  = round(min(mx, max(mn, s[k]+delta)), 4)
        elif key == curses.KEY_F1:  self._preset(0)
        elif key == curses.KEY_F2:  self._preset(1)
        elif key == curses.KEY_F3:  self._preset(2)
        elif key == curses.KEY_F4:  self._preset(3)
        elif key == curses.KEY_F5:  self._preset(4)
        elif key == curses.KEY_F6:  self._preset(5)
        elif key == curses.KEY_F7:  self._preset(6)
        elif key == curses.KEY_F8:  self._preset(7)
        elif key == curses.KEY_F9:  self._preset(8)
        elif key == curses.KEY_F10: self._preset(9)
        elif key == curses.KEY_RESIZE: self.scr.clear()
        return True

    def _tap(self):
        now = time.time()
        if self.taps and now - self.taps[-1] > 3.0:
            self.taps.clear()
        self.taps.append(now)
        if len(self.taps) >= 2:
            ivs = [self.taps[i+1]-self.taps[i] for i in range(len(self.taps)-1)]
            self.state['bpm'] = max(40, min(240, round(60/(sum(ivs)/len(ivs)))))

    def _preset(self, idx):
        if idx < len(PRESETS):
            for k,v in PRESETS[idx].items():
                if k != 'name' and k in self.state:
                    self.state[k] = v
            self.state['auto_cycle'] = False

    def _draw(self):
        scr = self.scr
        h, w = scr.getmaxyx()
        s    = self.state

        R  = curses.color_pair(1)|curses.A_BOLD
        G  = curses.color_pair(2)|curses.A_BOLD
        N  = curses.color_pair(3)
        HL = curses.color_pair(4)
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

        row = 0
        # header
        try: scr.addstr(0, 0, '╔'+'═'*(w-2)+'╗', R)
        except curses.error: pass
        row = 1; brow(row)
        title = 'MOCT 7  ·  LIVE CONTROLLER'
        put(row, (w-len(title))//2, title, R)
        row = 2; hline(row)

        # engine status
        row = 3; brow(row)
        st    = read_status()
        alive = st and (time.time()-st.get('ts',0)) < 2.0
        if alive:
            put(row, 2, '● LIVE', G)
            put(row, 10, f" F:{st.get('frame',0):>7}  {st.get('fps',0):.0f}fps"
                         f"  {st.get('mode_label','?'):<10} {st.get('palette','')}", CY)
        else:
            put(row, 2, '○ ENGINE NOT RUNNING  →  python3 visuals.py', R)
        row = 4; hline(row)

        # mode — sliding window of 9 centered on current
        row = 5; brow(row)
        cur  = s['mode']
        n    = len(MODES)
        win  = 9
        half = win // 2
        put(row, 2, 'MODE', N|curses.A_BOLD)
        col = 8
        for offset in range(-half, half+1):
            idx  = (cur + offset) % n
            m    = MODES[idx]
            tag  = f'[{idx}:{m}]' if offset==0 else f' {idx}:{m} '
            attr = G if offset==0 else (N if abs(offset)<=2 else D)
            if col+len(tag) < w-2:
                put(row, col, tag, attr)
            col += len(tag)+1
        put(row, w-18, '[ prev  ] next', D)
        row = 6; hline(row)

        # palette
        row = 7; brow(row)
        put(row, 2, 'PAL ', N|curses.A_BOLD)
        col = 8
        for i, pal in enumerate(PALETTES):
            tag  = f'[{pal}]' if i==s['palette'] else f' {pal} '
            attr = Y if i==s['palette'] else D
            if col+len(tag) < w-2: put(row, col, tag, attr)
            col += len(tag)+1
        row = 8; hline(row)

        # bpm + toggles
        row = 9; brow(row)
        put(row, 2,  f"BPM {s['bpm']:<3}", Y if s['bpm_sync'] else N|curses.A_BOLD)
        put(row, 10, f" SYNC:{'ON ' if s['bpm_sync'] else 'OFF'}", G if s['bpm_sync'] else D)
        if self.taps: put(row, 22, f" taps:{len(self.taps)}", D)
        right = (f"AUTO:{'ON ' if s['auto_cycle'] else 'OFF'}  "
                 f"BLACK:{'ON ' if s['blackout'] else 'OFF'}  "
                 f"FLASH:{'ON' if s['flash_active'] else 'OFF'}")
        put(row, w-len(right)-2, right, D)
        row = 10; hline(row)

        # params
        for i, (k, label, mn, mx, _, fmt) in enumerate(PARAMS):
            row += 1
            if row >= h-6: break
            val  = s[k]
            b    = pbar(val, mn, mx)
            line = f'  {label}  {b}  {fmt.format(val)}'
            brow(row)
            put(row, 1, line[:w-2].ljust(w-2), HL if i==self.sel else N)
        row += 1; hline(row)

        # text
        row += 1
        if row < h-5:
            brow(row)
            if self.text_mode:
                put(row, 2, 'INPUT ›', Y|curses.A_BOLD)
                put(row, 10, (self.text_buf+'_')[:w-12], HL)
            else:
                txt = s.get('flash_text','')
                put(row, 2, 'TEXT  ', N|curses.A_BOLD)
                put(row, 8, f'"{txt[:w-22]}"', CY if s['flash_active'] else D)
                put(row, w-16, 'ENTER to edit', D)
            row += 1; hline(row)

        # presets
        row += 1
        if row < h-4:
            brow(row)
            put(row, 2, 'PRESETS', N|curses.A_BOLD)
            col = 11
            for i, pr in enumerate(PRESETS):
                tag = f'F{i+1}:{pr["name"]}'
                if col+len(tag)+2 < w-2: put(row, col, tag, D)
                col += len(tag)+2
            row += 1; hline(row)

        # keys
        row += 1
        if row < h-1:
            brow(row)
            put(row, 2,
                '↑↓ param  ←→ val  0-9 mode  [/] cycle  P palette  '
                'S sync  T tap  SPC flash  B black  A auto  ! panic  Q quit', D)
            row += 1
            if row < h:
                try: scr.addstr(row, 0, '╚'+'═'*(w-2)+'╝', R)
                except curses.error: pass

        scr.refresh()


def main(stdscr):
    Controller(stdscr).run()


if __name__ == '__main__':
    curses.wrapper(main)
