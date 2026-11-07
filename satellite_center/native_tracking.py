"""TLE-only desktop orbital tracking. Orbital geometry is NEVER RF evidence.

No browser/HTTP server, hardware access, TLE fetch or network work.
"""
from datetime import datetime, timedelta, timezone
import math
from pathlib import Path
import time

MAX_SATELLITES = 180
MAX_TLE_AGE_SECONDS = 7 * 86400

def clamp_lat(value):
    return max(-85.05112878,min(85.05112878,float(value)))

def mercator_pixel(lat, lon, zoom):
    """Standard OSM/WebMercator 256-pixel XYZ tile coordinates."""
    if not isinstance(zoom,int) or not 0 <= zoom <= 19:
        raise ValueError("Invalid OSM zoom 0–19")
    if not all(math.isfinite(float(x)) for x in (lat,lon)):
        raise ValueError("Nonfinite position")
    lat=clamp_lat(lat)
    lam=math.radians(lat)
    world=256*(2**zoom)
    return (((float(lon)+180.0)/360.0*world)%world,
            (1.0-math.asinh(math.tan(lam))/math.pi)/2.0*world)

def mercator_unproject(x,y,zoom):
    world=256*(2**zoom)
    lon=(float(x)%world)/world*360-180
    lat=math.degrees(math.atan(math.sinh(math.pi*(1-2*float(y)/world))))
    return max(-90,min(90,lat)),lon

def sky_project(azimuth,elevation,width,height):
    if not all(math.isfinite(float(v)) for v in (azimuth,elevation,width,height)):
        raise ValueError("Nonfinite sky point")
    r=max(1.0,min(width,height)*0.46)*(1-min(90,max(0,elevation))/90)
    theta=math.radians(azimuth)
    return width/2+math.sin(theta)*r,height/2-math.cos(theta)*r

def split_dateline(points):
    """Do not draw long orbital line jumps across the ±180 meridian."""
    output=[]; segment=[]
    for item in points:
        if segment and abs(item[1]-segment[-1][1])>180:
            if len(segment)>1:output.append(segment)
            segment=[]
        segment.append(item)
    if len(segment)>1:output.append(segment)
    return output

def footprint_radius_km(altitude_km, min_elevation=0):
    """Simple spherical geometric radio horizon model; no RF propagation claim."""
    radius=6371.0
    h=max(0.0,float(altitude_km))
    elevation=math.radians(float(min_elevation))
    if not 0 <= min_elevation <= 90:
        raise ValueError("Elevation must be 0–90 degrees")
    angle=math.acos(radius/(radius+h)*math.cos(elevation))-elevation
    return radius*max(0,angle)

def load_cached_satellites(station,*, max_age=MAX_TLE_AGE_SECONDS):
    """Only recently cached public TLEs, never automatic download or unbounded reads."""
    from skyfield.api import EarthSatellite, load
    from .__main__ import SOURCE_URLS, parse_tle, family, selectable
    ts=load.timescale()
    entries=[];warnings=[]
    now=time.time()
    for source in SOURCE_URLS:
        path=Path(station.directory)/(source+".tle")
        if not path.is_file():
            warnings.append(source+": no cached TLE");continue
        if now-path.stat().st_mtime>max_age:
            warnings.append(source+": stale cached TLE (>7 days)");continue
        rows=parse_tle(path.read_text(encoding="ascii",errors="ignore"),limit=200)
        if source=="amateur":
            rows=[row for row in rows if selectable(source,row)][:18]
        for row in rows:
            if not selectable(source,row):continue
            try:
                obj=EarthSatellite(row["l1"],row["l2"],row["name"],ts)
                entries.append({"id":row["id"],"name":row["name"],
                                "family":family(source,row),"object":obj})
            except (ValueError,OverflowError,RuntimeError):
                continue
            if len(entries)>=MAX_SATELLITES:
                return entries,warnings
    return entries,warnings

def orbital_snapshot(station,lat,lon,at=None,*,family_filter="all",above_only=False):
    from skyfield.api import load,wgs84
    if not all(math.isfinite(float(n)) for n in (lat,lon)) or not -90<=lat<=90 or not -180<=lon<=180:
        raise ValueError("Invalid station coordinates")
    moment=at or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        raise ValueError("Tracking time must be timezone-aware")
    entries,warnings=load_cached_satellites(station)
    ts=load.timescale()
    t=ts.from_datetime(moment.astimezone(timezone.utc))
    observer=wgs84.latlon(lat,lon)
    rows=[]
    for row in entries:
        if family_filter!="all" and row["family"]!=family_filter:continue
        try:
            position=row["object"].at(t)
            ground=wgs84.subpoint(position)
            el,az,rng=(row["object"]-observer).at(t).altaz()
            if above_only and el.degrees<0:continue
            rows.append({
                "id":row["id"],"name":row["name"],"family":row["family"],
                "lat":round(ground.latitude.degrees,5),
                "lon":round(ground.longitude.degrees,5),
                "altitude_km":round(ground.elevation.km,2),
                "azimuth_deg":round(az.degrees,2),
                "elevation_deg":round(el.degrees,2),
                "distance_km":round(rng.km,1),
                "tle_only":True,"rf_verified":False})
        except (ValueError,OverflowError,RuntimeError,ZeroDivisionError):
            continue
    return {"as_of":moment.astimezone(timezone.utc).isoformat(),
            "observer":{"lat":lat,"lon":lon},"satellites":rows,
            "warnings":warnings,"source":"CelesTrak cached TLE, Skyfield",
            "note":"Predicted orbital geometry, not received RF or visual identification."}

def ground_track(station,norad,*,at=None,minutes=45,step_minutes=5):
    from skyfield.api import load,wgs84
    if not 0<=minutes<=90 or not 1<=step_minutes<=15:
        raise ValueError("Unbounded tracking horizon")
    entries,_=load_cached_satellites(station)
    sat=next((s["object"] for s in entries if int(s["id"])==int(norad)),None)
    if sat is None:return []
    center=at or datetime.now(timezone.utc)
    if center.tzinfo is None:raise ValueError("Time must be timezone-aware")
    ts=load.timescale()
    path=[]
    for delta in range(-minutes,minutes+1,step_minutes):
        try:
            position=wgs84.subpoint(sat.at(ts.from_datetime(center+timedelta(minutes=delta))))
            path.append((float(position.latitude.degrees),float(position.longitude.degrees)))
        except (ValueError,OverflowError,RuntimeError):
            continue
    return split_dateline(path)
