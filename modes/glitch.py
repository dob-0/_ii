import math, random
from modes.base import Mode, C, LOGO


class Glitch(Mode):
    NAME  = 'GLITCH'
    ORDER = 2

    def render(self, buf, w, h, t, frame, cfg, pal, syms):
        p         = pal
        intensity = float(cfg.get('glitch_intensity', 0.4))

        # Sparse scanline noise
        n = max(1, int(h * intensity * random.random()))
        for _ in range(n):
            y   = random.randint(0, h - 1)
            col = random.choice([C[p['p']], C[p['a']], C[p['s']], C['dim']])
            if random.random() < 0.18:
                buf[y][:] = [None] * w
            else:
                off  = random.randint(0, 6)
                line = ' ' * off + ''.join(random.choice(syms) for _ in range(w))
                for x in range(w):
                    ch = line[x] if x < len(line) else ' '
                    buf[y][x] = (ch, col) if ch != ' ' else None

        # Horizontal band shift — chromatic aberration / video corruption
        n_bands = int(intensity * random.random() * 7)
        for _ in range(n_bands):
            y0    = random.randint(0, h - 1)
            rows  = random.randint(1, max(1, int(h * 0.07)))
            shift = random.choice([-1, 1]) * random.randint(3, max(3, w // 6))
            col   = random.choice([C[p['a']], C[p['p']], C[p['s']]])
            for y in range(y0, min(h, y0 + rows)):
                row = buf[y][:]
                if shift > 0:
                    new_row = [None] * min(shift, w) + row[:max(0, w - shift)]
                else:
                    s = min(abs(shift), w)
                    new_row = row[s:] + [None] * s
                for x in range(min(w, len(new_row))):
                    cell = new_row[x]
                    buf[y][x] = (cell[0], col) if cell is not None else None

        # Scan-hold: duplicate a band of rows (VHS freeze artifact)
        if random.random() < intensity * 0.25:
            src_y = random.randint(0, max(0, h - 4))
            for dy in range(1, random.randint(2, 4)):
                if src_y + dy < h:
                    buf[src_y + dy][:] = list(buf[src_y])

        # LOGO flash
        if frame % 53 == 0:
            sy = (h - len(LOGO)) // 2
            for i, row in enumerate(LOGO):
                sx  = max(0, (w - len(row)) // 2)
                ly  = sy + i
                col = C[p['a']] if math.sin(frame * 0.12 + i * 0.4) > 0 else C[p['p']]
                if 0 <= ly < h:
                    for x, ch in enumerate(row[:w - sx]):
                        if ch not in (' ', ''):
                            buf[ly][sx + x] = (ch, col)
