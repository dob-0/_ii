#!/usr/bin/env python3
"""MOCT 7 | HAYFILM CLUSTER — Terminal Visual Engine v1.0"""

import sys, os, time, math, random, json, signal, array

BASE        = os.path.dirname(__file__)
CONFIG_PATH = os.path.join(BASE, 'config.json')
CTRL_PATH   = os.path.join(BASE, 'control.json')
STATUS_PATH = os.path.join(BASE, 'status.json')

ESC   = '\033'
RESET = f'{ESC}[0m'
HIDE  = f'{ESC}[?25l'
SHOW  = f'{ESC}[?25h'
CLEAR = f'{ESC}[2J{ESC}[H'
HOME  = f'{ESC}[H'
TAU   = math.tau

C = {
    'red':     f'{ESC}[1;31m',
    'green':   f'{ESC}[1;92m',
    'white':   f'{ESC}[1;37m',
    'dim':     f'{ESC}[2;37m',
    'cyan':    f'{ESC}[1;96m',
    'yellow':  f'{ESC}[1;93m',
    'magenta': f'{ESC}[1;95m',
    'red_d':   f'{ESC}[0;31m',
    'green_d': f'{ESC}[0;32m',
    'blue':    f'{ESC}[1;94m',
}

PALETTES = [
    {'name': 'INDUSTRIAL', 'p': 'red',     's': 'green',   'a': 'white'},
    {'name': 'ACID',       'p': 'cyan',    's': 'yellow',  'a': 'white'},
    {'name': 'VOID',       'p': 'white',   's': 'dim',     'a': 'red'},
    {'name': 'BLOOD',      'p': 'red',     's': 'red_d',   'a': 'white'},
    {'name': 'MATRIX',     'p': 'green',   's': 'green_d', 'a': 'white'},
    {'name': 'NEON',       'p': 'magenta', 's': 'cyan',    'a': 'white'},
]

CUBE_V = [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),
          (-1,-1, 1),(1,-1, 1),(1,1, 1),(-1,1, 1)]
CUBE_E = [(0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),(0,4),(1,5),(2,6),(3,7)]


def rot3d(pts, rx, ry, rz):
    cx, cy, cz = math.cos(rx), math.cos(ry), math.cos(rz)
    sx, sy, sz = math.sin(rx), math.sin(ry), math.sin(rz)
    out = []
    for x, y, z in pts:
        y,  z  = y*cx - z*sx,  y*sx + z*cx
        x,  z  = x*cy + z*sy, -x*sy + z*cy
        x,  y  = x*cz - y*sz,  x*sz + y*cz
        out.append((x, y, z))
    return out


