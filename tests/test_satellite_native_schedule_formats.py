"""Regression checks for native SDR pass scheduling / format compatibility.

Hardware-free tests. Never claim that an RF signal or decoder was verified.
"""
from datetime import timedelta
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from satellite_center.__main__ import Station, now, stamp


class NativePassFormatTests(unittest.TestCase):
    def test_meteor_300_second_iq_is_one_native_scheduled_job(self):
        with tempfile.TemporaryDirectory() as tmp:
            station = Station(Path(tmp))
            try:
                station.receiver_enabled = True
                aos = now() + timedelta(minutes=10)
                los = aos + timedelta(minutes=12)
                pass_id = "59051:synthetic"
                station.predicted = {
                    pass_id: {
                        "id": pass_id, "norad": 59051, "name": "METEOR-M2 4",
                        "family": "meteor", "profiles": ["meteor", "meteor_backup"],
                        "aos": stamp(aos), "los": stamp(los),
                    },
                }
                with patch("satellite_center.__main__.shutil.disk_usage") as usage, patch.object(
                    station, "start_scheduler"
                ):
                    usage.return_value.free = 6_000_000_000
                    job = station.schedule(
                        pass_id, "meteor", "iq",
                        stamp(aos + timedelta(seconds=20)), 300,
                        sample_rate=1024000,
                    )
                    self.assertEqual(job["mode"], "iq")
                    self.assertEqual(job["capture_seconds"], 300)
                    self.assertEqual(job["sample_rate"], 1024000)
                    self.assertEqual(job["estimated_bytes"], 614_400_000)
                    self.assertEqual(len(station.jobs), 1)

                    with self.assertRaisesRegex(ValueError, "requires original raw IQ"):
                        station.schedule(
                            pass_id, "meteor", "sstv_audio",
                            stamp(aos + timedelta(seconds=25)), 60,
                        )
                    with self.assertRaisesRegex(ValueError, "requires original raw IQ"):
                        station.schedule(
                            pass_id, "meteor", "iq_and_fm_wav",
                            stamp(aos + timedelta(seconds=25)), 60,
                        )
                    self.assertEqual(len(station.jobs), 1)
            finally:
                station.close()

    def test_flight_radar_readsb_conflict_is_diagnostic_not_auto_killed(self):
        with tempfile.TemporaryDirectory() as tmp:
            station = Station(Path(tmp))
            try:
                with patch("satellite_center.__main__.tuner_present", return_value=True), patch(
                    "satellite_center.__main__.detect_busy",
                    return_value=[{"process": "readsb", "pid": 12345}],
                ):
                    with self.assertRaisesRegex(RuntimeError, "Flight Radar/readsb"):
                        station._acquire()
                self.assertIsNone(station.device_lock)
            finally:
                station.close()

    def test_failed_native_receiver_includes_real_stderr_and_releases_child(self):
        class FakeProcess:
            returncode = 1

            def poll(self):
                return 1

        with tempfile.TemporaryDirectory() as tmp:
            station = Station(Path(tmp))
            fake = FakeProcess()

            def fake_launch(_cmd, **kwargs):
                kwargs["stderr"].write(b"usb_claim_interface error -6\\n")
                return fake

            try:
                with patch.object(station, "_launch_receiver", side_effect=fake_launch), patch(
                    "satellite_center.__main__.stop_process"
                ) as stop:
                    with self.assertRaisesRegex(RuntimeError, "usb_claim_interface error -6"):
                        station._run_bounded(["rtl_sdr", "-n", "8192"], 1)
                    stop.assert_called_once_with(fake)
                    self.assertIsNone(station.process)
            finally:
                station.close()

    def test_shared_browser_and_qt_desktop_show_native_contract(self):
        root = Path(__file__).resolve().parents[1] / "satellite_center"
        browser = (root / "browser" / "browser.js").read_text(encoding="utf-8")
        desktop = (root / "native_desktop_bridge.js").read_text(encoding="utf-8")
        service = (root / "__main__.py").read_text(encoding="utf-8")

        self.assertIn('durationSeconds>900?"/api/schedule-chain":"/api/schedule"', browser)
        self.assertIn("Native direct-to-disk:", browser)
        self.assertIn('if(pass.family==="meteor"&&!saveRaw)', browser)
        self.assertIn("Meteor LRPT must be saved as raw IQ.", browser)
        self.assertIn("enhanceNativePassForm", desktop)
        self.assertIn("wav.disabled=!supportsWav", desktop)
        self.assertIn("No WebUSB, browser downloads", desktop)
        self.assertIn("hardwareState.verified=Boolean(hw.last_real_sample?.sample_bytes)", desktop)
        self.assertIn("OTHER SDR ACTIVE", desktop)
        self.assertIn("manualDuration.min='8'", desktop)
        self.assertIn("manualDuration.max='900'", desktop)
        self.assertIn("The previous 6-second input is not supported", desktop)
        self.assertIn("Native direct-to-disk: 1 continuous", desktop)
        self.assertIn('sample_rate=data.get("sample_rate", 1024000)', service)


if __name__ == "__main__":
    unittest.main()
