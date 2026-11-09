"""Regression contracts for on-demand RTL-SDR ownership in Kaffeine Radio.

No physical USB device is accessed. C++ builds in CI cover the Qt signatures;
these focused tests guard against regressions to leaving welle-cli alive
after the main playback Stop command or a normal explicit radio Stop.
"""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
UI=(ROOT/"kaffeine_next/native_radio_tab.h").read_text(encoding="utf8")


def method(name, end):
    start=UI.index(name)
    finish=UI.index(end,start)
    return UI[start:finish]


class RadioReceiverLifecycleTests(unittest.TestCase):
    def test_radio_stop_releases_usb_by_default_and_keep_ready_is_explicit(self):
        self.assertIn('releaseSdrOnStop"),true).toBool()',UI)
        self.assertIn("releaseOnStop_->setChecked(",UI)
        self.assertIn('releaseSdrOnStop"),enabled',UI)
        self.assertIn("stopRadioListening();",UI)
        self.assertIn("forceRelease_",UI)
        block=method("void stopRadioListening() {","void monitorRadioPlaybackStop() {")
        self.assertIn("releaseOnStop_->isChecked()",block)
        self.assertIn("stopReceiver();",block)
        self.assertIn("stopCaptioning();",block)
        self.assertIn("stopLyrics();",block)
        self.assertIn("stopRecording();",block)
        self.assertIn("player_->stop();",block)
        self.assertIn("playingKey_.clear();",block)
        self.assertIn("Receiver kept ready by choice",block)

    def test_normal_shutdown_releases_only_this_apps_receiver(self):
        stop=method("void stopReceiver() {","QString apiFailureDetails() const")
        self.assertIn("backend_.terminate();",stop)
        self.assertIn("backend_.waitForFinished(1200)",stop)
        self.assertIn("backend_.kill();",stop)
        self.assertIn("QFile::remove(wellePortFile_)",stop)
        self.assertIn("tick_.stop();",stop)
        self.assertIn("++receiverGeneration_",stop)
        self.assertIn("++stationRequestId_",stop)
        self.assertIn("updateReceiverOwnership();",stop)
        self.assertIn("~TihuluRadioTab() override { stopReceiver(); }",UI)
        self.assertNotIn("pkill",stop)
        self.assertNotIn("killall",stop)

    def test_global_player_stop_is_distinct_from_pause_and_retune(self):
        monitor=method("void monitorRadioPlaybackStop() {","void stopReceiver() {")
        self.assertIn("MediaWidget::Playing",monitor)
        self.assertIn("MediaWidget::Idle",monitor)
        self.assertIn("!playingKey_.isEmpty()",monitor)
        self.assertIn("dabPlaybackObserved_",monitor)
        self.assertIn("now-dabIdleSinceMs_>=2300",monitor)
        self.assertIn("stopRadioListening();",monitor)
        self.assertIn("stopAnalog();",monitor)
        self.assertIn("monitorRadioPlaybackStop();",UI)
        station=method("void selectStation(QTreeWidgetItem *item) {",
                       "void toggleRecording() {")
        self.assertLess(station.index("dabPlaybackObserved_=false"),
                        station.index("player_->stop();"))
        self.assertIn("if(!active()) {",station)
        self.assertIn("startReceiver();",station)

    def test_receiver_ownership_is_visible_and_never_guesses_external_owner(self):
        ownership=method("void updateReceiverOwnership() {",
                         "void stopRadioListening() {")
        self.assertIn("backend_.state()!=QProcess::NotRunning",ownership)
        self.assertIn("analogDemod_.state()!=QProcess::NotRunning",ownership)
        self.assertIn("RELEASED by TIHULU",ownership)
        self.assertIn("IN USE by TIHULU",ownership)
        self.assertIn("receiverOwnership_=new QLabel(",UI)
        self.assertIn("updateReceiverOwnership();",UI)


if __name__=="__main__":
    unittest.main()
