"""Contracts for independent radio Karaoke timing and opt-in estimated lyric sweep.

These checks guard native Qt/C++ integration when the full Kaffeine build is
not available in local Python jobs. Actual speaker/DAC lip-sync remains
hardware-dependent and is NOT asserted here.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
RADIO = (ROOT / "kaffeine_next/native_radio_tab.h").read_text(encoding="utf-8")


class RadioKaraokeIndependentTimingTests(unittest.TestCase):
    def test_new_mode_is_opt_in_and_audio_matched_stays_default(self):
        self.assertIn('karaokePolicy_->addItem(tr("Karaoke · Audio matched"),"verified")', RADIO)
        self.assertIn('karaokePolicy_->addItem(tr("Karaoke · Lyrics found (preview)"),"found")', RADIO)
        self.assertIn('Karaoke · Lyrics found + lip-sync (estimated)', RADIO)
        self.assertIn('QLatin1String("found-sync")', RADIO)
        self.assertIn('QLatin1String("karaokeMatchPolicy")', RADIO)
        self.assertIn('QLatin1String("verified")).toString()', RADIO)

    def test_preview_runs_for_both_found_policies_and_respects_manual_navigation(self):
        preview = RADIO.split("void showFoundKaraokePreview(qint64 now)")[1].split("void showKaraokeLine")[0]
        self.assertIn('policy!=QLatin1String("found") && !previewLipSync', preview)
        self.assertIn('policy==QLatin1String("found-sync")', preview)
        self.assertIn("previewIndexShift_", preview)
        self.assertIn("lyricsOffset_->value()", preview)
        self.assertIn("karaokePreviewSpeed_->value()", preview)
        self.assertIn("lastVerifiedLyricMs_>0", preview)
        self.assertNotIn("showRadioCanvasCaption(", preview)

    def test_sweep_is_separate_from_whisper_word_anchors_and_exposes_uncertainty(self):
        preview = RADIO.split("void showFoundKaraokePreview(qint64 now)")[1].split("void showKaraokeLine")[0]
        self.assertIn("previewSeconds", preview)
        self.assertIn('QLatin1String("start")', preview)
        self.assertIn('QLatin1String("end")', preview)
        self.assertIn("6000.", preview)
        self.assertIn('QRegularExpression wordPattern', preview)
        self.assertIn("wordPattern.globalMatch(line)", preview)
        self.assertIn("swept", preview)
        self.assertIn("Qt::RichText", preview)
        self.assertIn("unverified lip-sync", preview)
        self.assertIn("karaokeWordAnchors_=QJsonArray()", preview)
        self.assertNotIn("cue.wordAnchors", preview)

    def test_verified_karaoke_hold_is_not_driven_by_subtitle_reading_mode(self):
        verified = RADIO.split("void showKaraokeLine(const TimedPlainLyric &cue)")[1].split(
            "void updateRadioCaptionTypography()", 1)[0]
        self.assertIn("lastKaraokeUntilMs_=now+5500;", verified)
        self.assertIn("lastWord+activePlaybackCacheMs_", verified)
        self.assertNotIn("radioCaptionReadingHoldMs(", verified)
        self.assertNotIn("radioReadingPreset_", verified)
        reading = RADIO.split("int radioCaptionReadingHoldMs(")[1].split(
            "void setRadioLyricMatchStatus(", 1)[0]
        self.assertIn("radioReadingPreset_", reading)
        self.assertNotIn("lastKaraokeUntilMs_", reading)

    def test_estimated_sweep_does_not_change_original_or_translated_captions(self):
        preview = RADIO.split("void showFoundKaraokePreview(qint64 now)")[1].split("void showKaraokeLine")[0]
        for forbidden in ("captionProcess_.start(", "captionProcess_.kill(",
                          "radioCanvasCaption_->setText(", "cueQueue_.clear()"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, preview)
        self.assertIn("karaokeTranslationsEnabled_->isChecked()", preview)
        self.assertIn("selectedRadioTargets()", preview)


if __name__ == "__main__":
    unittest.main()
