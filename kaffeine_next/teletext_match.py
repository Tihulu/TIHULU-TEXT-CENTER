"""Continuous, bounded DVB Teletext vs actual spoken-audio ASR audit.

Auto mode only. Never treat valid Teletext PID or matching timestamps as
proof captions belong to the heard programme. Comparison needs same,
confirmed language and substantial lexical evidence; translation/summaries
and unrelated-language subtitles remain UNKNOWN rather than false mismatch.
Captions and audio come from the SAME selected SID/TSID capture epoch.
"""
from __future__ import annotations
from collections import deque
from difflib import SequenceMatcher
import re
import unicodedata


def _tokens(text):
    clean=unicodedata.normalize("NFKC",str(text or "")).casefold()
    return re.findall(r"[^\W_]+",clean,flags=re.UNICODE)[:120]


def compare_text(teletext,spoken,teletext_language,spoken_language):
    """matching/conflicting/unknown; not a semantic or timestamp guarantee."""
    if (not isinstance(teletext_language,str) or
            not isinstance(spoken_language,str) or
            teletext_language in ("","auto","und") or
            spoken_language in ("","auto","und") or
            teletext_language != spoken_language):
        return "unknown"
    a,b=_tokens(teletext),_tokens(spoken)
    if len(a)<5 or len(b)<5:
        return "unknown"
    common=len(set(a)&set(b))/max(1,min(len(set(a)),len(set(b))))
    similarity=SequenceMatcher(None,a,b,autojunk=False).ratio()
    if similarity>=.47 or common>=.48:
        return "matching"
    if similarity<.18 and common<.12:
        return "conflicting"
    return "unknown"


class TeletextAudit:
    """Initial + periodic speech probes and hysteretic recovery.

    On fallback ASR continues every clip; the old Teletext is sampled only
    periodically. Two independent matching checks are required to return.
    'delayed' is a suspected caption shift, NOT measured video/audio PTS.
    """
    def __init__(self,maximum=4,required_conflicts=3,probe_interval=3,
                 required_recoveries=2):
        if min(maximum,required_conflicts,probe_interval,required_recoveries)<1:
            raise ValueError("Teletext audit limits must be positive")
        self.maximum=maximum
        self.required_conflicts=required_conflicts
        self.probe_interval=probe_interval
        self.required_recoveries=required_recoveries
        self.reset()

    def reset(self):
        self.attempts=0
        self.conflicts=0
        self.prefer_asr=False
        self.complete=False
        self.clips=0
        self.recoveries=0
        self.last_verdict="unknown"
        self.last_reason="waiting for actual broadcaster speech"
        self.status="TELETEXT · CHECKING"
        self._previous=deque(maxlen=3)

    def mark_clip(self):
        """Call exactly once per selected-service capture, not per UI tick."""
        self.clips+=1

    def needs_probe(self):
        return self.clips<=self.maximum or self.clips%self.probe_interval==0

    def missing(self):
        self.prefer_asr=True
        self.recoveries=0
        self.last_verdict="missing"
        self.last_reason="No usable broadcaster subtitle text; Whisper active"
        self.status="WHISPER · AUTO FALLBACK"
        return "missing"

    def observe(self,teletext,spoken,source_lang,speech_lang):
        verdict=compare_text(teletext,spoken,source_lang,speech_lang)
        if verdict=="conflicting":
            # Speech and Teletext may be one capture apart. Check bounded
            # neighbouring verified snippets before calling a mismatch.
            for prior_teletext,prior_spoken,prior_source,prior_speech in self._previous:
                if (compare_text(teletext,prior_spoken,source_lang,
                                 prior_speech)=="matching" or
                    compare_text(prior_teletext,spoken,prior_source,
                                 speech_lang)=="matching"):
                    verdict="delayed"
                    break
        if spoken and teletext:
            self._previous.append((str(teletext)[:2500],str(spoken)[:2500],
                                   source_lang,speech_lang))
        self.attempts+=1
        self.last_verdict=verdict
        if self.prefer_asr:
            # Never return to old subtitles on one lucky matching phrase.
            if verdict=="matching":
                self.recoveries+=1
                if self.recoveries>=self.required_recoveries:
                    self.prefer_asr=False
                    self.conflicts=0
                    self.recoveries=0
                    self.status="TELETEXT · SYNCED"
                    self.last_reason="Recovered; two verified matching audio checks"
                    return "recovered"
            elif verdict!="unknown":
                self.recoveries=0
            self.status="WHISPER · AUTO FALLBACK"
            self.last_reason="Rechecking broadcaster captions against live audio"
            return verdict
        if verdict=="matching":
            self.conflicts=0
            self.complete=True
            self.status="TELETEXT · SYNCED"
            self.last_reason="Current caption text corroborated by real speech"
        elif verdict=="delayed":
            self.conflicts=0
            self.status="TELETEXT · DELAY CHECK"
            self.last_reason=("Neighbouring captured phrases match; timing "
                              "may lag. No verified libVLC output PTS.")
        elif verdict=="conflicting":
            self.conflicts+=1
            self.status="TELETEXT · MISMATCH"
            self.last_reason=f"{self.conflicts}/{self.required_conflicts} independent mismatches"
            if self.conflicts>=self.required_conflicts:
                self.prefer_asr=True
                self.complete=True
                self.recoveries=0
                self.status="WHISPER · AUTO FALLBACK"
                self.last_reason="Confirmed repeated Teletext/speech mismatch"
                return "switched"
        else:
            self.last_reason="No reliable same-language spoken verification yet"
            if self.status!="TELETEXT · SYNCED":
                self.status="TELETEXT · CHECKING"
        return verdict
