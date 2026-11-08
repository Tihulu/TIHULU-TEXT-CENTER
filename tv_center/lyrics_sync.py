"""Optional timed lyrics for user-owned audio and DAB+ radio metadata.

Internet lookup is NEVER automatic. It requires explicit --online or a
user-initiated GUI action; the free LRCLIB service needs no token. A
plain/unsynced lyric cannot be aligned to music from metadata alone, so
the player does not invent timings. The caller should retain provenance
and respect rights/terms of third-party lyric sources.
"""
from __future__ import annotations

from dataclasses import dataclass
import bisect
import json
from pathlib import Path
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request


_LRC_LINE = re.compile(r"^\[(\d{1,3}):(\d{2})(?:\.(\d{1,3}))?\](.*)$")
_MAX_RECORD_BYTES = 2_000_000
_CLIENT = "TIHULU-Kaffeine/0.2 (+https://github.com/Tihulu/TIHULU-TEXT-CENTER)"


@dataclass(frozen=True)
class LyricCue:
    start: float
    end: float
    text: str
    provenance: str = "local"
    language: str | None = None


def parse_lrc(content: str, *, duration: float | None = None,
              provenance: str = "local") -> list[LyricCue]:
    """Parse synced LRC lines, including multiple leading time tags.

    Preserve order at equal timestamps and truncate pathological inputs.
    A lyric cue is shown only after its own timestamp; labels/metadata are
    ignored and are never mistaken for song lines.
    """
    if not isinstance(content, str) or len(content) > _MAX_RECORD_BYTES:
        raise ValueError("LRC content missing or exceeds safety limit")
    lines = []
    for line in content.splitlines()[:6000]:
        remainder = line.strip()
        stamps = []
        while True:
            match = _LRC_LINE.match(remainder)
            if not match:
                break
            mins, secs, fraction, rest = match.groups()
            if int(secs) >= 60:
                break
            decimal = (fraction or "0").ljust(3, "0")[:3]
            timestamp = 60 * int(mins) + int(secs) + int(decimal) / 1000
            stamps.append(timestamp)
            remainder = rest.strip()
        lyric = remainder.strip()
        if not stamps or not lyric:
            continue
        if lyric.startswith("[") and lyric.endswith("]"):
            continue
        if len(lyric) > 700:
            lyric = lyric[:700]
        for stamp in stamps:
            if 0 <= stamp <= 36000:
                lines.append((stamp, lyric))
    lines = sorted(set(lines), key=lambda item: item[0])[:1500]
    cues = []
    for i, (stamp, text) in enumerate(lines):
        following = lines[i+1][0] if i+1 < len(lines) else stamp + 5
        if duration is not None:
            following = min(following, float(duration))
        end = max(stamp + 0.1, min(stamp + 12, following))
        cues.append(LyricCue(stamp, end, text, provenance))
    return cues


def cue_at(cues: list[LyricCue], position: float) -> LyricCue | None:
    if not cues or position < 0:
        return None
    starts = [cue.start for cue in cues]
    i = bisect.bisect_right(starts, position) - 1
    return cues[i] if i >= 0 and position < cues[i].end else None


def local_lrc(media_path: str | Path) -> Path | None:
    target = Path(media_path).expanduser().resolve(strict=True)
    if not target.is_file():
        raise ValueError("Expected a local audio file")
    candidate = target.with_suffix(".lrc")
    if candidate.is_file() and not candidate.is_symlink() and (
            candidate.stat().st_size <= _MAX_RECORD_BYTES):
        return candidate
    return None


