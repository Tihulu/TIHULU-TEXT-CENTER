"""Synthetic, explicitly non-RF Robot36 tests (no hardware acceptance)."""
import io
from pathlib import Path
import struct
import tempfile
import math
import unittest
import wave
import zlib

from satellite_center.sstv_series35 import (
    SERIES35, _line_alignment, _png, _syncs, extract_robot36_wav,
)

class Robot36Series35Test(unittest.TestCase):
    def test_public_event_profile_is_candidate_not_received(self):
        self.assertEqual(SERIES35["frequency_hz"], 437550000)
        self.assertEqual(SERIES35["mode"], "Robot36")
        self.assertEqual(SERIES35["start_utc_date"], "2026-11-09")

    def test_sync_requires_repeating_150ms_train(self):
        trace = [0.0] * 38000
        for row in range(240):
            at = 1000 + row*150
            for i in range(at, at+9):
                trace[i] = 1200
        syncs = _syncs(trace)
        self.assertGreaterEqual(len(syncs), 235)
        result = _line_alignment(syncs)
        self.assertIsNotNone(result)
        self.assertGreaterEqual(result[1], 225)
        self.assertIsNone(_line_alignment(_syncs([1200.0] * 40000)))

    def test_png_signature_and_dimensions(self):
        encoded = _png(2, 1, bytes([1,2,3,4,5,6]))
        self.assertTrue(encoded.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertEqual(struct.unpack(">II", encoded[16:24]), (2,1))
        with self.assertRaises(zlib.error):
            zlib.decompress(b"not zlib")

    def test_full_36_second_synthetic_tone_can_reconstruct_candidate(self):
        # Deterministic artificial audio is NOT a real ISS reception.
        rate = 8000
        seconds = 38
        pcm = bytearray(rate * seconds * 2)
        phase = 0.0
        for i in range(rate * seconds):
            within = (i / rate) % .150
            tone = 1200 if within < .009 else 1900
            phase += 2 * math.pi * tone / rate
            struct.pack_into("<h", pcm, i * 2, int(14000 * math.sin(phase)))
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "TIHULU_ISS-SSTV-CANDIDATE_SYNTH_437550000Hz_48000SPS_SSTV-AUDIO.wav"
            with wave.open(str(source), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(rate)
                wav.writeframes(pcm)
            result = extract_robot36_wav(source)
            self.assertEqual(result["status"], "robot36_sync_candidates_decoded")
            self.assertGreaterEqual(len(result["images"]), 1)
            self.assertFalse(result["images"][0]["satellite_identity_verified"])
            self.assertTrue((Path(directory)/result["images"][0]["file"]).read_bytes().startswith(b"\x89PNG"))

    def test_invalid_wav_rejected_without_fabrication(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"actually_recorded.wav"
            with wave.open(str(path), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(8000)
                wav.writeframes(b"\x00\x00" * 8000)  # 1s is not an image
            with self.assertRaisesRegex(ValueError, "32-910"):
                extract_robot36_wav(path)
            self.assertEqual(list(Path(directory).glob("*.png")), [])

if __name__ == "__main__":
    unittest.main()
