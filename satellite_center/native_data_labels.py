"""Conservative labels for locally stored satellite/RF file formats.

A valid magic header confirms a file *format*, never a satellite transmitter,
a decoded protocol, or RF provenance. This module does not run external tools,
upload content, or read beyond the small format signature.
"""
from __future__ import annotations

from pathlib import Path


def describe_local_file(source):
    """Return (short label, explicit format/provenance explanation)."""
    path = Path(source)
    suffix = path.suffix.lower()
    if suffix == ".cu8":
        return (
            "RAW RF · CU8",
            "Unsigned interleaved I/Q samples. No image, audio, text or "
            "satellite identity has been decoded or verified.",
        )
    if suffix in (".png", ".jpg", ".jpeg", ".wav"):
        try:
            with path.open("rb") as stream:
                header = stream.read(16)
        except OSError:
            return ("UNREADABLE · " + suffix.lstrip(".").upper(),
                    "File could not be opened; format and content unverified.")
        if suffix == ".png":
            kind, valid = "IMAGE · PNG", header.startswith(b"\x89PNG\r\n\x1a\n")
        elif suffix in (".jpg", ".jpeg"):
            kind, valid = "IMAGE · JPEG", header.startswith(b"\xff\xd8\xff")
        else:
            kind = "AUDIO · WAV"
            valid = (header[:4] in (b"RIFF", b"RF64")
                     and header[8:12] == b"WAVE")
        if not valid:
            return (
                "INVALID? · " + suffix.lstrip(".").upper(),
                "The filename extension suggests a media file but its header "
                "does not match. Do not treat it as a decoded result.",
            )
        return (
            kind,
            "File signature matches. Actual media content is present on disk; "
            "satellite origin and decoder authenticity are not independently verified.",
        )
    if suffix == ".txt":
        return ("TEXT · TXT", "Local text file; not proof of a decoded RF packet.")
    if suffix == ".json":
        return ("DATA · JSON", "Local JSON metadata/report; not a decoded image.")
    if suffix == ".csv":
        return ("TABLE · CSV", "Local tabular data; not an image or audio stream.")
    if suffix == ".geojson":
        return ("MAP DATA · GeoJSON",
                "Saved map coordinates; orbital predictions are not RF measurements.")
    if suffix == ".zip":
        return ("ARCHIVE · ZIP",
                "Container of files. Contents and RF provenance are not independently verified.")
    return ("OTHER · FILE", "Unknown local format; no decoder or content claim.")
