"""Truthful channel center and scan contracts. These are mocked data, NOT RF acceptance."""
import json
from pathlib import Path
import tempfile
import unittest

from textcenter.core import Store
from textcenter.channel_center import ChannelCenter,parse_dvbv5_services
from textcenter.auto_scan import fm_tuning_candidates
from textcenter.dvb_full_scan import DVBFullScanner
from textcenter.dab_bridge import dab_audio_url,DABError

DVB_OUTPUT="""[WDR Fernsehen HD]
SERVICE_ID = 512
VIDEO_PID = 101
AUDIO_PID = 102
DELIVERY_SYSTEM = DVBT2
FREQUENCY = 514000000

[Radio via DVB]
SERVICE_ID = 513
AUDIO_PID = 201
DELIVERY_SYSTEM = DVBT
FREQUENCY = 514000000

[Unverified]
SERVICE_ID = banana
VIDEO_PID = 101
DELIVERY_SYSTEM = DVBT2
FREQUENCY = 514000000
"""


class UnifiedChannelTests(unittest.TestCase):
    def test_real_dvb_scan_parser_rejects_invalid_and_retains_provenance(self):
        actual=parse_dvbv5_services(DVB_OUTPUT,scan_plan="de-NRW",adapter=0)
        self.assertEqual(len(actual),2)
        self.assertEqual(actual[0]["name"],"WDR Fernsehen HD")
        self.assertEqual(actual[0]["delivery_system"],"DVBT2")
        self.assertEqual(actual[0]["frequency_hz"],514_000_000)
        with self.assertRaises(ValueError):
            parse_dvbv5_services(DVB_OUTPUT,scan_plan="../other")
        self.assertEqual(parse_dvbv5_services("[fake]\nFREQUENCY=514000000",
            scan_plan="de-NRW"),[])

    def test_edit_rename_favorite_hide_order_preserves_originals(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"channels.db"
            center=ChannelCenter(Store(path))
            center.verified.save_fm(frequency_hz=98_600_000,name="WDR 2")
            center.verified.save_dab(channel="11D",frequency_hz=222_064_000,
                service_id="0x1234",name="WDR 5",ensemble="WDR NRW",
                audio_advertised=True)
            center.ingest_tv_scan(DVB_OUTPUT,scan_plan="de-NRW",adapter=0)
            before=center.list()
            self.assertEqual(len(before),4)
            dab=next(x for x in before if x["medium"]=="dab")
            self.assertTrue(dab["playable"])
            tv=next(x for x in before if x["medium"]=="tv")
            self.assertFalse(tv["playable"])
            self.assertEqual(tv["source"],"verified_dvb_scan")
            self.assertIn("relay",tv["playback_note"])
            custom=center.update(id=dab["id"],display_name="My favorite",
                                 favorite=True,position=1)
            self.assertEqual(custom["name"],"WDR 5")
            self.assertEqual(custom["display_name"],"My favorite")
            self.assertTrue(custom["favorite"])
            reopened=ChannelCenter(Store(path))
            preserved=next(x for x in reopened.list() if x["id"]==dab["id"])
            self.assertEqual(preserved["display_name"],"My favorite")
            self.assertEqual(preserved["name"],"WDR 5")
            reopened.update(id=tv["id"],hidden=True)
            self.assertEqual(len(reopened.list()),3)
            self.assertEqual(len(reopened.list(include_hidden=True)),4)
            with self.assertRaises(KeyError):
                reopened.update(id="fm:98700000",favorite=True)
            with self.assertRaises(ValueError):
                reopened.update(id=dab["id"],position=-1)

    def test_preconfigured_tv_stream_is_separately_labeled(self):
        with tempfile.TemporaryDirectory() as td:
            center=ChannelCenter(Store(Path(td)/"db.sqlite"))
            rows=center.list(medium="tv",tv_channels=[{
                "id":"ardhd","name":"ARD HD","url":"http://127.0.0.1:5000/stream/ard"
            }])
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]["source"],"operator_configured_stream")
            self.assertTrue(rows[0]["playable"])
            self.assertIsNone(rows[0]["frequency_hz"])

    def test_full_fm_trials_are_not_invented_radio_stations(self):
        peaks=[{"frequency_hz":87_500_000+i*200_000} for i in range(100)]
        candidates=fm_tuning_candidates(peaks,maximum=128)
        self.assertLessEqual(len(candidates),128)
        self.assertTrue(all(isinstance(x,float) for x in candidates))
        self.assertEqual(fm_tuning_candidates([],maximum=128),[])

    def test_real_dvb_capability_is_false_without_tool_or_frontend(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            center=ChannelCenter(Store(root/"db"))
            scanner=DVBFullScanner(center,plans={"de-NRW":str(root/"de-NRW")},
                frontend_root=root/"nonexistent",lookup=lambda _:None)
            status=scanner.available()
            self.assertFalse(status["ready"])
            with self.assertRaises(Exception):
                scanner.start(plan="de-NRW",adapter=0,frontend=0,consent=False)

    def test_dab_audio_source_is_real_and_exactly_localhost(self):
        def fetch(path,limit):
            if path=="/channel":return b"11D"
            return json.dumps({
                "receiver":{"software":{"name":"welle-cli"}},
                "ensemble":{"label":"WDR NRW"},
                "services":[{"sid":"0x1234","label":"WDR 5",
                             "url_mp3":"/mp3/0x1234"}]
            }).encode()
        self.assertEqual(dab_audio_url("0x1234",fetcher=fetch),
                         "http://127.0.0.1:7979/mp3/0x1234")
        with self.assertRaises(DABError):
            dab_audio_url("0x1234/../sensitive",fetcher=fetch)
        with self.assertRaises(DABError):
            dab_audio_url("0x9999",fetcher=fetch)


if __name__=="__main__":unittest.main()
