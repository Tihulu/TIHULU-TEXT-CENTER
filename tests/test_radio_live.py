import tempfile
from pathlib import Path
import unittest
from textcenter.core import Store
from textcenter.radio_live import LiveRadio,LiveRadioError,ffmpeg_mp3_command


class LiveRadioTests(unittest.TestCase):
    @staticmethod
    def inv():return {"platform":"Linux","rtl_usb_count":1}
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.dir=Path(self.tmp.name)
        self.srv=LiveRadio(Store(self.dir/"app.db"),
            inventory=self.inv,lookup=lambda _:None,
            conflicts=lambda:[],lock_dir=self.dir/"locks",
            record_dir=self.dir/"recordings")
    def tearDown(self):self.tmp.cleanup()

    def test_fixed_mp3_pipeline_and_no_implicit_start(self):
        command=ffmpeg_mp3_command("/usr/bin/ffmpeg")
        self.assertEqual(command[-2:],["mp3","pipe:1"])
        self.assertIn("libmp3lame",command)
        self.assertFalse(self.srv.availability()["ready"])
        self.assertFalse(self.srv.status()["active"])
        with self.assertRaises(LiveRadioError):
            self.srv.start(frequency_mhz=98.6)
        self.assertEqual(self.srv.recordings(),[])
        self.assertIsNone(self.srv.recording("../../etc/passwd"))
        with self.assertRaises(LiveRadioError):
            next(self.srv.stream_chunks("wrong"))

    def test_readsb_blocks_real_live_start(self):
        self.srv.lookup=lambda exe:"/usr/bin/"+exe
        self.srv.conflicts=lambda:[{"process":"readsb"}]
        self.assertFalse(self.srv.availability()["ready"])
        with self.assertRaises(LiveRadioError):
            self.srv.start(frequency_mhz=98.6,record=True)
        self.assertEqual(self.srv.recordings(),[])

    def test_settings_reject_unconsented_record_or_out_of_band(self):
        self.srv.lookup=lambda exe:"/usr/bin/"+exe
        with self.assertRaises(ValueError):
            self.srv.start(frequency_mhz=98.6,record="true")
        with self.assertRaises(ValueError):
            self.srv.start(frequency_mhz=109.0)


if __name__=="__main__":
    unittest.main()
