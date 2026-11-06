import json
import tempfile
from pathlib import Path
import unittest
from textcenter.live_tv import (
    LiveTV,LiveTVError,load_channels,validate_local_tv_url,tv_ffmpeg_argv
)


class TVTests(unittest.TestCase):
    def test_network_sources_restrict_upstream(self):
        good="http://127.0.0.1:9981/stream/channelid"
        self.assertEqual(validate_local_tv_url(good),good)
        for bad in ("http://example.org/stream/x",
            "http://127.0.0.1:80/stream/x",
            "http://127.0.0.1:9981/admin",
            "http://user:secret@127.0.0.1:9981/stream/x",
            "http://127.0.0.1:9981/stream/x?retune=1",
            "file:///tmp/video.ts","http://localhost:9981/stream/x"):
            with self.subTest(url=bad),self.assertRaises(ValueError):
                validate_local_tv_url(bad)

    def test_channel_catalog_read_only_and_no_tuning_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/"channels.json"
            file.write_text(json.dumps({"version":1,"channels":[
                {"id":"a","name":"Operator supplied channel",
                 "url":"http://127.0.0.1:9981/stream/channelid"},
                {"id":"x","name":"Unsafe","url":"http://10.0.0.1:9981/stream/id"}]}))
            channels=load_channels(file)
            self.assertEqual(len(channels),1)
            self.assertEqual(channels[0]["id"],"a")
            tv=LiveTV(archive_dir=Path(tmp)/"records",channels_file=file,
                      lookup=lambda _:None)
            self.assertFalse(tv.availability()["ready"])
            with self.assertRaises(LiveTVError):
                tv.start("a",upstream_authorized=False)
            with self.assertRaises(LiveTVError):
                tv.start("a",upstream_authorized=True)
            self.assertFalse(tv.status()["active"])

    def test_missing_speech_model_preserves_real_tv_playback(self):
        from unittest.mock import MagicMock,patch
        from textcenter.speech import SpeechError
        with tempfile.TemporaryDirectory() as tmp:
            channels=Path(tmp)/"channels.json"
            channels.write_text(json.dumps({"version":1,"channels":[{
                "id":"safe-tv","name":"Authorized local relay",
                "url":"http://127.0.0.1:9981/stream/channelid"
            }]}))
            from textcenter.core import Store
            from textcenter.transcripts import TranscriptStore
            captions=TranscriptStore(Store(Path(tmp)/"captions.db"))
            tv=LiveTV(archive_dir=Path(tmp)/"recordings",transcripts=captions,
                channels_file=channels,lookup=lambda _:"/usr/bin/ffmpeg")
            fake=MagicMock()
            fake.poll.return_value=0
            with patch("textcenter.live_tv.SpeechPipeline",
                       side_effect=SpeechError("Compatible Whisper model missing")),\
                 patch("textcenter.live_tv.subprocess.Popen",return_value=fake),\
                 patch("textcenter.live_tv.threading.Thread") as thread:
                started=tv.start("safe-tv",subtitles=True,
                    language="en",translate_to="tr",upstream_authorized=True)
                self.assertTrue(started["active"])
                self.assertTrue(started["subtitles_requested"])
                self.assertFalse(started["subtitles_active"])
                self.assertIn("Compatible Whisper model missing",
                              started["subtitle_unavailable_reason"])
                self.assertFalse(started["speech"]["enabled"])
                self.assertEqual(thread.call_count,1,
                                 "Speech PCM worker must not run with missing model")
                stopped=tv.stop()
                self.assertFalse(stopped["active"])
                self.assertIsNone(tv.audio_read)

    def test_transcoding_produces_h264_aac_fragmented_mp4(self):
        argv=tv_ffmpeg_argv("/usr/bin/ffmpeg","http://127.0.0.1:9981/stream/a")
        self.assertIn("libx264",argv)
        self.assertIn("aac",argv)
        self.assertIn("frag_keyframe+empty_moov+default_base_moof",argv)
        self.assertEqual(argv[-2:],["mp4","pipe:1"])
        with_sub=tv_ffmpeg_argv("/usr/bin/ffmpeg",
                    "http://127.0.0.1:9981/stream/a",17)
        self.assertEqual(with_sub[-1],"pipe:17")


if __name__=="__main__":
    unittest.main()
