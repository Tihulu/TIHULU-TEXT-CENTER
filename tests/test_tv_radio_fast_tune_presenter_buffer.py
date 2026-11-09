"""DAB fast tune, optional caching and presenter/lyrics regression tests.

No receiver, network, CUDA or actual audio hardware is accessed.
"""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from tv_center.media_ai import CHUNK_SAMPLES
from tv_center.lyrics_sync import LyricCue
from tv_center.radio_ai import decode_radio_live

ROOT=Path(__file__).resolve().parents[1]


class RadioLowLatencyAndSpeechTests(unittest.TestCase):
    def test_opt_in_defaults_and_fast_live_tuning_are_not_scan_dwell(self):
        ui=(ROOT/"kaffeine_next/native_radio_tab.h").read_text()
        vlc=(ROOT/"kaffeine_next/patch_upstream.py").read_text()
        self.assertIn('quickAi_->setChecked(false)',ui)
        self.assertIn('quickBuffer_->setChecked(false)',ui)
        self.assertIn('radioBufferEnabled"),false).toBool()',ui)
        self.assertIn('radioAutoBufferEnabled"),false).toBool()',ui)
        self.assertIn('radioSettings.value(QLatin1String("playbackBufferMs"),0).toInt()',vlc)
        self.assertIn('scanningRequest?3200:650',ui)
        self.assertIn('ticket==stationRequestId_',ui)
        self.assertIn('ticket==scanRequestId_',ui)
        self.assertIn('radioSettings.setValue(QLatin1String("playbackBufferMs"),desired)',ui)
        self.assertIn('int requestedPlaybackBufferMs() const',ui)
        self.assertIn('const int desired=requestedPlaybackBufferMs()',ui)
        self.assertIn('if(desired==activePlaybackCacheMs_)',ui)
        self.assertIn('bufferUnit_->addItem(tr("Seconds"),1000)',ui)
        self.assertIn('captionProgress_->setRange(0,0)',ui)
        self.assertIn('captionProgress_->setVisible(true)',ui)
        self.assertIn('radioQuickRow_->insertWidget(3,autoLyrics_)',ui)
        self.assertIn('lastUnmatchedVoiceUntilMs_',ui)

    def test_unmatched_lyrics_do_not_erase_actual_presenter_words(self):
        with tempfile.TemporaryDirectory() as temp:
            output=Path(temp)/"tihulu-radio-captions-314.json"
            lyric=Path(temp)/"tihulu-radio-lyrics-314.json"
            lyric.write_text(json.dumps({
                "plain_lines":["Old song lyrics in English"],
                "alignment_mode":"asr_lexical",
                "translation_targets":[],
                "source_language":"en"
            }))
            worker=Mock()
            worker.stdout.read.side_effect=[b"\x01\x00"*(CHUNK_SAMPLES*6)]
            ai=Mock()
            ai.values={"asr_enabled":True,"translation_enabled":False}
            seen_modes=[]
            def recognize(pcm,*,position,lang,profile,backend,music,detection):
                seen_modes.append(music)
                return [LyricCue(position+0.5,position+2.0,
                     "Guten Abend. Hier sind die Nachrichten.",
                     "Whisper/CUDA","de")]
            with (patch.dict(os.environ,{"XDG_RUNTIME_DIR":temp}),
                  patch("tv_center.radio_ai.AISettings",return_value=ai),
                  patch("tv_center.radio_ai._choose_model",return_value=({}, "gpu")),
                  patch("tv_center.radio_ai.subprocess.Popen",return_value=worker),
                  patch("tv_center.radio_ai.signal.signal"),
                  patch("tv_center.radio_ai._near_silent_pcm",return_value=False),
                  patch("tv_center.radio_ai._chunk_cues",side_effect=recognize)):
                state=decode_radio_live(
                    port=8765,sid="0123",source="de",targets=(),
                    output=str(output),music=False,
                    prefer_verified_lyrics=True,max_chunks=1)
            result=json.loads(output.read_text())
            self.assertEqual(state["chunks"],1)
            self.assertIn("Guten Abend",result["original"])
            self.assertTrue(result["speech_preserved_when_lyrics_unmatched"])
            self.assertFalse(result["lyric_match_verified"])
            self.assertFalse(result["music_detected"])
            self.assertNotIn("[music]",result["original"])
            # Loaded lyrics must NOT implicitly disable Whisper VAD.
            self.assertEqual(seen_modes,[False])

    def test_auto_lyrics_require_actual_vocal_evidence(self):
        source=(ROOT/"kaffeine_next/native_radio_tab.h").read_text()
        self.assertIn("lastLyricsAutoLookup_=automatic",source)
        self.assertIn("lastVerifiedLyricMs_<=0",source)
        self.assertIn("lastUnmatchedVoiceUntilMs_>currentEpoch",source)
        self.assertIn("lastVerifiedLyricMs_=now",source)
        self.assertIn("if(!alreadyRunning) {",source)
        self.assertIn("const bool restartAi=quickAi_->isChecked()",source)

if __name__=="__main__":
    unittest.main()
