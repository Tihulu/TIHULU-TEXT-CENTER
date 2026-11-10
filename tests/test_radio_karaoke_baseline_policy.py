"""Offline contracts: language-safe karaoke, DLS/presenter switching, baseline.

No GPU, SDR, remote inference, or downloads in this test module.
"""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tv_center.radio_karaoke_router import (
    MusicSpeechRouter, karaoke_alignment_choice, QWEN_ALIGN_LANGUAGES)
from tv_center.ai_provision import install_baseline_models

ROOT=Path(__file__).resolve().parents[1]


class KaraokeLanguageRouterTests(unittest.TestCase):
    def test_turkish_and_unknown_language_always_whisper(self):
        for code in ("tr","ar","nl","und","","auto",None):
            with self.subTest(code=code):
                chosen=karaoke_alignment_choice(code,qwen_installed=True)
                self.assertEqual(chosen["engine"],"whisper")
                self.assertTrue(chosen["whisper_caption_independent"])
        self.assertNotIn("tr",QWEN_ALIGN_LANGUAGES)

    def test_qwen_only_when_both_supported_and_installed(self):
        for lang in ("en","de","ja","ko","fr"):
            self.assertEqual(karaoke_alignment_choice(lang,qwen_installed=True)[
                "engine"],"qwen")
            self.assertEqual(karaoke_alignment_choice(lang,qwen_installed=False)[
                "engine"],"whisper")
        self.assertEqual(karaoke_alignment_choice(
            "de-DE",qwen_installed=True,requested="whisper")["engine"],
            "whisper")

    def test_dls_only_does_not_force_music_mode_and_presenter_is_never_latched(self):
        route=MusicSpeechRouter()
        route.change_song(True)
        self.assertFalse(route.use_music_vocals(enabled=True))
        route.observe(matched=True,recognized_speech=True,chunk=2)
        self.assertTrue(route.use_music_vocals(enabled=True))
        route.observe(matched=False,recognized_speech=True,chunk=3)
        self.assertEqual(route.observe(
            matched=False,recognized_speech=True,chunk=4),"speech_whisper")
        self.assertFalse(route.use_music_vocals(enabled=True))
        # A new DLS song resets old verified lyric evidence only.
        route.change_song(True)
        self.assertFalse(route.matching_active)
        route.change_song(False)
        self.assertEqual(route.observe(
            matched=False,recognized_speech=True),"speech_whisper")

    def test_offline_worker_reports_selected_fallback_and_presenter_route(self):
        code=(ROOT/"tv_center/radio_ai.py").read_text()
        self.assertIn('karaoke_alignment_choice(',code)
        self.assertIn('"karaoke_alignment_candidate":alignment_option["engine"]',code)
        self.assertIn('"karaoke_alignment_engine":("qwen" if qwen_refinement else "whisper")',code)
        self.assertIn("qwen_future=qwen_pool.submit(",code)
        self.assertIn("qwen_pool.shutdown(wait=False",code)
        self.assertIn('"radio_content_route":radio_content_route',code)
        self.assertIn('song_router.use_music_vocals(',code)
        self.assertIn('song_router.observe(',code)


class BaselineInstallerTests(unittest.TestCase):
    def test_starter_does_not_downgrade_existing_cuda_model(self):
        code=(ROOT/"tv_center/ai_provision.py").read_text()
        self.assertIn("keep_saved=bool(saved_model",code)
        self.assertIn('if keep_saved',code)
        self.assertIn('"backend": (self.ai.values.get("backend"',code)

    def test_one_liner_defaults_to_baseline_and_no_ai_opt_out(self):
        shell=(ROOT/"kaffeine_next/install.sh").read_text()
        self.assertIn('if [[ "$MODE" != --no-ai ]]; then',shell)
        self.assertIn("tihulu-tv-center ai install-baseline",shell)
        self.assertIn('--no-ai) MODE=--no-ai',shell)
        self.assertNotIn("tihulu-tv-center ai install\n",shell)

    def test_baseline_is_profile_scoped_and_does_not_force_pi_gpu_models(self):
        code=(ROOT/"tv_center/ai_provision.py").read_text()
        self.assertIn("is_pi or ram < 7500",code)
        self.assertIn("vram>=12000 and ram>=16000",code)
        self.assertIn('"component":"qwen_aligner"',code)
        self.assertIn('"component":"sound_labels"',code)
        self.assertIn('"component":"speaker_embedding"',code)
        self.assertNotIn('os.environ["CUDA_VISIBLE_DEVICES"]',code)
        self.assertNotIn('subprocess.Popen(["rtl',code)


if __name__=="__main__":
    unittest.main()
