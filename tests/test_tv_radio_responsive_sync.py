"""Radio UI and sync contracts: no feature removal while making tabs responsive.

These assertions supplement pinned Qt native compile; they do not claim
that a physical RTL-SDR audio-output clock is sample-accurate.
"""
import unittest
from pathlib import Path

BASE=Path(__file__).resolve().parents[1]


class RadioModesAndSyncTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.radio=(BASE/"kaffeine_next/native_radio_tab.h").read_text()
        cls.patch=(BASE/"kaffeine_next/patch_upstream.py").read_text()
        cls.ai=(BASE/"tv_center/radio_ai.py").read_text()

    def test_compact_modes_preserve_each_major_radio_function(self):
        for section in ('DAB+ · stations','Internet radio','Vintage FM / AM / LW',
                        'AI subtitles / lyrics','RF Lab · advanced'):
            self.assertIn('modes_->addTab(',self.radio)
            self.assertIn(section,self.radio)
        for legacy in ('scanProgress_', 'scanSNR_', 'webStations_',
                       'analogDial_', 'analogScale_', 'radioCanvas_',
                       'stations_', 'captionSource_', 'music_', 'lyrics_',
                       'rfQuality_', 'multiRf_', 'slideHistory_',
                       'stopCaption_', 'lyricsImport_', 'record_'):
            self.assertIn(legacy,self.radio)
        self.assertIn('setOrientation(width()<930?Qt::Vertical:Qt::Horizontal)',self.radio)
        self.assertIn('radioModeTab',self.radio)

    def test_native_tuner_station_label_avoids_fake_fm_frequency(self):
        self.assertIn('showSelectedSource(item->text(1)',self.radio)
        self.assertIn('showSelectedSource(knownName',self.radio)
        self.assertIn('showSelectedSource(name,tr("DAB+ · live mux verified")',self.radio)
        self.assertIn('analogue dial remains independent of DAB/Internet',self.radio)
        self.assertIn('analogBand_->currentText()',self.radio)

    def test_cache_guard_matches_actual_vlc_media_option(self):
        self.assertIn('bufferMs_->setRange(0,60000)',self.radio)
        self.assertIn('activePlaybackCacheMs_',self.radio)
        self.assertIn('lastAudioRetuneMs_>=180000',self.radio)
        self.assertIn('QCheckBox(tr("Allow automatic radio audio restart")',self.radio)
        self.assertIn('qMax(0,remaining)+radioOffsetMs_->value()',self.radio)
        self.assertIn('radioSettings.value(QLatin1String("playbackBufferMs"),12000).toInt()',self.patch)
        self.assertIn('60000);',self.patch)
        self.assertIn('60 s',self.radio)

    def test_lyric_alignment_requires_reliable_evidence_and_is_rate_limited(self):
        self.assertIn('confidence>=0.92',self.radio)
        self.assertIn('lyricOffsetConsistency_>=2',self.radio)
        self.assertIn('now-lastLyricSyncUpdateMs_>=30000',self.radio)
        self.assertIn('qBound(-250,int(delta/8),250)',self.radio)
        self.assertIn('lastVerifiedLyricTranslations_',self.radio)
        self.assertIn('lyric_translations',self.ai)
        self.assertIn('"timed_lrc" if cues else "asr_lexical"',self.ai)


if __name__=="__main__":
    unittest.main()
