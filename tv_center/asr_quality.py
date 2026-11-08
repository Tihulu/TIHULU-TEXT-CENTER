# SPDX-License-Identifier: GPL-2.0-or-later
"""Conservative post-decode quality gate for optional live-TV Whisper captions.

Do not turn music, silence, corrupted RF audio or short low-confidence guesses
into translated subtitles. Real words with credible confidence still pass.
This only filters model output and does not edit the broadcast transport.
"""
from __future__ import annotations
import re


def _number(field, value, default):
    try:
        return float(value if value is not None else default)
    except (ValueError, TypeError, OverflowError):
        return default


def accepted_whisper_segments(
    segments, *, source_language="auto", detected_probability=None,
    music_mode=False,
):
    """Return (accepted segments, suppression reason or None).

    Whisper confidence is heuristic, not a certainty of transcription.
    Short captions are rejected only with additional measurable concerns.
    """
    if source_language == "auto" and detected_probability is not None:
        confidence = _number("lang", detected_probability, 0.0)
        if confidence < 0.50:
            return [], "uncertain_auto_detect_language"

    accepted = []
    reasons = []
    for segment in segments:
        text = str(getattr(segment, "text", "") or "").strip()
        if not text:
            continue
        tokens = text.split()
        no_speech = _number("no_speech", getattr(segment, "no_speech_prob", 0.), 0.)
        logprob = _number("logprob", getattr(segment, "avg_logprob", 0.), 0.)
        compression = _number("compression", getattr(segment, "compression_ratio", 0.), 0.)
        start = _number("start", getattr(segment, "start", 0.), 0.)
        end = _number("end", getattr(segment, "end", start), start)
        duration = max(0., end - start)
        reason = None
        if no_speech >= (0.87 if music_mode else 0.65) or (
                not music_mode and no_speech >= 0.43 and logprob < -0.35):
            reason = "probable_silence_or_background_audio"
        elif logprob < -1.0:
            reason = "low_ASR_confidence"
        elif compression > 2.8:
            reason = "repetitive_ASR_hallucination"
        elif (not music_mode and len(tokens) <= 3 and duration < 1.1
              and (no_speech > 0.18 or logprob < -0.40)):
            reason = "unverified_short_phrase"
        elif (not music_mode and len(tokens) <= 3
              and sum(c.isdigit() for c in text) >= 2
              and (no_speech > 0.12 or logprob < -0.35
                   or duration < 1.3)):
            # Broadcast logos, clipped years and jingles are common
            # hallucination patterns. An explicit long, confident spoken
            # year may still pass.
            reason = "unverified_short_numeric_phrase"
        if reason:
            reasons.append(reason)
        else:
            accepted.append(segment)
    return accepted, (None if accepted else
                      reasons[0] if reasons else "no_speech_detected")
