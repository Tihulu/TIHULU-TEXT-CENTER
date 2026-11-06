"""Native desktop station search over the shared 8,084 DE/TR offline cities.

No browser, online geocoding, GPS access or geolocation inference.
Raw city dataset stays in satellite_center/browser/cities-de-tr.json (ODbL).
"""
import json
import math
from pathlib import Path
import unicodedata

CITIES_JSON = Path(__file__).parent / "browser" / "cities-de-tr.json"

def fold(value):
    result=unicodedata.normalize("NFD",str(value).strip().casefold())
    result="".join(c for c in result if unicodedata.category(c)!="Mn")
    return result.replace("ı","i").replace("ß","ss").replace("æ","ae")

ALIASES = {
    "cologne":"koln","koln":"koln","munich":"munchen","huerth":"hurth",
    "nuremberg":"nurnberg","dusseldorf":"dusseldorf","antep":"gaziantep",
    "sanliurfa":"sanliurfa",
}

def load_locations(path=CITIES_JSON):
    payload=json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema")!="country,name,region,latitude,longitude":
        raise ValueError("Unknown local city schema")
    result=[]
    for row in payload.get("places",[]):
        if not isinstance(row,list) or len(row)!=5:
            continue
        cc,name,region,lat,lon=row
        if cc not in ("DE","TR") or not isinstance(name,str) or not isinstance(region,str):
            continue
        if not all(isinstance(v,(float,int)) and math.isfinite(v) for v in (lat,lon)):
            continue
        if -90<=lat<=90 and -180<=lon<=180:
            result.append((cc,name,region,float(lat),float(lon)))
    return result

def search_locations(rows,query,country="all",limit=12):
    query=fold(query)
    query=ALIASES.get(query,query)
    if len(query)<2 or country not in ("all","DE","TR"):
        return []
    found=[]
    for row in rows:
        cc,name,region,lat,lon=row
        if country!="all" and cc!=country:continue
        key=fold(name)
        if key==query:priority=0
        elif key.startswith(query):priority=1
        elif query in key:priority=2
        elif all(term in (key+" "+fold(region)) for term in query.split()):priority=3
        else:continue
        found.append((priority,len(name),name.casefold(),row))
    found.sort(key=lambda x:(x[0],x[1],x[2]))
    return [v[3] for v in found[:max(1,min(20,limit))]]

def city_label(row):
    cc,name,region,_,_=row
    return f"{name} · {region} · {'Germany' if cc=='DE' else 'Türkiye'}"
