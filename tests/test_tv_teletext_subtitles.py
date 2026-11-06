"""Real Teletext-first subtitles and safe TV archive reader contracts.

No physical broadcast is simulated or reported as accepted by these tests.
"""
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import MagicMock,patch
from textcenter.core import Store
from textcenter.transcripts import TranscriptStore
from textcenter.tv_teletext_subtitles import (
    parse_subrip_cue,teletext_ffmpeg_argv,TeletextSubtitleSidecar)
from textcenter.live_tv import LiveTV,load_channels


class TeletextSubtitleTests(unittest.TestCase):
    def test_ebu_subtitle_srt_cue_must_have_real_bounded_timing(self):
        actual=parse_subrip_cue(
            "12\n00:00:02,280 --> 00:00:05,335\nGuten Abend\n")
        self.assertEqual(actual["text"],"Guten Abend")
        self.assertAlmostEqual(actual["start"],2.28)
        self.assertAlmostEqual(actual["end"],5.335)
        self.assertIsNone(parse_subrip_cue(
            "1\n00:00:02,280 --> 1193:02:49,575\nBad end time\n"))
        self.assertIsNone(parse_subrip_cue(
            "1\n00:00:02,280 --> 00:00:44,280\nOverlong stale caption\n"))
        self.assertIsNone(parse_subrip_cue("No actual subtitle timestamps"))

    def test_teletext_decoder_only_from_fixed_local_mpeg_ts_relay(self):
        args=teletext_ffmpeg_argv("/usr/bin/ffmpeg",
            "http://127.0.0.1:9981/stream/wdr",
            subtitle_index=2,page="subtitle")
        for item in ("-txt_format","text","-txt_page","subtitle",
                     "-fix_sub_duration","0:s:2","-f","srt"):
            self.assertIn(item,args)
        for invalid in ("http://localhost:9981/stream/a",
                        "http://127.0.0.1:9981/admin",
                        "http://evil.invalid/stream/a",
                        "file:///tmp/record.ts"):
            with self.assertRaises(ValueError):
                teletext_ffmpeg_argv("/usr/bin/ffmpeg",invalid)

    def test_sidecar_refuses_unapproved_parallel_stream(self):
        called=[]
        side=TeletextSubtitleSidecar(on_cue=called.append,
            lookup=lambda x:"/usr/bin/ffmpeg",
            popen=lambda *a,**kw:called.append(a))
        with self.assertRaises(ValueError):
            side.start("http://127.0.0.1:9981/stream/a")
        self.assertEqual(called,[])
        self.assertFalse(side.status()["active"])

    def test_channel_config_marks_only_exact_optin_as_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"channels.json"
            path.write_text(json.dumps({"version":1,"channels":[{
                "id":"a","name":"TV A","url":"http://127.0.0.1:9981/stream/a",
                "teletext_shared_safe":1,"teletext_subtitle_index":2
            },{
                "id":"b","name":"TV B","url":"http://127.0.0.1:9981/stream/b",
                "teletext_shared_safe":True,"teletext_subtitle_page":150,
                "teletext_language":"de"
            }]}))
            channels=load_channels(path)
            self.assertFalse(channels[0]["teletext_shared_safe"])
            self.assertEqual(channels[0]["teletext_subtitle_index"],2)
            self.assertTrue(channels[1]["teletext_shared_safe"])
            self.assertEqual(channels[1]["teletext_subtitle_page"],150)
            self.assertEqual(channels[1]["teletext_language"],"de")

    def test_real_teletext_priority_then_stale_fallback_to_speech(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=TranscriptStore(Store(Path(tmp)/"app.sqlite"))
            tv=LiveTV(archive_dir=Path(tmp)/"recordings",transcripts=store)
            tv.state["active"]=True
            tv.state["session"]="a"*32
            tv.caption_enabled=True
            tv.caption_source="auto"
            tv.subtitle_channel={"id":"wdr","teletext_language":"de",
                                  "teletext_shared_safe":False}
            tv.subtitle_target="en"
            tv.subtitle_language="en"
            tv.speech=MagicMock()
            tv.speech.status.return_value={"enabled":True}
            with patch("textcenter.live_tv.translate_offline",
                       return_value="Good evening"):
                tv._on_received_teletext({"text":"Guten Abend",
                    "start":2.2,"end":5.2})
            entries=store.list(session="a"*32)
            self.assertEqual(len(entries),1)
            self.assertEqual(entries[0]["compute_backend"],"broadcast_teletext")
            self.assertEqual(entries[0]["source_id"],"configured_tv:wdr:teletext")
            self.assertEqual(entries[0]["translated_text"],"Good evening")
            self.assertEqual(tv._effective_subtitle_source(),"teletext")
            tv.teletext_last_seen=time.monotonic()-20
            self.assertEqual(tv._effective_subtitle_source(),"speech")
            tv.caption_source="teletext"
            self.assertEqual(tv._effective_subtitle_source(),"teletext_waiting")
            tv.state["active"]=False

    def test_waits_for_really_decoded_teletext_before_asr_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            tv=LiveTV(archive_dir=Path(tmp)/"records")
            tv.caption_enabled=True
            tv.caption_source="auto"
            tv.speech=MagicMock()
            tv.teletext_sidecar=MagicMock()
            tv.teletext_sidecar.status.return_value={"active":True}
            tv.teletext_probe_until=time.monotonic()+12
            self.assertEqual(tv._effective_subtitle_source(),"teletext_waiting")
            tv.teletext_probe_until=time.monotonic()-1
            self.assertEqual(tv._effective_subtitle_source(),"speech")
            tv.teletext_sidecar.status.return_value={"active":False}
            self.assertEqual(tv._effective_subtitle_source(),"speech")

    def test_invalid_or_disabled_cues_are_never_imported(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=TranscriptStore(Store(Path(tmp)/"db"))
            tv=LiveTV(archive_dir=Path(tmp)/"records",transcripts=store)
            tv.state["active"]=True
            tv.state["session"]="b"*32
            tv.caption_enabled=False
            tv.subtitle_channel={"id":"a","teletext_language":"de"}
            tv._on_received_teletext({"text":"No opt in","start":1,"end":2})
            self.assertEqual(store.list(session="b"*32),[])
            tv.state["active"]=False

    def test_runtime_tv_caption_switches_preserve_tv_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=TranscriptStore(Store(Path(tmp)/"db.sqlite"))
            tv=LiveTV(archive_dir=Path(tmp)/"recordings",transcripts=store)
            tv.state["active"]=True
            tv.state["session"]="c"*32
            tv.subtitle_channel={"id":"safe","teletext_shared_safe":False}
            tv.caption_source="auto"
            status=tv.configure_captions(enabled=True,source="auto",
                translate_to="de",original_visible=False,
                translated_visible=True)
            self.assertTrue(status["active"])
            self.assertTrue(status["captions_enabled"])
            self.assertFalse(status["caption_original_visible"])
            self.assertTrue(status["caption_translated_visible"])
            self.assertEqual(status["subtitle_effective_source"],"unavailable")
            self.assertIn("multi-client-safe",status["teletext_error"])
            off=tv.configure_captions(enabled=False)
            self.assertEqual(off["subtitle_effective_source"],"off")
            with self.assertRaises(ValueError):
                tv.configure_captions(source="externally_invented")
            tv.state["active"]=False

    def test_fm_caption_toggle_does_not_retune_running_receiver(self):
        from textcenter.live_fm import LiveFM
        with tempfile.TemporaryDirectory() as tmp:
            fm=LiveFM(archive_dir=Path(tmp)/"recordings")
            fm.state.update(active=True,session="d"*32,
                frequency_hz=98_600_000,caption_language="en",
                caption_target=None,caption_compute="auto",
                caption_translation_backend="auto",
                subtitles_requested=False)
            with patch.object(fm,"_configure_optional_speech") as setup:
                fm.configure_captions(enabled=True,translate_to="tr")
                self.assertEqual(setup.call_count,1)
                self.assertEqual(setup.call_args.kwargs["translate_to"],"tr")
            speech=MagicMock()
            fm.speech=speech
            fm.configure_captions(enabled=False)
            speech.stop.assert_called_once()
            self.assertTrue(fm.state["active"],"Receiver must remain live")
            fm.state["active"]=False

    def test_tv_and_text_alerts_share_real_archived_page_ui(self):
        root=Path(__file__).resolve().parents[1]
        app=(root/"web/app.js").read_text()
        for marker in ("function addTvTeletextPagesPanel",
                       'api("/api/pages")',
                       'api("/api/page?"+q.toString())',
                       "async function showTextAndAlerts",
                       'id="live-caption-source"',
                       "live-caption-source"):
            if marker=='id="live-caption-source"':
                self.assertIn(marker,(root/"web/index.html").read_text())
            else:self.assertIn(marker,app)


if __name__=="__main__":
    unittest.main()
