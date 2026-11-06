import unittest
from satellite_center.native_locations import load_locations,search_locations,city_label

class NativeCitySearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows=load_locations()
    def test_full_shared_offline_city_dataset(self):
        self.assertEqual(len(self.rows),8084)
        self.assertEqual(sum(c=="DE" for c,*_ in self.rows),7104)
        self.assertEqual(sum(c=="TR" for c,*_ in self.rows),980)
    def test_hurth_izmir_and_city_labels(self):
        places=search_locations(self.rows,"huerth","DE")
        self.assertEqual(places[0][1],"Hürth")
        self.assertIn("Germany",city_label(places[0]))
        tr=search_locations(self.rows,"Izmir","TR")
        self.assertTrue(tr)
        self.assertTrue(all(p[0]=="TR" for p in tr))
    def test_short_queries_and_country_filters(self):
        self.assertEqual(search_locations(self.rows,"i"),[])
        self.assertEqual(search_locations(self.rows,"izmir","DE"),[])
        self.assertLessEqual(len(search_locations(self.rows,"ber","all")),12)
