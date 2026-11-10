"""Regression: lyrics queries must never target service/station labels.

No SDR, internet, real music or model weights are needed for these checks.
Qt source contracts complement real C++ build jobs.
"""
import unittest
from pathlib import Path

from tv_center.radio_dls_metadata import parse_dls_song, parse_service_song

HEADER=(Path(__file__).resolve().parents[1] /
        "kaffeine_next/native_radio_tab.h").read_text(encoding="utf-8")


class RadioSongMetadataSourceTests(unittest.TestCase):
    def test_station_name_and_slogan_are_not_tracks(self):
        service={
            "label": {"label": "WDR 2 Köln"},
            "dls": {"label": {"label": "WDR 2 - Die besten Hits"}},
        }
        self.assertIsNone(parse_service_song(service))
        self.assertIsNone(parse_dls_song(
            "WDR 2 Köln - die besten Hits",station="WDR 2 Köln"))
        self.assertIsNone(parse_service_song({
            "label": "Radio Köln",
            "dls": {"label": "Radio Köln"}
        }))

    def test_real_dls_track_is_separate_from_service_label(self):
        service={
            "label": {"label": "Radio Köln"},
            "dls": {"label": {"label": "ERNEST LA ROCHE - WITH YOU BY MY SIDE"}},
        }
        hint=parse_service_song(service)
        self.assertEqual((hint.artist,hint.title),
                         ("ERNEST LA ROCHE","WITH YOU BY MY SIDE"))

    def test_typed_now_playing_overrides_rotating_station_dls(self):
        service={
            "label": {"label": "WDR 2 Köln"},
            "dls": {"label": {"label": "WDR 2 - Die besten Hits"}},
            "now_playing": {"artist": "Loi & David Puentez",
                            "title": "Golden Summer"},
        }
        hint=parse_service_song(service)
        self.assertEqual((hint.artist,hint.title,hint.format),
                         ("Loi & David Puentez","Golden Summer","Now playing"))

    def test_nested_dls_plus_tags_and_radio_info(self):
        service={
            "label": {"label": "WDR 2 Köln"},
            "dls": {"label": "WDR 2 - Hitmix",
                    "dlplus": {"item":{"artist":"Example Artist",
                                       "title":"Example Song"}}},
        }
        song=parse_service_song(service)
        self.assertEqual((song.artist,song.title,song.format),
                         ("Example Artist","Example Song","DLS+"))
        tag_service={
            "label": "Radio Köln",
            "dlplus": {"tags":[
                {"type":"ITEM.ARTIST","text":"Another Artist"},
                {"type":"ITEM.TITLE","text":"Another Song"},
            ]}
        }
        tagged=parse_service_song(tag_service)
        self.assertEqual((tagged.artist,tagged.title),
                         ("Another Artist","Another Song"))

    def test_nested_dls_plus_tags(self):
        service={
            "label":"Radio Köln",
            "dls":{"label":"Radio Köln - Der beste Mix",
                   "dlplus":{"tags":[
                       {"type":"ITEM.ARTIST","text":"Example Band"},
                       {"type":"ITEM.TITLE","text":"Example Track"},
                   ]}},
        }
        song=parse_service_song(service)
        self.assertEqual((song.artist,song.title),
                         ("Example Band","Example Track"))

    def test_radio_text_and_rds_plus_sources(self):
        self.assertEqual(
            parse_service_song({
                "label":"FM Station", "radiotext":"Artist Name - Song Title"
            }).title,"Song Title")
        self.assertEqual(
            parse_service_song({
                "label":"FM Station",
                "rtplus":{"item_artist":"Music Group","item_title":"A Song"}
            }).artist,"Music Group")

    def test_dls_track_first_and_named_fields(self):
        self.assertEqual(
            parse_dls_song("JETZT ON AIR :: Golden Summer :: Loi & David Puentez").title,
            "Golden Summer")
        self.assertEqual(
            parse_dls_song("Artist: Test Artist | Title: Test Song").artist,
            "Test Artist")

    def test_single_fields_are_not_songs_and_unknown_means_no_online_query(self):
        for entry in (
            {"label":"WDR 2", "song":{"title":"Unknown Artist"}},
            {"label":"WDR 2", "metadata":{"title":"Station News"}},
            {"label":"WDR 2", "now_playing":{"artist":"Known Artist"}},
            {"label":"WDR 2", "dls":{"label":"WDR 2"}},
        ):
            with self.subTest(entry=entry):
                self.assertIsNone(parse_service_song(entry))

    def test_native_engine_uses_accepted_song_and_multiple_sources(self):
        for contract in (
            "tihuluDlsSongFromService(service)",
            "tihuluStationSong(song,station)",
            "service.value(QLatin1String(\"dlplus\"))",
            "service.value(QLatin1String(\"rtplus\"))",
            "service.value(QLatin1String(\"radio_info\"))",
            "lastAcceptedSongHint_=acceptedSong",
            "const TihuluDlsSong song=lastAcceptedSongHint_;",
            "pendingSongObservations_<2",
            "now-lastObservedSongMs_>12000",
        ):
            with self.subTest(contract=contract):
                self.assertIn(contract,HEADER)
        lookup=HEADER.split("void fetchLyrics(bool automatic=false)",1)[1]
        lookup=lookup.split("void updateLyrics()",1)[0]
        self.assertNotIn("lastSongDls_.isEmpty()?lastSongDls_:lastDls_",lookup)
        self.assertNotIn("tihuluDlsSong(lastDls_)",lookup)


if __name__=="__main__":
    unittest.main()
