"""Regression for additive sound labels and true audio-verified Teletext fallback.

Synthetic phrases only; no installed sound model, tuner or network required.
"""
import unittest
from tv_center.sound_event_captions import (
    sound_prefix, decorate_caption, decorate_result)
from kaffeine_next.teletext_match import compare_text, TeletextAudit


MUSIC=[{"type":"music","confidence":0.97,"source":"AST AudioSet"}]
APPLAUSE=[{"type":"applause","confidence":0.91,"source":"AST AudioSet"}]


class AdditiveSoundLabels(unittest.TestCase):
    def test_label_and_real_speech_are_kept_together(self):
        english="It starts here, and we are still speaking."
        self.assertEqual(decorate_caption(english,MUSIC,"en"),
                         "[Music] "+english)
        self.assertEqual(decorate_caption(
            "Das ist unser Text",MUSIC,"de"),"[Musik] Das ist unser Text")
        self.assertEqual(decorate_caption(
            "Konuşma devam ediyor",MUSIC,"tr"),
            "[Müzik] Konuşma devam ediyor")

    def test_sound_label_is_display_only_after_translation(self):
        original={"original":"I can hear your voice","raw_asr_original":"I can hear your voice",
                  "source_language":"en","translations":{
                      "de":"Ich höre deine Stimme","tr":"Sesini duyabiliyorum"},
                  "sound_events":MUSIC,"word_timing_source":"Whisper timed","source":"local_asr"}
        decorated=decorate_result(original,True)
        self.assertEqual(original["original"],"I can hear your voice")
        self.assertEqual(original["translations"]["de"],"Ich höre deine Stimme")
        self.assertEqual(decorated["original"],
                         "[Music] I can hear your voice")
        self.assertEqual(decorated["translations"]["de"],
                         "[Musik] Ich höre deine Stimme")
        self.assertEqual(decorated["translations"]["tr"],
                         "[Müzik] Sesini duyabiliyorum")
        self.assertEqual(decorated["word_timing_source"],"Whisper timed")

    def test_detector_backed_sound_only_has_no_fake_lyrics(self):
        result={"original":"","translations":{},
                "source_language":"en","target_languages":["de","tr"],
                "source":"local_asr","sound_events":APPLAUSE,
                "word_timing_source":"estimated","words":[{"text":"fake"}]}
        decorated=decorate_result(result,True)
        self.assertEqual(decorated["original"],"[Applause]")
        self.assertEqual(decorated["translations"]["tr"],"[Alkış]")
        self.assertEqual(decorated["source"],"acoustic_event")
        self.assertEqual(decorated["words"],[])
        self.assertIsNone(decorated["word_timing_source"])

    def test_uncertain_detector_labels_do_not_change_speech(self):
        utterance="The programme continues."
        uncertain=[{"type":"music","confidence":0.79,"source":"AST AudioSet"}]
        self.assertEqual(decorate_caption(utterance,uncertain,"en"),utterance)
        self.assertEqual(decorate_caption(utterance,[
            {"type":"music","confidence":.99,"source":"guessed"}],"en"),utterance)
        self.assertEqual(decorate_caption(utterance,[],"en"),utterance)
        self.assertEqual(decorate_result({"original":utterance},False)["original"],
                         utterance)

    def test_radio_sound_labels_are_opt_in_and_dont_replace_asr(self):
        from pathlib import Path
        root=Path(__file__).resolve().parents[1]
        radio=(root/"tv_center/radio_ai.py").read_text("utf-8")
        ui=(root/"kaffeine_next/native_radio_tab.h").read_text("utf-8")
        for token in ('--sound-labels','sound_labels: bool=False',
                      "Optional offline AST AudioSet sound model not installed",
                      "rendered_original[:1800]",
                      "rendered_translations",
                      "if original else original",
                      "sound_labels=requested_labels"):
            with self.subTest(token=token):
                self.assertIn(token,radio)
        self.assertIn('QLatin1String("radioSoundLabelsEnabled"),false',ui)
        self.assertIn('QStringLiteral("sound_labels")',ui)
        self.assertIn('options<<QLatin1String("--sound-labels")',ui)

    def test_two_real_events_keep_transcript(self):
        words="Real dialogue"
        joined=decorate_caption(words,MUSIC+APPLAUSE,"en")
        self.assertEqual(joined,"[Music] [Applause] Real dialogue")


