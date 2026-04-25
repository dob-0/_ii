import math
import random

from modes.base import C, Mode


class Pulse(Mode):
    NAME = 'PULSE'
    ORDER = 5

    def render(self, buf, w, h, t, frame, cfg, pal, syms):
        p = pal
        cx = w // 2
        cy = h // 2
        max_r = math.sqrt(cx ** 2 + (cy * 2) ** 2)
        bpm = cfg.get('bpm', 140)
        beat = 60.0 / max(1, bpm)
        audio_peak = float(cfg.get('audio_peak', 0.0) or 0.0)
        audio_level = float(cfg.get('audio_level', 0.0) or 0.0)
        energy = max(audio_peak, audio_level * 0.6)

        t_full = (t % beat) / beat
        t_half = (t % (beat * 0.5)) / (beat * 0.5)
        t_qtr  = (t % (beat * 0.25)) / (beat * 0.25)

        r_full = t_full * max_r * (1.0 + energy * 0.18)
        r_half = t_half * max_r * 0.55
        r_qtr  = t_qtr  * max_r * 0.28

        ring_w_main = 2.5 + energy * 2.5

        self.clear(buf, w, h)

        for y in range(h):
            dy = (y - cy) * 2
            for x in range(w):
                dx = x - cx
                r = math.sqrt(dx * dx + dy * dy)

                d_full = abs(r - r_full)
                d_half = abs(r - r_half)
                d_qtr  = abs(r - r_qtr)

                if d_full < ring_w_main:
                    bri = 1.0 - d_full / ring_w_main
                    col = C[p['a']] if bri > 0.55 else C[p['p']]
                    buf[y][x] = ('█' if bri > 0.8 else random.choice(syms), col)
                elif d_half < 1.8:
                    buf[y][x] = (random.choice(syms), C[p['s']])
                elif d_qtr < 1.2:
                    buf[y][x] = (random.choice(syms), C['dim'])
                elif r < r_full - ring_w_main and random.random() < 0.025 + energy * 0.04:
                    buf[y][x] = (random.choice(syms), C[p['s']])

        # Center: brief blast on beat hit then hold ◈
        if t_full < 0.1:
            frac = 1.0 - t_full / 0.1
            col = C[p['a']] if frac > 0.5 else C[p['p']]
            ch = '█' if frac > 0.7 else '◈'
            self.put(buf, cx, cy, ch, col, w, h)
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                if random.random() < frac:
                    self.put(buf, cx + dx, cy + dy, random.choice(syms), C[p['p']], w, h)
        else:
            self.put(buf, cx, cy, '◈', C[p['a']], w, h)
