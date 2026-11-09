"""Conservative, bounded broadcaster Teletext vs real speech audit.

Only ASR and Teletext captions of the SAME recognized source language can be
compared lexically. TV subtitles may legitimately be translations or
summaries: never treat language mismatch alone as bad subtitles. Only a
sequence of substantial near-disjoint phrases can make Auto select ASR.
Teletext Hard never instantiates this probe.
"""
from __future__ import annotations
from difflib import SequenceMatcher
import re
import unicodedata


def _tokens(text):
    clean=unicodedata.normalize("NFKC",str(text or "")).casefold()
    return re.findall(r"[^\W_]+",clean,flags=re.UNICODE)[:120]


def compare_text(teletext,spoken,teletext_language,spoken_language):
    """Return matching/conflicting/unknown, not a semantic correctness claim."""
    if (not isinstance(teletext_language,str) or
            not isinstance(spoken_language,str) or
            teletext_language in ("","auto","und") or
            spoken_language in ("","auto","und") or
            teletext_language != spoken_language):
        return "unknown"
    a,b=_tokens(teletext),_tokens(spoken)
    if len(a)<5 or len(b)<5:
        return "unknown"
    common=len(set(a)&set(b)) / max(1,min(len(set(a)),len(set(b))))
    similarity=SequenceMatcher(None,a,b,autojunk=False).ratio()
    if similarity>=.47 or common>=.48:
        return "matching"
    if similarity<.18 and common<.12:
        return "conflicting"
    return "unknown"


class TeletextAudit:
    def __init__(self,maximum=4,required_conflicts=3):
        self.maximum=maximum
        self.required_conflicts=required_conflicts
        self.reset()

    def reset(self):
        self.attempts=0
        self.conflicts=0
        self.prefer_asr=False
        self.complete=False

    def needs_probe(self):
        return not self.complete and not self.prefer_asr and self.attempts<self.maximum

    def observe(self,teletext,spoken,source_lang,speech_lang):
        if not self.needs_probe():
            return "switched" if self.prefer_asr else "done"
        verdict=compare_text(teletext,spoken,source_lang,speech_lang)
        self.attempts+=1
        if verdict=="conflicting":
            self.conflicts+=1
        elif verdict=="matching":
            # A matching caption means this may be a correct broadcaster
            # transcript, even if other clips differ through time offsets.
            self.conflicts=0
            self.complete=True
        if self.conflicts>=self.required_conflicts:
            self.prefer_asr=True
            self.complete=True
            return "switched"
        if self.attempts>=self.maximum:
            self.complete=True
        return verdict
