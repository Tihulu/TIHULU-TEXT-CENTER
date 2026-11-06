"""UI-only Text & Alerts consolidation invariants.

These checks do not pretend to validate physical DVB, Teletext, DAB or
emergency warning reception.
"""
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


class TestTextAlertsUI(unittest.TestCase):
    def test_local_menu_has_single_text_alerts_destination(self):
        html=(ROOT/"web/index.html").read_text(encoding="utf-8")
        self.assertIn('data-page="500"',html)
        self.assertIn("Text &amp; Alerts",html)
        self.assertNotIn('data-page="300"><span class="nav-icon">☁</span>',html)
        self.assertNotIn('data-page="800"><span class="nav-icon">↗</span>',html)
        self.assertIn('data-page="410"',html)
        self.assertIn('data-page="420"',html)

    def test_legacy_numbered_pages_and_tv_remain_available(self):
        app=(ROOT/"web/app.js").read_text(encoding="utf-8")
        self.assertIn("if(state.page===300) return showWeather();",app)
        self.assertIn("if(state.page===500) return showTextAndAlerts();",app)
        self.assertIn("if(state.page===800) return showDirectory();",app)
        self.assertIn("if(state.page===420) return showLiveTVPage();",app)
        self.assertIn('document.body.classList.toggle("text-alerts-mode"',app)
        css=(ROOT/"web/styles.css").read_text(encoding="utf-8")
        self.assertIn("body.text-alerts-mode #teletext-frame",css)
        self.assertIn("button(\"LEGACY WEATHER TEXT\"",app)
        self.assertIn("button(\"TEXT NETWORK DIRECTORY\"",app)

    def test_reader_preserves_real_archive_provenance(self):
        app=(ROOT/"web/app.js").read_text(encoding="utf-8")
        for expected in (
            "async function showTextAndAlerts()",
            'api("/api/events")',
            'api("/api/pages")',
            'api("/api/articles")',
            'api("/api/page?"+query.toString())',
            "DECODER IMPORT / NOT AUTHORITY VERIFIED",
            "CACHED INTERNET / NOT RF",
            'if(entry.kind==="article")return "internet";',
            "FM RadioText / RDS",
            "DAB+ Dynamic Label",
            "DVB Teletext",
            "Journaline",
            "NAVTEX maritime",
            "HF weather text",
            "DRM broadcast text",
            "APRS data",
            "No authenticated alert feed is connected"
        ):
            self.assertIn(expected,app)

    def test_no_os_driver_or_auto_receiver_work_is_added_to_reader(self):
        app=(ROOT/"web/app.js").read_text(encoding="utf-8")
        part=app.split("async function showTextAndAlerts(){",1)[1].split(
            "async function showBulletins(){",1)[0]
        self.assertNotIn("/api/dvb/scan/start",part)
        self.assertNotIn("/api/live/tv/start",part)
        self.assertNotIn("/api/auto/fm/start",part)
        self.assertNotIn("/api/dab/manage/start",part)
        self.assertNotIn("setInterval(",part)
        self.assertIn("TV application's live Teletext",part)

    def test_pages_capability_boundary(self):
        html=(ROOT/"docs/index.html").read_text(encoding="utf-8")
        js=(ROOT/"docs/pages.js").read_text(encoding="utf-8")
        self.assertIn('id="view-text"',html)
        self.assertIn('data-view="text"',html)
        self.assertIn('127.0.0.1:8787/#page=500',html)
        self.assertIn("does not have access to the local SQLite archive",html)
        self.assertIn('"text"',js)


if __name__=="__main__":
    unittest.main()
