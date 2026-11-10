"""Live radio lyric bar and multilingual IN regression tests.

All tests are offline. No SDR, GUI, remote lyrics or model downloads.
"""
from pathlib import Path
import unittest

from tv_center.lyrics_sync import LiveLyricMatcher

ROOT=Path(__file__).resolve().parents[1]
UI=(ROOT/"kaffeine_next/native_radio_tab.h").read_text(encoding="utf-8")
APP=(ROOT/"tv_center/__main__.py").read_text(encoding="utf-8")


class AutoLyricsLiveMatchTests(unittest.TestCase):
    def test_acquire_real_lyrics_when_tuned_in_mid_song(self):
        lyrics=[
            "Golden river over crimson hills",
            "Walking quietly between ancient buildings",
            "Waiting all night under summer starlight",
            "Another distant road along the valley",
            "Every quiet echo passes through shadows",
            "Winter morning beneath bright blue mountains",
            "Gathering around the lantern in the meadow",
            "Night falls softly over distant oceans",
            "Trees blow softly beside forgotten rivers",
            "Someone calling underneath the silver moon",
            "Dreams return again behind the silent village",
            "Our footsteps echo inside the empty station",
            "Where shadows gather beneath the silver moon",
            "Dancing with ghosts until the morning comes",
        ]
        matcher=LiveLyricMatcher(lyrics)
        self.assertIsNone(matcher.observe(
            "Welcome back listeners here are the news headlines"))
        match=matcher.observe(
            "Where shadows gather beneath the silver moon")
        self.assertIsNotNone(match)
        self.assertEqual(match["index"],12)
        self.assertGreaterEqual(match["confidence"],0.89)
        self.assertEqual(matcher.position,13)
        self.assertIsNone(matcher.observe(
            "Welcome again to our advertising programme"))

    def test_lyrics_found_not_equivalent_to_audio_match(self):
        matcher=LiveLyricMatcher([
            "The midnight rain is falling in the street",
            "We meet again beneath the neon city lights"])
        self.assertIsNone(matcher.observe(
            "Good morning from the studio and here is the traffic"))
        self.assertIsNone(matcher.observe(
            "Now another quick message from our sponsors"))

    def test_verified_match_is_shown_in_karaoke_without_hiding_speech(self):
        for required in (
            "radioLyricMatchStatus_=new QLabel(radioCanvas_)",
            "captionSurface->addWidget(radioLyricMatchStatus_)",
            "void setRadioLyricMatchStatus(const QString &message)",
            "LYRICS SEARCHING",
            "LYRICS FOUND",
            "LYRICS MATCHED %1%",
            "NOT MATCHED to this audio",
            "LYRICS NOT FOUND",
            "verifiedLyricQueue_.append",
            "verifiedLyricQueue_.first().dueMs<=now",
            "showKaraokeLine(cue)",
            "lastMatchedLyricUntilMs_",
            "real audio",
            "Whisper speech/advert fallback",
        ):
            self.assertIn(required,UI)
        self.assertIn("if(lastLyricsAutoLookup_) return;",UI)
        self.assertIn("if(lyric) return;",UI)
        self.assertIn("showRadioCanvasCaption(cue.text);",UI)
        self.assertNotIn("showRadioCanvasCaption(cue.text,true)",UI)
        self.assertIn("lastUnmatchedVoiceUntilMs_",UI)
        self.assertIn("verifiedLyricQueue_.clear();",UI)

    def test_rotating_dls_text_does_not_wipe_current_lyrics(self):
        # Announcer or broadcaster metadata may rotate while the same
        # song is playing. Only a *different song-looking* label should
        # trigger a new lookup, never just any changed DLS string.
        self.assertIn("inline TihuluDlsSong tihuluDlsSong",UI)
        self.assertIn("const TihuluDlsSong newSong=tihuluDlsSong(dls)",UI)
        self.assertIn("const QString candidate=newSong.normalizedKey();",UI)
        self.assertIn("candidate==lastSongMetadataKey_",UI)
        self.assertIn("QTimer::singleShot(5000,this,",UI)
        self.assertIn("commitPendingDlsSong(candidate,station,ticket)",UI)
        self.assertIn("lastSongDls_=acceptedDls;",UI)
        self.assertIn("lastSongDls_.clear();",UI)
        self.assertIn("lastSongMetadataKey_.clear();",UI)

    def test_spoken_auto_detect_and_other_supported_languages_are_listed(self):
        self.assertIn('Auto detect · Whisper (selected local model)',UI)
        self.assertIn('QLatin1String("speech_languages")',UI)
        self.assertIn('QSignalBlocker block(speechLanguage_)',UI)
        self.assertIn('const int index=speechLanguage_->findData(previous)',UI)
        self.assertIn('speech_model_present',APP)
        self.assertIn('speech_models_installed',APP)
        self.assertIn('for code in LANGUAGES if not english_only or code=="en"',APP)
        self.assertIn("FasterWhisperCUDA().installed()",APP)
        self.assertIn("ModelLibrary().installed()",APP)


if __name__=="__main__":
    unittest.main()
