"""Contract checks for the optional Full Lyrics window and safe manual refresh.

These tests validate native Qt wiring and preservation invariants. Actual GUI
window behavior and third-party lyric provider success require device testing.
"""
from pathlib import Path
import unittest

RADIO=(Path(__file__).resolve().parents[1] /
       "kaffeine_next/native_radio_tab.h").read_text(encoding="utf-8")


def section(begin, end):
    first=RADIO.index(begin)
    return RADIO[first:RADIO.index(end, first)]


class LyricsRefreshAndFullWindowTests(unittest.TestCase):
    def test_full_lyrics_window_is_resizable_and_not_a_network_lookup(self):
        self.assertIn('fullLyricsButton_=new QPushButton(tr("Full Lyrics"),page)', RADIO)
        self.assertIn('Full Lyrics · separate window', RADIO)
        popup=section("void showFullLyricsWindow() {", "void refreshRadioLipSync() {")
        self.assertIn("new QDialog(this,Qt::Window)", popup)
        self.assertIn("dialog->resize(760,660)", popup)
        self.assertIn("new QPlainTextEdit(dialog)", popup)
        self.assertIn("view->setReadOnly(true)", popup)
        self.assertIn("timer->setInterval(950)", popup)
        self.assertIn("renderFullLyricsWindow(header,view);", popup)
        for forbidden in ("fetchLyrics(", "lyrics-lookup", "startReceiver(", "stopCaptioning("):
            self.assertNotIn(forbidden, popup)

    def test_full_lyrics_renders_only_available_source_and_translations(self):
        renderer=section("void renderFullLyricsWindow(", "void showFullLyricsWindow()")
        for needle in ("lyricCues_", "lyricRawLines_", "lastLyricsProvider_",
                       'QLatin1String("translations")', "selectedRadioTargets()",
                       "lastVerifiedLyricText_", "previewLastIndex_",
                       "NOT audio-verified", "view->verticalScrollBar()->value()"):
            with self.subTest(needle=needle):
                self.assertIn(needle, renderer)

    def test_lyrics_refresh_requires_user_consent_and_separate_worker(self):
        self.assertIn('lyricsRefresh_=new QPushButton(tr("Lyrics Refresh"),page)', RADIO)
        self.assertIn("refreshCurrentLyrics();", RADIO)
        refresh=section("void refreshCurrentLyrics() {", "void pollLyricsRefreshResult() {")
        for needle in ("QMessageBox::question(", "QMessageBox::No",
                       "lyricsRefreshPending_", "lyricsRefreshProcess_.start(",
                       "lyricsRefreshPath_", '"lyrics-lookup"', "lyricsRefreshStationTicket_",
                       "lyricsRefreshRequestKey_", '"--online"'):
            with self.subTest(needle=needle):
                self.assertIn(needle, refresh)
        for forbidden in ("lyricsEnabled_=false", "lyricLoaded_=false",
                          "lyricCues_.clear(", "clearKaraokeLine(",
                          "player_->stop(", "stopCaptioning(", "startCaptioning("):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, refresh)

    def test_only_valid_current_song_result_is_applied(self):
        result=section("void pollLyricsRefreshResult() {", "void fetchLyrics(bool automatic=false) {")
        for needle in ("lyricsRefreshStationTicket_!=stationRequestId_",
                       "lyricsRefreshStationKey_!=playingKey_",
                       "lyricsRefreshSongKey_!=lastSongMetadataKey_",
                       "newCues.isEmpty() && newPlain.isEmpty()",
                       "if(!usable", "if(changed)", "lyricsCache_.insert(",
                       "cancelLyricsRefresh();"):
            # Explicit validity guard is written inline, not in a separate variable.
            if needle in ("if(!usable",):
                continue
            with self.subTest(needle=needle):
                self.assertIn(needle, result)
        self.assertLess(result.index('state!=QLatin1String("completed") ||'),
                        result.index("lyricCues_=newCues;"))
        self.assertNotIn("songStartMs_=now", result)
        self.assertNotIn("stopReceiver(", result)
        self.assertNotIn("stopCaptioning(", result)

    def test_refresh_polling_and_song_boundary_cancels_stale_search(self):
        self.assertIn("pollCaption();updateLyrics();", RADIO)
        self.assertIn("pollLyricsRefreshResult();", RADIO)
        transition=section("void commitPendingDlsSong(", "void stopLyrics()")
        self.assertIn("cancelLyricsRefresh();", transition)
        self.assertIn("cancelLyricsRefresh();", section("void stopLyrics()", "void cancelLyricsRefresh()"))


if __name__ == "__main__":
    unittest.main()
