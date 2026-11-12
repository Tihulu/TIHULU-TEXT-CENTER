"""REG-16 cross-clock regression: synthetic captions only, no live hardware.

An integration boundary missing from the existing separate pure timing and
live-offset suites: Kaffeine's ACTUAL (possibly capped) TV FIFO age, user
offset changes and genuine source-word cues must compose exactly once.
No GPU, decoder, tuner, audio output, ffmpeg or Qt event loop is started.
"""
from dataclasses import replace
import unittest

from kaffeine_next.caption_timing import (
    CaptionConfig, CueQueue, confirmed_cue_config,
)
from kaffeine_next.word_cues import enqueue_word_cues


class CaptionCrossClockAcceptance(unittest.TestCase):
    def test_ten_second_request_native_cap_and_live_offset_compose_once(self):
        requested = CaptionConfig(
            mode="auto", source="de", playback_delay_ms=10000,
            offset_ms=1000, target_languages=("en", "tr"),
            revision=3).validate()
        # The settings UI requests 10s, but native Kaffeine applies only
        # 6.5s. Neither the wanted 10s nor decoder wall-clock is the cue.
        capped = {"requested_ms": 10000, "effective_ms": 6500,
                  "primed": True}
        effective = confirmed_cue_config(requested, capped)
        self.assertIsNotNone(effective)
        self.assertEqual(effective.playback_delay_ms, 6500)
        self.assertEqual(requested.playback_delay_ms, 10000)
        queue = CueQueue()
        phrase = {"original": "Eigene Sendung in deutscher Sprache",
                  "source": "broadcaster_teletext_subtitles"}
        first = queue.add(phrase, effective, 100, 106, 102)
        self.assertAlmostEqual(first["due"], 108.05)
        self.assertEqual(len(queue.items), 1)
        # A live +1.5s offset change moves already-decoded cues only once.
        updated = replace(effective, offset_ms=2500)
        queue.retime(updated.offset_ms - effective.offset_ms, updated)
        self.assertAlmostEqual(queue.items[0]["due"], 109.55)
        # Applying other GUI settings later with the same chosen offset
        # must never create another 1.5s shift or rerun Whisper.
        queue.retime(updated.offset_ms - updated.offset_ms, updated)
        self.assertEqual(len(queue.items), 1)
        self.assertAlmostEqual(queue.items[0]["due"], 109.55)
        self.assertIsNone(queue.poll(109.54, 3))
        shown = queue.poll(109.56, 3)
        self.assertEqual(shown["result"]["original"], phrase["original"])

    def test_release_acknowledgement_required_for_real_word_cue_and_translation(self):
        config = CaptionConfig(
            mode="asr", source="de", playback_delay_ms=10000,
            offset_ms=1000, target_languages=("en", "tr"),
            revision=5).validate()
        # Before native buffer priming, the live player must not advertise
        # a confirmed delay or release multilingual word cues early.
        self.assertIsNone(confirmed_cue_config(config, {
            "requested_ms": 10000, "effective_ms": 6500,
            "primed": False, "has_release_clock": True,
            "release_fresh": False,
        }))
        # A NEW acknowledged TS release-age sample overrides both GUI
        # requested delay and the FIFO target, without claiming DAC PTS.
        actual = confirmed_cue_config(config, {
            "requested_ms": 10000, "effective_ms": 6500,
            "primed": True, "has_release_clock": True,
            "release_fresh": True, "released_age_ms": 6100,
        })
        self.assertIsNotNone(actual)
        self.assertEqual(actual.playback_delay_ms, 6100)
        decoded = {
            "original": "Hallo Welt",
            "source": "local_asr", "source_language": "de",
            "word_timing_source": "faster_whisper_cuda_word_timestamps",
            "words": [
                {"text": "Hallo", "start": .4, "end": .8},
                {"text": "Welt", "start": 1.0, "end": 1.45},
            ],
            "translations": {"en": "Hello world", "tr": "Merhaba dünya"},
        }
        queue = CueQueue()
        group = enqueue_word_cues(queue, decoded, actual,
                                  captured_start=100, captured_end=106,
                                  finished=102)
        self.assertIsNotNone(group)
        self.assertEqual(len(queue.items), 1)
        # First REAL source word .4s + measured TS age 6.1s +
        # user offset 1.0s + bounded .15s word hold = 107.65s.
        self.assertAlmostEqual(group["due"], 107.65)
        self.assertEqual(group["result"]["original"], "Hallo Welt")
        self.assertIn("not exact word alignment",
                      group["result"]["translation_alignment"])
        self.assertEqual(set(group["result"]["translations"]), {"en", "tr"})
        self.assertIsNone(queue.poll(107.64, 5))
        self.assertEqual(queue.poll(107.66, 5)["result"]["original"], "Hallo Welt")


if __name__ == "__main__":
    unittest.main()
