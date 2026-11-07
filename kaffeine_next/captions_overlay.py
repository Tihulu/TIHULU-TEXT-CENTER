# SPDX-License-Identifier: GPL-2.0-or-later
"""Caption overlay for the *already tuned* DVB service in Kaffeine.

The patched Kaffeine v2.0.19 sends optional best-effort 188-byte-aligned
MPEG-TS datagrams to this user-owned AF_UNIX endpoint. This process never
opens /dev/dvb, never changes the channel, never makes network requests
during captions, and never runs on startup without owner action.
"""
from __future__ import annotations
from pathlib import Path
import os
import queue
import re
import socket
import sys
import threading
import time

CHUNK_SECONDS = 10
MAX_TS_BYTES = 24 * 1024 * 1024
LANGS = ("de", "en", "tr")

def validate_socket(path: str) -> Path:
    location = Path(os.environ.get("XDG_RUNTIME_DIR", ""))
    p = Path(path)
    if not location.is_dir() or not p.is_absolute() or p.parent != location:
        raise ValueError("Captions socket must be in the current user's XDG_RUNTIME_DIR")
    if not re.fullmatch(r"tihulu-dvb-[0-9]{1,10}\.sock", p.name):
        raise ValueError("Expected a private Kaffeine DVB socket from this session")
    return p

class CaptionTap:
    def __init__(self, path, current_options, events, packet_sink=None):
        self.path = validate_socket(path)
        self.packet_sink = packet_sink
        self.current_options = current_options
        self.events = events
        self.stop = threading.Event()
        self.busy = threading.Event()
        self.thread = None
        self.sock = None
        self.packet_count = 0
        self.bad_packets = 0

    def start(self):
        if self.path.exists():
            raise RuntimeError("Another captions window uses this Kaffeine socket")
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.sock.bind(str(self.path))
        os.chmod(self.path, 0o600)
        self.sock.settimeout(0.3)
        self.thread = threading.Thread(target=self._reader, name="tihulu-kaffeine-ts",
                                       daemon=True)
        self.thread.start()

    def _reader(self):
        chunks = bytearray()
        last = time.monotonic()
        while not self.stop.is_set():
            try:
                data = self.sock.recv(188 * 32)
            except socket.timeout:
                continue
            except OSError:
                break
            # Each datagram is independently 188-byte aligned; reject partial
            # packets rather than inserting invalid bytes into the MPEG-TS clip.
            if not data or len(data) % 188:
                self.bad_packets += 1
                continue
            if any(data[i] != 0x47 for i in range(0, len(data), 188)):
                self.bad_packets += 1
                continue
            self.packet_count += len(data) // 188
            if self.packet_sink:
                try:
                    self.packet_sink(data)
                except (OSError, RuntimeError, ValueError) as exc:
                    self.events.put(("warning", "Mobile packet relay: " + str(exc)[:100]))
            options = self.current_options()
            if options["mode"] == "off":
                chunks.clear()
                last = time.monotonic()
                continue
            if len(chunks) + len(data) > MAX_TS_BYTES:
                chunks.clear()
                self.events.put(("warning", "Caption buffer overflow; live TV remains unaffected"))
                last = time.monotonic()
            chunks.extend(data)
            if time.monotonic() - last >= CHUNK_SECONDS and len(chunks) >= 188 * 300:
                capture = bytes(chunks)
                chunks.clear()
                last = time.monotonic()
                if not self.busy.is_set():
                    self.busy.set()
                    threading.Thread(target=self._decode, args=(capture, options),
                        name="tihulu-caption-decode", daemon=True).start()
                else:
                    self.events.put(("warning", "ASR slower than real time; skipping one segment"))

    def _decode(self, capture, options):
        try:
            from tv_center.ai_settings import AISettings
            from tv_center.captions import decode_segment
            ai = AISettings()
            ai.configure_environment()
            selected = options["mode"]
            if selected in ("asr", "auto") and not ai.values["asr_enabled"]:
                if selected == "asr":
                    raise RuntimeError("Whisper disabled. Enable in AI Model Market.")
                selected = "teletext"
            source = options["source"]
            target = options["target"] if ai.values["translation_enabled"] else source
            result = decode_segment(capture, mode=selected, page=options["page"],
                source=source, target=target, model=ai.values["model_path"],
                service_id=None)
            self.events.put(("caption", result))
        except (OSError, RuntimeError, ImportError, ValueError) as error:
            self.events.put(("warning", str(error)[:180]))
        finally:
            self.busy.clear()

    def close(self):
        self.stop.set()
        if self.sock:
            self.sock.close()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)
        # Only unlink our own previously bound socket.
        try:
            self.path.unlink(missing_ok=True)
        except OSError:
            pass

