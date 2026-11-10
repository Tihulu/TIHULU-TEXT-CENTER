"""Optional sound-event tags alongside, never instead of, actual subtitles.

Tags are based only on installed, opt-in acoustic classifier evidence. They
are display decorations applied AFTER ASR, sentence assembly and translation;
they never enter Whisper prompts, translation inputs or diarization. Unknown
or stale events stay hidden, preserving original speech.
"""
from __future__ import annotations

LABELS = {
    "en": {"music": "Music", "hum": "Humming", "applause": "Applause",
           "laughter": "Laughter", "noise": "Noise"},
    "de": {"music": "Musik", "hum": "Summen", "applause": "Applaus",
           "laughter": "Lachen", "noise": "Geräusch"},
    "tr": {"music": "Müzik", "hum": "Mırıldanma", "applause": "Alkış",
           "laughter": "Gülme", "noise": "Gürültü"},
    "fr": {"music": "Musique", "hum": "Fredonnement", "applause": "Applaudissements",
           "laughter": "Rires", "noise": "Bruit"},
}
VALID = frozenset(LABELS["en"])


def sound_prefix(events, language: str = "en") -> str:
    if not isinstance(events, list):
        return ""
    dictionary = LABELS.get(str(language or "en").lower(), LABELS["en"])
    names = []
    for row in events[:5]:
        if not isinstance(row, dict):
            continue
        kind, confidence = row.get("type"), row.get("confidence")
        if (kind not in VALID or
            type(confidence) not in (float, int) or
            not .80 <= confidence <= 1.0 or
            row.get("source") != "AST AudioSet" or kind in names):
            continue
        names.append(kind)
        if len(names) == 2:
            break
    return " ".join("[" + dictionary[kind] + "]" for kind in names)


def decorate_caption(text: str, events, language: str) -> str:
    """Never replace, truncate, translate or remove genuine recognized words."""
    if not isinstance(text, str):
        return ""
    prefix=sound_prefix(events, language)
    if not prefix:
        return text
    return prefix + (" " + text if text else "")


def decorate_result(result: dict, enabled: bool) -> dict:
    """Produce a separate display copy, leaving raw ASR and translations intact."""
    if not isinstance(result, dict):
        raise ValueError("Expected caption result object")
    output=dict(result)
    if not enabled:
        return output
    events=result.get("sound_events") or []
    if not events:
        return output
    original=result.get("original","")
    output["original"]=decorate_caption(
        original,events,result.get("source_language","en"))
    output["translations"]={
        lang:decorate_caption(line,events,lang)
        for lang,line in (result.get("translations") or {}).items()
    }
    # UI status can still explain which detector produced the label; this
    # metadata never claims sample-accurate event boundaries.
    output["sound_labels_source"]="AST AudioSet · approximate clip"
    return output
