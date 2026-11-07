# SPDX-License-Identifier: GPL-2.0-or-later
"""Bounded real DVB capture queue with contiguous clips, overlap, and telemetry.

Inference may be slower than broadcast. Unlike the old 'busy => drop 4s'
logic, each chunk is placed in FIFO and processed in chronological order.
The memory cap is explicit; sustained CPU overload eventually exceeds
finite resources and is reported rather than silently inventing captions.
"""
from __future__ import annotations
from collections import deque
from dataclasses import dataclass
import threading


@dataclass(frozen=True)
class CapturedClip:
    data: bytes
    options: dict
    started: float
    ended: float

    @property
    def bytes(self):
        return len(self.data)


class BufferedCaptionQueue:
    def __init__(self, maximum_bytes=96*1024*1024, max_clips=24):
        if maximum_bytes <= 0 or max_clips <= 0:
            raise ValueError("Invalid capture queue limits")
        self.limit = int(maximum_bytes)
        self.max_clips = int(max_clips)
        self.items = deque()
        self.bytes = 0
        self.overflow_seconds = 0.0
        self.overflow_count = 0
        self.cv = threading.Condition()
        self.closed = False

    def offer(self, clip: CapturedClip):
        if not isinstance(clip, CapturedClip):
            raise TypeError("Expected captured DVB TS clip")
        with self.cv:
            if self.closed:
                return False
            if (clip.bytes > self.limit or len(self.items) >= self.max_clips or
                    self.bytes + clip.bytes > self.limit):
                self.overflow_count += 1
                self.overflow_seconds += max(0.0, clip.ended-clip.started)
                return False
            self.items.append(clip)
            self.bytes += clip.bytes
            self.cv.notify()
            return True

    def get(self, timeout=None):
        with self.cv:
            if not self.items and not self.closed:
                self.cv.wait(timeout)
            if not self.items:
                return None
            clip = self.items.popleft()
            self.bytes -= clip.bytes
            return clip

    def clear(self):
        with self.cv:
            self.items.clear()
            self.bytes = 0

    def close(self):
        with self.cv:
            self.closed = True
            self.items.clear()
            self.bytes = 0
            self.cv.notify_all()

    def snapshot(self):
        with self.cv:
            return {"queued_clips": len(self.items), "queued_mib": round(self.bytes/1048576,1),
                    "missed_seconds": round(self.overflow_seconds,1),
                    "overflows":self.overflow_count, "queue_cap_mib":round(self.limit/1048576)}


def prepended_overlap(current: bytes, previous: bytes, preceding_duration: float,
                       overlap_seconds=0.75, cap_bytes=1024*1024) -> bytes:
    """Carry a short packet-aligned previous tail across speech boundaries.

    This covers words cut between chunks without hallucinating time samples.
    The separate text-level de-duplicator removes repeat words when they occur.
    """
    if not previous or not current or preceding_duration <= 0:
        return current
    packets = int(min(len(previous)/max(0.2, preceding_duration)*overlap_seconds,
                      cap_bytes) // 188)
    if packets <= 0:
        return current
    return previous[-packets*188:]+current


def _words(text):
    return [w for w in text.split() if w]


def remove_repeated_prefix(previous: str, current: str, maximum_words=16) -> str:
    """Trim the longest repeated word suffix / prefix after audio overlap.

    Conservative token-level matching: do not remove a whole different
    sentence merely because it shares a generic two-word expression.
    """
    import re
    before = _words(previous)
    now = _words(current)
    if not before or not now:
        return current.strip()
    def normalized(w):
        return re.sub(r"^[^\w]+|[^\w]+$", "", w, flags=re.UNICODE).casefold()
    for n in range(min(maximum_words,len(before),len(now)),0,-1):
        if [normalized(x) for x in before[-n:]] == [normalized(x) for x in now[:n]]:
            if n == 1 and len(now)>2:
                continue
            return " ".join(now[n:]).strip()
    return current.strip()
