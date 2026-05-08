"""MOCT7 | Projection mapping engine — zone routing."""

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


def render_zones(buf, w, render_h, modes, active_mode, mapping, merged, pal, syms, t, frame):
    """Render mapping zones into buf. Returns True if zone rendering was applied.

    Skips and returns False for trivial single-zone full-screen mappings so the
    caller can use the normal A/B blend path instead.
    """
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

        zone_cfg = dict(merged)
        zone_cfg['_map_zone_id'] = zone.get('id', '')

        sub = [[None] * zw for _ in range(zh)]
        modes[mode_idx].render(sub, zw, zh, t, frame, zone_cfg, pal, syms)

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
