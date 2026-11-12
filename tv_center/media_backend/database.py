"""Media-only SQLite adapter for optional transcript persistence.

Does not import or mutate Text Center Store, feeds, news or Teletext tables.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import re
import sqlite3


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def clean_text(value: object, limit: int = 4000) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()[:limit]


class MediaTranscriptStore:
    def __init__(self, filename):
        self.filename = Path(filename).expanduser()

    def connect(self):
        self.filename.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        db = sqlite3.connect(self.filename, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db
