"""Opt-in, purely local text language detection for installed language models.

No network access, no automatic model downloads, no speculative language labels.
"""
from __future__ import annotations
import importlib.util


class LanguageDetectionUnavailable(ValueError):
    pass


def text_detection_status():
    return {
        "ready": importlib.util.find_spec("langdetect") is not None,
        "engine": "langdetect (local package, no network)",
        "supported": ["en", "de", "tr"],
        "note": "Automatic text detection is available only if langdetect is installed locally; uncertain/unsupported labels are rejected.",
    }


def detect_text_language(text):
    if not isinstance(text,str) or not 20<=len(text.strip())<=12000:
        raise LanguageDetectionUnavailable("Auto Detect requires at least 20 characters of actual text")
    if not text_detection_status()["ready"]:
        raise LanguageDetectionUnavailable("Local langdetect package is not installed; choose the source language manually")
    try:
        from langdetect import DetectorFactory,detect_langs
        from langdetect.lang_detect_exception import LangDetectException
    except ImportError as exc:
        raise LanguageDetectionUnavailable("Local text detector is not importable") from exc
    try:
        DetectorFactory.seed=0
        guesses=detect_langs(text)
    except (ValueError,LangDetectException) as exc:
        raise LanguageDetectionUnavailable("Unable to detect source language reliably") from exc
    if not guesses or guesses[0].lang not in ("en","de","tr") or guesses[0].prob<0.80:
        raise LanguageDetectionUnavailable("Source language is unknown, unsupported or uncertain; choose manually")
    return guesses[0].lang,round(guesses[0].prob,3)
