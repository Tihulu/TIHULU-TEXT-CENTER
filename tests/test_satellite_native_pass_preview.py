"""Regression checks: native calendar, Skyfield preview, and datetime scope.

No actual SDR or network access. TLE orbit geometry must not imply reception.
"""
import ast
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType, SimpleNamespace
import sys
import unittest
from unittest.mock import Mock, patch

from satellite_center.native_orbit import OrbitEngine

ROOT = Path(__file__).resolve().parents[1] / "satellite_center"


class NativePassPreviewTests(unittest.TestCase):
    def test_qt_bridge_does_not_shadow_datetime(self):
        source=(ROOT/"native_web_shell.py").read_text(encoding="utf-8")
        tree=ast.parse(source)
        cls=next(item for item in tree.body
                 if isinstance(item,ast.ClassDef) and item.name=="NativeReceiver")
        execute=next(item for item in cls.body
                     if isinstance(item,ast.FunctionDef) and item.name=="execute")
        # Previously: 'from datetime import datetime,timezone' inside schedule
        # made datetime a local across execute() and crashed orbit_snapshot.
        self.assertFalse(any(
            isinstance(node,ast.ImportFrom) and node.module=="datetime"
            for node in ast.walk(execute)))
        self.assertIn('if command=="pass_preview":',source)
        self.assertIn('if command=="cancel_schedule":',source)

    def test_skyfield_trajectory_sampling_and_timing_without_network(self):
        class Angle:
            def __init__(self,value):self.degrees=value
        class Range:
            km=850.0
        class Position:
            pass
        class FakeSatellite:
            def __sub__(self,other):return self
            def at(self,date):return self
            def altaz(self):
                return Angle(23.0), Angle(300.0), Range()
        class Subpoint:
            latitude=Angle(51.0)
            longitude=Angle(7.0)
        fake_wgs84=SimpleNamespace(
            latlon=lambda lat,lon:object(),
            subpoint_of=lambda pos:Subpoint()
        )
        fake_api=ModuleType("skyfield.api")
        fake_api.wgs84=fake_wgs84
        fake_package=ModuleType("skyfield")
        fake_package.api=fake_api
        orbit=OrbitEngine(SimpleNamespace(directory=Path("/unused")))
        orbit.records=[({"id":59051,"name":"METEOR M2-4"},"meteor4",FakeSatellite(),0.0)]
        orbit.ts=SimpleNamespace(from_datetime=lambda value:value)
        start=datetime(2026,11,8,12,tzinfo=timezone.utc)
        stop=start+timedelta(minutes=10)
        with patch.object(orbit,"_load"),patch.dict(sys.modules,{
            "skyfield":fake_package,"skyfield.api":fake_api
        }):
            result=orbit.preview_pass(50.89651,6.89686,59051,start,stop)
        self.assertEqual(result["norad"],59051)
        self.assertGreater(len(result["steps"]),10)
        self.assertEqual(result["steps"][0]["at_ms"],int(start.timestamp()*1000))
        self.assertEqual(result["steps"][-1]["at_ms"],int(stop.timestamp()*1000))
        self.assertTrue(all(0<=r["az"]<360 for r in result["steps"]))
        self.assertEqual(result["peak"]["el"],23.0)
        self.assertIn("Geometric prediction",result["disclaimer"])

    def test_schedule_is_not_faked_as_orbital_prediction(self):
        browser=(ROOT/"browser"/"browser.js").read_text(encoding="utf-8")
        maps=(ROOT/"browser"/"satellite_maps.mjs").read_text(encoding="utf-8")
        html=(ROOT/"browser"/"index.html").read_text(encoding="utf-8")
        bridge=(ROOT/"native_desktop_bridge.js").read_text(encoding="utf-8")
        self.assertIn("renderPredictedPassCalendar()",browser)
        self.assertIn("nativeScheduledJobs",browser)
        self.assertIn("window.nativeScheduleStatus=()=>lookup('status')",bridge)
        self.assertIn("window.nativePassPreview=",bridge)
        self.assertIn("tihulu-native-schedule-changed",bridge)
        self.assertIn("tihulu-passes-updated",maps)
        self.assertIn("passPreview.steps",maps)
        for control in ("predicted-pass-calendar-grid","map-pass-select",
                        "map-pass-play","map-pass-stop","map-pass-time"):
            self.assertIn('id="'+control+'"',html)


if __name__=="__main__":
    unittest.main()
