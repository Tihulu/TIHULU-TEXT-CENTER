"""On-demand Flight Radar overlay; optional local readsb and public ADSB.lol JSON.

This is a companion to, NOT a replacement for, Tihulu Flight Radar's
full tar1090 map, receiver controls, export, aircraft details and history.
No SDR open, polling on import, automatic network traffic or fictitious
positions. The Internet provider's ODbL attribution is always displayed.
"""
from __future__ import annotations
from datetime import datetime,timezone
import json
import math
import re
from threading import Lock
import time
import urllib.request

from .core import Store

MAX_JSON=1_400_000
MAX_AIRCRAFT=350
ONLINE_DELAY=30.0
SOURCE_URLS=(
    "http://127.0.0.1:8505/api/aircraft",
    "http://127.0.0.1:8080/data/aircraft.json",
    "http://127.0.0.1:8080/aircraft.json",
)
PROVIDER="https://api.adsb.lol"
ATTRIBUTION="Internet ADS-B data: adsb.lol · ODbL 1.0 (https://www.adsb.lol/)"


class RadarError(RuntimeError):
    pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        return None


def validate_area(lat,lon,radius):
    if type(lat) not in (int,float) or type(lon) not in (int,float) or type(radius) not in (int,float):
        raise ValueError("Invalid numeric radar position or radius")
    if not all(math.isfinite(x) for x in (lat,lon,radius)):
        raise ValueError("Radar coordinates must be finite")
    if not -90<=lat<=90 or not -180<=lon<=180 or not 1<=radius<=250:
        raise ValueError("Coordinates must be valid and radius 1–250 nautical miles")
    return round(lat,4),round(lon,4),int(radius)


def source_filter(value):
    if value not in ("antenna","internet","hybrid"):
        raise ValueError("Select Antenna, Internet or Hybrid")
    return value


def read_json(url,limit=MAX_JSON):
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),_NoRedirect())
    request=urllib.request.Request(url,headers={"Accept":"application/json","User-Agent":"TihuluTextCenter/0.6 (manual radar overlay)"},method="GET")
    try:
        with opener.open(request,timeout=3) as response:
            if response.status!=200:
                raise RadarError("Radar feed returned an unsuccessful status")
            raw=response.read(limit+1)
    except (OSError,ValueError) as exc:
        raise RadarError("Local radar or Internet provider unreachable") from exc
    if len(raw)>limit:
        raise RadarError("Radar response exceeds size limit")
    try:
        result=json.loads(raw)
    except (UnicodeError,ValueError) as exc:
        raise RadarError("Malformed radar data") from exc
    if not isinstance(result,dict):
        raise RadarError("Radar response must be a JSON object")
    return result


def parse_aircraft(obj,source):
    if source not in ("antenna","internet"):
        raise ValueError("Invalid aircraft source")
    raw=obj.get("aircraft") if source=="antenna" else obj.get("ac")
    if not isinstance(raw,list):
        raise RadarError("Decoder returned no recognized aircraft list")
    result=[]
    for row in raw[:MAX_AIRCRAFT*2]:
        if not isinstance(row,dict):continue
        hx=row.get("hex")
        if not isinstance(hx,str) or not re.fullmatch(r"[0-9a-fA-F]{6}",hx):
            continue
        age=row.get("seen")
        if type(age) not in (int,float) or not math.isfinite(age) or not 0<=age<=90:
            continue
        lat,lon=row.get("lat"),row.get("lon")
        seen_pos=row.get("seen_pos",age)
        valid=(type(lat) in (int,float) and type(lon) in (int,float) and
               type(seen_pos) in (int,float) and
               all(math.isfinite(x) for x in (lat,lon,seen_pos)) and
               -90<=lat<=90 and -180<=lon<=180 and 0<=seen_pos<=90)
        gs=row.get("gs")
        altitude=row.get("alt_baro")
        flight=row.get("flight") if isinstance(row.get("flight"),str) else ""
        result.append({
            "hex":hx.lower(),"flight":flight.strip()[:16],
            "lat":round(lat,5) if valid else None,
            "lon":round(lon,5) if valid else None,
            "positioned":valid,
            "alt_baro":altitude if type(altitude) in (int,float) and math.isfinite(altitude) else None,
            "gs":round(gs,1) if type(gs) in (int,float) and math.isfinite(gs) else None,
            "age_seconds":round(age,1),
            "sources":[source],"position_source":source if valid else None,
            "stale":False,
        })
        if len(result)>=MAX_AIRCRAFT:break
    return result


