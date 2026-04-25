import math
import random

from modes.base import C, Mode

BLOCK5 = {
    'M': ['█   █', '██ ██', '█ █ █', '█   █', '█   █'],
    'O': [' ███ ', '█   █', '█   █', '█   █', ' ███ '],
    'C': [' ████', '█    ', '█    ', '█    ', ' ████'],
    'T': ['█████', '  █  ', '  █  ', '  █  ', '  █  '],
    '7': ['█████', '   █ ', '  ██ ', ' █   ', '█    '],
    'H': ['█   █', '█   █', '█████', '█   █', '█   █'],
    'A': [' ███ ', '█   █', '█████', '█   █', '█   █'],
    'Y': ['█   █', ' █ █ ', '  █  ', '  █  ', '  █  '],
    'F': ['█████', '█    ', '████ ', '█    ', '█    '],
    'I': ['███  ', ' █   ', ' █   ', ' █   ', '███  '],
    'L': ['█    ', '█    ', '█    ', '█    ', '█████'],
    'S': [' ████', '█    ', ' ███ ', '    █', '████ '],
    'U': ['█   █', '█   █', '█   █', '█   █', ' ███ '],
    'D': ['████ ', '█   █', '█   █', '█   █', '████ '],
    'R': ['████ ', '█   █', '████ ', '█ █  ', '█  ██'],
    'E': ['█████', '█    ', '████ ', '█    ', '█████'],
    'B': ['████ ', '█   █', '████ ', '█   █', '████ '],
    'N': ['█   █', '██  █', '█ █ █', '█  ██', '█   █'],
    'G': [' ████', '█    ', '█  ██', '█   █', ' ████'],
    'P': ['████ ', '█   █', '████ ', '█    ', '█    '],
    'V': ['█   █', '█   █', '█   █', ' █ █ ', '  █  '],
    'W': ['█   █', '█   █', '█ █ █', '██ ██', '█   █'],
    'X': ['█   █', ' █ █ ', '  █  ', ' █ █ ', '█   █'],
    'Z': ['█████', '   █ ', '  █  ', ' █   ', '█████'],
    'K': ['█   █', '█  █ ', '███  ', '█  █ ', '█   █'],
    'J': ['  ███', '   █ ', '   █ ', '█  █ ', ' ██  '],
    '&': [' ██  ', '█  █ ', ' ███ ', '█ █  ', ' ██ █'],
    ' ': ['     ', '     ', '     ', '     ', '     '],
    '-': ['     ', '     ', '███  ', '     ', '     '],
}


