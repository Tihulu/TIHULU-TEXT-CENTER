"""Regression tests for readable live TV subtitles and stable native timing.

Never depend on RF, ffmpeg, CUDA, network or the actual Kaffeine process.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
import tempfile
import unittest

from kaffeine_next.caption_timing import (
    CaptionConfig, CueQueue, NativeReleaseClock, readable_display_seconds,
    confirmed_cue_config)
from kaffeine_next.word_cues import enqueue_word_cues
from tv_center.sentence_joiner import LiveSentenceJoiner


class ReadableDisplayTests(unittest.TestCase):
    def test_long_multilingual_phrase_holds_longer_than_short_words(self):
        cfg=CaptionConfig(target_languages=("en","tr"),readable_pacing=True)
        short={"original":"Ja."}
        long={"original":"Eine wichtige Entscheidung wurde heute getroffen.",
              "translations":{"en":"An important decision was made today.",
                              "tr":"Bugün önemli bir karar alındı."}}
        self.assertGreater(readable_display_seconds(long,cfg),
                           readable_display_seconds(short,cfg))
        self.assertGreaterEqual(readable_display_seconds(short,cfg),2.8)
        self.assertLessEqual(readable_display_seconds(long,cfg),8.0)
        progressive={"original":"Guten Morgen",
                     "word_progress":{"start":0,"end":1,"count":20}}
        self.assertGreaterEqual(readable_display_seconds(progressive,cfg),1.35)
        self.assertFalse(CaptionConfig(readable_pacing=False).options()[
            "readable_pacing"])

    def test_queued_real_dialogue_is_not_deleted_if_decoder_was_late(self):
        cfg=CaptionConfig(playback_delay_ms=6000)
        q=CueQueue(maximum=12)
        first=q.add({"source":"local_asr",
                     "original":"Eine bereits erkannte echte Untertitelzeile"},
                    cfg,100,106,108)
        self.assertLess(first["expires"],135)
        # Previously the queue deleted this REAL subtitle before poll().
        shown=q.poll(135,cfg.revision)
        self.assertIsNotNone(shown)
        self.assertEqual(shown["result"]["original"],
                         "Eine bereits erkannte echte Untertitelzeile")
        self.assertGreaterEqual(shown["expires"],135+2.8)

    def test_late_word_groups_fallback_to_whole_readable_sentence(self):
        original={"source":"local_asr","source_language":"de",
                  "original":"Heute reden wir über einen wichtigen neuen Film.",
                  "translations":{"tr":"Bugün önemli yeni bir film hakkında konuşuyoruz."},
                  "words":[
                    {"text":w,"start":i*0.7,"end":i*0.7+0.38}
                    for i,w in enumerate(
                        "Heute reden wir über einen wichtigen neuen Film".split())]}
        cfg=CaptionConfig(playback_delay_ms=6000,readable_pacing=True)
        q=CueQueue()
        self.assertIsNone(enqueue_word_cues(
            q,original,cfg,100,106,109))
        self.assertFalse(q.items)
        # Controller then schedules ONE readable complete phrase instead.
        cue=q.add(original,cfg,100,106,109)
        self.assertIn("Film",cue["result"]["original"])
        self.assertIsNotNone(q.poll(cue["due"]+0.1,cfg.revision))

    def test_no_extra_wait_for_real_unpunctuated_words_in_comfort_mode(self):
        words="Das ist ein echter erkennbarer gesprochener Satz ohne Punkt heute"
        joiner=LiveSentenceJoiner(max_words=90,max_chunks=2)
        normal=joiner.push(words,language="de",prefer_readable=False)
        self.assertTrue(normal["pending"])
        self.assertFalse(normal["text"])
        joiner.reset()
        quick=joiner.push(words,language="de",prefer_readable=True)
        self.assertTrue(quick["readable_early"])
        self.assertIn("erkennbarer",quick["text"])
        self.assertFalse(quick["pending"])
        self.assertFalse(joiner.pending)
        self.assertEqual(joiner.push("Ein kurzer Satz",language="de",
                                     prefer_readable=True)["text"],"")


class StableClockTests(unittest.TestCase):
    def status(self,measured,stamp,requested=12000,effective=12000):
        return {"requested_ms":requested,"effective_ms":effective,
                "primed":True,"release_fresh":True,
                "has_release_clock":True,"released_age_ms":measured,
                "released_at_ms":stamp}

    def test_hysteresis_prevents_early_jump_from_one_fifo_measurement(self):
        smooth=NativeReleaseClock()
        first=smooth.stabilized(self.status(8500,1))
        self.assertEqual(first["raw_released_age_ms"],8500)
        self.assertEqual(first["released_age_ms"],11650)
        second=smooth.stabilized(self.status(11900,2))
        self.assertLessEqual(abs(second["released_age_ms"]-11650),220)
        # Reading the same native status many times should not step
        # the filter again; only a NEW native release timestamp may.
        replay=smooth.stabilized(self.status(11900,2))
        self.assertEqual(replay["released_age_ms"],second["released_age_ms"])
        self.assertTrue(replay["release_clock_filtered"])

    def test_retarget_resets_history(self):
        smooth=NativeReleaseClock()
        smooth.stabilized(self.status(8500,1))
        new=smooth.stabilized(self.status(8000,3,requested=8000,effective=8000))
        self.assertEqual(new["released_age_ms"],8000)
        smooth.clear()
        self.assertIsNone(smooth.current_ms)

    def test_confirmed_cue_uses_filtered_actual_age_not_untrusted_ui_target(self):
        cfg=CaptionConfig(playback_delay_ms=12000)
        smooth=NativeReleaseClock()
        corrected=smooth.stabilized(self.status(10700,1))
        result=confirmed_cue_config(cfg,corrected)
        self.assertIsNotNone(result)
        self.assertGreaterEqual(result.playback_delay_ms,11650)
        invalid=self.status(11000,1)
        invalid["release_fresh"]=False
        self.assertIsNone(confirmed_cue_config(cfg,smooth.stabilized(invalid)))


class WiringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path=Path(__file__).resolve().parent.parent/"kaffeine_next"/"captions_overlay.py"
        cls.source=cls.path.read_text(encoding="utf8")
        ast.parse(cls.source)

    def test_only_real_tune_source_changes_bump_audio_generation(self):
        # Playback-buffer changes must NOT make the MPEG-TS capture reader
        # clear its work queue or drop an in-progress six-second clip.
        self.assertIn("int(source_changed))",self.source)
        self.assertNotIn("int(source_changed or playback_changed))",
                         self.source)
        self.assertIn("elif playback_changed:",self.source)
        self.assertIn("pending_buffer_retime_ms =",self.source)
        self.assertIn("cues.retime(current_actual-old_clock,applied)",self.source)

    def test_captions_pause_during_new_buffer_ack_without_losing_queue(self):
        self.assertIn("if service_running and buffer_ready else None",self.source)
        self.assertIn("native_release_clock.stabilized(",self.source)
        self.assertIn("comfort_reading.setChecked(True)",self.source)
        self.assertIn("prefer_readable=bool(options.get(",self.source)

    def test_waits_for_ui_before_counting_real_caption_loss(self):
        self.assertIn("self.events.put((\"caption\", result), timeout=1.25)",
                      self.source)
        self.assertIn("lost_ui_caption_events",self.source)


if __name__=="__main__":
    unittest.main()
