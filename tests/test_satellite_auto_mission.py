"""Synthetic safety checks for one-click *native* unattended satellite planning.
No USB hardware, network, RF tools or receiver programs are opened.
"""
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from satellite_center.__main__ import Station

class AutoMissionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.station = Station(directory=Path(self.tmp.name))
        self.addCleanup(self.station.close)
        # Prevent network access: on-demand catalogue files are fresh/cached.
        for source in ("iss", "meteor3", "meteor4"):
            (self.station.directory / (source + ".tle")).write_text("cached TLE\n")
        self.now = datetime.now(timezone.utc)
        self.events = []
        for id, offset, family in [(57166, 3600, "meteor"), (59051, 3630, "meteor"),
                                    (25544, 7200, "iss")]:
            a = self.now + timedelta(seconds=offset)
            b = a + timedelta(seconds=480)
            self.events.append({"id": str(id)+":"+str(offset), "norad": id, "name": "Test "+str(id),
                                "family": family, "aos": a.isoformat(), "los": b.isoformat(),
                                "profiles": ["meteor"] if family=="meteor" else ["iss_sstv", "iss_aprs_uhf"]})
        self.captured = []
        def fake_schedule(pass_id, profile, mode):
            record = next(r for r in self.events if r["id"] == pass_id)
            job = {"id": str(len(self.captured)+1), "pass_id": pass_id, "satellite": record["name"],
                   "aos": record["aos"], "los": record["los"], "profile": profile,
                   "mode": mode, "state": "pending"}
            self.station.jobs.append(job)
            self.captured.append(job)
            return job
        self.patches = [
            patch.object(self.station, "passes", return_value={"predictions": self.events, "warnings": []}),
            patch.object(self.station, "refresh", side_effect=AssertionError("Unexpected network refresh")),
            patch.object(self.station, "schedule", side_effect=fake_schedule),
            patch("satellite_center.__main__.shutil.which", side_effect=lambda tool: "/fake/bin/"+tool),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def test_schedules_nonoverlapping_real_public_targets_without_claiming_receiver(self):
        outcome = self.station.auto_schedule(
            ["meteor-m2-3", "meteor-m2-4", "iss-sstv"], hours=24, max_jobs=6
        )
        self.assertEqual(outcome["scheduled_count"], 2)
        self.assertEqual([j["profile"] for j in outcome["scheduled"]], ["meteor", "iss_sstv"])
        self.assertEqual([j["mode"] for j in outcome["scheduled"]], ["iq", "iq"])
        self.assertEqual(outcome["receiver_claimed"], False)
        self.assertIsNone(self.station.device_lock)

    def test_aprs_uhf_profile_without_claiming_receiver(self):
        outcome = self.station.auto_schedule(["iss-aprs"], hours=24)
        self.assertEqual(outcome["scheduled_count"], 1)
        self.assertEqual(outcome["scheduled"][0]["profile"], "iss_aprs_uhf")
        self.assertEqual(outcome["scheduled"][0]["mode"], "aprs")

    def test_two_iss_passes_serve_different_downlink_objectives(self):
        a = self.now + timedelta(seconds=10800)
        b = a + timedelta(seconds=480)
        self.events.append({"id": "25544:extra", "norad": 25544, "name": "Test 25544 later",
                            "family": "iss", "aos": a.isoformat(), "los": b.isoformat(),
                            "profiles": ["iss_sstv", "iss_aprs_uhf"]})
        outcome = self.station.auto_schedule(["iss-sstv", "iss-aprs"], max_jobs=6)
        self.assertEqual(outcome["scheduled_count"], 2)
        self.assertEqual([j["profile"] for j in outcome["scheduled"]],
                         ["iss_sstv", "iss_aprs_uhf"])

    def test_no_unsupported_or_retired_catalog_targets(self):
        with self.assertRaisesRegex(ValueError, "Unknown"):
            self.station.auto_schedule(["legacy-noaa"])
        with self.assertRaisesRegex(ValueError, "Unknown"):
            self.station.auto_schedule(["iss-hamtv"])
        self.assertFalse(self.captured)

if __name__=="__main__":
    unittest.main()
