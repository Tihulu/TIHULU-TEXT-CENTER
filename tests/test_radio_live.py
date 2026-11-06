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

    def test_mock_continuous_stream_and_optional_mp3_archive(self):
        # Fixture uses fake PCM and fake encoded bytes, NOT RF reception.
        import time
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            tuner=root/"mock_tuner"
            transcoder=root/"mock_encoder"
            tuner.write_text(
                "#!/usr/bin/env python3\n"
                "import sys,time\n"
                "for i in range(80):\n"
                " sys.stdout.buffer.write(b'\\\x00'*8192)\n"
                " sys.stdout.buffer.flush()\n"
                " time.sleep(.012)\n")
            transcoder.write_text(
                "#!/usr/bin/env python3\n"
                "import sys\n"
                "while True:\n"
                " block=sys.stdin.buffer.read(8192)\n"
                " if not block:break\n"
                " sys.stdout.buffer.write(b'MOCKMP3'+block[:64])\n"
                " sys.stdout.buffer.flush()\n")
            tuner.chmod(0o700);transcoder.chmod(0o700)
            srv=LiveRadio(Store(root/"app.sqlite"),
                inventory=self.inv,conflicts=lambda:[],
                lookup=lambda name:str(tuner if name=="rtl_fm" else transcoder),
                lock_dir=root/"locks",record_dir=root/"recordings")
            started=srv.start(frequency_mhz=98.6,record=True)
            self.assertTrue(started["active"])
            stream=srv.stream_chunks(started["session"])
            first=next(stream)
            self.assertTrue(first.startswith(b"MOCKMP3"),first[:100])
            stream.close()
            srv.stop(wait=True)
            deadline=time.monotonic()+4
            while srv.status()["active"] and time.monotonic()<deadline:
                time.sleep(.03)
            self.assertFalse(srv.status()["active"])
            self.assertEqual(len(srv.recordings()),1)
            recording=srv.recording(srv.recordings()[0]["id"])
            self.assertIsNotNone(recording)
            self.assertIn(b"MOCKMP3",recording)

    def test_settings_reject_unconsented_record_or_out_of_band(self):
        self.srv.lookup=lambda exe:"/usr/bin/"+exe
        with self.assertRaises(ValueError):
            self.srv.start(frequency_mhz=98.6,record="true")
        with self.assertRaises(ValueError):
            self.srv.start(frequency_mhz=109.0)


if __name__=="__main__":
    unittest.main()
