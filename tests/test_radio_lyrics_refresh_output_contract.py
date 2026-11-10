"""Regression: Lyrics Refresh must use the exact safe output prefix.

The provider worker accepts only private /tihulu-radio-lyrics-*.json;
a different GUI prefix silently prevents every result from being written.
"""
import ast
from pathlib import Path
import unittest
from tv_center.radio_ai import checked_runtime_output

ROOT=Path(__file__).resolve().parents[1]
NATIVE=(ROOT/"kaffeine_next/native_radio_tab.h").read_text("utf-8")
RADIO=(ROOT/"tv_center/radio_ai.py").read_text("utf-8")


class LyricActionsTests(unittest.TestCase):
    def test_refresh_matches_python_runtime_output_prefix(self):
        block=NATIVE.split("void refreshCurrentLyrics() {",1)[1].split(
            "void pollLyricsRefreshResult() {",1)[0]
        self.assertIn('"/tihulu-radio-lyrics-refresh-"',block)
        self.assertNotIn('"/tihulu-lyrics-refresh-"',block)
        self.assertIn('prefix="tihulu-radio-lyrics-"',RADIO)
        self.assertIn('"lyrics-lookup"',block)
        self.assertIn('"--output"',block)
        self.assertIn('"--online"',block)
        self.assertIn("lyricsRefreshPending_=true;",block)

    def test_full_lyrics_displays_real_lines_not_metadata(self):
        window=NATIVE.split("void renderFullLyricsWindow(",1)[1].split(
            "void showFullLyricsWindow(",1)[0]
        for marker in ("lyricRawLines_","lyricCues_","QPlainTextEdit",
                       'count<=0', "setPlainText(all)", "lastLyricsProvider_"):
            self.assertIn(marker,window)
        self.assertIn("No usable lyric TEXT is loaded",window)
        self.assertIn("Full Lyrics",NATIVE)

    def test_found_status_requires_nonempty_actual_catalog(self):
        block=NATIVE.split("void updateLyrics() {",1)[1].split(
            "MediaWidget *player_",1)[0]
        self.assertIn("const bool realLyrics=!lyricRawLines_.isEmpty()",block)
        self.assertIn("LYRICS NOT FOUND · provider returned no usable text",block)

    def test_one_line_baseline_and_whisper_language_fallback(self):
        script=(ROOT/"kaffeine_next/install.sh").read_text("utf-8")
        self.assertIn("ai install-baseline",script)
        self.assertIn("--no-ai",script)
        from tv_center.radio_karaoke_router import karaoke_alignment_choice
        self.assertEqual(karaoke_alignment_choice(
            "tr",qwen_installed=True)["engine"],"whisper")
        self.assertEqual(karaoke_alignment_choice(
            "de",qwen_installed=True)["engine"],"qwen")


if __name__=="__main__":
    unittest.main()
