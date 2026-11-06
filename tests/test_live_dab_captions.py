"""Real-audio live caption contract tests; RF/AI acceptance requires physical devices."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from textcenter.core import Store
from textcenter.transcripts import TranscriptStore
from textcenter.speech import SpeechError
from textcenter.live_dab_captions import LiveDABCaptions


class DABLiveCaptionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.transcripts=TranscriptStore(Store(Path(self.tmp.name)/"transcripts.db"))

    def tearDown(self):
        self.tmp.cleanup()

    def test_only_explicit_verified_channel_is_accepted(self):
        capt=LiveDABCaptions(self.transcripts)
        with self.assertRaises(ValueError):
            capt.start(channel="14G",service_id="0x1234")
        with self.assertRaises(ValueError):
            capt.start(channel="11D",service_id=None)
        self.assertFalse(capt.status()["active"])

    def test_missing_speech_model_does_not_open_dab_audio_or_ffmpeg(self):
        calls=[]
        def opener(service):
            calls.append(service)
            raise AssertionError("Do not open DAB audio with no ASR")
        capt=LiveDABCaptions(self.transcripts,opener=opener,
                             which=lambda _: "/usr/bin/ffmpeg",profile=lambda:{})
        with patch("textcenter.live_dab_captions.SpeechPipeline",
                   side_effect=SpeechError("No compatible installed Whisper model")):
            result=capt.start(channel="11D",service_id="0x1234",
                language="en",translate_to="tr")
        self.assertFalse(result["active"])
        self.assertEqual(result["status"],"unavailable")
        self.assertIn("No compatible installed Whisper model",result["unavailable_reason"])
        self.assertEqual(calls,[])
        self.assertIsNone(capt.decoder)

    def test_no_ffmpeg_keeps_existing_dab_playback_untouched(self):
        fake=MagicMock()
        capt=LiveDABCaptions(self.transcripts,which=lambda _:None,profile=lambda:{})
        with patch("textcenter.live_dab_captions.SpeechPipeline",return_value=fake):
            status=capt.start(channel="11D",service_id="0x1234")
        self.assertFalse(status["active"])
        self.assertIn("ffmpeg",status["unavailable_reason"])
        self.assertIsNone(capt.stream)
        fake.stop.assert_called_once()

    def test_explicit_stop_only_terminates_app_owned_decoder(self):
        response=MagicMock()
        process=MagicMock()
        process.poll.return_value=0
        process.stdin=MagicMock()
        process.stdout=MagicMock()
        fake_speech=MagicMock()
        fake_speech.status.return_value={"enabled":True,"segments_completed":0}
        capt=LiveDABCaptions(self.transcripts,which=lambda _: "/usr/bin/ffmpeg",
            opener=lambda service:response,profile=lambda:{},
            popen=lambda args,**kwargs:process)
        # Never start actual threads or read RF samples in mock contract tests.
        with patch("textcenter.live_dab_captions.SpeechPipeline",
                   return_value=fake_speech),\
             patch("textcenter.live_dab_captions._local_get",return_value=b"11D"),\
             patch("textcenter.live_dab_captions.threading.Thread") as thread:
            thread.return_value.is_alive.return_value=False
            result=capt.start(channel="11D",service_id="0x1234",
                language="de",translate_to="en",backend="cpu")
            self.assertTrue(result["active"])
            self.assertEqual(len(result["session"]),32)
            self.assertEqual(result["source"],"real_welle_cli_mp3")
            self.assertEqual(thread.call_count,3)
            ended=capt.stop(wait=True)
        self.assertFalse(ended["active"])
        fake_speech.stop.assert_called_once()
        response.close.assert_called_once()
        self.assertIsNone(capt.decoder)

    def test_local_http_api_has_real_dab_caption_routes(self):
        from textcenter.http_app import LocalServer
        import http.client
        import threading
        with tempfile.TemporaryDirectory() as folder:
            server=LocalServer(("127.0.0.1",0),Store(Path(folder)/"db.sqlite"))
            bg=threading.Thread(target=server.serve_forever,daemon=True)
            bg.start()
            try:
                conn=http.client.HTTPConnection("127.0.0.1",server.server_port,timeout=3)
                conn.request("GET","/api/dab/captions/status")
                answer=conn.getresponse()
                self.assertEqual(answer.status,200)
                self.assertFalse(json.loads(answer.read())["active"])
                conn.close()

                conn=http.client.HTTPConnection("127.0.0.1",server.server_port,timeout=3)
                conn.request("POST","/api/dab/captions/start",
                    body=b"{}",headers={"Content-Type":"application/json"})
                answer=conn.getresponse()
                self.assertEqual(answer.status,403)
                answer.read();conn.close()

                self.assertFalse(server.live_dab_captions.status()["active"])
            finally:
                server.shutdown()
                server.server_close()
                bg.join(timeout=3)

    def test_channel_selector_uses_real_asr_options(self):
        root=Path(__file__).resolve().parents[1]
        js=(root/"web/app.js").read_text()
        page=(root/"web/index.html").read_text()
        for marker in (
            "channel-live-captions","channel-live-translation",
            "channel-speech-language","channel-translate-language",
            'api("/api/dab/captions/start","POST"',
            'api("/api/dab/captions/status")',
            "pollLiveRadio","pollLiveTV",
            "updateDockCaptionExport",
            "SAMPLE_RATE"
        ):
            # SAMPLE_RATE exists in the actual ffmpeg-backed DAB audio tap.
            if marker=="SAMPLE_RATE":
                tap=(root/"textcenter/live_dab_captions.py").read_text()
                self.assertIn(marker,tap)
            else:
                self.assertIn(marker,js)
        self.assertIn('id="live-dock-caption-exports"',page)


if __name__=="__main__":
    unittest.main()
