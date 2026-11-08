"""Regression tests for the instant native output-language checkbox menu."""
import inspect
import subprocess
import unittest
from types import SimpleNamespace
from unittest import mock


class FastOutputLanguageTests(unittest.TestCase):
    def test_argos_readonly_lookup_has_bounded_optional_deadline(self):
        from tv_center.argos_market_bridge import run
        with mock.patch("tv_center.runtime.AIRuntime") as market, \
             mock.patch("tv_center.argos_market_bridge.subprocess.run") as process:
            market.return_value.status.return_value={
                "installed":True,"python":"/tmp/managed-python"}
            process.return_value=SimpleNamespace(returncode=0,stdout=b"[]")
            self.assertEqual(run("installed",installed_timeout=8.0),[])
            self.assertEqual(process.call_args.kwargs["timeout"],8.0)
            with self.assertRaises(ValueError):
                run("install",installed_timeout=8.0)

    def test_timeout_preserves_selectable_languages(self):
        from tv_center.installed_languages import catalog
        with mock.patch("tv_center.argos_market_bridge.run",
            side_effect=subprocess.TimeoutExpired(["argos"],8)) as run:
            result=catalog(installed_pairs=None,nllb_installed=False)
        run.assert_called_once_with("installed",installed_timeout=8.0)
        self.assertEqual(result["languages"],[])
        self.assertTrue(result["errors"])
        self.assertIn("timed",result["errors"][0].lower())

    def test_madlad_installed_destinations_are_marked_unverified(self):
        from tv_center.installed_languages import catalog
        result=catalog(installed_pairs=[],nllb_installed=False,
                       madlad_installed=True)
        by_code={item["code"]:item for item in result["languages"]}
        self.assertTrue(result["madlad_present"])
        self.assertIn("en",by_code)
        self.assertIn("tr",by_code)
        self.assertIn("MADLAD (weights present)",by_code["tr"]["engines"])
        self.assertFalse(by_code["tr"]["verified_by_runtime"])

    def test_fast_model_discovery_does_not_import_argos(self):
        from tv_center.installed_languages import catalog
        with mock.patch("tv_center.argos_market_bridge.run") as run:
            results=catalog(installed_pairs=None,scan_argos=False,
                            madlad_installed=True,nllb_installed=False,
                            deepl_configured=False)
        run.assert_not_called()
        by_code={r["code"]:r for r in results["languages"]}
        self.assertIn("MADLAD (weights present)",by_code["en"]["engines"])
        self.assertFalse(results["scan_argos"])

    def test_deepl_is_remote_even_when_key_is_configured(self):
        from tv_center.installed_languages import catalog
        results=catalog(installed_pairs=[],nllb_installed=False,
                        madlad_installed=False,deepl_configured=True)
        code={r["code"]:r for r in results["languages"]}
        self.assertIn("DeepL API (online; configured key, target unverified)",
                      code["tr"]["engines"])
        self.assertTrue(results["deepl_online_key_configured"])
        self.assertFalse(code["tr"]["verified_by_runtime"])

    def test_native_dropdown_is_populated_before_async_scan(self):
        from kaffeine_next import captions_overlay
        code=inspect.getsource(captions_overlay.main)
        initial=code.index('fill_languages({"languages":[]},pending=True)')
        asynchronous=code.index("QTimer.singleShot(150,start_language_catalog)")
        self.assertLess(initial,asynchronous)
        self.assertIn('baseline = ("en", "tr", "de", "fr")',code)
        self.assertIn('requested_languages = {"en"}',code)
        self.assertIn("language_timeout.start(11000)",code)
        self.assertIn("language_timeout.start(3500)",code)
        self.assertIn('["-m","tv_center.installed_languages","--fast"]',code)
        self.assertIn("known_models = {}",code)
        self.assertIn("language_process.errorOccurred.connect(language_catalog_error)",code)

    def test_refresh_preserves_user_checked_values(self):
        from kaffeine_next import captions_overlay
        code=inspect.getsource(captions_overlay.main)
        self.assertIn("requested_languages.add(code)",code)
        self.assertIn("requested_languages.discard(code)",code)
        self.assertIn("cb.setChecked(code in requested_languages)",code)
        self.assertIn("Refresh installed languages",code)
        self.assertIn("local model: ",code)
        self.assertIn("no offline translation pack confirmed",code)
        self.assertIn("no model, source or channel changed",code.lower())


if __name__=="__main__":
    unittest.main()
