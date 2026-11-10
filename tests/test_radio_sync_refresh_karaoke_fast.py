"""10s reusable Whisper sync history and independent Live-fast caption timing."""
from pathlib import Path
import unittest

RADIO=(Path(__file__).resolve().parents[1] /
       "kaffeine_next/native_radio_tab.h").read_text(encoding="utf-8")


def section(start,end):
    start_i=RADIO.index(start)
    return RADIO[start_i:RADIO.index(end,start_i)]


class KaraokeAndFastRefreshTests(unittest.TestCase):
    def test_refresh_button_reuses_timestamps_without_audio_buffer_reset(self):
        click=section("connect(radioSyncRefresh_,&QPushButton::clicked",
                      "connect(quickAi_,&QCheckBox::toggled")
        self.assertIn("refreshRadioLipSync();",click)
        method=section("void refreshRadioLipSync() {",
                       "void refreshKaraokeWordHighlight(")
        for marker in ("lyricOffsetConsistency_=0;",
                       "lastLyricSyncUpdateMs_=0;", "lastLyricDirection_=0;",
                       "lastHighlightedKaraokeWord_=-2;",
                       "refreshKaraokeWordHighlight(now);",
                       "karaokeSyncHistorySeconds_", "recentKaraokeEvidence_",
                       "showKaraokeLine(e.cue);",
                       "lyricsOffset_->value()", "radioOffsetMs_->value()",
                       "activePlaybackCacheMs_"):
            with self.subTest(marker=marker):
                self.assertIn(marker,method)
        for forbidden in ("lagSamples_.clear();", "cueQueue_", "retimedWhisperCues",
                          "stopReceiver(", "startReceiver(", "player_->stop(",
                          "player_->play(", "stopCaptioning(", "startCaptioning(",
                          "fetchLyrics(", "clearKaraokeLine(", "cueQueue_.clear(",
                          "karaokeWordAnchors_.clear(", "previewStartedMs_=0;"):
            self.assertNotIn(forbidden,method)

    def test_ai_lipsync_refresh_only_reschedules_unshown_speech(self):
        click=section("connect(aiSyncRefresh_,&QPushButton::clicked",
                      "connect(radioSyncRefresh_,&QPushButton::clicked")
        self.assertIn("refreshRadioCaptionLipSync();",click)
        method=section("void refreshRadioCaptionLipSync() {",
                       "void refreshRadioLipSync() {")
        for marker in ("lagSamples_.clear();","cueQueue_",
                       "unoffsetDueMs", "requestedCacheAtQueueMs",
                       "displayedRadioChunk_", "displayDueRadioCues(now)",
                       "radioOffsetMs_->value()"):
            self.assertIn(marker,method)
        for forbidden in ("plainLyricQueue_", "verifiedLyricQueue_",
                          "karaokeWordAnchors_", "karaokeSyncRefreshToken_",
                          "refreshKaraokeWordHighlight(", "startCaptioning(",
                          "stopCaptioning(", "player_->play("):
            self.assertNotIn(forbidden,method)

    def test_only_Whisper_epoch_times_recalculate_pending_cues(self):
        method=section("void refreshRadioLipSync() {",
                       "void refreshKaraokeWordHighlight(")
        self.assertIn("entry.wordAnchors.isEmpty()",method)
        self.assertIn('QLatin1String("epoch_ms")',method)
        self.assertIn("entry.dueMs=qMax(now,captured+activePlaybackCacheMs_",method)
        self.assertIn("updatePending(verifiedLyricQueue_);",method)
        self.assertIn("updatePending(plainLyricQueue_);",method)

    def test_fast_caption_polls_faster_without_affecting_karaoke(self):
        hold=section("int radioCaptionReadingHoldMs(",
                     "void setRadioLyricMatchStatus(")
        self.assertIn("cueQueue_.size()>=2?250:900",hold)
        self.assertIn("if(preset<=0) {",hold)
        self.assertNotIn("karaokeWordAnchors_",hold)
        self.assertIn("150:300",RADIO)

    def test_legacy_speed_does_not_guess_lip_sync(self):
        preview=section("void showFoundKaraokePreview(qint64 now)",
                        "void showKaraokeLine(")
        self.assertNotIn("previewSeconds",preview)
        self.assertNotIn("qRound64(lrc",preview)
        self.assertNotIn("wordPattern",preview)
        self.assertIn("No guessed word sweep",preview)
        self.assertIn("karaokePreviewSpeed_->setEnabled(false)",RADIO)

    def test_10s_window_bounded_and_keeps_same_song(self):
        helper=section("void pruneRecentKaraokeEvidence(qint64 now)",
                       "void refreshRadioLipSync() {")
        self.assertIn("karaokeSyncHistorySeconds_->value():10",helper)
        self.assertIn("recentKaraokeEvidence_.removeFirst()",helper)
        self.assertIn("recentKaraokeEvidence_.size()>48",helper)
        self.assertIn("first().songKey!=lastSongMetadataKey_",helper)
        self.assertIn("first().stationKey!=playingKey_",helper)
        self.assertIn("recentKaraokeEvidence_.append",helper)


if __name__=="__main__":
    unittest.main()
