"""Native planning notes and altitude regression: no connected SDR needed."""
import json
import tempfile
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace, ModuleType
from unittest.mock import patch

from satellite_center.planning_store import (
    add_candidate,load_candidates,remove_candidate,validate_candidate)
from satellite_center.native_orbit import OrbitEngine,footprint_deg

class PlanningAndOrbitalGeometryTests(unittest.TestCase):
    def test_candidate_survives_new_native_qt_session_without_receiver(self):
        with tempfile.TemporaryDirectory() as temp:
            now=datetime.now(timezone.utc)
            aos=int((now+timedelta(minutes=10)).timestamp()*1000)
            record={"norad":59051,"name":"METEOR M2-4",
                    "aos":aos,"los":aos+10*60000,"family":"meteor",
                    "observer":{"lat":50.938,"lon":6.960},
                    "status":"planning-only","radioArmed":False}
            saved=add_candidate(temp,record,now=now)
            self.assertEqual(len(saved),1)
            self.assertFalse(saved[0]["radioArmed"])
            self.assertFalse(saved[0]["actualRecording"])
            self.assertEqual(load_candidates(temp)[0]["norad"],59051)
            self.assertNotIn("receiver_enabled",Path(temp,"planning_candidates.json").read_text())
            self.assertEqual(remove_candidate(temp,saved[0]["id"]),[])
            self.assertEqual(load_candidates(temp),[])
            record["radioArmed"]=True
            with self.assertRaisesRegex(ValueError,"cannot arm"):
                validate_candidate(record,now)
    def test_real_satellite_geodetic_altitude_not_subpoint_zero(self):
        class Angle:
            def __init__(self,v):self.degrees=v
        class Length:
            def __init__(self,v):self.km=v
        class Position:
            def at(self,t):return self
            def altaz(self):return Angle(38),Angle(280),Length(820)
        class Satellite(Position):
            def __sub__(self,observer):return self
        class Geographic:
            latitude=Angle(51.5)
            longitude=Angle(7.5)
            elevation=Length(540)
        class Subpoint:
            latitude=Angle(51.5)
            longitude=Angle(7.5)
            elevation=Length(0)
        calls=[]
        def geo(position):
            calls.append("geographic_position_of")
            return Geographic()
        wgs=SimpleNamespace(latlon=lambda *args:object(),
            geographic_position_of=geo,
            subpoint_of=lambda x:Subpoint())
        api=ModuleType("skyfield.api");api.wgs84=wgs
        pkg=ModuleType("skyfield");pkg.api=api
        orbit=OrbitEngine(SimpleNamespace(directory=Path("/nonexistent")))
        orbit.records=[({"id":59051,"name":"METEOR M2-4"},"amateur",Satellite(),0)]
        orbit.ts=SimpleNamespace(from_datetime=lambda v:v)
        with patch.object(orbit,"_load"),patch.dict(sys.modules,
                 {"skyfield":pkg,"skyfield.api":api}):
            result=orbit.snapshot(50.938,6.960,datetime.now(timezone.utc))
        self.assertEqual(len(result["satellites"]),1)
        self.assertEqual(result["satellites"][0]["alt_km"],540.0)
        self.assertGreater(footprint_deg(result["satellites"][0]["alt_km"],10),0)
        self.assertEqual(calls,["geographic_position_of"])

    def test_offline_leaflet_bundle_and_csp_friendly_local_loader(self):
        root=Path(__file__).resolve().parents[1]/"satellite_center"
        web=root/"browser"
        javascript=(web/"leaflet.js").read_text(encoding="utf-8")
        css=(web/"leaflet.css").read_text(encoding="utf-8")
        maps=(web/"satellite_maps.mjs").read_text(encoding="utf-8")
        self.assertGreater(len(javascript),110000)
        self.assertGreater(len(css),10000)
        self.assertTrue((web/"leaflet.LICENSE.txt").is_file())
        self.assertIn('css.href="./leaflet.css"',maps)
        self.assertIn('script.src="./leaflet.js"',maps)
        self.assertNotIn('cdn.jsdelivr.net/npm/leaflet@',maps)
        native=(root/"native_web_shell.py").read_text(encoding="utf-8")
        self.assertIn('".js":b"text/javascript"',native)
