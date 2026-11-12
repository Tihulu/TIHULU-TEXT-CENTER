"""REG-10 canonical Text Center negative capability contracts.

Synthetic-only: no receiver, welle-cli daemon, network, DVB tuner or installed
speech/translation model. Do not import Media Center or archived Text copies.
"""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from textcenter.core import Store
from textcenter.dab_bridge import DABError, DABReader, _local_get
from textcenter.fm_survey import parse_power_csv


class Reg10SourceIntegrityTests(unittest.TestCase):
    def test_unrecognized_welle_metadata_does_not_invent_dls_plus_or_journaline(self):
        # The current bridge supports plain decoder-reported DLS and MOT.
        # It MUST NOT claim to have decoded structured DLS+ or Journaline
        # merely because the external mux JSON contains unfamiliar keys.
        mux = json.dumps({
            "receiver": {"software": {"name": "welle.io"}},
            "ensemble": {"label": "SYNTHETIC"},
            "services": [{
                "sid": "0x1234", "label": "SYNTHETIC DAB",
                "dls_label": "Ordinary external DLS",
                "dls_time": 0,  # deliberately NOT a trusted reception timestamp
                "mot_time": 0,
                "dls_plus": {"tags": [{"type": "item.artist",
                                         "value": "NOT DECODED"}]},
                "journaline": {"pages": [{"title": "NOT DECODED"}]},
            }],
        }).encode("utf-8")
        paths = []

        def fetch(path, _limit):
            paths.append(path)
            return b"11D" if path == "/channel" else mux

        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / "archive.sqlite")
            result = DABReader(store, fetcher=fetch).refresh(include_images=True)
            self.assertEqual(paths, ["/channel", "/mux.json"])
            self.assertTrue(result["radio_not_retuned"])
            self.assertEqual(result["imported_dls"], 0)
            self.assertEqual(result["saved_mot_images"], 0)
            self.assertEqual(store.events(), [])
            row = result["services"][0]
            self.assertEqual(row["dls"], "Ordinary external DLS")
            self.assertFalse(any("journaline" in k.lower() or "dls_plus" in k.lower()
                                 for k in row))
            self.assertNotIn("NOT DECODED", repr(row))

    def test_missing_external_welle_receiver_has_no_archive_or_spawn_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / "archive.sqlite")
            reader = DABReader(
                store,
                fetcher=lambda *_: (_ for _ in ()).throw(
                    DABError("welle-cli not running")),
            )
            with patch("subprocess.Popen",
                       side_effect=AssertionError("must not start welle-cli")):
                with self.assertRaisesRegex(DABError, "not running"):
                    reader.refresh()
            self.assertEqual(store.events(), [])
            self.assertEqual(store.counts()["events"], 0)

    def test_dab_bridge_rejects_tune_and_unrecognized_local_paths_before_network(self):
        # Guard rail for the read-only welle-cli bridge; this assertion
        # only tests path admission, not an actual network connection.
        with patch("textcenter.dab_bridge.urllib.request.build_opener",
                   side_effect=AssertionError("network should not be consulted")):
            for path in ("/channel/retune", "/channel?freq=5C",
                         "/start", "/stream/0x1234", "/journaline/0x1234"):
                with self.subTest(path=path):
                    with self.assertRaises(DABError):
                        _local_get(path, 100)

    def test_strong_dab_energy_peak_is_not_snr_dls_or_service_discovery(self):
        # Same rtl_power format as deployed parser: exceptionally high
        # relative energy must not be represented as calibrated C/N or a
        # successfully received DAB broadcast service.
        bins = [-69.0] * 24
        bins[13] = -10.0
        csv = ("2026-11-12, 00:00:00, 174000000, 180000000, 250000, 1, "
               + ", ".join(str(x) for x in bins) + "\n")
        parsed = parse_power_csv(csv, band="dab")
        self.assertEqual(len(parsed["candidates"]), 1, parsed)
        peak = parsed["candidates"][0]
        self.assertEqual(peak["verification"], "unidentified_rf_energy")
        self.assertIn("relative_power_db", peak)
        self.assertIn("above_median_db", peak)
        self.assertTrue({"snr_db", "cn_db", "signal_dbm", "service_id",
                         "station", "dls", "ensemble"}.isdisjoint(peak))
        self.assertIn("Candidate RF energy only", parsed["note"])


if __name__ == "__main__":
    unittest.main()
