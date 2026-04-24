#!/usr/bin/env python3
"""MOCT 7 | node_lib — signal generators and processors for nodes.py"""

import math, random

TAU = math.tau


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