def bresenham(x0, y0, x1, y1):
    pts = []
    dx, dy = abs(x1-x0), abs(y1-y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy
    while True:
        pts.append((x0, y0))
        if x0 == x1 and y0 == y1: break
        e2 = err * 2
        if e2 > -dy: err -= dy; x0 += sx
        if e2 <  dx: err += dx; y0 += sy
    return pts


def load_cfg():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def load_ctrl():
    try:
        with open(CTRL_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def write_status(data):
    tmp = STATUS_PATH + '.tmp'
    try:
        with open(tmp, 'w') as f:
            json.dump(data, f)
        os.replace(tmp, STATUS_PATH)
    except Exception:
        pass


def tsize():
    s = os.get_terminal_size()
    return s.columns, s.lines


def mv(x, y):
    return f'{ESC}[{y+1};{x+1}H'


class Engine:
    LOGO = [
        '███╗   ███╗ ██████╗  ██████╗████████╗  ███████╗',
        '████╗ ████║██╔═══██╗██╔════╝╚══██╔══╝        ██╗',
        '██╔████╔██║██║   ██║██║        ██║          ██╔╝',
        '██║╚██╔╝██║██║   ██║██║        ██║         ██╔╝ ',
        '██║ ╚═╝ ██║╚██████╔╝╚██████╗   ██║        ██╔╝  ',
        '╚═╝     ╚═╝ ╚═════╝  ╚═════╝   ╚═╝        ╚═╝   ',
    ]

    def __init__(self):
        self.cfg        = load_cfg()
        self.ctrl       = {}
        self.frame      = 0
        self.t0         = time.time()
        self.w, self.h  = tsize()
        self.syms       = self.cfg['symbols']
        self.mode       = 0
        self._mtime     = os.path.getmtime(__file__)
        self._fps_t     = time.time()
        self._fps       = 0.0
        self._pal_idx   = 0

        # Per-mode state
        self.rain_y     = {}
        self.particles  = []
        self.rings      = []
        self.storm_pts  = []
        self.storm_age  = 0
        self._tcache    = None   # tunnel precompute cache
        self._tcache_sz = (0, 0)
        self._vcache    = None   # vortex precompute cache
        self._vcache_sz = (0, 0)

        self.mode_fns = [
            self._rain,      # 0
            self._wave,      # 1
            self._glitch,    # 2
            self._strobe,    # 3
            self._logo,      # 4
            self._pulse,     # 5
            self._text,      # 6
            self._tunnel,    # 7
            self._plasma,    # 8
            self._vortex,    # 9
            self._grid,      # 10
            self._particles, # 11
            self._scanner,   # 12
            self._storm,     # 13
            self._cube,      # 14
            self._shockwave, # 15
            self._noise,     # 16
        ]
        self.mode_labels = [
            'RAIN','WAVE','GLITCH','STROBE','LOGO','PULSE','TEXT',
            'TUNNEL','PLASMA','VORTEX','GRID','PARTICLES',
            'SCANNER','STORM','CUBE','SHOCKWAVE','NOISE',
        ]

    @property
    def pal(self):
        return PALETTES[self._pal_idx % len(PALETTES)]

    def _s(self):
        return random.choice(self.syms)

    def _put(self, x, y, ch, col=''):
        if 0 <= x < self.w and 0 <= y < self.h - 1:
            sys.stdout.write(mv(x, y) + col + ch + RESET)

    def _beat_phase(self):
        beat = 60.0 / max(1, self.cfg.get('bpm', 140))
        return ((time.time() - self.t0) % beat) / beat

    def _bar(self, label=None):
        lbl  = label or self.mode_labels[self.mode]
        bpm  = int(self.cfg.get('bpm', 140))
        sync = ' SYNC' if self.cfg.get('bpm_sync') else ''
        txt  = (f' MOCT7 | {lbl} | {self.pal["name"]} | '
                f'{bpm}BPM{sync} | {self._fps:.0f}fps | {time.time()-self.t0:06.1f}s ')
        sys.stdout.write(mv(0, self.h - 1) + C['dim'] + txt[:self.w].ljust(self.w) + RESET)

    # ── precompute polar grid for tunnel & vortex ────────────────────────────
    def _precompute_polar(self):
        if self._tcache_sz == (self.w, self.h):
            return
        H  = self.h - 1
        cx = self.w / 2.0
        cy = H / 2.0
        cache = []
        for y in range(H):
            dy = (y - cy) * 2.0
            row_r, row_a = [], []
            for x in range(self.w):
                dx = x - cx
                r  = math.sqrt(dx*dx + dy*dy) + 1e-4
                row_r.append(r)
                row_a.append(math.atan2(dy, dx))
            cache.append((row_r, row_a))
        self._tcache = cache
        self._tcache_sz = (self.w, self.h)
        # Vortex: normalise r
        max_r = math.sqrt(cx**2 + (cy*2)**2) or 1
        vcache = []
        for row_r, row_a in cache:
            vcache.append(([r / max_r for r in row_r], row_a))
        self._vcache = vcache
        self._vcache_sz = (self.w, self.h)

    def run(self):
        sys.stdout.write(HIDE + CLEAR)
        prev_mode = self.mode
        try:
            while True:
                self.w, self.h = tsize()
                self.ctrl      = load_ctrl()
                c              = self.ctrl

                for key in ('frame_delay','strobe_speed','glitch_intensity',
                            'wave_amplitude','rain_density','mode_cycle_frames',
                            'bpm','bpm_sync'):
                    if key in c:
                        self.cfg[key] = c[key]

                self._pal_idx = c.get('palette', 0)
                self.syms     = self.cfg.get('symbols', self.syms)

                # Hot-reload
                if self.frame % 20 == 0 and os.path.getmtime(__file__) != self._mtime:
                    sys.stdout.write(SHOW + RESET + CLEAR)
                    sys.stdout.flush()
                    os.execv(sys.executable, [sys.executable] + sys.argv)

                # Status ping
                if self.frame % 10 == 0:
                    now = time.time()
                    self._fps = 10 / max(0.001, now - self._fps_t)
                    self._fps_t = now
                    write_status({'frame': self.frame, 'fps': round(self._fps, 1),
                                  'mode': self.mode, 'mode_label': self.mode_labels[self.mode],
                                  'palette': self.pal['name'], 'ts': now})

                # Blackout
                if c.get('blackout'):
                    for y in range(self.h - 1):
                        sys.stdout.write(mv(0, y) + ' ' * self.w)
                    self._bar('BLACKOUT')
                    sys.stdout.flush()
                    self.frame += 1
                    time.sleep(self.cfg.get('frame_delay', 0.05))
                    continue

                # Mode selection
                if c.get('auto_cycle', False):
                    cycle = self.cfg.get('mode_cycle_frames', 250)
                    if self.frame > 0 and self.frame % cycle == 0:
                        self.mode = (self.mode + 1) % len(self.mode_fns)
                else:
                    self.mode = c.get('mode', self.mode)

                if self.mode != prev_mode:
                    sys.stdout.write(CLEAR)
                    prev_mode = self.mode

                self.mode_fns[self.mode]()

                flash_text = c.get('flash_text', '')
                if c.get('flash_active') and flash_text:
                    self._flash(flash_text)

                self._bar()
                sys.stdout.flush()
                self.frame += 1
                time.sleep(self.cfg.get('frame_delay', 0.05))
        finally:
            sys.stdout.write(SHOW + RESET + CLEAR)
            sys.stdout.flush()

    # ════════════════════════════════════════════════════════════════════
    # ORIGINAL 7 MODES
    # ════════════════════════════════════════════════════════════════════

    def _rain(self):
        p = self.pal
        for x in range(self.w):
            if x not in self.rain_y:
                self.rain_y[x] = random.randint(0, self.h)
            y = self.rain_y[x] % self.h
            self._put(x, y, self._s(), C[p['a']])
            for dy in range(1, random.randint(4, 10)):
                self._put(x, (y-dy) % self.h, self._s(), C[p['p']])
            self._put(x, (y-12) % self.h, ' ')
            if random.random() > 0.2:
                self.rain_y[x] += 1

    def _wave(self):
        p, H = self.pal, self.h - 1
        t   = self.frame * 0.08
        amp = self.cfg.get('wave_amplitude', 0.35)
        grid = [[None]*self.w for _ in range(H)]
        for x in range(self.w):
            px = x / self.w * TAU
            y1 = int(H*.5 + math.sin(px*2+t)*H*amp)
            y2 = int(H*.5 + math.cos(px*3+t*1.5)*H*amp*.6)
            y3 = int(H*.5 + math.sin(px+t*.7)*math.cos(px*2-t)*H*amp*.4)
            for y, col in [(y1,p['p']),(y2,p['s']),(y3,p['a'])]:
                if 0 <= y < H: grid[y][x] = col
        out = []
        for y in range(H):
            out.append(mv(0, y))
            for x in range(self.w):
                col = grid[y][x]
                out.append((C[col]+self._s()+RESET) if col else ' ')
        sys.stdout.write(''.join(out))

    def _glitch(self):
        p         = self.pal
        intensity = self.cfg.get('glitch_intensity', 0.4)
        n = max(1, int((self.h-1)*intensity*random.random()))
        for _ in range(n):
            y   = random.randint(0, self.h-2)
            col = random.choice([C[p['p']],C[p['a']],C[p['s']],C['dim']])
            if random.random() < 0.2:
                sys.stdout.write(mv(0,y) + ' '*self.w)
            else:
                off  = random.randint(0, 6)
                line = ' '*off + ''.join(self._s() for _ in range(self.w))
                sys.stdout.write(mv(0,y) + col + line[:self.w] + RESET)
        if self.frame % 53 == 0:
            self._logo(overlay=True)

    def _strobe(self):
        p       = self.pal
        density = self.cfg.get('rain_density', 0.7)
        speed   = max(1, int(self.cfg.get('strobe_speed', 2)))
        on = self._beat_phase() < 0.5 if self.cfg.get('bpm_sync') else (self.frame//speed)%2==0
        if on:
            col = random.choice([C[p['p']], C[p['a']]])
            for y in range(self.h-1):
                line = ''.join(self._s() if random.random() < density else ' ' for _ in range(self.w))
                sys.stdout.write(mv(0,y) + col + line + RESET)
        else:
            for y in range(self.h-1):
                sys.stdout.write(mv(0,y) + ' '*self.w)

    def _logo(self, overlay=False):
        p = self.pal
        if not overlay:
            for _ in range(self.w*(self.h-1)//12):
                self._put(random.randint(0,self.w-1), random.randint(0,self.h-2), self._s(), C[p['s']])
        sy = (self.h - len(self.LOGO)) // 2
        for i, line in enumerate(self.LOGO):
            sx = max(0, (self.w - len(line))//2)
            y  = sy + i
            if 0 <= y < self.h-1:
                col = C[p['p']] if math.sin(self.frame*0.12+i*0.4)>0 else C[p['a']]
                sys.stdout.write(mv(sx,y) + col + line[:self.w-sx] + RESET)

    def _pulse(self):
        p  = self.pal
        H  = self.h - 1
        cx = self.w//2; cy = H//2
        max_r = math.sqrt(cx**2+(cy*2)**2)
        ring_r = self._beat_phase() * max_r
        out = []
        for y in range(H):
            out.append(mv(0,y))
            for x in range(self.w):
                dx = x-cx; dy = (y-cy)*2
                r    = math.sqrt(dx*dx+dy*dy)
                dist = abs(r - ring_r)
                if dist < 2.5:
                    bri = 1 - dist/2.5
                    out.append(C[p['a'] if bri>0.6 else p['p']] + self._s() + RESET)
                elif r < ring_r-2 and random.random() < 0.03:
                    out.append(C[p['s']] + self._s() + RESET)
                else:
                    out.append(' ')
        sys.stdout.write(''.join(out))

    def _text(self):
        p    = self.pal
        text = self.ctrl.get('flash_text','MOCT 7') or 'MOCT 7'
        H    = self.h - 1
        t    = self.frame
        for _ in range(self.w*H//25):
            self._put(random.randint(0,self.w-1), random.randint(0,H-1), self._s(), C['dim'])
        tile     = text + '  '
        repeated = tile * ((self.w//max(1,len(tile)))+3)
        band_gap = max(3, H//5)
        for row in range(5):
            y      = (row*band_gap + t//3) % H
            offset = (t + row*17) % len(tile)
            line   = repeated[offset: offset+self.w]
            glitched = ''.join(random.choice(self.syms) if random.random()<0.07 else c for c in line)
            col = C[p['p']] if (row+t//5)%2==0 else C[p['a']]
            sys.stdout.write(mv(0,y) + col + glitched[:self.w] + RESET)
        cy = H//2; cx = max(0,(self.w-len(text))//2)
        if cy < H:
            big = ''.join(random.choice(self.syms) if random.random()<0.05 else c for c in text)
            col = C[p['a']] if math.sin(t*0.2)>0 else C[p['p']]
            sys.stdout.write(mv(cx,cy) + col + big[:self.w-cx] + RESET)
            for dy in (1,2):
                if cy+dy < H:
                    sys.stdout.write(mv(cx,cy+dy) + C[p['s']] + ' '.join(text)[:self.w-cx] + RESET)

    # ════════════════════════════════════════════════════════════════════
    # 10 NEW ELITE MODES
    # ════════════════════════════════════════════════════════════════════

    # 7 ── TUNNEL ─────────────────────────────────────────────────────────────
    def _tunnel(self):
        self._precompute_polar()
        p      = self.pal
        H      = self.h - 1
        t      = self.frame
        syms_n = len(self.syms)
        out    = []
        for y in range(H):
            out.append(mv(0, y))
            row_r, row_a = self._tcache[y]
            for x in range(self.w):
                r     = row_r[x]
                angle = row_a[x]
                u     = int(angle/TAU*6 + t*0.15) % 6
                v     = int(28/r + t*0.9) % syms_n
                ch    = self.syms[v]
                zone  = r / (max(self.w,H)*0.6)
                col   = (C[p['a']] if zone < 0.18 else
                         C[p['p']] if zone < 0.45 else
                         C[p['s']] if zone < 0.75 else C['dim'])
                out.append(col + (ch if u%2==0 else self._s()) + RESET)
        sys.stdout.write(''.join(out))

    # 8 ── PLASMA ─────────────────────────────────────────────────────────────
    def _plasma(self):
        p   = self.pal
        H   = self.h - 1
        t   = self.frame * 0.06
        n   = len(self.syms) - 1
        out = []
        for y in range(H):
            out.append(mv(0, y))
            ny = y / H * 10
            for x in range(self.w):
                nx = x / self.w * 20
                v  = (math.sin(nx*0.9 + t) +
                      math.sin(ny*0.7 + t*1.2) +
                      math.sin((nx+ny)*0.5 + t*0.8) +
                      math.sin(math.sqrt(nx*nx+ny*ny)*0.6 + t*1.1))
                v = (v + 4) / 8
                ch  = self.syms[int(v*n)]
                col = (C[p['a']] if v>0.72 else
                       C[p['p']] if v>0.45 else
                       C[p['s']] if v>0.18 else C['dim'])
                out.append(col + ch + RESET)
        sys.stdout.write(''.join(out))

    # 9 ── VORTEX ─────────────────────────────────────────────────────────────
    def _vortex(self):
        self._precompute_polar()
        p   = self.pal
        H   = self.h - 1
        t   = self.frame * 0.055
        out = []
        for y in range(H):
            out.append(mv(0, y))
            row_rn, row_a = self._vcache[y]
            for x in range(self.w):
                rn  = row_rn[x]
                a   = row_a[x]
                twist = a + t*1.8 - rn*3.5 + math.sin(rn*4 - t)*0.4
                arms  = 3
                phase = (twist*arms/TAU) % 1.0
                if phase < 0.22:
                    col = C[p['a']] if rn<0.28 else C[p['p']] if rn<0.62 else C[p['s']]
                    out.append(col + self._s() + RESET)
                elif phase < 0.38 and random.random() < 0.35:
                    out.append(C['dim'] + self._s() + RESET)
                else:
                    out.append(' ')
        sys.stdout.write(''.join(out))

    # 10 ── GRID (Synthwave) ───────────────────────────────────────────────────
    def _grid(self):
        p       = self.pal
        H       = self.h - 1
        horizon = H // 3
        cx      = self.w // 2
        fov     = float(max(self.w, H) * 2)
        gs      = 3.0
        z_off   = (self.frame * 0.04) % gs

        for y in range(H):
            sys.stdout.write(mv(0, y) + ' '*self.w)

        # Stars
        for _ in range(50):
            x = random.randint(0, self.w-1)
            y = random.randint(0, horizon-1)
            self._put(x, y, random.choice(['.','·','+']),
                      C[p['a']] if random.random()<0.15 else C['dim'])

        # Sun
        sw = min(self.w//5, 22); sx = cx - sw//2
        for i in range(4):
            col = C[p['a']] if i==0 else C[p['p']] if i==1 else C[p['s']] if i==2 else C['dim']
            ys  = horizon - i - 1
            if 0 <= ys < H:
                sys.stdout.write(mv(max(0,sx), ys) + col + '▄'*sw + RESET)

        # Horizontal grid lines (perspective scroll)
        for n in range(1, 50):
            z = n*gs - z_off + 0.01
            if z <= 0: continue
            y = int(horizon + fov/z)
            if not (horizon < y < H): continue
            df = (y-horizon)/(H-horizon)
            col = C[p['p']] if df>0.55 else C[p['s']] if df>0.25 else C['dim']
            sys.stdout.write(mv(0, y) + col + '─'*self.w + RESET)

        # Vertical lines (linear perspective — x = cx + xw*(y-horizon))
        for i in range(-11, 12):
            xw = i * 1.1
            for y in range(horizon, H):
                x = int(cx + xw*(y-horizon))
                if 0 <= x < self.w:
                    df = (y-horizon)/(H-horizon)
                    col = C[p['p']] if df>0.55 else C[p['s']] if df>0.25 else C['dim']
                    self._put(x, y, '│', col)

    # 11 ── PARTICLES ─────────────────────────────────────────────────────────
    def _particles(self):
        p   = self.pal
        H   = self.h - 1
        cx  = self.w//2; cy = H//2
        n_spawn = max(1, int(self.cfg.get('rain_density', 0.7)*10))

        for _ in range(n_spawn):
            angle = random.uniform(0, TAU)
            spd   = random.uniform(0.3, 3.0)
            life  = random.randint(20, 90)
            self.particles.append({
                'x': float(cx+random.randint(-2,2)),
                'y': float(cy+random.randint(-1,1)),
                'vx': math.cos(angle)*spd,
                'vy': math.sin(angle)*spd*0.45,
                'life': life, 'max': life,
                'char': self._s(),
                'col': random.choice([p['p'],p['a'],p['s']]),
            })

        alive = []
        for pt in self.particles:
            pt['x']  += pt['vx']
            pt['y']  += pt['vy']
            pt['vy'] += 0.04
            pt['vx'] *= 0.988
            pt['life'] -= 1
            if pt['life'] <= 0: continue
            x, y = int(pt['x']), int(pt['y'])
            if x < -12 or x > self.w+12 or y > H+12: continue
            frac = pt['life']/pt['max']
            col  = C[pt['col']] if frac>0.5 else C[p['s']] if frac>0.2 else C['dim']
            if 0 <= x < self.w and 0 <= y < H:
                self._put(x, y, pt['char'], col)
            alive.append(pt)
        self.particles = alive[-700:]

        self._put(cx, cy, '◈', C[p['a']])
        for dx,dy in ((-1,0),(1,0),(0,-1),(0,1)):
            self._put(cx+dx, cy+dy, self._s(), C[p['p']])

    # 12 ── SCANNER (Radar) ────────────────────────────────────────────────────
    def _scanner(self):
        p      = self.pal
        H      = self.h - 1
        cx     = self.w//2; cy = H//2
        angle  = (self.frame*0.05) % TAU
        max_r  = int(math.sqrt(cx**2+(cy*2)**2))
        trail  = 16

        # Crosshair
        for dx in range(-2,3): self._put(cx+dx, cy, '─', C['dim'])
        for dy in range(-1,2): self._put(cx, cy+dy, '│', C['dim'])
        self._put(cx, cy, '◈', C[p['a']])

        # Static rings
        for frac in (0.33, 0.66, 1.0):
            r = int(max_r*frac)
            for s in range(64):
                a = s/64*TAU
                x = int(cx + r*math.cos(a))
                y = int(cy + r*math.sin(a)*0.5)
                if 0 <= x < self.w and 0 <= y < H:
                    self._put(x, y, '·', C['dim'])

        # Sweep beam + phosphor trail
        for r in range(3, max_r):
            bx = int(cx + r*math.cos(angle))
            by = int(cy + r*math.sin(angle)*0.5)
            if 0 <= bx < self.w and 0 <= by < H:
                self._put(bx, by, '█', C[p['a']])
            for i in range(1, trail):
                at = angle - i*0.06
                tx = int(cx + r*math.cos(at))
                ty = int(cy + r*math.sin(at)*0.5)
                if 0 <= tx < self.w and 0 <= ty < H:
                    frac = 1 - i/trail
                    col  = C[p['p']] if frac>0.55 else C[p['s']] if frac>0.28 else C['dim']
                    self._put(tx, ty, self._s(), col)

    # 13 ── STORM (Lightning) ──────────────────────────────────────────────────
    def _storm(self):
        p = self.pal
        H = self.h - 1

        if self.frame % 4 == 0:
            for _ in range(self.w*H//35):
                self._put(random.randint(0,self.w-1), random.randint(0,H-1), self._s(), C['dim'])

        if self.storm_age <= 0 or not self.storm_pts:
            self.storm_pts = self._lightning(random.randint(self.w//6, 5*self.w//6), 0, H-1)
            self.storm_age = random.randint(3, 8)
            for y in range(H):
                sys.stdout.write(mv(0,y) + C[p['a']] + self._s()*self.w + RESET)
            sys.stdout.flush(); time.sleep(0.035)
            for y in range(H):
                sys.stdout.write(mv(0,y) + ' '*self.w)

        self.storm_age -= 1
        half = len(self.storm_pts)//2
        for i, (x, y) in enumerate(self.storm_pts):
            if 0 <= x < self.w and 0 <= y < H:
                col = C[p['a']] if i<4 else C[p['p']] if i<half else C[p['s']]
                self._put(x, y, random.choice(['│','╎','▌','█','╷']), col)

    def _lightning(self, x, y0, y1, roughness=10, min_seg=3):
        segs   = [(x, y0, x, y1)]
        result = []
        while segs:
            x0, ya, x1, yb = segs.pop()
            if abs(yb-ya) < min_seg:
                result += bresenham(x0,ya,x1,yb)
                continue
            my = (ya+yb)//2
            mx = (x0+x1)//2 + random.randint(-roughness, roughness)
            segs.append((x0,ya,mx,my))
            segs.append((mx,my,x1,yb))
            if random.random() < 0.28:
                fx = mx + random.randint(-18,18)
                fy = min(my + random.randint(4,22), y1)
                segs.append((mx,my,fx,fy))
        return result

    # 14 ── CUBE (3D Wireframe) ────────────────────────────────────────────────
    def _cube(self):
        p  = self.pal
        H  = self.h - 1
        cx = self.w//2; cy = H//2
        t  = self.frame * 0.03
        sc = min(cx, cy*2) * 0.58

        if self.frame % 3 == 0:
            for _ in range(self.w*H//50):
                self._put(random.randint(0,self.w-1), random.randint(0,H-1), self._s(), C['dim'])

        verts = rot3d(CUBE_V, t*0.7, t, t*0.4)

        def proj(x, y, z):
            zc = z + 3.5
            if zc <= 0: return None
            return (int(cx + x/zc*sc), int(cy + y/zc*sc*0.5))

        ecols = [C[p['a']], C[p['p']], C[p['s']]]
        for ei, (i, j) in enumerate(CUBE_E):
            p0, p1 = proj(*verts[i]), proj(*verts[j])
            if p0 and p1:
                col = ecols[ei % 3]
                ch  = random.choice(['█','▓','◈','7','M'])
                for bx, by in bresenham(p0[0],p0[1],p1[0],p1[1]):
                    if 0 <= bx < self.w and 0 <= by < H:
                        self._put(bx, by, ch, col)

        for v in verts:
            pt = proj(*v)
            if pt and 0 <= pt[0] < self.w and 0 <= pt[1] < H:
                self._put(pt[0], pt[1], '◈', C[p['a']])

    # 15 ── SHOCKWAVE (Expanding rings) ───────────────────────────────────────
    def _shockwave(self):
        p = self.pal
        H = self.h - 1

        # BPM-sync spawn
        if self.cfg.get('bpm_sync') and self._beat_phase() < 0.06:
            if not self.rings or self.rings[-1]['r'] > 5:
                self.rings.append({'x':self.w//2,'y':H//2,'r':0.0,
                                   'max':math.sqrt((self.w//2)**2+H**2)})
        elif random.random() < 0.018:
            self.rings.append({
                'x': random.randint(self.w//5, 4*self.w//5),
                'y': random.randint(H//5, 4*H//5),
                'r': 0.0,
                'max': math.sqrt((self.w//2)**2+H**2),
            })

        alive = []
        for ring in self.rings:
            ring['r'] += 1.8
            r = ring['r']; rx = ring['x']; ry = ring['y']
            frac = 1 - r/ring['max']
            if frac <= 0: continue
            col = (C[p['a']] if frac>0.65 else
                   C[p['p']] if frac>0.38 else
                   C[p['s']] if frac>0.15 else C['dim'])
            steps = max(16, int(r * math.pi * 0.8))
            for s in range(steps):
                a = s/steps*TAU
                x = int(rx + r*math.cos(a))
                y = int(ry + r*math.sin(a)*0.5)
                if 0 <= x < self.w and 0 <= y < H:
                    self._put(x, y, self._s(), col)
            alive.append(ring)
        self.rings = alive[-14:]

    # 16 ── NOISE (Smooth field) ───────────────────────────────────────────────
    def _noise(self):
        p   = self.pal
        H   = self.h - 1
        t   = self.frame * 0.035
        n   = len(self.syms) - 1
        out = []
        for y in range(H):
            out.append(mv(0, y))
            ny = y/H * 8
            for x in range(self.w):
                nx = x/self.w * 16
                v  = (math.sin(nx*0.85 + t) * math.cos(ny*1.15 - t*0.65) +
                      math.sin((nx-ny)*0.55 + t*1.25) * 0.55 +
                      math.cos((nx+ny*0.7)*0.42 - t*0.88) * 0.45)
                v = (v + 2) / 4
                v = max(0.0, min(1.0, v))
                ch  = self.syms[int(v*n)]
                col = (C[p['a']] if v>0.72 else
                       C[p['p']] if v>0.48 else
                       C[p['s']] if v>0.24 else C['dim'])
                out.append(col + ch + RESET)
        sys.stdout.write(''.join(out))

    # ── Flash overlay ─────────────────────────────────────────────────────────
    def _flash(self, text):
        p  = self.pal
        cy = (self.h-1)//2
        cx = max(0, (self.w-len(text))//2)
        col = C[p['a']] if self.frame%4<2 else C[p['p']]
        if cy < self.h-1:
            sys.stdout.write(mv(cx,cy) + col + text[:self.w-cx] + RESET)


def _quit(sig, frame):
    sys.stdout.write(SHOW + RESET + CLEAR)
    sys.stdout.flush()
    print('[ MOCT7 VISUAL ENGINE STOPPED ]')
    sys.exit(0)


if __name__ == '__main__':
    signal.signal(signal.SIGINT,  _quit)
    signal.signal(signal.SIGTERM, _quit)
    Engine().run()
