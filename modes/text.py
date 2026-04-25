import math
import random

from modes.base import C, Mode


class Text(Mode):
    NAME = 'TEXT'
    ORDER = 6

    def render(self, buf, w, h, t, frame, cfg, pal, syms):
        p = pal
        text = cfg.get('flash_text', 'MOCT 7') or 'MOCT 7'

        for _ in range(w * h // 25):
            self.put(buf, random.randint(0, w - 1), random.randint(0, h - 1), random.choice(syms), C['dim'], w, h)

        tile = text + '  '
        repeated = tile * ((w // max(1, len(tile))) + 3)
        band_gap = max(3, h // 5)

        for row in range(5):
            y = (row * band_gap + frame // 3) % h
            offset = (frame + row * 17) % len(tile)
            line = repeated[offset: offset + w]
            glitched = ''.join(random.choice(syms) if random.random() < 0.07 else c for c in line)
            col = C[p['p']] if (row + frame // 5) % 2 == 0 else C[p['a']]
            for x, ch in enumerate(glitched[:w]):
                if ch == ' ':
                    buf[y][x] = None
                else:
                    buf[y][x] = (ch, col)

        cy = h // 2
        cx = max(0, (w - len(text)) // 2)
        big = ''.join(random.choice(syms) if random.random() < 0.05 else c for c in text)
        col = C[p['a']] if math.sin(frame * 0.2) > 0 else C[p['p']]
        for x, ch in enumerate(big[: w - cx]):
            if ch != ' ':
                buf[cy][cx + x] = (ch, col)

        for dy in (1, 2):
            y = cy + dy
            if y >= h:
                continue
            spaced = ' '.join(text)[: w - cx]
            for x, ch in enumerate(spaced):
                if ch != ' ':
                    buf[y][cx + x] = (ch, C[p['s']])
