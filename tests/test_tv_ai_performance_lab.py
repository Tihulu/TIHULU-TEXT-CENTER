"""Offline AI measurements and installed-language GUI regression tests."""
from pathlib import Path
import inspect
import unittest
from unittest.mock import Mock,patch

from tv_center.installed_languages import catalog
from tv_center.performance_lab import recommend,diagnose_live,inventory


class InstalledOutputLanguagesTests(unittest.TestCase):
    def test_catalog_does_not_guess_uninstalled_language_packs(self):
        found=catalog(installed_pairs=[
            {"source":"de","target":"en"},
            {"source":"de","target":"tr"},
            {"source":"en","target":"de"},
            {"source":"invalid","target":"zz"}],nllb_installed=False)
        languages={x["code"]:x for x in found["languages"]}
        self.assertEqual(set(languages),{"de","en","tr"})
        self.assertEqual(languages["en"]["engines"],["Argos"])
        self.assertEqual(found["installed_argos_pairs"],4)
        self.assertFalse(found["nllb_present"])

    def test_nllb_weights_do_not_claim_real_success(self):
        found=catalog(installed_pairs=[],nllb_installed=True)
        languages={x["code"]:x for x in found["languages"]}
        self.assertIn("fr",languages)
        self.assertFalse(languages["fr"]["verified_by_runtime"])
        self.assertIn("weights present",languages["fr"]["engines"][0].lower())


class BenchmarkRecommendationTests(unittest.TestCase):
    def test_fastest_real_model_keeps_preexisting_larger_tv_buffer(self):
        measurements=[
            {"kind":"asr","status":"ok","backend":"cpu",
             "model_path":"/local/tiny.bin","elapsed_s":9.2},
            {"kind":"asr","status":"ok","backend":"gpu",
             "model_path":"/local/gpu-model","elapsed_s":1.7},
            {"kind":"translation","status":"ok","engine":"argos",
             "target":"en","elapsed_s":0.4},
            {"kind":"translation","status":"ok","engine":"argos",
             "target":"tr","elapsed_s":0.8},
            {"kind":"translation","status":"timeout","engine":"nllb",
             "target":"tr","elapsed_s":99},
        ]
        result=recommend(measurements,current_buffer_ms=14500)
        self.assertEqual(result["backend"],"gpu")
        self.assertEqual(result["translation_model"],"argos")
        self.assertEqual(result["minimum_buffer_ms"],14500)
        self.assertTrue(result["realtime_sustainable"])

    def test_no_inference_is_not_a_verified_model(self):
        result=recommend([{"kind":"asr","status":"timeout",
                          "elapsed_s":65}],current_buffer_ms=9000)
        self.assertIsNone(result["backend"])
        self.assertFalse(result["realtime_sustainable"])
        self.assertEqual(result["minimum_buffer_ms"],9000)

    def test_measured_slow_pipeline_vs_radio_transport_loss(self):
        over=diagnose_live([{"compute_ms":9200,"queue_wait_ms":1800}] * 4,
                           queue_overflows=1,ts_audio_gaps=2)
        self.assertEqual(over["state"],"measured")
        self.assertIn("caption_capture_queue_overflow",over["causes"])
        self.assertIn("dvb_audio_continuity_gaps",over["causes"])
        self.assertIn("inference_or_translation_too_slow",over["causes"])
        self.assertIn("caption_queue_backlog",over["causes"])
        self.assertFalse(over["hardware_proven"])
        stable=diagnose_live([{"compute_ms":1200,"queue_wait_ms":60}] * 4)
        self.assertEqual(stable["causes"],[])
        self.assertLess(stable["median_compute_realtime_factor"],1)


class KaffeineModelGuiTests(unittest.TestCase):
    def test_only_user_approved_benchmark_may_write_settings(self):
        import tv_center.performance_lab as lab
        source=inspect.getsource(lab)
        self.assertNotIn("AISettings().update(",source)
        self.assertIn('["ffmpeg","-hide_banner","-nostdin"',source)
        self.assertIn('"HF_HUB_OFFLINE":"1"',source)
        self.assertIn("No model will download".lower()[:8],"No model will download".lower())

    def test_new_ui_has_nonblocking_dropdown_and_approval_gate(self):
        from kaffeine_next import captions_overlay
        source=inspect.getsource(captions_overlay.main)
        self.assertIn("output_button = QToolButton()",source)
        self.assertIn("QWidgetAction(output_menu)",source)
        self.assertIn("QCheckBox(code.upper()",source)
        self.assertIn('["-m","tv_center.installed_languages"]',source)
        self.assertIn('source.addItem("Auto detect", "auto")',source)
        self.assertNotIn("Auto detect → English (UI default)",source)
        self.assertIn('requested_languages = {"en"}',source)
        self.assertIn("source.currentData() == \"auto\"",source)
        self.assertIn("Run model performance test".lower()[:6],"run model performance test".lower())
        self.assertIn("QMessageBox.Yes | QMessageBox.No,QMessageBox.No",source)
        self.assertIn("buttons.accepted.connect(apply_benchmark_choice)",source)
        self.assertIn("AISettings().update(update)",source)
        self.assertIn("tap.performance_snapshot()",source)
        self.assertIn("decoded phrases held, NOT dropped",source)

    def test_asr_translation_only_after_joined_sentence(self):
        from kaffeine_next import captions_overlay
        from tv_center import captions
        sidecar=inspect.getsource(captions_overlay.CaptionTap._decode)
        base=inspect.getsource(captions.decode_segment)
        self.assertIn("defer_asr_translation=not bool",sidecar)
        self.assertIn('defer_asr_translation and used=="local_asr"',base)
        self.assertIn("LiveSentenceJoiner(max_words=90,max_chunks=2)",
                      inspect.getsource(captions_overlay.CaptionTap.__init__))
        self.assertIn("translation_languages_ms",sidecar)


if __name__ == "__main__":
    unittest.main()
