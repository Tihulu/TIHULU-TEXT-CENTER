"""Offline integration tests: the live sidecar must not discard Whisper word PTS.

Real DVB lip-sync still requires calibrated Kaffeine/libVLC presentation PTS.
These tests make no unsupported real-device precision claim.
"""
import queue
import unittest
from unittest.mock import patch

from kaffeine_next.captions_overlay import CaptionTap
from tv_center.sentence_joiner import LiveSentenceJoiner


def tap_for_test():
    tap = object.__new__(CaptionTap)
    tap.events = queue.Queue()
    tap.program_epoch = 0
    tap.previous_original = ""
    tap.previous_revision = -1
    tap.sentence_joiner = LiveSentenceJoiner(max_words=90,max_chunks=2)
    tap.sentence_session = None
    tap.sentence_captured_start = None
    from kaffeine_next.teletext_match import TeletextAudit
    tap.teletext_audit = TeletextAudit()
    tap.teletext_audit_session = None
    return tap


def recognized():
    return {
        "source": "local_asr", "source_language": "de",
        "original": "Hallo Welt", "raw_asr_original": "Hallo Welt",
        "words": [
            {"text": "Hallo", "start": .2, "end": .5},
            {"text": "Welt", "start": .9, "end": 1.2},
        ], "word_timing_source": "faster_whisper_cuda_word_timestamps",
        "speaker_turns": [
            {"id": "SPEAKER_00", "start": 0, "end": .75},
            {"id": "SPEAKER_01", "start": .75, "end": 1.6},
        ], "processing_ms": {},
    }


class LiveWordPipelineTests(unittest.TestCase):
    def decode(self, result, gaps=0):
        tap = tap_for_test()
        options = {
            "mode": "asr", "source": "de", "targets": ("en",), "page": 150,
            "revision": 0, "program_epoch": 0, "service_id": 5,
            "ts_integrity": {"critical_gaps": gaps},
            "speaker_enabled": True, "speaker_provider": "resemblyzer",
            "music_transcription": False, "speech_priority": False,
        }
        with (patch("tv_center.ai_settings.AISettings") as ai,
              patch("tv_center.captions.decode_segment",
                    return_value=result),
              patch("tv_center.captions.translate",
                    return_value=("Hello world",None)) as tr):
            ai.return_value.values = {
                "asr_enabled": True, "translation_enabled": True,
                "model_path": "offline-test-model"}
            tap._decode(b"dummy", options, 100.0, 106.0)
        return tap, tr

    def test_real_word_times_survive_sentence_joiner_and_translation(self):
        tap, translator = self.decode(recognized())
        kind, item = tap.events.get_nowait()
        self.assertEqual(kind, "caption")
        self.assertEqual(len(item["words"]), 2)
        self.assertEqual(item["word_timing_source"],
                         "faster_whisper_cuda_word_timestamps")
        self.assertEqual(item["caption_alignment"],
                         "Source audio word timestamps")
        self.assertEqual(item["translations"], {"en": "Hello world"})
        self.assertEqual(item["speaker_turns"][1]["id"], "SPEAKER_01")
        translator.assert_called_once_with("Hallo Welt","de","en")
        self.assertFalse(tap.sentence_joiner.pending)

    def test_damaged_source_disables_claimed_word_alignment(self):
        source=recognized()
        source["original"]="Hallo Welt."
        source["raw_asr_original"]="Hallo Welt."
        tap, translator = self.decode(source,gaps=1)
        events=list(tap.events.queue)
        caption = next((value for kind,value in events if kind=="caption"),None)
        if caption is not None:
            self.assertEqual(caption["words"],[])
            self.assertNotIn("caption_alignment",caption)
        else:
            self.assertTrue(any(kind=="sentence_pending" for kind,_ in events))
        # A damaged clip must never publish misleading source-word times.
        self.assertFalse(any(
            value.get("caption_alignment")=="Source audio word timestamps"
            for kind,value in events if kind=="caption"))


if __name__ == "__main__":
    unittest.main()
