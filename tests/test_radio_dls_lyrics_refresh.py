"""Offline regression for RTL DLS, karaoke fallback, sources and refresh.

No real tuner, music rights, internet, audio, or AI weights are used in CI.
"""
import unittest
from pathlib import Path
from tv_center.radio_dls_metadata import parse_dls_song
from tv_center.direct_de_tr import direct_de_tr_order, translate_de_tr_direct

ROOT=Path(__file__).resolve().parents[1]
RADIO=(ROOT/"kaffeine_next/native_radio_tab.h").read_text(encoding="utf-8")
TV=(ROOT/"kaffeine_next/captions_overlay.py").read_text(encoding="utf-8")


class DlsAndRefreshTests(unittest.TestCase):
    def test_rockfm_artist_title(self):
        hint=parse_dls_song("ERNEST LA ROCHE - WITH YOU BY MY SIDE")
        self.assertEqual((hint.artist,hint.title),
                         ("ERNEST LA ROCHE","WITH YOU BY MY SIDE"))

    def test_rtl_radio_german_track_first(self):
        hint=parse_dls_song(
            "JETZT ON AIR :: Golden Summer :: Loi & David Puentez")
        self.assertEqual((hint.artist,hint.title),
                         ("Loi & David Puentez","Golden Summer"))

    def test_dls_unsupported_station_slogans_are_not_fake_lyrics(self):
        for item in ("ROCK FM", "Jetzt mehr Hits!", "JETZT ON AIR :: talk",
                     "Artist - Artist", ""):
            with self.subTest(item=item):
                self.assertIsNone(parse_dls_song(item))

    def test_normalized_song_hint_key(self):
        a=parse_dls_song("ÄRZTË - Mein Lied")
        b=parse_dls_song("ÄRZTË - Mein Lied")
        self.assertEqual(a.key,b.key)

    def test_cxx_radio_lookup_uses_parsed_hint_and_not_raw_dash_only(self):
        for anchor in ("inline TihuluDlsSong tihuluDlsSong",
                       'QLatin1String("jetzt on air")',
                       "const TihuluDlsSong newSong=tihuluDlsSong(dls);",
                       "newSong.normalizedKey()!=lastSongMetadataKey_",
                       "const TihuluDlsSong song=tihuluDlsSong(lastDls_)",
                       "const QString title=overridden?lyricsTitle_->text().trimmed():song.title",
                       "fetchLyrics(true);"):
            self.assertIn(anchor,RADIO)

    def test_legal_localization_catalog_is_search_only(self):
        for domain in ("genius.com","soundchapter.com","liedertexte.com",
                       "muziksozleri.com.tr","sarki.sozmuzik.net"):
            self.assertIn(domain,RADIO)
        self.assertIn("QDesktopServices::openUrl(url)",RADIO)
        self.assertIn("No lyrics are copied automatically",RADIO)
        self.assertIn("TIHULU_MUSIXMATCH_API_KEY",(
            ROOT/"tv_center/lyrics_sync.py").read_text(encoding="utf-8"))

    def test_karaoke_no_lyrics_does_not_invent_song_words(self):
        self.assertIn("No licensed/verified lyrics · Whisper captions below",RADIO)
        self.assertIn("Lyrics retrieved · listening for actual sung words",RADIO)
        self.assertIn("lastKaraokeUntilMs_",RADIO)
        self.assertIn("showKaraokeLine(cue)",RADIO)
        self.assertIn("LYRICS NOT FOUND · Whisper fallback",RADIO)

    def test_ai_master_preserves_privacy_and_manual_off(self):
        self.assertIn("lyricsOnlineConsentAsked",RADIO)
        self.assertIn("lyricsOnlineOptIn",RADIO)
        self.assertIn("radioAiAutoTranslate",RADIO)
        self.assertIn("radioAiAutoKaraoke",RADIO)
        self.assertIn("radioAiAutoSync",RADIO)
        self.assertIn("Offline Whisper still works if you decline.",RADIO)

    def test_refresh_on_both_players_does_not_retune(self):
        for key in ("AI Caption Refresh","Lip-sync Refresh",
                    "captionBoundStationKey_!=playingKey_",
                    "lagSamples_.clear();", "startCaptioning();"):
            self.assertIn(key,RADIO)
        for key in ("AI Caption Refresh","Lip-sync Refresh",
                    "def refresh_tv_captions():",
                    "def refresh_tv_sync():",
                    "applied.revision + 1",
                    "tap.work_queue.clear()",
                    "estimator.clear()"):
            self.assertIn(key,TV)
        self.assertIn("manual offset",TV.lower())
        
    def test_direct_translation_prefers_installed_direct_models(self):
        self.assertEqual(direct_de_tr_order(
            nllb_installed=True,madlad_installed=True),
            ("nllb","madlad","argos"))
        result=translate_de_tr_direct("Guten Morgen",available={
            "nllb":True,"madlad":True},translators={
            "nllb":lambda *_: "Günaydın",
            "madlad":lambda *_: "Yedek",
            "argos":lambda *_: "Ara yol"})
        self.assertEqual(result.engine,"nllb-direct-de-tr")
        self.assertEqual(result.text,"Günaydın")

    def test_existing_translator_selection_is_opt_in_not_cloud(self):
        s=(ROOT/"kaffeine_next/captions_overlay.py").read_text(encoding="utf-8")
        self.assertIn('"translation_requested":bool(self.show_translation)',
            (ROOT/"kaffeine_next/caption_timing.py").read_text(encoding="utf-8"))
        self.assertIn('"de_tr_direct"',s)
        self.assertIn("translation_allowed",s)


if __name__=="__main__":
    unittest.main()
