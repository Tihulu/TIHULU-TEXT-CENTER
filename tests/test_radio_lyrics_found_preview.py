"""Lyrics Found is now a STATIC viewer until actual sung words are heard.

No LRC wall-clock, six-second line timer or interpolation can claim lip-sync.
"""
from pathlib import Path
import unittest

RADIO=(Path(__file__).resolve().parents[1] /
       "kaffeine_next/native_radio_tab.h").read_text(encoding="utf-8")


class LyricsFoundPreviewTests(unittest.TestCase):
    def test_audio_verified_remains_default_and_old_setting_migrates(self):
        self.assertIn('karaokePolicy_->addItem(tr("Karaoke · Audio matched"),"verified")',RADIO)
        self.assertIn('QLatin1String("found-sync")',RADIO)
        self.assertIn('karaokePolicy_->findData(savedPolicy)',RADIO)
        self.assertIn('policyIndex<0?0:policyIndex',RADIO)
        self.assertIn("Lip-sync waiting for AUDIO MATCH",RADIO)

    def test_never_overwrites_Whisper_and_does_not_invent_word_times(self):
        preview=RADIO.split("void showFoundKaraokePreview(qint64 now) {",1)[1].split(
            "void showKaraokeLine(",1)[0]
        self.assertIn("!lyricsEnabled_ || !lyricLoaded_",preview)
        self.assertIn("LYRICS FOUND · UNVERIFIED",preview)
        self.assertIn("karaokeWordAnchors_=QJsonArray()",preview)
        self.assertIn("karaokeCurrent_->setText(line)",preview)
        self.assertNotIn("showKaraokeLine(",preview)
        self.assertNotIn("showRadioCanvasCaption(",preview)

    def test_no_DLS_LRC_or_six_second_auto_seek(self):
        preview=RADIO.split("void showFoundKaraokePreview(qint64 now) {",1)[1].split(
            "void showKaraokeLine(",1)[0]
        for banned in ("songStartMs_", "manualSongStartMs_",
                       "previewStartedMs_", "previewSeconds",
                       "previewClockNow", "previewSpeedCompensationMs_",
                       "qRound64(lrc", "int(fraction*words.size())",
                       "wordPattern.globalMatch", "Qt::RichText",
                       "estimate=i", "6000."):
            with self.subTest(banned=banned):
                self.assertNotIn(banned,preview)
        self.assertIn("const int anchored=lastVerifiedLyricIndex_",preview)
        self.assertIn("anchored+previewIndexShift_",preview)
        self.assertIn("STATIC until Whisper hears matching words",preview)

    def test_manual_previous_next_and_existing_translations(self):
        preview=RADIO.split("void showFoundKaraokePreview(qint64 now) {",1)[1].split(
            "void showKaraokeLine(",1)[0]
        self.assertIn("karaokePrevious_->setText(lineAt(index-1))",preview)
        self.assertIn("karaokeNext_->setText(lineAt(index+1))",preview)
        self.assertIn("previewIndexShift_",preview)
        self.assertIn('QLatin1String("translations")',preview)
        self.assertIn("selectedRadioTargets()",preview)
        self.assertIn("if(!value.isEmpty())",preview)
        self.assertIn("karaokeTranslationsEnabled_->isChecked()",preview)
        self.assertIn("previewPrevious_=new QPushButton",RADIO)
        self.assertIn("previewNext_=new QPushButton",RADIO)
        self.assertIn("karaokePreviewSpeed_->setEnabled(false)",RADIO)

    def test_unmatched_speech_never_overwrites_loaded_preview(self):
        status=RADIO.split(
            "void setRadioLyricMatchStatus(const QString &message) {",1)[1].split(
            "void showRadioCanvasCaption(",1)[0]
        self.assertIn('const bool previewMode=policy==QLatin1String("found")',status)
        self.assertIn('policy==QLatin1String("found-sync")',status)
        self.assertIn("lyricsEnabled_ && lyricLoaded_",status)
        self.assertIn("!lyricRawLines_.isEmpty() || !lyricCues_.isEmpty()",status)
        self.assertIn("showFoundKaraokePreview(QDateTime::currentMSecsSinceEpoch());",status)
        self.assertLess(status.index("showFoundKaraokePreview("),
                        status.index("Lyrics retrieved · listening for actual sung words"))
        polling=RADIO.split("void pollCaption() {",1)[1].split(
            "void stopCaptioning()",1)[0]
        self.assertIn("clearKaraokeLine();",polling)
        self.assertIn("showFoundKaraokePreview(now);",polling)
        self.assertLess(polling.index("clearKaraokeLine();"),
                        polling.index("showFoundKaraokePreview(now);"))

    def test_lookup_result_and_refresh_render_lyrics_immediately(self):
        loader=RADIO.split("void updateLyrics() {",1)[1].split(
            "MediaWidget *player_",1)[0]
        self.assertIn("showFoundKaraokePreview(now);",loader)
        refresher=RADIO.split("void pollLyricsRefreshResult() {",1)[1].split(
            "void fetchLyrics(bool automatic=false) {",1)[0]
        self.assertIn("showFoundKaraokePreview(now);",refresher)
        preview=RADIO.split("void showFoundKaraokePreview(qint64 now) {",1)[1].split(
            "void showKaraokeLine(",1)[0]
        self.assertIn("!lyricCues_.isEmpty() &&",preview)
        self.assertIn("lyricRawLines_.isEmpty()",preview)
        self.assertIn("karaokeCurrent_->setText(line)",preview)

    def test_song_change_resets_verified_evidence(self):
        self.assertIn("recentKaraokeEvidence_.clear();",RADIO)
        self.assertIn("lastVerifiedLyricIndex_=-1;",RADIO)
        self.assertIn("showFoundKaraokePreview(now);",RADIO)


if __name__ == "__main__":
    unittest.main()
