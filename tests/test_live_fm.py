import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from textcenter.speech import SpeechError
from textcenter.live_fm import LiveFM, LiveError,encode_argv


class LiveFMTests(unittest.TestCase):
    def test_missing_speech_runtime_degrades_to_audio_only(self):
        # Simulates the user's detected GPU but unavailable Whisper model.
        with tempfile.TemporaryDirectory() as td:
            radio=LiveFM(archive_dir=Path(td)/"recordings")
            radio.state["active"]=True
            radio.state["subtitles_requested"]=True
            with patch("textcenter.live_fm.SpeechPipeline",
                       side_effect=SpeechError("No compatible installed speech executable/model")):
                radio._configure_optional_speech(
                    session="f"*32,hz=98_600_000,language="de",
                    translate_to="en",backend="auto",translation_backend="auto")
            self.assertTrue(radio.state["active"])
            self.assertIsNone(radio.speech)
            self.assertFalse(radio.state["subtitles_active"])
            self.assertIn("No compatible installed speech",
                          radio.state["subtitle_unavailable_reason"])
            report=radio.status()
            self.assertFalse(report["speech"]["enabled"])
            self.assertIn("No compatible installed speech",
                          report["speech"]["reason"])

    def test_optional_asr_can_be_enabled_when_runtime_is_available(self):
        with tempfile.TemporaryDirectory() as td:
            radio=LiveFM(archive_dir=Path(td)/"recordings")
            fake=object()
            with patch("textcenter.live_fm.SpeechPipeline",return_value=fake):
                radio._configure_optional_speech(
                    session="f"*32,hz=98_600_000,language="de",
                    translate_to=None,backend="cpu",translation_backend="auto")
            self.assertIs(radio.speech,fake)
            self.assertTrue(radio.state["subtitles_active"])
            self.assertIsNone(radio.state["subtitle_unavailable_reason"])

    def test_audio_encoding_has_safe_args(self):
        args=encode_argv("/usr/bin/ffmpeg")
        self.assertIn("libmp3lame",args)
        self.assertEqual(args[-2:],["mp3","pipe:1"])
        self.assertNotIn("-y",args)

    def test_readsb_blocks_start_without_process(self):
        with tempfile.TemporaryDirectory() as t:
            live=LiveFM(archive_dir=Path(t)/"rec",
                inventory=lambda:{"platform":"Linux","rtl_usb_count":1},
                lookup=lambda n:"/usr/bin/"+n,
                conflicts=lambda:[{"process":"readsb"}],
                lock_dir=Path(t)/"lock")
            self.assertFalse(live.availability()["ready"])
            with self.assertRaises(LiveError):
                live.start(98.6)
            self.assertFalse(live.status()["active"])
            self.assertIsNone(live.recording("../secret.mp3"))
            self.assertIsNone(live.recording("bad.mp3"))

    def test_no_model_or_dongle_is_not_fake_radio(self):
        with tempfile.TemporaryDirectory() as t:
            live=LiveFM(archive_dir=Path(t)/"rec",
                inventory=lambda:{"platform":"Linux","rtl_usb_count":0},
                lookup=lambda _:None,conflicts=lambda:[])
            self.assertFalse(live.availability()["ready"])
            with self.assertRaises(LiveError):
                live.start(98.6)
            self.assertEqual(live.recordings(),[])


if __name__=="__main__":
    unittest.main()
