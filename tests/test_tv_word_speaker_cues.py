"""No hardware/network required: word pacing and optional speaker labeling."""
import unittest
from unittest.mock import patch

from kaffeine_next.caption_timing import CaptionConfig, CueQueue
from kaffeine_next.word_cues import word_groups, enqueue_word_cues
from tv_center.captions import _speaker_details


def clip(*, words=None, translations=None, turns=None):
    return {"source":"local_asr", "source_language":"de",
            "original":"Guten Morgen meine Freunde und willkommen zurück",
            "words": words or [
                {"text":"Guten","start":0.2,"end":0.5},
                {"text":"Morgen","start":0.6,"end":0.9},
                {"text":"meine","start":1.2,"end":1.45},
                {"text":"Freunde","start":1.5,"end":1.85},
                {"text":"und","start":2.0,"end":2.2},
                {"text":"willkommen","start":2.5,"end":2.9},
                {"text":"zurück","start":3.0,"end":3.3}],
            "translations":translations or {"tr":"Günaydın arkadaşlarım tekrar hoş geldiniz"},
            "speaker_turns":turns or []}


class WordCueTests(unittest.TestCase):
    def test_cues_are_short_and_timed_to_prebuffer_capture(self):
        data=clip()
        groups=word_groups(data,maximum_words=3)
        self.assertGreaterEqual(len(groups),3)
        self.assertTrue(all(len(g[2]["original"].split())<=3 for g in groups))
        self.assertTrue(all(len(g[2]["translations"]["tr"].split())<=9 for g in groups))
        q=CueQueue(maximum=32)
        # Explicit word-by-word mode keeps the legacy short groups; the
        # new default comfort mode intentionally groups larger phrases.
        config=CaptionConfig(playback_delay_ms=10000,readable_pacing=False)
        final=enqueue_word_cues(q,data,config,
                                captured_start=100.0,captured_end=106.0,
                                finished=107.0)
        self.assertIsNotNone(final)
        self.assertGreater(len(q.items),1)
        self.assertTrue(min(item["due"] for item in q.items) >= 110.0)
        self.assertEqual(q.poll(109,0),None)
        self.assertIsNotNone(q.poll(111,0))

    def test_fast_bilingual_word_cues_use_complete_readable_phrase(self):
        data=clip()
        cfg=CaptionConfig(playback_delay_ms=12000,
                          readable_pacing=True,target_languages=("en","tr"))
        from kaffeine_next.word_cues import enqueue_word_cues
        queue=CueQueue()
        result=enqueue_word_cues(queue,data,cfg,100.0,106.0,107.0)
        self.assertIsNone(result)
        self.assertEqual(queue.items,[])
        # Full source-timed Whisper metadata remains available for a
        # single natural sentence anchored to a real first word.
        from kaffeine_next.caption_timing import cue_window
        data["word_timing_source"]="CUDA"
        when=cue_window(100.0,106.0,107.0,cfg,data)
        self.assertGreater(when["expires"]-when["due"],2.8)

    def test_legacy_word_by_word_still_available_without_readable_pacing(self):
        cfg=CaptionConfig(playback_delay_ms=12000,readable_pacing=False)
        queue=CueQueue()
        result=enqueue_word_cues(queue,clip(),cfg,100,106,107)
        self.assertIsNotNone(result)
        self.assertGreater(len(queue.items),1)

    def test_timed_words_keep_actual_source_spacing_not_cumulative_ui_holds(self):
        cfg=CaptionConfig(playback_delay_ms=20000)
        queue=CueQueue(minimum_hold=1.75)
        a={"source":"local_asr","original":"First voice",
           "word_progress":{"start":0,"end":1,"count":4}}
        b={"source":"local_asr","original":"Second voice",
           "word_progress":{"start":2,"end":3,"count":4}}
        one=queue.add(a,cfg,100.0,100.5,105.0)
        two=queue.add(b,cfg,100.6,101.1,105.0)
        self.assertAlmostEqual(one["due"],120.15)
        self.assertAlmostEqual(two["due"],120.75)
        self.assertIsNotNone(queue.poll(120.2,cfg.revision))
        # Without the fix the 1.75s reading slot delayed voice 2
        # until 121.9s (and accumulated further with each new speaker).
        # Comfort reading holds even a brief source-word group long
        # enough to see it, without stacking a 1.75s delay for each word.
        self.assertIsNone(queue.poll(120.8,cfg.revision))
        self.assertEqual(queue.poll(121.05,cfg.revision)["result"]["original"],
                         "Second voice")

    def test_overlapping_speaker_windows_do_not_mislabel_a_new_voice(self):
        data=clip(words=[
            {"text":"Hallo","start":0.2,"end":0.5},
            {"text":"Welt","start":0.8,"end":1.1},
            {"text":"Anderer","start":1.4,"end":1.65},
            {"text":"Sprecher","start":1.7,"end":2.0}
        ],turns=[
            {"id":"SPEAKER_00","start":0.0,"end":1.5},
            {"id":"SPEAKER_01","start":1.0,"end":2.5}])
        groups=word_groups(data)
        self.assertTrue(any(g[2].get("speaker_index")==1 for g in groups))
        self.assertTrue(any(g[2].get("speaker_index")==2 for g in groups))
        self.assertTrue(all(not ("Hallo" in g[2]["original"] and
                                  "Anderer" in g[2]["original"]) for g in groups))
        # A contested transition word has no confident assigned voice.
        contested=word_groups(clip(words=[
            {"text":"Maybe","start":1.17,"end":1.33}
        ],turns=data["speaker_turns"]))
        self.assertNotIn("speaker_label",contested[0][2])

    def test_missing_timestamps_and_non_whisper_use_normal_chunk(self):
        self.assertEqual(word_groups({"source":"broadcaster_teletext_subtitles",
                                     "words":clip()["words"]}),[])
        self.assertEqual(word_groups(clip(words=[
            {"text":"bad","start":1.0,"end":1.4},
            {"text":"earlier","start":0.1,"end":0.2}])),[])

    def test_identifies_real_speaker_turns_per_clip_without_age_gender(self):
        data=clip(turns=[
            {"id":"SPEAKER_00","start":0.0,"end":1.2},
            {"id":"SPEAKER_01","start":1.2,"end":5.0}])
        groups=word_groups(data)
        self.assertGreaterEqual(len(groups),2)
        self.assertIn("[Speaker 1 · clip]",groups[0][2]["speaker_label"])
        self.assertIn("[Speaker 2 · clip]",groups[-1][2]["speaker_label"])
        self.assertNotIn("woman",str(groups).lower())
        self.assertNotIn("child",str(groups).lower())

    def test_diarization_never_erases_transcript_if_unavailable(self):
        with patch("tv_center.speaker_market.diarize_pcm",
                   side_effect=RuntimeError("Missing gated model")):
            meta={}
            text=_speaker_details(b"1234","Guten Morgen",meta,True,
                                  provider="pyannote")
        self.assertEqual(text,"Guten Morgen")
        self.assertIn("Missing gated model",meta["speaker_error"])
        with patch("tv_center.speaker_market.diarize_pcm") as worker:
            meta={}
            self.assertEqual(_speaker_details(b"1234","Hallo",meta,False),"Hallo")
            worker.assert_not_called()

    def test_config_requires_opt_in(self):
        self.assertFalse(CaptionConfig().speaker_enabled)
        self.assertFalse(CaptionConfig().options()["speaker_enabled"])
        cfg=CaptionConfig(speaker_enabled=True).validate()
        self.assertTrue(cfg.options()["speaker_enabled"])
        cfg.render({"original":"Test","speaker_label":"[Speaker 2 · clip]"})
        self.assertIn("Speaker 2",cfg.render(
            {"original":"Test","speaker_label":"[Speaker 2 · clip]"}))
        manual=CaptionConfig(speaker_enabled=True,
                             speaker_aliases=("Woman","Man","Child")).validate()
        rendered=manual.render({"original":"Test",
                    "speaker_index":3,"speaker_label":"[Speaker 3 · clip]"})
        self.assertTrue(rendered.startswith("[Child]  Test"))
        prefixed=CaptionConfig(
            speaker_enabled=True,show_original=True,
            show_translation=True,target_languages=("en",),
            speaker_aliases=("Adam 1","Çocuk 2")).validate()
        result={"original":"Merhaba", "source_language":"tr",
                "translations":{"en":"Hello"},
                "speaker_index":2,"speaker_label":"[Speaker 2 · clip]"}
        lines=prefixed.render(result).splitlines()
        self.assertEqual(len(lines),2)
        self.assertTrue(all(line.startswith("[Çocuk 2]  ") for line in lines))
        untouched=CaptionConfig(speaker_enabled=False,
                                 speaker_aliases=("Woman",)).validate()
        self.assertNotIn("Woman",untouched.render(
            {"original":"Test","speaker_index":1,
             "speaker_label":"[Speaker 1 · clip]"}))

if __name__=="__main__":
    unittest.main()
