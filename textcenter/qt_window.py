"""Optional native desktop window backed by Qt WebEngine (no external browser).

This component is loaded only for graphical desktop mode, never during
headless server/tests and never during RF scanning. PySide6 (QtWebEngine)
is an optional GUI dependency: lack of the package must not break the
standard no-dependencies text web server.
"""
from __future__ import annotations

import os
import sys


class QtWindowUnavailable(RuntimeError):
    pass


def native_window_available():
    if sys.platform.startswith("linux") and not (
        os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")
    ):
        return False
    try:
        from PySide6.QtWidgets import QApplication  # noqa: F401
        from PySide6.QtWebEngineWidgets import QWebEngineView  # noqa: F401
    except (ImportError,OSError):
        return False
    return True


def run_qt_window(url):
    if not url.startswith("http://127.0.0.1:") or not url.endswith("/"):
        raise ValueError("Qt window may load only local Text Center backend")
    if not native_window_available():
        raise QtWindowUnavailable(
            "Native QtWebEngine unavailable. Install the optional PySide6 Qt WebEngine "
            "package in an isolated Python environment, or use the fallback app window."
        )
    from PySide6.QtCore import QUrl,Qt
    from PySide6.QtWidgets import QApplication,QMainWindow
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWebEngineCore import QWebEngineProfile,QWebEnginePage

    owned=QApplication.instance() is None
    app=QApplication.instance() or QApplication([sys.argv[0]])
    app.setApplicationName("TIHULU Text Center")
    window=QMainWindow()
    window.setWindowTitle("TIHULU Text Center — Radio, TV & Text")
    window.resize(1250,850)
    window.setMinimumSize(420,440)
    view=QWebEngineView(window)
    # Off-the-record, no disk-resident browsing cache/cookies. All actual
    # user data and recordings stay in the Text Center SQLite archive.
    profile=QWebEngineProfile(window)
    profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.MemoryHttpCache)
    profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies)
    page=QWebEnginePage(profile,view)
    view.setPage(page)
    window.setCentralWidget(view)
    view.setUrl(QUrl(url))
    window.show()
    if owned:
        return app.exec()
    # This is the primary user-facing desktop entry point, not an embedded
    # plugin in another Qt application; an existing QApplication must own
    # its event loop. Avoid silently returning and closing the server.
    raise QtWindowUnavailable("Text Center must own its Qt event loop in desktop mode")
