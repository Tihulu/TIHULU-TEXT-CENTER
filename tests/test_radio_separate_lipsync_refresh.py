"""Separate Whisper caption timing from Karaoke model refresh.

These checks intentionally do not require an SDR receiver, model download,
or DAC measurement. They verify wiring, independence and language selection.
"""
from pathlib import Path
import unittest

from tv_center.radio_karaoke_router import karaoke_alignment_choice

ROOT = Path(__file__).resolve().parents[1]
NATIVE = (ROOT / "kaffeine_next/native_radio_tab.h").read_text("utf-8")
WORKER = (ROOT / "tv_center/radio_ai.py").read_text("utf-8")


def section(start: str, end: str) -> str:
    begin = NATIVE.index(start)
    return NATIVE[begin:NATIVE.index(end, begin)]


class SeparateLipSyncRefreshTests(unittest.TestCase):
    def test_two_refresh_buttons_have_independent_handlers(self):
        self.assertIn('tr("AI Lip-sync Refresh")', NATIVE)
        self.assertIn('tr("Karaoke Lip-sync Refresh")', NATIVE)
        self.assertIn('this,[this](){refreshRadioCaptionLipSync();}', NATIVE)
        self.assertIn('this,[this](){refreshRadioLipSync();}', NATIVE)

    def test_ai_sync_changes_only_pending_whisper_captions(self):
        action = section("void refreshRadioCaptionLipSync() {",
                         "void refreshRadioLipSync() {")
        self.assertIn("lagSamples_.clear();", action)
        self.assertIn("for(auto &cue:cueQueue_)", action)
        self.assertIn("cue.unoffsetDueMs", action)
        self.assertIn("cue.dueMs=", action)
        self.assertNotIn("verifiedLyricQueue_", action)
        self.assertNotIn("plainLyricQueue_", action)
        self.assertNotIn("karaokeSyncRefreshToken_", action)
        self.assertNotIn("stopCaptioning(", action)
        self.assertNotIn("startCaptioning(", action)
        self.assertNotIn("player_->play(", action)

    def test_karaoke_refresh_does_not_retime_speech(self):
        action = section("void refreshRadioLipSync() {",
                         "void refreshKaraokeWordHighlight(")
        self.assertIn("++karaokeSyncRefreshToken_;", action)
        self.assertIn("requestedRematch=writeRadioLanguageControls()", action)
        self.assertIn("recentKaraokeEvidence_", action)
        self.assertIn("verifiedLyricQueue_", action)
        self.assertNotIn("for(auto &cue:cueQueue_)", action)
        self.assertNotIn("lagSamples_.clear()", action)
        self.assertNotIn("displayDueRadioCues(", action)
        for prohibited in ("stopCaptioning(", "startCaptioning(",
                           "player_->play(", "player_->stop("):
            self.assertNotIn(prohibited, action)

    def test_installed_aligner_is_optional_and_language_gated(self):
        self.assertEqual(karaoke_alignment_choice(
            "en", qwen_installed=True)["engine"], "qwen")
        self.assertEqual(karaoke_alignment_choice(
            "de", qwen_installed=True)["engine"], "qwen")
        self.assertEqual(karaoke_alignment_choice(
            "tr", qwen_installed=True)["engine"], "whisper")
        self.assertEqual(karaoke_alignment_choice(
            "en", qwen_installed=False)["engine"], "whisper")
        self.assertEqual(karaoke_alignment_choice(
            None, qwen_installed=True)["engine"], "whisper")

    def test_karaoke_language_is_independent_of_presenter(self):
        self.assertIn("alignment_language=(", WORKER)
        self.assertIn("lyric_source_language in QWEN_ALIGN_LANGUAGES", WORKER)
        self.assertIn("alignment_option=karaoke_alignment_choice(", WORKER)
        self.assertIn("qwen_installed=qwen_installed", WORKER)
        self.assertIn("align_observed_phrase,qwen_audio_pcm", WORKER)
        self.assertIn('lyric_match["text"],alignment_option["language"]', WORKER)
        self.assertIn("sync_refresh_windows_left=3", WORKER)
        self.assertIn("karaoke_qwen_refinement", WORKER)
        self.assertIn("Whisper", WORKER)


if __name__ == "__main__":
    unittest.main()
