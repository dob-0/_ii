import random

from modes.base import C, CUBE_E, CUBE_V, Mode, bresenham, rot3d


class Cube(Mode):
    NAME = 'CUBE'
    ORDER = 14

    def render(self, buf, w, h, t, frame, cfg, pal, syms):
        p = pal
        cx = w // 2
        cy = h // 2
        tf = frame * 0.03
        sc = min(cx, cy * 2) * 0.58

        if frame % 3 == 0:
            for _ in range(w * h // 50):
                self.put(buf, random.randint(0, w - 1), random.randint(0, h - 1), random.choice(syms), C['dim'], w, h)

        verts = rot3d(CUBE_V, tf * 0.7, tf, tf * 0.4)

        def proj(x, y, z):
            zc = z + 3.5
            if zc <= 0:
                return None
            return int(cx + x / zc * sc), int(cy + y / zc * sc * 0.5)

        ecols = [C[p['a']], C[p['p']], C[p['s']]]
        for ei, (i, j) in enumerate(CUBE_E):
            p0 = proj(*verts[i])
            p1 = proj(*verts[j])
            if not p0 or not p1:
                continue
            col = ecols[ei % 3]
            ch = random.choice(['█', '▓', '◈', '7', 'M'])
            for bx, by in bresenham(p0[0], p0[1], p1[0], p1[1]):
                if 0 <= bx < w and 0 <= by < h:
                    buf[by][bx] = (ch, col)

        for v in verts:
            pt = proj(*v)
            if pt and 0 <= pt[0] < w and 0 <= pt[1] < h:
                buf[pt[1]][pt[0]] = ('◈', C[p['a']])
