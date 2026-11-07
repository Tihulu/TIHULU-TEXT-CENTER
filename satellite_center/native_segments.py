"""Receive-only segmented native captures with clear reset gaps.

These parts are separate RF recordings, never mathematically continuous I/Q.
The native receiver can also record a single continuous IQ file when desired.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import ceil
from typing import Any

MAX_GROUP_SECONDS = 900
MAX_NATIVE_PARTS = 30
NATIVE_PART_SECONDS = 180
NATIVE_RESET_SECONDS = 2


def capture_parts(total_seconds: int, *, cap_seconds: int = NATIVE_PART_SECONDS,
                  gap_seconds: int = NATIVE_RESET_SECONDS) -> list[dict[str, int]]:
    if type(total_seconds) is not int or not 8 <= total_seconds <= MAX_GROUP_SECONDS:
        raise ValueError("Total native recording must be 8–900 whole seconds")
    if type(cap_seconds) is not int or not 8 <= cap_seconds <= 900:
        raise ValueError("Segment cap must be 8–900 whole seconds")
    if type(gap_seconds) is not int or not 0 <= gap_seconds <= 15:
        raise ValueError("Native restart gap must be 0–15 seconds")
    n = ceil(total_seconds / cap_seconds)
    if n > MAX_NATIVE_PARTS:
        raise ValueError("Too many native segments")
    base, extra = divmod(total_seconds, n)
    cursor = 0
    parts: list[dict[str, int]] = []
    for i in range(n):
        duration = base + (i < extra)
        if duration < 8:
            raise ValueError("Native segment shorter than minimum receiver duration")
        parts.append({
            "index": i + 1, "count": n,
            "offset_seconds": cursor, "duration_seconds": duration,
            "end_offset_seconds": cursor + duration,
        })
        cursor += duration + (gap_seconds if i + 1 < n else 0)
    return parts


def format_native_countdown(remaining: float) -> str:
    n = max(0, ceil(remaining))
    days, rem = divmod(n, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)
    return f"{days}d {hours:02}h {minutes:02}m {seconds:02}s"


def total_wall_seconds(parts: list[dict[str, int]]) -> int:
    return parts[-1]["end_offset_seconds"] if parts else 0
