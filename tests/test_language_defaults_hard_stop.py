"""English defaults, opt-in real local detection, and owned-only HARD STOP tests.

Mock inference isn't physical speech or USB hardware acceptance.
"""
import tempfile
import time
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from textcenter.compute import LANGUAGES
from textcenter.core import Store
from textcenter.transcripts import TranscriptStore
from textcenter.speech import SpeechPipeline,SpeechError,WINDOW_BYTES,detected_speech_language,select_speech_backend
from textcenter.language_detection import detect_text_language,LanguageDetectionUnavailable,text_detection_status


def profile():
    return {
        "devices":[
            {"id":"cpu","name":"Fixture CPU","detected":True},
            {"id":"gpu","name":"Unavailable CUDA","detected":False},
            {"id":"npu","name":"Unavailable NPU","detected":False},
        ],
        "speech":{"ready_cpu":True,"ready_gpu":False,"ready_npu":False,
                  "model_path":"/test/fixture"},
    }


class LanguageAndGlobalStopTests(TestCase):
    def test_auto_detection_does_not_require_external_services(self):
        self.assertEqual(select_speech_backend(profile(),"auto","auto")["selected"],"cpu")
        with self.assertRaises(SpeechError):
            select_speech_backend(profile(),"npu","auto")
        self.assertEqual(detected_speech_language("de"),"de")
        self.assertEqual(detected_speech_language("es"),"und")
        self.assertEqual(detected_speech_language(None),"und")

    def test_auto_speech_stores_detector_language_not_auto(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=TranscriptStore(Store(Path(tmp)/"db.sqlite"))
            target="a"*32
            pipeline=SpeechPipeline(
                store=store,session=target,source_id="fm:98600000",
                source_language="auto",target_language="en",backend="auto",
                profile=profile(),transcriber=lambda *args:("Guten Tag","de"),
                translator=lambda text,source,dest:"Good day")
            pipeline.feed(b"\x00"*WINDOW_BYTES)
            deadline=time.monotonic()+4
            while not store.list(target) and time.monotonic()<deadline:
                time.sleep(0.02)
            pipeline.stop()
            rows=store.list(target)
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]["original_language"],"de")
            self.assertEqual(rows[0]["translated_language"],"en")

    def test_unknown_speech_language_cannot_synthesize_translation(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=TranscriptStore(Store(Path(tmp)/"db.sqlite"))
            sid="b"*32
            pipeline=SpeechPipeline(
                store=store,session=sid,source_id="fm:98600000",
                source_language="auto",target_language="en",backend="auto",
                profile=profile(),transcriber=lambda *args:("Test signal","und"),
                translator=lambda *args: (_ for _ in ()).throw(AssertionError("should not translate")))
            pipeline.feed(b"\x00"*WINDOW_BYTES)
            deadline=time.monotonic()+4
            while not store.list(sid) and time.monotonic()<deadline:
                time.sleep(0.02)
            pipeline.stop()
            rows=store.list(sid)
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]["original_language"],"und")
            self.assertIsNone(rows[0]["translated_text"])

    def test_optional_local_text_detector_fails_closed(self):
        with patch("textcenter.language_detection.importlib.util.find_spec",return_value=None):
            self.assertFalse(text_detection_status()["ready"])
            with self.assertRaises(LanguageDetectionUnavailable):
                detect_text_language("This is definitely long enough for a local language classifier.")

    def test_ui_has_globally_visible_stop_and_english_defaults(self):
        root=Path(__file__).resolve().parents[1]
        index=(root/"web/index.html").read_text()
        js=(root/"web/app.js").read_text()
        page=(root/"docs/index.html").read_text()
        self.assertIn('id="global-hard-stop"',index)
        self.assertIn('id="pages-hard-stop"',page)
        self.assertIn('"/api/receiver/hard-stop"',js)
        self.assertIn('laterLanguage.value="en"',js)
        self.assertIn('laterLang.value="en"',js)
        self.assertIn('language.value="en";target.value="en"',js)
        self.assertIn('Detect language (Whisper CPU/GPU)',js)
        self.assertNotIn('source.value="de";target.value="tr"',js)
        self.assertIn('en',LANGUAGES)
