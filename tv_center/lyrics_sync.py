"""Lyrics from opt-in online metadata or local LRC.

The client only requests LRCLIB with explicit opt-in. Plain lyrics are
allowed as *text*, not fabricated timestamps. Optional locally recognized
speech can provide approximate, evidence-based sequential line alignment;
unmatched lyrics remain hidden and are not given invented times.
"""
from __future__ import annotations

from dataclasses import dataclass
import bisect
import json
from pathlib import Path
import re
import ssl
import unicodedata
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


def _get_json(url: str, *, allow_list: bool=False):
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
    if allow_list and isinstance(record,list):
        return [item for item in record[:20] if isinstance(item,dict)]
    if not isinstance(record, dict):
        raise ValueError("Unexpected LRCLIB response")
    return record


def lookup_synced_lyrics(*, title: str, artist: str,
                         album: str = "", duration: float | None = None,
                         online: bool = False,
                         allow_plain: bool = False) -> tuple[list[LyricCue],dict]:
    """User-authorized keyless lookup with optional unsynced plain lines.

    Plain lines are data for a *subsequent* real ASR matcher; never
    pass them off as synchronized lyric timestamps.
    """
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
        # One opt-in catalog search; accept ONLY exact title+artist metadata.
        search_url="https://lrclib.net/api/search?"+urllib.parse.urlencode(
            {"track_name":title.strip(),"artist_name":artist.strip()})
        results=_get_json(search_url,allow_list=True)
        exact=[item for item in results
               if str(item.get("trackName","")).casefold().strip()==title.casefold().strip()
               and str(item.get("artistName","")).casefold().strip()==artist.casefold().strip()
               and not item.get("instrumental")]
        record=next((item for item in exact if item.get("syncedLyrics")),
                    exact[0] if exact else {})
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
        raw = record.get("plainLyrics")
        if allow_plain and isinstance(raw,str):
            # Newlines only; reject headers/tags and enforce tight bounds.
            cleaned = []
            for line in raw.splitlines()[:300]:
                line = " ".join(line.strip().split())
                if (3 <= len(line) <= 240 and
                        not (line.startswith("[") and line.endswith("]"))):
                    cleaned.append(line)
                if len(cleaned) >= 150:
                    break
            if cleaned:
                return [], {
                    "status":"plain","provider":"LRCLIB",
                    "record_id":record.get("id"),
                    "track":title,"artist":artist,
                    "plain_lines":cleaned,
                    "alignment":"awaiting_real_audio_ASR",
                    "online_lookup":True}
        return [], {"status":"unsynced_only","provider":"LRCLIB",
                    "message":"Only plain lyrics found; no time codes"}
    cues = parse_lrc(synced,duration=duration,provenance="LRCLIB")
    return cues, {"status":"synced" if cues else "invalid",
                  "provider":"LRCLIB","record_id":record.get("id"),
                  "track":title,"artist":artist,
                  "online_lookup":True}



def _lyric_tokens(text: str) -> list[str]:
    # NFKD gives case/accent-insensitive candidates, including Turkish.
    plain = unicodedata.normalize("NFKD", text).casefold()
    plain = "".join(c for c in plain if not unicodedata.combining(c))
    return re.findall(r"[^\W_]+", plain, flags=re.UNICODE)[:90]


class LiveLyricMatcher:
    """Conservative forward-only match of verified lyrics to *heard* ASR.

    Does not detect a song by itself and makes no timestamps where no
    recognizable vocal phrase is present. One or two generic words are
    insufficient evidence for a match. This is approximate chunk timing,
    NOT sample-accurate forced alignment.
    """
    def __init__(self, lines: list[str]):
        if not isinstance(lines,list) or len(lines)>150:
            raise ValueError("Invalid plain lyric line catalog")
        self.lines=[line for line in lines if isinstance(line,str) and
                    3<=len(line)<=240]
        self.position=0
        self.seen_chunks=0
        self.previous_text=""

    def observe(self, recognized: str) -> dict | None:
        if not isinstance(recognized,str) or not recognized.strip():
            return None
        self.seen_chunks += 1
        heard = _lyric_tokens(self.previous_text + " " + recognized)
        self.previous_text = recognized[-480:]
        if len(heard)<3:
            return None
        hearing=set(heard)
        best=None
        # At most 8 forward lines. Never jump to a random distant refrain.
        for index in range(self.position, min(len(self.lines),self.position+8)):
            original=self.lines[index]
            expected=_lyric_tokens(original)
            if len(expected)<3:
                continue
            distinctive={word for word in expected if len(word)>=3}
            evidence=sum(1 for word in distinctive if word in hearing)
            if evidence<3:
                continue
            coverage=evidence/max(1,len(distinctive))
            precision=evidence/max(1,len(hearing))
            confidence=0.82*coverage+0.18*min(1.,precision*2.)
            if confidence>=0.74 and (best is None or confidence>best[0]):
                best=(confidence,index,original)
        if best is None:
            return None
        score,index,line=best
        self.position=index+1
        return {"index":index,"text":line,"confidence":round(score,3),
                "kind":"observed_ASR_chunk_match","approximate":True}

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
