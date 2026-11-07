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

 def test_cursor_zoom_keeps_point_under_pointer(self):
  from satellite_center.native_orbit import cursor_anchored_zoom
  for lat,lon in [(50.87,6.87),(38.42,27.14),(30.0,179.4)]:
   old,new=5,8
   dx,dy=125,-93
   cx,cy=mercator_xy(lat,lon,old)
   before=mercator_reverse(cx+dx,cy+dy,old)
   updated=cursor_anchored_zoom(lat,lon,old,new,dx,dy)
   nx,ny=mercator_xy(*updated,new)
   after=mercator_reverse(nx+dx,ny+dy,new)
   self.assertAlmostEqual(before[0],after[0],places=5)
   self.assertAlmostEqual((before[1]-after[1]+180)%360-180,0,places=5)
 def test_invalid_native_zoom_rejected(self):
  from satellite_center.native_orbit import cursor_anchored_zoom
  self.assertRaises(ValueError,cursor_anchored_zoom,50,7,1,20,100,50)
