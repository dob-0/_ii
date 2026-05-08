#!/usr/bin/env python3
"""_ii — stage-aware launcher for visuals.

Usage:
  python3 window.py           # spawn visuals in a dedicated terminal window
  python3 window.py --inline  # run visuals in the current terminal
"""

import os
import shlex
import shutil
import subprocess
import sys
import time

from architecture import BASE, CONFIG_PATH, VISUALS_PATH, load_json

WINDOW_CHILD_ENV = 'MCT7_WINDOW_CHILD'
DEFAULT_TITLE = 'ii-VISUALS'
AUTO_SECOND_MONITOR = 'auto-second'
KWIN_SCRIPT_NAME = 'ii_visuals_placement'
KWIN_SCRIPT_PATH = os.path.join(BASE, 'scripts', 'kwin-place-visuals.js')


def _cfg():
    return load_json(CONFIG_PATH, {})


def _title(cfg):
    return cfg.get('visuals_window_title', DEFAULT_TITLE)


def _inline_cmd():
    return [sys.executable, VISUALS_PATH]


def _child_script():
    return (
        f'cd {shlex.quote(BASE)} && '
        f'export {WINDOW_CHILD_ENV}=1 && '
        f'exec {shlex.quote(sys.executable)} {shlex.quote(__file__)} --inline'
    )


def _custom_spawn_cmd(cfg):
    custom = cfg.get('visuals_launch_cmd')
    if isinstance(custom, list) and custom:
        return custom
    if isinstance(custom, str) and custom.strip():
        return shlex.split(custom)
    return []


def _spawn_cmd(cfg):
    custom = _custom_spawn_cmd(cfg)
    if custom:
        return custom

    title = _title(cfg)
    child = _child_script()
    fullscreen = cfg.get('visuals_fullscreen', True)
    preferred = cfg.get('visuals_terminal', 'auto')
    wm_rules_available = shutil.which('wmctrl') and shutil.which('xrandr')

    commands = []
    if preferred in ('auto', 'kitty') and shutil.which('kitty'):
        cmd = ['kitty', '--title', title]
        if fullscreen:
            cmd.append('--start-as=fullscreen')
        cmd.extend(['sh', '-lc', child])
        commands.append(cmd)
    if preferred in ('auto', 'x-terminal-emulator') and shutil.which('x-terminal-emulator'):
        commands.append(['x-terminal-emulator', '-e', 'sh', '-lc', child])
    if preferred in ('auto', 'gnome-terminal') and shutil.which('gnome-terminal'):
        commands.append(['gnome-terminal', '--title', title, '--', 'sh', '-lc', child])
    if preferred in ('auto', 'xterm') and shutil.which('xterm'):
        commands.append(['xterm', '-T', title, '-e', 'sh', '-lc', child])
    return commands[0] if commands else []


def _is_kde_wayland():
    desktop = os.environ.get('XDG_CURRENT_DESKTOP', '')
    return (
        os.environ.get('XDG_SESSION_TYPE') == 'wayland'
        and 'KDE' in desktop.upper()
        and shutil.which('qdbus')
    )


