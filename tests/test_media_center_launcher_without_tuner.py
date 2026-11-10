"""Native launcher contract: no false held shell locks or tuner requirement.

The pinned Kaffeine app owns single-instance activation through KDE's
KDBusService::Unique. The shell wrapper must never block that IPC route,
nor require SDR/DVB devices to be attached just to display its home UI.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
INSTALL = (ROOT / "kaffeine_next/install.sh").read_text(encoding="utf-8")
PATCH = (ROOT / "kaffeine_next/patch_upstream.py").read_text(encoding="utf-8")


class LauncherWithoutAntennaTests(unittest.TestCase):
    def test_launcher_delegates_unique_instance_to_kde(self):
        self.assertIn("KDBusService::Unique", INSTALL)
        self.assertIn('QStringLiteral("tihulu-media-center")', PATCH)
        self.assertNotIn("flock -n 9", INSTALL)
        self.assertNotIn("exec 9>", INSTALL)
        self.assertNotIn("Focus or close that window first.", INSTALL)

    def test_no_auto_tuning_or_hardware_claim_at_launch(self):
        launcher = INSTALL.split("cat > \"$HOME/.local/bin/tihulu-kaffeine\" <<'LAUNCH'")[1].split(
            "\nLAUNCH",1)[0]
        self.assertIn('TIHULU_AUTOPLAY_LAST_CHANNEL:-0',launcher)
        self.assertIn('set -- --lastchannel',launcher)
        self.assertIn('env -u LD_LIBRARY_PATH',launcher)
        self.assertNotIn("rtl_test",launcher)
        self.assertNotIn("dvbv5-zap",launcher)
        self.assertNotIn("lsusb",launcher)
        self.assertNotIn("flock",launcher)

    def test_diagnostic_flag_is_still_available_without_receiver(self):
        self.assertIn("--diagnose-tuner)",INSTALL)
        self.assertIn("dvb_diagnostics.sh",INSTALL)
        self.assertIn('ln -sfn tihulu-kaffeine',INSTALL)


if __name__=="__main__":
    unittest.main()
