"""Unified, source-attributed FM/DAB/TV directory with editable local preferences.

Preferences NEVER overwrite decoder observations. An entry from a DVB scan is
not a playable TV stream until a separate authorized local relay is configured.
"""
from __future__ import annotations

from datetime import datetime,timezone
import re
from .core import Store,clean_text
from .channel_catalog import ChannelCatalog
from .live_tv import load_channels

_MEDIUMS=("fm","dab","tv")
_TV_HEADER=re.compile(r"^\[([^\]\r\n]{1,100})\]$")
_SAFE_PLAN=re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,119}$")


def parse_dvbv5_services(raw:str, *, scan_plan:str, adapter:int=0)->list[dict]:
    """Parse only actual dvbv5-scan output, not a guessed regional TV catalog."""
    if not isinstance(raw,str) or len(raw)>2_000_000 or not _SAFE_PLAN.fullmatch(scan_plan):
        raise ValueError("Invalid DVB service scan output or plan")
    if type(adapter) is not int or not 0<=adapter<=15:raise ValueError("Invalid adapter")
    services=[]
    section=None
    def flush():
        if not section:return
        props=section["props"]
        try:
            sid_text=props.get("SERVICE_ID","")
            sid=int(sid_text,16 if sid_text.lower().startswith("0x") else 10)
            hz=int(props.get("FREQUENCY",""),10)
        except (ValueError,TypeError):return
        if not 1<=sid<=65535 or not 40_000_000<=hz<=900_000_000:return
        system=props.get("DELIVERY_SYSTEM","").upper()
        if system not in ("DVBT","DVBT2"):return
        if "VIDEO_PID" not in props and "AUDIO_PID" not in props:return
        name=clean_text(section["name"],100)
        if not name:return
        ident=f"tv:dvbt:{adapter}:{hz}:{sid}"
        services.append({"id":ident,"name":name,"frequency_hz":hz,
            "service_id":sid,"delivery_system":system,
            "adapter":adapter,"scan_plan":scan_plan})
    for line in raw.splitlines():
        line=line.strip()
        if not line or line.startswith("#"):continue
        m=_TV_HEADER.fullmatch(line)
        if m:
            flush()
            section={"name":m.group(1),"props":{}}
        elif section and "=" in line:
            key,val=line.split("=",1)
            key=key.strip().upper()
            if key in ("SERVICE_ID","FREQUENCY","DELIVERY_SYSTEM","VIDEO_PID","AUDIO_PID"):
                section["props"][key]=val.strip()
    flush()
    return list({s["id"]:s for s in services[:500]}.values())


