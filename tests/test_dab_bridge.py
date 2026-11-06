import json
from pathlib import Path
import tempfile
import unittest
from textcenter.core import Store
from textcenter.dab_bridge import DABReader,parse_mux,DABError
from textcenter.media import MediaStore

PNG=(b"\x89PNG\r\n\x1a\n"+b"\x00\x00\x00\x0dIHDR"+
     b"\x00\x00\x00\x01\x00\x00\x00\x01"+b"\x08\x02\x00\x00\x00"+
     b"\x90\x77\x53\xde"+b"\x00\x00\x00\x00IEND\xae\x42\x60\x82")


class DABTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.store=Store(Path(self.tmp.name)/"db.sqlite")
        self.raw=json.dumps({
            "receiver":{"software":{"name":"welle.io","version":"2.x"}},
            "ensemble":{"label":"TEST NRW"},
            "services":[{
                "sid":"0x1234","label":"TEST STATION",
                "dls_label":"REAL DATA ONLY WHEN FROM ACTUAL DECODER",
                "dls_time":1_783_610_000,"mot_time":1_783_610_000,
                "ptystring":"News","url_mp3":"/mp3/0x1234",
            }]
        }).encode()

    def tearDown(self):self.tmp.cleanup()

    def test_readonly_decoder_bridge_preserves_real_provenance(self):
        requested=[]
        def fetch(path,limit):
            requested.append(path)
            return {"/channel":b"11D","/mux.json":self.raw,"/slide/0x1234":PNG}[path]
        reader=DABReader(self.store,fetcher=fetch)
        result=reader.refresh(include_images=True)
        self.assertEqual(result["channel"],"11D")
        self.assertEqual(result["frequency_hz"],222_064_000)
        self.assertEqual(result["imported_dls"],1)
        self.assertEqual(result["saved_mot_images"],1)
        self.assertEqual(len(self.store.events()),1)
        self.assertEqual(len(MediaStore(self.store).list()),1)
        self.assertEqual(requested,["/channel","/mux.json","/slide/0x1234"])
        self.assertTrue(result["radio_not_retuned"])
        self.assertEqual(result["services"][0]["name"],"TEST STATION")

    def test_all_standard_channel_centres_can_archive_real_decoder_images(self):
        from textcenter.dab_bridge import DAB_HZ
        for channel,centre in (("5C",178_352_000),("8B",197_648_000),
                               ("9D",208_064_000),("11D",222_064_000)):
            with self.subTest(channel=channel):
                seen=[]
                def fetch(path,_):
                    seen.append(path)
                    return channel.encode() if path=="/channel" else (
                        self.raw if path=="/mux.json" else PNG
                    )
                reader=DABReader(self.store,fetcher=fetch)
                result=reader.refresh(include_images=True)
                self.assertEqual(result["frequency_hz"],centre)
                self.assertEqual(result["saved_mot_images"],1)
                self.assertEqual(result["services"][0]["mot_image_status"],"saved")
                self.assertTrue(result["services"][0]["mot_media_id"])
                self.assertEqual(result["mot_images_failed"],0)
                self.assertEqual(DAB_HZ[channel],centre)

    def test_image_missing_vs_failed_is_visible_and_does_not_claim_save(self):
        source=json.loads(self.raw)
        source["services"].append({
            "sid":"0x5678","label":"NO IMAGE",
            "dls_label":"","mot_time":0
        })
        payload=json.dumps(source).encode()
        def broken_slide(path,_):
            if path=="/channel":return b"11D"
            if path=="/mux.json":return payload
            raise DABError("no MOT for this station")
        report=DABReader(self.store,fetcher=broken_slide).refresh()
        self.assertEqual(report["saved_mot_images"],0)
        self.assertEqual(report["mot_images_failed"],1)
        self.assertEqual(report["mot_images_missing"],1)
        services={x["name"]:x for x in report["services"]}
        self.assertEqual(services["TEST STATION"]["mot_image_status"],"failed")
        self.assertEqual(services["NO IMAGE"]["mot_image_status"],"not_broadcast")
        self.assertIn("No new MOT image saved",report["archive_notice"])
        self.assertFalse(MediaStore(self.store).list())
        skipped=DABReader(self.store,fetcher=broken_slide).refresh(include_images=False)
        self.assertEqual(skipped["mot_images_skipped"],2)
        self.assertTrue(all(x["mot_image_status"]=="not_requested" for x in skipped["services"]))

    def test_bad_endpoint_identity_and_unknown_channel_fail_closed(self):
        with self.assertRaises(DABError):
            parse_mux(json.dumps({"receiver":{"software":{"name":"fake"}},"services":[]}).encode(),"11D")
        doc=parse_mux(self.raw,"UNKNOWN")
        self.assertIsNone(doc["frequency_hz"])
        reader=DABReader(self.store,fetcher=lambda path,_:b"??" if path=="/channel" else self.raw)
        result=reader.refresh()
        self.assertEqual(result["imported_dls"],0)
        self.assertEqual(result["saved_mot_images"],0)
        self.assertEqual(self.store.counts()["events"],0)


if __name__=="__main__":
    unittest.main()
