"""Same real TLE metadata sorting/filtering in both native planner views."""
import unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from satellite_center.native_pass_filters import sort_filter_passes
from satellite_center.__main__ import Station


def synthetic_row(name,norad,when,elev,family,profiles,length=5):
    return {
        "id":f"{norad}:{when.timestamp()}",
        "name":name, "norad":norad, "aos":when.isoformat(),
        "los":(when+timedelta(minutes=length)).isoformat(),
        "max_elevation_deg":elev,
        "family":family,"profiles":profiles
    }


class NativeSharedPassFilters(unittest.TestCase):
    def setUp(self):
        start=datetime(2026,11,8,12,tzinfo=timezone.utc)
        self.rows=[
            synthetic_row("Meteor beta",101,start+timedelta(hours=3),55,
                          "meteor",["meteor"],12),
            synthetic_row("ISS Alpha",25544,start+timedelta(hours=1),30,
                          "iss",["iss_sstv"],8),
            synthetic_row("Cube Z",200,start+timedelta(hours=2),10,
                          "cubesat",["survey"],3),
        ]

    def test_sort_order_by_time_elevation_duration_and_name(self):
        def names(order):
            return [r["name"] for r in sort_filter_passes(self.rows,order=order)]
        self.assertEqual(names("soonest"),["ISS Alpha","Cube Z","Meteor beta"])
        self.assertEqual(names("latest"),["Meteor beta","Cube Z","ISS Alpha"])
        self.assertEqual(names("high"),["Meteor beta","ISS Alpha","Cube Z"])
        self.assertEqual(names("low"),["Cube Z","ISS Alpha","Meteor beta"])
        self.assertEqual(names("duration-long"),["Meteor beta","ISS Alpha","Cube Z"])
        self.assertEqual(names("duration-short"),["Cube Z","ISS Alpha","Meteor beta"])
        self.assertEqual(names("name"),["Cube Z","ISS Alpha","Meteor beta"])

    def test_family_media_search_filters_keep_original_list_intact(self):
        result=sort_filter_passes(self.rows,family="meteor",medium="Image")
        self.assertEqual([r["name"] for r in result],["Meteor beta"])
        self.assertEqual(len(sort_filter_passes(self.rows,medium="Text")),0)
        self.assertEqual(len(sort_filter_passes(self.rows,search="25544")),1)
        self.assertEqual(len(self.rows),3)
        with self.assertRaises(ValueError):
            sort_filter_passes(self.rows,order="invented")

    def test_first_run_requests_real_tle_when_no_cache(self):
        with TemporaryDirectory() as td:
            station=Station(Path(td))
            try:
                with patch.object(station,"refresh",return_value={
                    "iss":{"cached":2}
                }) as refresh, patch.object(station,"passes",return_value={
                    "predictions":[],"warnings":[]
                }) as predict:
                    result=station.plan_passes(lat=50.938,lon=6.96,hours=24)
                refresh.assert_called_once()
                predict.assert_called_once()
                self.assertEqual(result["predictions"],[])
                self.assertTrue(result["warnings"])
                self.assertIn("automatic_tle_refresh",result)
            finally:
                station.close()

    def test_offline_cached_tle_never_requires_network(self):
        with TemporaryDirectory() as td:
            station=Station(Path(td))
            try:
                (Path(td)/"iss.tle").write_text("user-provided orbital cache")
                with patch.object(station,"refresh") as refresh, patch.object(
                    station,"passes",return_value={"predictions":[],"warnings":[]}
                ):
                    result=station.plan_passes(lat=50.938,lon=6.96)
                refresh.assert_not_called()
                self.assertEqual(result["predictions"],[])
                self.assertNotIn("automatic_tle_refresh",result)
            finally:
                station.close()


if __name__=="__main__":
    unittest.main()
