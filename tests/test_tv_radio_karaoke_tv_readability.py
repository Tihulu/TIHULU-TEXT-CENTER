"""Blue-screen karaoke lyric view and TV-style radio reading contracts.

No hardware, Qt display, lyrics service, GPU or streaming required.
Kaffeine's C++ compilation and behavior are checked by native CI.
"""
from pathlib import Path
import unittest

UI=(Path(__file__).resolve().parents[1]/
    "kaffeine_next/native_radio_tab.h").read_text(encoding="utf-8")


def code_section(start,end):
    a=UI.index(start)
    return UI[a:UI.index(end,a)]


class RadioKaraokeAccessibilityTests(unittest.TestCase):
    def test_large_blue_player_keeps_bottom_whisper_subtitles_independent(self):
        for text in (
            "karaokePanel_=new QWidget(radioCanvas_)",
            "karaokePrevious_=new QLabel(karaokePanel_)",
            "karaokeCurrent_=new QLabel(karaokePanel_)",
            "karaokeNext_=new QLabel(karaokePanel_)",
            "karaokeTranslation_=new QLabel(karaokePanel_)",
            "karaokeSource_=new QLabel(karaokePanel_)",
            "captionSurface->addWidget(karaokePanel_",
            "captionSurface->addWidget(radioLyricMatchStatus_)",
            "captionSurface->addWidget(radioCanvasCaption_)",
            "setMinimumHeight(235)",
            "color:#ffe17c",
            "color:#94a7b9",
            "color:#ffdc61",
            "AUDIO MATCH: %3% · LINE %4",
            "SOURCE: %2",
        ):
            self.assertIn(text,UI)

    def test_user_may_disable_karaoke_or_yellow_translations_independently(self):
        for required in (
            "karaokeEnabled_=new QCheckBox(",
            "karaokeTranslationsEnabled_=new QCheckBox(",
            'QLatin1String("karaokeDisplayEnabled"),true',
            'QLatin1String("karaokeTranslationsEnabled"),true',
            "karaokePanel_->setVisible(enabled &&",
            "karaokeTranslation_->setVisible(enabled &&",
            "radioPlaybackRow_->insertWidget(3,karaokeEnabled_)",
            "radioPlaybackRow_->insertWidget(4,karaokeTranslationsEnabled_)",
        ):
            self.assertIn(required,UI)
        renderer=code_section("void showKaraokeLine(", "void updateRadioCaptionTypography()")
        self.assertIn("const QString value=cue.translations.value(lang)",renderer)
        self.assertIn("for(const QString &lang:selectedRadioTargets())",renderer)
        self.assertIn("karaokeTranslation_->setVisible(karaokeTranslationsEnabled_",renderer)
        self.assertIn("karaokeEnabled_->isChecked()",renderer)
        self.assertNotIn("radioCanvasCaption_->setVisible(false)",renderer)

    def test_real_audio_matched_lyric_index_drives_karaoke_neighbors(self):
        self.assertIn("int lineIndex;",UI)
        self.assertIn("int index=-1",UI)
        self.assertIn("QString original;",UI)
        self.assertIn("QJsonObject translations;",UI)
        self.assertIn("lyricRawLines_.at(index-1)",UI)
        self.assertIn("lyricRawLines_.at(index+1)",UI)
        self.assertIn('QLatin1String("plain_lines")',UI)
        self.assertIn('lastLyricsProvider_=provider.isEmpty()',UI)
        self.assertIn('matched.value(QLatin1String("index")).toInt(-1)',UI)
        self.assertIn("showKaraokeLine(cue);",UI)
        self.assertNotIn("showRadioCanvasCaption(cue.text,true);",UI)
        self.assertIn("showRadioCanvasCaption(cue.text);",UI)
        self.assertIn("clearKaraokeLine();",UI)
        self.assertIn("lastKaraokeUntilMs_",UI)
        self.assertIn("lastUnmatchedVoiceUntilMs_",UI)
        self.assertIn("lyricRawLines_.clear();",UI)
        self.assertIn("lastLyricsProvider_.clear();",UI)
        self.assertNotIn("setWordTimingFromDls",UI)

    def test_tv_style_adaptive_mode_reuses_full_sentence_readability_principles(self):
        for expected in (
            "TV-style Adaptive · readable + live",
            'QLatin1String("radioReadingPreset"),3',
            "qBound(2800,chars*63,9000)",
            "qMin(adjusted,2500)",
            "qMin(adjusted,4000)",
            "captionReadingHoldUntilMs_",
            "AI captions ↔ audio (estimated)",
            "Actual libVLC/ALSA audio presentation time is unmeasured",
        ):
            self.assertIn(expected,UI)
        self.assertNotIn("karaokeClockIsWordAccurate",UI)


if __name__=="__main__":
    unittest.main()
