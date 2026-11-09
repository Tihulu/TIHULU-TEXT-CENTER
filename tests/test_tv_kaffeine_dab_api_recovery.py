"""No-hardware regression for native welle-cli API readiness and USB ownership."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
SOURCE=(ROOT/"kaffeine_next/native_radio_tab.h").read_text(encoding="utf-8")


class NativeDabApiRecoveryTests(unittest.TestCase):
    def test_only_owned_welle_restarts_on_explicit_start(self):
        self.assertIn('if (active() && apiReady_)',SOURCE)
        self.assertIn('if(active() && !apiReady_)',SOURCE)
        self.assertIn('stopReceiver();',SOURCE)
        self.assertIn('backend_.start(binaryPath(), receiverArgs);',SOURCE)
        self.assertIn('Only an explicit Start restarts this app',SOURCE)
        self.assertNotIn('systemctl stop readsb',SOURCE)
        self.assertNotIn('killall',SOURCE)
    def test_dab_probe_checks_current_port_generation_and_retries(self):
        self.assertIn('const quint64 generation=receiverGeneration_',SOURCE)
        self.assertIn('const quint16 targetPort=port_',SOURCE)
        self.assertIn('generation!=receiverGeneration_ || targetPort!=port_',SOURCE)
        self.assertIn('apiWaitCount_<18',SOURCE)
        self.assertIn('request.setTransferTimeout(850)',SOURCE)
        self.assertIn('QLatin1String("/channel")',SOURCE)
        self.assertIn('127.0.0.1:%1',SOURCE)
    def test_no_false_rf_status_and_no_tune_before_api(self):
        self.assertIn('if (!active() || !apiReady_ || scanning_) return;',SOURCE)
        self.assertIn('if(activeChannel_!=block || !apiReady_) tune(block,ready)',SOURCE)
        self.assertIn('DAB SNR NOT MEASURED',SOURCE)
        self.assertIn('lastMux_=QJsonObject()',SOURCE)
        self.assertIn('Cannot tune DAB %1:',SOURCE)
        self.assertIn('apiFailureDetails()',SOURCE)
    def test_display_actual_usb_owner_diagnostics_without_unbinding(self):
        self.assertIn('lastWelleError_',SOURCE)
        self.assertIn('receiverGeneration_',SOURCE)
        self.assertIn('usb_claim',SOURCE)
        self.assertIn('readsb, rtl_tcp, WebUSB or a kernel DVB driver',SOURCE)
        self.assertIn('QProcess::errorOccurred',SOURCE)
        self.assertIn('QMessageBox::information(this,tr("Receiver diagnostics")',SOURCE)
        self.assertNotIn('modprobe -r',SOURCE)
        self.assertNotIn('pkill -f',SOURCE)


if __name__=="__main__":
    unittest.main()
