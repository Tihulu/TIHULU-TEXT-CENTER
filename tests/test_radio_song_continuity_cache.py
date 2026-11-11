"""Regression contracts for DLS song changes and duplicate lyric lookups.

These source checks assert native Qt transition guards and cache semantics.
Real station/DAC audio confirmation still requires hardware tests.
"""
from pathlib import Path
import unittest

RADIO=(Path(__file__).resolve().parents[1] /
       "kaffeine_next/native_radio_tab.h").read_text(encoding="utf-8")


class RadioSongContinuityTests(unittest.TestCase):
    def test_dls_update_does_not_directly_clear_karaoke(self):
        dls = RADIO.split("const TihuluDlsSong newSong=tihuluDlsSongFromService(service);")[1]
        dls = dls.split("const QJsonObject errs=service.value(", 1)[0]
        self.assertIn("pendingSongKey_=candidate", dls)
        self.assertIn("QTimer::singleShot(5100,this,", dls)
        self.assertIn("commitPendingDlsSong(candidate,station,ticket)", dls)
        self.assertIn("candidate==lastSongMetadataKey_", dls)
        for forbidden in ("clearKaraokeLine();", "lyricCues_=QJsonArray();",
                          "lyricsProcess_.kill();", "fetchLyrics(true);"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, dls)

    def test_confirm_requires_same_station_and_same_pending_song(self):
        transition=RADIO.split("void commitPendingDlsSong(")[1].split(
            "void stopLyrics()",1)[0]
        for guard in ("candidate!=pendingSongKey_",
                      "station!=playingKey_", "ticket!=stationRequestId_",
                      "now-pendingSongSinceMs_<5000",
                      "now-lastVerifiedLyricMs_<7000",
                      "pendingSongKey_.clear();",
                      "lastSongMetadataKey_=candidate",
                      "lastSongDls_=acceptedDls",
                      "clearKaraokeLine();"):
            with self.subTest(guard=guard):
                self.assertIn(guard, transition)
        # No separate automatic HTTP request until the same candidate
        # survives the hold and current-song ASR no longer matches.
        self.assertEqual(transition.count("fetchLyrics(true);"),1)

    def test_lookup_deduplication_is_before_clear_and_online_spawn(self):
        lookup=RADIO.split("void fetchLyrics(bool automatic=false)")[1].split(
            "void updateLyrics()",1)[0]
        dedup=lookup.index("requestKey==lyricsRequestKey_")
        clearing=lookup.index("clearKaraokeLine();")
        worker=lookup.index("lyricsProcess_.start(")
        self.assertLess(dedup,clearing)
        self.assertLess(dedup,worker)
        self.assertIn("lyricsLookupCooldownUntilMs_",lookup)
        self.assertIn("lyricsLookupGeneration_",lookup)
        self.assertIn("pendingSongKey_.isEmpty()",lookup)
        self.assertIn("lastAcceptedSongHint_",lookup)
        self.assertIn("sourceCode",lookup)
        self.assertIn("dests.join(",lookup)

    def test_cache_is_bounded_and_reuses_normal_parser(self):
        lookup=RADIO.split("void fetchLyrics(bool automatic=false)")[1].split(
            "void updateLyrics()",1)[0]
        parsed=RADIO.split("void updateLyrics()")[1].split(
            "MediaWidget *player_",1)[0]
        self.assertIn("lyricsCache_.contains(requestKey)",lookup)
        self.assertIn("7200000",lookup) # 2h expiration
        self.assertIn("QSaveFile cacheOutput",lookup)
        self.assertIn("updateLyrics();",lookup)
        self.assertIn("lyricsCache_.size()>=12",parsed)
        self.assertIn("lyricsCache_.insert(lyricsRequestKey_,value)",parsed)
        self.assertIn("lyricsCacheTime_.insert(lyricsRequestKey_,now)",parsed)

    def test_stop_and_new_station_invalidate_song_candidate(self):
        self.assertIn("pendingSongKey_.clear();",RADIO)
        station=RADIO.split("lastDls_.clear();")[1][:220]
        self.assertIn("pendingSongKey_.clear();",station)
        self.assertIn("pendingSongDls_.clear();",station)
        self.assertIn("pendingSongSinceMs_=0;",station)


if __name__=="__main__":
    unittest.main()
