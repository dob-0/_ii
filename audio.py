#!/usr/bin/env python3
"""_ii | audio.py — Audio reactive input.

Captures audio from the system microphone/line-in, computes RMS level,
peak hold, and BPM via beat detection, then merges results into
control.json every ~100ms so visual modes can react.

Usage:
    python3 audio.py                    # default input device
    python3 audio.py --device 2         # specify device index
    python3 audio.py --list             # list available devices
    python3 audio.py --sensitivity 2.0  # gain multiplier (default 1.0)
    python3 audio.py --device 2 --sensitivity 1.5
"""

import argparse
import json
import math
import os
import signal
import sys
import tempfile
import threading
import time

try:
    import sounddevice as sd
    import numpy as np
except ImportError:
    missing = []
    try:
        import sounddevice as sd  # noqa: F401
    except ImportError:
        missing.append("sounddevice")
    try:
        import numpy as np  # noqa: F401
    except ImportError:
        missing.append("numpy")
    print("ERROR: missing dependencies: " + ", ".join(missing))
    print("  pip install sounddevice numpy")
    sys.exit(1)

# ── Paths ──────────────────────────────────────────────────────────────────────

BASE = os.path.dirname(os.path.abspath(__file__))
CTRL_PATH = os.path.join(BASE, 'control.json')

# ── Audio parameters ───────────────────────────────────────────────────────────

SAMPLE_RATE   = 44100
BLOCK_SIZE    = 1024          # samples per callback (~23ms at 44100)
CHANNELS      = 1
WRITE_EVERY   = 10            # write control.json every N callbacks (~100ms)
PRINT_EVERY   = 43            # print VU meter approx every 1 second

# Normalisation: map RMS values to 0–1.
# -20 dBFS is typical speech; -6 dBFS is loud music.
# RMS of full-scale sine = 0.707 → we target that as "near 1".
# Typical quiet input ~0.01 RMS → we leave headroom so 0.5 RMS = 1.0 after scale.
RMS_SCALE     = 2.0           # multiplied by sensitivity arg

# Peak hold
PEAK_DECAY    = 0.95          # multiply per callback (~0.05 drop per ~23ms)

# Beat detection
BEAT_THRESHOLD_MULT = 1.3     # threshold = running mean of peaks × this
BEAT_HISTORY        = 8       # keep last N beat timestamps
BEAT_WINDOW_SEC     = 5.0     # only count beats within this window for BPM
BEAT_MIN_INTERVAL   = 0.25    # seconds between beats (max 240 BPM)
BEAT_CONFIDENCE_MIN = 4       # minimum beats in window to report BPM
BEAT_CONSISTENCY    = 0.20    # inter-beat interval variance tolerance (±20%)

# Running mean for adaptive threshold (exponential moving average)
MEAN_ALPHA    = 0.05          # smoothing factor for peak mean

# ── JSON helpers ───────────────────────────────────────────────────────────────

def read_ctrl():
    try:
        with open(CTRL_PATH, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def save_ctrl_atomic(data):
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(
            prefix=os.path.basename(CTRL_PATH) + '.',
            suffix='.tmp',
            dir=os.path.dirname(CTRL_PATH),
        )
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, CTRL_PATH)
    except Exception as exc:
        try:
            with open(CTRL_PATH, 'w', encoding='utf-8') as f:
                json.dump(data, f)
        except Exception as exc2:
            print(f"[audio] WARNING: write failed: {exc2}")
    finally:
        if tmp:
            try:
                os.unlink(tmp)
            except FileNotFoundError:
                pass

# ── VU meter rendering ─────────────────────────────────────────────────────────

def vu_bar(level, width=8):
    """Render a UTF-8 block VU bar of given width for level in [0,1]."""
    filled = int(round(level * width))
    filled = max(0, min(filled, width))
    bar = "█" * filled + "░" * (width - filled)
    return bar

# ── Beat detection ─────────────────────────────────────────────────────────────

