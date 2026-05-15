import math
import random

from modes.base import C, Mode


class Shards(Mode):
    NAME = 'SHARDS'
    ORDER = 19

    def render(self, buf, w, h, t, frame, cfg, pal, syms):
        audio = float(cfg.get('audio_level', 0.0) or 0.0)
        peak = float(cfg.get('audio_peak', 0.0) or 0.0)
        cam = max(
            float(cfg.get('camera4_motion', 0.0) or 0.0),
            float(cfg.get('camera2_motion', 0.0) or 0.0),
        )
        energy = max(0.0, min(1.0, audio * 0.7 + peak * 0.6 + cam * 0.8))
        tf = frame * (0.024 + energy * 0.05)
        primary = C[pal['p']]
        secondary = C[pal['s']]
        accent = C[pal['a']]
        dark = C['dim']
        right_start = int(w * 0.38)
        slices = []
        for y in range(h):
            band = int((y / max(1, h)) * 14)
            offset = math.sin(tf * 2.2 + band * 0.9) * (3.0 + energy * 7.0)
            offset += math.cos(tf * 0.7 + y * 0.16) * 1.8
            slices.append(offset)

        bodies = [
            (w * 0.78, h * 0.24, w * 0.18, h * 0.10),
            (w * 0.72, h * 0.46, w * 0.20, h * 0.12),
            (w * 0.80, h * 0.74, w * 0.19, h * 0.11),
        ]

        for y in range(h):
            for x in range(w):
                base = None
                if y % 4 == 0 and random.random() < 0.10 + energy * 0.08:
                    base = (random.choice(['─', '·']), dark)
                elif x < right_start and random.random() < 0.02:
                    base = (random.choice(['·', '░']), dark)

                field = 0.0
                sx = x - slices[y]
                for cx, cy, rx, ry in bodies:
                    dx = (sx - cx) / max(1.0, rx)
                    dy = (y - cy) / max(1.0, ry)
                    field += 1.0 / (0.22 + dx * dx + dy * dy)
                ripple = (
                    math.sin((sx * 0.10) - tf * 1.8) * 0.22 +
                    math.cos((y * 0.24) + tf * 1.3) * 0.18 +
                    math.sin((sx + y) * 0.08 + tf * 2.0) * 0.16
                )
                v = field + ripple * (0.9 + energy * 0.5)
                if v > 5.1:
                    cell = ('█', C['white'])
                elif v > 4.0:
                    cell = (random.choice(['█', '▓']), accent)
                elif v > 3.0:
                    cell = (random.choice(['▓', '▒']), secondary)
                elif v > 2.25:
                    cell = (random.choice(['▒', '░']), primary)
                else:
                    cell = base
                buf[y][x] = cell

        title = str(cfg.get('event_title', cfg.get('flash_text', 'SYNAPSE')) or 'SYNAPSE').upper()
        meta = f"{str(cfg.get('event_kicker', 'EPOCA ->')).upper()} {str(cfg.get('event_when', 'MAY 15')).upper()}"
        tx = max(2, int(w * 0.08))
        ty = max(2, h // 8)
        for i, ch in enumerate(meta[: max(0, w - tx - 2)]):
            if ch != ' ':
                self.put(buf, tx + i, ty, ch, C['white'], w, h)
        for i, ch in enumerate(title[: max(0, w - tx - 2)]):
            if ch != ' ':
                self.put(buf, tx + i, ty + 3, ch, C['white'], w, h)

