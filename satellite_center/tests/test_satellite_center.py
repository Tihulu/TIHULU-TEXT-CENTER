"""Synthetic only: no SDR probing, orbital network or receiver process needed."""
import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from satellite_center.__main__ import (Station, allowed_mode, parse_power,
                                       parse_tle, PROFILES)


class SatelliteTests(unittest.TestCase):
    def test_allowed_modes_and_iridium_privacy(self):
        self.assertTrue(allowed_mode('meteor', 'iq'))
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

    def test_missing_pass_cannot_be_scheduled(self):
        with tempfile.TemporaryDirectory() as td:
            app=Station(Path(td))
            with self.assertRaises(ValueError):
                app.schedule('fake:12345', 'meteor', 'iq')
            self.assertEqual(app.jobs, [])


if __name__ == '__main__': unittest.main()
