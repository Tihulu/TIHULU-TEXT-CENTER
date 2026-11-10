"""Sync Refresh must re-anchor only to recent, genuinely heard Whisper text.

These are offline unit/source-contract tests, not hardware DAC timing tests.
"""
from pathlib import Path
import unittest

from tv_center.lyrics_sync import LiveLyricMatcher

ROOT=Path(__file__).resolve().parents[1]
AI=(ROOT/"tv_center/radio_ai.py").read_text(encoding="utf-8")
NATIVE=(ROOT/"kaffeine_next/native_radio_tab.h").read_text(encoding="utf-8")


class WhisperKaraokeRefreshTests(unittest.TestCase):
    def setUp(self):
        self.lines=[
            "Northern lanterns shimmer across the silent valley",
            "Painted clouds dance beneath the distant mountain",
            "Golden rivers wind through our bright memories",
        ] + [f"Violet echoes around midnight satellite {i} signal" for i in range(12)]
        self.lines[12]="Crystal harmonies awaken beyond the distant skyline"

    def test_refresh_reacquires_late_song_after_forward_lock(self):
        matcher=LiveLyricMatcher(self.lines,threshold=.74)
        self.assertEqual(matcher.observe(self.lines[0])["index"],0)
        # Forward-only matcher cannot jump far from the current verse.
        self.assertIsNone(matcher.observe(self.lines[12]))
        result=matcher.reacquire(self.lines[12])
        self.assertIsNotNone(result)
        self.assertEqual(result["index"],12)
        self.assertTrue(result["refresh_reacquired"])
        self.assertGreaterEqual(result["confidence"],.89)
        self.assertEqual(matcher.position,13)

    def test_refresh_without_vocal_evidence_keeps_last_position(self):
        matcher=LiveLyricMatcher(self.lines,threshold=.65)
        matcher.observe(self.lines[0])
        position=matcher.position
        self.assertIsNone(matcher.reacquire("Welcome to the sponsored weather report"))
        self.assertEqual(matcher.position,position)
        self.assertIsNone(matcher.reacquire(""))
        self.assertEqual(matcher.position,position)

    def test_repeated_chorus_does_not_guess_a_distant_verse(self):
        refrain="Crystal harmonies awaken beyond the distant skyline"
        lyrics=["Gentle water rises over bright forests"] + [
            "Quiet sunset drifts behind the glowing hills"]*11 + [refrain] + [
            "Brave cloud patterns meet the open ocean"]*10 + [refrain]
        matcher=LiveLyricMatcher(lyrics)
        self.assertIsNone(matcher.reacquire(refrain))
        # Once actual earlier verse establishes proximity, only one
        # chorus occurrence is plausible, not a fabricated song-wide seek.
        matcher.position=12
        found=matcher.reacquire(refrain)
        self.assertIsNotNone(found)
        self.assertEqual(found["index"],12)

    def test_refresh_does_not_accept_generic_short_refrain_far_ahead(self):
        lines=["Morning chorus runs softly past the meadow"]*10 + [
            "Gül kokar gül"]
        matcher=LiveLyricMatcher(lines)
        self.assertIsNone(matcher.reacquire("Gül kokar gül"))

    def test_worker_uses_last_10_seconds_original_asr_not_lyrics(self):
        for marker in (
            "heard_asr=original",
            "recent_lyric_asr=deque(maxlen=4)",
            "capture_epoch_ms-recent_lyric_asr[0][\"epoch_ms\"]>10000",
            "plain_matcher.reacquire(recent[\"text\"])",
            '"karaoke_sync_refresh_token"',
            '"karaoke_sync_refresh_applied":sync_refresh_applied',
            '"caption_revision":0,',
            '"lyric_word_anchors":lyric_word_anchors',
            "sync_refresh_windows_left=3",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker,AI)
        self.assertIn("if lyric_match else [])",AI)

    def test_native_refresh_requests_rematch_not_audio_restart(self):
        refresh=NATIVE.split("void refreshRadioLipSync() {",1)[1].split(
            "void refreshKaraokeWordHighlight(",1)[0]
        self.assertIn("++karaokeSyncRefreshToken_;",refresh)
        self.assertIn("requestedRematch=writeRadioLanguageControls();",refresh)
        self.assertIn("canRematch",refresh)
        self.assertIn("recentKaraokeEvidence_",refresh)
        self.assertIn("activePlaybackCacheMs_",refresh)
        for banned in ("stopCaptioning(", "startCaptioning(",
                       "player_->stop(", "player_->play(",
                       "stopReceiver(", "startReceiver("):
            self.assertNotIn(banned,refresh)
        self.assertIn('QStringLiteral("karaoke_sync_refresh_token")',NATIVE)
        self.assertIn("freshRefreshMatch",NATIVE)
        self.assertIn("lastHandledKaraokeSyncToken_=syncApplied",NATIVE)


if __name__=="__main__":
    unittest.main()
