"""Regression gates for real DVB Teletext-first subtitle priority and UI.

No test asserts a DVB tuner, official Teletext transmission, libzvbi binary,
or speech model is physically available without hardware acceptance.
"""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from textcenter.core import Store
from textcenter.transcripts import TranscriptStore
from textcenter.tv_teletext_subtitles import (
    TVTeletextTap,parse_srt_cue,teletext_probe_stream
)
from textcenter.live_tv import LiveTV


def _subtitles():
    tmp=tempfile.TemporaryDirectory()
    store=TranscriptStore(Store(Path(tmp.name)/"captions.sqlite"))
    return tmp,store


class TeletextFirstTests(unittest.TestCase):
    def test_real_srt_cue_must_have_bounded_timing_and_translatable_text(self):
        self.assertEqual(parse_srt_cue([
            "1","00:00:05,520 --> 00:00:08,280",
            "Guten Abend und willkommen!", ""
        ]),(5.52,8.28,"Guten Abend und willkommen!"))
        self.assertIsNone(parse_srt_cue([
            "1","00:00:05,520 --> 1193:02:52,815","DVB corrupt timestamp"
        ]))
        self.assertIsNone(parse_srt_cue([
            "1","00:00:01,000 --> 00:02:59,000","Too long subtitle cue"
        ]))
        self.assertIsNone(parse_srt_cue([
            "1","00:00:01,000 --> 00:00:03,000",""
        ]))
        self.assertIsNone(parse_srt_cue([
            "1","00:00:01,000 --> 00:00:03,000",""
        ]))

    def test_only_real_dvb_teletext_metadata_is_used_not_bitmap(self):
        def fake_probe(argv,**kw):
            return SimpleNamespace(returncode=0,stdout=json.dumps({"streams":[
                {"index":2,"codec_type":"subtitle","codec_name":"dvb_subtitle",
                 "tags":{"language":"deu"}},
                {"index":3,"codec_type":"subtitle","codec_name":"dvb_teletext",
                 "tags":{"language":"deu"}}
            ]}).encode())
        r=teletext_probe_stream("http://127.0.0.1:9981/stream/ard","/usr/bin/ffprobe",runner=fake_probe)
        self.assertEqual(r,{"index":3,"language":"de","codec":"dvb_teletext"})
        self.assertIsNone(teletext_probe_stream(
            "http://127.0.0.1:9981/stream/ard","/usr/bin/ffprobe",
            runner=lambda *a,**k:SimpleNamespace(returncode=0,stdout=
                b'{"streams":[{"codec_type":"subtitle","codec_name":"dvb_subtitle","index":2}]}')))
        with self.assertRaises(ValueError):
            teletext_probe_stream("http://evil.example/stream/ard","ffprobe",runner=fake_probe)

    def test_only_real_timed_cues_are_stored_with_source_provenance(self):
        tmp,store=_subtitles()
        try:
            tap=TVTeletextTap(store)
            tap.session="a"*32
            tap.source_id="configured_tv:ard"
            tap.started_at=__import__("time").monotonic()-15
            tap.language="de"
            tap.stream_index=3
            tap._store((5.0,7.0,"Original German subtitle received"))
            rows=store.list("a"*32)
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]["original_language"],"de")
            self.assertEqual(rows[0]["compute_backend"],"broadcast_teletext_libzvbi")
            self.assertEqual(rows[0]["source_id"],"configured_tv:ard:teletext:3")
            self.assertFalse(rows[0]["translated_text"])
            # A cue is "live" ONLY while the real decoder remains active.
            running=MagicMock()
            running.poll.return_value=None
            tap.process=running
            self.assertTrue(tap.status()["recent"])
            running.poll.return_value=1
            self.assertFalse(tap.status()["recent"])
        finally:tmp.cleanup()

    def test_tv_auto_prefers_current_teletext_and_skips_speech_pcm(self):
        tmp,store=_subtitles()
        try:
            tv=LiveTV(archive_dir=Path(tmp.name)/"archive",transcripts=store)
            tv.subtitle_source="auto"
            tv.caption_processing_enabled=True
            tv.subtitle_started=__import__("time").monotonic()-30
            tv.audio_read=91
            tap=MagicMock()
            tap.status.return_value={"recent":True,"status":"receiving_real_teletext"}
            tv.teletext=tap
            speech=MagicMock()
            tv.speech=speech
            with patch("textcenter.live_tv.os.read",side_effect=[b"\x00\x00"*512,b""]):
                tv._audio_worker()
            speech.skip.assert_called_once()
            speech.feed.assert_not_called()

            tap.status.return_value={"recent":False,"status":"waiting_for_real_cues"}
            with patch("textcenter.live_tv.os.read",side_effect=[b"\x00\x00"*512,b""]):
                tv._audio_worker()
            speech.feed.assert_called_once()
        finally:tmp.cleanup()

    def test_no_secondary_reader_consent_never_claims_teletext(self):
        tmp,store=_subtitles()
        try:
            channels=Path(tmp.name)/"channels.json"
            channels.write_text(json.dumps({"version":1,"channels":[{
                "id":"ard","name":"Authorized relay",
                "url":"http://127.0.0.1:9981/stream/ard"
            }]}))
            tv=LiveTV(archive_dir=Path(tmp.name)/"archive",transcripts=store,
                channels_file=channels,lookup=lambda name:"/usr/bin/"+name)
            mock=MagicMock()
            mock.poll.return_value=0
            with patch("textcenter.live_tv.subprocess.Popen",return_value=mock),\
                 patch("textcenter.live_tv.threading.Thread") as thread,\
                 patch("textcenter.live_tv.SpeechPipeline") as speech:
                speech.side_effect=RuntimeError("Missing speech model")
                status=tv.start("ard",upstream_authorized=True,subtitles=True,
                    subtitle_source="auto",auxiliary_teletext_consent=False)
                self.assertTrue(status["active"])
                self.assertIsNone(tv.teletext)
                self.assertFalse(status["teletext_subtitles"]["recent"])
                self.assertTrue(status["teletext_unavailable_reason"])
                self.assertEqual(thread.call_count,1)
                tv.stop()
        finally:tmp.cleanup()

    def test_tv_playback_survives_invalid_source_flags_and_off_toggle(self):
        tmp,store=_subtitles()
        try:
            tv=LiveTV(archive_dir=Path(tmp.name)/"archive",transcripts=store)
            with self.assertRaises(ValueError):
                tv.start("x",subtitle_source="synthetic")
            with self.assertRaises(ValueError):
                tv.start("x",auxiliary_teletext_consent="yes")
            with self.assertRaises(Exception):
                tv.configure_captions(processing=False)
        finally:tmp.cleanup()

    def test_tv_ui_has_source_visibility_and_read_only_page_reader(self):
        root=Path(__file__).resolve().parents[1]
        app=(root/"web/app.js").read_text()
        html=(root/"web/index.html").read_text()
        for marker in (
            "channel-tv-subtitle-source",
            "channel-tv-secondary-teletext-reader",
            "live-tv-caption-display",
            "live-tv-caption-processing",
            "live-tv-caption-translation",
            '"/api/live/tv/captions/config"',
            "caption_source_active",
            "tv-teletext-reader",
            'api("/api/pages")',
            "OPEN ALL TEXT & ALERTS",
            "ANTENNA ARCHIVE"
        ):
            self.assertIn(marker,app+html)
        self.assertIn("live-dock-tv-captions",html)
        self.assertIn("libzvbi",(
            root/"textcenter/tv_teletext_subtitles.py").read_text())


if __name__=="__main__":
    unittest.main()
