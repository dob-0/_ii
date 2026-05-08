#!/usr/bin/env python3
"""_ii | cues.py — Named cue list with load/save/advance."""

import json
import os

from architecture import BASE

CUES_PATH = os.path.join(BASE, 'cues.json')

BUILTIN = [
    {'name': 'RAIN',    'mode': 0,  'palette': 2, 'rain_density': 0.9,  'frame_delay': 0.04},
    {'name': 'STROBE',  'mode': 3,  'palette': 3, 'strobe_speed': 2,    'bpm_sync': True},
    {'name': 'TUNNEL',  'mode': 7,  'palette': 0, 'frame_delay': 0.03},
    {'name': 'PLASMA',  'mode': 8,  'palette': 5, 'wave_amplitude': 0.45},
    {'name': 'VORTEX',  'mode': 9,  'palette': 3, 'frame_delay': 0.035},
    {'name': 'GLITCH',  'mode': 2,  'palette': 4, 'glitch_intensity': 1.0},
    {'name': 'LIQUID',  'mode': 17, 'palette': 5, 'layer_b_enabled': True, 'mode_b': 8, 'layer_b_alpha': 0.6},
    {'name': 'POSTER',  'mode': 18, 'palette': 0},
]


class CueList:
    """Named preset list. Each cue is a dict of control overrides plus a 'name' key."""

    def __init__(self):
        self.cues = []
        self.idx = 0
        self.load()

    def load(self):
        try:
            with open(CUES_PATH) as f:
                data = json.load(f)
            if isinstance(data, list) and data:
                self.cues = data
                return
        except Exception:
            pass
        self.cues = list(BUILTIN)

    def save(self):
        try:
            with open(CUES_PATH, 'w') as f:
                json.dump(self.cues, f, indent=2)
        except Exception:
            pass

    def current_params(self):
        """Return cue overrides (name key stripped)."""
        if not self.cues:
            return {}
        c = dict(self.cues[self.idx % len(self.cues)])
        c.pop('name', None)
        return c

    def name(self):
        if not self.cues:
            return ''
        return self.cues[self.idx % len(self.cues)].get('name', f'CUE{self.idx + 1}')

    def advance(self):
        if self.cues:
            self.idx = (self.idx + 1) % len(self.cues)

    def prev(self):
        if self.cues:
            self.idx = (self.idx - 1) % len(self.cues)

    def go(self, n):
        if self.cues:
            self.idx = int(n) % len(self.cues)

    def store(self, name, overrides):
        """Store overrides as a named cue. Replaces existing cue with same name."""
        cue = {'name': name}
        cue.update({k: v for k, v in overrides.items() if not k.startswith('_')})
        for i, c in enumerate(self.cues):
            if c.get('name') == name:
                self.cues[i] = cue
                self.save()
                return
        self.cues.append(cue)
        self.idx = len(self.cues) - 1
        self.save()
