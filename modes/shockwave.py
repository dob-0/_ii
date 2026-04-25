import math
import random

from modes.base import C, Mode, TAU


class Shockwave(Mode):
    NAME = 'SHOCKWAVE'
    ORDER = 15

    def __init__(self):
        self.rings = []

    def render(self, buf, w, h, t, frame, cfg, pal, syms):
        p = pal

        bpm = cfg.get('bpm', 140)
        beat = 60.0 / max(1, bpm)
        beat_phase = (t % beat) / beat

        if cfg.get('bpm_sync') and beat_phase < 0.06:
            if not self.rings or self.rings[-1]['r'] > 5:
                self.rings.append({'x': w // 2, 'y': h // 2, 'r': 0.0, 'max': math.sqrt((w // 2) ** 2 + h ** 2)})
        elif random.random() < 0.018:
            self.rings.append({
                'x': random.randint(w // 5, 4 * w // 5),
                'y': random.randint(h // 5, 4 * h // 5),
                'r': 0.0,
                'max': math.sqrt((w // 2) ** 2 + h ** 2),
            })

        alive = []
        for ring in self.rings:
            ring['r'] += 1.8
            r = ring['r']
            rx = ring['x']
            ry = ring['y']
            frac = 1 - r / ring['max']
            if frac <= 0:
                continue
            col = C[p['a']] if frac > 0.65 else C[p['p']] if frac > 0.38 else C[p['s']] if frac > 0.15 else C['dim']
            steps = max(16, int(r * math.pi * 0.8))
            for s in range(steps):
                a = s / steps * TAU
                x = int(rx + r * math.cos(a))
                y = int(ry + r * math.sin(a) * 0.5)
                self.put(buf, x, y, random.choice(syms), col, w, h)
            alive.append(ring)
        self.rings = alive[-14:]
