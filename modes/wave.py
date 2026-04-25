import math, random
from modes.base import Mode, C, TAU


class Wave(Mode):
    NAME  = 'WAVE'
    ORDER = 1

    def render(self, buf, w, h, t, frame, cfg, pal, syms):
        p   = pal
        tf  = frame * 0.08
        amp = cfg.get('wave_amplitude', 0.35)
        self.clear(buf, w, h)
        for x in range(w):
            px = x / w * TAU
            y1 = int(h * .5 + math.sin(px*2 + tf) * h * amp)
            y2 = int(h * .5 + math.cos(px*3 + tf*1.5) * h * amp * .6)
            y3 = int(h * .5 + math.sin(px + tf*.7) * math.cos(px*2 - tf) * h * amp * .4)
            for y, col in [(y1, p['p']), (y2, p['s']), (y3, p['a'])]:
                if 0 <= y < h:
                    buf[y][x] = (random.choice(syms), C[col])
