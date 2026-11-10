"""Real audio gating, independent Karaoke evidence, no guessed words."""
from pathlib import Path
import unittest

RADIO=(Path(__file__).resolve().parents[1] /
       "kaffeine_next/native_radio_tab.h").read_text(encoding="utf-8")


class RadioKaraokeIndependentTimingTests(unittest.TestCase):
    def test_real_audio_mode_default_and_legacy_found_sync_key(self):
        self.assertIn('karaokePolicy_->addItem(tr("Karaoke · Audio matched"),"verified")',RADIO)
        self.assertIn('karaokePolicy_->addItem(tr("Karaoke · Lyrics found (preview)"),"found")',RADIO)
        self.assertIn('Karaoke · Lyrics found + lip-sync (audio gated)',RADIO)
        self.assertIn('QLatin1String("found-sync")',RADIO)
        self.assertIn('QLatin1String("karaokeMatchPolicy")',RADIO)

    def test_preview_manual_not_estimated_wall_clock(self):
        preview=RADIO.split("void showFoundKaraokePreview(qint64 now)",1)[1].split(
            "void showKaraokeLine(",1)[0]
        self.assertIn('policy!=QLatin1String("found") && !previewLipSync',preview)
        self.assertIn('policy==QLatin1String("found-sync")',preview)
        self.assertIn("previewIndexShift_",preview)
        self.assertIn("lastVerifiedLyricIndex_",preview)
        self.assertIn("LYRICS FOUND · UNVERIFIED",preview)
        for forbidden in ("previewStartedMs_", "previewSeconds",
                          "autoLyricSync_", "int(fraction*words.size())",
                          "qBound(0.35,end-begin", "6000.", "wordPattern"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden,preview)
        self.assertNotIn("showRadioCanvasCaption(",preview)
        self.assertIn("karaokeWordAnchors_=QJsonArray()",preview)

    def test_verified_word_anchors_are_independent_of_reading_hold(self):
        verified=RADIO.split("void showKaraokeLine(const TimedPlainLyric &cue)")[1].split(
            "void updateRadioCaptionTypography()",1)[0]
        self.assertIn("karaokeWordAnchors_=cue.wordAnchors",verified)
        self.assertIn("lastWord+activePlaybackCacheMs_",verified)
        self.assertNotIn("radioCaptionReadingHoldMs(",verified)
        self.assertNotIn("radioReadingPreset_",verified)

    def test_audio_buffer_and_10s_karaoke_evidence_are_separate(self):
        self.assertIn('karaokeSyncHistorySeconds"),',RADIO)
        self.assertIn("karaokeSyncHistorySeconds_->setRange(3,30)",RADIO)
        self.assertIn("QList<RecentKaraokeEvidence> recentKaraokeEvidence_",RADIO)
        self.assertIn("rememberKaraokeEvidence(matchedCue,now)",RADIO)
        self.assertIn("pruneRecentKaraokeEvidence(now)",RADIO)
        refresh=RADIO.split("void refreshRadioLipSync() {",1)[1].split(
            "void refreshKaraokeWordHighlight(",1)[0]
        self.assertIn("recentKaraokeEvidence_",refresh)
        self.assertIn("showKaraokeLine(e.cue);",refresh)
        self.assertNotIn("player_->stop(",refresh)
        self.assertNotIn("player_->play(",refresh)
        self.assertNotIn("stopCaptioning(",refresh)
        self.assertNotIn("startCaptioning(",refresh)
        self.assertNotIn("fetchLyrics(",refresh)

    def test_sound_and_translation_streams_are_untouched(self):
        preview=RADIO.split("void showFoundKaraokePreview(qint64 now)",1)[1].split(
            "void showKaraokeLine(",1)[0]
        for forbidden in ("captionProcess_.start(", "captionProcess_.kill(",
                          "radioCanvasCaption_->setText(", "cueQueue_.clear()"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden,preview)
        self.assertIn("karaokeTranslationsEnabled_->isChecked()",preview)


if __name__ == "__main__":
    unittest.main()
