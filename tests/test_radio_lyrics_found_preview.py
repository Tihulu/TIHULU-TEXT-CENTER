"""Regression contract for user-opted Lyrics Found Karaoke preview.

Audio verified remains default; plain lyric preview is intentionally marked
unverified with no fabricated ASR word times, and standard Whisper captions
remain independent below the blue song-lyric panel.
"""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
RADIO=(ROOT/"kaffeine_next/native_radio_tab.h").read_text(encoding="utf-8")


class LyricsFoundPreviewTests(unittest.TestCase):
    def test_verified_only_remains_default_and_saved_mode_is_bounded(self):
        self.assertIn('karaokePolicy_->addItem(tr("Karaoke · Audio matched"),"verified")',RADIO)
        self.assertIn('karaokePolicy_->addItem(tr("Karaoke · Lyrics found (preview)"),"found")',RADIO)
        self.assertIn('QLatin1String("karaokeMatchPolicy")',RADIO)
        self.assertIn('QLatin1String("verified")',RADIO)
        self.assertIn('karaokePolicy_->findData(savedPolicy)',RADIO)
        self.assertIn('policyIndex<0?0:policyIndex',RADIO)

    def test_never_calls_verified_renderer_or_overwrites_whisper_in_preview(self):
        start=RADIO.index("void showFoundKaraokePreview(qint64 now)")
        end=RADIO.index("void showKaraokeLine(",start)
        preview=RADIO[start:end]
        self.assertIn("!lyricsEnabled_ || !lyricLoaded_",preview)
        self.assertIn('QLatin1String("found")',preview)
        self.assertIn("lastVerifiedLyricMs_>0",preview)
        self.assertIn("LYRICS FOUND · UNVERIFIED",preview)
        self.assertIn("karaokeWordAnchors_=QJsonArray()",preview)
        self.assertIn("karaokeCurrent_->setText(line)",preview)
        self.assertNotIn("showKaraokeLine(",preview)
        self.assertNotIn("showRadioCanvasCaption(",preview)
        self.assertNotIn("AUDIO MATCH: ",preview)

    def test_timed_lrc_uses_uncalibrated_dls_clock_and_manual_offset(self):
        snippet=RADIO.split("void showFoundKaraokePreview(qint64 now)")[1].split("void showKaraokeLine")[0]
        for token in ("songStartMs_", "manualSongStartMs_", "lyricsOffset_->value()",
                      'QLatin1String("start")', "previewIndexShift_",
                      "estimated broadcaster-DLS/LRC clock"):
            with self.subTest(token=token):
                self.assertIn(token,snippet)

    def test_plain_text_has_explicitly_estimated_timing_and_navigation(self):
        snippet=RADIO.split("void showFoundKaraokePreview(qint64 now)")[1].split("void showKaraokeLine")[0]
        self.assertIn("previewStartedMs_",snippet)
        self.assertIn("6000",snippet)
        self.assertIn("plain lyrics · approximate 6s/line",snippet)
        self.assertIn("karaokePrevious_->setText(lineAt(index-1))",snippet)
        self.assertIn("karaokeNext_->setText(lineAt(index+1))",snippet)
        self.assertIn("previewPrevious_=new QPushButton",RADIO)
        self.assertIn("previewNext_=new QPushButton",RADIO)

    def test_song_switch_and_lyrics_stop_reset_the_preview(self):
        self.assertGreaterEqual(RADIO.count("previewStartedMs_=0;"),2)
        self.assertGreaterEqual(RADIO.count("previewIndexShift_=0;"),2)
        self.assertIn("previewStartedMs_=now;",RADIO)
        self.assertIn("showFoundKaraokePreview(now);",RADIO)

    def test_translation_is_never_invented_and_normal_captions_continue(self):
        start=RADIO.index("void showFoundKaraokePreview(qint64 now)")
        end=RADIO.index("void showKaraokeLine(",start)
        snippet=RADIO[start:end]
        self.assertIn('QLatin1String("translations")',snippet)
        self.assertIn("selectedRadioTargets()",snippet)
        self.assertIn("if(!value.isEmpty())",snippet)
        self.assertIn("karaokeTranslationsEnabled_->isChecked()",snippet)
        self.assertNotIn("captionProcess_.start(",snippet)
        self.assertNotIn("captionProcess_.kill(",snippet)
        self.assertIn("void showRadioCanvasCaption(",RADIO)


if __name__=="__main__":
    unittest.main()
