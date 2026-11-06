"""Bounded, receive-only Robot36 candidate extraction from genuine FM PCM WAV.

The ISS pass/TLE/frequency do NOT authenticate a transmitter. Only a repeated
1200 Hz Robot36 line-sync train permits a candidate PNG; no generated examples
or substitute frames. Handles long recordings in overlapped, bounded windows
without loading the entire RF pass or installing Pillow/Numpy.
"""
from __future__ import annotations

from .compute_backends import resolve_compute_backend, vectorized_frequency_trace
from array import array
from bisect import bisect_left
from pathlib import Path
import json
import struct
import sys
import wave
import zlib

WIDTH, HEIGHT = 320, 240
LINE_SECONDS = 0.150
WINDOW_SECONDS = 55
STEP_SECONDS = 23
MIN_ALIGNED_LINES = 200
MAX_IMAGES = 12
SERIES35 = {
    "event": "ARISS Expedition 75 Series 35 - Space Memories",
    "start_utc_date": "2026-11-09",
    "end_utc_date": "2026-11-16",
    "times": "TBD; verify live ARISS status before scheduling",
    "frequency_hz": 437550000,
    "mode": "Robot36",
    "transmit_seconds": 36,
    "gap_seconds": 120,
    "source": "https://www.ariss.org/upcoming-sstv-events.html",
    "mode_note": "ARISS event web page has a Robot 35/36 discrepancy; announcement and amateur-radio reports say Robot36.",
}


def _clamp(value: float) -> int:
    return max(0, min(255, round(value)))


def _trace(raw: bytes, rate: int) -> list[float]:
    samples = array("h")
    samples.frombytes(raw)
    if sys.byteorder != "little":
        samples.byteswap()  # RIFF PCM is little endian.
    crosses = []
    for i in range(1, len(samples)):
        left, right = samples[i - 1], samples[i]
        if left < 0 <= right:
            crosses.append((i - 1 - left / (right - left or 1)) / rate)
    length = int(len(samples) * 1000 / rate)
    trace = [0.0] * length
    lo = hi = 0
    for n in range(length):
        center = (n + .5) / 1000
        a, b = center - .003, center + .003
        while lo < len(crosses) and crosses[lo] < a:
            lo += 1
        if hi < lo:
            hi = lo
        while hi < len(crosses) and crosses[hi] <= b:
            hi += 1
        if hi - lo >= 5:
            trace[n] = max(400, min(4000,
                (hi - lo - 1) / (crosses[hi - 1] - crosses[lo])))
    return trace


def _syncs(trace: list[float]) -> list[float]:
    found = []
    start = None
    for i in range(len(trace) + 1):
        matched = i < len(trace) and 1050 < trace[i] < 1340
        if matched and start is None:
            start = i
        elif not matched and start is not None:
            if 5 <= i - start <= 16:
                found.append(start / 1000)
            start = None
    return found


def _nearest(syncs: list[float], expected: float, tolerance: float = .0055):
    pos = bisect_left(syncs, expected)
    values = syncs[max(0, pos-1):pos+1]
    matches = [v for v in values if abs(v - expected) < tolerance]
    return min(matches, key=lambda v: abs(v-expected)) if matches else None


def _line_alignment(syncs: list[float]):
    if len(syncs) < MIN_ALIGNED_LINES:
        return None
    best = None
    # A 55-second window cannot contain many independent 36-second images.
    for origin in syncs[:250]:
        matched = 0
        drift = 0.0
        for row in range(HEIGHT):
            expected = origin + row * LINE_SECONDS
            if expected > syncs[-1] + .01:
                break
            near = _nearest(syncs, expected)
            if near is not None:
                matched += 1
                drift += abs(near-expected)
        if best is None or (matched, -drift) > (best[1], -best[2]):
            best = (origin, matched, drift)
    return best if best and best[1] >= MIN_ALIGNED_LINES else None


def _tone(trace: list[float], second: float) -> float:
    center = int(second * 1000)
    values = [trace[i] for i in range(center-2, center+3)
              if 0 <= i < len(trace) and 700 < trace[i] < 3000]
    return sum(values) / len(values) if values else 0


def _pixel(trace: list[float], second: float) -> int:
    value = _tone(trace, second)
    return _clamp((value-1500) * 255 / 800) if value else 127


def _png(width: int, height: int, rgb: bytes) -> bytes:
    def chunk(kind, payload):
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(
            ">I", zlib.crc32(kind + payload) & 0xffffffff)
    raw = b"".join(b"\x00" + rgb[y * width * 3:(y + 1) * width * 3]
                   for y in range(height))
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, level=6))
            + chunk(b"IEND", b""))


