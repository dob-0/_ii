#!/usr/bin/env python3
"""_ii | osc_server.py — OSC input receiver.

Listens for OSC messages and merges them into control.json so visuals.py
and ii.py pick them up on their next read cycle.

Usage:
    python3 osc_server.py               # listen on 0.0.0.0:7000
    python3 osc_server.py --port 9000   # custom port
    python3 osc_server.py --host 127.0.0.1 --port 7000

Optional mapping file: place osc_map.json in the project root to define
additional or override address → key mappings:
    {
        "/my/address": "control_key",
        "/live/tempo": "bpm"
    }
"""

import argparse
import json
import os
import signal
import sys
import tempfile

try:
    from pythonosc import dispatcher as osc_dispatcher
    from pythonosc import osc_server as osc_server_lib
    from pythonosc.dispatcher import Dispatcher
    from pythonosc.osc_server import ThreadingOSCUDPServer
except ImportError:
    print("ERROR: python-osc is not installed.")
    print("  pip install python-osc")
    sys.exit(1)

# ── Paths ──────────────────────────────────────────────────────────────────────

BASE = os.path.dirname(os.path.abspath(__file__))
CTRL_PATH = os.path.join(BASE, 'control.json')
OSC_MAP_PATH = os.path.join(BASE, 'osc_map.json')

# ── Default OSC address → control.json key mapping ────────────────────────────
#
# Format:  "/osc/address": ("control_key", type_coerce)
#   type_coerce is called on the first OSC argument:
#     int, float, str, or a lambda for custom logic.
#
# For /ii/blackout and /ii/flash: int 0/1 → bool

DEFAULT_MAP = {
    # ii native addresses
    "/_ii/mode":         ("mode",              int),
    "/_ii/mode_b":       ("mode_b",            int),
    "/_ii/palette":      ("palette",           int),
    "/_ii/bpm":          ("bpm",               float),
    "/_ii/blackout":     ("blackout",          lambda v: bool(int(v))),
    "/_ii/master_dim":   ("master_dim",        float),
    "/_ii/glitch":       ("glitch_intensity",  float),
    "/_ii/rain":         ("rain_density",      float),
    "/_ii/wave":         ("wave_amplitude",    float),
    "/_ii/strobe":       ("strobe_speed",      int),
    "/_ii/layer_b":      ("layer_b_enabled",   lambda v: bool(int(v))),
    "/_ii/layer_b_alpha":("layer_b_alpha",     float),
    "/_ii/audio_level":  ("audio_level",       float),
    "/_ii/audio_peak":   ("audio_peak",        float),
    "/_ii/flash_text":   ("flash_text",        str),
    "/_ii/flash":        ("flash_active",      lambda v: bool(int(v))),
    "/_ii/auto_cycle":   ("auto_cycle",        lambda v: bool(int(v))),

    # Ableton Live standard addresses (common Live → Max for Live OSC outputs)
    "/live/tempo":      ("bpm",               float),
    "/live/master/volume": ("master_dim",     float),

    # TouchOSC default page 1 faders and toggles (common layout)
    "/1/fader1":        ("master_dim",        float),
    "/1/fader2":        ("glitch_intensity",  float),
    "/1/fader3":        ("wave_amplitude",    float),
    "/1/fader4":        ("rain_density",      float),
    "/1/fader5":        ("bpm",               lambda v: 40.0 + float(v) * 200.0),
    "/1/fader6":        ("layer_b_alpha",     float),
    "/1/toggle1":       ("blackout",          lambda v: bool(int(v))),
    "/1/toggle2":       ("flash_active",      lambda v: bool(int(v))),
    "/1/toggle3":       ("layer_b_enabled",   lambda v: bool(int(v))),
    "/1/toggle4":       ("auto_cycle",        lambda v: bool(int(v))),
    "/1/push1":         ("flash_active",      lambda v: bool(int(v))),
    "/1/rotary1":       ("strobe_speed",      lambda v: max(1, int(float(v) * 10))),
    "/1/rotary2":       ("palette",           lambda v: int(float(v) * 5)),
    "/1/rotary3":       ("mode",              lambda v: int(float(v) * 18)),
}

# ── JSON helpers ──────────────────────────────────────────────────────────────

