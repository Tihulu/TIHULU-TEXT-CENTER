import unittest
from satellite_center.native_orbit import mercator_xy
try:
 from satellite_center.native_osm_tiles import tile_url,visible_tiles
except ImportError:
 tile_url=visible_tiles=None
class NativeOSMTileMathTests(unittest.TestCase):
 def test_base_map_projection(self):
  x,y=mercator_xy(0,0,2);self.assertEqual((x,y),(512,512))
 @unittest.skipIf(tile_url is None,"QtNetwork optional on non-Debian CI")
 def test_tiles_only_current_view_and_https(self):
  data=visible_tiles(50.87,6.86,5,850,550)
  self.assertTrue(data);self.assertLessEqual(len(data),48)
  self.assertEqual(len(data),len(set(data)))
  self.assertTrue(all(tile_url(*t).startswith("https://tile.openstreetmap.org/") for t in data))
  self.assertRaises(ValueError,tile_url,12,-1,0)
