"""Live DAB subtitle ordering: captions before slow translations, stable timing.

All execution uses mocked local PCM; no SDR, internet, GPU or model downloads.
"""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from tv_center.media_ai import CHUNK_SAMPLES
from tv_center.lyrics_sync import LyricCue
from tv_center.radio_ai import decode_radio_live, write_runtime_json


ROOT=Path(__file__).resolve().parents[1]


class RadioCaptionLiveLanguageTests(unittest.TestCase):
    def test_original_is_published_before_multi_output_translations(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            output=root/"tihulu-radio-captions-314.json"
            control=root/"tihulu-radio-controls-314.json"
            control.write_text(json.dumps({
                "source":"en","targets":["de","tr"]}))
            worker=Mock()
            worker.stdout.read.side_effect=[
                b"\x01\x00"*(CHUNK_SAMPLES*6)]
            ai=Mock()
            ai.values={"asr_enabled":True,
                       "translation_enabled":True}
            events=[]
            def capture_write(path,payload):
                events.append(dict(payload))
                write_runtime_json(path,payload)
            def recognize(pcm,*,position,lang,profile,backend,music,detection):
                self.assertEqual(lang,"en")
                return [LyricCue(position+0.5,position+2.0,
                                 "Hello from the radio.",
                                 "mock Whisper","en")]
            def translator(text,src,dst):
                self.assertEqual(src,"en")
                self.assertIn(dst,("de","tr"))
                # The first publication must ALREADY include original
                # before the first translator call.
                self.assertTrue(any(e.get("caption_revision")==0 and
                                    "Hello from the radio" in e.get("original","")
                                    for e in events))
                return f"{dst.upper()} translation",None
            with (patch.dict(os.environ,{"XDG_RUNTIME_DIR":temp}),
                  patch("tv_center.radio_ai.AISettings",return_value=ai),
                  patch("tv_center.radio_ai._choose_model",return_value=({}, "gpu")),
                  patch("tv_center.radio_ai.subprocess.Popen",return_value=worker),
                  patch("tv_center.radio_ai.signal.signal"),
                  patch("tv_center.radio_ai._near_silent_pcm",return_value=False),
                  patch("tv_center.radio_ai._chunk_cues",side_effect=recognize),
                  patch("tv_center.radio_ai.write_runtime_json",side_effect=capture_write),
                  patch("tv_center.captions.translate",side_effect=translator)):
                decode_radio_live(
                    port=8765,sid="0123",source="auto",targets=("en",),
                    output=str(output),controls=str(control),max_chunks=1)
            updates=[e for e in events if "caption_revision" in e]
            self.assertEqual([e["caption_revision"] for e in updates],[0,1])
            self.assertEqual(updates[0]["translations"],{})
            self.assertEqual(updates[0]["requested_targets"],["de","tr"])
            self.assertEqual(updates[1]["translations"],
                             {"de":"DE translation","tr":"TR translation"})
            self.assertEqual(updates[1]["control_status"],"live_preferences_applied")
            self.assertEqual(updates[1]["source_language"],"en")
            self.assertEqual(updates[0]["subtitle_audio_end_epoch_ms"],
                             updates[1]["subtitle_audio_end_epoch_ms"])
            self.assertAlmostEqual(
                updates[0]["source_capture_epoch_ms"]-
                updates[0]["subtitle_audio_end_epoch_ms"],4000,delta=150)
            self.assertEqual(json.loads(output.read_text())["caption_revision"],1)

    def test_invalid_private_controls_cannot_override_previous_targets(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            output=root/"tihulu-radio-captions-314.json"
            control=root/"tihulu-radio-controls-314.json"
            control.write_text('{"source": [], "targets":["ar"]}')
            worker=Mock()
            worker.stdout.read.side_effect=[
                b"\x01\x00"*(CHUNK_SAMPLES*6)]
            ai=Mock()
            ai.values={"asr_enabled":True,
                       "translation_enabled":False}
            with (patch.dict(os.environ,{"XDG_RUNTIME_DIR":temp}),
                  patch("tv_center.radio_ai.AISettings",return_value=ai),
                  patch("tv_center.radio_ai._choose_model",return_value=({}, "gpu")),
                  patch("tv_center.radio_ai.subprocess.Popen",return_value=worker),
                  patch("tv_center.radio_ai.signal.signal"),
                  patch("tv_center.radio_ai._near_silent_pcm",return_value=False),
                  patch("tv_center.radio_ai._chunk_cues",
                        return_value=[LyricCue(.5,2,"Guten Tag.", "test","de")])):
                decode_radio_live(
                    port=8765,sid="0123",source="de",targets=("en","tr"),
                    output=str(output),controls=str(control),max_chunks=1)
            result=json.loads(output.read_text())
            self.assertEqual(result["requested_targets"],["en","tr"])
            self.assertTrue(result["control_status"].startswith("invalid_controls_"))

    def test_radio_player_only_updates_existing_cue_for_translation_revision(self):
        src=(ROOT/"kaffeine_next/native_radio_tab.h").read_text()
        for required in (
            "quickLanguageButton_=new QPushButton(",
            "writeRadioLanguageControls()",
            "QSaveFile file(captionControlsPath_)",
            "lastRadioRevision_",
            'QLatin1String("caption_revision")',
            "if(newChunk) {",
            "cue.text=caption.left(1300)",
            "if(!queued && displayedRadioChunk_==chunk",
            'QLatin1String("subtitle_audio_end_epoch_ms")',
            "wordEpoch+activePlaybackCacheMs_+radioOffsetMs_->value()",
            "Output languages updated LIVE.",
            "model not found",
            "rightLayout->addWidget(captionProgress_)"):
            self.assertIn(required,src)
        self.assertNotIn("now+qMax(0,remaining)+radioOffsetMs_->value();",src)


if __name__=="__main__":
    unittest.main()
