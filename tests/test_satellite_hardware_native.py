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

    def test_usb_open_only_does_not_arm_rf_or_claim_iq(self):
        self.station.disconnect_receiver()
        proc = _FakeProcess(b"Using device 0: Generic RTL2832U OEM\\n")
        with patch("satellite_center.__main__.shutil.which", return_value="/usr/bin/rtl_test"), patch.object(
            self.station, "_acquire"
        ), patch.object(self.station, "_release") as release, patch.object(
            self.station, "_launch_receiver", return_value=proc
        ), patch("satellite_center.__main__.stop_process"):
            result = self.station.usb_test()
        self.assertEqual(result["state"], "usb_receiver_opened")
        self.assertFalse(self.station.receiver_enabled)
        self.assertIsNone(self.station.receiver_last_sample)
        self.assertFalse(self.station.launching)
        release.assert_called_once()

    def test_native_desktop_labels_separate_usb_access_from_connect(self):
        bridge = (Path(__file__).resolve().parents[1] /
                  "satellite_center" / "native_desktop_bridge.js").read_text(
                      encoding="utf-8")
        self.assertIn("Connect & enable RF (USB + real IQ)", bridge)
        self.assertIn("USB access check only (does not enable RF)", bridge)
        self.assertIn("USB ACCESS DIAGNOSTIC PASS", bridge)
        self.assertIn("RF is still DISABLED", bridge)

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

    def test_dual_native_capture_uses_same_iq_file_for_real_fm_conversion(self):
        report={"output_wav":str(self.station.archive/"from_real_iq_fm.wav")}
        with patch.object(self.station,"capture",return_value={
            "file":"native_real_recording.cu8","mode":"iq","bytes":1048576
        }) as captured, patch(
            "satellite_center.native_signal_tools.fm_to_wav",return_value=report
        ) as demodulated:
            result=self.station.capture_dual("iss_sstv",30)
        self.assertEqual(result["mode"],"iq_and_fm_wav")
        self.assertEqual(result["wav"],"from_real_iq_fm.wav")
        self.assertEqual(captured.call_args.args[:3],("iss_sstv","iq",30))
        self.assertEqual(demodulated.call_args.args[0],
                         self.station.archive/"native_real_recording.cu8")
        with self.assertRaisesRegex(ValueError,"ISS audio profile"):
            self.station.capture_dual("meteor",30)

    def test_local_tle_import_is_bounded_and_never_claims_a_downlink(self):
        source=self.path/"saved_iss.tle"
        source.write_text("\n".join([
            "ISS (ZARYA)",
            ("1 25544U 98067A   26311.35246347  .00001234  00000-0  29639-4 0  9996").ljust(70),
            ("2 25544  51.6345 159.7912 0005428  79.9879  38.5994 15.50433348711115").ljust(70),
        ])+"\n")
        report=self.station.import_tle(source,"iss")
        self.assertEqual(report["tle_count"],1)
        self.assertFalse(report["radio_signal_verified"])
        self.assertTrue((self.path/"iss.tle").is_file())
        with self.assertRaisesRegex(ValueError,"does not match"):
            self.station.import_tle(source,"meteor3")

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
