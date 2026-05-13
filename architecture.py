#!/usr/bin/env python3
"""Shared runtime architecture helpers for ii engine and controller."""

import importlib
import inspect
import json
import os
import pkgutil
import tempfile

from modes.base import Mode

BASE = os.path.dirname(__file__)
CONFIG_PATH = os.path.join(BASE, 'config.json')
CTRL_PATH = os.path.join(BASE, 'control.json')
STATUS_PATH = os.path.join(BASE, 'status.json')
NODES_PATH = os.path.join(BASE, 'nodes.py')
MODES_DIR = os.path.join(BASE, 'modes')
MAPPINGS_DIR = os.path.join(BASE, 'mappings')
VISUALS_PATH = os.path.join(BASE, 'visuals.py')
WINDOW_PATH = os.path.join(BASE, 'window.py')

DEFAULTS = {
    'mode': 0,
    'mode_b': 1,
    'layer_b_enabled': False,
    'mode_lock': False,
    'auto_cycle': False,
    'blackout': False,
    'flash_active': False,
    'bpm_sync': True,
    'palette': 0,
    'primary_color': -1,
    'secondary_color': -1,
    'accent_color': -1,
    'flash_text': 'MOCT',
    'frame_delay': 0.05,
    'strobe_speed': 2,
    'glitch_intensity': 0.4,
    'wave_amplitude': 0.35,
    'rain_density': 0.7,
    'mode_cycle_frames': 250,
    'bpm': 140,
    'audio_level': 0.0,
    'audio_peak': 0.0,
    'camera4_motion': 0.0,
    'camera4_brightness': 0.0,
    'camera4_online': False,
    'camera2_motion': 0.0,
    'camera2_brightness': 0.0,
    'camera2_online': False,
    'sym_set': 0,
    'layer_b_alpha': 1.0,
    'master_dim': 1.0,
    'mapping': 0,
    'map_mode': False,
    'map_selected': -1,
    'map_cursor_x': None,
    'map_cursor_y': None,
}


def load_json(path, default=None):
    if default is None:
        default = {}
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default


def save_json_atomic(path, data):
    """Write JSON atomically with a unique temp file in the target directory."""
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(prefix=os.path.basename(path) + '.', suffix='.tmp', dir=os.path.dirname(path))
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        # Fallback to direct write in case of transient filesystem rename issues.
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f)
    finally:
        if tmp:
            try:
                os.unlink(tmp)
            except FileNotFoundError:
                pass


def discover_modes():
    modes = []
    for module_info in pkgutil.iter_modules([MODES_DIR]):
        if module_info.name in ('base', '__init__'):
            continue
        mod = importlib.import_module(f'modes.{module_info.name}')
        for _, cls in inspect.getmembers(mod, inspect.isclass):
            if issubclass(cls, Mode) and cls is not Mode and cls.__module__ == mod.__name__:
                modes.append(cls())
    modes.sort(key=lambda m: (getattr(m, 'ORDER', 99), getattr(m, 'NAME', m.__class__.__name__)))
    return modes


def discover_mode_names():
    return [m.NAME for m in discover_modes()]