def compute_bpm(beat_times, now):
    """Compute BPM from a list of recent beat timestamps.

    Returns (bpm, confident) where confident is True if we have enough
    consistent data to report a reliable BPM.
    """
    # Filter to beats within the window
    recent = [t for t in beat_times if now - t <= BEAT_WINDOW_SEC]
    if len(recent) < BEAT_CONFIDENCE_MIN:
        return None, False

    # Compute inter-beat intervals
    intervals = [recent[i+1] - recent[i] for i in range(len(recent)-1)]
    if not intervals:
        return None, False

    mean_interval = sum(intervals) / len(intervals)
    if mean_interval <= 0:
        return None, False

    # Check consistency: all intervals within ±BEAT_CONSISTENCY of mean
    threshold = mean_interval * BEAT_CONSISTENCY
    consistent = all(abs(iv - mean_interval) <= threshold for iv in intervals)
    if not consistent:
        return None, False

    bpm = 60.0 / mean_interval
    # Clamp to sane range
    bpm = max(40.0, min(240.0, bpm))
    return bpm, True

# ── Audio processor (shared state, updated in callback) ───────────────────────

class AudioProcessor:
    def __init__(self, sensitivity):
        self.sensitivity    = sensitivity
        self.lock           = threading.Lock()

        # Output values (read by main thread)
        self.audio_level    = 0.0
        self.audio_peak     = 0.0
        self.bpm            = None          # None = not confident yet

        # Internal state (callback thread only — no lock needed for these)
        self._peak          = 0.0
        self._peak_mean     = 0.05          # adaptive threshold seed
        self._beat_times    = []            # timestamps of recent beats
        self._last_beat_t   = 0.0
        self._callback_count = 0
        self._in_beat       = False         # debounce: don't double-count

    def callback(self, indata, frames, time_info, status):
        """sounddevice InputStream callback — runs in a dedicated audio thread."""
        if status:
            pass  # ignore overflow/underflow messages during normal operation

        samples = indata[:, 0].astype(np.float32)

        # 1. RMS level
        rms = math.sqrt(float(np.mean(samples ** 2)) + 1e-12)

        # 2. Normalize: scale by RMS_SCALE × sensitivity, clamp to [0, 1]
        level = min(1.0, rms * RMS_SCALE * self.sensitivity)

        # 3. Peak hold: fast attack (takes max with current rms), slow decay
        self._peak = max(self._peak * PEAK_DECAY, level)

        # 4. Adaptive threshold for beat detection (exponential moving average)
        self._peak_mean = (1.0 - MEAN_ALPHA) * self._peak_mean + MEAN_ALPHA * self._peak

        # 5. Beat detection
        now = time.monotonic()
        threshold = self._peak_mean * BEAT_THRESHOLD_MULT
        since_last = now - self._last_beat_t

        if level >= threshold and since_last >= BEAT_MIN_INTERVAL:
            if not self._in_beat:
                # Rising edge — new beat
                self._last_beat_t = now
                self._beat_times.append(now)
                # Keep only last BEAT_HISTORY entries
                if len(self._beat_times) > BEAT_HISTORY:
                    self._beat_times = self._beat_times[-BEAT_HISTORY:]
                self._in_beat = True
        else:
            self._in_beat = False

        # 6. Compute BPM
        bpm, confident = compute_bpm(self._beat_times, now)

        # 7. Write to shared output (lock protects cross-thread read)
        with self.lock:
            self.audio_level = level
            self.audio_peak  = self._peak
            if confident and bpm is not None:
                self.bpm = bpm

        self._callback_count += 1

    def snapshot(self):
        """Return (audio_level, audio_peak, bpm_or_None) thread-safely."""
        with self.lock:
            return self.audio_level, self.audio_peak, self.bpm

# ── Main loop ──────────────────────────────────────────────────────────────────

_stream_ref = None

