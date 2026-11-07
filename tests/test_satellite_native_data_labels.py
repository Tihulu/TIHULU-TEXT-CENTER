"""File-format labels shown in the native Qt archive/result lists."""
import tempfile
import unittest
from pathlib import Path

from satellite_center.native_data_labels import describe_local_file


class NativeDataLabelsTests(unittest.TestCase):
    def test_raw_iq_is_not_called_an_image_or_decoded_audio(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "capture_137900000Hz.cu8"
            path.write_bytes(bytes([127, 127]) * 100)
            label, explanation = describe_local_file(path)
            self.assertEqual(label, "RAW RF · CU8")
            self.assertIn("No image", explanation)

    def test_image_and_audio_headers_are_required(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            png = root / "picture.png"
            png.write_bytes(b"\x89PNG\r\n\x1a\n" + bytes(8))
            self.assertEqual(describe_local_file(png)[0], "IMAGE · PNG")
            jpeg = root / "photo.jpg"
            jpeg.write_bytes(b"\xff\xd8\xff\xe0" + bytes(12))
            self.assertEqual(describe_local_file(jpeg)[0], "IMAGE · JPEG")
            wav = root / "audio.wav"
            wav.write_bytes(b"RIFF" + bytes(4) + b"WAVEfmt ")
            self.assertEqual(describe_local_file(wav)[0], "AUDIO · WAV")
            wav.write_bytes(b"not a wav file")
            self.assertTrue(describe_local_file(wav)[0].startswith("INVALID?"))
            png.write_bytes(b"not a PNG file")
            self.assertTrue(describe_local_file(png)[0].startswith("INVALID?"))

    def test_reports_are_not_misrepresented_as_decoded_media(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for filename, expected in [
                ("metadata.json", "DATA · JSON"),
                ("aprs.txt", "TEXT · TXT"),
                ("spectrum.csv", "TABLE · CSV"),
                ("orbit.geojson", "MAP DATA · GeoJSON"),
                ("bundle.zip", "ARCHIVE · ZIP"),
                ("unknown.bin", "OTHER · FILE"),
            ]:
                self.assertEqual(describe_local_file(root / filename)[0], expected)
            self.assertIn("not RF measurements",
                          describe_local_file(root / "orbit.geojson")[1])

    def test_missing_media_cannot_be_verified(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertTrue(describe_local_file(Path(td) / "absent.png")[0].startswith("UNREADABLE"))


if __name__ == "__main__":
    unittest.main()
