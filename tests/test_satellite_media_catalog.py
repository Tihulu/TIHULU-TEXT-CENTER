"""Never mistake a geometric pass for a verified image or packet."""
import unittest
from satellite_center.media_catalog import capabilities_for_pass,filter_passes,kinds_for_pass,media_summary

class MediaCatalogTests(unittest.TestCase):
    def test_iss_has_only_possible_media_not_guaranteed(self):
        p={"name":"ISS (ZARYA)","family":"iss","profiles":["iss_sstv","iss_voice","iss_aprs_uhf","iss_uhf"]}
        self.assertEqual(kinds_for_pass(p),["Image","Audio","Text","RF data"])
        messages=media_summary(p)
        self.assertTrue(any("Event only / unverified" in line for line in messages))
        self.assertIn("≠ actual received RF",messages[-1])

    def test_meteor_image_requires_decoder_and_real_rf(self):
        p={"name":"METEOR-M2 4","family":"meteor","profiles":["meteor","meteor_backup"]}
        self.assertEqual(kinds_for_pass(p),["Image","RF data"])
        self.assertTrue(any("SatDump" in line for line in media_summary(p)))
        self.assertFalse("Text" in kinds_for_pass(p))

    def test_iridium_and_unknown_are_rf_only(self):
        p={"name":"IRIDIUM 109","family":"iridium","profiles":["iridium","iridium_rf_iq"]}
        self.assertEqual(kinds_for_pass(p),["RF data"])
        self.assertTrue(any("No image protocol is catalogued" in line for line in media_summary(p)))
        self.assertFalse(filter_passes([p],"Image"))

    def test_search_and_media_filters(self):
        p1={"name":"METEOR-M2 3","norad":57166,"family":"meteor","profiles":["meteor"]}
        p2={"name":"CUBESAT","norad":99999,"family":"cubesat","profiles":["cubesat_uhf"]}
        self.assertEqual(filter_passes([p1,p2],"Image"),[p1])
        self.assertEqual(filter_passes([p1,p2],"All","99999"),[p2])
        self.assertEqual(filter_passes([p1,p2],"Text"),[])
        self.assertEqual(kinds_for_pass(p2),["RF data"])
