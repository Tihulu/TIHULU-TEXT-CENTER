"""USB setup diagnostic tests; uses only synthetic tools, never opens real RTL hardware."""
from pathlib import Path
from unittest.mock import patch
import subprocess
import sys
import tempfile
import unittest

from satellite_center.__main__ import Station


class UsbDiagnosticsTests(unittest.TestCase):
    def test_usb_check_requires_installed_rtl_test(self):
        with tempfile.TemporaryDirectory() as td:
            station = Station(Path(td))
            try:
                with patch("satellite_center.__main__.shutil.which", return_value=None):
                    with self.assertRaisesRegex(RuntimeError, "rtl_test is missing"):
                        station.usb_test()
            finally:
                station.close()

    def test_readsb_conflict_blocks_usb_check_and_does_not_stop_readsb(self):
        with tempfile.TemporaryDirectory() as td:
            station = Station(Path(td))
            try:
                with patch("satellite_center.__main__.shutil.which", return_value="rtl_test"), \
                     patch("satellite_center.__main__.tuner_present", return_value=True), \
                     patch("satellite_center.__main__.detect_busy",
                           return_value=[{"process": "readsb"}]):
                    with self.assertRaisesRegex(RuntimeError, "readsb|Another receiver"):
                        station.usb_test()
                self.assertIsNone(station.process)
                self.assertIsNone(station.device_lock)
            finally:
                station.close()

    def test_fake_rtl_usb_open_then_release_without_claiming_signal(self):
        with tempfile.TemporaryDirectory() as td:
            station = Station(Path(td))
            lockfile = Path(td)/"receiver"/"rtl_fm_rds.lock"
            original = station._launch_receiver

            def mock_launcher(command, **kwargs):
                # Do not require rtl_test or a USB dongle in CI: create only a
                # synthetic child emitting the marker used by rtl_test.
                return original([sys.executable, "-c",
                    "import sys;sys.stderr.write('Found 1 device(s)\\nUsing device 0: Mock RTL2832U\\nFound Rafael Micro R820T tuner\\n')"],
                    **kwargs)
            try:
                with patch("satellite_center.__main__.TEXT_CENTER_LOCK", lockfile), \
                     patch("satellite_center.__main__.shutil.which", return_value="rtl_test"), \
                     patch("satellite_center.__main__.tuner_present", return_value=True), \
                     patch("satellite_center.__main__.detect_busy", return_value=[]), \
                     patch.object(station, "_launch_receiver", side_effect=mock_launcher):
                    result = station.usb_test()
                self.assertEqual(result["state"], "usb_receiver_opened")
                self.assertFalse(result["satellite_identified"])
                self.assertFalse(result["signal_decoded"])
                self.assertIsNone(station.device_lock)
                self.assertIsNone(station.process)
                self.assertFalse(station.launching)
                self.assertEqual(len(station.owned_processes), 0)
            finally:
                station.close()


if __name__ == "__main__":
    unittest.main()
