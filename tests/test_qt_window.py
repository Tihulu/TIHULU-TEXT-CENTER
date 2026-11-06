import unittest
from textcenter.qt_window import run_qt_window,QtWindowUnavailable


class QtDesktopTests(unittest.TestCase):
    def test_native_gui_forbids_nonlocal_url_even_without_qt_installed(self):
        for url in ("https://tihulu.github.io/","http://0.0.0.0:8787/","file:///etc/passwd"):
            with self.assertRaises(ValueError):
                run_qt_window(url)


if __name__=="__main__":
    unittest.main()
