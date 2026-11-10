"""Contracts for shared Lip-sync Refresh and Live-fast radio caption timing.

Static source-contract tests complement separate Qt5/native compile checks.
Real DAC latency must be measured on the user's Linux desktop.
"""
from pathlib import Path
import unittest

RADIO=(Path(__file__).resolve().parents[1] /
       "kaffeine_next/native_radio_tab.h").read_text(encoding="utf-8")


def section(start, end):
    a=RADIO.index(start)
    return RADIO[a:RADIO.index(end,a)]


class KaraokeAndFastRefreshTests(unittest.TestCase):
    def test_refresh_button_updates_both_lipsync_paths(self):
        click=section("connect(radioSyncRefresh_,&QPushButton::clicked",
                      "connect(quickAi_,&QCheckBox::toggled")
        self.assertIn("refreshRadioLipSync();",click)
        method=section("void refreshRadioLipSync() {",
                       "void refreshKaraokeWordHighlight(")
        for marker in (
            "lagSamples_.clear();", "lyricOffsetConsistency_=0;",
            "lastLyricSyncUpdateMs_=0;", "lastLyricDirection_=0;",
            "lastHighlightedKaraokeWord_=-2;",
            "previewLastHighlightedWord_=-2;",
            "previewLastIndex_=-1;",
            "refreshKaraokeWordHighlight(now);",
            "showFoundKaraokePreview(now);",
            "lyricsOffset_->value()",
            "radioOffsetMs_->value()",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, method)

    def test_refresh_reanchors_only_real_whisper_word_times(self):
        method=section("void refreshRadioLipSync() {",
                       "void refreshKaraokeWordHighlight(")
        self.assertIn("entry.wordAnchors.isEmpty()",method)
        self.assertIn('QLatin1String("epoch_ms")',method)
        self.assertIn("entry.dueMs=qMax(now,captured+activePlaybackCacheMs_",method)
        self.assertIn("updatePending(verifiedLyricQueue_);",method)
        self.assertIn("updatePending(plainLyricQueue_);",method)
        # The current song, original text and audio stream are retained.
        for forbidden in (
            "stopReceiver(", "startReceiver(", "player_->stop(",
            "player_->play(", "stopCaptioning(", "startCaptioning(",
            "fetchLyrics(", "clearKaraokeLine(", "previewStartedMs_=0",
            "lyricRawLines_.clear(", "karaokeWordAnchors_.clear(",
            "cueQueue_.clear(",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden,method)

    def test_live_fast_avoids_rapid_flicker_without_reading_delay(self):
        hold=section("int radioCaptionReadingHoldMs(",
                     "void setRadioLyricMatchStatus(")
        self.assertIn("cueQueue_.size()>=2?250:900",hold)
        self.assertIn("if(preset<=0) {",hold)
        self.assertNotIn("karaokeWordAnchors_",hold)
        self.assertIn("150:300",RADIO)
        poll=section("void pollCaption() {",
                     "void stopCaptioning() {")
        self.assertIn("fastReading && lateBy>800",poll)
        self.assertIn("Lip-sync Refresh cannot undo model latency",poll)

    def test_estimated_preview_uses_independent_timeline_on_refresh(self):
        method=section("void refreshRadioLipSync() {",
                       "void refreshKaraokeWordHighlight(")
        self.assertIn("estimated preview timeline kept",method)
        preview=section("void showFoundKaraokePreview(qint64 now)",
                        "void showKaraokeLine(")
        self.assertIn("karaokePreviewSpeed_->value()",preview)
        self.assertIn("previewStartedMs_",preview)
        self.assertNotIn("radioCaptionReadingHoldMs(",preview)


if __name__=="__main__":
    unittest.main()