def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 2 or argv[0] != "--socket":
        raise SystemExit("Usage: tihulu-tv-center kaffeine-captions --socket $XDG_RUNTIME_DIR/tihulu-dvb-PID.sock")
    endpoint = validate_socket(argv[1])
    from PyQt5.QtCore import Qt, QTimer
    from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QComboBox, QPushButton, QSpinBox, QCheckBox)
    app = QApplication.instance() or QApplication(["TIHULU Kaffeine Live Captions"])
    window = QWidget()
    window.setWindowTitle("TIHULU · Live TV captions / Whisper / Translator")
    window.setMinimumWidth(720)
    window.setWindowFlags(window.windowFlags() | Qt.WindowStaysOnTopHint)
    window.setStyleSheet("QWidget{background:#0c1722;color:#ebf6fa;font-size:14px}"
        "QComboBox,QSpinBox,QPushButton{background:#183347;border:1px solid #35718b;"
        "border-radius:6px;padding:7px} QLabel#subtitle{font-size:21px;}")
    layout = QVBoxLayout(window)
    row = QHBoxLayout()
    mode = QComboBox()
    mode.addItem("Teletext → Whisper fallback", "auto")
    mode.addItem("Broadcast Teletext only", "teletext")
    mode.addItem("Whisper live transcription", "asr")
    mode.addItem("Teletext page only", "page")
    mode.addItem("Off (zero AI work)", "off")
    source = QComboBox(); source.addItems(LANGS)
    target = QComboBox(); target.addItems(("tr", "en", "de"))
    page = QSpinBox(); page.setRange(100, 899); page.setValue(150)
    for label, widget in (("Source", mode), ("Spoken", source),
                           ("Translate to", target), ("Teletext page", page)):
        row.addWidget(QLabel(label)); row.addWidget(widget)
    layout.addLayout(row)
    original = QLabel("Waiting for Kaffeine's live DVB transport stream…")
    original.setObjectName("subtitle"); original.setWordWrap(True)
    translated = QLabel(""); translated.setObjectName("subtitle")
    translated.setWordWrap(True)
    layout.addWidget(original)
    layout.addWidget(translated)
    status = QLabel("Kaffeine retains tuner ownership. Only the selected TV service is sampled.")
    status.setWordWrap(True)
    layout.addWidget(status)
    market = QPushButton("Whisper + Translator Model Market")
    market.clicked.connect(lambda: __import__("subprocess").Popen(
        ["tihulu-tv-center", "ai-market"], close_fds=True))
    layout.addWidget(market)
    phone = QCheckBox("Allow phone/tablet on trusted Wi-Fi (OFF by default)")
    video = QCheckBox("Share the live channel as H.264/AAC HLS (CPU intensive)")
    lan_note = QLabel("Mobile access OFF. No network listener.")
    lan_note.setWordWrap(True)
    layout.addWidget(phone)
    layout.addWidget(video)
    layout.addWidget(lan_note)
    state_lock = threading.Lock()
    current = {"mode":"auto","source":"de","target":"tr","page":150}
    def update(*_):
        with state_lock:
            current.update(mode=mode.currentData(), source=source.currentText(),
                 target=target.currentText(), page=page.value())
    for w in (mode, source, target):
        w.currentIndexChanged.connect(update)
    page.valueChanged.connect(update)
    def options():
        with state_lock:
            return dict(current)
    events = queue.Queue(maxsize=30)
    from .mobile import KaffeineMobile
    mobile = KaffeineMobile(options, lambda msg: events.put(("warning", str(msg))))
    tap = CaptionTap(str(endpoint), options, events, packet_sink=mobile.receive)

    def set_phone(enabled):
        if enabled:
            try:
                data = mobile.enable_lan(lambda num: events.put(("remote_page", int(num))))
                lan_note.setText("Phone: " + data["url"] + "  |  Pairing code: " + data["pin"]
                    + "\nTrusted Wi-Fi only; HTTP is not encrypted. Never port-forward.")
            except (OSError, RuntimeError) as exc:
                phone.blockSignals(True); phone.setChecked(False); phone.blockSignals(False)
                lan_note.setText("LAN sharing unavailable: " + str(exc))
        else:
            mobile.stop_lan()
            video.blockSignals(True); video.setChecked(False); video.blockSignals(False)
            lan_note.setText("Mobile access OFF. All paired sessions revoked.")

    def set_video(enabled):
        if enabled:
            try:
                mobile.enable_video()
                lan_note.setText(lan_note.text() + "\nLive HLS on. iPhone Safari supports native playback.")
            except (RuntimeError, OSError, ValueError) as exc:
                video.blockSignals(True); video.setChecked(False); video.blockSignals(False)
                lan_note.setText("Cannot share live video: " + str(exc))
        else:
            mobile.stop_video()

    phone.toggled.connect(set_phone)
    video.toggled.connect(set_video)

    try:
        tap.start()
    except (OSError, RuntimeError) as exc:
        status.setText("Cannot connect to live Kaffeine DVB stream: "+str(exc))
        window.show()
        return app.exec_()
    def pump():
        for _ in range(5):
            try:
                kind, data = events.get_nowait()
            except queue.Empty:
                break
            if kind == "remote_page":
                page.setValue(int(data))
            elif kind == "caption":
                mobile.set_caption(data)
                if data.get("original"):
                    original.setText("ORIGINAL: " + data["original"])
                    translated.setText("TRANSLATED: " + (data.get("translated") or
                        "(source language or translator unavailable)"))
                    status.setText("Source: " + data.get("source", "unknown") +
                        " · " + str(tap.packet_count) + " TS packets received")
                elif data.get("error"):
                    status.setText("Caption decode: " + data["error"])
            elif kind == "warning":
                status.setText(str(data))
    timer = QTimer(window)
    timer.timeout.connect(pump)
    timer.start(250)
    app.aboutToQuit.connect(mobile.close)
    app.aboutToQuit.connect(tap.close)
    window.show()
    return app.exec_()

if __name__ == "__main__":
    raise SystemExit(main())
