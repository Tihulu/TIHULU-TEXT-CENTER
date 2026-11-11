"""Tests for evidence-only native radio word karaoke.

Synthetic words below are original test phrases, not copied song lyrics.
No SDR, GPU, UI session, online lyrics, or soundcard is required.
"""
from pathlib import Path
import unittest

from tv_center.lyrics_sync import aligned_karaoke_word_anchors

ROOT = Path(__file__).resolve().parents[1]
RADIO_AI = (ROOT / "tv_center/radio_ai.py").read_text(encoding="utf-8")
MEDIA_AI = (ROOT / "tv_center/media_ai.py").read_text(encoding="utf-8")
NATIVE = (ROOT / "kaffeine_next/native_radio_tab.h").read_text(encoding="utf-8")


def heard(*tokens):
    return [{"text": word, "start": i * .45 + .2, "end": i * .45 + .57}
            for i, word in enumerate(tokens)]


class VerifiedWordKaraoke(unittest.TestCase):
    def test_real_gpu_times_map_to_original_lyric_characters(self):
        line = "The satellites are singing under blue skies"
        words = heard("satellites", "are", "singing", "under")
        anchors = aligned_karaoke_word_anchors(
            line, words, capture_end_epoch_ms=1_800_000_000_000)
        self.assertEqual([line[a["start"]:a["end"]] for a in anchors],
                         ["satellites", "are", "singing", "under"])
        self.assertEqual(
            [a["epoch_ms"] for a in anchors],
            [1_800_000_000_000 - round((6 - w["start"]) * 1000)
             for w in words])
        self.assertEqual(sorted(a["epoch_ms"] for a in anchors),
                         [a["epoch_ms"] for a in anchors])

    def test_mid_song_alignment_is_not_anchored_to_first_word(self):
        line = "Across the open sky our radio signal flies"
        result = aligned_karaoke_word_anchors(
            line, heard("radio", "signal", "flies"),
            capture_end_epoch_ms=1_800_000_000_000)
        self.assertEqual([line[a["start"]:a["end"]] for a in result],
                         ["radio", "signal", "flies"])

    def test_no_word_time_for_cpu_chunks_or_unrelated_speech(self):
        line = "Clouds above the quiet mountains"
        self.assertEqual(aligned_karaoke_word_anchors(
            line, [], capture_end_epoch_ms=1_800_000_000_000), [])
        self.assertEqual(aligned_karaoke_word_anchors(
            line, heard("commercial", "break", "starts"),
            capture_end_epoch_ms=1_800_000_000_000), [])
        self.assertEqual(aligned_karaoke_word_anchors(
            line, heard("clouds"), capture_end_epoch_ms=1_800_000_000_000), [])

    def test_reject_invalid_timestamp_not_fabricated(self):
        self.assertEqual(aligned_karaoke_word_anchors(
            "Little planets spin", [
                {"text":"Little","start":-5,"end":2},
                {"text":"planets","start":80,"end":82}],
            capture_end_epoch_ms=1_800_000_000_000), [])

    def test_qt_utf16_offsets_survive_non_bmp_emoji(self):
        line = "🚀 Aurora dances brightly"
        anchors = aligned_karaoke_word_anchors(
            line, heard("Aurora", "dances", "brightly"),
            capture_end_epoch_ms=1_800_000_000_000)
        self.assertEqual(anchors[0]["start"], 3)  # emoji occupies 2 UTF16 units
        self.assertEqual(anchors[0]["end"], 9)

    def test_anchors_only_published_after_audio_verified_line_match(self):
        self.assertIn('if lyric_match else [])', RADIO_AI)
        self.assertIn('"lyric_word_anchors":lyric_word_anchors', RADIO_AI)
        self.assertIn('detection["asr_words"]=words[:120]', MEDIA_AI)
        self.assertIn('"gpu_whisper_pcm_estimated_not_dac"', RADIO_AI)

    def test_native_word_highlighting_is_safe_and_preserves_existing_ui(self):
        for phrase in (
            "void refreshKaraokeWordHighlight(qint64 now)",
            "karaokeCurrent_->setTextFormat(Qt::RichText)",
            "karaokeLine_.mid(begin,end-begin).toHtmlEscaped()",
            "activePlaybackCacheMs_+",
            "lyricsOffset_->value()",
            "radioOffsetMs_->value()",
            'QLatin1String("lyric_word_anchors")',
            "wordAnchors(alignedWords)",
            "else refreshKaraokeWordHighlight(now)",
            "karaokeTranslationsEnabled_->isChecked()",
            "captionSurface->addWidget(radioCanvasCaption_)",
            "Line sync only · no verified word timestamps",
            "DAC unverified",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, NATIVE)
        self.assertNotIn("karaokeClockIsWordAccurate", NATIVE)


if __name__ == "__main__":
    unittest.main()
