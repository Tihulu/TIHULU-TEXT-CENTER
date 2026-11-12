"""EXIT-01 Satellite synthetic lifecycle contracts; no SDR, SatDump or Qt run.

All subprocesses are fake objects, all lock files reside in TemporaryDirectory.
Tests exercise the exact feature branch rather than installed host receivers.
"""
from __future__ import annotations

import os
import threading
import time
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from satellite_center import __main__ as satellite
from satellite_center.bridge import lock_receiver, unlock_receiver


class FakeChild:
    """Represents a subprocess.Popen handle directly owned by Station."""

    def __init__(self):
        self.running = True
        self.stop_calls = 0

    def poll(self):
        return None if self.running else 0


def stop_fake(child):
    child.stop_calls += 1
    child.running = False


class Exit01SatelliteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="satellite-exit01-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.station = satellite.Station(self.root)
        self.addCleanup(self.station.close)

    def lease(self):
        """Synthetic file lock, not the user's shared receiver lock or USB."""
        fd = os.open(self.root / "owned-rf-test.lock", os.O_RDWR | os.O_CREAT, 0o600)
        lock_receiver(fd)
        self.station.device_lock = fd
        return fd

    def future_job(self):
        start = datetime.now(timezone.utc) + timedelta(minutes=10)
        job = {
            "id": "synthetic-pass-1", "state": "pending", "profile": "meteor",
            "mode": "iq", "sample_rate": 1024000, "run_at": start.isoformat(),
            "aos": start.isoformat(), "los": (start + timedelta(minutes=10)).isoformat(),
            "capture_seconds": 12, "satellite": "SYNTHETIC-NO-RF",
        }
        self.station.jobs.append(job)
        return job

    def test_true_quit_cancels_pending_schedule_persistently_and_is_idempotent(self):
        job = self.future_job()
        with mock.patch.object(self.station, "capture",
                               side_effect=AssertionError("late capture launched")):
            self.station.start_scheduler()
            first = self.station.close()
            second = self.station.close()
        self.assertEqual(job["state"], "cancelled")
        self.assertEqual(first["state"], "stopped")
        self.assertEqual(second["state"], "stopped")
        self.assertFalse(self.station.scheduler_thread.is_alive())
        persisted = satellite.safe_read(self.root / "schedule.json", [])
        self.assertEqual(persisted[0]["state"], "cancelled")
        self.assertFalse(any(item["state"] == "pending" for item in persisted))
        self.station.start_scheduler()
        self.assertFalse(self.station.scheduler_thread.is_alive())

    def test_quit_stops_only_owned_fake_process_and_releases_own_lock(self):
        owned, external = FakeChild(), FakeChild()
        self.station.process = owned
        self.station.owned_processes.add(owned)
        fd = self.lease()
        external_fd = os.open(self.root / "external-not-satellite.lock",
                              os.O_RDWR | os.O_CREAT, 0o600)
        self.addCleanup(lambda: os.close(external_fd))
        lock_receiver(external_fd)
        self.addCleanup(lambda: unlock_receiver(external_fd))
        with mock.patch.object(satellite, "stop_process", side_effect=stop_fake) as stopped:
            outcome = self.station.close()
        self.assertTrue(outcome["app_released"])
        self.assertEqual(outcome["owned_processes_remaining"], 0)
        self.assertTrue(owned.stop_calls >= 1)
        self.assertEqual(external.stop_calls, 0)
        self.assertFalse(external_fd == fd)
        os.fstat(external_fd)  # untouched independent external file lock
        with self.assertRaises(OSError):
            os.fstat(fd)  # own FD was actually closed
        self.assertTrue(all(call.args[0] is owned for call in stopped.call_args_list))

    def test_timeout_reports_partial_release_then_can_retry_without_double_free(self):
        owned = FakeChild()
        self.station.process = owned
        self.station.owned_processes.add(owned)
        fd = self.lease()
        with mock.patch.object(satellite, "stop_process", side_effect=lambda _: None):
            incomplete = self.station.close(timeout_seconds=0.08)
        self.assertEqual(incomplete["state"], "stop_failed_partial")
        self.assertTrue(incomplete["lease_held"])
        self.assertEqual(incomplete["owned_processes_remaining"], 1)
        os.fstat(fd)  # held while the fake app child still runs
        with mock.patch.object(satellite, "stop_process", side_effect=stop_fake):
            complete = self.station.close(timeout_seconds=0.5)
        self.assertEqual(complete["state"], "stopped")
        self.assertTrue(complete["app_released"])
        with self.assertRaises(OSError):
            os.fstat(fd)

    def test_quit_denies_late_receiver_launch_and_schedule_without_tools(self):
        job = self.future_job()
        self.station.begin_quit()
        with mock.patch.object(satellite, "start_receiver_process",
                               side_effect=AssertionError("must not spawn")):
            with self.assertRaisesRegex(RuntimeError, "stopping"):
                self.station._launch_receiver(["fake-rtl_sdr"])
        with self.assertRaisesRegex(RuntimeError, "quitting"):
            self.station.schedule("never-run", "meteor", "iq", seconds=12)
        with self.assertRaisesRegex(RuntimeError, "quitting"):
            self.station.schedule_chain("never-run", "meteor", "iq", seconds=12)
        with self.assertRaisesRegex(RuntimeError, "quitting"):
            self.station.auto_schedule(["not-a-real-mission"])
        self.assertEqual(job["state"], "cancelled")

    def test_scheduler_running_capture_cannot_publish_completed_after_quit(self):
        job = self.future_job()
        job["run_at"] = (datetime.now(timezone.utc) - timedelta(seconds=2)).isoformat()
        job["aos"] = job["run_at"]
        job["los"] = (datetime.now(timezone.utc) + timedelta(minutes=3)).isoformat()
        started, release = threading.Event(), threading.Event()

        def capture_stub(*args, **kwargs):
            started.set()
            release.wait(3)
            # Existing IQ must remain available even as the GUI closes.
            (self.station.archive / "preserved-original.cu8").write_bytes(b"\x7f\x80")
            return {"file": "preserved-original.cu8", "status": "recorded_unverified_rf"}

        with mock.patch.object(self.station, "capture", side_effect=capture_stub):
            self.station.start_scheduler()
            self.assertTrue(started.wait(2), "scheduler did not start fixture")
            outcome_box = []
            closer = threading.Thread(target=lambda: outcome_box.append(self.station.close()))
            closer.start()
            self.assertTrue(self.station.closed.wait(2))
            release.set()
            closer.join(4)
        self.assertFalse(closer.is_alive())
        self.assertEqual(job["state"], "interrupted")
        self.assertEqual(outcome_box[0]["state"], "stopped")
        self.assertEqual((self.station.archive / "preserved-original.cu8").read_bytes(),
                         b"\x7f\x80")

    def test_owned_satdump_mock_is_cancelled_without_deleting_input_or_images(self):
        name = "synthetic-meteor-input.cu8"
        original = self.station.archive / name
        original.write_bytes(b"\x7f\x80" * 5)
        prior_image = self.station.archive / "keep-preexisting.png"
        prior_image.write_bytes(b"ALREADY SAVED IMAGE")
        entered = threading.Event()
        decoder = FakeChild()
        errors = []

        def fake_spawn(cmd, **kwargs):
            self.assertEqual(cmd[0], "/synthetic/satdump")
            self.station.owned_processes.add(decoder)
            entered.set()
            return decoder

        def decode():
            try:
                self.station.decode_meteor(name)
            except RuntimeError as exc:
                errors.append(str(exc))

        with mock.patch.object(satellite, "meteor_capture", return_value=True), \
             mock.patch.object(satellite.shutil, "which", return_value="/synthetic/satdump"), \
             mock.patch.object(self.station, "_launch_receiver", side_effect=fake_spawn), \
             mock.patch.object(satellite, "stop_process", side_effect=stop_fake):
            thread = threading.Thread(target=decode)
            thread.start()
            self.assertTrue(entered.wait(2), "fake SatDump was not admitted")
            result = self.station.close()
            thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(result["state"], "stopped")
        self.assertTrue(errors)
        self.assertTrue(any("canceled" in error.lower() for error in errors))
        self.assertGreaterEqual(decoder.stop_calls, 1)
        self.assertEqual(original.read_bytes(), b"\x7f\x80" * 5)
        self.assertEqual(prior_image.read_bytes(), b"ALREADY SAVED IMAGE")
        self.assertFalse(self.station.decoder_active)

    def test_bounded_quit_reports_incomplete_owned_wav_postprocess(self):
        # A fake in-memory conversion session must not yield a false "released".
        self.station.postprocess_active = True
        incomplete = self.station.close(timeout_seconds=0.03)
        self.assertEqual(incomplete["state"], "stop_failed_partial")
        self.assertTrue(incomplete["owned_postprocess_worker_alive"])
        self.station.postprocess_active = False
        complete = self.station.close(timeout_seconds=0.2)
        self.assertTrue(complete["app_released"])
        self.assertFalse(complete["owned_postprocess_worker_alive"])

    def test_qt_unjoinable_capture_marker_never_receives_thread_join(self):
        class FakeQtDummy:
            def join(self, *args):
                raise AssertionError("Qt thread must not be joined as Python thread")

            def is_alive(self):
                raise AssertionError("Qt dummy thread lifetime cannot be polled")

        self.station.active_worker = FakeQtDummy()
        incomplete = self.station.close(timeout_seconds=0.03)
        self.assertEqual(incomplete["state"], "stop_failed_partial")
        self.assertTrue(incomplete["owned_capture_worker_alive"])
        self.station.active_worker = None
        self.assertEqual(self.station.close(timeout_seconds=0.2)["state"], "stopped")

    def test_invalid_decoder_does_not_reserve_worker_or_launch_satdump(self):
        with self.assertRaises(ValueError):
            self.station.decode_meteor("not-a-meteor")
        self.assertFalse(self.station.decoder_active)
        outcome = self.station.close()
        self.assertEqual(outcome["state"], "stopped")


if __name__ == "__main__":
    unittest.main()
