"""One source of truth for native home and detailed satellite pass sorting.

Only TLE-derived geometric predictions are handled; never produces RF claims.
"""
from __future__ import annotations

from datetime import datetime
from .media_catalog import filter_passes, kinds_for_pass

SORTS=("soonest","latest","high","low","duration-long","duration-short","name")
FAMILIES=("all","iss","meteor","cubesat","iridium")
MEDIA=("All","Image","Audio","Text","RF data","RF only")


def sort_filter_passes(all_rows, *, search="", family="all", medium="All",
                       order="soonest"):
    if family not in FAMILIES or order not in SORTS or medium not in MEDIA:
        raise ValueError("Unknown orbit planning filter")
    if medium=="RF only":
        rows=[r for r in filter_passes(all_rows,"RF data",search)
              if kinds_for_pass(r)==["RF data"]]
    else:
        rows=filter_passes(all_rows,medium,search)
    if family!="all":
        rows=[r for r in rows if r.get("family")==family]
    def duration(row):
        try:
            return (datetime.fromisoformat(row["los"])-
                    datetime.fromisoformat(row["aos"])).total_seconds()
        except (KeyError,TypeError,ValueError):
            return 0
    if order=="latest":
        rows.sort(key=lambda r:r.get("aos",""),reverse=True)
    elif order=="high":
        rows.sort(key=lambda r:float(r.get("max_elevation_deg",0)),reverse=True)
    elif order=="low":
        rows.sort(key=lambda r:float(r.get("max_elevation_deg",0)))
    elif order=="duration-long":
        rows.sort(key=duration,reverse=True)
    elif order=="duration-short":
        rows.sort(key=duration)
    elif order=="name":
        rows.sort(key=lambda r:str(r.get("name","")).casefold())
    else:
        rows.sort(key=lambda r:r.get("aos",""))
    return rows