def _install_kwin_placement_rule(cfg, title):
    if not _is_kde_wayland():
        return False

    monitor_name = cfg.get('visuals_monitor') or AUTO_SECOND_MONITOR
    fullscreen = bool(cfg.get('visuals_fullscreen', True))
    try:
        subprocess.run(
            ['qdbus', 'org.kde.KWin', '/Scripting', 'org.kde.kwin.Scripting.unloadScript', KWIN_SCRIPT_NAME],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        loaded = subprocess.run(
            ['qdbus', 'org.kde.KWin', '/Scripting', 'org.kde.kwin.Scripting.loadScript', KWIN_SCRIPT_PATH, KWIN_SCRIPT_NAME],
            capture_output=True,
            text=True,
            check=False,
        )
        if loaded.returncode != 0:
            return False
        subprocess.run(
            [
                'qdbus', 'org.kde.KWin',
                f'/Scripting/Script{loaded.stdout.strip()}',
                'org.kde.kwin.Script.setConfig',
                'title',
                title,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        subprocess.run(
            [
                'qdbus', 'org.kde.KWin',
                f'/Scripting/Script{loaded.stdout.strip()}',
                'org.kde.kwin.Script.setConfig',
                'output',
                monitor_name,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        subprocess.run(
            [
                'qdbus', 'org.kde.KWin',
                f'/Scripting/Script{loaded.stdout.strip()}',
                'org.kde.kwin.Script.setConfig',
                'fullscreen',
                'true' if fullscreen else 'false',
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        subprocess.run(
            ['qdbus', 'org.kde.KWin', '/Scripting', 'org.kde.kwin.Scripting.start'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return True
    except Exception:
        return False


def _read_monitors():
    if not shutil.which('xrandr'):
        return {}
    try:
        proc = subprocess.run(['xrandr', '--query'], capture_output=True, text=True, check=False)
    except Exception:
        return {}
    monitors = {}
    for line in proc.stdout.splitlines():
        parts = line.split()
        if len(parts) < 3 or parts[1] != 'connected':
            continue
        geom = next((p for p in parts if '+' in p and 'x' in p), None)
        if not geom:
            continue
        try:
            size, xoff, yoff = geom.split('+')
            width, height = size.split('x')
            monitors[parts[0]] = {
                'x': int(xoff),
                'y': int(yoff),
                'w': int(width),
                'h': int(height),
                'primary': 'primary' in parts,
            }
        except Exception:
            continue
    return monitors


def _select_monitor(monitors, monitor_name):
    if not monitors:
        return None
    if monitor_name and monitor_name not in ('auto', AUTO_SECOND_MONITOR):
        return monitors.get(monitor_name)

    ordered = sorted(monitors.items(), key=lambda item: (item[1]['x'], item[1]['y'], item[0]))
    if len(ordered) == 1:
        return ordered[0][1]

    primary_names = [name for name, mon in ordered if mon.get('primary')]
    if primary_names:
        for name, mon in ordered:
            if name not in primary_names:
                return mon

    return ordered[1][1]


def _apply_window_rules(cfg, title):
    if not shutil.which('wmctrl'):
        return
    monitor_name = cfg.get('visuals_monitor') or AUTO_SECOND_MONITOR
    fullscreen = cfg.get('visuals_fullscreen', True)
    geometry = cfg.get('visuals_geometry')
    monitors = _read_monitors()
    target = _select_monitor(monitors, monitor_name)

    for _ in range(20):
        try:
            proc = subprocess.run(['wmctrl', '-l'], capture_output=True, text=True, check=False)
            found = any(title in line for line in proc.stdout.splitlines())
            if found:
                break
        except Exception:
            return
        time.sleep(0.15)
    else:
        return

    if target:
        try:
            subprocess.run(['wmctrl', '-r', title, '-b', 'remove,fullscreen'], check=False)
            mv = f'0,{target["x"]},{target["y"]},{target["w"]},{target["h"]}'
            subprocess.run(['wmctrl', '-r', title, '-e', mv], check=False)
        except Exception:
            pass
    elif isinstance(geometry, str) and geometry.count('x') == 1 and geometry.count('+') >= 2:
        try:
            size, xoff, yoff = geometry.split('+', 2)
            width, height = size.split('x', 1)
            mv = f'0,{int(xoff)},{int(yoff)},{int(width)},{int(height)}'
            subprocess.run(['wmctrl', '-r', title, '-e', mv], check=False)
        except Exception:
            pass

    if fullscreen:
        try:
            subprocess.run(['wmctrl', '-r', title, '-b', 'add,fullscreen'], check=False)
        except Exception:
            pass


def toggle_fullscreen(title=None):
    """Toggle fullscreen on the visuals window by title (X11/XWayland via wmctrl)."""
    cfg = _cfg()
    t = title or _title(cfg)
    if shutil.which('wmctrl'):
        subprocess.run(
            ['wmctrl', '-r', t, '-b', 'toggle,fullscreen'],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    return False


def spawn_window():
    cfg = _cfg()
    cmd = _spawn_cmd(cfg)
    if not cmd:
        print('No supported terminal launcher found. Run python3 visuals.py manually.', file=sys.stderr)
        return 1
    try:
        kwin_rule = _install_kwin_placement_rule(cfg, _title(cfg))
        subprocess.Popen(cmd, cwd=BASE)
    except Exception as exc:
        print(f'Failed to launch visuals window: {exc}', file=sys.stderr)
        return 1
    if not kwin_rule:
        _apply_window_rules(cfg, _title(cfg))
    return 0


def run_inline():
    os.execv(sys.executable, _inline_cmd())


def main(argv=None):
    argv = argv or sys.argv[1:]
    if os.environ.get(WINDOW_CHILD_ENV) == '1' or '--inline' in argv:
        run_inline()
        return 0
    return spawn_window()


if __name__ == '__main__':
    raise SystemExit(main())
