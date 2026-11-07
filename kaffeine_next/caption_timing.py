# SPDX-License-Identifier: GPL-2.0-or-later
"""Applied caption controls, bounded cue scheduling and private Kaffeine OSD IPC.

Only the current user's runtime directory is used. A caption never moves
audio relative to video: both remain in the DVB transport stream. The optional
native playback buffer is a separate, explicit setting.

Whisper works in chunks; the cue is anchored to capture timestamps and is
displayed as soon as possible, never deceptively described as sample-accurate.
"""
from __future__ import annotations
from dataclasses import dataclass, replace
import json
import os
from pathlib import Path
import queue
import re
import tempfile
import time

MODE = ("auto", "teletext", "asr", "page", "off")
LANGS = ("de", "en", "tr")

@dataclass(frozen=True)
class CaptionConfig:
    mode: str = "auto"
    source: str = "de"
    target: str = "tr"
    page: int = 150
    offset_ms: int = 0
    playback_delay_ms: int = 0
    on_video: bool = True
    show_original: bool = True
    show_translation: bool = True
    position: str = "bottom"
    font_px: int = 25
    opacity: int = 70
    revision: int = 0

    def validate(self):
        if self.mode not in MODE or self.source not in LANGS or self.target not in LANGS:
            raise ValueError("Unknown caption source or language")
        if type(self.page) is not int or not 100 <= self.page <= 899:
            raise ValueError("Teletext page must be an integer 100–899")
        if type(self.offset_ms) is not int or not -10000 <= self.offset_ms <= 10000:
            raise ValueError("Caption offset must be -10 to +10 seconds")
        if type(self.playback_delay_ms) is not int or not 0 <= self.playback_delay_ms <= 8000:
            raise ValueError("Playback buffering must be 0–8 seconds")
        if self.position not in ("bottom", "top"):
            raise ValueError("Unknown caption position")
        if type(self.font_px) is not int or not 16 <= self.font_px <= 44:
            raise ValueError("Font size must be 16–44 pixels")
        if type(self.opacity) is not int or not 0 <= self.opacity <= 100:
            raise ValueError("Opacity must be 0–100%")
        for key in ("on_video", "show_original", "show_translation"):
            if type(getattr(self, key)) is not bool:
                raise ValueError("Caption display toggles must be boolean")
        return self

    def options(self):
        return {"mode":self.mode,"source":self.source,
                "target":self.target,"page":self.page,"revision":self.revision}

    def render(self, result):
        original = (result.get("original") or "").strip()
        translated = (result.get("translated") or "").strip()
        lines = []
        if self.show_original and original:
            lines.append(original)
        if self.show_translation and translated and translated != original:
            lines.append(translated)
        return "\n".join(lines)[:1100]


def cue_window(started, ended, finished, config: CaptionConfig):
    """Schedule a chunk relative to the *captured* audio, not decoder finish.

    When ASR finishes late the caption is necessarily late and the reported
    lateness tells the user whether more TV buffering is needed.
    """
    cue_start = float(started) + (config.playback_delay_ms +
                                   config.offset_ms) / 1000.0
    duration = max(2.5, min(8.0, float(ended) - float(started) + 1.0))
    return {
        "due":max(float(finished), cue_start),
        "expires":max(float(finished), cue_start) + duration,
        "lateness_ms":max(0, round((float(finished) - cue_start) * 1000)),
        "revision":config.revision,
    }


class CueQueue:
    def __init__(self, maximum=8):
        self.maximum = maximum
        self.items = []

    def add(self, result, config, captured_start, captured_end, finished):
        when = cue_window(captured_start, captured_end, finished, config)
        cue = {"result":dict(result), "config":config, **when}
        self.items = [x for x in self.items
                      if x["revision"] == config.revision and x["expires"] > finished]
        self.items.append(cue)
        self.items.sort(key=lambda x: x["due"])
        self.items = self.items[-self.maximum:]
        return cue

    def poll(self, now, revision):
        self.items = [x for x in self.items
                      if x["revision"] == revision and x["expires"] > now]
        due = [x for x in self.items if x["due"] <= now]
        if not due:
            return None
        selected = due[-1]
        self.items = [x for x in self.items if x["due"] > now]
        return selected

    def clear(self):
        self.items.clear()


class KaffeineOSD:
    def __init__(self, pid, runtime=None):
        runtime = Path(runtime or os.environ.get("XDG_RUNTIME_DIR", ""))
        if not runtime.is_dir() or runtime.is_symlink():
            raise ValueError("XDG_RUNTIME_DIR unavailable or unsafe")
        if type(pid) is not int or pid <= 0 or pid > 2**31-1:
            raise ValueError("Invalid Kaffeine PID")
        self.root = runtime
        self.path = runtime / f"tihulu-caption-{pid}.json"
        self.delay = runtime / f"tihulu-playback-delay-{pid}.txt"
        self.last_delay = 0

    def _atomic(self, path, content):
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", prefix=".tihulu-",
                                         dir=self.root, delete=False) as fp:
            temp = Path(fp.name)
            fp.write(content)
        try:
            os.chmod(temp, 0o600)
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)

    def publish(self, text, config: CaptionConfig, ttl_ms=2000):
        config.validate()
        if not config.on_video or config.mode == "off":
            text = ""
        obj = {"text":str(text)[:1100], "position":config.position,
               "size":config.font_px, "opacity":config.opacity,
               "enabled":bool(config.on_video and config.mode != "off"),
               "expires_ms":int(time.time()*1000) + min(max(int(ttl_ms),0),15000)}
        self._atomic(self.path, json.dumps(obj,ensure_ascii=False,separators=(",",":")))

    def set_playback_delay(self, config: CaptionConfig):
        config.validate()
        self._atomic(self.delay, str(config.playback_delay_ms) + "\n")
        self.last_delay = config.playback_delay_ms

    def close(self):
        for path in (self.path, self.delay):
            path.unlink(missing_ok=True)
