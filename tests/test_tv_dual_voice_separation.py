"""No-network, no-GPU tests for REAL independent two-voice captions."""
from __future__ import annotations
import ast
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from kaffeine_next.caption_timing import CaptionConfig, SpeakerLineHistory
from tv_center.overlap_separation import (
    accept_two_transcripts, OverlapSeparation, MODEL_FILES)


def details(text,lang="tr",start=0.2):
    words=text.split()
    return {"text":text,"language":lang,
            "words":[{"text":w,"start":start+i*0.32,
                      "end":start+i*0.32+0.27}
                     for i,w in enumerate(words)]}


class SourceSeparationTests(unittest.TestCase):
    def test_only_two_genuine_independent_word_timed_transcripts(self):
        result=accept_two_transcripts([
            details("Merhaba iyi günler",start=0.05),
            details("Seni duyamıyorum yine",start=0.05)])
        self.assertEqual(len(result),2)
        self.assertEqual([x["speaker_index"] for x in result],[1,2])
        self.assertNotEqual(result[0]["original"],result[1]["original"])
        self.assertIsNone(accept_two_transcripts([
            details("Aynı cümleyi söylüyor",start=0.05),
            details("Aynı cümleyi söylüyor",start=0.05)]))
        self.assertIsNone(accept_two_transcripts([
            details("Merhaba iyi günler"),
            {"text":"İkinci sahte cümle","language":"tr","words":[]}]))
        self.assertIsNone(accept_two_transcripts([
            details("Merhaba iyi günler"),
            details("x")]))
        self.assertIsNone(accept_two_transcripts([details("tek ses")]))

    def test_does_not_download_or_import_model_on_status(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch("subprocess.run",
                       side_effect=AssertionError("never scan at startup")):
                model=OverlapSeparation(Path(directory)/"sep")
                self.assertFalse(model.installed())
        self.assertEqual(len(MODEL_FILES),4)

    def test_sepformer_download_runtime_keeps_compatible_hub_major(self):
        source=(Path(__file__).resolve().parents[1]/
                "tv_center/overlap_separation.py").read_text(encoding="utf8")
        ast.parse(source)
        self.assertIn("huggingface_hub>=0.26,<1.0",source)
        self.assertIn("HF_HUB_DISABLE_XET",source)
        self.assertIn("SepFormer model download failed at",source)

    def test_actual_two_voice_subtitles_render_in_two_lines(self):
        branches=accept_two_transcripts([
            details("Merhaba nasılsın"),
            details("Bu çok önemli")])
        branches[0]["translations"]={"en":"Hello how are you"}
        branches[1]["translations"]={"en":"This is important"}
        result={"original":"Mixed and garbled words",
                "source":"local_asr","overlap_lines":branches}
        config=CaptionConfig(
            speaker_enabled=True,show_speaker_numbers=False,
            separate_overlapping_voices=True,
            show_original=True,show_translation=False).validate()
        actual=config.render(result)
        self.assertEqual(len(actual.splitlines()),2)
        self.assertIn("Merhaba nasılsın",actual)
        self.assertIn("Bu çok önemli",actual)
        self.assertNotIn("Voice",actual)
        self.assertNotIn("Speaker",actual)
        labeled=CaptionConfig(
            speaker_enabled=True,show_speaker_numbers=True,
            separate_overlapping_voices=True,
            show_original=True,show_translation=True,
            target_languages=("en",)).validate()
        shown=labeled.render(result)
        self.assertIn("[Voice 1",shown)
        self.assertIn("[Voice 2",shown)
        self.assertIn("[EN] Hello how are you",shown)
        self.assertIn("[EN] This is important",shown)

    def test_speaker_change_new_line_without_identity_label(self):
        history=SpeakerLineHistory()
        config=CaptionConfig(speaker_enabled=True,
            show_speaker_numbers=False,break_speaker_lines=True).validate()
        first={"source":"local_asr","speaker_index":1}
        second={"source":"local_asr","speaker_index":2}
        self.assertEqual(history.compose(first,"Merhaba",config,100,epoch=1),
                         "Merhaba")
        self.assertEqual(history.compose(second,"Seni duydum",config,101,epoch=1),
                         "Merhaba\nSeni duydum")
        # Don't pair speakers across distinct channel/program epochs.
        self.assertEqual(history.compose(first,"Merhaba",config,102,epoch=2),
                         "Merhaba")
        self.assertEqual(history.compose(second,"Geç cevap",config,120,epoch=2),
                         "Geç cevap")

    def test_speaker_type_and_sound_tags_are_independent(self):
        config=CaptionConfig(
            show_speaker_numbers=False,show_voice_types=True,
            show_sound_events=True,speaker_enabled=True,
            target_languages=("en",)).validate()
        result={"original":"Günaydın","source":"local_asr",
                "speaker_index":1,"voice_type":"female",
                "voice_type_confidence":0.92,
                "sound_events":[{"type":"music","confidence":0.91,"source":"AST AudioSet"},
                                {"type":"hum","confidence":0.81,"source":"AST AudioSet"}]}
        shown=config.render(result)
        self.assertIn("Weibliche Stimme?",shown)
        self.assertIn("[Music]",shown)
        self.assertIn("[Humming]",shown)
        self.assertNotIn("[Speaker",shown)
        # Weak classification is NOT guessed.
        result["voice_type_confidence"]=0.3
        self.assertNotIn("Weibliche",config.render(result))
        result["sound_events"][0]["confidence"]=0.15
        self.assertNotIn("[Music]",config.render(result))

    def test_ui_does_not_implicitly_enable_heavy_separation(self):
        source=(Path(__file__).resolve().parents[1]/
                "kaffeine_next/captions_overlay.py").read_text(encoding="utf8")
        ast.parse(source)
        self.assertIn("overlap_enabled.setChecked(False)",source)
        self.assertIn("show_speaker_numbers=speaker_numbers.isChecked()",source)
        self.assertIn("separate_overlapping_voices=overlap_enabled.isChecked()",source)
        self.assertIn("owner_install",source)
        self.assertIn('QMessageBox.Yes | QMessageBox.No,QMessageBox.No',source)
        self.assertIn("overlap_separation=(",source)


if __name__=="__main__":
    unittest.main()
