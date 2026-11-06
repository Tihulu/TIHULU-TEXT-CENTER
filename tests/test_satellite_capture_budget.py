import unittest
from datetime import datetime, timedelta, timezone
from satellite_center.capture_budget import (
    plan_capture_budget, MAX_CAPTURE_SECONDS, IQ_BYTES_PER_SECOND,
)

class CaptureBudgetTests(unittest.TestCase):
    def setUp(self):
        self.aos = datetime(2026, 11, 7, 12, 0, tzinfo=timezone.utc)
        self.los = self.aos + timedelta(seconds=650)

    def test_full_image_window_can_exceed_old_480_and_browser_60(self):
        p = plan_capture_budget(self.aos,self.los,"meteor-m2-3",free_bytes=3_000_000_000)
        self.assertEqual(p["coverage"],"full-pass-attempt")
        self.assertEqual(p["capture_seconds"],656)
        self.assertEqual(p["estimated_bytes"],656*IQ_BYTES_PER_SECOND)
        self.assertEqual(MAX_CAPTURE_SECONDS,900)

    def test_disk_shortfall_is_honest_and_prevents_unusable_reception(self):
        p = plan_capture_budget(self.aos,self.los,"meteor-m2-3",free_bytes=600_000_000)
        self.assertTrue(p["feasible"])
        self.assertEqual(p["coverage"],"partial-pass")
        self.assertGreater(p["shortfall_seconds"],300)
        q = plan_capture_budget(self.aos,self.los,"meteor-m2-3",free_bytes=210_000_000)
        self.assertFalse(q["feasible"])
        self.assertEqual(q["estimated_bytes"],q["capture_seconds"]*IQ_BYTES_PER_SECOND)
        self.assertLess(q["capture_seconds"],q["minimum_useful_seconds"])

    def test_light_packet_and_short_modes_are_explicit(self):
        q = plan_capture_budget(self.aos,self.los,"iss-aprs",free_bytes=0)
        self.assertEqual(q["coverage"],"full-pass-attempt")
        self.assertEqual(q["estimated_bytes"],0)  # Packet text, not raw IQ
        s = plan_capture_budget(self.aos,self.los,"iss-sstv",free_bytes=3_000_000_000,goal="sample")
        self.assertEqual(s["capture_seconds"],60)
        self.assertEqual(s["coverage"],"partial-pass")

    def test_custom_recording_duration_and_type_limits(self):
        plan=plan_capture_budget(self.aos,self.los,"meteor-m2-4",free_bytes=3_000_000_000,
                                 requested_seconds=600)
        self.assertEqual(plan["capture_seconds"],600)
        self.assertEqual(plan["requested_seconds"],600)
        self.assertEqual(plan["coverage"],"partial-pass")
        self.assertGreater(plan["shortfall_seconds"],0)
        with self.assertRaisesRegex(ValueError,"8–900"):
            plan_capture_budget(self.aos,self.los,"meteor-m2-4",free_bytes=3_000_000_000,
                                requested_seconds=901)
        with self.assertRaisesRegex(ValueError,"at most 60"):
            plan_capture_budget(self.aos,self.los,"iss-sstv",free_bytes=3_000_000_000,
                                goal="sample",requested_seconds=90)

    def test_los_and_too_short_windows_rejected(self):
        with self.assertRaises(ValueError):
            plan_capture_budget(self.los,self.aos,"iss-sstv",free_bytes=3_000_000_000)
        short = plan_capture_budget(self.aos,self.aos+timedelta(seconds=20),"meteor-m2-3",
                                    free_bytes=3_000_000_000)
        self.assertFalse(short["feasible"])
        self.assertLess(short["capture_seconds"],120)

if __name__=="__main__":
    unittest.main()
