"""Native Skyfield TLE tracking; never a claim of received RF."""
from datetime import datetime,timedelta,timezone
import math,time
R_KM=6371.0
def valid(lat,lon):
    return all(isinstance(v,(int,float)) and math.isfinite(v) for v in (lat,lon)) and -90<=lat<=90 and -180<=lon<=180
def footprint_deg(alt_km,min_el=0):
    if not (0<=alt_km<=100000 and 0<=min_el<=90):raise ValueError("Invalid footprint bounds")
    e=math.radians(min_el)
    return max(0,math.degrees(math.acos(R_KM/(R_KM+alt_km)*math.cos(e))-e))
def sky_xy(az,el):
    radius=max(0,min(1,(90-el)/90))
    return radius*math.sin(math.radians(az)),-radius*math.cos(math.radians(az))
def mercator_xy(lat,lon,z):
    if not valid(lat,lon) or not 0<=z<=18:raise ValueError("Invalid Mercator coordinates")
    lat=max(-85.05112878,min(85.05112878,lat))
    t=math.sin(math.radians(lat));n=256*2**z
    return (lon+180)/360*n,(.5-math.log((1+t)/(1-t))/(4*math.pi))*n
def mercator_reverse(x,y,z):
    n=256*2**z
    return math.degrees(math.atan(math.sinh(math.pi*(1-2*max(0,min(n,y))/n)))), (x%n)/n*360-180
def dateline_segments(points):
    result=[];batch=[]
    for p in points:
        if batch and abs(p["lon"]-batch[-1]["lon"])>180:
            if len(batch)>1:result.append(batch)
            batch=[]
        batch.append(p)
    if len(batch)>1:result.append(batch)
    return result

class OrbitEngine:
    """Reuses cached Skyfield objects, updates when downloaded TLE files change."""
    def __init__(self,station):
        self.station=station
        self.keys=None
        self.records=[]
        self.warnings=[]
        self.ts=None
    def invalidate(self):self.keys=None
    def _load(self):
        from skyfield.api import load,EarthSatellite
        from .__main__ import SOURCE_URLS,parse_tle,selectable
        key=[]
        for source in SOURCE_URLS:
            f=self.station.directory/(source+".tle")
            try:
                st=f.stat();key.append((source,st.st_mtime_ns,st.st_size))
            except OSError:key.append((source,None,None))
        if tuple(key)==self.keys:return
        self.keys=tuple(key)
        self.ts=load.timescale(builtin=True)
        self.records=[];self.warnings=[]
        for source,_,_ in key:
            f=self.station.directory/(source+".tle")
            if not f.is_file():
                self.warnings.append(source+": missing cached TLE");continue
            age=time.time()-f.stat().st_mtime
            if age>7*86400:
                self.warnings.append(source+": stale TLE over 7 days");continue
            records=parse_tle(f.read_text(encoding="ascii",errors="replace"),limit=200)
            for item in records:
                if not selectable(source,item):continue
                if source=="amateur" and sum(x[1]=="amateur" for x in self.records)>=15:break
                try:sat=EarthSatellite(item["l1"],item["l2"],item["name"],self.ts)
                except (RuntimeError,ValueError):continue
                self.records.append((item,source,sat,age/86400))
                if len(self.records)>=160:return
    def snapshot(self,lat,lon,at=None,*,family_filter="all",minimum_el=-90,
                 selected_norad=None,with_track=False,track_scope="selected"):
        from skyfield.api import wgs84
        from .__main__ import family
        lat=float(lat);lon=float(lon)
        if not valid(lat,lon):raise ValueError("Select valid observer coordinates")
        if track_scope not in ("selected","all"):
            raise ValueError("Only selected/all track scopes are supported")
        at=at or datetime.now(timezone.utc)
        if at.tzinfo is None:raise ValueError("UTC-aware time required")
        at=at.astimezone(timezone.utc)
        self._load()
        observer=wgs84.latlon(lat,lon)
        t=self.ts.from_datetime(at)
        rows=[];selected=None;orbit_sources={}
        for item,source,sat,age in self.records:
            fam=family(source,item)
            if family_filter not in ("all",fam):continue
            try:
                point=wgs84.subpoint_of(sat.at(t))
                el,az,distance=(sat-observer).at(t).altaz()
                numbers=[point.latitude.degrees,point.longitude.degrees,point.elevation.km,
                         el.degrees,az.degrees,distance.km]
                if not all(math.isfinite(v) for v in numbers):continue
                row=dict(norad=int(item["id"]),name=item["name"],family=fam,
                         lat=round(numbers[0],5),lon=round(numbers[1],5),
                         alt_km=round(numbers[2],2),el=round(numbers[3],2),
                         az=round(numbers[4],2),range_km=round(numbers[5],2),
                         tle_age_days=round(age,2),status="ORBITAL_POSITION_ONLY")
                if selected_norad is not None and row["norad"]==int(selected_norad):
                    selected=(row,sat)
                if row["el"]>=minimum_el:
                    rows.append(row)
                    orbit_sources[row["norad"]]=sat
            except (ValueError,RuntimeError,OverflowError,ArithmeticError):continue
        rows.sort(key=lambda p:(-p["el"],p["name"]))
        track=[];choices=[]
        if with_track:
            # All visible tracks is bounded to avoid 100s of propagations on
            # every Qt frame; 12 objects at most, updated by map timer cache.
            if track_scope=="all":
                choices=[(row["norad"],orbit_sources[row["norad"]])
                         for row in rows if row["el"]>=0][:12]
            elif selected:
                choices=[(selected[0]["norad"],selected[1])]
            sample_times=[
                self.ts.from_datetime(at+timedelta(minutes=minute))
                for minute in range(-45,46,5)]
            for _norad,satellite in choices:
                samples=[]
                for minute,tick in zip(range(-45,46,5),sample_times):
                    try:
                        pos=wgs84.subpoint_of(satellite.at(tick))
                        samples.append(dict(
                            lat=pos.latitude.degrees,lon=pos.longitude.degrees,
                            minute_offset=minute))
                    except (ValueError,OverflowError,RuntimeError,ArithmeticError):
                        continue
                track.extend(dateline_segments(samples))
        return dict(at_utc=at.isoformat(),observer={"lat":lat,"lon":lon},satellites=rows,
                    selected=selected[0] if selected else None,track_segments=track,
                    track_scope=track_scope,track_object_count=len(choices),
                    total_loaded=len(self.records),warnings=list(self.warnings),
                    note="TLE geometry only. No actual RF reception or satellite data verified.")
