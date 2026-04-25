import math
import random

from modes.base import C, Mode, TAU


class Particles(Mode):
    NAME = 'PARTICLES'
    ORDER = 11

    def __init__(self):
        self.particles = []

    def render(self, buf, w, h, t, frame, cfg, pal, syms):
        p = pal
        cx = w // 2
        cy = h // 2
        n_spawn = max(1, int(cfg.get('rain_density', 0.7) * 10))

        for _ in range(n_spawn):
            angle = random.uniform(0, TAU)
            spd = random.uniform(0.3, 3.0)
            life = random.randint(20, 90)
            self.particles.append({
                'x': float(cx + random.randint(-2, 2)),
                'y': float(cy + random.randint(-1, 1)),
                'vx': math.cos(angle) * spd,
                'vy': math.sin(angle) * spd * 0.45,
                'life': life,
                'max': life,
                'char': random.choice(syms),
                'col': random.choice([p['p'], p['a'], p['s']]),
            })

        alive = []
        for pt in self.particles:
            pt['x'] += pt['vx']
            pt['y'] += pt['vy']
            pt['vy'] += 0.04
            pt['vx'] *= 0.988
            pt['life'] -= 1
            if pt['life'] <= 0:
                continue
            x = int(pt['x'])
            y = int(pt['y'])
            if x < -12 or x > w + 12 or y > h + 12:
                continue
            frac = pt['life'] / pt['max']
            col = C[pt['col']] if frac > 0.5 else C[p['s']] if frac > 0.2 else C['dim']
            if 0 <= x < w and 0 <= y < h:
                buf[y][x] = (pt['char'], col)
            alive.append(pt)
        self.particles = alive[-700:]

        self.put(buf, cx, cy, '◈', C[p['a']], w, h)
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            self.put(buf, cx + dx, cy + dy, random.choice(syms), C[p['p']], w, h)
