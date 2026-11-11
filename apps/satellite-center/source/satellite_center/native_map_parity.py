"""Evidence-honest native satellite-map media badges and orbital exports.

These are *orbital predictions*, not physical RF or received image packets.
The local Qt map uses exactly the same catalog as the Qt pass list.
"""
from __future__ import annotations
from datetime import datetime, timezone
import json
import math
from pathlib import Path

from .media_catalog import kinds_for_pass, media_summary
from .__main__ import profiles_for

KNOWN_MEDIA_ORBITS = {
    25544: "iss",
    57166: "meteor",
    59051: "meteor",
}

def map_satellite_capabilities(sat):
    """Media capability is determined by a known NORAD/profile pairing.

    Generic family labels alone are not enough: a newly launched or
    unidentified "meteor" craft must not inherit a verified decoder.
    Unknown orbit objects show only unclassified RF capability.
    """
    try:
        norad=int(sat.get("norad"))
    except (TypeError, ValueError):
        norad=-1
    category=str(sat.get("family","unknown"))
    recognized=KNOWN_MEDIA_ORBITS.get(norad)
    profiles=(profiles_for(recognized) if recognized==category else [])
    if not profiles:
        return ["RF data"]
    return kinds_for_pass({"profiles":profiles})

def map_satellite_protocols(sat):
    try:norad=int(sat.get("norad"))
    except (TypeError,ValueError):norad=-1
    category=sat.get("family")
    recognized=KNOWN_MEDIA_ORBITS.get(norad)
    if recognized!=category:
        return ["No specific image/audio/text decoder is catalogued for this NORAD object.",
                "Only the predicted orbital position is known; RF content is unverified."]
    return media_summary({"profiles":profiles_for(recognized)})

def filter_orbit_snapshot(snapshot,media="All",above_only=False,query=""):
    if media not in ("All","Image","Audio","Text","RF data","RF only"):
        raise ValueError("Unknown satellite map media filter")
    search=str(query).casefold().strip()
    original=snapshot.get("satellites",[])
    kept=[]
    for sat in original:
        kinds=map_satellite_capabilities(sat)
        if media=="RF only" and kinds!=["RF data"]:
            continue
        if media not in ("All","RF only") and media not in kinds:
            continue
        if above_only and sat.get("el",-90)<0:continue
        if search and search not in (str(sat.get("name",""))+" "+str(sat.get("norad",""))).casefold():
            continue
        kept.append(sat)
    result=dict(snapshot)
    result["satellites"]=kept
    result["unfiltered_orbital_candidates"]=len(original)
    return result

def _point(sat):
    lat=float(sat["lat"]);lon=float(sat["lon"])
    if not all(map(math.isfinite,(lat,lon))) or not -90<=lat<=90 or not -180<=lon<=180:
        raise ValueError("Invalid TLE subpoint in orbital GeoJSON export")
    return [lon,lat]

def orbital_geojson(snapshot):
    """Export map data only as explicitly synthetic/predicted orbital geometry.

    Uses true GeoJSON coordinate order [longitude,latitude].
    Includes relative track traces and observer, with a provenance warning.
    No satellite imagery or RF signal is represented by GeoJSON output.
    """
    if snapshot.get("note") and "RF" not in snapshot.get("note",""):
        raise ValueError("Missing orbital/RF provenance")
    features=[]
    for sat in snapshot.get("satellites",[]):
        point=_point(sat)
        features.append({
            "type":"Feature",
            "geometry":{"type":"Point","coordinates":point},
            "properties":{
                "name":str(sat.get("name",""))[:120],
                "norad":sat.get("norad"),"family":sat.get("family"),
                "azimuth_deg":sat.get("az"),"elevation_deg":sat.get("el"),
                "altitude_km":sat.get("alt_km"),"range_km":sat.get("range_km"),
                "tle_age_days":sat.get("tle_age_days"),
                "candidate_media_not_verified":map_satellite_capabilities(sat),
                "status":"ORBITAL_POSITION_ONLY"
            }
        })
    observer=snapshot.get("observer") or {}
    lat=float(observer.get("lat"));lon=float(observer.get("lon"))
    if not all(map(math.isfinite,(lat,lon))) or not -90<=lat<=90 or not -180<=lon<=180:
        raise ValueError("Invalid observer latitude/longitude")
    features.append({"type":"Feature","geometry":{"type":"Point","coordinates":[lon,lat]},
      "properties":{"name":"User-selected ground station","status":"OPERATOR_COORDINATES_UNVERIFIED"}})
    for segment in snapshot.get("track_segments",[]):
        coords=[]
        for point in segment:
            coords.append(_point(point))
        if len(coords)>=2:
            features.append({"type":"Feature",
                "geometry":{"type":"LineString","coordinates":coords},
                "properties":{"name":"Predicted selected-orbit path","status":"ORBITAL_TRACK_ONLY"}})
    return {
        "type":"FeatureCollection",
        "name":"TIHULU predicted satellite orbit map · NOT RF",
        "properties":{
            "format":"tihulu-native-orbital-geojson-v1",
            "generated_utc":datetime.now(timezone.utc).isoformat(),
            "orbit_at_utc":snapshot.get("at_utc"),
            "tles_loaded":snapshot.get("total_loaded"),
            "warnings":snapshot.get("warnings",[]),
            "source":"CelesTrak public TLEs cached and propagated locally using Skyfield",
            "has_rf_evidence":False,
            "contains_decoded_satellite_images":False,
            "note":"An orbital prediction is not a measured RF position or authenticated spacecraft downlink."
        },
        "features":features
    }

def export_orbit_geojson(snapshot,destination):
    target=Path(destination).expanduser()
    if target.suffix.lower() not in (".geojson",".json"):
        raise ValueError("Save GeoJSON with .geojson or .json extension")
    if target.is_symlink() or target.exists():
        raise ValueError("Refusing to overwrite an existing orbital GeoJSON")
    payload=orbital_geojson(snapshot)
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open("x",encoding="utf-8") as writer:
        json.dump(payload,writer,indent=2,ensure_ascii=False)
    return target