def _handle_signal(signum, frame):
    sig_name = signal.Signals(signum).name
    print(f"\n[audio] Received {sig_name}, stopping stream…")
    if _stream_ref is not None:
        _stream_ref.stop()
        _stream_ref.close()
    sys.exit(0)


def list_devices():
    print("\nAvailable audio input devices:\n")
    devices = sd.query_devices()
    for idx, dev in enumerate(devices):
        if dev['max_input_channels'] > 0:
            marker = " ← default" if idx == sd.default.device[0] else ""
            print(f"  [{idx:2d}]  {dev['name']}{marker}")
    print()


def main():
    global _stream_ref

    parser = argparse.ArgumentParser(description="_ii audio reactive input")
    parser.add_argument("--device", type=int, default=None,
                        help="Input device index (see --list)")
    parser.add_argument("--list", action="store_true",
                        help="List available input devices and exit")
    parser.add_argument("--sensitivity", type=float, default=1.0,
                        help="Gain multiplier for level/peak (default: 1.0)")
    args = parser.parse_args()

    if args.list:
        list_devices()
        sys.exit(0)

    # Show device info
    try:
        if args.device is not None:
            dev_info = sd.query_devices(args.device)
        else:
            dev_info = sd.query_devices(sd.default.device[0])
        dev_name = dev_info['name']
        dev_idx  = args.device if args.device is not None else sd.default.device[0]
    except Exception as exc:
        print(f"[audio] ERROR querying device: {exc}")
        print("[audio] Use --list to see available devices.")
        sys.exit(1)

    print()
    print("┌─────────────────────────────────────────────────┐")
    print("│  ii — audio reactive input                      │")
    print(f"│  Device [{dev_idx:2d}]  {dev_name[:38]:<38}│")
    print(f"│  Sample rate: {SAMPLE_RATE}   Block: {BLOCK_SIZE} samples          │")
    print(f"│  Sensitivity: {args.sensitivity:<5.2f}                              │")
    print("└─────────────────────────────────────────────────┘")
    print()
    print("  [audio] ████████ level | peak | bpm  — updating every ~1s")
    print("  Press Ctrl+C to stop.")
    print()

    signal.signal(signal.SIGINT,  _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    processor = AudioProcessor(sensitivity=args.sensitivity)

    stream_kwargs = dict(
        samplerate=SAMPLE_RATE,
        blocksize=BLOCK_SIZE,
        channels=CHANNELS,
        dtype='float32',
        callback=processor.callback,
    )
    if args.device is not None:
        stream_kwargs['device'] = args.device

    try:
        stream = sd.InputStream(**stream_kwargs)
        _stream_ref = stream
        stream.start()
    except Exception as exc:
        print(f"[audio] ERROR: could not open audio stream: {exc}")
        print("[audio] Use --list to see available devices.")
        sys.exit(1)

    write_tick  = 0
    print_tick  = 0

    try:
        while True:
            time.sleep(BLOCK_SIZE / SAMPLE_RATE)  # ~23ms per block

            write_tick += 1
            print_tick += 1

            level, peak, bpm = processor.snapshot()

            # Write to control.json every WRITE_EVERY callbacks (~100ms)
            if write_tick >= WRITE_EVERY:
                write_tick = 0
                ctrl = read_ctrl()
                ctrl['audio_level'] = round(level, 4)
                ctrl['audio_peak']  = round(peak,  4)
                if bpm is not None:
                    ctrl['bpm'] = round(bpm, 1)
                save_ctrl_atomic(ctrl)

            # Print VU meter ~every 1 second
            if print_tick >= PRINT_EVERY:
                print_tick = 0
                bar = vu_bar(level, width=8)
                bpm_str = f"{bpm:.0f}bpm" if bpm is not None else "---bpm"
                print(f"[audio] {bar} {level:.2f} | peak {peak:.2f} | {bpm_str}",
                      flush=True)

    except KeyboardInterrupt:
        pass
    finally:
        stream.stop()
        stream.close()
        print("[audio] Stream closed.")


if __name__ == "__main__":
    main()
