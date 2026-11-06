"""Only verified decoder observations enter the persistent station directory."""
from pathlib import Path
import tempfile
import unittest

from textcenter.core import Store
from textcenter.channel_catalog import ChannelCatalog


class ChannelCatalogTests(unittest.TestCase):
    def test_save_reopen_and_filter_verified_station_directory(self):
        with tempfile.TemporaryDirectory() as td:
            store=Store(Path(td)/"textcenter.db")
            stations=ChannelCatalog(store)
            self.assertEqual(stations.list(),[])
            stations.save_fm(frequency_hz=98_600_000,name="WDR 2",last_text="Decoder RadioText")
            stations.save_dab(channel="11D",frequency_hz=222_064_000,
                              service_id="0x0792",name="WDR 2 RHEIN-RUHR",
                              ensemble="WDR NRW",audio_advertised=True,
                              last_text="Actual DLS")
            latest=ChannelCatalog(store)
            self.assertEqual(len(latest.list()),2)
            fm=latest.list(medium="fm")
            self.assertEqual(len(fm),1)
            self.assertEqual(fm[0]["name"],"WDR 2")
            self.assertEqual(fm[0]["frequency_hz"],98_600_000)
            dab=latest.list(medium="dab")
            self.assertEqual(len(dab),1)
            self.assertEqual(dab[0]["channel"],"11D")
            self.assertEqual(dab[0]["decoder"],"welle_cli_fic")
            self.assertEqual(dab[0]["audio_advertised"],1)
            latest.save_fm(frequency_hz=98_600_000,name="WDR 2",last_text="Updated actual text")
            self.assertEqual(len(latest.list(medium="fm")),1)
            self.assertEqual(latest.list(medium="fm")[0]["last_text"],"Updated actual text")

    def test_reject_fabricated_radio_station_attributes(self):
        with tempfile.TemporaryDirectory() as td:
            catalog=ChannelCatalog(Store(Path(td)/"textcenter.db"))
            with self.assertRaises(ValueError):
                catalog.save_fm(frequency_hz=98_600_000,name="FM 98.6 MHz")
            with self.assertRaises(ValueError):
                catalog.save_dab(channel="11D",frequency_hz=222_063_000,
                                 service_id="0x1234",name="Something",
                                 ensemble="WDR NRW",audio_advertised=True)
            with self.assertRaises(ValueError):
                catalog.save_dab(channel="11D",frequency_hz=222_064_000,
                                 service_id="0x1234",name="Unlabelled decoded service",
                                 ensemble="WDR NRW",audio_advertised=True)
            with self.assertRaises(ValueError):
                catalog.list(medium="fm;DROP TABLE verified_stations")
            self.assertEqual(catalog.list(),[])


if __name__=="__main__":
    unittest.main()
