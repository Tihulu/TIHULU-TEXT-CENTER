"""Plain lyric provider opt-in and audio-verification boundaries."""
import unittest
from unittest import mock
from tv_center.lyrics_sync import lookup_alternative_plain,lookup_synced_lyrics


class LyricsProviderTests(unittest.TestCase):
    def test_radio_punctuation_normalization_and_wrong_first_result(self):
        bad={"trackName":"Different Song","artistName":"Artist","syncedLyrics":"[00:01.00]Wrong"}
        good={"trackName":"Güneşli-Gün","artistName":"M.K.","syncedLyrics":"[00:02.00]Günaydın"}
        def request(url,**kwargs):
            if "lrclib.net/api/get?" in url: return bad
            if "lrclib.net/api/search?" in url: return [bad,good]
            raise AssertionError("unexpected lyrics provider "+url)
        with mock.patch("tv_center.lyrics_sync._get_json", side_effect=request):
            cues,source=lookup_synced_lyrics(title="Güneşli Gün",artist="M K",
                                             online=True)
        self.assertEqual(source["status"],"synced")
        self.assertEqual([c.text for c in cues],["Günaydın"])

    def test_absent_metadata_never_uses_wrong_lrclib_song(self):
        wrong={"trackName":"Other track","artistName":"Other artist",
               "syncedLyrics":"[00:01.00]NOT THE SONG"}
        def request(url,**kwargs):
            if "lrclib.net/api/get?" in url: return wrong
            if "lrclib.net/api/search?" in url: return []
            if "lyrics.ovh" in url: return {"lyrics":"First real lyric line"}
            raise AssertionError("unexpected request")
        with mock.patch.dict("os.environ",{"TIHULU_MUSIXMATCH_API_KEY":""}):
            with mock.patch("tv_center.lyrics_sync._get_json",side_effect=request):
                cues,meta=lookup_synced_lyrics(title="Track",artist="Artist",
                                               online=True,allow_plain=True)
        self.assertEqual(cues,[])
        self.assertEqual(meta["provider"],"lyrics.ovh")
        self.assertEqual(meta["alignment"],"awaiting_real_audio_ASR")

    def test_official_musixmatch_requires_personal_license_and_opt_in(self):
        from tv_center.lyrics_sync import lookup_musixmatch_licensed_plain
        with mock.patch.dict("os.environ",{"TIHULU_MUSIXMATCH_API_KEY":""}):
            with mock.patch("tv_center.lyrics_sync._get_json") as network:
                lines,meta=lookup_musixmatch_licensed_plain(
                    title="Track",artist="Artist",online=True)
                self.assertEqual(lines,[])
                self.assertEqual(meta["status"],"not_configured")
                with self.assertRaises(PermissionError):
                    lookup_musixmatch_licensed_plain(
                        title="Track",artist="Artist",online=False)
                network.assert_not_called()
        full={"message":{"header":{"status_code":200},"body":{"lyrics":{
            "lyrics_body":"A line heard in audio\nAnother authorized line",
            "lyrics_copyright":"Owner"}}}}
        with mock.patch.dict("os.environ",{"TIHULU_MUSIXMATCH_API_KEY":"TEST_KEY"}):
            with mock.patch("tv_center.lyrics_sync._get_json",return_value=full) as http:
                lines,meta=lookup_musixmatch_licensed_plain(
                    title="Track",artist="Artist",online=True)
            self.assertEqual(meta["provider"],"Musixmatch official API")
            self.assertEqual(meta["alignment"],"awaiting_real_audio_ASR")
            self.assertIn("api.musixmatch.com/ws/1.1/matcher.lyrics.get",
                          http.call_args.args[0])
            self.assertEqual(len(lines),2)

    def test_musixmatch_preview_lyrics_are_rejected(self):
        from tv_center.lyrics_sync import lookup_musixmatch_licensed_plain
        preview={"message":{"header":{"status_code":200},"body":{"lyrics":{
            "lyrics_body":"Preview\\n******* This Lyrics is NOT for Commercial use *******"}}}}
        with mock.patch.dict("os.environ",{"TIHULU_MUSIXMATCH_API_KEY":"LICENSED_TEST"}):
            with mock.patch("tv_center.lyrics_sync._get_json",return_value=preview):
                lines,meta=lookup_musixmatch_licensed_plain(
                    title="Track",artist="Artist",online=True)
        self.assertEqual(lines,[])
        self.assertEqual(meta["status"],"no_full_licensed_lyrics")

    def test_requires_online_opt_in(self):
        with self.assertRaises(PermissionError):
            lookup_alternative_plain(artist="Example Artist",title="Song",online=False)

    def test_alternate_plain_does_not_invent_timestamps(self):
        with mock.patch("tv_center.lyrics_sync._get_json",
                return_value={"lyrics":"First line\nSecond real line\nThird line"}) as call:
            lines,source=lookup_alternative_plain(
                artist="Test artist",title="Test Song",online=True)
            self.assertEqual(lines,["First line","Second real line","Third line"])
            self.assertEqual(source["provider"],"lyrics.ovh")
            self.assertEqual(source["alignment"],"awaiting_real_audio_ASR")
            self.assertTrue(call.call_args.args[0].startswith(
                "https://api.lyrics.ovh/v1/"))

    def test_lrclib_not_found_uses_alternative_on_request(self):
        def fetch(url,**_):
            if "lrclib.net/api/get?" in url:return {}
            if "lrclib.net/api/search?" in url:return []
            if "lyrics.ovh/v1/" in url:return {"lyrics":"The whole sentence\nAnother text"}
            raise AssertionError("unexpected online provider")
        with mock.patch("tv_center.lyrics_sync._get_json",side_effect=fetch):
            cues,source=lookup_synced_lyrics(
                artist="Artist",title="Track",online=True,allow_plain=True)
            self.assertEqual(cues,[])
            self.assertEqual(source["provider"],"lyrics.ovh")
            self.assertEqual(source["plain_lines"],["The whole sentence","Another text"])
            self.assertNotIn("cues",source)


    def test_lrclib_connection_failure_uses_authorized_plain_fallback(self):
        import urllib.error
        calls=[]
        def request(url,**kwargs):
            calls.append(url)
            if "lrclib.net/api/get?" in url:
                raise urllib.error.URLError("offline")
            if "lrclib.net/api/search?" in url:
                self.fail("Do not retry failed LRCLIB origin during this lookup")
            if "api.lyrics.ovh/v1/" in url:
                return {"lyrics":"First heard line\nThe second heard line"}
            self.fail("Unexpected provider "+url)
        with mock.patch.dict("os.environ",{"TIHULU_MUSIXMATCH_API_KEY":""}):
            with mock.patch("tv_center.lyrics_sync._get_json",side_effect=request):
                cues,meta=lookup_synced_lyrics(
                    title="Track",artist="Artist",online=True,allow_plain=True)
        self.assertEqual(cues,[])
        self.assertEqual(meta["provider"],"lyrics.ovh")
        self.assertEqual(meta["plain_lines"],
                         ["First heard line","The second heard line"])
        self.assertEqual(len(calls),2)

    def test_lrclib_search_failure_still_uses_alternative(self):
        def request(url,**_):
            if "lrclib.net/api/get?" in url:return {}
            if "lrclib.net/api/search?" in url:
                raise RuntimeError("catalog service temporarily unavailable")
            if "api.lyrics.ovh/v1/" in url:
                return {"lyrics":"Vocal line from user-approved lyrics service"}
            self.fail("Unexpected provider "+url)
        with mock.patch.dict("os.environ",{"TIHULU_MUSIXMATCH_API_KEY":""}):
            with mock.patch("tv_center.lyrics_sync._get_json",side_effect=request):
                cues,meta=lookup_synced_lyrics(
                    title="Track",artist="Artist",online=True,allow_plain=True)
        self.assertFalse(cues)
        self.assertEqual(meta["provider"],"lyrics.ovh")
        self.assertEqual(meta["alignment"],"awaiting_real_audio_ASR")

    def test_malformed_synced_lyrics_uses_actual_plain_text(self):
        record={"trackName":"Track","artistName":"Artist",
                "syncedLyrics":"[bad timestamp]This is not valid LRC",
                "plainLyrics":"The first real line\nThe second real line",
                "instrumental":False,"id":3}
        with mock.patch("tv_center.lyrics_sync._get_json",return_value=record) as net:
            cues,meta=lookup_synced_lyrics(
                title="Track",artist="Artist",online=True,allow_plain=True)
        self.assertFalse(cues)
        self.assertEqual(meta["provider"],"LRCLIB")
        self.assertEqual(meta["plain_lines"],
                         ["The first real line","The second real line"])
        self.assertEqual(meta["alignment"],"awaiting_real_audio_ASR")
        self.assertEqual(net.call_count,1)

    def test_lrclib_outage_without_plain_opt_in_stays_error(self):
        import urllib.error
        with mock.patch("tv_center.lyrics_sync._get_json",
                        side_effect=urllib.error.URLError("offline")) as net:
            with self.assertRaises(urllib.error.URLError):
                lookup_synced_lyrics(
                    title="Track",artist="Artist",online=True,allow_plain=False)
        self.assertEqual(net.call_count,1)


if __name__=="__main__":
    unittest.main()
