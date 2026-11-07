"""Offline regressions for applied settings, real cue timestamps and OSD IPC."""
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from kaffeine_next.caption_timing import CaptionConfig, CueQueue, KaffeineOSD, cue_window
from kaffeine_next.patch_upstream import PATHS

class KaffeineTimingTests(unittest.TestCase):
    def test_overlay_patch_includes_native_video_and_osd(self):
        self.assertIn("src/osdwidget.cpp", PATHS)
        self.assertIn("src/mediawidget.cpp", PATHS)
        self.assertIn("src/dvb/dvbliveview.cpp", PATHS)

    def test_settings_validation_and_bilingual_text(self):
        cfg = CaptionConfig(playback_delay_ms=3000,offset_ms=-1200,
                            on_video=True,show_original=True,
                            show_translation=True).validate()
        self.assertEqual(cfg.render({"original":"Vorsicht, Kabel.",
                                     "translated":"Dikkat, kablo."}),
                         "Vorsicht, Kabel.\nDikkat, kablo.")
        self.assertEqual(CaptionConfig(show_original=False).render(
            {"original":"DE","translated":"TR"}),"TR")
        with self.assertRaises(ValueError):
            CaptionConfig(playback_delay_ms=25000).validate()
        with self.assertRaises(ValueError):
            CaptionConfig(page=999).validate()

    def test_cue_due_is_from_capture_not_decode_finish(self):
        cfg = CaptionConfig(playback_delay_ms=6000,offset_ms=-500,revision=7)
        timing = cue_window(started=10,ended=14,finished=15,config=cfg)
        self.assertAlmostEqual(timing["due"],15.5)
        self.assertEqual(timing["lateness_ms"],0)
        too_late = cue_window(10,14,19,cfg)
        self.assertEqual(too_late["lateness_ms"],3500)

    def test_apply_revision_discards_old_cues(self):
        q = CueQueue()
        old = CaptionConfig(revision=1)
        newer = CaptionConfig(revision=2)
        q.add({"original":"old"},old,0,4,5)
        self.assertIsNone(q.poll(5,revision=2))
        q.add({"original":"new"},newer,5,9,10)
        self.assertEqual(q.poll(10,revision=2)["result"]["original"],"new")
        self.assertIsNone(q.poll(11,revision=2))

    def test_osd_and_audio_video_buffer_are_private_and_cleaned(self):
        with tempfile.TemporaryDirectory() as root:
            p = KaffeineOSD(413, root)
            cfg = CaptionConfig(playback_delay_ms=2000,opacity=80,
                                position="top",font_px=30)
            p.publish("Hallo\nMerhaba",cfg)
            content = json.loads(p.path.read_text())
            self.assertEqual(content["text"],"Hallo\nMerhaba")
            self.assertEqual(content["position"],"top")
            self.assertEqual(content["opacity"],80)
            self.assertTrue(content["expires_ms"] >= time.time()*1000)
            p.set_playback_delay(cfg)
            self.assertEqual(p.delay.read_text().strip(),"2000")
            self.assertEqual(p.path.stat().st_mode & 0o777,0o600)
            p.close()
            self.assertFalse(p.path.exists())
            self.assertFalse(p.delay.exists())

    def test_video_hidden_without_caption_mode(self):
        with tempfile.TemporaryDirectory() as root:
            p=KaffeineOSD(4,root)
            p.publish("Speech",CaptionConfig(mode="off"))
            self.assertFalse(json.loads(p.path.read_text())["enabled"])
            p.close()
