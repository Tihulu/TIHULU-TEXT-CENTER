import tempfile
import time
from pathlib import Path
import unittest
from unittest.mock import patch
from textcenter.core import Store
from textcenter.subtitles import CaptionStore
from textcenter.caption_live import LiveCaptionRunner,prepare_caption_options,PCM_BYTES_PER_SECOND


class CaptionWorkerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.archive=CaptionStore(Store(Path(self.tmp.name)/"app.db"))
        self.model=Path(self.tmp.name)/"model"
        self.model.mkdir()
        (self.model/"model.bin").write_bytes(b"fixture")
        self.info={
            "devices":[{"id":"cpu","kind":"cpu","name":"Test CPU"}],
            "whisper_model_local_ready":True,
            "runtimes":{"faster_whisper":True},
        }
    def tearDown(self):self.tmp.cleanup()

    def config(self,**kwargs):
        with patch.dict("os.environ",{"TIHULU_WHISPER_MODEL":str(self.model)}):
            opts=dict(enabled=True,source_lang="tr",target_lang="de",
                      device="cpu",translate_live=True,save_original=True,save_translation=True)
            opts.update(kwargs)
            return prepare_caption_options(opts,self.info)

    def test_explicit_en_de_tr_options_and_unsupported_npu(self):
        self.assertEqual(prepare_caption_options({},self.info),{"enabled":False})
        with self.assertRaises(ValueError):
            self.config(device="npu:hailo0")
        with self.assertRaises(ValueError):
            self.config(save_translation=True,save_original=False)
        for s in ("en","de","tr"):
            for t in ("en","de","tr"):
                opts=self.config(source_lang=s,target_lang=t)
                self.assertEqual(opts["source_lang"],s)

    def test_real_pcm_fanout_to_mock_asr_with_saved_bilingual_cue(self):
        config=self.config()
        runner=LiveCaptionRunner(self.archive,config,source_label="FM RF 98.600 MHz",
            asr_factory=lambda:lambda audio:[(0.1,2.3,"Merhaba")],
            translator=lambda text,source,target:"Hallo")
        runner.start()
        runner.feed_pcm(b"\x00\x00"*(PCM_BYTES_PER_SECOND//2*8))
        deadline=time.monotonic()+4
        while time.monotonic()<deadline:
            if runner.status()["cue_count"]==1:break
            time.sleep(.04)
        self.assertEqual(runner.status()["cue_count"],1,runner.status())
        self.assertEqual(runner.status()["cues"][0]["translated"],"Hallo")
        runner.stop()
        self.assertEqual(self.archive.cues(runner.session)[0]["original_text"],"Merhaba")
        self.assertEqual(self.archive.cues(runner.session)[0]["translated_text"],"Hallo")


if __name__=="__main__":
    unittest.main()
