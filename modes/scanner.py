import math
import random

from modes.base import C, Mode, TAU


class Scanner(Mode):
    NAME = 'SCANNER'
    ORDER = 12

    def render(self, buf, w, h, t, frame, cfg, pal, syms):
        p = pal
        cx = w // 2
        cy = h // 2
        angle = (frame * 0.05) % TAU
        max_r = int(math.sqrt(cx ** 2 + (cy * 2) ** 2))
        trail = 16

        for dx in range(-2, 3):
            self.put(buf, cx + dx, cy, '─', C['dim'], w, h)
        for dy in range(-1, 2):
            self.put(buf, cx, cy + dy, '│', C['dim'], w, h)
        self.put(buf, cx, cy, '◈', C[p['a']], w, h)

        for frac in (0.33, 0.66, 1.0):
            r = int(max_r * frac)
            for s in range(64):
                a = s / 64 * TAU
                x = int(cx + r * math.cos(a))
                y = int(cy + r * math.sin(a) * 0.5)
                self.put(buf, x, y, '·', C['dim'], w, h)

        for r in range(3, max_r):
            bx = int(cx + r * math.cos(angle))
            by = int(cy + r * math.sin(angle) * 0.5)
            self.put(buf, bx, by, '█', C[p['a']], w, h)
            for i in range(1, trail):
                at = angle - i * 0.06
                tx = int(cx + r * math.cos(at))
                ty = int(cy + r * math.sin(at) * 0.5)
                frac = 1 - i / trail
                col = C[p['p']] if frac > 0.55 else C[p['s']] if frac > 0.28 else C['dim']
                self.put(buf, tx, ty, random.choice(syms), col, w, h)