def _get_json(url: str) -> dict:
    # No external redirect to other origins; do not send metadata to a
    # redirected host. This lookup is triggered only at user request.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, request, fp, code, msg, headers, newurl):
            return None
    opener = urllib.request.build_opener(
        NoRedirect(), urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    request = urllib.request.Request(
        url, headers={"User-Agent":_CLIENT, "Accept":"application/json"})
    try:
        with opener.open(request, timeout=8) as response:
            if response.status != 200:
                raise RuntimeError(f"Lyrics service HTTP {response.status}")
            data = response.read(_MAX_RECORD_BYTES + 1)
            if len(data) > _MAX_RECORD_BYTES:
                raise ValueError("Lyrics lookup response too large")
            record = json.loads(data)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return {}
        if exc.code == 429:
            raise RuntimeError(
                "Lyrics lookup rate-limited. Retry later; no automatic loop.") from exc
        raise RuntimeError(f"Lyrics lookup unavailable: HTTP {exc.code}") from exc
    if not isinstance(record, dict):
        raise ValueError("Unexpected LRCLIB response")
    return record


def lookup_synced_lyrics(*, title: str, artist: str,
                         album: str = "", duration: float | None = None,
                         online: bool = False) -> tuple[list[LyricCue],dict]:
    """User-authorized keyless search. No plain-lyrics timing guess."""
    if not online:
        raise PermissionError(
            "Online lyrics search is OFF by default; ask explicitly to search")
    if (not isinstance(title,str) or not isinstance(artist,str) or
            not title.strip() or not artist.strip() or
            max(len(title),len(artist),len(album)) > 180):
        raise ValueError("Artist and song title are required for safe matching")
    params = {"track_name":title.strip(), "artist_name":artist.strip()}
    if album.strip():
        params["album_name"] = album.strip()
    if duration is not None and 1 <= float(duration) <= 3600:
        params["duration"] = round(float(duration))
    url = "https://lrclib.net/api/get?" + urllib.parse.urlencode(params)
    record = _get_json(url)
    if not record:
        return [], {"status":"not_found","provider":"LRCLIB"}
    if (str(record.get("trackName","")).casefold().strip() !=
            title.casefold().strip() or
            str(record.get("artistName","")).casefold().strip() !=
            artist.casefold().strip()):
        raise ValueError("Lyrics result metadata did not match requested song")
    if duration is not None and isinstance(record.get("duration"),(int,float)):
        if abs(float(record["duration"])-float(duration)) > 3:
            raise ValueError("Lyrics duration mismatch; refusing unsafe auto-sync")
    if record.get("instrumental"):
        return [], {"status":"instrumental","provider":"LRCLIB"}
    synced = record.get("syncedLyrics")
    if not synced or not isinstance(synced,str):
        return [], {"status":"unsynced_only","provider":"LRCLIB",
                    "message":"No time-coded lyrics; not aligning by guess"}
    cues = parse_lrc(synced,duration=duration,provenance="LRCLIB")
    return cues, {"status":"synced" if cues else "invalid",
                  "provider":"LRCLIB","record_id":record.get("id"),
                  "track":title,"artist":artist,
                  "online_lookup":True}


def srt_timestamp(seconds: float) -> str:
    ms=max(0,int(round(seconds*1000)))
    return f"{ms//3600000:02}:{(ms//60000)%60:02}:{(ms//1000)%60:02},{ms%1000:03}"


def write_srt(cues: list[LyricCue], path: str | Path, *,
              overwrite: bool = False, translations: dict[int,str] | None = None):
    target=Path(path).expanduser()
    if target.is_symlink() or not target.parent.is_dir():
        raise ValueError("Output directory invalid or destination is symlink")
    lines = []
    for i, cue in enumerate(cues,1):
        if cue.end <= cue.start:
            continue
        text = cue.text
        if translations and translations.get(i):
            text += "\n" + translations[i]
        lines.append(f"{i}\n{srt_timestamp(cue.start)} --> {srt_timestamp(cue.end)}\n{text}\n")
    if len(lines) > 1500:
        raise ValueError("Subtitle cue budget exceeded")
    flags = "w" if overwrite else "x"
    with target.open(flags,encoding="utf-8") as output:
        output.write("\n".join(lines))
    return target
