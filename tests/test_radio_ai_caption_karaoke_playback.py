"""Independent live Whisper captions and lyric playback-position guards.

Offline source-contract tests. No claims of DAC/ALSA presentation timestamps
or acoustic instrumental classification.
"""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
RADIO=(ROOT/"kaffeine_next/native_radio_tab.h").read_text(encoding="utf-8")
AI=(ROOT/"tv_center/radio_ai.py").read_text(encoding="utf-8")


def section(begin,end):
    a=RADIO.index(begin)
    return RADIO[a:RADIO.index(end,a)]


class CaptionsAndKaraokePlaybackTests(unittest.TestCase):
    def test_main_whisper_subtitle_not_hidden_by_karaoke(self):
        render=section("void showRadioCanvasCaption(", "void displayDueRadioCues(")
        self.assertIn("if(lyric) return;",render)
        self.assertNotIn("currentMs<lastMatchedLyricUntilMs_",render)
        self.assertIn("radioCanvasCaption_->setText(text);",render)
        self.assertIn("showRadioCanvasCaption(cue.text);",RADIO)
        lyrics=section("void updateLyrics() {","MediaWidget *player_")
        self.assertIn("showKaraokeLine(cue);",lyrics)
        self.assertNotIn("showRadioCanvasCaption(cue.text,true)",lyrics)
        self.assertNotIn("showRadioCanvasCaption(current,true)",lyrics)

    def test_no_pcm_error_is_explicit_not_fabricated_as_silence(self):
        self.assertIn('if chunks == 0 and not was_cancelled:',AI)
        self.assertIn('"status":"audio_unavailable"',AI)
        self.assertIn('"ffmpeg_returncode":ffmpeg.returncode',AI)
        self.assertIn('"captured_windows":capture.captured_windows',AI)
        status=section("void pollCaption() {", "void stopCaptioning()")
        self.assertIn('aiStatus==QLatin1String("audio_unavailable")',status)
        self.assertIn("Whisper has NO DAB PCM audio",status)
        self.assertIn('aiStatus==QLatin1String("waiting_audio")',status)
        self.assertIn("Whisper input failed",status)
        self.assertNotIn('obj.value(QLatin1String("original")).toString("music")',status)

    def test_worker_ending_does_not_leave_false_ai_on(self):
        self.assertIn('AI captions · OFF (input ended)',RADIO)
        self.assertIn("const QSignalBlocker hold(quickAi_);",RADIO)
        self.assertIn("AI input ended · inspect DAB MP3 / FFmpeg",RADIO)

    def test_estimated_karaoke_pauses_without_actual_audio_or_vocals(self):
        preview=section("void showFoundKaraokePreview(qint64 now)", "void showKaraokeLine(")
        for token in ("player_->getPlaybackStatus()==MediaWidget::Playing",
                      "asrListening && noFreshVocalMatch",
                      "lastUnmatchedVoiceUntilMs_>now",
                      "previewPauseStartedMs_",
                      "previewClockNow", "lastVerifiedLyricIndex_",
                      "if(!holdPreview)", "if(previewLipSync && !holdPreview)",
                      "KARAOKE HOLD", "not claiming instrumental detection"):
            with self.subTest(token=token):
                self.assertIn(token,preview)
        self.assertNotIn("showRadioCanvasCaption(",preview)
        self.assertIn("previewSpeedCompensationMs_-=",preview)

    def test_verified_word_hold_preserves_last_sung_line_until_new_match(self):
        lyrics=section("void updateLyrics() {","MediaWidget *player_")
        self.assertIn("const bool keepLastMatchedWord",lyrics)
        self.assertIn("lastVerifiedLyricIndex_>=0",lyrics)
        self.assertIn("lastKaraokeUntilMs_=now+1500;",lyrics)
        poll=section("void pollCaption() {", "void stopCaptioning()")
        self.assertIn("lastVerifiedLyricIndex_=matched.value(",poll)
        self.assertIn('QLatin1String("index")',poll)
        self.assertIn("lastVerifiedLyricIndex_=-1;",RADIO)


if __name__=="__main__":
    unittest.main()
