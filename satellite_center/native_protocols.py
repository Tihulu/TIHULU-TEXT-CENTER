"""Browser-compatible, receive-only user downlink reference library.

Schema aligns with saved_satellite_protocols.mjs for JSON interchange.
No user profile can launch SDR, transmit or activate unverified decoders.
"""
from __future__ import annotations
import json
import math
import os
from pathlib import Path
import re
from urllib.parse import urlsplit

LIMIT=32
IMPORT_LIMIT=40_000
KINDS=("image","audio","text","video")
SCHEMA="tihulu-public-satellite-profiles-v1"

def parse_user_protocol(record):
    if not isinstance(record,dict):
        raise ValueError("Satellite protocol must be a JSON object")
    try:norad=int(record.get("norad"))
    except (TypeError,ValueError):raise ValueError("NORAD must be an integer")
    if str(norad)!=str(record.get("norad")) and type(record.get("norad")) is not int:
        raise ValueError("NORAD must be a whole number")
    if not 1000<=norad<=9_999_999:
        raise ValueError("NORAD must be between 1000 and 9999999")
    try:hz=float(record.get("frequencyHz"))
    except (TypeError,ValueError):raise ValueError("Frequency must be numeric")
    if not math.isfinite(hz) or not hz.is_integer() or not 24_000_000<=hz<=1_750_000_000:
        raise ValueError("RTL-SDR frequency must be 24–1750 MHz, whole hertz")
    hz=int(hz)
    kind=record.get("kind")
    if kind not in KINDS:
        raise ValueError("Use image, audio, text or video")
    protocol=str(record.get("protocol") or "").strip()[:64]
    if not protocol or any(ord(ch)<32 or ch in "<>" for ch in protocol):
        raise ValueError("Protocol label must be simple text, 1–64 characters")
    source=str(record.get("source") or "https://db.satnogs.org/").strip()[:300]
    url=urlsplit(source)
    if url.scheme!="https" or not url.netloc or url.username or url.password or any(
            ord(x)<32 for x in source):
        raise ValueError("Reference URL must be HTTPS without credentials")
    return {
        "id":f"user-{norad}-{hz}-{kind}","norad":norad,"kind":kind,
        "label":kind.upper()+" · USER","frequencyHz":hz,
        "protocol":protocol,"source":source,
        "activity":"user-supplied-not-verified",
        "decoder":"no-decoder-connected","station":f"NORAD {norad}",
        "note":"User reference only; no auto decoder, SDR capture or verified transmitter.",
        "provenance":"user-supplied"
    }

def validate_profiles(rows):
    if not isinstance(rows,list) or len(rows)>LIMIT:
        raise ValueError("Maximum 32 manually saved profiles")
    unique={}
    for row in rows:
        parsed=parse_user_protocol(row)
        unique[parsed["id"]]=parsed
    return list(unique.values())

def catalog_path(directory):
    return Path(directory)/"user_downlinks.json"

def load_profiles(directory):
    path=catalog_path(directory)
    if not path.exists():return []
    if path.is_symlink() or path.stat().st_size>IMPORT_LIMIT:
        raise ValueError("Local protocol catalog is unsafe or oversized")
    doc=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc,dict):
        raise ValueError("Local user protocol document must be a JSON object")
    return validate_profiles(doc.get("profiles",[]))

def save_profiles(directory,profiles):
    data=validate_profiles(profiles)
    directory=Path(directory)
    directory.mkdir(mode=0o700,parents=True,exist_ok=True)
    target=catalog_path(directory)
    if target.is_symlink():
        raise ValueError("Refusing symlink catalog")
    temp=directory/("user_downlinks."+str(os.getpid())+".tmp")
    doc={"schema":SCHEMA,"source":"user-supplied-unverified","profiles":data}
    with temp.open("x",encoding="utf-8") as f:
        json.dump(doc,f,indent=2,ensure_ascii=False)
        f.write("\n")
    try:
        os.chmod(temp,0o600)
        os.replace(temp,target)
    finally:temp.unlink(missing_ok=True)
    return data

def import_profiles(directory,file):
    path=Path(file)
    if not path.is_file() or path.is_symlink() or path.stat().st_size>IMPORT_LIMIT:
        raise ValueError("Choose a regular <=40KB protocol JSON file")
    doc=json.loads(path.read_text(encoding="utf-8"))
    if isinstance(doc,list):
        rows=doc
    elif isinstance(doc,dict):
        rows=doc.get("profiles")
    else:
        raise ValueError("User protocol import must be a list or a JSON object")
    data=validate_profiles(rows)
    old=load_profiles(directory)
    merged={r["id"]:r for r in old+data}
    result=save_profiles(directory,list(merged.values()))
    return result

def export_profiles(directory,file):
    target=Path(file)
    if target.suffix.lower()!=".json" or target.exists() or target.is_symlink():
        raise ValueError("Choose a new .json output (no overwrite)")
    rows=load_profiles(directory)
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open("x",encoding="utf-8") as f:
        json.dump({"schema":SCHEMA,"source":"user-supplied-unverified",
                   "profiles":rows},f,indent=2,ensure_ascii=False)
    return target

def match_user_hints(candidates,profiles):
    """Add explicit unverified user references to *measured* RF candidates."""
    for item in candidates.get("candidates",[]):
        hz=item.get("frequency_hz")
        if not isinstance(hz,(int,float)) or not math.isfinite(hz):
            continue
        bandwidth=max(20_000,min(150_000,abs(item.get("width_hz_approx") or 0)))
        matches=[{"norad":p["norad"],"frequency_hz":p["frequencyHz"],
                  "kind":p["kind"],"protocol":p["protocol"],
                  "status":"USER_SUPPLIED_NOT_VERIFIED"}
                 for p in profiles if abs(p["frequencyHz"]-hz)<=bandwidth]
        item["user_reference_matches_unverified"]=matches[:8]
    return candidates
