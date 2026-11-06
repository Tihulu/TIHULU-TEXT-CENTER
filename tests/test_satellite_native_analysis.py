"""Real local CU8 FFT and ZIP integrity, no USB or satellite claims."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from satellite_center.native_analysis import (
    analyze_cu8, save_spectrum_report, export_results_zip, safe_report_name
)


class NativeAnalysisTests(unittest.TestCase):
    def test_filename_is_sanitized(self):
        self.assertEqual(safe_report_name("../some planet!.cu8"), "some_planet_spectrum.json")

    def test_real_synthetic_tone_does_not_claim_satellite(self):
        try:
            import numpy as np
        except ImportError:
            self.skipTest("python3-numpy optional on this runner")
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            rate=1_024_000
            n=2048*20
            t=np.arange(n)
            tone=90*np.exp(2j*np.pi*64*t/2048)
            iq=np.column_stack((np.clip(127.5+tone.real,0,255),
                                np.clip(127.5+tone.imag,0,255))).astype("uint8")
            source=root/"test.cu8"
            source.write_bytes(iq.tobytes())
            overview=analyze_cu8(source,rate,137900000,mode="overview")
            full=analyze_cu8(source,rate,137900000,mode="full")
            self.assertFalse(overview["complete_time_coverage"])
            self.assertTrue(full["complete_time_coverage"])
            self.assertEqual(full["complex_samples_analyzed"], n)
            self.assertAlmostEqual(full["strongest_spectrum_bin_hz"],137900000+64*rate/2048,delta=rate/2048)
            self.assertIn("no satellite",full["warnings"][0].lower())
            report=save_spectrum_report(source,full,root)
            dest=root/"outputs.zip"
            export_results_zip([report],dest,source=source)
            import zipfile
            with zipfile.ZipFile(dest) as bundle:
                self.assertEqual(len(bundle.namelist()),2)
                self.assertIn("manifest.json",bundle.namelist())
                self.assertFalse(__import__("json").loads(bundle.read("manifest.json"))["spacecraft_verified"])

    def test_refuse_raw_iq_inside_zip(self):
        with tempfile.TemporaryDirectory() as td:
            src=Path(td)/"raw.cu8"
            src.write_bytes(b"abcdef")
            with self.assertRaisesRegex(ValueError,"PNG/JPG/WAV"):
                export_results_zip([src],Path(td)/"results.zip")
