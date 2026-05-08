import math, random

TAU   = math.tau
ESC   = '\033'
RESET = f'{ESC}[0m'
HIDE  = f'{ESC}[?25l'
SHOW  = f'{ESC}[?25h'

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
COLOR_KEYS = ['red','green','white','dim','cyan','yellow','magenta','red_d','green_d','blue']

PALETTES = [
    {'name': 'STEEL',  'p': 'blue',    's': 'cyan',    'a': 'white'},
    {'name': 'ACID',   'p': 'cyan',    's': 'yellow',  'a': 'white'},
    {'name': 'VOID',   'p': 'white',   's': 'dim',     'a': 'blue'},
    {'name': 'NEON',   'p': 'magenta', 's': 'cyan',    'a': 'white'},
    {'name': 'ULTRA',  'p': 'yellow',  's': 'magenta', 'a': 'white'},
    {'name': 'DEEP',   'p': 'blue',    's': 'magenta', 'a': 'cyan'},
    {'name': 'BLOOD',  'p': 'red',     's': 'red_d',   'a': 'white'},
    {'name': 'EMBER',  'p': 'red',     's': 'yellow',  'a': 'white'},
]

LOGO = [
    '███╗   ███╗ ██████╗  ██████╗████████╗  ███████╗',
    '████╗ ████║██╔═══██╗██╔════╝╚══██╔══╝        ██╗',
    '██╔████╔██║██║   ██║██║        ██║          ██╔╝',
    '██║╚██╔╝██║██║   ██║██║        ██║         ██╔╝ ',
    '██║ ╚═╝ ██║╚██████╔╝╚██████╗   ██║        ██╔╝  ',
    '╚═╝     ╚═╝ ╚═════╝  ╚═════╝   ╚═╝        ╚═╝   ',
]

CUBE_V = [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),
          (-1,-1, 1),(1,-1, 1),(1,1, 1),(-1,1, 1)]
CUBE_E = [(0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),(0,4),(1,5),(2,6),(3,7)]


def mv(x, y):
    return f'{ESC}[{y+1};{x+1}H'


def rot3d(pts, rx, ry, rz):
    cx, cy, cz = math.cos(rx), math.cos(ry), math.cos(rz)
    sx, sy, sz = math.sin(rx), math.sin(ry), math.sin(rz)
    out = []
    for x, y, z in pts:
        y, z = y*cx - z*sx,  y*sx + z*cx
        x, z = x*cy + z*sy, -x*sy + z*cy
        x, y = x*cz - y*sz,  x*sz + y*cz
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


def beat_phase(t, bpm):
    beat = 60.0 / max(1, bpm)
    return (t % beat) / beat


def color_key(value, fallback):
    try:
        if isinstance(value, str):
            return value if value in C else fallback
        idx = int(value)
        if idx < 0:
            return fallback
        return COLOR_KEYS[idx % len(COLOR_KEYS)]
    except Exception:
        return fallback


class Mode:
    """Base class for all visual modes.

    render() receives a persistent cell buffer buf[y][x] = (char, color_str) | None.
    The buffer is NOT cleared between frames — modes own their clearing strategy.
    Full-grid modes overwrite every cell; sparse modes rely on persistence or clear manually.
    """
    NAME  = 'UNNAMED'
    ORDER = 99

    def render(self, buf, w, h, t, frame, cfg, pal, syms):
        """Fill buf with this frame's content.

        buf  : list[list], buf[y][x] = (char, ansi_color) or None (→ space)
        w, h : terminal columns / renderable rows (status bar excluded)
        t    : seconds since engine start
        frame: integer frame counter
        cfg  : merged config+ctrl dict
        pal  : {'p','s','a','name'} — palette color keys
        syms : list of symbol chars
        """

    def put(self, buf, x, y, ch, col, w, h):
        if 0 <= x < w and 0 <= y < h:
            buf[y][x] = (ch, col)

    def clear(self, buf, w, h):
        for row in buf:
            row[:] = [None] * w
