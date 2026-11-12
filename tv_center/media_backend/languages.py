"""Whisper source-language vocabulary for Media Center; no model load on import."""
from __future__ import annotations

LANGUAGES = tuple("""
en zh de es ru ko fr ja pt tr pl ca nl ar sv it id hi fi vi he uk el ms cs ro da hu ta no th ur hr bg lt la mi ml cy sk te fa lv bn sr az sl kn et mk br eu is hy ne mn bs kk sq sw gl mr pa si km sn yo so af oc ka be tg sd gu am yi lo uz fo ht ps tk nn mt sa lb my bo tl mg as tt haw ln ha ba jw su yue
""".split())

def validate_language(value):
    if value not in LANGUAGES:
        raise ValueError("Not a language supported by the installed Whisper tokenizer")
    return value
