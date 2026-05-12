import math

from modes.base import C, Mode


class Noise(Mode):
    NAME = 'NOISE'
    ORDER = 16

    def render(self, buf, w, h, t, frame, cfg, pal, syms):
        p = pal
        tf = frame * 0.035
        syms_safe = syms or ['#']
        n = len(syms_safe) - 1

        for y in range(h):
            ny = y / h * 8
            for x in range(w):
                nx = x / w * 16
                v = (
                    math.sin(nx * 0.85 + tf) * math.cos(ny * 1.15 - tf * 0.65) +
                    math.sin((nx - ny) * 0.55 + tf * 1.25) * 0.55 +
                    math.cos((nx + ny * 0.7) * 0.42 - tf * 0.88) * 0.45
                )
                v = (v + 2) / 4
                v = max(0.0, min(1.0, v))
                ch = syms_safe[int(v * n)]
                col = (
                    C[p['a']] if v > 0.72 else
                    C[p['p']] if v > 0.48 else
                    C[p['s']] if v > 0.24 else
                    C['dim']
                )
                buf[y][x] = (ch, col)
