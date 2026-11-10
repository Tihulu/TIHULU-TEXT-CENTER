"""Live TV auto Teletext/Whisper tests. No tuner, Internet or real ASR weights."""
import unittest
from pathlib import Path

from kaffeine_next.teletext_match import TeletextAudit, compare_text
from kaffeine_next.caption_timing import CaptionConfig

ROOT=Path(__file__).resolve().parents[1]
OVERLAY=(ROOT/"kaffeine_next/captions_overlay.py").read_text(encoding="utf-8")
CAPTIONS=(ROOT/"tv_center/captions.py").read_text(encoding="utf-8")

A="Heute berichtet die Moderatorin über das Wetter in Köln und Umgebung"
B="Der Sprecher bespricht die aktuellen Nachrichten aus Berlin und Hamburg"
C="Wir sprechen heute ausführlich über Politik und Kultur in Deutschland"
D="Ein ganz anderes Gespräch über das neue Auto und die Reparaturkosten"


class TeletextSpeechRecoveryTests(unittest.TestCase):
    def test_matching_same_language_marks_teletext_synced(self):
        audit=TeletextAudit()
        audit.mark_clip()
        self.assertTrue(audit.needs_probe())
        self.assertEqual(audit.observe(A,A,"de","de"),"matching")
        self.assertEqual(audit.status,"TELETEXT · SYNCED")
        self.assertFalse(audit.prefer_asr)

    def test_timestamps_or_different_language_cannot_prove_match(self):
        self.assertEqual(compare_text(A,A,"de","tr"),"unknown")
        self.assertEqual(compare_text(A,B,"und","und"),"unknown")
        self.assertEqual(compare_text("Hallo", "Hallo", "de","de"),"unknown")
        audit=TeletextAudit()
        for _ in range(6):
            audit.mark_clip()
            audit.observe(A,B,"de","tr")
        self.assertFalse(audit.prefer_asr)

    def test_three_conflicts_then_whisper_fallback(self):
        audit=TeletextAudit()
        for _ in range(3):
            audit.mark_clip()
            audit.observe(A,D,"de","de")
        self.assertTrue(audit.prefer_asr)
        self.assertEqual(audit.status,"WHISPER · AUTO FALLBACK")

    def test_same_capture_delayed_text_checked_before_mismatch(self):
        audit=TeletextAudit()
        audit.mark_clip()
        audit.observe(A,B,"de","de")
        audit.mark_clip()
        # This clip's TELEtext matches the preceding verified speech,
        # while the current speech has advanced. Don't call false mismatch.
        self.assertEqual(audit.observe(B,C,"de","de"),"delayed")
        self.assertEqual(audit.status,"TELETEXT · DELAY CHECK")
        self.assertFalse(audit.prefer_asr)

    def test_recovery_requires_two_new_matching_audio_probes(self):
        audit=TeletextAudit(probe_interval=2)
        for _ in range(3):
            audit.mark_clip()
            audit.observe(A,D,"de","de")
        self.assertTrue(audit.prefer_asr)
        audit.mark_clip()
        self.assertEqual(audit.observe(B,B,"de","de"),"matching")
        self.assertTrue(audit.prefer_asr)
        audit.mark_clip()
        self.assertEqual(audit.observe(C,C,"de","de"),"recovered")
        self.assertFalse(audit.prefer_asr)
        self.assertEqual(audit.status,"TELETEXT · SYNCED")

    def test_probes_continue_after_initial_success(self):
        audit=TeletextAudit(maximum=4,probe_interval=3)
        observed=[]
        for _ in range(8):
            audit.mark_clip()
            observed.append(audit.needs_probe())
            if audit.needs_probe():
                audit.observe(A,A,"de","de")
        self.assertEqual(observed,[True,True,True,True,False,True,False,False])
        audit.missing()
        self.assertTrue(audit.prefer_asr)
        self.assertEqual(audit.last_verdict,"missing")

    def test_new_program_resets_caption_audit_and_language(self):
        audit=TeletextAudit()
        for _ in range(3):
            audit.mark_clip()
            audit.observe(A,D,"de","de")
        audit.reset()
        self.assertEqual(audit.attempts,0)
        self.assertFalse(audit.prefer_asr)
        self.assertEqual(audit.status,"TELETEXT · CHECKING")

    def test_config_exposes_independent_teletext_and_speech_language(self):
        opts=CaptionConfig(mode="auto",source="auto",teletext_language="de",
                           target="en",target_languages=("en","tr")).options()
        self.assertEqual(opts["teletext_language"],"de")
        self.assertEqual(opts["targets"],("en","tr"))

    def test_live_decoder_shadow_uses_same_selected_ts_and_no_second_asr(self):
        for statement in (
            "auto_teletext_recovery: bool = False",
            'if auto_teletext_recovery and mode=="asr":',
            "teletext_from_clip(p,shadow_page,service_id,teletext_pid)",
            '"teletext_shadow":teletext_shadow',
        ):
            self.assertIn(statement,CAPTIONS)

    def test_tv_auto_mode_refresh_recovery_status_and_translation(self):
        for statement in (
            "self.teletext_audit.mark_clip()",
            "self.teletext_audit.needs_probe()",
            "auto_teletext_recovery=bool(",
            "shadow=result.pop(\"teletext_shadow\",None)",
            'if verdict=="switched":',
            '"teletext_status"',
            "TELETEXT · MISMATCH",
            "WHISPER · AUTO FALLBACK",
            "teletext_speech_status.setText(",
            "if enabled:",
            'result["translations"]={}',
            "if options.get(\"program_epoch\") != self.program_epoch:",
        ):
            self.assertIn(statement,OVERLAY if statement!="TELETEXT · MISMATCH" else
                          (ROOT/"kaffeine_next/teletext_match.py").read_text(encoding="utf-8"))


if __name__=="__main__":
    unittest.main()
