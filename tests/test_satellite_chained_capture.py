"""No hardware needed: verify opt-in native 180s file-chain scheduling."""
import threading
import unittest
import uuid
from datetime import datetime, timedelta, timezone

from satellite_center.__main__ import Station


class NativeChainedCaptureTests(unittest.TestCase):
    def make_station(self, *, fail_second=False):
        app = object.__new__(Station)
        app.lock = threading.RLock()
        app.wake = threading.Event()
        app.jobs = []
        app.save_jobs = lambda: None
        start = datetime.now(timezone.utc)+timedelta(minutes=4)
        end = start+timedelta(minutes=13)
        app.predicted = {"fixture": {
            "aos": start.isoformat(), "los": end.isoformat(),
            "name": "METEOR-M2-4", "family": "meteor", "profiles": ["meteor"],
        }}
        attempts = []

        def fake_schedule(pass_id, profile, mode, run_at=None, seconds=None, *, automatic=False, sample_rate=1024000):
            attempts.append((run_at, seconds))
            if fail_second and len(attempts) == 2:
                raise ValueError("Simulated failure while creating the second part")
            job = {
                "id": uuid.uuid4().hex[:12], "pass_id": pass_id,
                "state": "pending", "capture_seconds": seconds,
                "run_at": run_at, "satellite": "METEOR-M2-4",
            }
            app.jobs.append(job)
            return dict(job)
        app.schedule = fake_schedule
        return app, start, attempts

    def test_300_seconds_schedules_two_independent_native_files(self):
        app, start, attempts = self.make_station()
        result = app.schedule_chain("fixture", "meteor", "iq", start.isoformat(), 300)
        self.assertEqual(result["scheduled_count"], 2)
        self.assertEqual([j["capture_seconds"] for j in result["scheduled"]], [180, 120])
        self.assertEqual(result["total_gap_seconds"], 21)
        self.assertEqual(result["elapsed_seconds"], 321)
        self.assertEqual(len(app.jobs), 2)
        self.assertEqual(app.jobs[0]["chain_id"], app.jobs[1]["chain_id"])
        self.assertEqual([j["chain_index"] for j in app.jobs], [1, 2])
        self.assertEqual((datetime.fromisoformat(attempts[1][0])
                          - datetime.fromisoformat(attempts[0][0])).total_seconds(), 201)

    def test_remainder_always_legal_eight_seconds(self):
        app, start, _ = self.make_station()
        result = app.schedule_chain("fixture", "meteor", "survey", start.isoformat(), 181)
        self.assertEqual([job["capture_seconds"] for job in result["scheduled"]], [173, 8])

    def test_chain_rolls_back_owned_jobs_if_later_segment_fails(self):
        app, start, _ = self.make_station(fail_second=True)
        external = {"id": "other", "state": "pending"}
        app.jobs.append(external)
        with self.assertRaisesRegex(ValueError, "Simulated failure"):
            app.schedule_chain("fixture", "meteor", "iq", start.isoformat(), 300)
        self.assertEqual(external["state"], "pending")
        self.assertEqual([j["state"] for j in app.jobs if j["id"] != "other"],
                         ["cancelled"])

    def test_chain_cannot_run_beyond_satellite_pass(self):
        app, start, _ = self.make_station()
        app.predicted["fixture"]["los"] = (start+timedelta(seconds=310)).isoformat()
        with self.assertRaisesRegex(ValueError, "exceed"):
            app.schedule_chain("fixture", "meteor", "iq", start.isoformat(), 300)
        self.assertEqual(app.jobs, [])

    def test_rejects_unbounded_part_sizes_and_zero_seconds(self):
        app, start, _ = self.make_station()
        with self.assertRaises(ValueError):
            app.schedule_chain("fixture", "meteor", "iq", start.isoformat(), 0)
        with self.assertRaises(ValueError):
            app.schedule_chain("fixture", "meteor", "iq", start.isoformat(), 301,
                               max_part_seconds=900)


if __name__ == "__main__":
    unittest.main()
