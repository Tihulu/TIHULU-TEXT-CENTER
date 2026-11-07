"""Conservative native file labels; no fake receiver/media provenance."""
import tempfile
import unittest
from pathlib import Path

from satellite_center.native_data_labels import describe_local_file


class NativeLocalFormatTests(unittest.TestCase):
    def test_video_audio_formats_are_checked_by_bounded_magic_header(self):
        samples={
            ".mp4":(b"\x00\x00\x00\x18ftypisom0000","VIDEO · MP4"),
            ".webm":(bytes((0x1a,0x45,0xdf,0xa3))+b"hello","VIDEO · WEBM"),
            ".gif":(b"GIF89a"+bytes(12),"IMAGE · GIF"),
            ".webp":(b"RIFF\x12\x00\x00\x00WEBPVP8 ","IMAGE · WEBP"),
            ".mp3":(b"ID3"+bytes(18),"AUDIO · MP3"),
            ".ogg":(b"OggS"+bytes(18),"AUDIO · OGG"),
            ".flac":(b"fLaC"+bytes(18),"AUDIO · FLAC"),
        }
        with tempfile.TemporaryDirectory() as td:
            for ext,(raw,expected) in samples.items():
                source=Path(td)/("capture_candidate"+ext)
                source.write_bytes(raw)
                label,why=describe_local_file(source)
                self.assertEqual(label,expected)
                self.assertIn("satellite origin",why)
                source.write_bytes(b"<html>not media</html>")
                invalid,_=describe_local_file(source)
                self.assertTrue(invalid.startswith("INVALID?"))


if __name__=="__main__":
    unittest.main()
