import math
from modes.base import C, Mode


class MapTest(Mode):
    NAME = 'MAPTST'
    ORDER = 20

    def render(self, buf, w, h, t, frame, cfg, pal, syms):
        self.clear(buf, w, h)
        p = pal
        ca = C[p['p']]
        cs = C[p['s']]
        cd = C['dim']

        # Dot grid — every 10 cols, every 5 rows
        for y in range(0, h, 5):
            for x in range(w):
                buf[y][x] = ('·', cd)
        for x in range(0, w, 10):
            for y in range(h):
                if buf[y][x] is None:
                    buf[y][x] = ('·', cd)

        # Safe-area border (5 % inset)
        sx0 = max(1, int(w * 0.05))
        sy0 = max(1, int(h * 0.05))
        sx1 = min(w - 2, int(w * 0.95))
        sy1 = min(h - 2, int(h * 0.95))
        for x in range(sx0, sx1 + 1):
            buf[sy0][x] = ('─', cs)
            buf[sy1][x] = ('─', cs)
        for y in range(sy0, sy1 + 1):
            buf[y][sx0] = ('│', cs)
            buf[y][sx1] = ('│', cs)
        buf[sy0][sx0] = ('┌', cs)
        buf[sy0][sx1] = ('┐', cs)
        buf[sy1][sx0] = ('└', cs)
        buf[sy1][sx1] = ('┘', cs)

        # Outer frame
        for x in range(w):
            buf[0][x] = ('█', ca)
            if h > 1:
                buf[h - 1][x] = ('█', ca)
        for y in range(1, h - 1):
            buf[y][0] = ('█', ca)
            if w > 1:
                buf[y][w - 1] = ('█', ca)

        # Corner crosshairs (+2 reach)
        def cross(cy, cx, size=2):
            for d in range(-size, size + 1):
                if 0 <= cx + d < w:
                    buf[cy][cx + d] = ('+', ca)
                if 0 <= cy + d < h:
                    buf[cy + d][cx] = ('+', ca)
            if 0 <= cy < h and 0 <= cx < w:
                buf[cy][cx] = ('X', ca)

        cross(2, 2)
        cross(2, w - 3)
        cross(h - 3, 2)
        cross(h - 3, w - 3)

        # Center crosshair
        mcx, mcy = w // 2, h // 2
        for d in range(-5, 6):
            if 0 <= mcx + d < w:
                buf[mcy][mcx + d] = ('+', ca)
        for d in range(-3, 4):
            if 0 <= mcy + d < h:
                buf[mcy + d][mcx] = ('+', ca)
        # Beat pulse on center marker
        beat = (t * float(cfg.get('bpm', 140)) / 60.0) % 1.0
        center_ch = '◉' if beat < 0.15 else '■'
        center_col = C[p['a']] if beat < 0.15 else ca
        buf[mcy][mcx] = (center_ch, center_col)

        # Size label below center
        info = f'{w}×{h}'
        ix = mcx - len(info) // 2
        for i, ch in enumerate(info):
            if 0 <= ix + i < w and 0 <= mcy + 2 < h:
                buf[mcy + 2][ix + i] = (ch, cs)

        # Zone ID top-left (passed in via cfg when running inside a zone)
        zone_id = cfg.get('_map_zone_id', '')
        if zone_id and h > 2 and w > 4:
            label = f'[{zone_id}]'
            for i, ch in enumerate(label[:w - 2]):
                buf[1][1 + i] = (ch, cs)
