import math
import random
import re

from modes.base import C, Mode


class Poster(Mode):
    NAME = 'POSTER'
    ORDER = 18

    DEFAULT_LINEUP = [
        'ARTIST A', 'ARTIST B', 'ARTIST C', 'ARTIST D',
    ]

    def _write(self, buf, w, h, x, y, text, col):
        if y < 0 or y >= h:
            return
        for i, ch in enumerate(text):
            if ch != ' ':
                self.put(buf, x + i, y, ch, col, w, h)

    def _hline(self, buf, w, h, x0, x1, y, ch, col):
        if y < 0 or y >= h:
            return
        for x in range(max(0, x0), min(w, x1)):
            self.put(buf, x, y, ch, col, w, h)

    def _meta(self, cfg, key, fallback):
        value = cfg.get(key)
        if value is None:
            return fallback
        text = str(value).strip()
        return text or fallback

    def _lineup(self, cfg):
        raw = self._meta(cfg, 'event_lineup', '|'.join(self.DEFAULT_LINEUP))
        items = [part.strip() for part in re.split(r'[|\n]+', raw) if part.strip()]
        return items or list(self.DEFAULT_LINEUP)

    def _title_text(self, cfg):
        title = self._meta(cfg, 'event_title', '') or self._meta(cfg, 'flash_text', 'SIGNAL')
        title = title.upper()
        if ' ' not in title and len(title) <= 10:
            return ' '.join(title)
        return re.sub(r'\s+', ' ', title)

    def _draw_blob(self, buf, w, h, tf, energy, primary, secondary, accent):
        x0 = max(0, int(w * 0.44))
        bodies = [
            (w * 0.80, h * 0.35, w * 0.17, h * 0.13),
            (w * 0.82, h * 0.55, w * 0.20, h * 0.15),
            (w * 0.76, h * 0.77, w * 0.16, h * 0.12),
        ]
        for y in range(h):
            for x in range(x0, w):
                field = 0.0
                for cx, cy, rx, ry in bodies:
                    dx = (x - cx) / max(1.0, rx)
                    dy = (y - cy) / max(1.0, ry)
                    field += 1.0 / (0.24 + dx * dx + dy * dy)
                ripple = (
                    math.sin(x * 0.16 - tf * 2.0) * 0.18 +
                    math.cos(y * 0.28 + tf * 1.5) * 0.18 +
                    math.sin((x + y) * 0.12 + tf * 2.2) * 0.12
                )
                v = field + ripple * (0.8 + energy * 0.6)
                if v <= 1.95:
                    continue
                sheen = math.sin((x * 0.32 - y * 0.18) + tf * 4.0)
                if v > 4.8 or (v > 3.9 and sheen > 0.45):
                    ch, col = '█', C['white']
                elif v > 3.6:
                    ch = random.choice(['█', '▓'])
                    col = accent
                elif v > 2.7:
                    ch = random.choice(['▓', '▒'])
                    col = secondary
                else:
                    ch = random.choice(['▒', '░'])
                    col = primary
                self.put(buf, x, y, ch, col, w, h)

    def render(self, buf, w, h, t, frame, cfg, pal, syms):
        audio = float(cfg.get('audio_level', 0.0) or 0.0)
        peak = float(cfg.get('audio_peak', 0.0) or 0.0)
        cam = max(
            float(cfg.get('camera4_motion', 0.0) or 0.0),
            float(cfg.get('camera2_motion', 0.0) or 0.0),
        )
        energy = max(0.0, min(1.0, audio * 0.8 + peak * 0.45 + cam * 0.9))
        tf = frame * (0.025 + energy * 0.06)
        fg = C['white']
        primary = C[pal['p']]
        secondary = C[pal['s']]
        accent = C[pal['a']]
        dark = C['dim']
        title = self._title_text(cfg)
        kicker = self._meta(cfg, 'event_kicker', 'LIVE SESSION').upper()
        when = self._meta(cfg, 'event_when', 'TONIGHT').upper()
        where = self._meta(cfg, 'event_where', 'MAIN ROOM').upper()
        footer = self._meta(cfg, 'event_footer', 'DOORS OPEN 23:00').upper()
        lineup = self._lineup(cfg)

        for y in range(h):
            for x in range(w):
                wave = math.sin(y * 0.18 + tf * 1.7 + x * 0.02)
                if y % 4 == 0 and random.random() < 0.12 + energy * 0.10:
                    buf[y][x] = (random.choice(['─', '·']), dark)
                elif x > w * 0.50 and y > h * 0.28 and x < w * 0.72 and random.random() < 0.58 + wave * 0.08:
                    buf[y][x] = (random.choice(['█', '▓', '▒']), primary)
                else:
                    buf[y][x] = None
        panel_x0 = max(0, int(w * 0.48))
        panel_x1 = min(w, int(w * 0.73))
        for y in range(int(h * 0.40), h):
            for x in range(panel_x0, panel_x1):
                if buf[y][x] is None or random.random() < 0.35:
                    buf[y][x] = (random.choice(['█', '▓']), primary)

        self._draw_blob(buf, w, h, tf, energy, primary, secondary, accent)

        meta_y = max(1, h // 9)
        meta = f'{kicker}   {when}'
        self._write(buf, w, h, 3, meta_y, meta, fg)
        self._hline(buf, w, h, 2, min(w - 2, 2 + len(meta) + 6), meta_y + 1, '─', dark)

        title_y = max(meta_y + 3, h // 5)
        title_x = max(2, (w - len(title)) // 2)
        self._write(buf, w, h, title_x + 1, title_y + 1, title, dark)
        self._write(buf, w, h, title_x, title_y, title, fg)
        self._hline(buf, w, h, title_x, min(w, title_x + len(title) - 6), title_y + 2, '─', primary)

        left_x = 3
        self._write(buf, w, h, left_x, title_y + 4, where, fg)
        self._hline(buf, w, h, left_x, min(w - 2, left_x + max(10, len(where) + 4)), title_y + 5, '─', dark)

        lineup_y = title_y + 6
        split = max(1, (len(lineup) + 1) // 2)
        columns = [lineup[:split], lineup[split:]]
        for ci, items in enumerate(columns):
            col_x = left_x + ci * max(18, w // 4)
            for li, name in enumerate(items):
                self._write(buf, w, h, col_x, lineup_y + li * 2, name.upper(), fg if (li + ci) % 3 else accent)

        for i in range(4):
            cx = int(w * 0.90)
            cy = int(h * (0.34 + i * 0.18))
            self.put(buf, cx, cy, '+', fg, w, h)
            self.put(buf, cx - 1, cy, '─', secondary, w, h)
            self.put(buf, cx + 1, cy, '─', secondary, w, h)
            self.put(buf, cx, cy - 1, '│', secondary, w, h)
            self.put(buf, cx, cy + 1, '│', secondary, w, h)

        footer_y = max(1, h - 3)
        self._write(buf, w, h, 3, footer_y, footer, fg)
        self._write(buf, w, h, max(3, w - len(when) - 4), footer_y, when, secondary)

        for _ in range(10 + int(energy * 10)):
            x = random.randint(0, max(0, w - 8))
            y = random.randint(1, max(1, h - 2))
            span = random.randint(3, max(3, w // 8))
            self._hline(buf, w, h, x, x + span, y, '─', dark if random.random() < 0.7 else primary)
