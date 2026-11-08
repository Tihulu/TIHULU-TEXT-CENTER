"""Offline regressions for applied settings, real cue timestamps and OSD IPC."""
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from kaffeine_next.caption_timing import (CaptionConfig, CueQueue, KaffeineOSD, cue_window,
    AutoSyncEstimator, AutoSyncController, SyncRecommendation)
from kaffeine_next.patch_upstream import PATHS

class KaffeineTimingTests(unittest.TestCase):
    def test_auto_sync_starts_disabled_and_checkbox_is_applied_only(self):
        self.assertFalse(CaptionConfig().automatic_sync)
        self.assertTrue(CaptionConfig(automatic_sync=True).validate().automatic_sync)
        with self.assertRaises(ValueError):
            CaptionConfig(automatic_sync=1).validate()
        from pathlib import Path
        source = (Path(__file__).resolve().parent.parent /
                  "kaffeine_next" / "captions_overlay.py").read_text()
        self.assertIn('QCheckBox("Automatic sync', source)
        self.assertIn("automatic_sync=automatic.isChecked()", source)
        self.assertIn("(show_video,automatic,*language_boxes.values())", source)
        self.assertIn("auto_controller.next_delay(", source)
        self.assertIn("ipc.set_playback_delay(revised)", source)

    def test_real_asr_only_and_minimum_samples_before_suggesting_delay(self):
        e = AutoSyncEstimator()
        self.assertIsNone(e.recommend())
        self.assertFalse(e.observe(0,4,4.7,"broadcaster_teletext_subtitles"))
        self.assertTrue(e.observe(0,4,4.7,"local_asr"))
        self.assertTrue(e.observe(4,8,9,"local_asr"))
        self.assertIsNone(e.recommend())
        self.assertTrue(e.observe(8,12,13.4,"local_asr"))
        rec = e.recommend()
        self.assertEqual(rec.samples,3)
        self.assertEqual(rec.observed_lag_ms,5000)
        self.assertEqual((rec.safe_min_ms,rec.safe_max_ms),(5500,6000))
        self.assertEqual(rec.suggested_delay_ms,6000)
        self.assertIn("safe playback delay",rec.summary)
        self.assertFalse(rec.saturated)

    def test_auto_sync_rejects_discontinuous_or_invalid_capture_windows(self):
        e = AutoSyncEstimator(minimum=1)
        self.assertFalse(e.observe(0,0.1,1,"local_asr"))
        self.assertFalse(e.observe(1,5,4,"local_asr"))
        self.assertFalse(e.observe(0,5,99,"local_asr"))
        self.assertFalse(e.observe(None,5,6,"local_asr"))
        self.assertIsNone(e.recommend())

    def test_auto_safe_cap_and_live_bitrate_memory_budget(self):
        e = AutoSyncEstimator(minimum=3,ceiling_ms=6000)
        for start in (0,4,8):
            e.observe(start,start+4,start+12,"local_asr")
        rec = e.recommend(platform_cap_ms=4000)
        self.assertEqual(rec.safe_max_ms,4000)
        self.assertEqual(rec.suggested_delay_ms,4000)
        self.assertTrue(rec.saturated)
        # 24 MiB/s -> 48 MiB budget allows only 2s buffering.
        rec = e.recommend(bytes_per_second=24 * 1024 * 1024)
        self.assertEqual(rec.safety_cap_ms,2000)
        self.assertTrue(rec.saturated)
        self.assertLessEqual(rec.suggested_delay_ms,rec.safe_max_ms)

    def test_auto_changes_only_on_opt_in_with_cooldown_and_small_updates(self):
        ctrl = AutoSyncController(cooldown_seconds=30,deadband_ms=750,step_ms=500)
        rec = SyncRecommendation(4,5000,5000,6000,5500,6000,False)
        self.assertIsNone(ctrl.next_delay(rec,0,10,enabled=False))
        self.assertEqual(ctrl.next_delay(rec,0,10,enabled=True),5500)
        self.assertIsNone(ctrl.next_delay(rec,5500,20,enabled=True))
        unchanged = SyncRecommendation(5,5300,5000,6000,6000,6000,False)
        self.assertIsNone(ctrl.next_delay(unchanged,5500,45,enabled=True))
        ctrl.last_change_at = 10
        self.assertEqual(ctrl.next_delay(unchanged,5000,50,enabled=True),5500)
        ctrl.reset()
        self.assertFalse(ctrl.has_applied)

    def test_timestamp_only_estimators_never_claim_exact_word_alignment(self):
        e=AutoSyncEstimator(minimum=3)
        for start in (0,4,8):
            e.observe(start,start+4,start+5,"local_asr")
        self.assertGreater(e.recommend().observed_lag_ms,4000)
        self.assertIn("chunk",AutoSyncEstimator.__doc__.lower())

    def test_overlay_patch_includes_native_video_and_osd(self):
        self.assertIn("src/osdwidget.cpp", PATHS)
        self.assertIn("src/mediawidget.cpp", PATHS)
        self.assertIn("src/dvb/dvbliveview.cpp", PATHS)

    def test_whisper_receives_undelayed_ts_and_only_kaf_playback_is_buffered(self):
        from kaffeine_next.patch_upstream import transform
        import inspect
        source = inspect.getsource(transform)
        # The source patch is compiled against pinned KDE Kaffeine in CI.
        # Critical architecture: nonblocking sidecar -> bitrate cap ->
        # audio+video playback FIFO, never the other way around.
        self.assertLess(source.index("::sendto(tihuluCaptionFd"),
                        source.index("tihuluDelayed.append"))
        self.assertIn("tihuluObservedRate",source)
        self.assertIn("tihuluEffectiveDelayFile",source)
        self.assertIn("48LL * 1024 * 1024 * 1000",source)
        self.assertIn("tihuluDelayCooldownUntil",source)
        self.assertIn("timeShiftFile.isOpen()",source)

    def test_applied_tv_delay_is_read_from_player_not_guessed_from_gui(self):
        with tempfile.TemporaryDirectory() as root:
            ipc = KaffeineOSD(931, root)
            self.assertIsNone(ipc.read_effective_delay())
            ipc.effective.write_text("15000 7500 4200000")
            os = __import__("os")
            os.chmod(ipc.effective, 0o600)
            state = ipc.read_effective_delay()
            self.assertEqual(state["requested_ms"],15000)
            self.assertEqual(state["effective_ms"],7500)
            self.assertEqual(state["ts_bytes_per_second"],4200000)
            self.assertTrue(state["capped"])
            ipc.effective.write_text("15000 15000 1000000")
            self.assertFalse(ipc.read_effective_delay()["capped"])
            ipc.effective.write_text("15000 22000 1000000")
            self.assertIsNone(ipc.read_effective_delay())
            ipc.effective.write_text("15000 7500 4200000")
            os.utime(ipc.effective,(time.time()-20,time.time()-20))
            self.assertIsNone(ipc.read_effective_delay())

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
