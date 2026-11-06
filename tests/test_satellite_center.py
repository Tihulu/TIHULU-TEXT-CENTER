"""Synthetic only: no SDR probing, orbital network or receiver process needed."""
import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from satellite_center.__main__ import (Station, allowed_mode, parse_power,
                                       parse_tle, PROFILES, topocentric_elevation_deg)


class SatelliteTests(unittest.TestCase):
    def test_altaz_ordering_is_elevation_not_azimuth(self):
        class Angle:
            def __init__(self, degrees):
                self.degrees = degrees
        class Position:
            def altaz(self):
                return (Angle(42.7), Angle(268.4), object())
        self.assertEqual(topocentric_elevation_deg(Position()), 42.7)
        class InvalidPosition:
            def altaz(self):
                return (Angle(268.4), Angle(42.7), object())
        with self.assertRaisesRegex(ValueError, 'Invalid topocentric elevation'):
            topocentric_elevation_deg(InvalidPosition())

    def test_allowed_modes_and_iridium_privacy(self):
        self.assertTrue(allowed_mode('meteor', 'iq'))
        self.assertTrue(allowed_mode('meteor_backup', 'iq'))
        self.assertTrue(allowed_mode('iss_aprs', 'aprs'))
        self.assertFalse(allowed_mode('iridium', 'iq'))
        self.assertFalse(allowed_mode('cubesat_vhf', 'sstv_audio'))
        self.assertEqual(PROFILES['iridium']['freq'], None)

    def test_spectrum_unverified_only(self):
        s='2026-11-06, 10:00:00, 1616000000, 1616200000, 50000, 1, -50, -50, -20, -51\n'
        value=parse_power(s, 'iridium')
        self.assertEqual(len(value['measured_bins']), 4)
        self.assertNotIn('satellite', value)
        self.assertIn('NOT proven', value['warning'])

    def test_malformed_tle_is_not_a_satellite(self):
        self.assertEqual(parse_tle('IRIDIUM\n1 41917X\n2 33333X\n'), [])

    @patch('satellite_center.__main__.tuner_present', return_value=False)
    def test_no_sdr_fails_closed(self, _):
        with tempfile.TemporaryDirectory() as td:
            app=Station(Path(td))
            with self.assertRaisesRegex((RuntimeError, ValueError), 'RTL2832U|Required'):
                app.capture('meteor', 'survey', 18)
            self.assertFalse(app.session['active'])
            self.assertEqual(list((Path(td)/'captures').iterdir()), [])

    def test_native_long_iridium_iq_is_rf_only_and_profile_allowlisted(self):
        from datetime import timedelta
        from satellite_center.__main__ import now, stamp
        self.assertFalse(allowed_mode("iridium","iq"))
        self.assertTrue(allowed_mode("iridium_rf_iq","iq"))
        with tempfile.TemporaryDirectory() as td:
            app=Station(Path(td))
            start=now()+timedelta(minutes=7)
            stop=start+timedelta(minutes=14)
            app.predicted={"fake:pass":{"id":"fake:pass","norad":12345,
                "name":"IRIDIUM candidate","family":"iridium",
                "profiles":["iridium","iridium_rf_iq"],
                "aos":stamp(start),"los":stamp(stop)}}
            try:
                with patch("satellite_center.__main__.shutil.disk_usage") as usage:
                    usage.return_value.free=5_000_000_000
                    job=app.schedule("fake:pass","iridium_rf_iq","iq",
                                     stamp(start+timedelta(seconds=20)),360)
                self.assertEqual(job["capture_seconds"],360)
                self.assertEqual(job["estimated_bytes"],360*2048000)
                self.assertEqual(job["data_kind"],"raw RF energy")
                self.assertEqual(job["state"],"pending")
                with self.assertRaisesRegex(ValueError,"overlap"):
                    app.schedule("fake:pass","iridium_rf_iq","iq",
                                 stamp(start+timedelta(seconds=60)),60)
                with self.assertRaisesRegex(ValueError,"Unsupported"):
                    app.schedule("fake:pass","iridium","iq")
            finally:
                app.close()

    def test_missing_pass_cannot_be_scheduled(self):
        with tempfile.TemporaryDirectory() as td:
            app=Station(Path(td))
            with self.assertRaises(ValueError):
                app.schedule('fake:12345', 'meteor', 'iq')
            self.assertEqual(app.jobs, [])


if __name__ == '__main__': unittest.main()