class ChannelCenter:
    def __init__(self,store:Store):
        self.store=store
        self.verified=ChannelCatalog(store)
        with store.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS station_preferences(
                    id TEXT PRIMARY KEY,
                    display_name TEXT,
                    favorite INTEGER NOT NULL DEFAULT 0,
                    hidden INTEGER NOT NULL DEFAULT 0,
                    position INTEGER NOT NULL DEFAULT 500
                );
                CREATE TABLE IF NOT EXISTS discovered_tv_services(
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    frequency_hz INTEGER NOT NULL,
                    service_id INTEGER NOT NULL,
                    delivery_system TEXT NOT NULL,
                    adapter INTEGER NOT NULL,
                    scan_plan TEXT NOT NULL,
                    observed_at TEXT NOT NULL
                );
            """)

    def ingest_tv_scan(self,raw:str, *, scan_plan:str, adapter:int=0)->int:
        rows=parse_dvbv5_services(raw,scan_plan=scan_plan,adapter=adapter)
        if not rows:return 0
        now=datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self.store.connect() as db:
            for item in rows:
                db.execute("""INSERT INTO discovered_tv_services
                    (id,name,frequency_hz,service_id,delivery_system,adapter,scan_plan,observed_at)
                    VALUES(?,?,?,?,?,?,?,?)
                    ON CONFLICT(id) DO UPDATE SET name=excluded.name,
                    delivery_system=excluded.delivery_system,
                    observed_at=excluded.observed_at""",
                    (item["id"],item["name"],item["frequency_hz"],item["service_id"],
                    item["delivery_system"],item["adapter"],item["scan_plan"],now))
        return len(rows)

    def list(self, *, medium:str|None=None, include_hidden:bool=False,
             tv_channels:list[dict]|None=None)->list[dict]:
        if medium is not None and medium not in _MEDIUMS:
            raise ValueError("Unknown channel medium")
        channels=[]
        if medium in (None,"fm","dab"):
            for st in self.verified.list(medium=medium):
                channels.append({
                    "id":st["id"],"medium":st["medium"],"name":st["name"],
                    "frequency_hz":st["frequency_hz"],"channel":st["channel"],
                    "service_id":st["service_id"],"ensemble":st["ensemble"],
                    "audio_advertised":bool(st["audio_advertised"]),
                    "source":"verified_decoder","observed_at":st["observed_at"],
                    "last_text":st["last_text"],
                    "playable":bool(st["audio_advertised"]),
                    "playback_note":"Tune explicitly; actual RF reception depends on current antenna and available decoder",
                })
        if medium in (None,"tv"):
            for configured in (tv_channels if tv_channels is not None else load_channels()):
                channels.append({
                    "id":"tvstream:"+configured["id"],"medium":"tv",
                    "name":configured["name"],"frequency_hz":None,
                    "channel":None,"service_id":None,"ensemble":None,
                    "audio_advertised":False,"source":"operator_configured_stream",
                    "observed_at":None,"last_text":None,"playable":True,
                    "playback_note":"Authorized local MPEG-TS relay, NOT automatically verified DVB RF reception",
                    "tv_channel_id":configured["id"],
                })
            with self.store.connect() as db:
                scanned=db.execute("""SELECT * FROM discovered_tv_services
                    ORDER BY observed_at DESC,name LIMIT 500""").fetchall()
            for st in scanned:
                channels.append({
                    "id":st["id"],"medium":"tv","name":st["name"],
                    "frequency_hz":st["frequency_hz"],"channel":None,
                    "service_id":st["service_id"],"ensemble":None,
                    "audio_advertised":False,"source":"verified_dvb_scan",
                    "observed_at":st["observed_at"],"last_text":None,
                    "playable":False,"playback_note":"DVB service detected; an authorized tuner/TS relay is still needed for playback",
                    "delivery_system":st["delivery_system"],"scan_plan":st["scan_plan"],
                })
        with self.store.connect() as db:
            preferences={
                r["id"]:dict(r)
                for r in db.execute("SELECT * FROM station_preferences").fetchall()
            }
        for row in channels:
            p=preferences.get(row["id"],{})
            row["display_name"]=p.get("display_name") or row["name"]
            row["favorite"]=bool(p.get("favorite",0))
            row["hidden"]=bool(p.get("hidden",0))
            row["position"]=p.get("position",500)
        channels=[r for r in channels if include_hidden or not r["hidden"]]
        channels.sort(key=lambda x:(not x["favorite"],x["position"],x["display_name"].casefold(),x["id"]))
        return channels

    def update(self, *, id:str, display_name=None, favorite=None, hidden=None,
               position=None, tv_channels:list[dict]|None=None):
        if not isinstance(id,str) or len(id)>160:
            raise ValueError("Invalid channel identifier")
        channels=self.list(include_hidden=True,tv_channels=tv_channels)
        current=next((x for x in channels if x["id"]==id),None)
        if current is None:raise KeyError("Only discovered or configured channels may be edited")
        if display_name is not None:
            if not isinstance(display_name,str) or not display_name.strip() or len(display_name)>100:
                raise ValueError("Invalid channel display name")
            display_name=clean_text(display_name,100)
        if favorite is not None and type(favorite) is not bool:raise ValueError("favorite must be Boolean")
        if hidden is not None and type(hidden) is not bool:raise ValueError("hidden must be Boolean")
        if position is not None and (type(position) is not int or not 0<=position<=9999):
            raise ValueError("Invalid channel order")
        if all(x is None for x in (display_name,favorite,hidden,position)):
            raise ValueError("No channel preference supplied")
        with self.store.connect() as db:
            db.execute("""INSERT OR IGNORE INTO station_preferences
                (id,display_name,favorite,hidden,position) VALUES(?,NULL,0,0,500)""",(id,))
            old=db.execute("SELECT * FROM station_preferences WHERE id=?",(id,)).fetchone()
            db.execute("""UPDATE station_preferences
                SET display_name=?,favorite=?,hidden=?,position=? WHERE id=?""",
                (display_name if display_name is not None else old["display_name"],
                 int(favorite) if favorite is not None else old["favorite"],
                 int(hidden) if hidden is not None else old["hidden"],
                 position if position is not None else old["position"],id))
        return next(x for x in self.list(include_hidden=True,tv_channels=tv_channels) if x["id"]==id)
