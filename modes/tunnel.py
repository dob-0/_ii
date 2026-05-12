import math
import random

from modes.base import C, Mode, TAU


class Tunnel(Mode):
    NAME = 'TUNNEL'
    ORDER = 7

    def __init__(self):
        self.cache = None
        self.cache_sz = (0, 0)

    def _precompute(self, w, h):
        if self.cache_sz == (w, h):
            return
        cx = w / 2.0
        cy = h / 2.0
        cache = []
        for y in range(h):
            dy = (y - cy) * 2.0
            row_r = []
            row_a = []
            for x in range(w):
                dx = x - cx
                r = math.sqrt(dx * dx + dy * dy) + 1e-4
                row_r.append(r)
                row_a.append(math.atan2(dy, dx))
            cache.append((row_r, row_a))
        self.cache = cache
        self.cache_sz = (w, h)

    def render(self, buf, w, h, t, frame, cfg, pal, syms):
        self._precompute(w, h)
        p = pal
        syms_safe = syms or ['#']
        syms_n = len(syms_safe)

        for y in range(h):
            row_r, row_a = self.cache[y]
            for x in range(w):
                r = row_r[x]
                angle = row_a[x]
                u = int(angle / TAU * 6 + frame * 0.15) % 6
                v = int(28 / r + frame * 0.9) % syms_n
                ch = syms_safe[v]
                zone = r / (max(w, h) * 0.6)
                col = (
                    C[p['a']] if zone < 0.18 else
                    C[p['p']] if zone < 0.45 else
                    C[p['s']] if zone < 0.75 else
                    C['dim']
                )
                buf[y][x] = ((ch if u % 2 == 0 else random.choice(syms_safe)), col)
