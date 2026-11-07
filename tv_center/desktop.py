"""Native Qt Widgets television application for Debian/Ubuntu/Pop!_OS/Pi OS.

No embedded browser, WebUSB, libVLC or hidden polling. MPV is embedded as a
separate native X11 child window; on Wayland set QT_QPA_PLATFORM=xcb.
"""
from __future__ import annotations
from pathlib import Path
import json
import os
import tempfile
import queue
import subprocess
import sys
import threading

from . import __version__
from .core import TVCapture, discover_channels, read_channels, receiver_status, parse_signal_log, format_frequency, Channel
from .bridge import TVBridge
from .captions import install_argos_pack
from .scanner import AutoScanner, ScanError, PROFILES, MODES
from .satellite import SATELLITES, satellite_hardware_note
from .channel_prefs import ChannelPreferences, profile_key
from .ai_settings import AISettings
from .channels_ui import edit_channels
from .settings_ui import open_ai_settings
from .scan_ui import ScanMonitor

def main():
    if os.environ.get("WAYLAND_DISPLAY"):
        os.environ.setdefault("QT_QPA_PLATFORM", "xcb")
    try:
        from PyQt5.QtCore import Qt, QTimer
        from PyQt5.QtWidgets import (
            QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel,
            QPushButton, QListWidget, QComboBox, QSpinBox, QFileDialog, QLineEdit,
            QMessageBox, QSplitter, QGroupBox, QFormLayout, QCheckBox, QInputDialog
        )
    except ImportError:
        print("Qt desktop dependency missing: sudo apt install python3-pyqt5", file=sys.stderr)
        return 2

    class Window(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("TIHULU TV Center · Native DVB")
            self.resize(1280, 795)
            self.capture = TVCapture()
            self.scanner = AutoScanner()
            self.ai = AISettings()
            self.ai.configure_environment()
            self.preferences = ChannelPreferences()
            self.scan_monitor = None
            self.bridge = None
            self.latest = {"original": "", "translated": "", "source": "none"}
            self.channels = []
            self.setStyleSheet("""
                QMainWindow, QWidget { background: #111827; color: #e2e8f0; font-size: 13px; }
                QGroupBox { border: 1px solid #334155; border-radius: 7px; margin-top: 12px;
                            padding-top: 12px; font-weight: bold; }
                QPushButton { background: #243448; border: 1px solid #36516c; border-radius: 5px;
                              padding: 7px 11px; color: #f1f5f9; }
                QPushButton:hover { background: #385473; }
                QComboBox, QLineEdit, QSpinBox, QListWidget {
                    background: #192535; border: 1px solid #39485a; padding: 5px;
                    selection-background-color: #1e749a; color: #e2e8f0; }
                QLabel#caption { background: #080f1b; border-radius: 6px; padding: 12px;
                                 color: #fff; font-size: 17px; }
            """)
            root = QWidget()
            self.setCentralWidget(root)
            outer = QVBoxLayout(root)
            title = QLabel("TIHULU  /  TV CENTER")
            title.setStyleSheet("font-size: 23px; font-weight: bold; color: #70d6ed;")
            outer.addWidget(title)
            splitter = QSplitter(Qt.Horizontal)
            outer.addWidget(splitter, 1)
            left = QWidget()
            left.setMaximumWidth(325)
            splitter.addWidget(left)
            l = QVBoxLayout(left)
            self.devices = QLabel("Receiver status pending")
            self.devices.setWordWrap(True)
            l.addWidget(self.devices)
            self.adapter_choice = QComboBox()
            available = sorted(Path("/dev/dvb").glob("adapter*/frontend0"))
            for path in available:
                number = int(path.parent.name.replace("adapter", ""))
                self.adapter_choice.addItem("DVB adapter " + str(number), number)
            if not available:
                self.adapter_choice.addItem("DVB adapter 0 (not detected)", 0)
            self.adapter_choice.currentIndexChanged.connect(self.change_adapter)
            l.addWidget(self.adapter_choice)
            self.channel_list = QListWidget()
            self.channel_list.itemDoubleClicked.connect(lambda *_: self.play())
            l.addWidget(self.channel_list, 1)
            import_btn = QPushButton("Import DVBv5 channel file")
            import_btn.clicked.connect(self.import_channels)
            l.addWidget(import_btn)
            self.country = QComboBox()
            self.country.addItem("Germany (DE)", "DE")
            self.country.addItem("Türkiye (TR)", "TR")
            self.country.currentIndexChanged.connect(self.refresh_channels)
            l.addWidget(self.country)
            self.delivery = QComboBox()
            self.delivery.addItem("Antenna · DVB-T / DVB-T2", "t")
            self.delivery.addItem("Cable · DVB-C", "c")
            self.delivery.addItem("Satellite dish · DVB-S/S2", "s")
            self.delivery.currentIndexChanged.connect(self.update_delivery)
            l.addWidget(self.delivery)
            self.satellite = QComboBox()
            for orbital, label in SATELLITES.items():
                self.satellite.addItem(label, orbital)
            self.satellite.currentIndexChanged.connect(self.refresh_channels)
            l.addWidget(self.satellite)
            self.diseqc = QComboBox()
            self.diseqc.addItem("LNB direct · no DiSEqC switch", None)
            for port in range(4):
                self.diseqc.addItem("DiSEqC port " + str(port + 1), port)
            l.addWidget(self.diseqc)
            self.satellite.setVisible(False)
            self.diseqc.setVisible(False)
            scan_btn = QPushButton("🔎 Automatic full channel scan")
            scan_btn.clicked.connect(self.scan_channels)
            l.addWidget(scan_btn)
            self.stop_scan_btn = QPushButton("Cancel running scan")
            self.stop_scan_btn.setEnabled(False)
            self.stop_scan_btn.clicked.connect(self.cancel_scan)
            l.addWidget(self.stop_scan_btn)
            self.list_origin = QLabel("Previously saved frequencies. Run automatic scan to verify.")
            self.list_origin.setWordWrap(True)
            l.addWidget(self.list_origin)
            manager_btn = QPushButton("Manage scanned channels · ★ Favorites")
            manager_btn.clicked.connect(self.open_channel_manager)
            l.addWidget(manager_btn)
            manual_btn = QPushButton("Advanced · Scan from frequency file")
            manual_btn.clicked.connect(self.scan_from_file)
            l.addWidget(manual_btn)
            self.signal_btn = QPushButton("Measure current signal · 15 s")
            self.signal_btn.clicked.connect(self.measure_signal)
            l.addWidget(self.signal_btn)
            self.signal_result = QLabel("C/N and UCB: not yet measured")
            self.signal_result.setWordWrap(True)
            l.addWidget(self.signal_result)
            self.play_btn = QPushButton("▶  Play selected channel")
            self.play_btn.clicked.connect(self.play)
            l.addWidget(self.play_btn)
            stop_btn = QPushButton("■  Stop / release tuner")
            stop_btn.clicked.connect(self.stop)
            l.addWidget(stop_btn)

            right = QWidget()
            splitter.addWidget(right)
            r = QVBoxLayout(right)
            self.video = QWidget()
            self.video.setAttribute(Qt.WA_NativeWindow, True)
            self.video.setMinimumSize(540, 305)
            self.video.setStyleSheet("background: black;")
            r.addWidget(self.video, 5)
            self.subtitle = QLabel("Captions off — video is real local DVB, never a demo stream.")
            self.subtitle.setObjectName("caption")
            self.subtitle.setWordWrap(True)
            self.subtitle.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
            self.subtitle.setMinimumHeight(70)
            r.addWidget(self.subtitle)
            self.settings_button = QPushButton("Settings · Model Market · CPU / GPU / NPU")
            self.settings_button.clicked.connect(self.open_ai_settings)
            r.addWidget(self.settings_button)
            controls = QGroupBox("Broadcast subtitles · Interactive Teletext · Offline speech / translation")
            r.addWidget(controls, 3)
            form = QFormLayout(controls)
            self.mode = QComboBox()
            self.mode.addItems(["Off", "Broadcast Teletext", "Live transcription", "Teletext first → ASR fallback", "Teletext page viewer"])
            self.mode.currentIndexChanged.connect(self.apply_mode)
            form.addRow("Subtitle source", self.mode)
            self.page = QSpinBox()
            self.page.setRange(100, 899)
            self.page.setValue(150)
            self.page.valueChanged.connect(self.apply_mode)
            form.addRow("Teletext page (100–899)", self.page)
            self.lang_in = QComboBox()
            self.lang_in.addItems(["de", "en", "tr"])
            self.lang_in.currentIndexChanged.connect(self.apply_mode)
            form.addRow("Broadcast / speech language", self.lang_in)
            self.lang_out = QComboBox()
            self.lang_out.addItems(["tr", "de", "en"])
            self.lang_out.currentIndexChanged.connect(self.apply_mode)
            form.addRow("Subtitle output language", self.lang_out)
            self.model = QLineEdit(self.ai.values["model_path"])
            self.model.setPlaceholderText("Select an installed multilingual GGML Whisper model")
            self.model.editingFinished.connect(self.apply_mode)
            browse = QPushButton("Choose offline ASR model…")
            browse.clicked.connect(self.choose_model)
            form.addRow(browse, self.model)
            pack = QPushButton("Install local .argosmodel language pack…")
            pack.clicked.connect(self.install_pack)
            form.addRow("Offline translation", pack)
            self.hw = QComboBox()
            self.hw.addItems(["no", "auto-safe"])
            form.addRow("MPV hardware decode (next tune)", self.hw)
            self.renderer = QComboBox()
            self.renderer.addItems(["x11-gpu", "x11-compat"])
            form.addRow("Embedded video renderer", self.renderer)
            self.bridge_toggle = QCheckBox("Enable token-protected local web bridge")
            self.bridge_toggle.toggled.connect(self.toggle_bridge)
            form.addRow("GitHub Pages / local web", self.bridge_toggle)
            self.bridge_token = QLineEdit()
            self.bridge_token.setReadOnly(True)
            self.bridge_token.setPlaceholderText("Bridge OFF — no local server")
            form.addRow("Temporary bridge token", self.bridge_token)
            self.statusbar = QLabel("Idle. No active tuner or AI worker.")
            self.statusbar.setWordWrap(True)
            outer.addWidget(self.statusbar)
            splitter.setSizes([280, 890])
            self.refresh_channels()
            self.update_device_status()
            self.timer = QTimer(self)
            self.timer.timeout.connect(self.poll)
            self.timer.start(250)

        def update_device_status(self):
            s = receiver_status(self.capture.adapter)
            self.devices.setText("DVB frontend: " + ("connected" if s["frontend_present"] else "missing")
                                 + "  |  WinTV USB 2040:8268: " + ("detected" if s["win_tv_solohd_usb_present"] else "not seen")
                                 + "  |  Si2168 D60 firmware: " + ("yes" if s["si2168_d60_firmware_present"] else "no")
                                 + "  |  MPV: " + ("yes" if s["mpv"] else "no")
                                 + "  |  ffmpeg: " + ("yes" if s["ffmpeg"] else "no"))

        def change_adapter(self):
            if self.capture.thread and self.capture.thread.is_alive():
                self.statusbar.setText("Stop playback before switching the DVB adapter.")
                return
            self.capture.adapter = int(self.adapter_choice.currentData() or 0)
            self.update_device_status()

        def measure_signal(self):
            if not (self.capture.zap and self.capture.zap.poll() is None):
                self.signal_result.setText("Tune a live DVB channel before measuring.")
                return
            if not receiver_status(self.capture.adapter)["frontend_present"]:
                self.signal_result.setText("DVB frontend unavailable.")
                return
            self.signal_result.setText("Measuring receiver… do not move antenna during each comparison.")
            adapter = self.capture.adapter
            def worker():
                try:
                    p = subprocess.run(["dvb-fe-tool", "-a", str(adapter), "-m"],
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       timeout=15, check=False)
                    raw = p.stdout.decode("utf-8", "replace")
                except subprocess.TimeoutExpired as exc:
                    raw = (exc.stdout or b"").decode("utf-8", "replace")
                except OSError as exc:
                    self.capture.emit("measurement", {"error": str(exc)})
                    return
                self.capture.emit("measurement", parse_signal_log(raw))
            threading.Thread(target=worker, daemon=True, name="tihulu-tv-signal").start()

        def update_delivery(self, *_):
            satellite = self.delivery.currentData() == "s"
            self.satellite.setVisible(satellite)
            self.diseqc.setVisible(satellite)
            self.refresh_channels()

        def current_profile(self):
            country, medium = self.country.currentData(), self.delivery.currentData()
            return profile_key(country, medium, self.satellite.currentData() if medium == "s" else "")

        def refresh_channels(self, *_):
            country, medium = self.country.currentData(), self.delivery.currentData()
            profile = self.current_profile()
            expected = Path.home() / ".config/tihulu-tv-center" / ("channels-" + profile + ".conf")
            if expected.is_file():
                scanned = read_channels([expected])
                source_label = f"Saved verified scan · {profile}"
            elif country == "DE" and medium == "t":
                scanned = discover_channels()
                source_label = "Historical Germany channel imports · NOT a fresh automatic scan"
            else:
                scanned = []
                source_label = f"No scan for {profile} — run Automatic full channel scan"
            self.all_channels = sorted(scanned, key=lambda c: (c.frequency, c.name.casefold()))
            curated = self.preferences.rows(profile, self.all_channels)
            self.current_rows = curated
            self.visible_rows = [r for r in curated if r["included"]]
            self.channels = [r["channel"] for r in self.visible_rows]
            self.channel_list.clear()
            for row in self.visible_rows:
                c = row["channel"]
                star = "★ " if row["favorite"] else ""
                category = "RADIO" if row["kind"] == "radio" else "TV"
                encrypted = " 🔒" if c.encrypted else ""
                self.channel_list.addItem(f"{star}{c.name} · {category} · {format_frequency(c)}{encrypted}")
            new_count = sum(1 for r in curated if r["new"])
            self.list_origin.setText(f"{source_label}\n{len(self.all_channels)} scanned · "
                                     f"{len(self.channels)} included · {new_count} awaiting review")
            if not self.scanner.running:
                self.statusbar.setText(source_label)

        def open_channel_manager(self):
            if not getattr(self, "all_channels", []):
                QMessageBox.information(self, "No channels", "Scan first or import an existing channel file.")
                return
            if edit_channels(self, self.preferences, self.current_profile(), self.all_channels):
                self.refresh_channels()

        def open_ai_settings(self):
            open_ai_settings(self, self.ai, self.sync_ai_settings)

        def sync_ai_settings(self):
            self.model.setText(self.ai.values["model_path"])
            self.apply_mode()
            self.statusbar.setText("AI settings saved. Transcription/translation operate only when enabled.")

        def import_channels(self):
            file, _ = QFileDialog.getOpenFileName(
                self, "Choose DVBv5 channels.conf", str(Path.home()),
                "DVBv5 config (*.conf);;All files (*)")
            if not file:
                return
            target = Path.home() / ".config/tihulu-tv-center/channels.conf"
            target.parent.mkdir(parents=True, exist_ok=True)
            from shutil import copyfile
            if Path(file).resolve() != target.resolve():
                copyfile(file, target)
            self.refresh_channels()

        def scan_channels(self):
            if self.scanner.running:
                QMessageBox.information(self, "Scan running", "A scan is already active.")
                return
            if self.capture.thread and self.capture.thread.is_alive():
                QMessageBox.warning(self, "Receiver busy", "Stop live TV before scanning.")
                return
            country, medium = self.country.currentData(), self.delivery.currentData()
            satellite = self.satellite.currentData() if medium == "s" else "S42E0"
            port = self.diseqc.currentData() if medium == "s" else None
            adapter = self.capture.adapter
            label = (SATELLITES[satellite] + " · DVB-S/S2" if medium == "s" else
                     f"{PROFILES[country]['name']} · {MODES[medium]}")
            if medium == "s":
                question = (label + "\n\n" + satellite_hardware_note() +
                            "\n\nOnly continue with a dedicated DVB-S/S2 tuner connected to the LNB.")
            else:
                question = (label + "\n\nScan the real connected antenna/cable now?")
            if QMessageBox.question(self, "Automatic full scan",
                question + "\n\nExisting channels and favorites are preserved if no results are found."
            ) != QMessageBox.Yes:
                return
            self.stop_scan_btn.setEnabled(True)
            self.scan_monitor = ScanMonitor(self, self.cancel_scan, label)
            self.scan_monitor.show()
            self.statusbar.setText(label + " · scanning")
            def worker():
                try:
                    result = self.scanner.run(
                        country, medium, adapter, satellite=satellite, diseqc_port=port,
                        notify=lambda obj: self.capture.emit("scan_progress", obj))
                    self.capture.emit("scan", (True, f"{result['channels']} services on "
                                        f"{result['frequencies']} real frequencies ({label})"))
                except (ScanError, ValueError, OSError, RuntimeError) as exc:
                    self.capture.emit("scan", (False, str(exc)))
            threading.Thread(target=worker, daemon=True, name="tihulu-tv-auto-scan").start()

        def cancel_scan(self):
            self.scanner.cancel()
            self.stop_scan_btn.setEnabled(False)
            self.statusbar.setText("Cancelling scan; existing channel lists remain preserved")

        def scan_from_file(self):
            if self.delivery.currentData() == "s":
                QMessageBox.information(self, "Satellite scanning",
                    "Use the Satellite automatic scan so LNB/DiSEqC settings are applied.")
                return
            if self.scanner.running or (self.capture.thread and self.capture.thread.is_alive()):
                QMessageBox.warning(self, "Receiver busy", "Stop TV or automatic scan first.")
                return
            initial, _ = QFileDialog.getOpenFileName(
                self, "Choose genuine initial transponder file (advanced mode)",
                "/usr/share/dvb", "Initial scan data (*);;All files (*)")
            if not initial:
                return
            target = Path.home() / ".config/tihulu-tv-center/channels.conf"
            target.parent.mkdir(parents=True, exist_ok=True)
            country, adapter = self.country.currentData(), self.capture.adapter
            self.statusbar.setText("Advanced scan in progress (existing results preserved on failure)")
            def worker():
                try:
                    with tempfile.TemporaryDirectory(prefix="tihulu-tv-manual-") as tmp:
                        staged = Path(tmp) / "channels.conf"
                        p = subprocess.run(["dvbv5-scan", "-a", str(adapter), "-C", country,
                                            "-T", "5", "-o", str(staged), initial],
                                           capture_output=True, text=True, timeout=600, check=False)
                        if p.returncode != 0 or not read_channels([staged]):
                            self.capture.emit("scan", (False, p.stderr[-500:] or "No channels found"))
                        else:
                            import shutil
                            shutil.copyfile(staged, target)
                            self.capture.emit("scan", (True, "Advanced scan saved " + str(target)))
                except (OSError, subprocess.TimeoutExpired) as exc:
                    self.capture.emit("scan", (False, str(exc)))
            threading.Thread(target=worker, daemon=True).start()

        def play(self):
            idx = self.channel_list.currentRow()
            if not 0 <= idx < len(self.channels):
                QMessageBox.information(self, "Select a channel", "Choose a channel from the list.")
                return
            self.stop()
            try:
                self.capture.start(self.channels[idx], int(self.video.winId()), self.hw.currentText(),
                                   self.renderer.currentText())
                self.apply_mode()
            except (RuntimeError, OSError, ValueError) as exc:
                QMessageBox.warning(self, "TV receiver", str(exc))

        def stop(self):
            self.capture.stop()

        def choose_model(self):
            file, _ = QFileDialog.getOpenFileName(self, "Select installed multilingual Whisper GGML model", str(Path.home()), "Whisper GGML models (*.bin);;All files (*)")
            if file:
                self.model.setText(file)
                self.ai.update({"model_path": file})
                self.ai.configure_environment()
                self.apply_mode()

        def install_pack(self):
            file, _ = QFileDialog.getOpenFileName(self, "Install offline Argos language pack", str(Path.home()), "Argos packages (*.argosmodel)")
            if not file:
                return
            if QMessageBox.question(self, "Install local package", "Install the selected local translation package? No network download occurs.") != QMessageBox.Yes:
                return
            try:
                name = install_argos_pack(file)
                QMessageBox.information(self, "Installed", name + " installed for offline translation.")
            except (ImportError, RuntimeError, OSError, ValueError) as exc:
                QMessageBox.warning(self, "Translation pack", str(exc))

        def apply_mode(self, *_):
            modes = ["off", "teletext", "asr", "auto", "page"]
            mode = modes[self.mode.currentIndex()]
            if mode in ("asr", "auto") and not self.ai.values["asr_enabled"]:
                self.statusbar.setText("ASR is optional and OFF. Enable in Settings → Model Market.")
                mode = "off" if mode == "asr" else "teletext"
            target = (self.lang_out.currentText() if self.ai.values["translation_enabled"]
                      else self.lang_in.currentText())
            self.capture.set_captions(mode, self.page.value(),
                                      self.lang_in.currentText(), target,
                                      self.model.text())

        def snapshot(self):
            return {"source": "live_native_dvb" if self.capture.zap and self.capture.zap.poll() is None else "offline",
                    "channel": self.capture.channel.name if self.capture.channel else None,
                    "caption": dict(self.latest),
                    "subtitle_mode": self.capture.caption_mode,
                    "teletext_page": self.capture.page,
                    "supported_languages": ["tr", "de", "en"],
                    "web_video": "not_available_in_pages_preview",
                    "pi5_hardware_verified": False}

        def toggle_bridge(self, enabled):
            if enabled:
                try:
                    self.bridge = TVBridge(self.snapshot, lambda p: self.capture.set_captions(
                        "page", p, self.lang_in.currentText(), self.lang_out.currentText(), self.model.text()))
                    info = self.bridge.start()
                    self.bridge_token.setText(info["token"])
                    self.statusbar.setText("Local bridge: " + info["url"] + " — loopback only")
                except OSError as exc:
                    self.bridge_toggle.blockSignals(True)
                    self.bridge_toggle.setChecked(False)
                    self.bridge_toggle.blockSignals(False)
                    QMessageBox.warning(self, "Web bridge", str(exc))
            elif self.bridge:
                self.bridge.stop()
                self.bridge = None
                self.bridge_token.clear()

        def poll(self):
            for _ in range(15):
                try:
                    kind, info = self.capture.events.get_nowait()
                except queue.Empty:
                    break
                if kind == "caption":
                    self.latest = info
                    self.subtitle.setText((info.get("translated") or info["original"])
                                          + "\n" + ("Source: " + info.get("source", "unknown")))
                elif kind == "scan_progress":
                    if isinstance(info, dict) and self.scan_monitor:
                        self.scan_monitor.feed(info)
                        if info.get("kind") == "status":
                            self.statusbar.setText(info.get("text", "Scanning…"))
                elif kind == "scan":
                    ok, message = info
                    self.stop_scan_btn.setEnabled(False)
                    if self.scan_monitor:
                        self.scan_monitor.feed({"kind": "complete" if ok else "failed",
                                                "count": len(getattr(self.scan_monitor, "seen", [])),
                                                "text": message})
                    self.refresh_channels()
                    self.statusbar.setText("Scan: " + ("completed" if ok else "failed") + " — " + message)
                    if ok:
                        self.open_channel_manager()
                elif kind == "measurement":
                    if "error" in info:
                        self.signal_result.setText("Signal tool error: " + info["error"])
                    else:
                        self.signal_result.setText(
                            f"C/N: {info['cn_min_db']}–{info['cn_max_db']} dB | "
                            f"UCB change: {info['ucb_delta']} | "
                            f"Loss indications: {info['loss_indications']} | "
                            f"Readings: {info['lock_readings']}")
                elif kind in ("status", "warning", "error"):
                    self.statusbar.setText(str(info))

        def closeEvent(self, event):
            self.scanner.cancel()
            if self.bridge:
                self.bridge.stop()
            self.stop()
            event.accept()

    app = QApplication(sys.argv)
    w = Window()
    w.show()
    return app.exec_()
