"""No-hardware safety contract for the native Satellite Center Hardware panel."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from satellite_center.__main__ import (
    Station, _linux_usb_receiver_inventory,
)


class _FakeProcess:
    returncode = 0

    def __init__(self, data):
        self.data = data

    def communicate(self, timeout=None):
        return self.data, b"Found Rafael Micro tuner\n"

    def poll(self):
        return 0


class NativeHardwareTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.station = Station(self.path)
        self.addCleanup(self.station.close)

    def test_disconnect_persists_and_blocks_new_rf_capture_and_auto_planning(self):
        self.station.jobs = [{
            "id": "one", "state": "pending", "run_at": "2099-01-01T00:00:00+00:00",
            "aos": "2099-01-01T00:00:00+00:00",
        }]
        result = self.station.disconnect_receiver()
        self.assertFalse(result["receiver_enabled"])
        self.assertTrue(result["app_released"])
        self.assertEqual(result["pending_jobs_paused"], 1)
        self.assertEqual(self.station.jobs[0]["state"], "pending")
        self.assertFalse(self.station.status()["hardware"]["receiver_enabled"])
        with self.assertRaisesRegex(RuntimeError, "disabled in Hardware"):
            self.station.auto_schedule(["meteor-m2-3"])
        with self.assertRaisesRegex(RuntimeError, "disabled in Hardware"):
            self.station.capture("meteor", "iq", 8)
        self.station.close()
        new = Station(self.path)
        self.addCleanup(new.close)
        self.assertFalse(new.receiver_enabled)
        self.assertFalse(new.scheduler_thread and new.scheduler_thread.is_alive())

    def test_connection_requires_both_physical_open_and_actual_iq_samples(self):
        self.station.disconnect_receiver()
        usb = {"state": "usb_receiver_opened", "evidence": "rtl_test device access"}
        iq = {"state": "real_iq_samples_received", "sample_bytes": 1048576,
              "evidence": "physical rtl_sdr sample"}
        with patch.object(self.station, "usb_test", return_value=usb), patch.object(
            self.station, "sample_test", return_value=iq
        ):
            result = self.station.connect_receiver()
        self.assertTrue(result["receiver_enabled"])
        self.assertEqual(result["sample_test"]["sample_bytes"], 1048576)
        self.assertTrue(self.station.status()["hardware"]["receiver_enabled"])
        self.station.disconnect_receiver()
        with patch.object(self.station, "usb_test", return_value=usb), patch.object(
            self.station, "sample_test", side_effect=RuntimeError("USB busy")
        ):
            with self.assertRaisesRegex(RuntimeError, "USB busy"):
                self.station.connect_receiver()
        self.assertFalse(self.station.receiver_enabled)

    def test_explicit_test_does_not_enable_receiver_and_releases_it(self):
        self.station.disconnect_receiver()
        fake = _FakeProcess(bytes([120, 140] * 524288))
        with patch("satellite_center.__main__.shutil.which", return_value="/usr/bin/rtl_sdr"), patch.object(
            self.station, "_acquire"
        ), patch.object(self.station, "_release"), patch.object(
            self.station, "_launch_receiver", return_value=fake
        ), patch("satellite_center.__main__.stop_process"):
            result = self.station.sample_test(137900000)
        self.assertEqual(result["sample_bytes"], 1048576)
        self.assertEqual(result["complex_samples"], 524288)
        self.assertFalse(result["satellite_identified"])
        self.assertFalse(self.station.launching)
        self.assertIsNone(self.station.process)
        self.assertFalse(self.station.receiver_enabled)

    def test_sample_test_rejects_invented_frequency(self):
        with self.assertRaisesRegex(ValueError, "published receive-only"):
            self.station.sample_test(9999)

    def test_usb_inventory_identifies_tuner_types_without_opening(self):
        root = self.path / "fake-sysfs"
        rtl = root / "1-2"
        tv = root / "1-3"
        rtl.mkdir(parents=True)
        tv.mkdir()
        for directory, vendor, product, name in (
            (rtl, "0bda", "2838", "RTL2838 SDR"),
            (tv, "2040", "0265", "Hauppauge TV"),
        ):
            (directory / "idVendor").write_text(vendor)
            (directory / "idProduct").write_text(product)
            (directory / "product").write_text(name)
        found = _linux_usb_receiver_inventory(root)
        self.assertEqual({x["receiver_type"] for x in found},
                         {"rtl_sdr", "dvb_tv_not_generic_iq"})
        self.assertTrue(all("usb_present" in x for x in found))

    def test_status_cannot_claim_released_during_active_capture(self):
        self.station.session["active"] = True
        self.assertFalse(self.station.status()["hardware"]["app_released"])


if __name__ == "__main__":
    unittest.main()
