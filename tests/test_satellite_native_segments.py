import threading
import unittest
from datetime import datetime, timedelta, timezone
from types import MethodType
from satellite_center.native_segments import (
    capture_parts, format_native_countdown, total_wall_seconds,
)
from satellite_center.__main__ import Station

class NativeSegmentedCaptureTests(unittest.TestCase):
    def test_300_seconds_becomes_two_150_second_surveys_with_real_gaps(self):
        parts=capture_parts(300)
        self.assertEqual([p["duration_seconds"] for p in parts],[150,150])
        self.assertEqual([p["offset_seconds"] for p in parts],[0,152])
        self.assertEqual(total_wall_seconds(parts),302)

    def test_full_length_native_session_split_and_countdown(self):
        parts=capture_parts(900)
        self.assertEqual(len(parts),5)
        self.assertEqual([p["duration_seconds"] for p in parts],[180]*5)
        self.assertEqual(total_wall_seconds(parts),908)
        self.assertEqual(format_native_countdown(90061),"1d 01h 01m 01s")

    def test_invalid_lengths_rejected_before_touching_radio(self):
        for seconds in (-1,0,7,901,1.5):
            with self.subTest(seconds=seconds):
                with self.assertRaises(ValueError):
                    capture_parts(seconds)
        with self.assertRaises(ValueError):
            capture_parts(300,gap_seconds=999)

    def _station(self,fail_after=None):
        station=Station.__new__(Station)
        station.lock=threading.RLock()
        station.wake=threading.Event()
        start=datetime.now(timezone.utc)+timedelta(minutes=5)
        station.predicted={"pass-1":{"aos":start.isoformat(),
                     "los":(start+timedelta(minutes=10)).isoformat()}}
        station.jobs=[]
        station.save_jobs=lambda:None
        def schedule(this,pass_id,profile,mode,run_at=None,seconds=None,**kwargs):
            if fail_after is not None and len(this.jobs)>=fail_after:
                raise ValueError("Injected second part failure")
            value={"id":f"native-{len(this.jobs)+1}","run_at":run_at,
                   "capture_seconds":seconds,"segment_group":kwargs.get("segment_group"),
                   "segment_index":kwargs.get("segment_index"),"segment_count":kwargs.get("segment_count")}
            this.jobs.append(value)
            return dict(value)
        station.schedule=MethodType(schedule,station)
        return station,start

    def test_schedule_series_produces_two_calendar_entries(self):
        station,start=self._station()
        r=station.schedule_series("pass-1","meteor","survey",start.isoformat(),300)
        self.assertEqual(r["scheduled_count"],2)
        self.assertEqual(r["unrecorded_gap_seconds"],2)
        self.assertEqual([v["capture_seconds"] for v in r["scheduled"]],[150,150])
        self.assertEqual(
            (datetime.fromisoformat(r["scheduled"][1]["run_at"])-
             datetime.fromisoformat(r["scheduled"][0]["run_at"])).total_seconds(),152)

    def test_native_multi_part_rolls_back_all_on_failure(self):
        station,start=self._station(fail_after=1)
        with self.assertRaisesRegex(ValueError,"Injected"):
            station.schedule_series("pass-1","meteor","survey",start.isoformat(),300)
        self.assertEqual(station.jobs,[])

if __name__=="__main__":
    unittest.main()
