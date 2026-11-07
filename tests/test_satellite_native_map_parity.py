"""Native map/parity export: no SDR, network, Qt widgets or fake RF claims."""
import tempfile
import unittest
import json
from pathlib import Path

from satellite_center.native_map_parity import (
    map_satellite_capabilities,map_satellite_protocols,filter_orbit_snapshot,
    orbital_geojson,export_orbit_geojson)

def row(norad,family,name,el=30):
    return {"norad":norad,"name":name,"family":family,
            "lat":38.4,"lon":27.1,"el":el,"az":65,
            "alt_km":390,"range_km":690,"tle_age_days":1}

class NativeMapParityTests(unittest.TestCase):
    def test_only_specific_known_norad_receives_media_candidate_badges(self):
        self.assertEqual(map_satellite_capabilities(row(25544,"iss","ISS")),
                         ["Image","Audio","Text","RF data"])
        self.assertEqual(map_satellite_capabilities(row(59051,"meteor","METEOR")),
                         ["Image","RF data"])
        self.assertEqual(map_satellite_capabilities(row(999999,"meteor","Unknown METEOR")),
                         ["RF data"])
        self.assertEqual(map_satellite_capabilities(row(999001,"iridium","IRIDIUM")),
                         ["RF data"])
        self.assertTrue(any("SatDump" in text for text in map_satellite_protocols(
            row(59051,"meteor","METEOR"))))
    def test_native_map_media_filter_without_identity_claim(self):
        objects=[row(59051,"meteor","METEOR"),row(25544,"iss","ISS",el=-12),
                 row(1000,"iridium","IRIDIUM")]
        snapshot={"satellites":objects}
        self.assertEqual(len(filter_orbit_snapshot(snapshot,"Image")["satellites"]),2)
        self.assertEqual(len(filter_orbit_snapshot(snapshot,"Image",True)["satellites"]),1)
        self.assertEqual(len(filter_orbit_snapshot(snapshot,"RF only")["satellites"]),1)
        self.assertEqual(len(filter_orbit_snapshot(snapshot,"All",query="met")["satellites"]),1)
    def test_installed_desktop_uses_native_orbits_and_bundled_world_map(self):
        root=Path(__file__).resolve().parents[1]/"satellite_center"
        frontend=(root/"native_desktop_bridge.js").read_text(encoding="utf-8")
        backend=(root/"native_web_shell.py").read_text(encoding="utf-8")
        planner=(root/"browser"/"browser.js").read_text(encoding="utf-8")
        maps=(root/"browser"/"satellite_maps.mjs").read_text(encoding="utf-8")
        for name in ("nativeOrbitCatalog", "nativeOrbitPasses",
                     "nativeOrbitSnapshot", "nativeWorldOutline",
                     "nativeImportTle", "nativeCustomTle"):
            self.assertIn("window."+name,frontend)
        for op in ('"tle_catalog"','"orbit_snapshot"','"world_outline"',
                   '"tle_import"','"tle_custom"'):
            self.assertIn(op,backend)
        self.assertIn("with_track=with_tracks",backend)
        self.assertIn("typeof window.nativeOrbitCatalog==='function'",planner)
        self.assertIn("typeof window.nativeOrbitPasses==='function'",planner)
        self.assertIn("typeof window.nativeImportTle==='function'",planner)
        self.assertIn("typeof window.nativeOrbitSnapshot==='function'",maps)
        self.assertIn("typeof window.nativeWorldOutline==='function'",maps)
        self.assertIn("await getSatLib()",maps) # browser/PWA fallback remains
        self.assertIn('"manual"',(root/"native_orbit.py").read_text(encoding="utf-8"))
        geo=json.loads((root/"browser"/"natural-earth-land-110m.geojson").read_text())
        self.assertEqual(geo["type"],"FeatureCollection")
        self.assertGreater(len(geo["features"]),100)

    def test_geojson_source_and_utc_provenance(self):
        sample={"satellites":[row(59051,"meteor","METEOR")],
                "observer":{"lat":50.87,"lon":6.86},"at_utc":"2026-11-07T12:00:00+00:00",
                "total_loaded":20,"warnings":["public TLE"],"note":"TLE geometry; no RF",
                "track_segments":[[{"lat":38.4,"lon":27.0},{"lat":39.0,"lon":28.0}]]}
        data=orbital_geojson(sample)
        self.assertEqual(data["type"],"FeatureCollection")
        self.assertFalse(data["properties"]["has_rf_evidence"])
        self.assertEqual(data["features"][0]["geometry"]["coordinates"],[27.1,38.4])
        self.assertEqual(data["features"][0]["properties"]["candidate_media_not_verified"],["Image","RF data"])
        self.assertEqual(data["features"][2]["geometry"]["type"],"LineString")
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"predicted-orbits.geojson"
            export_orbit_geojson(sample,path)
            self.assertEqual(json.loads(path.read_text())["features"][1]["properties"]["status"],
                             "OPERATOR_COORDINATES_UNVERIFIED")
            with self.assertRaisesRegex(ValueError,"overwrite"):
                export_orbit_geojson(sample,path)
