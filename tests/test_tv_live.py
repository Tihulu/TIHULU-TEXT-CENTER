import tempfile
from pathlib import Path
import unittest
from textcenter.core import Store
from textcenter.tv_live import LiveTV,tv_channels,zap_command,tv_ffmpeg_command


class TVTests(unittest.TestCase):
    def test_verified_channel_file_and_command_without_shell(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"channels.conf"
            path.write_text(
                "[TEST TV]\nFREQUENCY = 514000000\nDELIVERY_SYSTEM = DVBT2\n"
                "VIDEO_PID = 201\nAUDIO_PID = 202\n")
            parsed=tv_channels(path)
            self.assertTrue(parsed["ready"])
            self.assertEqual(parsed["channels"][0]["name"],"TEST TV")
            cmd=zap_command("/usr/bin/dvbv5-zap",str(path),"TEST TV")
            self.assertEqual(cmd[-3:],["-r","-p","TEST TV"])
            encoder=tv_ffmpeg_command("/usr/bin/ffmpeg",audio_fd=9)
            self.assertIn("pipe:9",encoder)
            self.assertIn("frag_keyframe+empty_moov+default_base_moof",encoder)

    def test_no_tuner_no_automatic_stream_or_recording(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            tv=LiveTV(Store(root/"app.db"),
                diagnose=lambda:{"model_confirmed":False,"dvb_frontends":[]},
                channels=lambda:{"ready":False,"channels":[],"reason":"No channel file"},
                lookup=lambda _:None,conflicts=lambda:[],
                lock_dir=root/"locks",record_dir=root/"tv")
            self.assertFalse(tv.availability()["ready"])
            self.assertFalse(tv.status()["active"])
            self.assertFalse(tv.channel_status()["capability"]["ready"])
            with self.assertRaises(Exception):
                tv.start(service="FAKE TV")
            self.assertEqual(tv.recordings(),[])
            self.assertFalse((root/"tv").exists())


if __name__=="__main__":
    unittest.main()
