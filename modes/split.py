import math
import random
import re

from modes.base import C, Mode


class Split(Mode):
    NAME = 'SPLIT'
    ORDER = 21

    def _parts(self, value, fallback):
        raw = str(value or fallback)
        items = [part.strip() for part in re.split(r'[|\n]+', raw) if part.strip()]
        return items or fallback

    def render(self, buf, w, h, t, frame, cfg, pal, syms):
        audio = float(cfg.get('audio_level', 0.0) or 0.0)
        peak = float(cfg.get('audio_peak', 0.0) or 0.0)
        cam = max(
            float(cfg.get('camera4_motion', 0.0) or 0.0),
            float(cfg.get('camera2_motion', 0.0) or 0.0),
        )
        energy = max(0.0, min(1.0, audio * 0.6 + peak * 0.6 + cam * 0.75))
        tf = frame * (0.02 + energy * 0.045)
        primary = C[pal['p']]
        secondary = C[pal['s']]
        accent = C[pal['a']]
        dark = C['dim']

        title = str(cfg.get('event_title', cfg.get('flash_text', 'SYNAPSE')) or 'SYNAPSE').upper()
        kicker = str(cfg.get('event_kicker', 'EPOCA ->') or 'EPOCA ->').upper()
        when = str(cfg.get('event_when', 'MAY 15') or 'MAY 15').upper()
        stage_a = str(cfg.get('event_stage_a', cfg.get('event_where', 'STUDIO')) or 'STUDIO').upper()
        stage_b = str(cfg.get('event_stage_b', 'BAR') or 'BAR').upper()
        lineup_a = self._parts(cfg.get('event_lineup_a'), ['UVALL [GE]', 'HONNELOOK', 'SCRIPT [GE]', 'FUKUMACHI [GE]', 'MTVARE [GE]'])
        lineup_b = self._parts(cfg.get('event_lineup_b'), ['MARS', 'ICECHAIN', 'MA', 'LYUPEN', 'ISO'])
        footer = str(cfg.get('event_footer', 'SCIENCE AND SPIRIT') or 'SCIENCE AND SPIRIT').upper()

        for y in range(h):
            for x in range(w):
                if y % 5 == 0 and random.random() < 0.16:
                    buf[y][x] = (random.choice(['─', '·']), dark)
                elif x > w * 0.50 and random.random() < 0.05 + energy * 0.03:
                    buf[y][x] = (random.choice(['░', '▒']), primary)
                else:
                    buf[y][x] = None

        # sliced chrome mass on right
        cx = w * 0.76
        for y in range(h):
            band = int((y / max(1, h)) * 11)
            shift = math.sin(tf * 2.1 + band * 0.85) * (2.0 + energy * 6.0)
            for x in range(int(w * 0.45), w):
                dx = (x - shift - cx) / max(1.0, w * 0.18)
                dy = (y - h * 0.53) / max(1.0, h * 0.38)
                arc = 1.0 / (0.28 + dx * dx * 1.2 + dy * dy * 1.8)
                wave = math.sin((x * 0.08) - tf * 2.0 + y * 0.03) * 0.28
                v = arc + wave
                if v > 2.1:
                    buf[y][x] = ('█', C['white'])
                elif v > 1.8:
                    buf[y][x] = (random.choice(['█', '▓']), accent)
                elif v > 1.5:
                    buf[y][x] = (random.choice(['▓', '▒']), secondary)
                elif v > 1.28 and random.random() < 0.75:
                    buf[y][x] = (random.choice(['▒', '░']), primary)

        meta = f'{kicker} {when}'
        mx = max(2, int(w * 0.08))
        my = max(2, h // 9)
        for i, ch in enumerate(meta[: max(0, w - mx - 2)]):
            if ch != ' ':
                self.put(buf, mx + i, my, ch, C['white'], w, h)
        title_y = my + 3
        title_x = max(2, (w - len(title)) // 2)
        for i, ch in enumerate(title[: max(0, w - title_x - 2)]):
            if ch != ' ':
                self.put(buf, title_x + i, title_y, ch, C['white'], w, h)
        for x in range(max(0, title_x), min(w, title_x + len(title) - 4)):
            self.put(buf, x, title_y + 2, '─', primary, w, h)

        left_x = max(2, int(w * 0.08))
        y0 = title_y + 5
        sections = [
            (stage_a, lineup_a, y0),
            (stage_b, lineup_b, y0 + 2 + len(lineup_a) * 2),
        ]
        for si, (label, artists, sy) in enumerate(sections):
            for i, ch in enumerate(label):
                if ch != ' ':
                    self.put(buf, left_x + i, sy, ch, C['white'], w, h)
            for li, name in enumerate(artists):
                row_y = sy + 2 + li * 2
                col = C['white'] if (li + si) % 2 == 0 else accent
                for i, ch in enumerate(name.upper()[: max(0, w - left_x - 2)]):
                    if ch != ' ':
                        self.put(buf, left_x + i, row_y, ch, col, w, h)

        fy = max(1, h - 3)
        for i, ch in enumerate(footer[: max(0, w - left_x - 2)]):
            if ch != ' ':
                self.put(buf, left_x + i, fy, ch, C['white'], w, h)