class TeletextVsLiveSpeech(unittest.TestCase):
    tt="The village is getting ready for the celebration this weekend"
    asr="The village is getting ready for the celebration this weekend"

    def test_same_clip_language_code_aliases_are_accepted(self):
        self.assertEqual(compare_text(self.tt,self.asr,"deu","de"),"matching")
        self.assertEqual(compare_text(self.tt,self.asr,"ger","de"),"matching")
        self.assertEqual(compare_text(self.tt,self.asr,"deu_Latn","de"),"matching")

    def test_synchronized_content_not_just_pts(self):
        unrelated="The bridge is closed and everyone must take another road instead"
        self.assertEqual(compare_text(self.tt,unrelated,"eng","en"),
                         "conflicting")
        self.assertEqual(compare_text(self.tt,unrelated,"deu","en"),
                         "unknown")
        self.assertEqual(compare_text(self.tt,"yes","eng","en"),"unknown")

    def test_three_verified_conflicts_trigger_whisper(self):
        monitor=TeletextAudit(required_conflicts=3)
        unrelated="The bridge is closed and everyone must take another road instead"
        statuses=[monitor.observe(self.tt,unrelated,"eng","en") for _ in range(3)]
        self.assertEqual(statuses[-1],"switched")
        self.assertTrue(monitor.prefer_asr)
        self.assertEqual(monitor.status,"WHISPER · AUTO FALLBACK")

    def test_two_separate_recoveries_restore_teletext(self):
        monitor=TeletextAudit(required_conflicts=1,required_recoveries=2)
        other="Please move away from the station while repairs are taking place"
        monitor.observe(self.tt,other,"eng","en")
        self.assertTrue(monitor.prefer_asr)
        self.assertEqual(monitor.observe(self.tt,self.asr,"eng","en"),"matching")
        self.assertTrue(monitor.prefer_asr)
        self.assertEqual(monitor.observe(self.tt,self.asr,"eng","en"),"recovered")
        self.assertFalse(monitor.prefer_asr)
        self.assertEqual(monitor.status,"TELETEXT · SYNCED")

    def test_persistent_one_clip_lag_uses_whisper_not_stale_teletext(self):
        check=TeletextAudit(required_conflicts=3)
        phrases=[
            "Green satellites circle above tall silver buildings tonight",
            "Three bicycles crossed the narrow bridge before sunrise today",
            "Scientists studied six marine species across distant coral reefs",
            "Gardeners collected ripe yellow peaches near the old railway",
            "Researchers measured rainfall over the southern mountains again",
        ]
        self.assertEqual(check.observe(phrases[0],phrases[1],"en","en"),
                         "conflicting")
        self.assertEqual(check.observe(phrases[1],phrases[2],"en","en"),
                         "delayed")
        self.assertEqual(check.observe(phrases[2],phrases[3],"en","en"),
                         "delayed")
        self.assertEqual(check.observe(phrases[3],phrases[4],"en","en"),
                         "switched")
        self.assertTrue(check.prefer_asr)
        self.assertIn("PTS",check.last_reason)

    def test_silent_empty_or_unconfirmed_language_is_not_false_mismatch(self):
        monitor=TeletextAudit(required_conflicts=1)
        self.assertEqual(monitor.observe(self.tt,"","eng","en"),"unknown")
        self.assertFalse(monitor.prefer_asr)
        self.assertEqual(monitor.observe(self.tt,self.asr,"und","en"),"unknown")
        self.assertFalse(monitor.prefer_asr)


if __name__=="__main__":
    unittest.main()
