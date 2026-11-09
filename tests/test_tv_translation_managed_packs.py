"""No-network regressions for Market-installed FR/EN/TR live translations.

The GUI's installed pack listing and the live Argos worker must use the
same managed Python environment. Loading NLLB, Torch or Hailo is never
required to test Argos CPU translation.
"""
from __future__ import annotations

from pathlib import Path
from types import ModuleType, SimpleNamespace
import os
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from tv_center.argos_generation import changed, generation, marker_path
from tv_center.captions import _translate_argos_local, translate
from tv_center.translation_service import ArgosService
from tv_center.translation_failover import TranslationFailover
from tv_center.ai_provision import StarterAI, translate_ready, translate_ready_three


class SharedArgosRuntimeTests(unittest.TestCase):
    def test_live_prefers_model_markets_managed_venv_even_if_system_argos_exists(self):
        with patch("tv_center.runtime.AIRuntime") as ai, patch(
                "tv_center.translation_service.translate_argos",
                return_value="Bonjour") as managed, patch(
                "textcenter.transcripts.translate_offline",
                side_effect=AssertionError("Do not read system packages")):
            ai.return_value.status.return_value={"installed":True}
            self.assertEqual(_translate_argos_local("Hello","en","fr"),"Bonjour")
        managed.assert_called_once_with("Hello","en","fr")

    def test_system_fallback_only_without_managed_runtime(self):
        with patch("tv_center.runtime.AIRuntime") as ai, patch(
                "textcenter.transcripts.translate_offline",
                return_value="Günaydın") as system, patch(
                "tv_center.translation_service.translate_argos",
                side_effect=AssertionError("Managed runtime missing")):
            ai.return_value.status.return_value={"installed":False}
            self.assertEqual(_translate_argos_local("Bonjour","fr","tr"),"Günaydın")
        self.assertEqual(system.call_args.kwargs["backend"],"cpu")

    def test_venv_readiness_does_not_report_unrelated_system_packages(self):
        ai=SimpleNamespace(values={"model_path":"",
              "asr_enabled":True,"translation_enabled":True})
        runtime=SimpleNamespace(status=lambda:{"installed":True})
        library=SimpleNamespace(_path=lambda code:Path("/no-test-file"))
        whisper=SimpleNamespace(ready=lambda:True)
        starter=StarterAI(ai=ai,library=library,runtime=runtime,whisper=whisper)
        pairs=[
            {"source":x,"target":y}
            for x,y in (("de","en"),("en","de"),("en","tr"),
                        ("tr","en"),("en","fr"),("fr","en"))
        ]
        with patch("tv_center.argos_market_bridge.run",return_value=pairs) as bridge, patch(
                "tv_center.ai_provision.argos_installed_pairs",
                side_effect=AssertionError("system Python must not be used")):
            state=starter.status()
        self.assertTrue(state["translation_four_languages_ready"])
        bridge.assert_called_once_with("installed",installed_timeout=9)

    def test_bidirectional_translation_mesh_including_french(self):
        pairs=[{"source":x,"target":y}
               for x,y in (("de","en"),("en","de"),("en","tr"),
                           ("tr","en"),("en","fr"),("fr","en"))]
        self.assertTrue(translate_ready(pairs))
        self.assertTrue(translate_ready_three(pairs))
        self.assertFalse(translate_ready(pairs[:-1]))


