import tempfile
import time
from pathlib import Path
import unittest
from textcenter.core import Store
from textcenter.transcripts import TranscriptStore
from textcenter.speech import SpeechPipeline,SpeechError,WINDOW_BYTES


class SpeechTests(unittest.TestCase):
    def test_real_audio_chunk_scheduler_uses_stub_instead_of_fake_ui(self):
        with tempfile.TemporaryDirectory() as td:
            db=TranscriptStore(Store(Path(td)/"db.sqlite"))
            profile={
                "devices":[{"id":"cpu","name":"Test CPU","detected":True}],
                "speech":{"ready_cpu":True,"model_path":"/fake/path",
                          "executable":"/fake/whisper"}
            }
            engine=SpeechPipeline(store=db,session="f"*32,source_id="fm:98600000",
                source_language="de",target_language="en",backend="cpu",profile=profile,
                transcriber=lambda pcm,lang,backend,prof:"Guten Tag",
                translator=lambda text,src,tgt:"Good day")
            engine.feed(b"\x00"*WINDOW_BYTES)
            end=time.monotonic()+3
            while time.monotonic()<end and not db.list("f"*32):
                time.sleep(0.02)
            engine.stop()
            rows=db.list("f"*32)
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]["original_text"],"Guten Tag")
            self.assertEqual(rows[0]["translated_text"],"Good day")
            self.assertEqual(engine.status()["selected_backend"],"cpu")

    def test_npu_runtime_without_local_export_is_blocked(self):
        from textcenter.speech import transcribe_pcm
        with self.assertRaises(SpeechError):
            transcribe_pcm(b"\\x00"*64000,"de","npu",{
                "speech":{"npu_engine":None,"ready_npu":False,"npu_model_path":None}
            })

    def test_missing_asr_backend_is_explicitly_blocked(self):
        with tempfile.TemporaryDirectory() as td:
            profile={
                "devices":[{"id":"cpu","name":"Test CPU","detected":True},
                           {"id":"gpu","name":"No","detected":False},
                           {"id":"npu","name":"No","detected":False}],
                "speech":{"ready_cpu":False,"ready_gpu":False,"ready_npu":False,
                          "model_path":None}}
            with self.assertRaises(SpeechError):
                SpeechPipeline(store=TranscriptStore(Store(Path(td)/"db.sqlite")),
                    session="b"*32,source_id="fm",source_language="tr",
                    target_language="de",backend="auto",profile=profile)


if __name__=="__main__":
    unittest.main()
