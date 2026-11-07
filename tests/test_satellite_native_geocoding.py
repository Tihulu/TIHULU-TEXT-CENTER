"""Offline contract tests for native worldwide geocoding and source provenance."""
import unittest
from unittest.mock import patch
from satellite_center.native_geocoding import (
    normalize_city_query, parse_worldwide_places, search_worldwide,
)

class DummyResponse:
    def __init__(self,body,url):
        self.body=body;self.url=url
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def geturl(self):return self.url
    def read(self,size):return self.body

class NativeGeocoderTests(unittest.TestCase):
    def test_sydney_typo_goes_to_actual_provider_not_guessed_coordinates(self):
        self.assertEqual(normalize_city_query("syney"),"Sydney")
        body=(b'{"results":[{"name":"Sydney","latitude":-33.8678,'
              b'"longitude":151.2073,"admin1":"New South Wales",'
              b'"country":"Australia","country_code":"AU"}]}')
        captured=[]
        def fake_open(request,timeout):
            captured.append(request.full_url)
            return DummyResponse(body,request.full_url)
        with patch("satellite_center.native_geocoding.urlopen",fake_open):
            rows=search_worldwide("syney")
        self.assertIn("name=Sydney",captured[0])
        self.assertEqual(rows[0]["provider"],"online")
        self.assertEqual(rows[0]["name"],"Sydney")
        self.assertAlmostEqual(rows[0]["lat"],-33.8678)
        self.assertAlmostEqual(rows[0]["lon"],151.2073)
        self.assertIn("Australia",rows[0]["label"])

    def test_reject_unauthorized_redirect_and_nonfinite_coordinates(self):
        with patch("satellite_center.native_geocoding.urlopen",return_value=DummyResponse(
            b'{"results":[]}',"https://example.com/malicious")):
            with self.assertRaisesRegex(ValueError,"redirected"):
                search_worldwide("Sydney")
        self.assertEqual(parse_worldwide_places({"results":[
            {"name":"Fake","latitude":"NaN","longitude":77},
            {"name":"Wrong country","latitude":1,"longitude":2,
             "country_code":"US"},
        ]},"DE"),[])

    def test_online_result_validation_and_de_tr_filter(self):
        source={"results":[
            {"name":"Berlin","latitude":52.52,"longitude":13.405,
             "country_code":"DE","country":"Germany"},
            {"name":"Izmir","latitude":38.42,"longitude":27.14,
             "country_code":"TR","country":"Türkiye"},
        ]}
        self.assertEqual(len(parse_worldwide_places(source)),2)
        self.assertEqual(len(parse_worldwide_places(source,"DE")),1)
        self.assertEqual(len(parse_worldwide_places(source,"TR")),1)
        with self.assertRaises(ValueError):normalize_city_query("x")


if __name__=="__main__":unittest.main()
