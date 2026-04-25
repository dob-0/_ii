import random

from modes.base import C, Mode


class Grid(Mode):
    NAME = 'GRID'
    ORDER = 10

    def render(self, buf, w, h, t, frame, cfg, pal, syms):
        p = pal
        horizon = h // 3
        cx = w // 2
        fov = float(max(w, h) * 2)
        gs = 3.0
        z_off = (frame * 0.04) % gs
        self.clear(buf, w, h)

        for _ in range(50):
            x = random.randint(0, w - 1)
            y = random.randint(0, max(0, horizon - 1))
            ch = random.choice(['.', '·', '+'])
            col = C[p['a']] if random.random() < 0.15 else C['dim']
            buf[y][x] = (ch, col)

        sw = min(w // 5, 22)
        sx = cx - sw // 2
        for i in range(4):
            ys = horizon - i - 1
            if ys < 0 or ys >= h:
                continue
            col = C[p['a']] if i == 0 else C[p['p']] if i == 1 else C[p['s']] if i == 2 else C['dim']
            for x in range(max(0, sx), min(w, sx + sw)):
                buf[ys][x] = ('▄', col)

        for n in range(1, 50):
            z = n * gs - z_off + 0.01
            if z <= 0:
                continue
            y = int(horizon + fov / z)
            if not (horizon < y < h):
                continue
            df = (y - horizon) / max(1, (h - horizon))
            col = C[p['p']] if df > 0.55 else C[p['s']] if df > 0.25 else C['dim']
            for x in range(w):
                buf[y][x] = ('─', col)

        for i in range(-11, 12):
            xw = i * 1.1
            for y in range(horizon, h):
                x = int(cx + xw * (y - horizon))
                if 0 <= x < w:
                    df = (y - horizon) / max(1, (h - horizon))
                    col = C[p['p']] if df > 0.55 else C[p['s']] if df > 0.25 else C['dim']
                    buf[y][x] = ('│', col)
