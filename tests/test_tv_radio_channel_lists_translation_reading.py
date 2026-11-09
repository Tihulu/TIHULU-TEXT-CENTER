"""Radio usability regression contracts with no receiver or network access."""
from pathlib import Path
import unittest

from tv_center.radio_ai import effective_radio_translation_enabled

ROOT=Path(__file__).resolve().parents[1]
RADIO=(ROOT/"kaffeine_next/native_radio_tab.h").read_text(encoding="utf-8")
PATCH=(ROOT/"kaffeine_next/patch_upstream.py").read_text(encoding="utf-8")
WORKER=(ROOT/"tv_center/radio_ai.py").read_text(encoding="utf-8")


class MediaRadioUxTests(unittest.TestCase):
    def test_home_does_not_push_shortcuts_to_bottom(self):
        self.assertIn("frame->addLayout(gridLayout,0);", PATCH)
        self.assertNotIn("frame->addLayout(gridLayout,1);", PATCH)
        self.assertIn("frame->addStretch(1);", PATCH)

    def test_status_and_caption_have_separate_surfaces(self):
        self.assertIn("radioCanvas_ = new QLabel(QString(), playerHost_)", RADIO)
        self.assertIn("radioCanvasStation_=new QLabel(", RADIO)
        self.assertIn("captionSurface->addWidget(radioCanvasStation_", RADIO)
        self.assertIn("captionSurface->addWidget(radioCanvasCaption_)", RADIO)
        self.assertNotIn("radioCanvas_->setText(", RADIO)
        self.assertIn("radioCanvasStation_->setText(", RADIO)

    def test_named_lists_are_manual_and_persist_locally(self):
        for text in ("stationListPicker_=new QComboBox",
                     "newStationList_=new QPushButton",
                     "addStationList_=new QPushButton",
                     "removeStationList_=new QPushButton",
                     "deleteStationList_=new QPushButton",
                     "stationListOnly_=new QCheckBox",
                     'QLatin1String("dabNamedLists")',
                     "void loadStationLists()", "void saveStationLists()",
                     "void createNamedStationList()",
                     "void changeSelectedStationList(bool add)",
                     "stationLists_.value(listName).contains(key)",
                     "loadStationLists();"):
            with self.subTest(value=text):
                self.assertIn(text,RADIO)
        self.assertIn("void selectStation(QTreeWidgetItem *item)",RADIO)
        self.assertIn("favorites_.contains(key)",RADIO)

    def test_radio_translation_consent_is_local_only(self):
        self.assertFalse(effective_radio_translation_enabled(False,False,"argos"))
        for backend in ("argos","nllb","madlad"):
            self.assertTrue(effective_radio_translation_enabled(False,True,backend))
            self.assertFalse(effective_radio_translation_enabled(False,False,backend))
        self.assertFalse(effective_radio_translation_enabled(False,True,"deepl"))
        self.assertTrue(effective_radio_translation_enabled(True,False,"deepl"))
        for text in ('QLatin1String("radioTranslationOptIn"),false',
                     'QStringLiteral("radio_translations")',
                     'QLatin1String("--radio-translations")',
                     "writeRadioLanguageControls();",
                     'quickTranslate_=new QCheckBox(tr("Radio translate · OFF")'):
            with self.subTest(text=text):
                self.assertIn(text,RADIO)
        self.assertIn('effective_radio_translation_enabled(',WORKER)
        self.assertIn('if type(requested_translation) is bool',WORKER)
        self.assertIn('"radio_translation_opt_in":radio_translations',WORKER)

    def test_reading_selection_applies_without_restarting_audio(self):
        begin=RADIO.index('connect(radioReadingPreset_,')
        end=RADIO.index('connect(radioCaptionFontSize_',begin)
        handler=RADIO[begin:end]
        self.assertIn("captionDisplayedStartedMs_",handler)
        self.assertIn("radioCaptionReadingHoldMs(",handler)
        self.assertIn("displayDueRadioCues(now)",handler)
        self.assertNotIn("startCaptioning(",handler)
        self.assertNotIn("player_->play(",handler)
        self.assertIn("lagSamples_.size()>=3",RADIO)
        self.assertIn("qBound(0,(p80-2500)/3,1700)",RADIO)

    def test_pcm_word_onset_is_not_fabricated_on_cpu(self):
        self.assertIn('if cues and detection.get("asr_words")',WORKER)
        self.assertIn("first_word_epoch_ms=0",WORKER)
        self.assertIn('"subtitle_audio_start_epoch_ms":first_word_epoch_ms',WORKER)
        self.assertIn('QLatin1String("subtitle_audio_start_epoch_ms")',RADIO)
        self.assertIn('firstWordEpoch>now-120000',RADIO)
        self.assertIn("DAC PTS",RADIO)


if __name__=="__main__":
    unittest.main()
