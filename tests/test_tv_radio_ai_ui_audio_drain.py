"""Regression tests for radio AI IN/OUT controls, lyrics, and read-ahead capture.

All tests are offline. No GPU, receiver, remote lyrics lookup or model import.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
import unittest

from tv_center.radio_capture import BoundedRadioCapture
from tv_center.installed_languages import catalog

ROOT=Path(__file__).resolve().parents[1]


class RadioAIUXRegressionTests(unittest.TestCase):
    def test_reader_keeps_six_second_pcm_windows_and_one_second_overlap(self):
        rate=40
        data=b"".join(bytes([i,i])*(rate*seconds)
                      for i,seconds in [(1,6),(2,5),(3,5)])
        capture=BoundedRadioCapture(
            BytesIO(data),samples_per_second=rate,max_windows=3,
            queue_size=4).start()
        self.assertTrue(capture.finished.wait(2))
        windows=[capture.next(),capture.next(),capture.next()]
        self.assertEqual([w[0] for w in windows],[0,1,2])
        self.assertTrue(all(len(w[1])==6*rate*2 for w in windows))
        self.assertEqual(capture.next(),None)
        self.assertEqual(capture.dropped_windows,0)
        capture.stop()

    def test_under_overload_only_old_ai_windows_are_dropped(self):
        rate=40
        data=b"x"*(6*rate*2)+b"y"*(7*5*rate*2)
        capture=BoundedRadioCapture(BytesIO(data),samples_per_second=rate,
                                    max_windows=8,queue_size=3).start()
        self.assertTrue(capture.finished.wait(2))
        observed=[capture.next()[0] for _ in range(3)]
        self.assertEqual(observed,[5,6,7])
        self.assertEqual(capture.dropped_windows,5)
        self.assertIsNone(capture.next())
        capture.stop()

    def test_catalog_shares_tv_model_market_sources(self):
        found=catalog(installed_pairs=[
            {"source":"de","target":"en"},
            {"source":"en","target":"tr"}],
            nllb_installed=True,madlad_installed=False,
            deepl_configured=False)
        by_code={row["code"]:row for row in found["languages"]}
        self.assertIn("Argos",by_code["en"]["engines"])
        self.assertTrue(any("NLLB" in engine
                        for engine in by_code["tr"]["engines"]))
        self.assertTrue(found["nllb_present"])
        self.assertFalse(found["deepl_online_key_configured"])

    def test_radio_ui_has_shared_in_out_and_visible_caption_surface(self):
        source=(ROOT/"kaffeine_next/native_radio_tab.h").read_text()
        self.assertIn('"ai-radio-languages"',source)
        self.assertIn("selectedRadioTargets() const",source)
        self.assertIn("const QStringList targets=selectedRadioTargets()",source)
        self.assertIn("const QStringList dests=selectedRadioTargets()",source)
        self.assertIn("radioCanvasCaption_=new QLabel(radioCanvas_)",source)
        self.assertNotIn("showRadioCanvasCaption(current,true)",source)
        self.assertIn("showKaraokeLine(cue);",source)
        self.assertIn("showRadioCanvasCaption(cue.text)",source)
        self.assertIn("QSignalBlocker block(installedTargets_)",source)
        self.assertIn("Advanced · audio cache, timing & diagnostics",source)
        self.assertIn("Advanced · lyrics source, timing, import",source)
        self.assertIn("ai_audio_windows_dropped",source)
        self.assertNotIn("radioCanvas_->setText(cue.text",source)

    def test_radio_backend_preserves_music_as_nontext_status(self):
        code=(ROOT/"tv_center/radio_ai.py").read_text()
        # Lower AI captions are the raw Whisper ASR stream, never a
        # potentially fuzzy/low-threshold lyric substitution.
        self.assertNotIn('original=lyric_match["text"]',code)
        self.assertIn('preferred_lyric_text=(lyric_match.get("text","")',code)
        self.assertIn('source_word_timed=bool(detection.get("asr_words"))',code)
        self.assertIn('prefer_readable=True',code)
        self.assertIn('and lyric_match else "")',code)
        self.assertNotIn('original="[music]"',code)
        self.assertIn('"music_detected":False',code)
        self.assertIn('"speech_preserved_when_lyrics_unmatched"',code)
        self.assertIn("music=music_for_matching,",code)
        self.assertIn("plain_matcher is not None and karaoke_enabled",code)
        self.assertIn("BoundedRadioCapture(ffmpeg.stdout",code)
        self.assertIn('"ai_audio_windows_dropped":capture.dropped_windows',code)
        self.assertIn("capture_index*5",code)
        self.assertIn("sentence_joiner.reset()",code)
        commands=(ROOT/"tv_center/__main__.py").read_text()
        self.assertIn('"ai-radio-languages"',commands)
        self.assertIn('"speech_languages"',commands)


if __name__=="__main__":
    unittest.main()
