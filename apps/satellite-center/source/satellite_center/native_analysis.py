"""Local bounded RF analysis and real-result ZIP. No browser/HTTP/Qt dependency.

CU8 is unsigned interleaved I/Q. This is statistical RF evidence only:
neither a satellite identifier nor a validated image/packet decoder.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import zipfile

MAX_IQ_BYTES = 2_000_000_000
MAX_RESULTS_BYTES = 256 * 1024 * 1024
ALLOWED_RESULTS = {".json", ".txt", ".csv", ".png", ".jpg", ".jpeg", ".wav"}


def _file(path):
    p = Path(path).expanduser()
    if not p.is_file() or p.is_symlink():
        raise ValueError("Select an existing regular local recording, not a symlink")
    return p


def safe_report_name(source):
    """Stable evidence name, never dependent on a remote/satellite claim."""
    stem = re.sub(r"[^a-zA-Z0-9_-]+", "_", Path(source).stem)[:95].strip("_")
    return (stem or "unidentified_rf") + "_spectrum.json"


def analyze_cu8(path, sample_rate=1_024_000, center_hz=0, *,
                mode="overview", fft_size=2048, overview_windows=48):
    """Chunked IQ FFT using a maximum ~1 MiB temporary block.

    'overview' inspects distributed time windows, not the complete recording.
    'full' visits all aligned 2048-complex-sample windows in bounded batches.
    No assumptions about modulation or spacecraft can follow from FFT peaks.
    """
    try:
        import numpy as np
    except ImportError as exc:
        raise RuntimeError("Native IQ analyzer needs python3-numpy") from exc
    p = _file(path)
    size = p.stat().st_size
    if p.suffix.lower() != ".cu8":
        raise ValueError("Native raw IQ spectrum accepts unsigned interleaved .cu8")
    if size < fft_size * 2 or size > MAX_IQ_BYTES:
        raise ValueError("CU8 recording must contain samples and be <= 2 GB")
    if type(sample_rate) is not int or not 100_000 <= sample_rate <= 3_200_000:
        raise ValueError("Enter an actual sample rate (100 k–3.2 MS/s)")
    if not isinstance(center_hz, (int, float)) or not math.isfinite(center_hz) or not 0 <= center_hz <= 2_000_000_000:
        raise ValueError("Invalid receiver center frequency")
    if mode not in ("overview", "full"):
        raise ValueError("Choose overview or full stream analysis")
    complex_count = size // 2
    total_windows = complex_count // fft_size
    if not total_windows:
        raise ValueError("Insufficient complete IQ samples")
    if mode == "overview":
        count = min(overview_windows, total_windows)
        indices = np.linspace(0, total_windows - 1, count, dtype=np.int64)
        groups = ([int(x)] for x in indices)
    else:
        batch_windows = 64
        groups = (range(i, min(i + batch_windows, total_windows))
                  for i in range(0, total_windows, batch_windows))
        count = total_windows
    taper = np.hanning(fft_size).astype(np.float32)
    spectrum_sum = np.zeros(fft_size, dtype=np.float64)
    waterfall = []
    samples_used = 0
    blocks = 0
    rms_sum = 0.0
    # At most 96 waterfall rows, never pretend an overview covered all time.
    row_every = max(1, int(math.ceil(count / 96))) if mode == "overview" else max(1, math.ceil(total_windows / 96))
    with p.open("rb") as f:
        for indices in groups:
            start = int(indices[0]) * fft_size
            length = len(indices) * fft_size
            f.seek(start * 2)
            raw = f.read(length * 2)
            q = np.frombuffer(raw, dtype=np.uint8)
            actual = len(q) // (2 * fft_size)
            if not actual:
                continue
            a = q[:actual * 2 * fft_size].astype(np.float32).reshape(actual, fft_size, 2)
            iq = (a[:, :, 0] - 127.5 + 1j * (a[:, :, 1] - 127.5)) / 128.0
            ft = np.fft.fftshift(np.fft.fft(iq * taper, axis=1), axes=1)
            power = (np.abs(ft) / max(1.0, float(taper.sum()))) ** 2
            spectrum_sum += power.sum(axis=0)
            rms_sum += float(np.mean(np.abs(iq) ** 2)) * actual
            samples_used += actual * fft_size
            blocks += actual
            if len(waterfall) < 96 and (blocks == actual or blocks % row_every < actual or blocks >= count):
                row = 10 * np.log10(np.mean(power, axis=0) + 1e-16)
                waterfall.append(row)
    if not blocks:
        raise RuntimeError("Recording did not contain usable complete IQ windows")
    spectrum = 10 * np.log10(spectrum_sum / blocks + 1e-16)
    peak = int(np.argmax(spectrum))
    frequency = float(center_hz + (peak - fft_size // 2) * sample_rate / fft_size)
    # 512 bins/row bounded JSON, even for a 2 GB full scan.
    stride = max(1, math.ceil(fft_size / 512))
    def compact(row):
        return [round(float(np.mean(row[i:i+stride])), 3) for i in range(0, fft_size, stride)]
    return {
        "format": "tihulu-native-real-cu8-spectrum-v1",
        "source": str(p), "source_bytes": size,
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "analysis_mode": mode, "complete_time_coverage": mode == "full",
        "sample_rate_hz": sample_rate, "center_hz": int(center_hz),
        "complex_samples_available": complex_count, "complex_samples_analyzed": samples_used,
        "processed_fft_windows": blocks, "fft_size": fft_size,
        "estimated_recording_seconds": round(complex_count / sample_rate, 3),
        "relative_rms_dbfs_like": round(10 * math.log10(rms_sum / blocks + 1e-16), 3),
        "strongest_spectrum_bin_hz": round(frequency, 2),
        "strongest_bin_relative_db": round(float(spectrum[peak]), 2),
        "frequencies_hz": [round(center_hz + (i + stride / 2 - fft_size / 2) * sample_rate / fft_size, 2)
                           for i in range(0, fft_size, stride)],
        "relative_spectrum_db": compact(spectrum),
        "waterfall_db": [compact(row) for row in waterfall],
        "warnings": [
            "Uncalibrated digital RF energy; no satellite or payload identity is proven.",
            "No image, packet CRC or audio content is claimed from an FFT.",
            "Overview samples distributed windows only; full processes aligned windows across the entire file."
        ]
    }


def save_spectrum_report(source, report, archive):
    root = Path(archive)
    root.mkdir(parents=True, exist_ok=True)
    destination = root / safe_report_name(source)
    tmp = destination.with_suffix(".json.partial")
    try:
        with tmp.open("x", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        os.replace(tmp, destination)
    finally:
        tmp.unlink(missing_ok=True)
    return destination


def export_results_zip(outputs, destination, *, source=None, max_bytes=MAX_RESULTS_BYTES):
    """Only genuine explicit files, never the raw multi-GB CU8 recording."""
    files = []
    total = 0
    for original in outputs:
        p = _file(original)
        if p.suffix.lower() not in ALLOWED_RESULTS:
            raise ValueError("Result ZIP only accepts real PNG/JPG/WAV/TXT/JSON/CSV outputs")
        if p in files:
            continue  # Same actual output selected through multiple result controls.
        size = p.stat().st_size
        total += size
        if total > max_bytes:
            raise ValueError("Result ZIP exceeds 256 MiB. Preserve large originals separately.")
        files.append(p)
    if not files:
        raise ValueError("No real analysis output files to export")
    dest = Path(destination).expanduser()
    if dest.suffix.lower() != ".zip":
        raise ValueError("Choose a .zip filename")
    if dest in files or dest.is_symlink():
        raise ValueError("ZIP destination conflicts with an existing result")
    dest.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "format": "tihulu-local-real-results-v1",
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": str(source) if source else "user-selected",
        "raw_iq_included": False, "spacecraft_verified": False,
        "complete_spacecraft_dataset": False,
        "files": [{"archive": f"results/{i:03d}_{p.name}", "size": p.stat().st_size,
                   "source_path": str(p)} for i, p in enumerate(files, 1)]
    }
    tmp = dest.with_name(dest.name + ".partial")
    try:
        with zipfile.ZipFile(tmp, mode="x", compression=zipfile.ZIP_STORED, allowZip64=False) as out:
            out.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
            for item, p in zip(manifest["files"], files):
                out.write(p, item["archive"])
        os.replace(tmp, dest)
    finally:
        tmp.unlink(missing_ok=True)
    return dest
