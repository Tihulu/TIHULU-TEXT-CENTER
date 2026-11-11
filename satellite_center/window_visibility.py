"""Optional geometric line-of-sight estimate for a window-mounted antenna.

Rectangular azimuth/elevation sectors are operator estimates only. No claim
about intervening walls, glazing, antenna pattern, weather or live downlinks.
"""
from __future__ import annotations
import math


def validate_window(profile):
    if profile is None or profile is False:
        return None
    if not isinstance(profile, dict) or set(profile) != {"az", "half", "min", "max"}:
        raise ValueError("Window profile needs az, half, min and max degrees")
    try:
        az, half, low, high = (float(profile[key]) for key in ("az", "half", "min", "max"))
    except (TypeError, ValueError, KeyError) as exc:
        raise ValueError("Window angles must be numeric") from exc
    if not all(math.isfinite(x) for x in (az, half, low, high)):
        raise ValueError("Window angles must be finite")
    if not (0 <= az < 360 and 1 <= half <= 90 and 0 <= low < high <= 90):
        raise ValueError("Window azimuth/width/elevation outside valid ranges")
    return {"az": az, "half": half, "min": low, "max": high}


def inside_window(az, elevation, window):
    if window is None:
        return True
    if not math.isfinite(az) or not math.isfinite(elevation):
        return False
    difference = abs(((az-window["az"]+540) % 360)-180)
    return difference <= window["half"] and window["min"] <= elevation <= window["max"]


def summarize_window(samples, window, *, max_gap_seconds=15):
    """Ordered (UNIX timestamp seconds, az degrees, elevation degrees) samples.

    Consecutive samples within the visibility window form segments. Gaps are
    NOT counted as visible. The rating is purely geometric, not RF quality.
    """
    window = validate_window(window)
    if window is None:
        return None
    tracks = []
    active = []
    best = -90.0
    for stamp, az, el in samples:
        if inside_window(az, el, window):
            best = max(best, el)
            if active and stamp-active[-1][0] > max_gap_seconds:
                tracks.append(active)
                active = []
            active.append((stamp, az, el))
        elif active:
            tracks.append(active)
            active = []
    if active:
        tracks.append(active)
    duration = sum(max(0, segment[-1][0]-segment[0][0])
                   for segment in tracks if len(segment)>1)
    if not tracks:
        return {"status": "outside", "seconds": 0,
                "peak_elevation": None, "segments": [],
                "note": "No predicted samples in assumed window sector"}
    status = "good_geometry" if duration >= 180 else (
        "short_window" if duration >= 60 else "very_short")
    return {
        "status": status, "seconds": round(duration),
        "peak_elevation": round(best, 1),
        "segments": [{"start": int(segment[0][0]*1000),
                      "end": int(segment[-1][0]*1000)}
                     for segment in tracks],
        "note": "Estimated window-sector overlap; no real RF/obstruction verification"
    }
