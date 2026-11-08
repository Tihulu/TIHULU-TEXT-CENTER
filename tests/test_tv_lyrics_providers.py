"""Plain lyric provider opt-in and audio-verification boundaries."""
import unittest
from unittest import mock
from tv_center.lyrics_sync import lookup_alternative_plain,lookup_synced_lyrics


class LyricsProviderTests(unittest.TestCase):
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


if __name__=="__main__":
    unittest.main()
