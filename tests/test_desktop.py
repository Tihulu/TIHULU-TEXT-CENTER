import unittest
from pathlib import Path
from textcenter.desktop import browser_candidates, desktop_browser_command


class DesktopLaunchTests(unittest.TestCase):
    def test_browser_flags_use_nonshared_user_profile(self):
        c=desktop_browser_command("/bin/chromium","chromium",
          "http://127.0.0.1:8787/",Path("/tmp/tihulu-profile"))
        self.assertIn("--app=http://127.0.0.1:8787/",c)
        self.assertIn("--user-data-dir=/tmp/tihulu-profile",c)
        self.assertNotIn("--remote-debugging-port",str(c))
        f=desktop_browser_command("/usr/bin/firefox","firefox",
          "http://127.0.0.1:8787/",Path("/tmp/profile"))
        self.assertIn("--no-remote",f)
        self.assertIn("--new-window",f)
        for url in ("https://example.org/","http://0.0.0.0:8787/",
                    "http://127.0.0.1:8787/evil"):
            with self.assertRaises(ValueError):
                desktop_browser_command("/bin/chromium","chromium",url,Path("/tmp/t"))

    def test_missing_browser_is_not_silently_installed(self):
        self.assertEqual(browser_candidates(system="Linux",lookup=lambda _:None),[])
        with self.assertRaises(ValueError):
            desktop_browser_command("/bin/a","unsafe","http://127.0.0.1:8787/",Path("/tmp/profile"))


if __name__=="__main__":
    unittest.main()
