"""Native Qt ground-station name lookup: explicit Open-Meteo, bounded HTTPS.

This is an optional user-initiated online search, NOT GPS. The UI may call it
after a short debounce only when the user has selected Worldwide online search
(or explicitly opted into online suggestions). No network access on startup.
"""
from __future__ import annotations

import json
import math
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

API_HOST = "geocoding-api.open-meteo.com"
# Narrow spelling rescue for the reported typo. No fabricated coordinates:
# the corrected query is always resolved through the real geocoder.
QUERY_ALIASES = {"syney": "Sydney"}


def normalize_city_query(query):
    typed=str(query).strip()
    if not 2 <= len(typed) <= 100:
        raise ValueError("Enter a city name (2–100 characters)")
    return QUERY_ALIASES.get(typed.casefold(),typed)


def parse_worldwide_places(payload, country="all"):
    """Parse validated Open-Meteo records without manufacturing coordinates."""
    if not isinstance(payload, dict):
        raise ValueError("Unrecognized geocoding response")
    if payload.get("error"):
        raise ValueError(str(payload.get("reason") or "Location provider error")[:200])
    records=payload.get("results") or []
    if not isinstance(records,list):
        raise ValueError("Invalid location results")
    result=[]
    for row in records[:30]:
        if not isinstance(row,dict):continue
        try:
            lat=float(row["latitude"])
            lon=float(row["longitude"])
        except (KeyError,ValueError,TypeError):continue
        if not (math.isfinite(lat) and math.isfinite(lon) and
                -90<=lat<=90 and -180<=lon<=180):continue
        cc=str(row.get("country_code") or "").upper()
        if country in ("DE","TR") and cc!=country:continue
        name=str(row.get("name") or "").strip()[:100]
        if not name:continue
        region=str(row.get("admin1") or "").strip()[:100]
        state=str(row.get("country") or "").strip()[:100]
        label=" · ".join(x for x in (name,region,state) if x)
        result.append({"provider":"online","name":name,"region":region,
                       "country":state,"country_code":cc,"lat":lat,"lon":lon,
                       "label":label+" · Online"})
        if len(result)>=10:break
    return result


def search_worldwide(query, country="all"):
    name=normalize_city_query(query)
    if country not in ("all","DE","TR"):
        raise ValueError("Invalid country filter")
    fields={"name":name,"count":"10","language":"en","format":"json"}
    if country!="all":fields["countryCode"]=country
    url="https://"+API_HOST+"/v1/search?"+urlencode(fields)
    request=Request(url,headers={"User-Agent":"TIHULU-Satellite-Center-native/0.3"})
    with urlopen(request,timeout=12) as response:
        redirect=urlsplit(response.geturl())
        if redirect.scheme!="https" or redirect.hostname!=API_HOST:
            raise ValueError("Location provider redirected outside approved HTTPS host")
        raw=response.read(500001)
    if len(raw)>500000:
        raise ValueError("Geocoding reply exceeds 500 KB")
    return parse_worldwide_places(json.loads(raw),country)
