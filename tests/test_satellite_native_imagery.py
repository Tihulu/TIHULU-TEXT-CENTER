"""Independent native NASA imagery contract: on-demand, provenance, safety."""
import unittest
from unittest.mock import patch

from satellite_center.native_imagery import (
    list_official_images, fetch_official_image,
)


class NativeOnlineImageryTests(unittest.TestCase):
    def test_epic_catalog_is_labeled_as_online_not_rf(self):
        with patch("satellite_center.native_imagery._catalog",return_value=[
            {"image":"epic_1","date":"2026-11-07 13:14:15",
             "caption":"Natural Earth visible disk"},
            {"image":"../invalid","date":"2026-11-07 13:14:15"},
        ]):
            rows=list_official_images("epic")
        self.assertEqual(len(rows),1)
        self.assertFalse(rows[0]["radio_source"])
        self.assertIn("api.nasa.gov/EPIC/archive",rows[0]["url"])
        self.assertIn("2026/11/07",rows[0]["url"])

    def test_iss_catalog_ignores_unapproved_external_hosts(self):
        with patch("satellite_center.native_imagery._catalog",return_value={
            "collection":{"items":[
                {"data":[{"media_type":"image","nasa_id":"ISS_TEST",
                           "title":"Earth from orbit",
                           "date_created":"2026-11-07T12:00:00Z"}],
                 "links":[{"href":"https://images-assets.nasa.gov/approved.jpg"}]},
                {"data":[{"media_type":"image","title":"untrusted"}],
                 "links":[{"href":"https://example.com/not-nasa.jpg"}]}
            ]}}):
            rows=list_official_images("iss")
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["provider"],"NASA ISS Earth archive")
        self.assertFalse(rows[0]["radio_source"])

    def test_photo_preview_requires_source_attribution_and_png_or_jpeg_header(self):
        record={"radio_source":False,
                "url":"https://api.nasa.gov/EPIC/archive/natural/2026/11/07/jpg/test.jpg"}
        with patch("satellite_center.native_imagery._https_bytes",return_value=b"\xff\xd8\xffjpeg"):
            self.assertTrue(fetch_official_image(record).startswith(b"\xff\xd8\xff"))
        with patch("satellite_center.native_imagery._https_bytes",return_value=b"<html>error</html>"):
            with self.assertRaisesRegex(ValueError,"PNG/JPEG"):
                fetch_official_image(record)
        with self.assertRaisesRegex(ValueError,"source"):
            fetch_official_image({"radio_source":True,"url":record["url"]})

    def test_invalid_nasa_provider_is_rejected(self):
        with self.assertRaisesRegex(ValueError,"NASA EPIC"):
            list_official_images("untrusted")


if __name__=="__main__":
    unittest.main()
