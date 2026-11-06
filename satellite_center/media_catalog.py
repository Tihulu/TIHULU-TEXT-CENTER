"""Honest, static satellite reception capability metadata for native Qt.

These are *candidate* formats and local catalogued receiver presets.
TLE passes do not prove transmission or a complete decoded media dataset.
"""
from __future__ import annotations

from dataclasses import dataclass
import shutil

MEDIA_TYPES = ("Image", "Audio", "Text", "RF data")
MEDIA_COLORS = {
    "Image": "#E1A852",
    "Audio": "#AFA0F3",
    "Text": "#59CEAB",
    "RF data": "#69BCF4",
}
MEDIA_SYMBOLS = {
    "Image": "▧",
    "Audio": "♫",
    "Text": "≡",
    "RF data": "◈",
}

@dataclass(frozen=True)
class MediaCapability:
    kind: str
    title: str
    profile: str
    frequency_hz: int | None
    processing: str
    confidence: str
    requirement: str


_CATALOG = {
    "iss_sstv": MediaCapability("Image", "ISS SSTV / Robot36 image candidate", "iss_sstv",
        437550000, "Real FM WAV → Robot36 (separate decoder)", "Event only / unverified",
        "Confirm an active ARISS SSTV event and actual carrier reception"),
    "iss_voice": MediaCapability("Audio", "ISS voice / FM audio", "iss_voice",
        145800000, "FM demodulated WAV", "Conditional / unverified",
        "A live voice/SSTV downlink may be absent on this pass"),
    "iss_aprs": MediaCapability("Text", "ISS APRS / AX.25 packets", "iss_aprs",
        145825000, "AFSK packet decoder; CRC validation required", "Conditional / unverified",
        "Requires real packet frames and a working decoder"),
    "iss_aprs_uhf": MediaCapability("Text", "ISS UHF APRS / AX.25 packets", "iss_aprs_uhf",
        437825000, "AFSK packet decoder; CRC validation required", "Conditional / unverified",
        "Confirm active frequency and valid packet CRC"),
    "iss_uhf": MediaCapability("Audio", "ISS FM repeater audio", "iss_uhf",
        437800000, "FM demodulated WAV", "Conditional / unverified",
        "The repeater may be inactive"),
    "meteor": MediaCapability("Image", "Meteor-M LRPT Earth imagery candidate", "meteor",
        137900000, "Raw CU8 IQ → SatDump LRPT/FEC → image", "Decoder required / unverified",
        "Install SatDump; record enough of a real pass for valid sync and FEC"),
    "meteor_backup": MediaCapability("Image", "Meteor-M alternate LRPT imagery candidate", "meteor_backup",
        137100000, "Raw CU8 IQ → SatDump LRPT/FEC → image", "Alternate channel / unverified",
        "Frequency and broadcast activity depend on the actual spacecraft"),
}

_NO_KNOWN_IMAGE = (
    "No image protocol is catalogued for this satellite here. "
    "This does not prove the spacecraft has no imagery payload."
)

def capabilities_for_pass(pass_row, profiles=None):
    """Return known possibilities from pass-specific local receiver profiles.

    Returns no capability for survey-only Cubesats/Iridium. An RF-only
    candidate is *not* evidence of satellite payload decoding.
    """
    from .__main__ import PROFILES
    available = PROFILES if profiles is None else profiles
    offered = set(pass_row.get("profiles") or [])
    capabilities = [_CATALOG[key] for key in _CATALOG
                    if key in offered and key in available]
    if "iss_voice" in offered and "iss_sstv" not in offered:
        capabilities.append(MediaCapability(
            "Image", "ISS VHF SSTV candidate", "iss_voice", 145800000,
            "Real FM WAV → SSTV decoder", "Event only / unverified",
            "Only during an announced active ISS SSTV event"))
    # Every predicted pass admits RF *survey* only when a receiver preset
    # exists. This alone does not identify a transmitter or payload.
    if offered:
        capabilities.append(MediaCapability(
            "RF data", "Raw/relative RF measurements (unidentified)", "",
            None, "Local rtl_sdr CU8 IQ or rtl_power spectrum survey",
            "Receiver measurement only", "Actual SDR hardware and reception required"))
    return capabilities

def kinds_for_pass(pass_row):
    kinds = {item.kind for item in capabilities_for_pass(pass_row)}
    return [kind for kind in MEDIA_TYPES if kind in kinds]

def filter_passes(rows, kind="All", search=""):
    if kind not in ("All",) + MEDIA_TYPES:
        raise ValueError("Unknown media filter")
    query = search.casefold().strip()
    def matches(row):
        if kind != "All" and kind not in kinds_for_pass(row):
            return False
        text = (str(row.get("name",""))+" "+str(row.get("norad",""))+" "+
                str(row.get("family",""))+" "+" ".join(row.get("profiles") or []))
        return query in text.casefold()
    return [row for row in rows if matches(row)]

def media_summary(pass_row, *, check_decoders=False):
    """Brief honest explanation shown beneath the selected Qt pass card."""
    items = capabilities_for_pass(pass_row)
    descriptions = []
    for cap in items:
        if cap.kind == "RF data":
            continue
        text = f"{cap.kind}: {cap.title} | {cap.confidence}"
        if cap.frequency_hz:
            text += f" | {cap.frequency_hz / 1e6:.3f} MHz"
        if check_decoders and cap.profile.startswith("meteor"):
            text += " | SatDump "+("installed" if shutil.which("satdump") else "not installed")
        descriptions.append(text+" | "+cap.requirement)
    if not any(c.kind == "Image" for c in items):
        descriptions.append(_NO_KNOWN_IMAGE)
    if not descriptions:
        descriptions.append("No published image/audio/text decoder in this app. RF survey only.")
    descriptions.append(
        "Predicted orbital visibility ≠ actual received RF; availability and full dataset are unverified.")
    return descriptions
