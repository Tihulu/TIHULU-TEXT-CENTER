"""Static Pages integration gates; not a physical RF receiver acceptance."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]

class PagesWebUSBTests(unittest.TestCase):
    def test_pages_exposes_real_browser_controls(self):
        page=(ROOT/"docs/index.html").read_text()
        script=(ROOT/"docs/webusb-radio.js").read_text()
        for name in ("usb-connect","usb-stop","usb-start","view-usb","usb-capture-status"):
            self.assertIn('id="'+name+'"',page)
        self.assertIn("navigator.usb",script)
        self.assertIn("provider.get()",script)
        self.assertIn("receiver.readSamples",script)
        self.assertIn("await owned.close()",script)
        self.assertIn("pagehide",script)
        self.assertIn("AudioWorklet",script)
        self.assertIn("Experimental",page)
    def test_pages_pwa_and_satellite_mirror(self):
        worker=(ROOT/"docs/sw.js").read_text()
        self.assertIn("webusb-radio.js",worker)
        self.assertTrue((ROOT/"docs/satellite/browser.js").is_file())
        self.assertTrue((ROOT/"docs/satellite/index.html").is_file())

if __name__=="__main__":
    unittest.main()
