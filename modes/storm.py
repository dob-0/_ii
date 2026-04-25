import random

from modes.base import C, Mode, bresenham


class Storm(Mode):
    NAME = 'STORM'
    ORDER = 13

    def __init__(self):
        self.storm_pts = []
        self.storm_age = 0

    def _lightning(self, x, y0, y1, roughness=10, min_seg=3):
        segs = [(x, y0, x, y1)]
        result = []
        while segs:
            x0, ya, x1, yb = segs.pop()
            if abs(yb - ya) < min_seg:
                result += bresenham(x0, ya, x1, yb)
                continue
            my = (ya + yb) // 2
            mx = (x0 + x1) // 2 + random.randint(-roughness, roughness)
            segs.append((x0, ya, mx, my))
            segs.append((mx, my, x1, yb))
            if random.random() < 0.28:
                fx = mx + random.randint(-18, 18)
                fy = min(my + random.randint(4, 22), y1)
                segs.append((mx, my, fx, fy))
        return result

    def render(self, buf, w, h, t, frame, cfg, pal, syms):
        p = pal

        if frame % 4 == 0:
            for _ in range(w * h // 35):
                self.put(buf, random.randint(0, w - 1), random.randint(0, h - 1), random.choice(syms), C['dim'], w, h)

        if self.storm_age <= 0 or not self.storm_pts:
            self.storm_pts = self._lightning(random.randint(w // 6, 5 * w // 6), 0, h - 1)
            self.storm_age = random.randint(3, 8)
            for y in range(h):
                for x in range(w):
                    buf[y][x] = (random.choice(syms), C[p['a']])

        self.storm_age -= 1
        half = len(self.storm_pts) // 2
        for i, (x, y) in enumerate(self.storm_pts):
            if 0 <= x < w and 0 <= y < h:
                col = C[p['a']] if i < 4 else C[p['p']] if i < half else C[p['s']]
                buf[y][x] = (random.choice(['│', '╎', '▌', '█', '╷']), col)
