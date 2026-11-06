"""Bounded, receive-only snapshot of an ALREADY-RUNNING local TIHULU Text Center.
No tuning, retuning, USB claim, writes, arbitrary URLs or automatically started
radio decoding. Local events may be stale or broadcaster-controlled untrusted text.
"""
from __future__ import annotations
import json
from urllib.request import build_opener, ProxyHandler, HTTPRedirectHandler, Request

BASE = "http://127.0.0.1:8787"
MAX_RESPONSE = 380_000

class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def _get(path):
    if path not in ("/api/rds/status", "/api/dab/last", "/api/events"):
        raise ValueError("Unsupported radio metadata source path")
    opener = build_opener(ProxyHandler({}), _NoRedirect())
    request = Request(BASE + path, method="GET", headers={"Accept": "application/json"})
    with opener.open(request, timeout=2) as response:
        if response.status != 200:
            raise ValueError("Existing local Text Center did not return data")
        raw = response.read(MAX_RESPONSE + 1)
    if len(raw) > MAX_RESPONSE:
        raise ValueError("Radio decoder response exceeded size cap")
    return json.loads(raw)


def read_local_radio_metadata():
    try:
        rds = _get("/api/rds/status")
        dab = _get("/api/dab/last")
        events = _get("/api/events")
    except (OSError, ValueError, TimeoutError, json.JSONDecodeError):
        return {"available": False, "events": [], "rdsActive": False, "dab": None,
                "message": "Local TIHULU Text Center not running on 127.0.0.1:8787 or decoder data unavailable. Start its own radio receiver only when desired."}
    if not isinstance(events, list):
        events = []
    acceptable = {"fm_rds", "fm_rds2", "dab", "dab_dls", "dab_mot", "rds"}
    safe = []
    for item in events[:150]:
        if not isinstance(item, dict):
            continue
        medium = str(item.get("medium", "")).lower()
        provenance = str(item.get("provenance", ""))
        if medium not in acceptable and "rds" not in medium and "dab" not in medium:
            continue
        freq = item.get("frequency_hz")
        freq = freq if type(freq) is int and 0 <= freq <= 1_800_000_000 else None
        safe.append({"kind": medium[:30], "station": str(item.get("station", ""))[:100],
                     "title": str(item.get("title", ""))[:180],
                     "body": str(item.get("body", ""))[:480],
                     "observedAt": str(item.get("received_at", ""))[:64],
                     "frequencyMHz": freq / 1e6 if freq is not None else None,
                     "source": "LOCAL TEXT CENTER DECODER / BROADCASTER-SUPPLIED, UNAUTHENTICATED",
                     "provenance": provenance[:160], "positionFix": False})
        if len(safe) >= 60:
            break
    rds_active = bool(rds.get("active")) if isinstance(rds, dict) else False
    dab_summary = None
    if isinstance(dab, dict):
        dab_summary = {"state": str(dab.get("status", "snapshot"))[:40],
                       "origin": "LOCAL WELLE-CLI DECODED DAB DATA (if available), NOT GPS"}
    return {"available": True, "events": safe, "rdsActive": rds_active,
            "dab": dab_summary,
            "message": "Read-only snapshot of existing local Text Center RDS/DAB reception. Never new RF capture or observer location."}
