"""DAB DLS song metadata extraction, shared contract with native radio tab.

DLS is *only* broadcaster metadata. An artist/title pair is a search hint,
never proof the lyrics are available or currently audible. No HTTP calls here.
"""
from __future__ import annotations
from dataclasses import dataclass
import re
import unicodedata

_PREFIX = re.compile(r"^(?:jetzt\s+on\s+air|now\s+(?:on\s+air|playing)|"
                     r"aktuell|şimdi\s+çalıyor|simdi\s+caliyor)\s*:*\s*",
                     re.I)
_EXTRA = re.compile(r"\s+(?:\[(?:live|radio\s+edit)\]|\((?:live|radio\s+edit)\))$", re.I)


@dataclass(frozen=True)
class SongHint:
    artist: str
    title: str
    format: str

    @property
    def key(self) -> str:
        def clean(part: str) -> str:
            p = unicodedata.normalize("NFKD",part).casefold()
            return " ".join(re.findall(r"[^\W_]+",p))
        return clean(self.artist)+"|"+clean(self.title)


def parse_dls_song(text: str) -> SongHint | None:
    """Support Artist - Title and German/Turkish track-first station formats."""
    if not isinstance(text,str) or not 5<=len(text)<=330:
        return None
    text=" ".join(text.strip().split())
    if "::" in text:
        parts=[p.strip(" :-") for p in text.split("::")]
        if len(parts)>=3 and _PREFIX.match(parts[0]+":"):
            title,artist=parts[1],parts[2]
            style="track_first_station"
        else:
            return None
    elif " - " in text or " – " in text or " — " in text:
        parts=re.split(r"\s+[-–—]\s+",text,maxsplit=1)
        if len(parts)!=2:
            return None
        artist,title=parts
        style="artist_first"
    else:
        match=re.match(r"^(?:now playing|jetzt läuft|şimdi çalıyor)\s*:\s*"
                       r"(.+?)\s+by\s+(.+)$",text,re.I)
        if not match:
            return None
        title,artist=match.group(1),match.group(2)
        style="track_first_by"
    title=_EXTRA.sub("",title).strip()
    artist=_PREFIX.sub("",artist).strip(" :-")
    if (not artist or not title or len(artist)>130 or len(title)>130
            or artist.casefold()==title.casefold()):
        return None
    return SongHint(artist,title,style)