class Poster(Mode):
    NAME = 'POSTER'
    ORDER = 18

    WORDS = [
        'MOCT', 'HAYFILM', 'STUDIO', 'BAR', 'PROJECTOR', 'BAK',
        'YEREVAN', '25-26', 'APRIL', '7 YEARS',
    ]

    def _block(self, buf, w, h, text, y0, col, scale=1):
        gap = scale
        char_w = 5 * scale + gap
        total = len(text) * char_w - gap
        x0 = max(0, (w - total) // 2)
        for ci, ch in enumerate(text.upper()):
            glyph = BLOCK5.get(ch, BLOCK5[' '])
            cx = x0 + ci * char_w
            for ri, row in enumerate(glyph):
                y = y0 + ri
                if y >= h:
                    break
                for gi, cell in enumerate(row):
                    if cell == '█':
                        for s in range(scale):
                            self.put(buf, cx + gi * scale + s, y, '█', col, w, h)

    def _write(self, buf, w, h, x, y, text, col):
        for i, ch in enumerate(text[: max(0, w - x)]):
            if ch != ' ':
                self.put(buf, x + i, y, ch, col, w, h)

    def render(self, buf, w, h, t, frame, cfg, pal, syms):
        audio = float(cfg.get('audio_level', 0.0) or 0.0)
        peak = float(cfg.get('audio_peak', 0.0) or 0.0)
        cam = max(
            float(cfg.get('camera4_motion', 0.0) or 0.0),
            float(cfg.get('camera2_motion', 0.0) or 0.0),
        )
        energy = max(0.0, min(1.0, audio * 0.8 + peak * 0.45 + cam * 0.9))
        tf = frame * (0.025 + energy * 0.06)

        palette = int(cfg.get('palette', 0) or 0) % 6
        if palette == 1:
            bg, fg, hot, dark = C['dim'],     C['white'],   C['yellow'],  C['dim']
        elif palette == 2:
            bg, fg, hot, dark = C['blue'],    C['white'],   C['cyan'],    C['dim']
        elif palette == 3:
            bg, fg, hot, dark = C['dim'],     C['magenta'], C['white'],   C['dim']
        elif palette == 4:
            bg, fg, hot, dark = C['dim'],     C['yellow'],  C['magenta'], C['dim']
        elif palette == 5:
            bg, fg, hot, dark = C['blue'],    C['cyan'],    C['magenta'], C['dim']
        else:
            bg, fg, hot, dark = C['dim'],     C['white'],   C['blue'],    C['dim']

        # Glitch background
        block = max(3, int(7 - energy * 4))
        for y in range(h):
            for x in range(w):
                glitch = ((x // block + y // block + frame // 9) % 5 == 0)
                stripe = (int((x + math.sin(y * 0.22 + tf) * 8) / max(2, block)) % 7 == 0)
                if glitch and random.random() < 0.72:
                    ch = random.choice(['█', '▓', '▒', ' '])
                    buf[y][x] = (ch, bg if ch != ' ' else dark)
                elif stripe and random.random() < 0.45:
                    buf[y][x] = (random.choice(['.', '·', '░']), dark)
                else:
                    buf[y][x] = None

        # Concentric arcs — MOCT/Tresor signature
        cx = w * (0.50 + math.sin(tf * 0.9) * 0.06)
        cy = h * 0.54
        for band in range(6):
            r = min(w, h * 2) * (0.18 + band * 0.07 + energy * 0.04)
            steps = max(60, int(r * math.pi * 1.2))
            for i in range(steps):
                a = -2.8 + i / (steps - 1) * 2.5 + math.sin(tf + band * 0.6) * 0.07
                x = int(cx + math.cos(a) * r)
                y = int(cy + math.sin(a) * r * 0.44)
                if i % 2 == 0:
                    self.put(buf, x, y, '─', fg if band < 3 else dark, w, h)

        # Determine phase: 0=MOCT, 1=HAYFILM, 2=date
        phase = (frame // 180) % 3

        # Scale block text to fit width
        if phase == 0:
            line1, line2 = 'MOCT', '7'
            sc1 = max(1, min(3, (w - 4) // (4 * 6 + 3)))
            sc2 = max(1, min(5, (w - 4) // 8))
        elif phase == 1:
            line1, line2 = 'HAYFILM', 'CLUSTER'
            sc1 = max(1, min(2, (w - 4) // (7 * 6 + 6)))
            sc2 = sc1
        else:
            line1, line2 = 'STUDIO', 'BAR'
            sc1 = max(1, min(2, (w - 4) // (6 * 6 + 5)))
            sc2 = max(1, min(3, (w - 4) // (3 * 6 + 2)))

        y0 = max(1, h // 9)
        self._block(buf, w, h, line1, y0, fg, scale=sc1)
        y1 = y0 + 5 * sc1 + 2
        self._block(buf, w, h, line2, y1, hot, scale=sc2)

        # Corner metadata
        meta = [
            ('25-26 APRIL', 2, 1),
            ('HAYFILM CLUSTER', max(2, w - 17), 1),
            ('MOCT 07 YEARS', 2, max(1, h - 3)),
            ('YEREVAN', max(2, w - 9), max(1, h - 3)),
        ]
        for text, x, y in meta:
            self._write(buf, w, h, x, y, text, fg if random.random() > 0.12 else hot)

        # Stage labels
        labels = ['STUDIO', 'BAR', 'PROJECTOR ROOM', 'BAK']
        active = frame // 60 % len(labels)
        for i, label in enumerate(labels):
            x = 4 + (i * max(8, w // 4)) % max(8, w - 20)
            y = max(2, h // 2 + (i % 2) * 4 - 2)
            self._write(buf, w, h, x, y, label, hot if i == active else fg)

        # Cross marks (energy-reactive count)
        for _ in range(8 + int(energy * 18)):
            x = random.randint(1, max(1, w - 2))
            y = random.randint(1, max(1, h - 2))
            self.put(buf, x, y, '+', fg if random.random() > 0.3 else hot, w, h)

        # Bottom scrolling strip
        strip = '  /  '.join(self.WORDS)
        repeated = (strip + '   ') * ((w // max(1, len(strip))) + 3)
        off = (frame // 2) % max(1, len(strip))
        self._write(buf, w, h, 0, h - 1, repeated[off:off + w], hot if peak > 0.35 else fg)
