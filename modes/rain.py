import random
from modes.base import Mode, C


class Rain(Mode):
    NAME  = 'RAIN'
    ORDER = 0

    def __init__(self):
        self.col_y = {}

    def render(self, buf, w, h, t, frame, cfg, pal, syms):
        p = pal
        for x in range(w):
            if x not in self.col_y:
                self.col_y[x] = random.randint(0, h)
            y = self.col_y[x] % h
            self.put(buf, x, y, random.choice(syms), C[p['a']], w, h)
            for dy in range(1, random.randint(4, 10)):
                self.put(buf, x, (y - dy) % h, random.choice(syms), C[p['p']], w, h)
            ey = (y - 12) % h
            if 0 <= ey < h:
                buf[ey][x] = None
            if random.random() > 0.2:
                self.col_y[x] += 1
