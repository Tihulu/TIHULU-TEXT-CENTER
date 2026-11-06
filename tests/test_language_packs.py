import tempfile
from pathlib import Path
import json
import unittest
from textcenter.language_packs import (
  LanguagePacks, LanguagePackError, available_from_index, normalize_code
)


class LanguageModelsTests(unittest.TestCase):
    def test_catalog_is_allowlisted_and_does_not_trigger_network(self):
        with self.assertRaises(ValueError):normalize_code("../download")
        items=available_from_index([
            {"type":"translate","from_code":"en","to_code":"fr","package_version":"2"},
            {"type":"translate","from_code":"en","to_code":"fr"},
            {"type":"sbd","from_code":"en","to_code":"fr"},
            {"type":"translate","from_code":"../../etc","to_code":"de"},
        ])
        self.assertEqual(len(items),1)
        self.assertEqual(items[0]["target"],"fr")
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/"index.json";path.write_text(json.dumps([
                {"type":"translate","from_code":"tr","to_code":"es"}
            ]))
            manager=LanguagePacks(index_path=path,installed=lambda:[],
                runner=lambda args,timeout: (_ for _ in ()).throw(
                    AssertionError("No network operation allowed by reading status")))
            status=manager.status()
            self.assertFalse(status["auto_download"])
            self.assertEqual(status["available_pairs"][0]["target"],"es")
            with self.assertRaises(LanguagePackError):
                manager.refresh_index()
            with self.assertRaises(LanguagePackError):
                manager.install("tr","es")
            with self.assertRaises(LanguagePackError):
                manager.translate("Merhaba","tr","es")

    def test_same_language_identity_and_no_faked_extended_model(self):
        manager=LanguagePacks(index_path=Path("/nonexistent"),installed=lambda:[])
        self.assertEqual(manager.translate("Hello","en","en")["translated"],"Hello")
        with self.assertRaises(ValueError):
            manager.translate("","de","de")


if __name__=="__main__":
    unittest.main()
