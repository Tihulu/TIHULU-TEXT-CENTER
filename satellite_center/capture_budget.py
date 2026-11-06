"""Receive-only duration and disk budget for a predicted satellite pass.

'full-pass-attempt' describes the visible recording window only, never
a complete spacecraft dataset, guaranteed RF signal or decoded image.
"""
from __future__ import annotations
from datetime import datetime, timedelta
import math

IQ_RATE = 1_024_000
IQ_BYTES_PER_SECOND = 2 * IQ_RATE
SSTV_WAV_BYTES_PER_SECOND = 48_000 * 2  # mono signed PCM via rtl_fm
MAX_IQ_BYTES = 2_000_000_000  # 2 GB streamed to disk, not to browser RAM
MAX_CAPTURE_SECONDS = 900
DISK_RESERVE_BYTES = 200_000_000
LEAD_SECONDS = 10
END_MARGIN_SECONDS = 4
MINIMUM_SECONDS = {
    "meteor-m2-3": 120, "meteor-m2-4": 120,
    "iss-sstv": 45, "iss-aprs": 20, "iss-voice": 20,
}
KINDS = {
    "meteor-m2-3": "image", "meteor-m2-4": "image",
    "iss-sstv": "image", "iss-aprs": "text", "iss-voice": "audio",
}


def plan_capture_budget(aos: datetime, los: datetime, mission_id: str,
                        *, free_bytes: int | None, goal: str = "full",
                        start_at: datetime | None = None) -> dict:
    if mission_id not in MINIMUM_SECONDS:
        raise ValueError("Unknown public downlink planning target")
    if goal not in ("full", "sample"):
        raise ValueError("Coverage goal must be full or sample")
    if aos.tzinfo is None or los.tzinfo is None or los <= aos:
        raise ValueError("Geometric pass must have timezone-aware times")
    start = start_at if start_at is not None else aos-timedelta(seconds=LEAD_SECONDS)
    if start.tzinfo is None:
        raise ValueError("Scheduled capture needs timezone-aware start")
    window = max(0, math.floor((los-start).total_seconds())-END_MARGIN_SECONDS)
    limit = min(window, MAX_CAPTURE_SECONDS)
    if goal == "sample":
        limit = min(limit, 60)
    bytes_per_second = (SSTV_WAV_BYTES_PER_SECOND if mission_id in ("iss-sstv","iss-voice")
                        else 0 if KINDS[mission_id] == "text"
                        else IQ_BYTES_PER_SECOND)
    if bytes_per_second:
        if bytes_per_second == IQ_BYTES_PER_SECOND:
            limit = min(limit, MAX_IQ_BYTES//IQ_BYTES_PER_SECOND)
        if free_bytes is not None:
            if not isinstance(free_bytes, int) or free_bytes < 0:
                raise ValueError("Invalid disk availability")
            limit = min(limit, max(0, (free_bytes-DISK_RESERVE_BYTES)//bytes_per_second))
    seconds = max(0, int(limit))
    estimated = seconds*bytes_per_second
    minimum = (20 if goal == "sample" and mission_id.startswith("meteor-")
               else MINIMUM_SECONDS[mission_id])
    coverage = "full-pass-attempt" if seconds >= window and seconds >= minimum else "partial-pass"
    return {
        "mission_id": mission_id, "data_kind": KINDS[mission_id],
        "pass_visible_seconds": max(0, math.floor((los-aos).total_seconds())),
        "target_seconds": window, "capture_seconds": seconds,
        "minimum_useful_seconds": minimum, "feasible": seconds >= minimum,
        "estimated_bytes": estimated, "coverage": coverage,
        "shortfall_seconds": max(0, window-seconds),
        "note": ("Short Meteor RF evidence only; do not infer a complete LRPT image."
                 if goal == "sample" and mission_id.startswith("meteor-")
                 else "Unverified downlink candidate. Full window cannot guarantee complete satellite data or image.")
    }
