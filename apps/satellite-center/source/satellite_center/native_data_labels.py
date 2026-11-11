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
            "File header matches; complete media decoding is not checked. "
            "satellite origin and decoder authenticity are not independently verified.",
        )
    if suffix in (".mp4",".m4v",".mov",".webm",".gif",".webp",
                  ".mp3",".ogg",".flac"):
        try:
            with path.open("rb") as stream:
                header=stream.read(24)
        except OSError:
            return ("UNREADABLE · "+suffix.lstrip(".").upper(),
                    "Cannot read a local media header; content not verified.")
        if suffix in (".mp4",".m4v",".mov"):
            valid=len(header)>=12 and header[4:8]==b"ftyp"
            media="VIDEO · "+suffix[1:].upper()
        elif suffix==".webm":
            valid=header.startswith(bytes((0x1a,0x45,0xdf,0xa3)))
            media="VIDEO · WEBM"
        elif suffix==".gif":
            valid=header[:6] in (b"GIF87a",b"GIF89a")
            media="IMAGE · GIF"
        elif suffix==".webp":
            valid=header[:4]==b"RIFF" and header[8:12]==b"WEBP"
            media="IMAGE · WEBP"
        elif suffix==".mp3":
            valid=header.startswith(b"ID3") or (len(header)>1 and
                   header[0]==0xff and header[1]&0xe0==0xe0)
            media="AUDIO · MP3"
        elif suffix==".ogg":
            valid=header.startswith(b"OggS")
            media="AUDIO · OGG"
        else:
            valid=header.startswith(b"fLaC")
            media="AUDIO · FLAC"
        if not valid:
            return ("INVALID? · "+suffix.lstrip(".").upper(),
                    "Filename extension and bounded header check disagree.")
        return (media,
                "Media magic-header matched. This does not verify full playback, "
                "valid codec support, satellite origin or actual RF reception.")

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
