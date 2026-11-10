"""Regression contracts for silent DAB output with independent Whisper captions.

A libVLC PLAYING state does not establish audible DAC output. Keep recovery
manual and do not retune the SDR or terminate separately running ASR.
"""
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RADIO=(ROOT/"kaffeine_next/native_radio_tab.h").read_text(encoding="utf-8")
PATCH=(ROOT/"kaffeine_next/patch_upstream.py").read_text(encoding="utf-8")


class SilentDabRecoveryTests(unittest.TestCase):
    def test_software_profile_does_not_inherit_no_audio(self):
        self.assertIn('tihuluProfile == "software"',PATCH)
        self.assertIn('option == QLatin1String("--no-audio")',PATCH)
        self.assertIn("existing.removeAt(n);",PATCH)
        self.assertIn('tihuluProfile == "software-no-audio"',PATCH)

    def test_radio_audio_controls_act_on_real_media_player(self):
        for item in ("radioOutputVolume_", "radioMuteButton_",
                     "radioReconnectAudio_", "radioAudioDiagnostics_",
                     "&MediaWidget::setVolume", "&MediaWidget::toggleMuted"):
            with self.subTest(item=item):
                self.assertIn(item,RADIO)

    def test_audio_reconnect_is_manual_and_does_not_touch_receiver_or_asr(self):
        method=RADIO.split("void retryDabAudioPlayback() {",1)[1].split(
            "void showRadioAudioDiagnostics()",1)[0]
        for item in ("playingKey_.isEmpty()", "scanning_",
                     '"/mp3/"', "player_->stop();", "player_->play(audio);",
                     "dabPlaybackObserved_=false;"):
            with self.subTest(item=item):
                if item == '"/mp3/"':
                    self.assertIn('QLatin1String("/mp3/")',method)
                else:
                    self.assertIn(item,method)
        for forbidden in ("stopReceiver(", "startReceiver(", "stopCaptioning(",
                          "startCaptioning(", "backend_.kill(", "lyricsProcess_.kill("):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden,method)

    def test_readonly_audio_routing_probe(self):
        diagnostic=RADIO.split("void showRadioAudioDiagnostics() {",1)[1].split(
            "void showReceiverDetails()",1)[0]
        self.assertIn('QLatin1String("wpctl")',diagnostic)
        self.assertIn('QLatin1String("pactl")',diagnostic)
        self.assertIn('QLatin1String("status")',diagnostic)
        self.assertIn('QLatin1String("info")',diagnostic)
        for forbidden in ("set-default", "set-volume", "set-mute", "QProcess::execute"):
            self.assertNotIn(forbidden,diagnostic)

    def test_playing_never_claims_actual_sound(self):
        self.assertIn("audible sound NOT confirmed",RADIO)
        self.assertIn("ASR subtitles use a separate audio input",RADIO)
        self.assertIn("Voice",RADIO)


if __name__=="__main__":
    unittest.main()
