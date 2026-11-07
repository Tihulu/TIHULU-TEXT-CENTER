import unittest
from pathlib import Path
from tv_center.scanner import PROFILES, MODES, scan_commands

class CountryAutoScanTest(unittest.TestCase):
    def test_de_terrestrial(self):
        cmd, second = scan_commands("DE", "t", 0, Path("/tmp/freq.conf"), Path("/tmp/channels.conf"))
        self.assertEqual(cmd[:7], ["w_scan_cpp", "-f", "t", "-c", "DE", "-a", "0"])
        self.assertIn("-x", cmd)
        self.assertEqual(second[0], "dvbv5-scan")
        self.assertIn("DE", second)
    def test_tr_cable(self):
        cmd, second = scan_commands("TR", "c", 1, Path("/tmp/freq.conf"), Path("/tmp/channels.conf"))
        self.assertEqual(cmd[1:5], ["-f", "c", "-c", "TR"])
        self.assertIn("TR", second)
        self.assertEqual(set(PROFILES), {"DE", "TR"})
        self.assertEqual(set(MODES), {"t", "c", "s"})
    def test_reject_invalid_country_medium_adapter(self):
        for country, medium, adapter in [("FR", "t", 0), ("TR", "x", 0), ("DE", "c", -1), ("DE", "t", 100)]:
            with self.subTest(country=country, medium=medium, adapter=adapter), self.assertRaises(ValueError):
                scan_commands(country, medium, adapter, Path("/tmp/a"), Path("/tmp/b"))
