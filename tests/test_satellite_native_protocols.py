"""Browser/Qt JSON protocol interoperability without any SDR acquisition."""
import json
import tempfile
import unittest
from pathlib import Path

from satellite_center.native_protocols import (
    parse_user_protocol,validate_profiles,load_profiles,save_profiles,
    import_profiles,export_profiles,match_user_hints)

def entry(norad=59051,hz=137900000,kind="image"):
    return {"norad":norad,"frequencyHz":hz,"kind":kind,
            "protocol":"Meteor LRPT (user reference)",
            "source":"https://db.satnogs.org/"}

class NativeUserProtocolsTests(unittest.TestCase):
    def test_same_schema_as_browser_and_roundtrip(self):
        p=parse_user_protocol(entry())
        self.assertEqual(p["id"],"user-59051-137900000-image")
        self.assertEqual(p["decoder"],"no-decoder-connected")
        with tempfile.TemporaryDirectory() as td:
            save_profiles(td,[entry()])
            self.assertEqual(load_profiles(td),[p])
            target=Path(td)/"portable_export.json"
            export_profiles(td,target)
            exported=json.loads(target.read_text())
            self.assertEqual(exported["schema"],"tihulu-public-satellite-profiles-v1")
            with tempfile.TemporaryDirectory() as another:
                import_profiles(another,target)
                self.assertEqual(load_profiles(another),[p])

    def test_invalid_protocol_and_unverified_https_reference(self):
        for bad in ({**entry(),"frequencyHz":2_000_000_000},
                    {**entry(),"kind":"weapon"},
                    {**entry(),"protocol":"<script>"},
                    {**entry(),"source":"http://example.org"},
                    {**entry(),"source":"https://user:pass@example.org"}):
            with self.assertRaises(ValueError):
                parse_user_protocol(bad)
        with self.assertRaises(ValueError):
            validate_profiles([entry(norad=1000+i) for i in range(33)])

    def test_rf_matches_remain_unverified_and_no_decoder_claim(self):
        profiles=validate_profiles([entry()])
        report={"candidates":[{"frequency_hz":137899800,
                "width_hz_approx":1000,"status":"UNCLASSIFIED_RF_ENERGY_ONLY"}]}
        match_user_hints(report,profiles)
        self.assertEqual(report["candidates"][0]["user_reference_matches_unverified"][0]["norad"],59051)
        self.assertEqual(report["candidates"][0]["status"],"UNCLASSIFIED_RF_ENERGY_ONLY")

    def test_import_does_not_execute_reference_or_start_radio(self):
        with tempfile.TemporaryDirectory() as td:
            target=Path(td)/"profiles.json"
            target.write_text(json.dumps({"profiles":[entry()]}))
            import_profiles(td,target)
            self.assertEqual(len(load_profiles(td)),1)
            self.assertFalse(any(x.name.endswith(".cu8") for x in Path(td).iterdir()))

    def test_malformed_json_shapes_rejected_without_crashing_gui(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"invalid.json"
            for bad in (42, True, "123", {"profiles":"not a list"}):
                path.write_text(json.dumps(bad),encoding="utf-8")
                with self.assertRaises(ValueError):
                    import_profiles(td,path)
            path.unlink()
            (Path(td)/"user_downlinks.json").write_text("99",encoding="utf-8")
            with self.assertRaises(ValueError):
                load_profiles(td)
