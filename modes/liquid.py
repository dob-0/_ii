import math
import random

from modes.base import C, Mode


class Liquid(Mode):
    NAME = 'LIQUID'
    ORDER = 17

    def render(self, buf, w, h, t, frame, cfg, pal, syms):
        p = pal
        audio = float(cfg.get('audio_level', 0.0) or 0.0)
        peak = float(cfg.get('audio_peak', 0.0) or 0.0)
        cam = max(
            float(cfg.get('camera4_motion', 0.0) or 0.0),
            float(cfg.get('camera2_motion', 0.0) or 0.0),
        )
        energy = max(0.0, min(1.0, audio * 0.7 + peak * 0.5 + cam * 0.8))
        tf = frame * (0.025 + energy * 0.045)
        cx = w * (0.42 + math.sin(tf * 0.7) * 0.08)
        cy = h * (0.45 + math.cos(tf * 0.9) * 0.10)

        for y in range(h):
            ny = (y - cy) / max(1, h)
            for x in range(w):
                nx = (x - cx) / max(1, w)
                r1 = math.sqrt((nx * 2.4) ** 2 + (ny * 3.4) ** 2)
                r2 = math.sqrt(((x - w * 0.72) / max(1, w) * 2.8) ** 2 + ((y - h * 0.68) / max(1, h) * 3.8) ** 2)
                wave = (
                    math.sin((nx * 9.0 + ny * 4.0) + tf * 3.0) +
                    math.cos((ny * 14.0 - nx * 5.0) - tf * 2.1) +
                    math.sin((r1 * 18.0) - tf * 3.5) * 1.3 +
                    math.cos((r2 * 15.0) + tf * 2.8) * 1.1
                )
                body = 1.25 / (0.18 + r1 * r1 * 7.0) + 1.05 / (0.18 + r2 * r2 * 8.0)
                v = body + wave * (0.23 + energy * 0.18)
                if v > 4.9:
                    buf[y][x] = ('█', C['white'])
                elif v > 3.6:
                    buf[y][x] = (random.choice(['▓', '▒', '█']), C[p['a']])
                elif v > 2.4:
                    buf[y][x] = (random.choice(['▒', '░', '▚']), C[p['p']])
                elif v > 1.65:
                    buf[y][x] = (random.choice(['░', '.', '·']), C[p['s']])
                else:
                    buf[y][x] = (random.choice([' ', ' ', '.', '·']), C['dim']) if random.random() < 0.14 else None

        arc_r = min(w, h * 2) * (0.28 + energy * 0.08)
        ox = w * 0.60
        oy = h * 0.54
        for i in range(80):
            a = -1.1 + i / 79 * 2.1 + tf * 0.05
            x = int(ox + math.cos(a) * arc_r)
            y = int(oy + math.sin(a) * arc_r * 0.50)
            self.put(buf, x, y, '.', C['white'], w, h)
