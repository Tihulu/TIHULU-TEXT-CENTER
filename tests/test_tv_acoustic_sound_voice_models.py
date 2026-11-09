"""Offline-only tests for independently switchable acoustic labels."""
import ast
from pathlib import Path
import tempfile
import unittest

from tv_center.audio_classifiers import (
    AudioLabels, classify_event_scores, voice_prediction)
from kaffeine_next.caption_timing import CaptionConfig


class AcousticClassifiersTests(unittest.TestCase):
    def test_sound_tags_only_from_real_model_scores(self):
        scores=[
            {"label":"Music","confidence":0.91},
            {"label":"Humming","confidence":0.88},
            {"label":"Applause","confidence":0.40},
            {"label":"Speech","confidence":0.99},
            {"label":"Hum","confidence":0.25},
        ]
        self.assertEqual(
            [x["type"] for x in classify_event_scores(scores)],
            ["music","hum"])
        self.assertEqual(classify_event_scores([{"label":"Noise",
                                                "confidence":0.2}]),[])
        self.assertEqual(classify_event_scores([{"label":"Music",
                                                "confidence":"high"}]),[])

    def test_perceived_voice_categories_need_strong_confidence(self):
        self.assertEqual(voice_prediction([0.97,0.02,0.01])["voice_type"],
                         "child")
        self.assertEqual(voice_prediction([0.05,0.93,0.02])["voice_type"],
                         "female")
        self.assertEqual(voice_prediction([0.01,0.03,0.96])["voice_type"],
                         "male")
        self.assertIsNone(voice_prediction([0.34,0.33,0.33]))
        self.assertIsNone(voice_prediction([-1,1,1]))
        self.assertIsNone(voice_prediction([]))
        # Female speech can acoustically resemble a child's voice.
        # Ambiguous or age-contradictory estimates are left unlabeled.
        self.assertIsNone(voice_prediction([0.91,0.06,0.03]))
        self.assertIsNone(voice_prediction([0.98,0.01,0.01],age_score=0.32))
        self.assertEqual(voice_prediction(
            [0.98,0.01,0.01],age_score=0.09)["voice_type"],"child")

    def test_no_model_load_or_download_for_local_status(self):
        with tempfile.TemporaryDirectory() as folder:
            market=AudioLabels(Path(folder))
            self.assertFalse(market.installed("voice"))
            self.assertFalse(market.installed("sound"))
            with self.assertRaises(ValueError):
                market.model_dir("unknown")

    def test_render_voice_types_and_sound_events_independently(self):
        result={"source":"local_asr","original":"Merhaba",
                "speaker_index":1,"speaker_label":"[Speaker 1 · clip]",
                "voice_type":"female","voice_type_confidence":0.95,
                "sound_events":[{"type":"music","confidence":0.96,"source":"AST AudioSet"},
                                {"type":"hum","confidence":0.90,"source":"AST AudioSet"}]}
        labels_only=CaptionConfig(speaker_enabled=True,
            show_speaker_numbers=False,show_voice_types=False,
            show_sound_events=True,target_languages=("en",)).validate()
        first=labels_only.render(result)
        self.assertIn("[Music]",first)
        self.assertIn("[Humming]",first)
        self.assertNotIn("Speaker",first)
        self.assertNotIn("Weibliche",first)
        voice_only=CaptionConfig(speaker_enabled=True,
            show_speaker_numbers=False,show_voice_types=True,
            show_sound_events=False).validate()
        second=voice_only.render(result)
        self.assertIn("Weibliche Stimme?",second)
        self.assertNotIn("[Music]",second)
        self.assertNotIn("Speaker",second)
        english=CaptionConfig(source="en",speaker_enabled=True,
            show_speaker_numbers=False,show_voice_types=True,
            show_sound_events=True,show_translation=False).validate()
        self.assertIn("Female voice?",english.render(result))
        turkish=CaptionConfig(source="tr",speaker_enabled=True,
            show_speaker_numbers=False,show_voice_types=True,
            show_sound_events=True,show_translation=False).validate()
        self.assertIn("Kadın sesi?",turkish.render(result))
        self.assertIn("[Müzik]",turkish.render(result))
        result["voice_type_confidence"]=0.4
        self.assertNotIn("Weibliche Stimme?",voice_only.render(result))

    def test_always_off_by_default(self):
        config=CaptionConfig()
        self.assertFalse(config.separate_overlapping_voices)
        self.assertFalse(config.show_sound_events)
        self.assertFalse(config.show_voice_types)

    def test_caption_ui_installer_requires_explicit_user_consent(self):
        source=(Path(__file__).resolve().parents[1]/
                "kaffeine_next/captions_overlay.py").read_text("utf-8")
        ast.parse(source)
        self.assertIn("install_classifier",source)
        self.assertIn("noncommercial_acknowledged",source)
        self.assertIn("QMessageBox.Yes | QMessageBox.No",source)
        self.assertIn("event_install_button.setEnabled(False)",source.replace(
            "button.setEnabled(False)","event_install_button.setEnabled(False)"))
        self.assertIn("classifier_install_queue.get_nowait()",source)


if __name__=="__main__":
    unittest.main()
