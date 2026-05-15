"""Projection mapping engine — zone/surface routing."""

import json
import os

_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mappings')


def load_mappings():
    """Return sorted list of mapping configs from mappings/*.json."""
    result = []
    if not os.path.isdir(_DIR):
        return result
    for fname in sorted(os.listdir(_DIR)):
        if not fname.endswith('.json'):
            continue
        try:
            with open(os.path.join(_DIR, fname), encoding='utf-8') as f:
                data = json.load(f)
            data.setdefault('_file', fname)
            result.append(data)
        except Exception:
            pass
    return result


def _point_in_poly(px, py, pts):
    inside = False
    j = len(pts) - 1
    for i, (xi, yi) in enumerate(pts):
        xj, yj = pts[j]
        if ((yi > py) != (yj > py)
                and px < (xj - xi) * (py - yi) / max(0.000001, yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def _surface_points(surface, w, render_h):
    corners = surface.get('corners', [])
    if len(corners) != 4:
        return []
    pts = []
    for nx, ny in corners:
        pts.append((
            int(float(nx) * (w - 1)),
            int(float(ny) * (render_h - 1)),
        ))
    return pts


def _is_non_space(cell):
    return cell is not None and cell[0] != ' '


def _composite_sub(out, buf_a, buf_b, alpha, sw, sh):
    for sy in range(sh):
        row_out = out[sy]
        row_a = buf_a[sy]
        row_b = buf_b[sy]
        for sx in range(sw):
            b = row_b[sx]
            if _is_non_space(b) and (alpha >= 0.999 or random.random() < alpha):
                row_out[sx] = b
            else:
                row_out[sx] = row_a[sx]


def _render_mode_stack(sw, sh, modes, mode_idx, mode_b_idx, merged, pal, syms, t_now, frame):
    out = [[None] * sw for _ in range(sh)]
    modes[mode_idx].render(out, sw, sh, t_now, frame, merged, pal, syms)
    if not bool(merged.get('layer_b_enabled', False)):
        return out

    alpha = float(merged.get('layer_b_alpha', 1.0) or 0.0)
    buf_a = out
    buf_b = [[None] * sw for _ in range(sh)]
    out = [[None] * sw for _ in range(sh)]
    modes[mode_b_idx].render(buf_b, sw, sh, t_now, frame, merged, pal, syms)
    _composite_sub(out, buf_a, buf_b, alpha, sw, sh)
    return out


def _render_surfaces(buf, w, render_h, modes, active_mode, mapping, merged, pal, syms, t, frame):
    surfaces = [s for s in mapping.get('surfaces', []) if s.get('enabled', True)]
    if not surfaces:
        return False

    if (len(surfaces) == 1
            and surfaces[0].get('mode') is None
            and surfaces[0].get('corners') == [[0, 0], [1, 0], [1, 1], [0, 1]]):
        return False

    for row in buf:
        row[:] = [None] * w

    for surface in surfaces:
        pts = _surface_points(surface, w, render_h)
        if len(pts) != 4:
            continue

        min_x = max(0, min(x for x, _ in pts))
        max_x = min(w - 1, max(x for x, _ in pts))
        min_y = max(0, min(y for _, y in pts))
        max_y = min(render_h - 1, max(y for _, y in pts))
        sw = max_x - min_x + 1
        sh = max_y - min_y + 1
        if sw <= 0 or sh <= 0:
            continue

        mode_spec = surface.get('mode')
        mode_idx = active_mode if mode_spec is None else max(0, min(len(modes) - 1, int(mode_spec)))
        mode_b_idx = max(0, min(len(modes) - 1, int(merged.get('mode_b', mode_idx) or mode_idx)))

        surface_cfg = dict(merged)
        surface_cfg['_map_zone_id'] = surface.get('id', '')

        t_surface = t + float(surface.get('phase', 0.0) or 0.0)

        sub = _render_mode_stack(sw, sh, modes, mode_idx, mode_b_idx, surface_cfg, pal, syms, t_surface, frame)

        for sy in range(sh):
            dy = min_y + sy
            row_dst = buf[dy]
            row_src = sub[sy]
            for sx in range(sw):
                dx = min_x + sx
                if _point_in_poly(dx + 0.5, dy + 0.5, pts):
                    row_dst[dx] = row_src[sx]

    return True


def render_zones(buf, w, render_h, modes, active_mode, mapping, merged, pal, syms, t, frame):
    """Render mapping zones into buf. Returns True if zone rendering was applied.

    Skips and returns False for trivial single-zone full-screen mappings so the
    caller can use the normal A/B blend path instead.
    """
    if mapping.get('surfaces'):
        return _render_surfaces(buf, w, render_h, modes, active_mode, mapping, merged, pal, syms, t, frame)

    zones = [z for z in mapping.get('zones', []) if z.get('enabled', True)]
    if not zones:
        return False

    # Single full-screen zone with no forced mode → let caller handle normally
    if (len(zones) == 1
            and zones[0].get('mode') is None
            and zones[0].get('x', 0.0) == 0.0
            and zones[0].get('y', 0.0) == 0.0
            and zones[0].get('w', 1.0) >= 1.0
            and zones[0].get('h', 1.0) >= 1.0):
        return False

    for row in buf:
        row[:] = [None] * w

    for zone in zones:
        zx = max(0, int(zone.get('x', 0.0) * w))
        zy = max(0, int(zone.get('y', 0.0) * render_h))
        zw = max(1, int(zone.get('w', 1.0) * w))
        zh = max(1, int(zone.get('h', 1.0) * render_h))
        zw = min(zw, w - zx)
        zh = min(zh, render_h - zy)
        if zw <= 0 or zh <= 0:
            continue

        mode_spec = zone.get('mode')
        mode_idx = active_mode if mode_spec is None else max(0, min(len(modes) - 1, int(mode_spec)))
        mode_b_idx = max(0, min(len(modes) - 1, int(merged.get('mode_b', mode_idx) or mode_idx)))

        zone_cfg = dict(merged)
        zone_cfg['_map_zone_id'] = zone.get('id', '')

        t_zone = t + float(zone.get('phase', 0.0))

        sub = _render_mode_stack(zw, zh, modes, mode_idx, mode_b_idx, zone_cfg, pal, syms, t_zone, frame)

        for sy in range(zh):
            dy = zy + sy
            if 0 <= dy < render_h:
                row_dst = buf[dy]
                row_src = sub[sy]
                for sx in range(zw):
                    dx = zx + sx
                    if 0 <= dx < w:
                        row_dst[dx] = row_src[sx]

    return True
