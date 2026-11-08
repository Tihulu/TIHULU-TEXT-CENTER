# SPDX-License-Identifier: GPL-2.0-or-later
"""Offline output-language catalog for the native Kaffeine subtitle picker.

Only languages actually supplied by on-device Argos packages or a provisioned
NLLB model are advertised. No network/catalog update and no model download.
A present NLLB model is labelled unverified until real translation is tested.
"""
from __future__ import annotations

import json
import subprocess
from .language_codes import language_code

NAMES = {
    "de":"German", "en":"English", "tr":"Turkish", "fr":"French",
    "es":"Spanish", "it":"Italian", "nl":"Dutch", "pl":"Polish",
    "pt":"Portuguese", "ru":"Russian", "uk":"Ukrainian", "ar":"Arabic",
    "ja":"Japanese", "ko":"Korean", "zh":"Chinese", "hi":"Hindi",
    "sv":"Swedish", "da":"Danish", "fi":"Finnish", "el":"Greek",
    "cs":"Czech", "ro":"Romanian", "hu":"Hungarian", "bg":"Bulgarian",
}

def catalog(*, installed_pairs=None, nllb_installed=None,
            madlad_installed=None):
    errors = []
    if installed_pairs is None:
        try:
            from .argos_market_bridge import run
            # PyTorch/Argos cold imports can block for up to a minute in
            # the normal Model Market. A caption language menu must not.
            # This is a read-only, local probe with a strict short deadline.
            installed_pairs = run("installed", installed_timeout=8.0)
        except (OSError, RuntimeError, ValueError, KeyError,
                subprocess.TimeoutExpired) as exc:
            installed_pairs = []
            errors.append("Argos package discovery unavailable: "+str(exc)[:150])
    if nllb_installed is None:
        try:
            from .translation_market import TranslationModelMarket
            nllb_installed = bool(TranslationModelMarket().status()["installed"])
        except (OSError, RuntimeError, ValueError) as exc:
            nllb_installed = False
            errors.append("NLLB status unavailable: "+str(exc)[:120])
    if madlad_installed is None:
        try:
            from .translation_madlad import MadladMarket
            madlad_installed = bool(MadladMarket().status()["installed"])
        except (OSError, RuntimeError, ValueError) as exc:
            madlad_installed = False
            errors.append("MADLAD status unavailable: "+str(exc)[:120])
    destinations = {}
    for pair in installed_pairs:
        if not isinstance(pair, dict):
            continue
        try:
            source = language_code(pair.get("source", ""))
            target = language_code(pair.get("target", ""))
        except ValueError:
            continue
        if source != target:
            destinations.setdefault(target, set()).add("Argos")
    if nllb_installed:
        from .translation_market import LANG
        for code in LANG:
            destinations.setdefault(code, set()).add("NLLB (weights present)")
    if madlad_installed:
        # MADLAD is one multilingual checkpoint. The tokenizer must still
        # verify <2xx> targets at real inference time; installed weights
        # alone do not prove a working translation direction.
        for code in NAMES:
            destinations.setdefault(code, set()).add("MADLAD (weights present)")
    return {
        "languages":[{"code":code,"label":NAMES.get(code,code.upper()),
                      "engines":sorted(engines),
                      "verified_by_runtime":False}
                     for code,engines in sorted(
                         destinations.items(),
                         key=lambda pair:(pair[0] not in ("en","tr","de","fr"),
                                          pair[0]))],
        "installed_argos_pairs":len([
            x for x in installed_pairs if isinstance(x,dict)]),
        "nllb_present":bool(nllb_installed),
        "madlad_present":bool(madlad_installed),
        "errors":errors,
        "note":"A model package on disk does not prove translation for the current spoken language. No downloads.",
    }


def main():
    print(json.dumps(catalog(),ensure_ascii=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
