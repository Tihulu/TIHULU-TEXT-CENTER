import tempfile
from pathlib import Path
import unittest
from textcenter.core import Store
from textcenter.subtitles import CaptionStore,language_pair


class SubtitleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=CaptionStore(Store(Path(self.tmp.name)/"subtitles.db"))
    def tearDown(self):self.tmp.cleanup()

    def test_all_six_pairs_and_opt_in_original_and_translation_archive(self):
        self.assertEqual(language_pair("de","tr"),("de","tr"))
        with self.assertRaises(ValueError):
            language_pair("fr","tr")
        session=self.db.new_session(media_kind="fm_radio",source_label="real receiver",
             source_lang="de",target_lang="tr",device="cpu",
             backend="faster-whisper",store_original=True,store_translation=False)
        self.assertTrue(self.db.add_cue(session,sequence=1,begin=0,end=2,
                original_text="Guten Morgen")["stored"])
        self.assertEqual(self.db.cues(session)[0]["translated_text"],"")
        archive=self.db.translate_saved(session,"tr",translator=lambda text,src,dst:"Günaydın")
        self.assertEqual(archive["translated"],1)
        self.assertEqual(self.db.cues(session)[0]["original_text"],"Guten Morgen")
        self.assertEqual(self.db.cues(session)[0]["translated_text"],"Günaydın")
        self.assertIn(b"00:00:00,000 --> 00:00:02,000",
                      self.db.subtitle_file(session,format="srt"))
        self.assertIn(b"WEBVTT",self.db.subtitle_file(session,format="vtt"))
        self.assertIn("Günaydın",self.db.subtitle_file(session,language="translated").decode())
        self.db.finish(session)
        self.assertEqual(self.db.sessions()[0]["saved_cues"],1)
        self.assertEqual(len(CaptionStore(self.db.store).cues(session)),1)

    def test_no_auto_record_and_translation_requires_original(self):
        ephem=self.db.new_session(media_kind="dvb_tv",source_label="TV",
            source_lang="tr",target_lang="en",device="cpu",backend="faster-whisper")
        self.assertFalse(self.db.add_cue(ephem,sequence=1,begin=0,end=1,
                     original_text="Merhaba")["stored"])
        self.assertEqual(self.db.cues(ephem),[])
        with self.assertRaises(KeyError):
            self.db.translate_saved(ephem,"en",translator=lambda *args:"Hello")
        with self.assertRaises(ValueError):
            self.db.new_session(media_kind="fm_radio",source_label="FM",
                source_lang="en",target_lang="de",device="cpu",
                backend="faster-whisper",store_translation=True)
        with self.assertRaises(ValueError):
            self.db.add_cue(ephem,sequence=1,begin=0,end=1,
                original_text="Test",translation="Translated")
        self.assertEqual(self.db.subtitle_file(ephem),b"")


if __name__=="__main__":
    unittest.main()