def combine_aircraft(local,remote):
    result={r["hex"]:dict(r) for r in remote}
    for row in local:
        key=row["hex"]
        if key not in result:
            result[key]=dict(row)
        else:
            existing=result[key]
            # Prefer real nearby antenna observations for equal/fresher age.
            if row.get("stale") and not existing.get("stale"):
                winner=dict(existing)
            elif existing.get("stale") and not row.get("stale"):
                winner=dict(row)
            elif row["positioned"] and (not existing["positioned"] or
                row["age_seconds"]<=existing["age_seconds"]+5):
                winner=dict(row)
            else:
                winner=dict(existing)
            winner["sources"]=["antenna","internet"]
            winner["source_freshness"]={
                "antenna":"cached" if row.get("stale") else "live",
                "internet":"cached" if existing.get("stale") else "live",
            }
            winner["position_source"]=winner.get("position_source")
            result[key]=winner
    return sorted(result.values(),key=lambda r:(not r["positioned"],r["age_seconds"]))[:MAX_AIRCRAFT]


class RadarOverlay:
    def __init__(self,store:Store,*,fetcher=None,time_fn=None):
        self.store=store
        self.fetcher=fetcher or read_json
        self.time_fn=time_fn or time.monotonic
        self._mutex=Lock()
        self._last_online_time=-1_000_000.0
        self._cached_online=None
        with store.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS radar_sources(
                source TEXT PRIMARY KEY, collected_at TEXT NOT NULL,
                aircraft_json TEXT NOT NULL)""")

    def _cache(self,source,rows):
        safe=json.dumps(rows,ensure_ascii=False)
        if len(safe)>400_000:return
        with self.store.connect() as db:
            db.execute("""INSERT INTO radar_sources(source,collected_at,aircraft_json)
                VALUES(?,?,?) ON CONFLICT(source) DO UPDATE SET
                collected_at=excluded.collected_at,aircraft_json=excluded.aircraft_json""",
                (source,datetime.now(timezone.utc).isoformat(timespec="seconds"),safe))

    def status(self):
        with self.store.connect() as db:
            rows=db.execute("SELECT source,collected_at,aircraft_json FROM radar_sources").fetchall()
        return {"cache":[{
            "source":r["source"],"collected_at":r["collected_at"],
            "aircraft_count":len(json.loads(r["aircraft_json"]))
        } for r in rows],"automatic_polling":False,
        "providers":["local Tihulu Flight Radar/readsb", "adsb.lol (ODbL)"],
        "full_map":"Independent full tar1090 map remains in Tihulu Flight Radar",
        "attribution":ATTRIBUTION}

    def _offline(self,source):
        with self.store.connect() as db:
            row=db.execute("SELECT collected_at,aircraft_json FROM radar_sources WHERE source=?",(source,)).fetchone()
        if not row:return [],None
        try:records=json.loads(row["aircraft_json"])
        except ValueError:return [],None
        if not isinstance(records,list):return [],None
        return [{**r,"stale":True} for r in records[:MAX_AIRCRAFT]],row["collected_at"]

    def refresh(self,*,mode,lat=51.1657,lon=10.4515,radius=150):
        mode=source_filter(mode)
        lat,lon,radius=validate_area(lat,lon,radius)
        local,remote=[],[]
        status={}
        if mode in ("antenna","hybrid"):
            for url in SOURCE_URLS:
                try:
                    local=parse_aircraft(self.fetcher(url),"antenna")
                    status["antenna"]={"status":"live","endpoint":url}
                    self._cache("antenna",local)
                    break
                except (RadarError,OSError,ValueError):
                    pass
            else:
                local,when=self._offline("antenna")
                status["antenna"]={"status":"cached" if when else "unavailable",
                                   "collected_at":when}
        if mode in ("internet","hybrid"):
            with self._mutex:
                now=self.time_fn()
                if now-self._last_online_time<ONLINE_DELAY:
                    ready=False
                else:
                    self._last_online_time=now
                    ready=True
            if ready:
                url=f"{PROVIDER}/v2/point/{lat}/{lon}/{radius}"
                try:
                    remote=parse_aircraft(self.fetcher(url),"internet")
                    status["internet"]={"status":"live","provider":"adsb.lol"}
                    self._cache("internet",remote)
                except (RadarError,OSError,ValueError) as exc:
                    remote,when=self._offline("internet")
                    status["internet"]={"status":"cached" if when else "unavailable",
                                       "collected_at":when,"reason":str(exc)[:140]}
            else:
                remote,when=self._offline("internet")
                status["internet"]={"status":"cached" if when else "cooldown",
                                   "collected_at":when,
                                   "reason":"Internet provider limited to one request per 30 s"}
        aircraft=combine_aircraft(local,remote) if mode=="hybrid" else local if mode=="antenna" else remote
        return {
            "checked_at":datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "mode":mode,"area":{"lat":lat,"lon":lon,"radius_nm":radius},
            "aircraft":aircraft,"statuses":status,
            "antenna_count":len(local),"internet_count":len(remote),
            "with_position":sum(r["positioned"] for r in aircraft),
            "attribution":ATTRIBUTION,
            "cache_warning":"Cached aircraft are historical positions, NOT live traffic",
            "automatic_polling":False,
        }
