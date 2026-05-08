#!/usr/bin/env python3
"""_ii | node_lib — signal generators, processors, and output nodes."""

import math, random, socket, threading, time

try:
    import numpy as _np
except Exception:
    _np = None

try:
    import sounddevice as _sd
except Exception:
    _sd = None

try:
    import cv2 as _cv2
except Exception:
    _cv2 = None

TAU = math.tau


def _clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


class _AudioInputHub:
    """Shared microphone input reader.

    Optional backend: sounddevice + numpy.
    Exposes normalized level and pulse-friendly peak values.
    """
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self.level = 0.0
        self.peak = 0.0
        self.error = None
        self.ready = False
        self._stream = None
        self._started = False

    @classmethod
    def get(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def start(self, device=None, samplerate=22050, channels=1, gain=6.0, smoothing=0.82):
        if self._started:
            return self
        self._started = True
        if _sd is None or _np is None:
            self.error = 'install numpy and sounddevice for audio nodes'
            return self

        gain = max(0.01, float(gain))
        smoothing = _clamp(float(smoothing), 0.0, 0.999)

        def callback(indata, frames, callback_time, status):
            if status:
                self.error = str(status)
            try:
                mono = _np.asarray(indata)
                if mono.size == 0:
                    return
                rms = float(_np.sqrt(_np.mean(_np.square(mono))))
                val = _clamp(rms * gain)
                self.level = self.level * smoothing + val * (1.0 - smoothing)
                self.peak = max(val, self.peak * 0.92)
                self.ready = True
            except Exception as exc:
                self.error = str(exc)

        try:
            self._stream = _sd.InputStream(
                device=device,
                channels=channels,
                samplerate=samplerate,
                callback=callback,
                blocksize=0,
            )
            self._stream.start()
        except Exception as exc:
            self.error = str(exc)
        return self


def _source_key(source):
    return str(source)


def _video_capture_source(source):
    if isinstance(source, str):
        stripped = source.strip()
        if stripped.isdigit():
            return int(stripped)
        return stripped
    return source


class _CameraInputHub:
    """Shared camera reader for simple motion/brightness metrics."""
    _instances = {}
    _lock = threading.Lock()

    def __init__(self, source=0):
        self.source = source
        self.motion = 0.0
        self.brightness = 0.0
        self.presence = 0.0
        self.error = None
        self.ready = False
        self._started = False
        self._thread = None

    @classmethod
    def get(cls, source=0):
        key = _source_key(source)
        with cls._lock:
            if key not in cls._instances:
                cls._instances[key] = cls(source)
            return cls._instances[key]

    def start(self, fps=12.0, width=160, height=90, motion_gain=5.0, smoothing=0.75):
        if self._started:
            return self
        self._started = True
        if _cv2 is None or _np is None:
            self.error = 'install numpy and opencv-python for camera nodes'
            return self

        fps = max(1.0, float(fps))
        motion_gain = max(0.1, float(motion_gain))
        smoothing = _clamp(float(smoothing), 0.0, 0.999)

        def worker():
            cap = None
            prev = None
            delay = 1.0 / fps
            try:
                cap = _cv2.VideoCapture(_video_capture_source(self.source))
                cap.set(_cv2.CAP_PROP_FRAME_WIDTH, width)
                cap.set(_cv2.CAP_PROP_FRAME_HEIGHT, height)
                while True:
                    ok, frame = cap.read()
                    if not ok or frame is None:
                        self.error = 'camera read failed'
                        self.presence = 0.0
                        time.sleep(delay)
                        continue
                    gray = _cv2.cvtColor(frame, _cv2.COLOR_BGR2GRAY)
                    small = _cv2.resize(gray, (64, 36))
                    bright = float(_np.mean(small) / 255.0)
                    if prev is None:
                        mot = 0.0
                    else:
                        diff = _cv2.absdiff(small, prev)
                        mot = _clamp(float(_np.mean(diff) / 255.0) * motion_gain)
                    prev = small
                    self.brightness = self.brightness * smoothing + bright * (1.0 - smoothing)
                    self.motion = self.motion * smoothing + mot * (1.0 - smoothing)
                    self.presence = 1.0
                    self.ready = True
                    time.sleep(delay)
            except Exception as exc:
                self.error = str(exc)
                self.presence = 0.0
            finally:
                if cap is not None:
                    cap.release()

        self._thread = threading.Thread(target=worker, name='mct7-camera', daemon=True)
        self._thread.start()
        return self


class _ArtNetSender:
    """Minimal Art-Net DMX sender.

    One sender owns one 512-channel universe buffer and sends ArtDMX packets over UDP.
    """
    _instances = {}
    _lock = threading.Lock()

    def __init__(self, host='127.0.0.1', port=6454, universe=0, length=512):
        self.host = host
        self.port = int(port)
        self.universe = int(universe)
        self.length = max(2, min(512, int(length)))
        self.buf = bytearray(self.length)
        self.error = None
        self.enabled = bool(host)
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    @classmethod
    def get(cls, host='127.0.0.1', port=6454, universe=0, length=512):
        key = (host, int(port), int(universe), int(length))
        with cls._lock:
            if key not in cls._instances:
                cls._instances[key] = cls(host, port, universe, length)
            return cls._instances[key]

    def set_channel(self, channel, value):
        idx = int(channel) - 1
        if not (0 <= idx < self.length):
            return
        self.buf[idx] = max(0, min(255, int(round(value))))

    def send(self):
        if not self.enabled:
            return
        packet = bytearray()
        packet.extend(b'Art-Net\x00')
        packet.extend((0x00, 0x50))  # OpDmx, little endian
        packet.extend((0x00, 0x0e))  # protocol version 14
        packet.extend((0x00, 0x00))  # sequence, physical
        packet.extend((self.universe & 0xff, (self.universe >> 8) & 0xff))
        packet.extend(((self.length >> 8) & 0xff, self.length & 0xff))
        packet.extend(self.buf)
        try:
            self._sock.sendto(packet, (self.host, self.port))
            self.error = None
        except Exception as exc:
            self.error = str(exc)


class Node:
    def evaluate(self, t, bpm, frame, state): return 0.0


# ── Sources ───────────────────────────────────────────────────────────────────

class Const(Node):
    """Fixed value."""
    def __init__(self, value):
        self.value = value
    def evaluate(self, t, bpm, frame, state):
        return self.value


class LFO(Node):
    """Low frequency oscillator.
    shapes: 'sin' 'tri' 'saw' 'rsaw' 'square'
    freq in Hz, output clamped to [min, max].
    """
    def __init__(self, freq=1.0, shape='sin', min=0.0, max=1.0, phase=0.0):
        self.freq = freq; self.shape = shape
        self.min = min;   self.max = max;  self.phase = phase

    def evaluate(self, t, bpm, frame, state):
        p = t * self.freq * TAU + self.phase
        if   self.shape == 'sin':    v = (math.sin(p) + 1) / 2
        elif self.shape == 'tri':    v = abs((p / TAU % 1) * 2 - 1)
        elif self.shape == 'saw':    v = p / TAU % 1
        elif self.shape == 'rsaw':   v = 1 - (p / TAU % 1)
        elif self.shape == 'square': v = 1.0 if math.sin(p) > 0 else 0.0
        else:                        v = 0.5
        return self.min + v * (self.max - self.min)


class BeatLFO(Node):
    """LFO synced to BPM — freq is in beats, not Hz."""
    def __init__(self, beats=1.0, shape='sin', min=0.0, max=1.0, phase=0.0):
        self.beats = beats; self.shape = shape
        self.min = min;     self.max = max;  self.phase = phase

    def evaluate(self, t, bpm, frame, state):
        freq = bpm / 60.0 / self.beats
        p    = t * freq * TAU + self.phase
        if   self.shape == 'sin':    v = (math.sin(p) + 1) / 2
        elif self.shape == 'tri':    v = abs((p / TAU % 1) * 2 - 1)
        elif self.shape == 'saw':    v = p / TAU % 1
        elif self.shape == 'rsaw':   v = 1 - (p / TAU % 1)
        elif self.shape == 'square': v = 1.0 if math.sin(p) > 0 else 0.0
        else:                        v = 0.5
        return self.min + v * (self.max - self.min)


class Seq(Node):
    """Steps through a list of values, one step every N beats."""
    def __init__(self, values, beats=4):
        self.values = list(values); self.beats = beats

    def evaluate(self, t, bpm, frame, state):
        beat = int(t * bpm / 60)
        idx  = (beat // max(1, int(self.beats))) % len(self.values)
        return self.values[idx]


class Ramp(Node):
    """Ramps 0→1 over `seconds` seconds, loops if loop=True."""
    def __init__(self, seconds=4.0, loop=True):
        self.seconds = seconds; self.loop = loop

    def evaluate(self, t, bpm, frame, state):
        if self.loop:
            return (t % self.seconds) / self.seconds
        return min(1.0, t / self.seconds)


class Noise(Node):
    """Random value that holds for `every` seconds, then jumps."""
    def __init__(self, every=1.0, min=0.0, max=1.0):
        self.every = every; self.min = min; self.max = max
        self._val  = min;   self._next = 0.0

    def evaluate(self, t, bpm, frame, state):
        if t >= self._next:
            self._val  = random.uniform(self.min, self.max)
            self._next = t + self.every
        return self._val


class BeatPulse(Node):
    """Fires 1.0 on every N beats, stays high for `hold` frames."""
    def __init__(self, div=1, hold=2):
        self.div = div; self.hold = hold
        self._last = -1; self._on = 0

    def evaluate(self, t, bpm, frame, state):
        beat = int(t * bpm / 60) // max(1, self.div)
        if beat != self._last:
            self._last = beat; self._on = self.hold
        if self._on > 0:
            self._on -= 1; return 1.0
        return 0.0


class AudioLevel(Node):
    """Normalized microphone RMS level in [0, 1].

    Optional dependency: numpy + sounddevice.
    Returns 0 when backend is unavailable.
    """
    def __init__(self, device=None, gain=6.0, smoothing=0.82):
        self.device = device
        self.gain = gain
        self.smoothing = smoothing
        self.hub = _AudioInputHub.get().start(device=device, gain=gain, smoothing=smoothing)

    def evaluate(self, t, bpm, frame, state):
        return self.hub.level


class AudioPeak(Node):
    """Fast-decaying microphone peak level in [0, 1]."""
    def __init__(self, device=None, gain=8.0, smoothing=0.7):
        self.device = device
        self.gain = gain
        self.smoothing = smoothing
        self.hub = _AudioInputHub.get().start(device=device, gain=gain, smoothing=smoothing)

    def evaluate(self, t, bpm, frame, state):
        return self.hub.peak


class AudioTrigger(Node):
    """One-shot trigger when microphone level crosses threshold."""
    def __init__(self, threshold=0.45, cooldown=6, device=None, gain=8.0):
        self.threshold = threshold
        self.cooldown = max(1, int(cooldown))
        self._cool = 0
        self.hub = _AudioInputHub.get().start(device=device, gain=gain)

    def evaluate(self, t, bpm, frame, state):
        if self._cool > 0:
            self._cool -= 1
        if self._cool <= 0 and self.hub.peak >= self.threshold:
            self._cool = self.cooldown
            return 1.0
        return 0.0


class AutoBPM(Node):
    """Onset-detection BPM from microphone.

    Detects rising edges in audio peak level and computes average interval.
    Output: estimated BPM rounded to nearest integer, clamped to [min_bpm, max_bpm].
    Falls back to `fallback` BPM when audio is unavailable or too few onsets.
    """
    def __init__(self, device=None, gain=8.0, onset_threshold=0.35,
                 min_bpm=60, max_bpm=200, smoothing=0.75, fallback=120):
        self.hub = _AudioInputHub.get().start(device=device, gain=gain)
        self.threshold = float(onset_threshold)
        self.min_bpm = int(min_bpm)
        self.max_bpm = int(max_bpm)
        self.smoothing = _clamp(float(smoothing), 0.0, 0.999)
        self.fallback = float(fallback)
        self._bpm = float(fallback)
        self._prev_peak = 0.0
        self._onset_times = []

    def evaluate(self, t, bpm, frame, state):
        peak = self.hub.peak
        if peak > self.threshold and self._prev_peak <= self.threshold:
            self._onset_times.append(t)
            self._onset_times = [x for x in self._onset_times if t - x < 8.0][-16:]
            if len(self._onset_times) >= 2:
                intervals = [b - a for a, b in zip(self._onset_times, self._onset_times[1:])]
                avg = sum(intervals) / len(intervals)
                if avg > 0:
                    raw = _clamp(60.0 / avg, self.min_bpm, self.max_bpm)
                    self._bpm = self._bpm * self.smoothing + raw * (1.0 - self.smoothing)
        self._prev_peak = peak
        return round(self._bpm)


class CameraMotion(Node):
    """Normalized camera motion amount in [0, 1].

    Optional dependency: numpy + opencv-python.
    Returns 0 when backend is unavailable.
    """
    def __init__(self, index=0, source=None, fps=12.0, gain=5.0, smoothing=0.75):
        self.source = index if source is None else source
        self.hub = _CameraInputHub.get(self.source).start(fps=fps, motion_gain=gain, smoothing=smoothing)

    def evaluate(self, t, bpm, frame, state):
        return self.hub.motion


class CameraBrightness(Node):
    """Normalized average camera brightness in [0, 1]."""
    def __init__(self, index=0, source=None, fps=12.0, smoothing=0.75):
        self.source = index if source is None else source
        self.hub = _CameraInputHub.get(self.source).start(fps=fps, smoothing=smoothing)

    def evaluate(self, t, bpm, frame, state):
        return self.hub.brightness


class CameraPresence(Node):
    """Returns 1 when camera frames are flowing, else 0."""
    def __init__(self, index=0, source=None, fps=12.0):
        self.source = index if source is None else source
        self.hub = _CameraInputHub.get(self.source).start(fps=fps)

    def evaluate(self, t, bpm, frame, state):
        return self.hub.presence


# ── Processors ────────────────────────────────────────────────────────────────

class Math(Node):
    """Arithmetic on a node: +  -  *  /  %  **"""
    def __init__(self, node, op, value):
        self.node = node; self.op = op; self.value = value

    def evaluate(self, t, bpm, frame, state):
        v = self.node.evaluate(t, bpm, frame, state)
        if   self.op == '+':  return v + self.value
        elif self.op == '-':  return v - self.value
        elif self.op == '*':  return v * self.value
        elif self.op == '/':  return v / self.value if self.value else 0
        elif self.op == '%':  return v % self.value if self.value else 0
        elif self.op == '**': return v ** self.value
        return v


class Clamp(Node):
    """Clamp node output to [min, max]."""
    def __init__(self, node, min=0.0, max=1.0):
        self.node = node; self.min = min; self.max = max

    def evaluate(self, t, bpm, frame, state):
        return max(self.min, min(self.max, self.node.evaluate(t, bpm, frame, state)))


class Mix(Node):
    """Linear blend: alpha 0→node_a, alpha 1→node_b. alpha can be a Node or float."""
    def __init__(self, node_a, node_b, alpha=0.5):
        self.a = node_a; self.b = node_b; self.alpha = alpha

    def evaluate(self, t, bpm, frame, state):
        va = self.a.evaluate(t, bpm, frame, state)
        vb = self.b.evaluate(t, bpm, frame, state)
        al = (self.alpha.evaluate(t, bpm, frame, state)
              if isinstance(self.alpha, Node) else self.alpha)
        return va * (1 - al) + vb * al


class Select(Node):
    """Picks one of several nodes based on integer index (Node or int)."""
    def __init__(self, nodes, index):
        self.nodes = list(nodes); self.index = index

    def evaluate(self, t, bpm, frame, state):
        idx = (self.index.evaluate(t, bpm, frame, state)
               if isinstance(self.index, Node) else self.index)
        idx = int(idx) % len(self.nodes)
        return self.nodes[idx].evaluate(t, bpm, frame, state)


class Hold(Node):
    """Sample-and-hold: captures node value when trigger fires (> 0.5)."""
    def __init__(self, node, trigger):
        self.node = node; self.trigger = trigger; self._held = 0.0

    def evaluate(self, t, bpm, frame, state):
        if self.trigger.evaluate(t, bpm, frame, state) > 0.5:
            self._held = self.node.evaluate(t, bpm, frame, state)
        return self._held


class Scale(Node):
    """Remap node output from [in_min, in_max] to [out_min, out_max]."""
    def __init__(self, node, in_min=0.0, in_max=1.0, out_min=0.0, out_max=1.0):
        self.node = node
        self.in_min = in_min; self.in_max = in_max
        self.out_min = out_min; self.out_max = out_max

    def evaluate(self, t, bpm, frame, state):
        v    = self.node.evaluate(t, bpm, frame, state)
        span = self.in_max - self.in_min or 1
        n    = (v - self.in_min) / span
        return self.out_min + n * (self.out_max - self.out_min)


class Gate(Node):
    """Passes node value only when gate node > threshold, else returns 0."""
    def __init__(self, node, gate, threshold=0.5):
        self.node = node; self.gate = gate; self.threshold = threshold

    def evaluate(self, t, bpm, frame, state):
        if self.gate.evaluate(t, bpm, frame, state) > self.threshold:
            return self.node.evaluate(t, bpm, frame, state)
        return 0.0


# ── Outputs ───────────────────────────────────────────────────────────────────

class Out(Node):
    """Write float value to control state."""
    def __init__(self, param, node):
        self.param = param; self.node = node

    def evaluate(self, t, bpm, frame, state):
        v = self.node.evaluate(t, bpm, frame, state)
        state[self.param] = v
        return v


class IntOut(Node):
    """Write int value to control state (for mode, palette, etc.)."""
    def __init__(self, param, node):
        self.param = param; self.node = node

    def evaluate(self, t, bpm, frame, state):
        v = int(self.node.evaluate(t, bpm, frame, state))
        state[self.param] = v
        return v


class BoolOut(Node):
    """Write bool (0/1) to control state."""
    def __init__(self, param, node, threshold=0.5):
        self.param = param; self.node = node; self.threshold = threshold

    def evaluate(self, t, bpm, frame, state):
        v = self.node.evaluate(t, bpm, frame, state) > self.threshold
        state[self.param] = v
        return float(v)


class ArtNetOut(Node):
    """Send a node value to one DMX channel over Art-Net.

    channel is 1-based. The node value is remapped from [in_min, in_max] to
    [out_min, out_max], then sent at most `fps` times per second.
    """
    def __init__(self, channel, node, host='127.0.0.1', universe=0, port=6454,
                 in_min=0.0, in_max=1.0, out_min=0, out_max=255, fps=30,
                 param=None, enabled=True):
        self.channel = int(channel)
        self.node = node
        self.in_min = in_min
        self.in_max = in_max
        self.out_min = out_min
        self.out_max = out_max
        self.fps = max(1.0, float(fps))
        self.param = param or f'artnet_ch_{self.channel}'
        self.enabled = enabled
        self.sender = _ArtNetSender.get(host=host, port=port, universe=universe)
        self._next_send = 0.0

    def evaluate(self, t, bpm, frame, state):
        raw = self.node.evaluate(t, bpm, frame, state)
        span = self.in_max - self.in_min or 1
        n = _clamp((raw - self.in_min) / span)
        value = self.out_min + n * (self.out_max - self.out_min)
        dmx = max(0, min(255, int(round(value))))
        state[self.param] = dmx
        if self.enabled and t >= self._next_send:
            self.sender.set_channel(self.channel, dmx)
            self.sender.send()
            self._next_send = t + 1.0 / self.fps
        return dmx


class ArtNetRGB(Node):
    """Send three node values to consecutive RGB DMX channels."""
    def __init__(self, start_channel, red, green, blue, host='127.0.0.1',
                 universe=0, port=6454, fps=30, param='artnet_rgb', enabled=True):
        self.param = param
        self.red = ArtNetOut(start_channel, red, host, universe, port, fps=fps, enabled=enabled)
        self.green = ArtNetOut(start_channel + 1, green, host, universe, port, fps=fps, enabled=enabled)
        self.blue = ArtNetOut(start_channel + 2, blue, host, universe, port, fps=fps, enabled=enabled)

    def evaluate(self, t, bpm, frame, state):
        r = self.red.evaluate(t, bpm, frame, state)
        g = self.green.evaluate(t, bpm, frame, state)
        b = self.blue.evaluate(t, bpm, frame, state)
        state[self.param] = f'{r},{g},{b}'
        return max(r, g, b) / 255.0
