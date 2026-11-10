"""Native fullscreen status-bar and complete local-media transcription regressions.

No DVB/SDR hardware and no paid services. Real libVLC/Wayland fullscreen
rendering and uninterrupted local audio still require interactive testing.
"""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tv_center.lyrics_sync import LyricCue,write_srt
from tv_center.media_ai import create_subtitles

ROOT=Path(__file__).resolve().parents[1]
PATCH=(ROOT/"kaffeine_next/patch_upstream.py").read_text("utf-8")
PANEL=(ROOT/"kaffeine_next/native_media_panel.h").read_text("utf-8")
TV=(ROOT/"kaffeine_next/captions_overlay.py").read_text("utf-8")
RADIO=(ROOT/"kaffeine_next/native_radio_tab.h").read_text("utf-8")
AI=(ROOT/"tv_center/media_ai.py").read_text("utf-8")


class LocalFullFileAndFullscreenTests(unittest.TestCase):
    def test_fullscreen_hides_cyan_receiver_bar_restores_on_exit(self):
        self.assertIn('tihuluReceiverSwitchProgress',PATCH)
        self.assertIn('displayMode == MediaWidget::FullScreenMode',PATCH)
        self.assertIn('displayMode == MediaWidget::FullScreenReturnToMinimalMode',PATCH)
        self.assertIn('statusBar()->setVisible(!tihuluFullVideo)',PATCH)
        self.assertIn('aiPanel->setVisible(mode==MediaWidget::NormalMode)',PATCH)
        self.assertIn('if (handoff) handoff->hide();',PATCH)

    def test_local_prepass_is_user_opt_in_and_does_not_block_live_sources(self):
        self.assertIn('transcribeBeforeOpen"),false',PANEL)
        self.assertIn('if(!url.isLocalFile() || !preprocessOnOpen_->isChecked())',PANEL)
        self.assertIn('return generate(true);',PANEL)
        self.assertIn('playerTab->prepareLocalFileOpen(copy)',PATCH)
        self.assertIn('if (copy.isLocalFile()',PATCH)
        self.assertIn('return;',PATCH.split('playerTab->prepareLocalFileOpen(copy)',1)[1])
        self.assertIn('pausedForAi_=beforeOpen || wait_->isChecked()',PANEL)
        self.assertIn('if(pausedForAi_) player_->stop();',PANEL)
        self.assertIn('player_->play(QUrl::fromLocalFile(path_));',PANEL)
        self.assertIn('player_->setSubtitle(QUrl::fromLocalFile(srtPath_));',PANEL)

    def test_video_settings_follow_applied_tv_not_dvb_playback_cache(self):
        self.assertIn('KaffeineTVFileCaptionDefaults',TV)
        for key in ('spokenSource','outputLanguages','showOriginal',
                    'showTranslation','musicTranscription'):
            self.assertIn('file_video_defaults.setValue("'+key+'"',TV)
        self.assertIn('KaffeineTVFileCaptionDefaults',PANEL)
        self.assertIn('KaffeineRadio',PANEL)
        self.assertIn('radioSpeechLanguage',PANEL)
        self.assertIn('radioOutputs',PANEL)
        self.assertIn('radioMusicTranscription',PANEL)
        self.assertIn('radioMusicTranscription',RADIO)
        self.assertIn('loadSharedCaptionProfile();',PANEL)
        self.assertIn('zho_Hant',PANEL)
        self.assertIn('QStringList extra;',PANEL)
        self.assertNotIn('radioOffsetMs_->value()',PANEL)
        self.assertNotIn('playback_delay_ms',PANEL)

    def test_live_radio_and_tv_continue_unaffected_by_file_mode(self):
        prepass=PANEL.split('bool generate(bool beforeOpen) {')[1].split(
            'MediaWidget *player_',1)[0]
        self.assertIn('QLatin1String("media-captions")',prepass)
        for forbidden in ('stopReceiver(', 'stopCaptioning(', 'rtl_sdr',
                          'dvbv5-zap','radio-captions','captions-overlay'):
            self.assertNotIn(forbidden,prepass)
        self.assertIn('cancelledForFileChange_=true;',PANEL)
        self.assertIn('if(cancelledForFileChange_)',PANEL)
        self.assertIn('QStandardPaths::AppLocalDataLocation',PANEL)
        self.assertIn('QLatin1String("--output"),srtPath_',PANEL)
        self.assertNotIn('QLatin1String("--overwrite")',PANEL)

    def test_translated_only_srt_keeps_original_if_translation_unavailable(self):
        cues=[LyricCue(0.0,1.5,"Hello world"),
              LyricCue(1.5,3.0,"How are you")]
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"translated.srt"
            write_srt(cues,path,include_original=False,
                      translations={1:"[TR] Merhaba dünya"})
            text=path.read_text()
            self.assertIn("[TR] Merhaba dünya",text)
            self.assertNotIn("Hello world",text)
            self.assertIn("How are you",text)

    def test_media_ai_full_transcription_mode_and_safe_file_output(self):
        self.assertIn('max_seconds:int=21600',AI)
        self.assertIn('File exceeds the six-hour offline transcription limit',AI)
        self.assertIn('options.translations_only',AI)
        self.assertIn('At most six translation languages supported',AI)
        with tempfile.TemporaryDirectory() as temp:
            media=Path(temp)/"sample.wav"
            media.write_bytes(b"RIFFdummy")
            result=Path(temp)/"prepared.srt"
            cues=[LyricCue(0,2,"Hello","Whisper","en")]
            with patch("tv_center.media_ai.transcribe_local_media",
                       return_value=(cues,("tr",),"cpu")), (
                 patch("tv_center.media_ai._translate_cues",
                       return_value=({1:"[TR] Merhaba"},[]))):
                state=create_subtitles(str(media),source="en",targets=("tr",),
                     output=str(result),translations_only=True)
            self.assertEqual(state["status"],"completed")
            self.assertEqual(state["cues"],1)
            self.assertIn("[TR] Merhaba",result.read_text())
            self.assertNotIn("Hello",result.read_text())


if __name__=="__main__":
    unittest.main()
