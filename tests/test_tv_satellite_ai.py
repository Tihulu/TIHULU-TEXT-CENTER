import hashlib
import tempfile
from pathlib import Path
import unittest

from tv_center.satellite import SATELLITES, satellite_scan_args, satellite_followup_args
from tv_center.channel_prefs import ChannelPreferences, profile_key
from tv_center.ai_settings import AISettings
from tv_center.model_market import ModelLibrary, ModelError, CATALOG
from tv_center.scanner import scan_commands, parse_scan_progress
from tv_center.core import Channel, read_channels

class SatelliteAndAISettingsTests(unittest.TestCase):
    def test_satellite_scan_is_not_terrestrial_country(self):
        args = satellite_scan_args(1, "S42E0", 0)
        self.assertEqual(args[:6], ["w_scan_cpp", "-f", "s", "-s", "S42E0", "-a"])
        self.assertIn("UNIVERSAL", args)
        self.assertEqual(args[-2:], ["-D", "0c"])
        first, follow = scan_commands("TR", "s", 1, Path("/tmp/sat"), Path("/tmp/services"),
                                      satellite="S42E0", diseqc_port=0)
        self.assertEqual(first, args)
        self.assertIn("-l", follow)
        self.assertEqual(profile_key("TR", "s", "S42E0"), "TR-s-S42E0")
        with self.assertRaises(ValueError):
            satellite_scan_args(0, "made-up-satellite")
        with self.assertRaises(ValueError):
            satellite_scan_args(0, "S42E0", 7)

    def test_scan_log_never_invents_service(self):
        d = parse_scan_progress("new channel: KiKA HD")
        self.assertEqual(d["service_reported"], "KiKA HD")
        self.assertIsNone(parse_scan_progress(""))
        self.assertIsNone(parse_scan_progress("   "))

    def test_satellite_frequency_and_radio_type(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/"sat.conf"
            path.write_text("[TRT RADYO]\nFREQUENCY=12000000000\n"
                            "SERVICE_ID=512\nDELIVERY_SYSTEM=DVBS2\nSERVICE_TYPE=2\n")
            channels = read_channels([path])
            self.assertEqual(channels[0].frequency, 12000000000)
            self.assertEqual(channels[0].kind, "radio")

    def test_rescan_preserves_favorites_and_new_services_not_auto_added(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = ChannelPreferences(Path(tmp)/"favorites.json")
            path = Path(tmp)/"channels.conf"
            old = Channel("KiKA", path, 538000000, 101)
            other = Channel("ZDF", path, 538000000, 102)
            rows = p.rows("DE-t", [old])
            self.assertTrue(rows[0]["included"])
            rows[0]["favorite"] = True
            p.save_rows("DE-t", rows)
            reread = ChannelPreferences(Path(tmp)/"favorites.json")
            merged = reread.rows("DE-t", [old, other])
            self.assertTrue(merged[0]["favorite"])
            self.assertTrue(merged[0]["included"])
            self.assertTrue(merged[1]["new"])
            self.assertFalse(merged[1]["included"])

    def test_ai_off_by_default_and_persists(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/"ai.json"
            cfg = AISettings(path)
            self.assertFalse(cfg.values["asr_enabled"])
            self.assertFalse(cfg.values["translation_enabled"])
            cfg.update({"backend":"gpu","asr_enabled":True})
            self.assertTrue(AISettings(path).values["asr_enabled"])
            with self.assertRaises(ValueError): cfg.update({"backend":"unverified"})

    def test_model_sha_and_delete_only_managed_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            content = b"tiny-test-model"
            CATALOG["fake"] = {"name":"test","filename":"fake.bin","size_mb":1,
                "max_bytes":100, "sha256":hashlib.sha256(content).hexdigest()}
            try:
                root = Path(tmp)/"models"
                manager = ModelLibrary(root)
                local = Path(tmp)/"download.bin"
                local.write_bytes(content)
                manager.add_local("fake", local)
                self.assertTrue((root/"fake.bin").is_file())
                manager.remove("fake")
                self.assertFalse((root/"fake.bin").exists())
                self.assertTrue(local.is_file())
                local.write_bytes(b"tampered")
                with self.assertRaises(ModelError): manager.add_local("fake", local)
            finally:
                del CATALOG["fake"]
