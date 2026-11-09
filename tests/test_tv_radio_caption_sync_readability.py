"""Radio audio-caption sync accessibility and reading comfort contracts.

No RF, libVLC, GUI, GPU or model inference is invoked in these tests.
Native Qt compilation is verified separately by GitHub Actions.
"""
from pathlib import Path
import re
import unittest

UI=(Path(__file__).resolve().parents[1]/
    "kaffeine_next/native_radio_tab.h").read_text(encoding="utf-8")


def section(start: str,end: str) -> str:
    first=UI.index(start)
    return UI[first:UI.index(end,first)]


class RadioCaptionComfortContracts(unittest.TestCase):
    def test_audio_sync_controls_are_on_main_radio_page(self):
        self.assertIn('"Audio ↔ captions (estimated):"',UI)
        self.assertIn('captionEarlier_=new QPushButton(tr("−250 ms"),page)',UI)
        self.assertIn('captionLater_=new QPushButton(tr("+250 ms"),page)',UI)
        self.assertIn('captionOffsetReadout_=new QLabel(tr("Offset +0 ms"),page)',UI)
        self.assertIn('dabLayout->addLayout(captionComfortRow)',UI)
        self.assertIn('radioOffsetMs_->value()-250',UI)
        self.assertIn('radioOffsetMs_->value()+250',UI)
        self.assertIn('captionOffsetMs"),newOffset',UI)
        self.assertIn('for(auto &cue:cueQueue_) cue.dueMs+=adjustment;',UI)

    def test_comfort_controls_are_saved_and_allow_real_live_mode(self):
        self.assertIn('radioReadingPreset_->addItem(tr("Live · fast"),0)',UI)
        self.assertIn('radioReadingPreset_->addItem(tr("Comfort · recommended"),1)',UI)
        self.assertIn('radioReadingPreset_->addItem(tr("Relaxed · longer hold"),2)',UI)
        self.assertIn('QLatin1String("radioReadingPreset"),3',UI)
        self.assertIn('TV-style Adaptive · readable + live',UI)
        self.assertIn('prefs.setValue(QLatin1String("radioReadingPreset")',UI)
        self.assertIn('QLatin1String("radioCaptionFontPt"),18',UI)
        self.assertIn('radioCaptionFontSize_->setRange(14,28)',UI)
        self.assertIn('updateRadioCaptionTypography()',UI)
        self.assertIn('captionSurface->addWidget(radioCanvasCaption_)',UI)

    def test_readable_held_phrases_without_faking_true_av_clock(self):
        hold=section("int radioCaptionReadingHoldMs(","void setRadioLyricMatchStatus(")
        self.assertIn('if(preset<=0) return 0;',hold)
        self.assertIn('qBound(3300,chars*45,8500)',hold)
        self.assertIn('qBound(5500,chars*65,12000)',hold)
        self.assertIn('qBound(2800,chars*63,9000)',hold)
        self.assertIn('cueQueue_.size()>=4',hold)
        self.assertIn('cueQueue_.size()>=2',hold)
        queue=section("void displayDueRadioCues(qint64 now) {",
                      "void pollCaption() {")
        self.assertIn('captionReadingHoldUntilMs_>now',queue)
        self.assertIn('break;',queue)
        self.assertIn('radio audio uninterrupted',queue)
        self.assertIn('cueQueue_.takeFirst()',queue)
        self.assertIn('captionReadingHoldUntilMs_=0;',UI)
        self.assertIn('Actual libVLC/ALSA audio presentation time is unmeasured.',UI)
        # Caption sync changes never retune receiver hardware.
        self.assertNotIn('startReceiver()',hold)
        self.assertNotIn('player_->stop()',hold)

    def test_existing_lyrics_audio_priority_is_unchanged(self):
        bar=section("void showRadioCanvasCaption(","void displayDueRadioCues(")
        self.assertIn('if(lyric && lastUnmatchedVoiceUntilMs_>currentMs) return;',bar)
        self.assertIn('lastMatchedLyricUntilMs_',bar)
        self.assertIn('radioCaptionReadingHoldMs(text)',bar)
        self.assertIn('lastCanvasLyricMs_=currentMs;',bar)


if __name__=="__main__":
    unittest.main()
