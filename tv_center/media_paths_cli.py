"""Read-only Media storage inspection and explicitly requested path settings.

Legacy discovery never reads secret values, copies, moves or deletes files.
Config changes require --set-* and affect future Media operations only.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

from .ai_settings import AISettings
from .paths import discover_legacy, media_paths, validate_storage_directory, APP_ID


def _validate_user_folder(raw: str) -> str:
    return str(validate_storage_directory(raw))


def main(argv=None):
    parser = argparse.ArgumentParser(description="TIHULU Media storage and legacy discovery")
    parser.add_argument("--discover-legacy", action="store_true",
                        help="read-only metadata; no secrets/models opened")
    parser.add_argument("--set-model-dir", metavar="ABSOLUTE_PATH")
    parser.add_argument("--set-cache-dir", metavar="ABSOLUTE_PATH")
    parser.add_argument("--set-recording-dir", metavar="ABSOLUTE_PATH")
    args = parser.parse_args(argv)
    config = AISettings()
    patch = {}
    for field, raw in (("model_dir", args.set_model_dir),
                       ("cache_dir", args.set_cache_dir),
                       ("recording_dir", args.set_recording_dir)):
        if raw is not None:
            try:
                patch[field] = _validate_user_folder(raw)
            except ValueError as exc:
                parser.error(str(exc))
    if patch:
        config.update(patch, persist=True)
    paths = media_paths()
    answer = {
        "app": APP_ID,
        "settings": str(config.path),
        "models": str(paths.model_root(config.values["model_dir"])),
        "cache": str(paths.cache_root(config.values["cache_dir"])),
        "recordings": str(paths.recordings_root(config.values["recording_dir"])),
        "data": str(paths.data),
        "runtime": str(paths.runtime),
        "wrote_settings": bool(patch),
        "legacy_discovered": discover_legacy() if args.discover_legacy else [],
        "legacy_auto_migrated": False,
    }
    print(json.dumps(answer, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
