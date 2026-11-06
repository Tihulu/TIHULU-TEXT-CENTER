import math,unittest
from satellite_center.native_orbit import footprint_deg,sky_xy,mercator_xy,mercator_reverse,dateline_segments
class NativeMapMathTests(unittest.TestCase):
 def test_footprint(self):
  self.assertGreater(footprint_deg(410,0),footprint_deg(410,15))
  self.assertEqual(footprint_deg(0,0),0)
  self.assertRaises(ValueError,footprint_deg,-5)
 def test_sky(self):
  self.assertEqual(sky_xy(0,90),(0.0,-0.0))
  self.assertAlmostEqual(sky_xy(90,0)[0],1)
 def test_mercator_roundtrip(self):
  for lat,lon in [(50.87079,6.86761),(38.4237,27.1428)]:
   x,y=mercator_xy(lat,lon,7)
   q,p=mercator_reverse(x,y,7)
   self.assertAlmostEqual(q,lat,places=5)
   self.assertAlmostEqual(p,lon,places=5)
 def test_track_antimeridian(self):
  a=dateline_segments([{"lon":170},{"lon":179},{"lon":-179},{"lon":-170}])
  self.assertEqual([len(x) for x in a],[2,2])
