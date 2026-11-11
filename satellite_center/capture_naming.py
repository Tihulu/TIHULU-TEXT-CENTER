"""Cross-platform source-attributed filenames. Names are candidate targets, not proof."""
from __future__ import annotations
from datetime import datetime, timezone
import re

PROFILE_TARGETS = {
    "iss_voice": "ISS-ZARYA-CANDIDATE",
    "iss_sstv": "ISS-SSTV-CANDIDATE",
    "iss_aprs": "ISS-ZARYA-CANDIDATE",
    "iss_uhf": "ISS-ZARYA-CANDIDATE",
    "meteor": "METEOR-M-CANDIDATE",
    "meteor_backup": "METEOR-M-CANDIDATE",
    "cubesat_vhf": "CUBESAT-UNATTRIBUTED",
    "cubesat_uhf": "CUBESAT-UNATTRIBUTED",
    "iridium": "IRIDIUM-UNATTRIBUTED",
}

def safe_satellite(value: str) -> str:
    text = re.sub(r"[^A-Z0-9]+", "-", str(value or "RF-UNATTRIBUTED").upper())
    return text.strip("-")[:44] or "RF-UNATTRIBUTED"

def recording_name(*, satellite: str, timestamp: datetime,
                   frequency_hz: int = 0, sample_rate: int | None = None,
                   kind: str = "IQ", extension: str = ".cu8") -> str:
    if timestamp.tzinfo is None:
        raise ValueError("UTC timestamp must include timezone")
    utc = timestamp.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if not isinstance(frequency_hz, int) or frequency_hz < 0:
        raise ValueError("Invalid receive frequency")
    if extension not in {".cu8", ".wav", ".json", ".txt", ".png", ".jpg"}:
        raise ValueError("Unsupported image or recording file extension")
    if sample_rate is not None and (not isinstance(sample_rate,int) or sample_rate<=0):
        raise ValueError("Invalid sample rate")
    rate = f"_{sample_rate}SPS" if sample_rate is not None else ""
    return (f"TIHULU_{safe_satellite(satellite)}_{utc}_{frequency_hz}Hz"
            f"{rate}_{safe_satellite(kind)}{extension}")

def meteor_capture(name: str) -> bool:
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,180}\.cu8", name):
        return False
    # New naming format includes source/candidate; legacy archives retain their
    # old *_meteor.cu8 format for backward-compatible SatDump decoding.
    return (bool(re.fullmatch(r"[A-Za-z0-9_-]+_meteor(?:_backup)?\.cu8",name))
            or bool(re.fullmatch(
                r"TIHULU_METEOR-[A-Z0-9-]+_\d{8}T\d{6}Z_137\d{6}Hz"
                r"(?:_\d{6,8}SPS)?_[A-Z0-9-]+\.cu8",name)))
