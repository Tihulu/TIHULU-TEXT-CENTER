"""Static browser-only WebUSB acceptance contract; never opens hardware."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1] / "satellite_center" / "browser"


class SatelliteBrowserStaticTests(unittest.TestCase):
    def test_page_has_direct_webusb_controls_and_clear_limits(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        for phrase in ("Choose RTL-SDR (WebUSB)", "Release USB", "Start real USB capture",
                       "browser.js", "Browser-only", "Shared Web + Desktop UI",
                       "in-browser APRS/Meteor LRPT decoding is not implemented"):
            self.assertIn(phrase, html)
        # The pass planner is shared by the installed companion and Pages/PWA.
        self.assertIn("3 · Satellite pass planner</h2>", html)
        self.assertNotIn("Satellite pass planner (web-only)", html)
        self.assertIn('href="http://127.0.0.1:8791/"', html)
        self.assertNotIn("../companion/", html)
        for required in ('id="orbit-fetch"', 'id="orbit-calc"', 'id="tle-file"',
                         'id="location-gps"', 'id="earth-world-canvas"',
                         'id="iq-analysis"'):
            self.assertIn(required, html)
        companion_source = (ROOT.parent / "__main__.py").read_text(encoding="utf-8")
        self.assertIn('WEB_ASSETS = PAGE.parent/"browser"', companion_source)
        self.assertIn('if route.startswith("/browser/"):', companion_source)
        self.assertNotIn("pair-token", html)
        self.assertNotIn("localhost:8791", html)
        # The page may document the OPTIONAL companion URL, but its
        # browser-only entry point must not silently connect to localhost.
        js = (ROOT / "browser.js").read_text(encoding="utf-8")
        self.assertNotIn('fetch("http://127.0.0.1:8791', js)
        self.assertNotIn("127.0.0.1:8791/api/capture", js)

    def test_cross_platform_satellite_images_data_tab(self):
        reception=(ROOT / "reception.html").read_text(encoding="utf-8")
        html=(ROOT / "index.html").read_text(encoding="utf-8")
        script=(ROOT / "reception.mjs").read_text(encoding="utf-8")
        catalog=(ROOT / "reception_catalog.mjs").read_text(encoding="utf-8")
        for asset in ("reception.html", "reception.css", "reception.mjs",
                      "reception_catalog.mjs"):
            self.assertTrue((ROOT / asset).is_file(), asset)
        self.assertIn('href="./reception.html"', html)
        self.assertIn('Satellite Images &amp; Data', reception)
        self.assertIn('id="local-file"', reception)
        self.assertIn('id="mission"', reception)
        self.assertIn('id="export-evidence"', reception)
        for ctl in ('auto-mission-arm', 'auto-mission-analyze',
                    'auto-mission-extract', 'auto-gps', 'auto-lat', 'auto-lon'):
            self.assertIn('id="' + ctl + '"', reception)
        for ctl in ('auto-plan', 'auto-analyze', 'auto-results', 'auto-mode'):
            self.assertIn('id="' + ctl + '"', html)
        self.assertIn('auto_reception_ui.mjs', script)
        self.assertIn('id="auto-mission-stop"', reception)
        self.assertIn('id="auto-stop"', html)
        self.assertIn('route == "/api/auto-cancel"', (ROOT.parent / "__main__.py").read_text(encoding="utf-8"))

        receiver=(ROOT / "browser.js").read_text(encoding="utf-8")
        self.assertIn('selectAutomaticPasses(', receiver)
        self.assertIn('runAutoMission(', receiver)
        backend=(ROOT.parent / "__main__.py").read_text(encoding="utf-8")
        self.assertIn('def auto_schedule(', backend)
        self.assertIn('route == "/api/auto-schedule"', backend)
        self.assertIn('str(PROFILES[profile]["freq"])', backend)

        for control in ('image-target', 'image-decode-sstv', 'image-decode-cuiq',
                        'image-sstv-file', 'image-cuiq-file', 'image-fetch-online',
                        'image-gallery', 'image-local-gallery', 'image-decode-status'):
            self.assertIn('id="' + control + '"', reception)
        self.assertIn('initSatelliteImageUI', script)
        self.assertIn('satellite_images_ui.mjs', script)
        self.assertIn('http://127.0.0.1:8791/', reception)
        self.assertIn("URL.revokeObjectURL", script)
        self.assertIn("source:\"user-imported_unverified\"", catalog)
        self.assertIn("retired", catalog)
        self.assertIn("meteor-m2-3", catalog)
        self.assertIn("iss-sstv", catalog)
        self.assertIn("image-target", (ROOT / "browser.js").read_text(encoding="utf-8"))
        native=(ROOT.parent / "index.html").read_text(encoding="utf-8")
        self.assertIn('./browser/reception.html', native)

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
