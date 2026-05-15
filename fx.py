#!/usr/bin/env python3
"""Shared post-FX rack for ii visuals/output buffers."""

import math
import random


def _clamp(value, low=0.0, high=1.0):
    try:
        return max(low, min(high, float(value)))
    except Exception:
        return low


def _clone(buf):
    return [row[:] for row in buf]


def _is_non_space(cell):
    return cell is not None and cell[0] != ' '


def active_fx_labels(state):
    mix = _clamp(state.get('fx_mix', 0.0))
    if mix <= 0.01:
        return []
    labels = []
    if _clamp(state.get('fx_shutter', 0.0)) > 0.05:
        labels.append('SHUT')
    if _clamp(state.get('fx_slice', 0.0)) > 0.05:
        labels.append('SLICE')
    if _clamp(state.get('fx_kaleido', 0.0)) > 0.05:
        labels.append('KALEIDO')
    if _clamp(state.get('fx_echo', 0.0)) > 0.05:
        labels.append('ECHO')
    return labels


class FXRack:
    def __init__(self):
        self._previous = {}

    def reset(self, key=None):
        if key is None:
            self._previous.clear()
        else:
            self._previous.pop(key, None)

    def apply(self, key, buf, w, h, state, frame):
        if w <= 0 or h <= 0:
            return

        wet = _clamp(state.get('fx_mix', 0.0))
        source = _clone(buf)
        prev = self._previous.get(key)
        work = source

        if wet > 0.01:
            shutter = wet * _clamp(state.get('fx_shutter', 0.0))
            if shutter > 0.01:
                work = self._apply_shutter(work, w, h, frame, shutter)

            slice_amt = wet * _clamp(state.get('fx_slice', 0.0))
            if slice_amt > 0.01:
                work = self._apply_slice(work, w, h, frame, slice_amt)

            kaleido = wet * _clamp(state.get('fx_kaleido', 0.0))
            if kaleido > 0.01:
                work = self._apply_kaleido(work, w, h, frame, kaleido)

            echo = wet * _clamp(state.get('fx_echo', 0.0))
            if echo > 0.01 and prev and len(prev) == h and len(prev[0]) == w:
                work = self._apply_echo(work, prev, w, h, echo)

        for y in range(h):
            buf[y][:] = work[y]
        self._previous[key] = _clone(buf)

    def _apply_shutter(self, src, w, h, frame, amount):
        dst = _clone(src)
        band = max(2, int(round(8 - amount * 5)))
        cut = max(1, int(round(1 + amount * 3)))
        open_phase = int(frame * (1 + amount * 2))
        for y in range(h):
            if ((y + open_phase) % (band + cut)) < cut:
                row = dst[y]
                for x in range(w):
                    if amount > 0.65 and (x + frame) % 2 == 0:
                        row[x] = None
                    elif amount > 0.25:
                        row[x] = None
        return dst

    def _apply_slice(self, src, w, h, frame, amount):
        dst = [[None] * w for _ in range(h)]
        strip_h = max(1, int(round(1 + (1.0 - amount) * max(2, h * 0.12))))
        max_shift = max(1, int(round(w * (0.04 + amount * 0.14))))
        for y0 in range(0, h, strip_h):
            phase = frame * (0.12 + amount * 0.18) + y0 * 0.61
            shift = int(round(math.sin(phase) * max_shift))
            for y in range(y0, min(h, y0 + strip_h)):
                src_row = src[y]
                dst_row = dst[y]
                for x in range(w):
                    dst_row[x] = src_row[(x - shift) % w]
        return dst

    def _apply_kaleido(self, src, w, h, frame, amount):
        dst = _clone(src)
        full_quad = amount > 0.55
        drift = int(round(math.sin(frame * 0.07) * amount * max(1, w * 0.04)))
        for y in range(h):
            sy = y
            if full_quad and y >= h // 2:
                sy = h - 1 - y
            for x in range(w):
                sx = x
                if x >= w // 2:
                    sx = w - 1 - x
                sx = (sx + drift) % max(1, w)
                sample = src[sy][sx]
                if _is_non_space(sample) and (amount >= 0.95 or random.random() < amount):
                    dst[y][x] = sample
        return dst

    def _apply_echo(self, src, prev, w, h, amount):
        dst = _clone(src)
        hold = 0.25 + amount * 0.55
        for y in range(h):
            dst_row = dst[y]
            prev_row = prev[y]
            for x in range(w):
                cur = dst_row[x]
                old = prev_row[x]
                if not _is_non_space(old):
                    continue
                if not _is_non_space(cur) or random.random() < hold:
                    dst_row[x] = old
        return dst
