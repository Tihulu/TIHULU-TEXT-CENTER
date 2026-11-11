"""Persist predicted satellite pass notes without reserving or touching SDR hardware.

Native Qt WebEngine runs an ephemeral browser profile, so browser localStorage
alone loses calendar notes on restart. This file is separate from the *armed*
RF scheduling store and contains no sample bytes, USB state or credentials.
"""
from __future__ import annotations
import json
import math
from pathlib import Path
from datetime import datetime, timezone, timedelta
from threading import RLock

_LOCK=RLock()
MAX=180
MAX_BYTES=150000

def _file(directory):
    return Path(directory)/"planning_candidates.json"

def load_candidates(directory):
    with _LOCK:
        file=_file(directory)
        try:
            if not file.is_file() or file.stat().st_size>MAX_BYTES:
                return []
            rows=json.loads(file.read_text(encoding="utf-8"))
            if not isinstance(rows,list):
                return []
            return [x for x in rows if isinstance(x,dict) and
                    x.get("status")=="planning-only" and
                    x.get("radioArmed") is False][-MAX:]
        except (OSError,ValueError,TypeError):
            return []

def validate_candidate(value,now=None):
    if not isinstance(value,dict):
        raise ValueError("Candidate must be a TLE-only calendar record")
    now=now or datetime.now(timezone.utc)
    try:
        norad=int(value.get("norad"))
        aos=int(value.get("aos"))
        los=int(value.get("los"))
        name=str(value.get("name","")).strip()[:96]
    except (TypeError,ValueError) as exc:
        raise ValueError("Invalid candidate NORAD, time or name") from exc
    if not 1<=norad<=999999 or not name or not 0<los-aos<=48*3600000:
        raise ValueError("Invalid orbital candidate window")
    if not now-timedelta(hours=2)<=datetime.fromtimestamp(aos/1000,timezone.utc)<=now+timedelta(days=45):
        raise ValueError("Candidate must be within 45 days of now")
    if value.get("status")!="planning-only" or value.get("radioArmed") is not False:
        raise ValueError("Candidate cannot arm any RF capture")
    observer=value.get("observer")
    if observer is not None:
        if not isinstance(observer,dict) or any(not isinstance(observer.get(k),(float,int)) or
            not math.isfinite(observer[k]) for k in ("lat","lon")) or not (
            -90<=observer["lat"]<=90 and -180<=observer["lon"]<=180):
            raise ValueError("Invalid observer coordinates")
        observer={"lat":float(observer["lat"]),"lon":float(observer["lon"])}
    return dict(id=f"{norad}_{aos//1000}",norad=norad,name=name,
                family=str(value.get("family","unknown"))[:30],
                aos=aos,los=los,observer=observer,
                status="planning-only",radioArmed=False,actualRecording=False,
                createdAt=int(value.get("createdAt") or now.timestamp()*1000),
                note="TLE-only calendar note. No receiver or RF job was armed.")

def _save(directory,rows):
    directory=Path(directory)
    directory.mkdir(parents=True,exist_ok=True)
    data=json.dumps(rows,ensure_ascii=False,separators=(",",":"))
    if len(data.encode("utf-8"))>MAX_BYTES:
        raise ValueError("Candidate calendar exceeds the storage limit")
    file=_file(directory)
    temporary=file.with_suffix(".tmp")
    temporary.write_text(data,encoding="utf-8")
    temporary.replace(file)
    return rows

def add_candidate(directory,value,now=None):
    with _LOCK:
        record=validate_candidate(value,now)
        rows=[x for x in load_candidates(directory) if x.get("id")!=record["id"]]
        rows.append(record)
        return _save(directory,sorted(rows,key=lambda x:x["aos"])[-MAX:])

def remove_candidate(directory,identifier):
    if not isinstance(identifier,str) or len(identifier)>40:
        raise ValueError("Invalid candidate identifier")
    with _LOCK:
        rows=[x for x in load_candidates(directory) if x.get("id")!=identifier]
        return _save(directory,rows)
