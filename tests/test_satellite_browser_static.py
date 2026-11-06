"""Static browser-only WebUSB acceptance contract; never opens hardware."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1] / "satellite_center" / "browser"


class SatelliteBrowserStaticTests(unittest.TestCase):
    def test_page_has_direct_webusb_controls_and_clear_limits(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        for phrase in ("Choose RTL-SDR (WebUSB)", "Release USB", "Start real USB capture",
                       "browser.js", "Browser-only", "No local app",
                       "in-page APRS/SSTV/Meteor image decoding is not connected yet"):
            self.assertIn(phrase, html)
        self.assertNotIn("pair-token", html)
        self.assertNotIn("localhost:8791", html)
        # The page may document the OPTIONAL companion URL, but its
        # browser-only entry point must not silently connect to localhost.
        js = (ROOT / "browser.js").read_text(encoding="utf-8")
        self.assertNotIn('fetch("http://127.0.0.1:8791', js)
        self.assertNotIn("127.0.0.1:8791/api/capture", js)

    def test_real_iq_capture_not_fabricated(self):
        script = (ROOT / "browser.js").read_text(encoding="utf-8")
        # The WebUSB provider now receives a browser-only USB adapter,
        # so the bare constructor from the early prototype is obsolete.
        self.assertIn("new driver({webusb})", script)
        self.assertIn("await provider.get()", script)
        self.assertIn("await device.readSamples(", script)
        self.assertIn("await previous.close()", script)
        self.assertIn("window.addEventListener('pagehide'", script)
        self.assertIn("document.addEventListener('visibilitychange'", script)
        self.assertIn("maxRecordBytes = 128 * 1024 * 1024", script)
        self.assertNotIn("/api/capture", script)
        self.assertNotIn("Math.random", script)

    def test_orbits_from_real_tle_and_not_rf_identification(self):
        script = (ROOT / "browser.js").read_text(encoding="utf-8")
        self.assertIn("celestrak.org/NORAD/elements/gp.php?", script)
        self.assertIn("satellite.js@6.0.1", script)
        self.assertIn("satlib.twoline2satrec", script)
        self.assertIn("satlib.ecfToLookAngles", script)
        self.assertIn("2*3600000", script)
        # Due work now uses an explicit foreground/receiver-busy state
        # machine; a stale inline conditional would miss those checks.
        self.assertIn("evaluateScheduledJob(job,now", script)
        self.assertIn("visible:!document.hidden", script)
        self.assertIn("receiverBusy:!!capturePromise||usbTestRunning", script)
        self.assertIn("await connectDevice({silent:true})", script)


if __name__ == "__main__":
    unittest.main()
