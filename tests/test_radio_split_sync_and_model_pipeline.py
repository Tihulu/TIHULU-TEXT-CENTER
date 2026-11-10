"""Split radio sync controls, real catalog delivery and Qwen fallback.

Only source-contract/unit tests here. Real DAB hardware, GPU timing and the
speaker DAC must be validated separately; no model weights are downloaded.
"""
from pathlib import Path
import unittest

from tv_center.radio_karaoke_router import karaoke_alignment_choice

ROOT=Path(__file__).resolve().parents[1]
UI=(ROOT/"kaffeine_next/native_radio_tab.h").read_text("utf-8")
AI=(ROOT/"tv_center/radio_ai.py").read_text("utf-8")


def section(start,end):
    a=UI.index(start)
    return UI[a:UI.index(end,a)]


class SplitSyncAndKaraokeEngineTests(unittest.TestCase):
    def test_separate_buttons_and_disjoint_refresh_paths(self):
        self.assertIn('tr("AI Lip-sync Refresh")',UI)
        self.assertIn('tr("Karaoke Lip-sync Refresh")',UI)
        self.assertIn("refreshRadioCaptionLipSync();",UI)
        self.assertIn("refreshRadioLipSync();",UI)
        speech=section("void refreshRadioCaptionLipSync() {",
                       "void refreshRadioLipSync() {")
        karaoke=section("void refreshRadioLipSync() {",
                        "void refreshKaraokeWordHighlight(")
        self.assertIn("cueQueue_",speech)
        self.assertIn("lagSamples_.clear()",speech)
        self.assertIn("unoffsetDueMs",speech)
        self.assertNotIn("karaokeSyncRefreshToken_",speech)
        self.assertNotIn("verifiedLyricQueue_",speech)
        self.assertNotIn("plainLyricQueue_",speech)
        self.assertIn("verifiedLyricQueue_",karaoke)
        self.assertIn("plainLyricQueue_",karaoke)
        self.assertIn("++karaokeSyncRefreshToken_;",karaoke)
        self.assertNotIn("cueQueue_",karaoke)
        self.assertNotIn("lagSamples_.clear()",karaoke)
        for method in (speech,karaoke):
            for forbidden in ("stopCaptioning(", "startCaptioning(",
                              "player_->stop(", "player_->play(",
                              "stopReceiver(", "startReceiver("):
                self.assertNotIn(forbidden,method)

    def test_live_lyrics_catalog_uses_exact_file_that_python_watches(self):
        publisher=section("QString liveRadioLyricsCatalogPath() const",
                          "void renderFullLyricsWindow(")
        self.assertIn('"/tihulu-radio-lyrics-"',publisher)
        self.assertIn("QCoreApplication::applicationPid()",publisher)
        self.assertIn("QSaveFile output(path)",publisher)
        self.assertIn("publishLiveRadioLyricsCatalog(",UI)
        self.assertIn("clearLiveRadioLyricsCatalog()",UI)
        self.assertIn('location.name.replace(\n        "tihulu-radio-captions-","tihulu-radio-lyrics-",1)',AI)
        self.assertIn('marker=(lyric_path.stat().st_mtime_ns',AI)
        updated=section("void pollLyricsRefreshResult()",
                        "void fetchLyrics(bool automatic=false)")
        self.assertIn("publishLiveRadioLyricsCatalog(value)",updated)
        loaded=section("void updateLyrics()", "MediaWidget *player_")
        self.assertIn("publishLiveRadioLyricsCatalog(value)",loaded)

    def test_karaoke_model_uses_real_lyric_words_and_recent_audio(self):
        self.assertIn('qwen_audio_pcm=recent["pcm"]',AI)
        self.assertIn('lyric_match["text"],alignment_option["language"],12',AI)
        self.assertIn("align_observed_phrase,qwen_audio_pcm",AI)
        self.assertIn('"karaoke_alignment_engine":("qwen" if qwen_refinement else "whisper")',AI)
        self.assertIn('"karaoke_sync_history_seconds"',AI)
        self.assertIn("sync_history_seconds*1000",AI)
        self.assertEqual(karaoke_alignment_choice(
            "en",qwen_installed=True)["engine"],"qwen")
        for code in ("tr","ar","und",None):
            with self.subTest(code=code):
                self.assertEqual(karaoke_alignment_choice(
                    code,qwen_installed=True)["engine"],"whisper")
        self.assertEqual(karaoke_alignment_choice(
            "de",qwen_installed=False)["engine"],"whisper")

    def test_opt_in_lrc_flow_is_never_called_acoustic_verification(self):
        self.assertIn('"estimated"',UI)
        estimated=section("void showEstimatedLrcFlow(qint64 now)",
                          "void showKaraokeLine(")
        self.assertIn('QLatin1String("estimated")',estimated)
        self.assertIn("lyricCues_.isEmpty()",estimated)
        self.assertIn("lastUnmatchedVoiceUntilMs_>now",estimated)
        self.assertIn("karaokeWordAnchors_=QJsonArray()",estimated)
        self.assertIn("NOT AUDIO VERIFIED",estimated)
        self.assertNotIn("karaoke_sync_refresh_token",estimated)
        self.assertNotIn("showRadioCanvasCaption(",estimated)
        self.assertIn("showEstimatedLrcFlow(now);",UI)


if __name__=="__main__":
    unittest.main()