class CacheRefreshTests(unittest.TestCase):
    def test_model_market_marks_changes_atomically(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertIsNone(generation(folder))
            first=changed(folder)
            self.assertEqual(first,generation(folder))
            self.assertTrue(marker_path(folder).is_file())
            self.assertEqual(marker_path(folder).stat().st_mode & 0o077,0)
            second=changed(folder)
            self.assertNotEqual(first,second)

    def test_persistent_worker_restarts_when_market_installs_new_pack(self):
        service=ArgosService()
        old_process=Mock()
        old_process.poll.return_value=None
        service.process=old_process
        service._generation=("previous",)
        with patch("tv_center.argos_generation.generation",
                   return_value=("new",)), patch(
                   "tv_center.translation_service.NLLBService.translate",
                   return_value="Bonjour") as invoke:
            result=service.translate("Hello","en","fr")
        self.assertEqual(result,"Bonjour")
        old_process.terminate.assert_called_once()
        invoke.assert_called_once()

    def test_external_package_added_without_marker_retries_stale_missing_model(self):
        service=ArgosService()
        with patch("tv_center.argos_generation.generation",return_value=None), patch(
             "tv_center.translation_service.NLLBService.translate",
             side_effect=[RuntimeError("Argos direct translation package missing"),
                          "Bonjour"]) as invoke, patch.object(
             service,"close_locked") as clear:
            self.assertEqual(service.translate("Hello","en","fr"),"Bonjour")
        self.assertEqual(invoke.call_count,2)
        clear.assert_called_once()

    def test_timeout_does_not_repeat_slow_worker_attempt(self):
        service=ArgosService()
        with patch("tv_center.argos_generation.generation",return_value=None), patch(
             "tv_center.translation_service.NLLBService.translate",
             side_effect=TimeoutError("live worker budget")) as invoke:
            with self.assertRaises(TimeoutError):
                service.translate("Bonjour","fr","tr")
        invoke.assert_called_once()


class AccurateErrorsTests(unittest.TestCase):
    def test_pack_present_but_worker_timeout_has_real_diagnostic(self):
        dispatcher=TranslationFailover()
        result=dispatcher.translate(
            "Bonjour","fr","en",preferred="argos",
            nllb=lambda *a:None,
            argos=lambda *a:(_ for _ in ()).throw(
                TimeoutError("Argos worker exceeded 10s live-caption budget")))
        self.assertIsNone(result.text)
        self.assertIn("FR → EN",result.error)
        self.assertIn("10s",result.error)
        self.assertNotIn("language pack unavailable",result.error)

    def test_live_translation_reports_managed_runtime_error(self):
        with patch.dict(os.environ,{"TIHULU_TRANSLATOR_MODEL":"argos"}), patch(
             "tv_center.runtime.AIRuntime") as runtime, patch(
             "tv_center.translation_service.translate_argos",
             side_effect=RuntimeError("Argos runtime model failed to load")):
            runtime.return_value.status.return_value={"installed":True}
            translated,error=translate("Bonjour","fr","en")
        self.assertIsNone(translated)
        self.assertIn("model failed to load",error)


class PureArgosCPUTranslationTests(unittest.TestCase):
    def test_cpu_path_skips_cuda_probe_and_uses_valid_pivot(self):
        from textcenter.transcripts import translate_offline
        class FakeModel:
            def __init__(self,code):
                self.code=code
            def translate(self,text):
                return ("EN: "+text) if self.code=="en" else "TR: "+text
        class FakeLang:
            def __init__(self,code): self.code=code
            def get_translation(self,destination):
                if (self.code,destination.code)==("fr","en"):
                    return FakeModel("en")
                if (self.code,destination.code)==("en","tr"):
                    return FakeModel("tr")
                raise LookupError("Direct pair unavailable")
        fake=ModuleType("argostranslate")
        worker=ModuleType("argostranslate.translate")
        worker.get_installed_languages=lambda:[
            FakeLang("fr"),FakeLang("en"),FakeLang("tr")]
        fake.translate=worker
        with patch.dict(sys.modules,{"argostranslate":fake,
                                     "argostranslate.translate":worker}), patch(
                "textcenter.transcripts.translation_devices",
                side_effect=AssertionError("No device scan in Argos CPU")):
            self.assertEqual(
                translate_offline("Bonjour","fr","tr",backend="cpu"),
                "TR: EN: Bonjour")
            self.assertEqual(
                translate_offline("Bonjour","fr","tr",backend="auto"),
                "TR: EN: Bonjour")


if __name__=="__main__":
    unittest.main()
