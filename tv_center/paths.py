"""Independent, non-destructive Media Center storage and legacy discovery.

No directory is created and no file is moved, loaded or removed on import.
Paths are XDG-aware on Linux, with platform user-home defaults elsewhere.
Old app settings/weights remain untouched and are never auto-migrated.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import stat


APP_ID = ("tihulu-media-standalone" if os.environ.get("TIHULU_MEDIA_STANDALONE") == "1" else "tihulu-media-center")


def _base(env_name: str, fallback: Path) -> Path:
    raw = os.environ.get(env_name, "").strip()
    return (Path(raw).expanduser() if raw and Path(raw).expanduser().is_absolute()
            else fallback).resolve(strict=False)


def validate_storage_directory(raw: str | Path) -> Path:
    """Reject root, relative paths, symlinked leaves or ancestors, without writes.

    A separately chosen external SSD mount may be used by path, but this
    validation never assigns ownership or grants model deletion permission.
    """
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute() or candidate == Path(candidate.anchor):
        raise ValueError("Choose an absolute, non-root user storage directory")
    current = Path(candidate.anchor)
    for part in candidate.parts[1:]:
        current = current / part
        try:
            info = current.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise ValueError("Storage directory cannot be inspected safely") from exc
        if stat.S_ISLNK(info.st_mode):
            raise ValueError("Refusing a symlink in the selected directory or parent")
        if not stat.S_ISDIR(info.st_mode):
            raise ValueError("Storage path contains a non-directory ancestor")
    return candidate


def _override(env_name: str, default: Path) -> Path:
    raw = os.environ.get(env_name, "").strip()
    if not raw:
        return default
    try:
        return validate_storage_directory(raw)
    except ValueError as exc:
        raise ValueError(env_name + ": " + str(exc)) from exc


@dataclass(frozen=True)
class MediaPaths:
    config: Path
    data: Path
    cache: Path
    state: Path
    runtime: Path
    recordings: Path

    @property
    def models(self) -> Path:
        return self.data / "models"

    @property
    def ai_settings(self) -> Path:
        return self.config / "ai-settings.json"

    @property
    def transcripts(self) -> Path:
        return self.data / "transcripts.sqlite3"

    def model_root(self, configured: str = "") -> Path:
        return _override("TIHULU_MEDIA_MODELS", (
            Path(configured).expanduser() if configured else self.models))

    def cache_root(self, configured: str = "") -> Path:
        return _override("TIHULU_MEDIA_CACHE", (
            Path(configured).expanduser() if configured else self.cache))

    def recordings_root(self, configured: str = "") -> Path:
        return _override("TIHULU_MEDIA_RECORDINGS", (
            Path(configured).expanduser() if configured else self.recordings))


def media_paths() -> MediaPaths:
    home = Path.home()
    config = _base("XDG_CONFIG_HOME", home / ".config") / APP_ID
    data = _base("XDG_DATA_HOME", home / ".local/share") / APP_ID
    cache = _base("XDG_CACHE_HOME", home / ".cache") / APP_ID
    state = _base("XDG_STATE_HOME", home / ".local/state") / APP_ID
    runtime = _base("XDG_RUNTIME_DIR", cache / "runtime") / APP_ID
    recordings = home / "Videos" / ("TIHULU Standalone Recordings" if APP_ID == "tihulu-media-standalone" else "TIHULU Recordings")
    return MediaPaths(config, data, cache, state, runtime, recordings)


def discover_legacy() -> list[dict]:
    """Read-only path metadata for a user-approved migration preview.

    No symlink is traversed, no secret bytes are read, and no destination
    directory is created. Unowned/unrecognized files are not adopted.
    """
    home = Path.home()
    names = (
        ".config/tihulu-tv-center/ai-settings.json",
        ".config/tihulu-tv-center/channels.conf",
        ".config/tihulu-tv-center/remote-gpu-token",
        ".config/tihulu-tv-center/deepl-api.key",
        ".local/share/tihulu-tv-center/models",
        ".local/share/tihulu-tv-center/translator-models",
        ".local/share/tihulu-tv-center/faster-whisper-models",
        ".local/share/tihulu-tv-center/ai-runtime",
        ".local/share/tihulu-tv-center/whisper-runtime",
        ".local/share/tihulu-tv-center/cuda-faster-whisper",
        ".local/share/tihulu-tv-center/speaker-resemblyzer",
        ".local/share/tihulu-tv-center/audio-label-classifiers",
        ".local/share/tihulu-tv-center/qwen-aligner",
        ".local/share/tihulu-tv-center/overlap-separation",
        ".local/share/tihulu-kaffeine",
        ".local/opt/tihulu-kaffeine",
        ".config/tihulu-media-centerrc",
        ".local/share/tihulu-media-center",
    )
    items = []
    for name in names:
        path = home / name
        # lstat() of the leaf alone follows symlinks in intermediate
        # directories. Never inspect any foreign child through those links.
        parent = home
        unsafe_parent = False
        for component in Path(name).parts[:-1]:
            parent = parent / component
            try:
                parent_entry = parent.lstat()
            except FileNotFoundError:
                break
            except OSError:
                unsafe_parent = True
                break
            if stat.S_ISLNK(parent_entry.st_mode):
                unsafe_parent = True
                break
        if unsafe_parent:
            items.append({"path": str(path), "type": "symlink-parent",
                          "action": "skip; no symlink traversal"})
            continue
        try:
            entry = path.lstat()
        except FileNotFoundError:
            continue
        except OSError:
            items.append({"path": str(path), "type": "unreadable", "action": "skip"})
            continue
        kind = ("symlink" if stat.S_ISLNK(entry.st_mode) else
                "directory" if stat.S_ISDIR(entry.st_mode) else
                "file" if stat.S_ISREG(entry.st_mode) else "other")
        items.append({
            "path": str(path), "type": kind, "bytes": entry.st_size,
            "action": "preserve; manual review" if kind in ("file", "directory")
                      else "skip; no symlink traversal",
        })
    return items
