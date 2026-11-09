"""Regress DAB centre frequency UI and honest live buffer progress.

Pure-source contract tests: no SDR/Qt/hardware opened.
Qt/C++ compilation is covered separately by the Kaffeine CI matrix.
"""
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parents[1]
RADIO=(ROOT/"kaffeine_next/native_radio_tab.h").read_text(encoding="utf-8")


class RadioFrequencyAndCacheUX(unittest.TestCase):
    def test_every_supported_band_iii_block_has_correct_center_khz(self):
        list_source=re.search(
            r'const QStringList blocks\s*=\s*\{(.*?)\};',RADIO,re.S)
        self.assertIsNotNone(list_source)
        listed=re.findall(r'"(\d{1,2}[A-F])"',list_source.group(1))
        table=re.search(
            r'static const QMap<QString,int> centers = \{(.*?)\};',RADIO,re.S)
        self.assertIsNotNone(table)
        entries=dict((block,int(khz)) for block,khz in
            re.findall(r'\{"(\d{1,2}[A-F])",(\d+)\}',table.group(1)))
        self.assertEqual(set(listed),set(entries))
        self.assertEqual(len(entries),38)
        for channel,expected in (
                ("5A",174928),("5C",178352),("9D",208064),
                ("10A",209936),("11D",222064),("12D",229072),
                ("13D",235776),("13F",239200)):
            self.assertEqual(entries[channel],expected)

    def test_now_playing_live_signal_and_vintage_share_frequency_helper(self):
        self.assertIn('dabCenterFrequencyMHz(ch)',RADIO)
        self.assertIn('dls_->setText(tr("Now playing: %1',RADIO)
        self.assertIn('DAB+ block %2 · %3 (centre frequency)',RADIO)
        self.assertIn('signal_->setText(tr("DAB+ block %1 · centre %2',RADIO)
        self.assertIn('vintageDabReadout_=new QLabel(analogCabinet)',RADIO)
        self.assertIn('vintageDabReadout_->setVisible(dab)',RADIO)
        self.assertIn('vintageDabReadout_->setText(tr(',RADIO)
        self.assertIn('arg(block,dabCenterFrequencyMHz(block),sid)',RADIO)
        self.assertIn('analogue dial remains independent',RADIO)

    def test_enabling_extra_buffer_shows_ui_progress_outside_advanced_panel(self):
        self.assertIn('quickBufferProgress_=new QProgressBar(page)',RADIO)
        self.assertIn('dabLayout->addWidget(quickBufferProgress_)',RADIO)
        self.assertIn('quickBufferProgress_->setVisible(enabled)',RADIO)
        self.assertIn('refreshRadioBufferProgress();',RADIO)
        self.assertIn('captionTick_.setInterval(300)',RADIO)
        self.assertIn('qMin(95,int(qMin(elapsed,qint64(requested))*95/requested))',
                      RADIO)
        self.assertIn('actual fill unmeasured',RADIO)
        self.assertIn('Player reports PLAYING',RADIO)
        self.assertIn('percent=100; // The player STARTED',RADIO)
        self.assertIn('if(!stationOpened)',RADIO)
        self.assertIn('for(QProgressBar *bar:{quickBufferProgress_,audioCacheProgress_})',
                      RADIO)
        self.assertNotIn('audioCacheProgress_->setRange(0,audioStartedMs_>0?0:100)',
                         RADIO)


if __name__=="__main__":
    unittest.main()
