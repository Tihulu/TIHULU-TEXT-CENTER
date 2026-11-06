"""Locally retained, source-attributed station directory from actual decoder events.

Never populate this table from frequencies alone, an Internet station directory,
test fixture in production or a presumed broadcast. The entries are historical
observations, not an active channel lock or broadcast availability claim.
"""
from __future__ import annotations

from datetime import datetime, timezone
from .core import Store, clean_text


class ChannelCatalog:
    def __init__(self,store:Store):
        self.store=store
        with self.store.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS verified_stations(
                    id TEXT PRIMARY KEY, medium TEXT NOT NULL, frequency_hz INTEGER NOT NULL,
                    channel TEXT, service_id TEXT, name TEXT NOT NULL, ensemble TEXT,
                    decoder TEXT NOT NULL, observed_at TEXT NOT NULL,
                    audio_advertised INTEGER NOT NULL DEFAULT 0, last_text TEXT
                );
                CREATE INDEX IF NOT EXISTS station_medium_recent
                    ON verified_stations(medium, observed_at DESC);
            """)

    def save_fm(self,*,frequency_hz:int,name:str,last_text:str|None=None):
        if type(frequency_hz) is not int or not 87_500_000<=frequency_hz<=108_000_000:
            raise ValueError("Invalid confirmed FM frequency")
        name=clean_text(name,80)
        if not name or name.startswith("FM ") and name.endswith(" MHz"):
            raise ValueError("A real decoder station label is required")
        ident=f"fm:{frequency_hz}"
        data=(ident,"fm",frequency_hz,None,None,name,None,"rtl_fm_redsea",
              datetime.now(timezone.utc).isoformat(timespec="seconds"),1,
              clean_text(last_text,1000))
        self._store(data)

    def save_dab(self,*,channel:str,frequency_hz:int,service_id:str,
                 name:str,ensemble:str,audio_advertised:bool,last_text:str|None=None):
        from .dab_bridge import DAB_HZ
        if channel not in DAB_HZ or frequency_hz!=DAB_HZ[channel]:
            raise ValueError("Unknown DAB block or mismatched frequency")
        if not isinstance(service_id,str) or not service_id.startswith("0x") or not 4<=len(service_id)<=10:
            raise ValueError("Invalid decoder service identifier")
        name=clean_text(name,120)
        ensemble=clean_text(ensemble,120)
        if not name or not ensemble or name=="Unlabelled decoded service":
            raise ValueError("Only actual FIC-decoded stations may be saved")
        data=(f"dab:{channel}:{service_id.lower()}","dab",frequency_hz,
              channel,service_id.lower(),name,ensemble,"welle_cli_fic",
              datetime.now(timezone.utc).isoformat(timespec="seconds"),
              int(audio_advertised is True),clean_text(last_text,1000))
        self._store(data)

    def _store(self,data):
        with self.store.connect() as db:
            db.execute("""INSERT INTO verified_stations
                (id,medium,frequency_hz,channel,service_id,name,ensemble,
                 decoder,observed_at,audio_advertised,last_text)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET name=excluded.name,
                    ensemble=excluded.ensemble,decoder=excluded.decoder,
                    observed_at=excluded.observed_at,
                    audio_advertised=excluded.audio_advertised,
                    last_text=excluded.last_text""",data)
            db.execute("""DELETE FROM verified_stations WHERE id NOT IN
                (SELECT id FROM verified_stations
                 ORDER BY observed_at DESC,id LIMIT 800)""")

    def list(self,*,medium:str|None=None)->list[dict]:
        if medium not in (None,"fm","dab"):
            raise ValueError("Unknown station medium")
        with self.store.connect() as db:
            if medium:
                rows=db.execute("""SELECT * FROM verified_stations WHERE medium=?
                    ORDER BY observed_at DESC,name LIMIT 800""",(medium,)).fetchall()
            else:
                rows=db.execute("""SELECT * FROM verified_stations
                    ORDER BY observed_at DESC,name LIMIT 800""").fetchall()
        return [dict(r) for r in rows]
