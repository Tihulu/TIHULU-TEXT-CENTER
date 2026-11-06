"""Portable tests for installed companion's source-attributed satellite imagery."""
import ast
from datetime import datetime, timezone, timedelta
from pathlib import Path
import unittest
from satellite_center.capture_naming import (
    recording_name, safe_satellite, meteor_capture, PROFILE_TARGETS,
)

ROOT = Path(__file__).resolve().parents[1] / "satellite_center"


class SatelliteImagesCrossPlatformTests(unittest.TestCase):
    def test_new_iq_utc_name_on_all_operating_systems(self):
        stamp = datetime(2026, 11, 6, 10, 15, 19, tzinfo=timezone.utc)
        name = recording_name(satellite="ISS (ZARYA) SSTV candidate",
                              timestamp=stamp, frequency_hz=437550000,
                              sample_rate=1024000, kind="IQ", extension=".cu8")
        self.assertEqual(name, "TIHULU_ISS-ZARYA-SSTV-CANDIDATE_20261106T101519Z_437550000Hz_1024000SPS_IQ.cu8")
        self.assertNotIn("/", name)
        self.assertEqual(safe_satellite("METEOR M2-4"), "METEOR-M2-4")
        self.assertEqual(recording_name(
            satellite="METEOR-M2-3",
            timestamp=datetime(2026, 11, 6, 11, 15, 19, tzinfo=timezone(timedelta(hours=1))),
            frequency_hz=137900000, sample_rate=1024000,
            extension=".cu8"), "TIHULU_METEOR-M2-3_20261106T101519Z_137900000Hz_1024000SPS_IQ.cu8")

    def test_decoder_meteor_filename_compatibility(self):
        self.assertTrue(meteor_capture(
            "TIHULU_METEOR-M2-4-CANDIDATE_20261106T101519Z_137900000Hz_1024000SPS_IQ.cu8"))
        self.assertTrue(meteor_capture("20261031T150000Z_1234567_meteor_backup.cu8"))
        self.assertFalse(meteor_capture("../x_meteor.cu8"))
        self.assertFalse(meteor_capture("TIHULU_ISS-SSTV-CANDIDATE_20261106T101519Z_437550000Hz_1024000SPS_IQ.cu8"))

    def test_receive_only_profile_and_python_syntax(self):
        source = (ROOT / "__main__.py").read_text(encoding="utf-8")
        ast.parse(source)
        self.assertIn('"iss_sstv":', source)
        self.assertIn('437550000', source)
        self.assertIn('satellite=nearest.get("satellite")', source)
        self.assertIn('target = self.archive/recording_name(', source)
        self.assertIn('meteor_m2-x_lrpt_80k', source)
        self.assertIn('from .capture_naming import', source)

    def test_same_origin_web_works_with_local_app_without_static_file_escape(self):
        source = (ROOT / "__main__.py").read_text(encoding="utf-8")
        self.assertIn('def browser_static(self, route):', source)
        self.assertIn('re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", name)', source)
        self.assertIn('self.send_header("X-Frame-Options", "SAMEORIGIN")', source)
        self.assertIn('frame-src \'self\'', source)
        for path in ("browser/index.html", "browser/satellite_maps.mjs",
                     "browser/orbit_clock.mjs", "browser/satellite_images_ui.mjs",
                     "browser/sstv_robot36.mjs", "browser/fm_iq_demod.mjs",
                     "browser/satellite_imagery.mjs"):
            self.assertTrue((ROOT / path).exists(), path)

    def test_desktop_uses_same_browser_renderer_and_source_attribution(self):
        page = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="open-live-workspace"', page)
        self.assertIn('id="satellite-live-frame"', page)
        self.assertIn('new URL("./browser/index.html",location.href)', page)
        self.assertIn('SatDump', page)
        self.assertIn("Decode Meteor LRPT ", page)
        self.assertIn('variant', page)


if __name__ == "__main__":
    unittest.main()
