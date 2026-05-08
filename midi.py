#!/usr/bin/env python3
"""_ii | midi.py — MIDI CC to control parameter router."""

import threading

try:
    import mido as _mido
except ImportError:
    _mido = None

# CC number → (param, range_lo, range_hi)
DEFAULT_MAP = {
    1:  ('master_dim',       0.0,  1.0),
    7:  ('layer_b_alpha',    0.0,  1.0),
    11: ('audio_level',      0.0,  1.0),
    14: ('frame_delay',      0.01, 0.20),
    16: ('glitch_intensity', 0.0,  1.0),
    17: ('wave_amplitude',   0.1,  0.5),
    18: ('rain_density',     0.1,  1.0),
    20: ('bpm',              40,   240),
    21: ('palette',          0,    5),
}


class MidiRouter:
    """Background thread that reads MIDI CC messages and maps them to control params.

    Values are written to `self.values` dict. Merge into overrides in the controller.
    Requires: pip install mido python-rtmidi
    """

    def __init__(self, port_name=None, cc_map=None):
        self.port_name = port_name
        self.cc_map = dict(DEFAULT_MAP)
        if cc_map:
            self.cc_map.update(cc_map)
        self.values = {}
        self.error = None
        self.port_label = ''
        self._started = False

    def start(self):
        if self._started:
            return self
        self._started = True
        if _mido is None:
            self.error = 'install mido + python-rtmidi'
            return self
        t = threading.Thread(target=self._run, name='ii-midi', daemon=True)
        t.start()
        return self

    def _run(self):
        try:
            ports = _mido.get_input_names()
            if not ports:
                self.error = 'no MIDI inputs found'
                return
            name = self.port_name if (self.port_name and self.port_name in ports) else ports[0]
            self.port_label = name
            with _mido.open_input(name) as port:
                for msg in port:
                    if msg.type == 'control_change':
                        self._handle_cc(msg.control, msg.value)
        except Exception as exc:
            self.error = str(exc)[:60]

    def _handle_cc(self, cc, raw):
        entry = self.cc_map.get(cc)
        if entry is None:
            return
        param, lo, hi = entry
        v = lo + (raw / 127.0) * (hi - lo)
        if isinstance(lo, int) and isinstance(hi, int):
            v = int(round(v))
        self.values[param] = v


_instance = None
_lock = threading.Lock()


def get_router(port_name=None):
    """Return the singleton MidiRouter (started on first call)."""
    global _instance
    with _lock:
        if _instance is None:
            _instance = MidiRouter(port_name=port_name)
            _instance.start()
        return _instance