def _decode_window(raw: bytes, sample_rate: int, trace_backend: str = "python-cpu"):
    trace = (_trace(raw, sample_rate) if trace_backend == "python-cpu" else
             vectorized_frequency_trace(raw, sample_rate, gpu=trace_backend == "cupy-cuda"))
    syncs = _syncs(trace)
    alignment = _line_alignment(syncs)
    if alignment is None:
        return None
    start, _, drift = alignment
    Y = [bytearray(WIDTH) for _ in range(HEIGHT)]
    red = [[0] * WIDTH for _ in range(HEIGHT)]
    blue = [[0] * WIDTH for _ in range(HEIGHT)]
    aligned = 0
    for row in range(HEIGHT):
        point = _nearest(syncs, start + row * LINE_SECONDS, .006)
        if point is None or point + .148 >= len(trace) / 1000:
            continue
        for x in range(WIDTH):
            Y[row][x] = _pixel(trace, point + .012 + (x+.5)*.088/WIDTH)
            chroma = _pixel(trace, point + .106 + (x+.5)*.044/WIDTH)-128
            if row % 2 == 0:
                red[row][x] = chroma
            else:
                blue[row][x] = chroma
        aligned += 1
    if aligned < MIN_ALIGNED_LINES:
        return None
    pixels = bytearray(WIDTH * HEIGHT * 3)
    for y in range(HEIGHT):
        pair = (y//2)*2
        for x in range(WIDTH):
            yy, cr, cb = Y[y][x], red[pair][x], blue[min(pair+1, HEIGHT-1)][x]
            index = (y*WIDTH+x)*3
            pixels[index] = _clamp(yy + 1.403*cr)
            pixels[index+1] = _clamp(yy - .714*cr - .344*cb)
            pixels[index+2] = _clamp(yy + 1.773*cb)
    return {"start": start, "aligned_lines": aligned, "sync_candidates": len(syncs),
            "mean_sync_drift_seconds": drift / max(1, aligned),
            "png": _png(WIDTH, HEIGHT, pixels)}


def extract_robot36_wav(path: str | Path, *, max_images: int = MAX_IMAGES,
                        compute_mode: str = "auto", compute_targets=None) -> dict:
    """Attempt automatic PNG candidates from a genuine 48 kHz mono PCM WAV.

    Never treats signal strength, a known ISS pass, or a WAV filename as
    an authenticated spacecraft transmission. No result image without
    at least MIN_ALIGNED_LINES repeated line syncs.
    """
    source = Path(path)
    if source.suffix.lower() != ".wav" or not source.is_file():
        raise ValueError("Choose an existing real WAV capture")
    if not 1 <= max_images <= MAX_IMAGES:
        raise ValueError("Maximum output image count must be 1-12")
    result = {
        "schema": "tihulu-robot36-reception-v1",
        "source_recording": source.name,
        "event_reference": SERIES35,
        "input_provenance": "actual-local-sdr-wav-unverified-satellite",
        "receiver_frequency_hz": SERIES35["frequency_hz"],
        "decoder": "stdlib-experimental-Robot36-1200Hz-line-sync",
        "min_aligned_lines": MIN_ALIGNED_LINES,
        "images": [],
        "status": "no_valid_robot36_sync",
        "warning": "Even matched line sync does not prove ISS origin, visual accuracy or a full image.",
    }
    candidates = []
    with wave.open(str(source), "rb") as wav:
        rate, channels, width = wav.getframerate(), wav.getnchannels(), wav.getsampwidth()
        if channels != 1 or width != 2 or not 8000 <= rate <= 96000 or wav.getcomptype() != "NONE":
            raise ValueError("Robot36 requires uncompressed mono 16-bit PCM WAV (8-96 kHz)")
        frames = wav.getnframes()
        duration = frames / rate
        if not 32 <= duration <= 910:
            raise ValueError("Recorded SSTV WAV must be 32-910 seconds")
        result["recorded_seconds"] = round(duration, 3)
        compute = resolve_compute_backend(compute_mode, compute_targets, seconds=duration)
        result["compute"] = compute
        for offset in range(0, max(1, int(duration)-31), STEP_SECONDS):
            wav.setpos(offset*rate)
            raw = wav.readframes(min(WINDOW_SECONDS*rate, frames-offset*rate))
            if len(raw) < 32*rate*2:
                continue
            try:
                candidate = _decode_window(raw, rate, compute["trace_backend"])
            except Exception as exc:
                if compute_mode != "auto" or compute["trace_backend"] != "cupy-cuda":
                    raise
                # A disappearing GPU must not destroy a successfully saved WAV.
                compute["fallback_reason"] = "Real GPU execution failed: " + str(exc)[:180]
                compute["trace_backend"] = resolve_compute_backend("auto", [], seconds=0)["trace_backend"]
                candidate = _decode_window(raw, rate, compute["trace_backend"])
            if candidate is None:
                continue
            candidate["recording_offset_seconds"] = round(offset+candidate["start"], 3)
            at = candidate["recording_offset_seconds"]
            old = next((x for x in candidates
                        if abs(x["recording_offset_seconds"]-at) < 4), None)
            if old is not None:
                if candidate["aligned_lines"] > old["aligned_lines"]:
                    candidates.remove(old)
                else:
                    continue
            candidates.append(candidate)
    candidates.sort(key=lambda candidate: candidate["recording_offset_seconds"])
    for index, candidate in enumerate(candidates[:max_images], start=1):
        output = source.with_name(source.stem + "_ROBOT36_" + f"{index:02d}" + ".png")
        output.write_bytes(candidate.pop("png"))
        result["images"].append({
            "file": output.name,
            "time_offset_seconds": candidate["recording_offset_seconds"],
            "aligned_lines": candidate["aligned_lines"],
            "sync_candidates": candidate["sync_candidates"],
            "status": "full-sync-candidate" if candidate["aligned_lines"] >= 225 else "partial-sync-candidate",
            "satellite_identity_verified": False,
        })
    if result["images"]:
        result["status"] = "robot36_sync_candidates_decoded"
    return result
