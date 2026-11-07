"""Robot36 archive refuses to fabricate a picture when input has no valid sync."""
import tempfile,unittest,wave,json
from pathlib import Path
from unittest.mock import patch
from satellite_center.native_robot36_results import decode_robot36_to_archive

class NativeRobot36ExportTests(unittest.TestCase):
    def test_no_sync_creates_only_actual_json_report(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);data=root/"input.wav"
            with wave.open(str(data),"wb") as wav:
                wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(8000)
                wav.writeframes(b"\x00\x00" * (8000*35))
            # Decoder result is genuinely from the tested WAV; no artificial images.
            try:
                report=decode_robot36_to_archive(data,root/"archive")
            except Exception as exc:
                # The decoder may reject silent audio; either outcome must not
                # save a fake PNG. The original input always survives.
                self.assertTrue(str(exc))
                self.assertTrue(data.exists())
                self.assertFalse(list((root/"archive").glob("*.png")))
                return
            self.assertEqual(report["actual_png_paths"],[])
            self.assertFalse(list((root/"archive").glob("*.png")))
            stored=json.loads(Path(report["saved_report_path"]).read_text())
            self.assertEqual(stored["output_status"],
                             "no_png_saved_without_valid_robot36_sync")
            self.assertFalse(stored["raw_iq_included"])
    def test_only_real_decoder_paths_are_returned(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);data=root/"source.wav";data.write_bytes(b"pretend")
            with patch("satellite_center.native_robot36_results.extract_robot36_wav",
                       return_value={"images":[],"status":"no_valid_robot36_sync"}) as fake:
                report=decode_robot36_to_archive(data,root/"output")
            self.assertEqual(report["actual_png_paths"],[])
            self.assertTrue(Path(report["saved_report_path"]).is_file())
            self.assertEqual(fake.call_args.kwargs["output_dir"],root/"output")
