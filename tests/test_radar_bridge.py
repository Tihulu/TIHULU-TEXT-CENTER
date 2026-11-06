import tempfile
from pathlib import Path
import unittest
from textcenter.core import Store
from textcenter.radar_bridge import RadarOverlay,RadarError,parse_aircraft,validate_area,combine_aircraft


class RadarTests(unittest.TestCase):
    def test_filter_and_fresh_position_provenance(self):
        with self.assertRaises(ValueError):validate_area(100,0,30)
        with self.assertRaises(ValueError):validate_area(51,7,251)
        rows=parse_aircraft({"aircraft":[{"hex":"ABCDEF","flight":"  TEST1  ",
            "seen":1.0,"lat":51.2,"lon":7.1},
            {"hex":"123456","seen":3.0,"lat":999,"lon":7}]}, "antenna")
        self.assertEqual(len(rows),2)
        self.assertTrue(rows[0]["positioned"])
        self.assertFalse(rows[1]["positioned"])
        internet=parse_aircraft({"ac":[{"hex":"abcdef","seen":5,"lat":51.21,"lon":7.11}]},"internet")
        merged=combine_aircraft(rows,internet)
        self.assertEqual(len(merged),2)
        self.assertEqual(merged[0]["sources"],["antenna","internet"])
        self.assertEqual(merged[0]["position_source"],"antenna")

    def test_cached_rf_never_overrides_fresh_internet_aircraft(self):
        rf=parse_aircraft({"aircraft":[{"hex":"abcdef","seen":1,
             "lat":51.0,"lon":7.0}]},"antenna")
        rf[0]["stale"]=True
        net=parse_aircraft({"ac":[{"hex":"abcdef","seen":10,
             "lat":52.0,"lon":8.0}]},"internet")
        merged=combine_aircraft(rf,net)
        self.assertEqual(merged[0]["position_source"],"internet")
        self.assertEqual(merged[0]["lat"],52.0)
        self.assertFalse(merged[0]["stale"])
        self.assertEqual(merged[0]["source_freshness"],{
            "antenna":"cached","internet":"live"})

    def test_manual_local_internet_hybrid_and_offline_cache(self):
        with tempfile.TemporaryDirectory() as td:
            calls=[]
            def fetch(url):
                calls.append(url)
                if "127.0.0.1" in url:return {"aircraft":[
                    {"hex":"abcdef","seen":1,"lat":51.2,"lon":7.1}]}
                if "api.adsb.lol" in url:return {"ac":[
                    {"hex":"abcdef","seen":4,"lat":51.21,"lon":7.13},
                    {"hex":"654321","seen":2,"lat":51.3,"lon":7.4}]}
                raise RadarError("Unexpected URL")
            overlay=RadarOverlay(Store(Path(td)/"data.db"),fetcher=fetch)
            a=overlay.refresh(mode="hybrid",lat=51.1,lon=7.2,radius=100)
            self.assertEqual(len(a["aircraft"]),2)
            self.assertEqual(a["with_position"],2)
            self.assertTrue(a["statuses"]["antenna"]["status"]=="live")
            self.assertEqual(a["aircraft"][0]["sources"],["antenna","internet"])
            self.assertIn("ODbL",a["attribution"])
            self.assertEqual(len(calls),2)
            fresh=overlay.refresh(mode="internet")
            self.assertEqual(fresh["statuses"]["internet"]["status"],"cached")
            self.assertTrue(all(x["stale"] for x in fresh["aircraft"]))
            self.assertEqual(len(calls),2)
            overlay2=RadarOverlay(Store(Path(td)/"data.db"),
                fetcher=lambda url: (_ for _ in ()).throw(RadarError("No RF")),
                time_fn=lambda:100)
            offline=overlay2.refresh(mode="antenna")
            self.assertEqual(offline["statuses"]["antenna"]["status"],"cached")
            self.assertTrue(offline["aircraft"][0]["stale"])

    def test_invalid_data_does_not_create_fake_aircraft(self):
        for doc in ({}, {"aircraft":"nope"}):
            with self.assertRaises(RadarError):parse_aircraft(doc,"antenna")
        self.assertEqual(parse_aircraft({"ac":[{"hex":"none","seen":1},
            {"hex":"abcdef","seen":200}]},"internet"),[])


if __name__=="__main__":
    unittest.main()
