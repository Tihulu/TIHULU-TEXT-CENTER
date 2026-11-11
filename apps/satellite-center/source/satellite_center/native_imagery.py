"""Optional NASA Earth imagery in native Qt (HTTPS, on-demand, NOT radio).

Matches the browser's official EPIC and NASA Images metadata routes without
opening a WebView or requiring WebUSB. No requests occur at import/startup.
"""
from __future__ import annotations

import json
import re
from urllib.request import Request, urlopen
from urllib.parse import urlencode, urlsplit
from pathlib import Path

_EPIC_API = "https://api.nasa.gov/EPIC/api/natural/images?api_key=DEMO_KEY"
_ISS_API = "https://images-api.nasa.gov/search?" + urlencode({
    "q": "earth from ISS", "media_type": "image", "page_size": 12})
_MAX_CATALOG = 2_000_000
_MAX_IMAGE = 8_000_000


def _https_bytes(url, cap):
    parsed = urlsplit(url)
    if parsed.scheme != "https":
        raise ValueError("Online imagery requires HTTPS")
    if parsed.hostname not in {
        "api.nasa.gov", "images-api.nasa.gov",
        "images.nasa.gov", "images-assets.nasa.gov",
    }:
        raise ValueError("Image URL is not an approved NASA host")
    request = Request(url, headers={"User-Agent": "TIHULU-Satellite-Center-native/0.3"})
    with urlopen(request, timeout=14) as response:
        final = urlsplit(response.geturl())
        if final.scheme != "https" or final.hostname not in {
            "api.nasa.gov", "images-api.nasa.gov",
            "images.nasa.gov", "images-assets.nasa.gov",
        }:
            raise ValueError("NASA response redirected outside approved HTTPS hosts")
        payload = response.read(cap+1)
    if len(payload)>cap:
        raise ValueError("NASA response exceeded bounded memory budget")
    return payload


def _catalog(url):
    return json.loads(_https_bytes(url, _MAX_CATALOG))


def list_official_images(provider="epic"):
    if provider == "epic":
        payload = _catalog(_EPIC_API)
        if not isinstance(payload,list):
            raise ValueError("NASA EPIC returned no valid image catalog")
        rows=[]
        for entry in payload[:24]:
            if not isinstance(entry,dict):continue
            image=entry.get("image","")
            date=entry.get("date","")
            if not re.fullmatch(r"[a-zA-Z0-9_-]{1,100}",str(image)):continue
            if not re.fullmatch(r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d",str(date)):continue
            y,m,d=date[:10].split("-")
            url=f"https://api.nasa.gov/EPIC/archive/natural/{y}/{m}/{d}/jpg/{image}.jpg?api_key=DEMO_KEY"
            rows.append({
                "provider":"NASA DSCOVR EPIC",
                "id":image,"time":date+" UTC",
                "caption":str(entry.get("caption") or "Full Earth disk")[:250],
                "url":url,"radio_source":False
            })
        return rows[:16]
    if provider == "iss":
        payload=_catalog(_ISS_API)
        items=payload.get("collection",{}).get("items",[])
        if not isinstance(items,list):raise ValueError("NASA Images returned no valid items")
        rows=[]
        for item in items[:36]:
            data=item.get("data") or []
            links=item.get("links") or []
            if not data or not links:continue
            meta=data[0]
            if meta.get("media_type")!="image":continue
            url=str(links[0].get("href") or "")
            parsed=urlsplit(url)
            if parsed.scheme!="https" or parsed.hostname not in (
                "images.nasa.gov","images-assets.nasa.gov","images-api.nasa.gov"):
                continue
            rows.append({
                "provider":"NASA ISS Earth archive",
                "id":str(meta.get("nasa_id") or "")[:100],
                "time":str(meta.get("date_created") or "Date unavailable")[:64],
                "caption":str(meta.get("title") or "Historic ISS Earth image")[:250],
                "url":url,"radio_source":False,
            })
        return rows[:12]
    raise ValueError("Only NASA EPIC or NASA ISS archives are supported")


def fetch_official_image(record):
    """Return validated JPEG/PNG bytes only. Source and medium are explicit."""
    if not isinstance(record,dict) or record.get("radio_source") is not False:
        raise ValueError("Missing verified online image source")
    url=record.get("url")
    if not isinstance(url,str):
        raise ValueError("Invalid NASA image URL")
    payload=_https_bytes(url,_MAX_IMAGE)
    valid=(payload.startswith(b"\xff\xd8\xff") or
           payload.startswith(b"\x89PNG\r\n\x1a\n"))
    if not valid:
        raise ValueError("NASA response is not a valid PNG/JPEG signature")
    return payload
