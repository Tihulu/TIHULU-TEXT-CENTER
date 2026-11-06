"""Mock-only unit tests for explicit automatic RF discovery.
No SDR, Internet receiver, audio player or physical antenna is accessed.
"""
import json
from pathlib import Path
import tempfile
import time
import unittest

from textcenter.auto_scan import (
    AutoScanError, FMAutoScanner, DABAutoScanner, fm_tuning_candidates,
    dab_channels_from_peaks
)
from textcenter.dab_bridge import DAB_HZ


class FakeSurvey:
    def __init__(self):
        self.running=False
        self.calls=0

    def availability(self,band):
        return {"ready":True}

    def start(self,band):
        self.running=True
        self.calls+=1
        return {"active":True}

    def status(self,heartbeat=True):
        return {
            "active":False,"status":"completed","band":"fm",
            "candidates":[{"frequency_hz":98_671_000,"above_median_db":14.0}],
            "fm_auto_candidates":[{"frequency_hz":98_671_000,"above_median_db":14.0}]
        }

    def stop(self,*,wait=False):
        self.running=False


class FakeRDS:
    def __init__(self):
        self.current=None
        self.trials=[]

    def availability(self):
        return {"ready":True}

    def start(self,*,frequency_mhz,duration,rds2_images=False):
        self.current=frequency_mhz
        self.trials.append(frequency_mhz)

    def status(self,heartbeat=True):
        # Real decoder would supply this label; RF power alone never does.
        good=self.current==98.6
        return {
            "active":False,"status":"completed",
            "received_groups":10 if good else 0,
            "recent":[{"station":"WDR 2","text":"Test fixture"}] if good else [],
            "last_text":"Test fixture" if good else None
        }

    def stop(self,*,wait=False):
        pass


class FakeStore:
    def __init__(self):
        self.imported=[]

    def import_data(self,body):
        self.imported.append(body)


class FakeDABReader:
    def __init__(self):
        self.store=FakeStore()


