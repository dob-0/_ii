import math

from modes.base import C, Mode


class Plasma(Mode):
    NAME = 'PLASMA'
    ORDER = 8

    def render(self, buf, w, h, t, frame, cfg, pal, syms):
        p = pal
        tf = frame * 0.06
        syms_safe = syms or ['#']
        n = len(syms_safe) - 1

        for y in range(h):
            ny = y / h * 10
            for x in range(w):
                nx = x / w * 20
                v = (
                    math.sin(nx * 0.9 + tf) +
                    math.sin(ny * 0.7 + tf * 1.2) +
                    math.sin((nx + ny) * 0.5 + tf * 0.8) +
                    math.sin(math.sqrt(nx * nx + ny * ny) * 0.6 + tf * 1.1)
                )
                v = (v + 4) / 8
                ch = syms_safe[int(v * n)]
                col = (
                    C[p['a']] if v > 0.72 else
                    C[p['p']] if v > 0.45 else
                    C[p['s']] if v > 0.18 else
                    C['dim']
                )
                buf[y][x] = (ch, col)
