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
from collections import deque
from statistics import median
import json
import os
from pathlib import Path
import queue
import re
import tempfile
import time

MODE = ("auto", "teletext", "asr", "page", "off")
LANGS = ("de", "en", "tr", "fr")

@dataclass(frozen=True)
class CaptionConfig:
    mode: str = "auto"
    source: str = "de"
    target: str = "tr"
    target_languages: tuple[str, ...] = ("tr",)
    page: int = 150
    teletext_pid: int | None = None
    audio_pid: int | None = None
    offset_ms: int = 0
    playback_delay_ms: int = 0
    automatic_sync: bool = False
    on_video: bool = True
    show_original: bool = True
    show_translation: bool = True
    position: str = "bottom"
    font_px: int = 25
    opacity: int = 70
    text_opacity: int = 100
    revision: int = 0

    def validate(self):
        if self.mode not in MODE or self.source not in LANGS or self.target not in LANGS:
            raise ValueError("Unknown caption source or language")
        if type(self.page) is not int or not 100 <= self.page <= 899:
            raise ValueError("Teletext page must be an integer 100–899")
        if self.teletext_pid is not None and (
                type(self.teletext_pid) is not int or not 1 <= self.teletext_pid <= 8190):
            raise ValueError("Invalid broadcaster Teletext subtitle PID")
        if self.audio_pid is not None and (
                type(self.audio_pid) is not int or not 1 <= self.audio_pid <= 8190):
            raise ValueError("Invalid selected broadcaster audio PID")
        if type(self.offset_ms) is not int or not -10000 <= self.offset_ms <= 10000:
            raise ValueError("Caption offset must be -10 to +10 seconds")
        if type(self.playback_delay_ms) is not int or not 0 <= self.playback_delay_ms <= 20000:
            raise ValueError("Playback buffering must be 0–20 seconds")
        if (not isinstance(self.target_languages, tuple) or
                len(self.target_languages) > 3 or
                len(set(self.target_languages)) != len(self.target_languages) or
                any(lang not in LANGS or lang == self.source
                    for lang in self.target_languages)):
            raise ValueError("Translation languages must be distinct and differ from spoken language")
        if not self.show_original and (not self.show_translation or
                                       not self.target_languages):
            raise ValueError("Select transcript or at least one translation")
        if self.position not in ("bottom", "top"):
            raise ValueError("Unknown caption position")
        if type(self.font_px) is not int or not 16 <= self.font_px <= 44:
            raise ValueError("Font size must be 16–44 pixels")
        if type(self.opacity) is not int or not 0 <= self.opacity <= 100:
            raise ValueError("Background opacity must be 0–100%")
        if type(self.text_opacity) is not int or not 0 <= self.text_opacity <= 100:
            raise ValueError("Text opacity must be 0–100%")
        for key in ("automatic_sync", "on_video", "show_original", "show_translation"):
            if type(getattr(self, key)) is not bool:
                raise ValueError("Caption display toggles must be boolean")
        return self

    def options(self):
        return {"mode":self.mode,"source":self.source,
                "target":self.target,"targets":self.target_languages,
                "page":self.page,"teletext_pid":self.teletext_pid,
                "audio_pid":self.audio_pid,"revision":self.revision}

    def render(self, result):
        """Produce independently selectable original/translated subtitle lines."""
        original = (result.get("original") or "").strip()
        raw = result.get("translations")
        translated = raw if isinstance(raw, dict) else {}
        lines = []
        if self.show_original and original:
            prefix = (f"[{self.source.upper()}] " if
                      self.show_translation and self.target_languages and translated else "")
            lines.append(prefix + original)
        if self.show_translation:
            if translated:
                for language in self.target_languages:
                    phrase = translated.get(language)
                    if isinstance(phrase, str) and phrase.strip() and phrase.strip() != original:
                        lines.append(f"[{language.upper()}] " + phrase.strip())
            else:
                legacy = (result.get("translated") or "").strip()
                if legacy and legacy != original:
                    lines.append(legacy)
        return "\n".join(lines)[:1100]

def effective_cue_config(config: CaptionConfig, native_status: dict | None) -> CaptionConfig:
    """Use the delay Kaffeine actually applies, not a requested but capped delay.

    Kaffeine's 64-MiB DVB buffer can temporarily shrink for high-bitrate
    services, timeshift, or recovery. A fresh status is already checked by
    KaffeineOSD.read_effective_delay(). Reject a status from an older
    user request: the C++ player may not have processed Apply yet.
    This is best effort; libVLC's own output latency is not measured.
    """
    if (not isinstance(native_status, dict) or
            type(native_status.get("requested_ms")) is not int or
            native_status["requested_ms"] != config.playback_delay_ms):
        return config
    actual = native_status.get("effective_ms")
    if type(actual) is not int or not 0 <= actual <= config.playback_delay_ms:
        return config
    return replace(config, playback_delay_ms=actual)


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


@dataclass(frozen=True)
class SyncRecommendation:
    """Coarse caption-availability timing, *not* word-aligned lip sync."""
    samples: int
    observed_lag_ms: int
    safe_min_ms: int
    safe_max_ms: int
    suggested_delay_ms: int
    safety_cap_ms: int
    saturated: bool

    @property
    def summary(self):
        band = f"{self.safe_min_ms / 1000:.1f}–{self.safe_max_ms / 1000:.1f} s"
        suffix = (" · processing exceeds safe TV buffer; late text is possible"
                  if self.saturated else "")
        return (f"Estimated caption availability lag: "
                f"{self.observed_lag_ms / 1000:.1f} s · "
                f"safe playback delay: {band} · "
                f"suggested: {self.suggested_delay_ms / 1000:.1f} s "
                f"({self.samples} live ASR samples){suffix}")