class AutoScanTests(unittest.TestCase):
    def test_fm_candidates_never_invent_stations(self):
        peaks=[{"frequency_hz":98_671_000}, {"frequency_hz":93_146_000}]
        self.assertEqual(fm_tuning_candidates(peaks,4),[98.7,98.6,93.1,93.2])
        self.assertEqual(fm_tuning_candidates([{"frequency_hz":30_000_000}],4),[])
        self.assertEqual(dab_channels_from_peaks([
            {"frequency_hz":222_039_000},{"frequency_hz":222_555_000},
            {"frequency_hz":197_805_000}]),["8B","11D"])
        self.assertEqual(DAB_HZ["11D"],222_064_000)

    def test_explicit_consent_gates_all_tuner_auto_scan_actions(self):
        with self.assertRaises(AutoScanError):
            FMAutoScanner(FakeSurvey(),FakeRDS()).start("quick")
        dab=DABAutoScanner(FakeDABReader(),fetcher=lambda path,limit:b"11D")
        with self.assertRaises(AutoScanError):
            dab.start("full")
        self.assertFalse(dab.status()["active"])

    def test_fm_sequential_real_decoder_label_only(self):
        fake_survey,fake_rds=FakeSurvey(),FakeRDS()
        scan=FMAutoScanner(fake_survey,fake_rds)
        first=scan.start("quick",consent=True)
        self.assertTrue(first["active"])
        for _ in range(150):
            result=scan.status()
            if not result["active"]:
                break
            time.sleep(0.02)
        else:
            scan.stop(wait=True)
            self.fail("FM mock worker did not finish")
        self.assertEqual(result["status"],"completed",result)
        self.assertEqual(fake_survey.calls,1)
        self.assertEqual(fake_rds.trials,[98.7,98.6])
        self.assertEqual(len(result["results"]),1)
        self.assertEqual(result["results"][0]["station"],"WDR 2")
        self.assertEqual(result["results"][0]["frequency_mhz"],98.6)
        self.assertTrue(result["results"][0]["rds_verified"])
        with self.assertRaises(ValueError):
            scan.start("unbounded",consent=True)

    def test_dab_real_mux_services_and_original_channel_restoration(self):
        receiver={"channel":"11D","post_history":[]}
        def poster(channel):
            receiver["channel"]=channel
            receiver["post_history"].append(channel)

        def fetcher(path,limit):
            if path=="/channel":
                return receiver["channel"].encode("ascii")
            if path=="/mux.json":
                detected=receiver["channel"]=="5C"
                data={
                    "receiver":{"software":{"name":"welle.io"}},
                    "ensemble":{"label":"TEST ENSEMBLE" if detected else ""},
                    "services":[{
                        "sid":"0x1234","label":"REAL DECODED STATION",
                        "dls_label":"RADIO DATA",
                        "dls_time":1_783_610_000,
                        "url_mp3":"/mp3/0x1234",
                    }] if detected else []
                }
                return json.dumps(data).encode()
            raise AssertionError(path)

        reader=FakeDABReader()
        scanner=DABAutoScanner(reader,fetcher=fetcher,poster=poster)
        initial=scanner.start("detected",dwell_seconds=4,candidates=["5C"],consent=True)
        self.assertTrue(initial["active"])
        for _ in range(250):
            state=scanner.status()
            if not state["active"]:
                break
            time.sleep(0.025)
        else:
            scanner.stop(wait=True)
            self.fail("DAB scan mock timed out")
        self.assertEqual(state["status"],"completed",state)
        self.assertTrue(state["restored"])
        self.assertEqual(receiver["channel"],"11D")
        self.assertEqual(receiver["post_history"],["5C","11D"])
        self.assertEqual(len(state["results"]),1)
        self.assertEqual(state["results"][0]["ensemble"],"TEST ENSEMBLE")
        self.assertEqual(state["results"][0]["services"][0]["name"],"REAL DECODED STATION")
        self.assertEqual(len(reader.store.imported),1)
        with self.assertRaises(AutoScanError):
            scanner.tune("5C",consent=False)
        tuned=scanner.tune("5C",consent=True)
        self.assertEqual(tuned["channel"],"5C")
        self.assertEqual(receiver["channel"],"5C")
        self.assertTrue(tuned["retuned_by_explicit_user"])

    def test_tune_same_verified_dab_block_does_not_reboot_decoder(self):
        from textcenter.core import Store
        from textcenter.channel_catalog import ChannelCatalog
        with tempfile.TemporaryDirectory() as td:
            real_store=Store(Path(td)/"db.sqlite")
            catalog=ChannelCatalog(real_store)
            catalog.save_dab(channel="11D",frequency_hz=222_064_000,
                service_id="0x1234",name="WDR 5",ensemble="WDR NRW",
                audio_advertised=True)
            reader=type("Reader",(),{"store":real_store})()
            posted=[]
            def fetch(path,limit):
                if path=="/channel":return b"11D"
                if path=="/mux.json":
                    return json.dumps({"receiver":{"software":{"name":"welle-cli"}},
                        "ensemble":{"label":"WDR NRW"},"services":[
                            {"sid":"0x1234","label":"WDR 5",
                             "url_mp3":"/mp3/0x1234"}]}).encode()
                raise AssertionError(path)
            scanner=DABAutoScanner(reader,fetcher=fetch,poster=posted.append)
            result=scanner.tune("11D",consent=True)
            self.assertFalse(result["retuned_by_explicit_user"])
            self.assertEqual(posted,[],"Same ensemble must not be reset")
            self.assertIn("Already on",result["note"])

    def test_dab_requires_real_welle_identity_and_hints(self):
        def fake_fetch(path,limit):
            if path=="/channel":return b"11D"
            return json.dumps({
                "receiver":{"software":{"name":"not-welle"}},
                "services":[]}).encode()
        scan=DABAutoScanner(FakeDABReader(),fetcher=fake_fetch)
        with self.assertRaisesRegex(RuntimeError,"welle"):
            scan.start("full",consent=True)
        self.assertFalse(scan.status()["active"])
        with self.assertRaises(ValueError):
            scan.start("unknown",consent=True)


if __name__=="__main__":
    unittest.main()
