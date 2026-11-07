import math
import unittest
from satellite_center.native_tracking import (
    mercator_pixel,mercator_unproject,sky_project,split_dateline,footprint_radius_km
)

class NativeTrackingGeometryTests(unittest.TestCase):
    def test_web_mercator_roundtrip(self):
        for lat,lon in [(50.938,6.96),(38.5,27.1),(-33.7,151.2),(0,179.5)]:
            x,y=mercator_pixel(lat,lon,6)
            a,b=mercator_unproject(x,y,6)
            self.assertAlmostEqual(a,lat,places=5)
            self.assertAlmostEqual(b,lon,places=5)
    def test_sky_cardinals_and_horizon(self):
        self.assertAlmostEqual(sky_project(0,90,400,400)[0],200)
        north=sky_project(0,0,400,400)
        east=sky_project(90,0,400,400)
        self.assertLess(north[1],200)
        self.assertGreater(east[0],200)
    def test_anti_meridian_split(self):
        segments=split_dateline([(1,175),(2,179),(3,-179),(4,-175),(5,-170)])
        self.assertEqual(len(segments),2)
        self.assertTrue(all(len(seg)>=2 for seg in segments))
    def test_geometric_footprint(self):
        self.assertGreater(footprint_radius_km(400),0)
        self.assertLess(footprint_radius_km(400,20),footprint_radius_km(400,0))