class AutoSyncEstimator:
    """Measure real Whisper+translation completion vs sampled DVB timeline.

    The spoken-word start inside a multi-second chunk is unknown. This only
    estimates *when the caption becomes available*, not the precise phoneme
    offset. Native Teletext captions should not train an ASR estimate.
    """
    def __init__(self, minimum=3, maximum=12, ceiling_ms=6000):
        if not 1 <= minimum <= maximum or not 0 <= ceiling_ms <= 20000:
            raise ValueError("Invalid automatic sync limits")
        self.minimum = minimum
        self.ceiling_ms = ceiling_ms
        self.values = deque(maxlen=maximum)

    def clear(self):
        self.values.clear()

    def observe(self, captured_start, captured_end, decoded_at, source):
        if source != "local_asr":
            return False
        try:
            start = float(captured_start)
            end = float(captured_end)
            done = float(decoded_at)
        except (TypeError, ValueError):
            return False
        # Unrealistic or discontinuous segment durations must not teach
        # automatic buffering or silently adjust a live DVB player.
        if not 0.5 <= end - start <= 12 or not end <= done <= end + 30:
            return False
        self.values.append(round((done - start) * 1000))
        return True

    def recommend(self, *, bytes_per_second=None, platform_cap_ms=None):
        if len(self.values) < self.minimum:
            return None
        cap = self.ceiling_ms
        if platform_cap_ms is not None:
            cap = min(cap, max(0, int(platform_cap_ms)))
        # Native delayed MPEG-TS queue is capped at 64 MiB; reserve 16 MiB
        # for bursts/other TV buffers. The byte-rate is a coarse estimate.
        if bytes_per_second is not None and bytes_per_second > 0:
            cap = min(cap, max(0, int(48 * 1024 * 1024 * 1000 /
                                       float(bytes_per_second))))
        cap = max(0, min(20000, (cap // 500) * 500))
        ordered = sorted(self.values)
        med = int(median(ordered))
        p80 = ordered[int(round(0.8 * (len(ordered) - 1)))]
        def up500(value):
            return max(0, ((max(0, int(value)) + 499) // 500) * 500)
        lower = min(cap, up500(med + 250))
        upper = min(cap, max(lower, up500(p80 + 850)))
        suggested = min(cap, max(lower, up500(p80 + 350)))
        return SyncRecommendation(
            samples=len(ordered), observed_lag_ms=med,
            safe_min_ms=lower, safe_max_ms=upper,
            suggested_delay_ms=suggested, safety_cap_ms=cap,
            saturated=(p80 + 350 > cap),
        )


class AutoSyncController:
    """Keep live playback stable: opt-in + initial settle + slow adjustments.

    A user-specified caption offset remains manual fine-tuning because chunk
    timestamps do not identify individual words in a sentence.
    """
    def __init__(self, cooldown_seconds=30, deadband_ms=750, step_ms=500):
        self.cooldown_seconds = cooldown_seconds
        self.deadband_ms = deadband_ms
        self.step_ms = step_ms
        self.last_change_at = None
        self.has_applied = False

    def reset(self):
        self.last_change_at = None
        self.has_applied = False

    def next_delay(self, recommendation, current_ms, now, enabled):
        if not enabled or recommendation is None:
            return None
        desired = recommendation.suggested_delay_ms
        if not self.has_applied:
            self.has_applied = True
            self.last_change_at = now
            return desired if desired != current_ms else None
        if self.last_change_at is not None and (
                now - self.last_change_at < self.cooldown_seconds):
            return None
        if abs(desired - current_ms) < self.deadband_ms:
            return None
        delta = max(-self.step_ms, min(self.step_ms, desired - current_ms))
        next_ms = max(0, min(recommendation.safety_cap_ms,
                             round((current_ms + delta) / 500) * 500))
        if next_ms == current_ms:
            return None
        self.last_change_at = now
        return next_ms


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
        self.effective = runtime / f"tihulu-playback-effective-{pid}.txt"
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
               "text_opacity":config.text_opacity,
               "enabled":bool(config.on_video and config.mode != "off"),
               "expires_ms":int(time.time()*1000) + min(max(int(ttl_ms),0),15000)}
        self._atomic(self.path, json.dumps(obj,ensure_ascii=False,separators=(",",":")))

    def set_playback_delay(self, config: CaptionConfig):
        config.validate()
        self._atomic(self.delay, str(config.playback_delay_ms) + "\n")
        self.last_delay = config.playback_delay_ms

    def read_effective_delay(self):
        """Native Kaffeine reports its queue setting, not end-to-end VLC delay.

        Return None if the player has not reported recently; never claim the
        user-requested number is the *actual* delayed broadcast.
        """
        try:
            info = self.effective.stat()
            if not info.st_uid == os.getuid() or time.time()-info.st_mtime > 3.5:
                return None
            if info.st_size > 120 or info.st_size < 3:
                return None
            requested, actual, bps = map(int, self.effective.read_text().split())
            if (not 0 <= requested <= 20000 or not 0 <= actual <= requested or
                    not 0 <= bps <= 500_000_000):
                return None
            return {"requested_ms": requested, "effective_ms": actual,
                    "ts_bytes_per_second": bps,
                    "capped": actual < requested}
        except (OSError, ValueError, UnicodeError):
            return None

    def close(self):
        for path in (self.path, self.delay):
            path.unlink(missing_ok=True)
