"""STAND-SAT isolated negative contracts (no other TIHULU packages or radio).

These tests complement, rather than replace, the existing Satellite USB,
EXIT-01 and Debian package CI. No actual tuner, network, Qt or SatDump is used.
"""
from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from satellite_center import __main__ as satellite
from satellite_center import bridge


class StandaloneSatelliteContractTests(unittest.TestCase):
    def test_textcenter_modules_absent_keeps_linux_receiver_diagnostics_available(self):
        """STAND-03/07: no compulsory import of Text Center for safe RF refusal."""
        with mock.patch.dict(sys.modules, {
            "textcenter": None,
            "textcenter.conflicts": None,
            "textcenter.receivers": None,
        }), mock.patch.object(satellite.platform, "system", return_value="Linux"), \
             mock.patch.object(satellite, "_linux_receiver_processes",
                               return_value=[{"process": "readsb", "pid": 31415}]) as processes, \
             mock.patch.object(satellite, "_linux_rtl_usb_count", return_value=1) as count:
            self.assertEqual(satellite.detect_busy(),
                             [{"process": "readsb", "pid": 31415}])
            self.assertTrue(satellite.tuner_present())
            count.assert_called_once_with()
            processes.assert_called_once_with()

    def test_missing_textcenter_with_two_rtl_receivers_refuses_single_tuner_claim(self):
        """STAND-07: a second dongle must not be mislabelled one unique radio."""
        with mock.patch.dict(sys.modules, {
            "textcenter": None, "textcenter.receivers": None,
        }), mock.patch.object(satellite.platform, "system", return_value="Linux"), \
             mock.patch.object(satellite, "_linux_rtl_usb_count", return_value=2):
            self.assertFalse(satellite.tuner_present())

    def test_settings_roots_are_namespaced_for_linux_macos_and_windows(self):
        """STAND-05: path selection never selects the Text/Flight/Media store."""
        with tempfile.TemporaryDirectory(prefix="stand-sat-paths-") as tmp:
            home = Path(tmp) / "clean-home"
            local = Path(tmp) / "AppData" / "Local"
            with mock.patch.object(bridge.Path, "home", return_value=home), \
                 mock.patch.dict(os.environ, {"LOCALAPPDATA": str(local)}):
                for system, expected in (
                    ("Linux", home / ".local/share/tihulu-satellite-center"),
                    ("Darwin", home / "Library/Application Support/TihuluSatelliteCenter"),
                    ("Windows", local / "Tihulu/SatelliteCenter"),
                ):
                    with self.subTest(system=system), \
                         mock.patch.object(bridge.platform, "system", return_value=system):
                        data = bridge.app_data_dir()
                        self.assertEqual(data, expected)
                        self.assertNotIn("tihulu-text-center", str(data).lower())
                        self.assertFalse(data.exists(), "Path selection must not create data")

    def test_new_profile_is_idle_without_other_app_or_receiver_children(self):
        """STAND-02/04/08: a clean Station is on-demand and owns only its data."""
        with tempfile.TemporaryDirectory(prefix="stand-sat-clean-") as tmp:
            root = Path(tmp)
            foreign = root / "other-app-recording.cu8"
            foreign.write_bytes(b"EXTERNAL RECORDING - DO NOT MODIFY")
            data = root / "isolated-satellite-settings"
            with mock.patch.object(satellite, "start_receiver_process",
                                   side_effect=AssertionError("No receiver may launch")), \
                 mock.patch.object(satellite, "urlopen",
                                   side_effect=AssertionError("No TLE fetch on startup")):
                station = satellite.Station(data)
                try:
                    self.assertEqual(station.jobs, [])
                    self.assertIsNone(station.scheduler_thread)
                    self.assertIsNone(station.process)
                    self.assertEqual(station.owned_processes, set())
                    self.assertIsNone(station.device_lock)
                    self.assertFalse(station.closed.is_set())
                    self.assertEqual(station.archive, data / "captures")
                    self.assertTrue((data / "pages-pairing.key").is_file())
                    self.assertEqual(station.close(timeout_seconds=0.25)["state"], "stopped")
                finally:
                    station.close(timeout_seconds=0.25)
            self.assertEqual(foreign.read_bytes(), b"EXTERNAL RECORDING - DO NOT MODIFY")
            self.assertEqual(set(root.iterdir()), {foreign, data})

    def test_debian_packager_installs_satellite_assets_without_text_runtime(self):
        """STAND-01/03: source assembly copies only Satellite package assets.

        This is a scope check, not proof an isolated Debian apt install works.
        """
        root = Path(__file__).resolve().parents[1]
        script = (root / "satellite_center/packaging/debian/build.sh").read_text()
        for required in ("cp satellite_center/*.py", "cp -R satellite_center/browser",
                         "cp -R satellite_center/assets", "python3-pyqt5.qtwebengine",
                         "python3-skyfield", "rtl-sdr"):
            self.assertIn(required, script)
        for foreign_source in ("cp textcenter/", "cp tv_center/",
                               "cp rf_geolocation_center/", "cp tihulu_flight_radar/"):
            self.assertNotIn(foreign_source, script)
        self.assertIn("exec /usr/bin/python3 -m satellite_center", script)


if __name__ == "__main__":
    unittest.main()
