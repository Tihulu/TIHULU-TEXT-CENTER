"""Window line-of-sight is a geometry estimate, not a received signal."""
import unittest
from satellite_center.window_visibility import (
    validate_window, inside_window, summarize_window)


class WindowGeometryTests(unittest.TestCase):
    def setUp(self):
        self.view={"az":300,"half":30,"min":10,"max":40}

    def test_compass_wrap_and_sector_edges(self):
        self.assertTrue(inside_window(300,20,self.view))
        self.assertTrue(inside_window(270,20,self.view))
        self.assertTrue(inside_window(330,20,self.view))
        self.assertFalse(inside_window(269.9,20,self.view))
        self.assertFalse(inside_window(300,45,self.view))
        wrapped={"az":355,"half":20,"min":5,"max":60}
        self.assertTrue(inside_window(5,20,wrapped))
        self.assertFalse(inside_window(40,20,wrapped))

    def test_window_duration_and_rating(self):
        samples=[(float(t),300,20) for t in range(0,241,10)]
        report=summarize_window(samples,self.view)
        self.assertEqual(report["status"],"good_geometry")
        self.assertEqual(report["seconds"],240)
        self.assertEqual(report["peak_elevation"],20.0)
        self.assertEqual(report["segments"],[{"start":0,"end":240000}])

    def test_disjoint_segments_never_count_hidden_time(self):
        samples=[(0,300,20),(10,300,21),(20,170,60),
                 (200,300,25),(210,300,26)]
        result=summarize_window(samples,self.view)
        self.assertEqual(result["seconds"],20)
        self.assertEqual(result["status"],"very_short")
        self.assertEqual(len(result["segments"]),2)

    def test_no_window_overlap_not_a_signal_failure(self):
        report=summarize_window([(0,90,20),(10,120,25)],self.view)
        self.assertEqual(report["status"],"outside")
        self.assertEqual(report["seconds"],0)
        self.assertIsNone(report["peak_elevation"])
        self.assertIn("predicted samples",report["note"])

    def test_invalid_window_is_rejected(self):
        for item in (
            {"az":300,"half":0,"min":10,"max":40},
            {"az":300,"half":30,"min":40,"max":10},
            {"az":float("nan"),"half":30,"min":10,"max":40},
            {"az":300,"half":30,"min":10},
            {"az":360,"half":30,"min":10,"max":40},
        ):
            with self.assertRaises(ValueError):
                validate_window(item)


if __name__=="__main__":
    unittest.main()
