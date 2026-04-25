import math, random
from modes.base import Mode, C, LOGO


class Logo(Mode):
    NAME  = 'LOGO'
    ORDER = 4

    def render(self, buf, w, h, t, frame, cfg, pal, syms):
        p = pal
        for _ in range(w * h // 12):
            self.put(buf, random.randint(0, w-1), random.randint(0, h-1),
                     random.choice(syms), C[p['s']], w, h)
        sy = (h - len(LOGO)) // 2
        for i, row in enumerate(LOGO):
            sx  = max(0, (w - len(row)) // 2)
            ly  = sy + i
            col = C[p['p']] if math.sin(frame * 0.12 + i * 0.4) > 0 else C[p['a']]
            if 0 <= ly < h:
                for x, ch in enumerate(row[:w - sx]):
                    if ch not in (' ', ''):
                        buf[ly][sx + x] = (ch, col)
