import random
from modes.base import Mode, C, beat_phase


class Strobe(Mode):
    NAME  = 'STROBE'
    ORDER = 3

    def render(self, buf, w, h, t, frame, cfg, pal, syms):
        p       = pal
        density = cfg.get('rain_density', 0.7)
        speed   = max(1, int(cfg.get('strobe_speed', 2)))
        bpm     = cfg.get('bpm', 140)
        on = (beat_phase(t, bpm) < 0.5
              if cfg.get('bpm_sync')
              else (frame // speed) % 2 == 0)
        if on:
            col = random.choice([C[p['p']], C[p['a']]])
            for y in range(h):
                for x in range(w):
                    buf[y][x] = (random.choice(syms), col) if random.random() < density else None
        else:
            self.clear(buf, w, h)
