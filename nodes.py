"""
MOCT 7 | nodes.py — Visual Automation Graph
Edit this file. ii.py hot-reloads it automatically.

Available nodes: Const, LFO, BeatLFO, Seq, Ramp, Noise, BeatPulse,
                 Math, Clamp, Mix, Select, Hold, Scale, Gate,
                 Out, IntOut, BoolOut
"""
from node_lib import *

# ── BPM (set this first so beat-synced nodes use correct value) ──────────────

GRAPH = [

    Out('bpm',      Const(140)),
    BoolOut('bpm_sync', Const(1)),

    # ── Mode — sequences through modes every 8 beats ─────────────────────────
    IntOut('mode',    Seq([0, 7, 8, 3, 9, 14, 5, 16], beats=8)),

    # ── Palette — changes every 32 beats ──────────────────────────────────────
    IntOut('palette', Seq([0, 1, 2, 3, 4, 5], beats=32)),

    # ── Wave amplitude — slow breath ─────────────────────────────────────────
    Out('wave_amplitude',   LFO(freq=0.18, shape='sin',    min=0.15, max=0.45)),

    # ── Glitch — square pulse, fires occasionally ─────────────────────────────
    Out('glitch_intensity', LFO(freq=0.07, shape='square', min=0.05, max=0.80)),

    # ── Rain / particle density — triangle wave ───────────────────────────────
    Out('rain_density',     LFO(freq=0.11, shape='tri',    min=0.30, max=0.95)),

    # ── Speed — gentle oscillation ────────────────────────────────────────────
    Out('frame_delay',      LFO(freq=0.04, shape='sin',    min=0.03, max=0.07)),

    # ── Strobe speed — beats-synced ───────────────────────────────────────────
    Out('strobe_speed',     BeatLFO(beats=2, shape='saw',  min=1,    max=6)),

]

# ─────────────────────────────────────────────────────────────────────────────
# Examples (uncomment to use):
#
# Override a single mode manually:
#   IntOut('mode', Const(7)),          # lock to TUNNEL
#
# Random palette every 4 beats:
#   IntOut('palette', Seq([0,1,2,3,4,5], beats=4)),
#
# Glitch ramps up over 16 seconds then resets:
#   Out('glitch_intensity', Ramp(seconds=16, loop=True)),
#
# Blackout fires on every 8th beat for 2 frames:
#   BoolOut('blackout', BeatPulse(div=8, hold=2)),
#
# Mix two speeds based on slow LFO:
#   Out('frame_delay', Mix(Const(0.03), Const(0.08), LFO(freq=0.05))),
#
# Hold a random mode until the next beat pulse:
#   IntOut('mode', Hold(Noise(every=0, min=0, max=16), BeatPulse(div=4))),
# ─────────────────────────────────────────────────────────────────────────────
