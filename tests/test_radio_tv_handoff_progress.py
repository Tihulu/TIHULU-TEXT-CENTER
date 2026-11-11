"""Regression contracts for Start-page Radio click and guarded native TV handoff.

Real SDR/DVB hardware and XWayland clicks require on-device follow-up.
These checks complement the pinned Qt5 mainwindow compilation in CI.
"""
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PATCH=(ROOT/"kaffeine_next/patch_upstream.py").read_text(encoding="utf-8")
RADIO=(ROOT/"kaffeine_next/native_radio_tab.h").read_text(encoding="utf-8")


class RadioAndTvHandoffTests(unittest.TestCase):
    def test_start_radio_tile_uses_actual_qt5_signal(self):
        self.assertIn(
            'connect(button, SIGNAL(clicked(bool)), mainWindow, SLOT(playRadio()));',
            PATCH)
        self.assertIn('SIGNAL(clicked(bool))',PATCH)
        self.assertIn('home_marker =',PATCH)
        self.assertIn('void MainWindow::playRadio()',PATCH)
        self.assertIn('activateTab(RadioTabId);',PATCH)
        self.assertIn('QSignalBlocker noRecursiveTabChange(tabBar)',PATCH)

    def test_tv_switch_releases_own_radio_before_activating_dvb(self):
        method=RADIO.split("bool releaseForTelevision() {",1)[1].split(
            "void hardwareStartDab()",1)[0]
        self.assertIn("if(tvHandoffInProgress_) return false;",method)
        self.assertIn("hardwareDabOwned()",method)
        self.assertIn("hardwareAnalogOwned()",method)
        self.assertIn("++stationRequestId_;",method)
        self.assertIn("++scanRequestId_;",method)
        self.assertIn("stopReceiver();",method)
        self.assertIn("!hardwareDabOwned() && !hardwareAnalogOwned()",method)
        self.assertNotIn("dvb_->",method)
        self.assertNotIn("pkill",method)
        self.assertNotIn("killall",method)
        self.assertNotIn("lsusb",method)

    def test_tab_switch_avoids_reentrancy_and_refuses_busy_sdr(self):
        for item in ('property("tihuluTabSwitchBusy").toBool()',
                     'setProperty("tihuluTabSwitchBusy",true)',
                     'setProperty("tihuluTabSwitchBusy",false)',
                     "radioOwned", "releaseForTelevision()",
                     'tabs.at(currentTabIndex)->activate()',
                     "tabBar->setCurrentIndex(currentTabIndex);"):
            with self.subTest(item=item):
                self.assertIn(item,PATCH)
        self.assertIn('if (currentTabIndex != DvbTabId) return;',PATCH)

    def test_percentage_is_stage_based_not_fake_rf_or_timing(self):
        for item in ('tihuluReceiverSwitchProgress',
                     'progress->setValue(10)', 'progress->setValue(35)',
                     'progress->setValue(85)', 'progress->setValue(100)',
                     'progress->setValue(70)',
                     "RF lock not yet measured","SDR on-demand"):
            with self.subTest(item=item):
                self.assertIn(item,PATCH)
        self.assertNotIn("USB transfer estimated",PATCH)


if __name__ == "__main__":
    unittest.main()
