import unittest
from satellite_center.native_locations import load_locations,search_locations,city_label,regions_for

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

    def test_country_state_province_city_combination(self):
        nrw="North Rhine-Westphalia"
        self.assertIn(nrw,regions_for(self.rows,"DE"))
        self.assertNotIn(nrw,regions_for(self.rows,"TR"))
        cities=search_locations(self.rows,"Hürth","DE",region=nrw)
        self.assertTrue(cities)
        self.assertTrue(all(row[0]=="DE" and row[2]==nrw for row in cities))
        self.assertFalse(search_locations(self.rows,"Hürth","DE",region="Bavaria"))
        izmir=search_locations(self.rows,"Izmir","TR")
        self.assertTrue(izmir)
        self.assertTrue(all(row[0]=="TR" for row in izmir))
        self.assertFalse(search_locations(self.rows,"Köln","TR"))
        self.assertIn("İzmir",regions_for(self.rows,"TR"))
        ilçeler=search_locations(self.rows,"Karaburun","TR",region="İzmir")
        self.assertTrue(ilçeler)
        self.assertEqual(ilçeler[0][1],"Karaburun")
        self.assertEqual(ilçeler[0][2],"İzmir")
        self.assertFalse(search_locations(self.rows,"Karaburun","TR",region="Ankara"))
