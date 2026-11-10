"""Regression for independent radio subtitle/karaoke controls and recovery.

Offline-only. No GPU, SDR, web lyrics or audio clock is assumed to run here.
"""
from pathlib import Path
import unittest

from tv_center.lyrics_sync import LiveLyricMatcher

ROOT=Path(__file__).resolve().parents[1]
UI=(ROOT/"kaffeine_next/native_radio_tab.h").read_text(encoding="utf-8")
WORKER=(ROOT/"tv_center/radio_ai.py").read_text(encoding="utf-8")


def section(first, last):
    begin=UI.index(first)
    return UI[begin:UI.index(last, begin)]


class RadioLyricsModelAndOffsetTests(unittest.TestCase):
    def test_user_threshold_allows_below_65_but_requires_heard_words(self):
        phrase="Moonlight echoes over distant mountains rivers"
        self.assertIsNone(LiveLyricMatcher([phrase],threshold=.65).observe(
            "Moonlight echoes over"))
        score=LiveLyricMatcher([phrase],threshold=.55).observe(
            "Moonlight echoes over")
        self.assertIsNotNone(score)
        self.assertLess(score["confidence"],.65)
        self.assertIsNone(LiveLyricMatcher([phrase],threshold=0.).observe(
            "Moonlight echoes"))
        self.assertEqual(LiveLyricMatcher([phrase],threshold=0.).threshold,0.)
        for invalid in (-.01,1.01,True,"zero"):
            with self.subTest(invalid=invalid),self.assertRaises(ValueError):
                LiveLyricMatcher([phrase],threshold=invalid)

    def test_Whisper_tolerant_words_are_distinct_from_exact(self):
        phrase="Moonlight echoes over distant mountains rivers"
        self.assertIsNone(LiveLyricMatcher(
            [phrase],threshold=.55,mode="lexical").observe(
            "Moonlights echoes over"))
        fuzzy=LiveLyricMatcher([phrase],threshold=.55,mode="fuzzy")
        self.assertIsNotNone(fuzzy.observe("Moonlights echoes over"))
        fuzzy.set_mode("lexical")
        self.assertEqual(fuzzy.mode,"lexical")
        with self.assertRaises(ValueError):
            fuzzy.set_mode("nonexistent")
        with self.assertRaises(ValueError):
            LiveLyricMatcher([phrase],mode="nonexistent")

    def test_native_user_model_selectors_are_independent(self):
        for expected in (
            "lyricMatchThreshold_->setRange(0,100)",
            "lyricMatchMode_->addItem",
            "lyricMatchMode_->currentData().toString()",
            "karaokeAligner_->addItem",
            "karaokeAligner_->currentData().toString()",
            'QLatin1String("karaokeAligner_")+mode',
            "loadModeAligner();",
            '"lyric_match_mode"',
            '"karaoke_aligner"',
            "writeRadioLanguageControls()",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected,UI)
        for expected in (
            'requested_mode=payload.get("lyric_match_mode")',
            'requested_aligner=payload.get("karaoke_aligner")',
            'requested=karaoke_aligner)',
            'mode=lyric_match_mode)',
            '"karaoke_alignment_requested":karaoke_aligner',
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected,WORKER)

    def test_karaoke_word_time_does_not_include_ai_caption_offset(self):
        word=section("void refreshKaraokeWordHighlight(qint64 now)",
                     "void showFoundKaraokePreview(qint64 now)")
        self.assertIn("lyricsOffset_->value()",word)
        self.assertNotIn("radioOffsetMs_->value()",word)
        refresh=section("void refreshRadioLipSync() {",
                        "void refreshKaraokeWordHighlight(")
        self.assertIn("lyricsOffset_->value()",refresh)
        self.assertNotIn("radioOffsetMs_->value()+lyricsOffset_->value()",refresh)
        speech=section("void refreshRadioCaptionLipSync() {",
                       "void refreshRadioLipSync() {")
        self.assertIn("radioOffsetMs_->value()",speech)
        self.assertNotIn("lyricsOffset_->value()",speech)

    def test_plain_lyrics_in_lrc_estimated_mode_have_static_fallback(self):
        method=section("void showFoundKaraokePreview(qint64 now)",
                       "void showKaraokeLine(")
        self.assertIn("estimatedNoLrc",method)
        self.assertIn('lyricCues_.isEmpty()',method)
        self.assertIn("No timestamped LRC: preview only",method)
        self.assertIn("karaokeWordAnchors_=QJsonArray()",method)
        self.assertNotIn("player_->play(",method)
        self.assertNotIn("captionProcess_.kill(",method)


class RadioWhisperContinuityTests(unittest.TestCase):
    def test_unexpected_worker_eof_does_not_disarm_ai(self):
        finished=section(
            "connect(&captionProcess_,QOverload<int,QProcess::ExitStatus>::of(",
            "connect(lyrics_, &QPushButton::clicked")
        self.assertIn("if(!quickAi_ || !quickAi_->isChecked()) return;",finished)
        self.assertIn("scheduleCaptionRecovery();",finished)
        self.assertNotIn("quickAi_->setChecked(false)",finished)
        self.assertIn("errorOccurred",finished)
        self.assertIn("AI captions ON",finished)

    def test_auto_recovery_retries_with_backoff_not_retune(self):
        method=section("void scheduleCaptionRecovery() {",
                       "void startCaptioning() {")
        for marker in ("checkCaptionRecovery()", "captionRecoveryFailures_",
                       "qint64(60000)", "quickAi_->isChecked()",
                       "playingKey_.isEmpty()", "shuttingDown_", "scanning_",
                       "tvHandoffInProgress_", "active()"):
            with self.subTest(marker=marker):
                self.assertIn(marker,method)
        for forbidden in ("player_->play(", "player_->stop(", "stopReceiver(",
                          "startReceiver(", "quickAi_->setChecked("):
            self.assertNotIn(forbidden,method)
        self.assertIn("checkCaptionRecovery();",UI)
        stop=section("void stopCaptioning() {","void beginLyricListening() {")
        self.assertIn("captionRecoveryNextMs_=0;",stop)

    def test_stopping_song_lyrics_does_not_disable_whisper_captions(self):
        stop=section("void stopLyrics() {","void cancelLyricsRefresh() {")
        self.assertNotIn('quickAi_->setChecked(false)',stop)
        self.assertNotIn('quickAi_->setText(tr("AI captions · OFF"))',stop)
        self.assertIn("(!quickAi_ || !quickAi_->isChecked())",stop)


if __name__=="__main__":
    unittest.main()