def read_ctrl():
    try:
        with open(CTRL_PATH, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def save_ctrl_atomic(data):
    """Atomic write matching save_json_atomic in architecture.py."""
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
        print(f"[osc] WARNING: atomic write failed ({exc}), falling back to direct write")
        with open(CTRL_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f)
    finally:
        if tmp:
            try:
                os.unlink(tmp)
            except FileNotFoundError:
                pass


def merge_and_write(key, value):
    """Read current control.json, set key=value, write back atomically."""
    ctrl = read_ctrl()
    ctrl[key] = value
    save_ctrl_atomic(ctrl)

# ── OSC handler factory ───────────────────────────────────────────────────────

def make_handler(osc_addr, ctrl_key, coerce):
    """Return a pythonosc handler function for the given mapping."""
    def handler(address, *args):
        if not args:
            print(f"[osc] {address} — received no arguments, ignoring")
            return
        raw = args[0]
        try:
            value = coerce(raw)
        except (ValueError, TypeError) as exc:
            print(f"[osc] {address} — coerce error: {exc} (raw={raw!r})")
            return
        merge_and_write(ctrl_key, value)
        print(f"[osc] {address}  →  {ctrl_key} = {value!r}")
    return handler


def make_default_handler(address_map):
    """Fallback handler: prints unmapped messages, also checks address_map for
    addresses registered after server start (shouldn't happen, but defensive)."""
    def handler(address, *args):
        print(f"[osc] (unmapped) {address}  args={args}")
    return handler

# ── Load optional osc_map.json ────────────────────────────────────────────────

def load_osc_map_file():
    """Load osc_map.json if it exists. Returns dict of addr → key (string keys only)."""
    if not os.path.exists(OSC_MAP_PATH):
        return {}
    try:
        with open(OSC_MAP_PATH, encoding='utf-8') as f:
            raw = json.load(f)
        if not isinstance(raw, dict):
            print(f"[osc] WARNING: {OSC_MAP_PATH} is not a JSON object, ignoring")
            return {}
        # Values must be strings (control.json keys). Coerce is always float→stored.
        result = {}
        for addr, key in raw.items():
            if isinstance(key, str):
                result[addr] = key
            else:
                print(f"[osc] WARNING: osc_map.json entry {addr!r}: value must be a string key, got {key!r}")
        print(f"[osc] Loaded {len(result)} custom mappings from osc_map.json")
        return result
    except Exception as exc:
        print(f"[osc] WARNING: could not load {OSC_MAP_PATH}: {exc}")
        return {}

# ── Build full address map ────────────────────────────────────────────────────

def build_address_map():
    """Merge DEFAULT_MAP with osc_map.json overrides.

    osc_map.json entries are addr → ctrl_key strings; coerce defaults to
    auto-detect (try int, then float, then str).
    """
    addr_map = dict(DEFAULT_MAP)

    def auto_coerce(v):
        # Try numeric coercion; fall back to str.
        try:
            as_float = float(v)
            if as_float == int(as_float):
                return int(as_float)
            return as_float
        except (ValueError, TypeError):
            return str(v)

    for addr, key in load_osc_map_file().items():
        addr_map[addr] = (key, auto_coerce)

    return addr_map

# ── Server setup ──────────────────────────────────────────────────────────────

def build_dispatcher(address_map):
    d = Dispatcher()
    for addr, (ctrl_key, coerce) in address_map.items():
        d.map(addr, make_handler(addr, ctrl_key, coerce))
    d.set_default_handler(make_default_handler(address_map))
    return d


def print_banner(host, port, address_map):
    print()
    print("┌─────────────────────────────────────────────────┐")
    print("│  ii — OSC server                                │")
    print(f"│  Listening on  {host}:{port:<5}                      │")
    print(f"│  Mapped addresses: {len(address_map):<4}                       │")
    print("└─────────────────────────────────────────────────┘")
    print()
    print("  OSC address            →  control key")
    print("  ──────────────────────────────────────────────")
    for addr, (key, _) in sorted(address_map.items()):
        print(f"  {addr:<26}  {key}")
    print()
    print("  Optional: create osc_map.json to add/override mappings.")
    print("  Press Ctrl+C to stop.")
    print()

# ── Signal handling ───────────────────────────────────────────────────────────

_server_ref = None

def _handle_signal(signum, frame):
    sig_name = signal.Signals(signum).name
    print(f"\n[osc] Received {sig_name}, shutting down…")
    if _server_ref is not None:
        _server_ref.shutdown()
    sys.exit(0)

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    global _server_ref

    parser = argparse.ArgumentParser(description="_ii OSC input receiver")
    parser.add_argument("--host", default="0.0.0.0", help="Bind address (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=7000, help="UDP port to listen on (default: 7000)")
    args = parser.parse_args()

    address_map = build_address_map()
    d = build_dispatcher(address_map)

    print_banner(args.host, args.port, address_map)

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    try:
        server = ThreadingOSCUDPServer((args.host, args.port), d)
        _server_ref = server
        server.serve_forever()
    except OSError as exc:
        print(f"[osc] ERROR: could not bind to {args.host}:{args.port} — {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
