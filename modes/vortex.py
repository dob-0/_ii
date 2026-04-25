import math
import random

from modes.base import C, Mode, TAU


class Vortex(Mode):
    NAME = 'VORTEX'
    ORDER = 9

    def __init__(self):
        self.cache = None
        self.cache_sz = (0, 0)

    def _precompute(self, w, h):
        if self.cache_sz == (w, h):
            return
        cx = w / 2.0
        cy = h / 2.0
        max_r = math.sqrt(cx ** 2 + (cy * 2) ** 2) or 1.0
        cache = []
        for y in range(h):
            dy = (y - cy) * 2.0
            row_rn = []
            row_a = []
            for x in range(w):
                dx = x - cx
                r = math.sqrt(dx * dx + dy * dy) + 1e-4
                row_rn.append(r / max_r)
                row_a.append(math.atan2(dy, dx))
            cache.append((row_rn, row_a))
        self.cache = cache
        self.cache_sz = (w, h)

    def render(self, buf, w, h, t, frame, cfg, pal, syms):
        self._precompute(w, h)
        p = pal
        tf = frame * 0.055

        for y in range(h):
            row_rn, row_a = self.cache[y]
            for x in range(w):
                rn = row_rn[x]
                a = row_a[x]
                twist = a + tf * 1.8 - rn * 3.5 + math.sin(rn * 4 - tf) * 0.4
                phase = (twist * 3 / TAU) % 1.0
                if phase < 0.22:
                    col = C[p['a']] if rn < 0.28 else C[p['p']] if rn < 0.62 else C[p['s']]
                    buf[y][x] = (random.choice(syms), col)
                elif phase < 0.38 and random.random() < 0.35:
                    buf[y][x] = (random.choice(syms), C['dim'])
                else:
                    buf[y][x] = None
