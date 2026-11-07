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

CHUNK_SECONDS = 4
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
        last_revision = -1
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
            if options.get("revision", 0) != last_revision:
                chunks.clear()
                last_revision = options.get("revision", 0)
                last = time.monotonic()
            if options["mode"] == "off":
                chunks.clear()
                last = time.monotonic()
                continue
            if len(chunks) + len(data) > MAX_TS_BYTES:
                chunks.clear()
                self.events.put(("warning", "Caption buffer overflow; live TV remains unaffected"))
                last = time.monotonic()
            chunks.extend(data)
            now = time.monotonic()
            if now - last >= CHUNK_SECONDS and len(chunks) >= 188 * 300:
                capture = bytes(chunks)
                started = last
                chunks.clear()
                last = now
                if not self.busy.is_set():
                    self.busy.set()
                    threading.Thread(target=self._decode,
                        args=(capture, options, started, now),
                        name="tihulu-caption-decode", daemon=True).start()
                else:
                    self.events.put(("warning", "ASR slower than real time; skipping one segment"))

    def _decode(self, capture, options, captured_start, captured_end):
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
            want_translate = options["target"] != source
            target = options["target"] if ai.values["translation_enabled"] else source
            result = decode_segment(capture, mode=selected, page=options["page"],
                source=source, target=target, model=ai.values["model_path"],
                service_id=None)
            if want_translate and not ai.values["translation_enabled"]:
                result["translation_error"] = "Translation disabled; enable it in Model Market."
            elif want_translate and not result.get("translated"):
                result["translation_error"] = (
                    result.get("error") or "Translation package unavailable; open Model Market.")
            result["captured_start"] = captured_start
            result["captured_end"] = captured_end
            result["decoded_at"] = time.monotonic()
            result["revision"] = options.get("revision", 0)
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
    from .caption_timing import CaptionConfig, CueQueue, KaffeineOSD
    from PyQt5.QtCore import Qt, QTimer
    from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QComboBox, QPushButton, QSpinBox, QDoubleSpinBox,
        QCheckBox, QGroupBox, QFormLayout)
    app = QApplication.instance() or QApplication(["TIHULU Kaffeine Live Captions"])
    window = QWidget()
    window.setWindowTitle("TIHULU · Live captions / Whisper / Translator")
    window.setMinimumWidth(780)
    window.setStyleSheet(
        "QWidget{background:#0c1722;color:#e8f3fa;font-size:13px}"
        "QGroupBox{border:1px solid #304b63;border-radius:8px;margin-top:14px;padding:10px}"
        "QGroupBox::title{subcontrol-origin:margin;left:12px;padding:0 5px}"
        "QComboBox,QSpinBox,QDoubleSpinBox,QPushButton{background:#173449;"
        "border:1px solid #356784;border-radius:6px;padding:7px}"
        "QPushButton#apply{background:#207796;font-weight:700}"
        "QLabel#subtitle{font-size:20px}"
    )
    root = QVBoxLayout(window)

    settings = QGroupBox("Live caption source & language")
    settings_layout = QFormLayout(settings)
    row = QHBoxLayout()
    mode = QComboBox()
    mode.addItem("Teletext subtitles → Whisper fallback", "auto")
    mode.addItem("Broadcaster Teletext subtitles", "teletext")
    mode.addItem("Whisper live transcription", "asr")
    mode.addItem("Manual Teletext page", "page")
    mode.addItem("Off", "off")
    source = QComboBox(); source.addItems(LANGS); source.setCurrentText("de")
    target = QComboBox(); target.addItem("Off (original only)", "off")
    for lang in ("tr", "en", "de"):
        target.addItem(lang, lang)
    target.setCurrentIndex(1)
    page = QSpinBox(); page.setRange(100, 899); page.setValue(150)
    for name, widget in (("Source",mode),("Spoken",source),
                         ("Translate",target),("Teletext",page)):
        row.addWidget(QLabel(name))
        row.addWidget(widget, 1)
    settings_layout.addRow(row)
    root.addWidget(settings)

    timing = QGroupBox("Synchronization & video overlay")
    timing_layout = QFormLayout(timing)
    offsets = QHBoxLayout()
    caption_offset = QDoubleSpinBox()
    caption_offset.setRange(-10.0, 10.0)
    caption_offset.setSingleStep(0.1)
    caption_offset.setSuffix(" s")
    caption_offset.setToolTip("Positive = later subtitle; negative = earlier. Cannot show before decoding completes.")
    playback_delay = QDoubleSpinBox()
    playback_delay.setRange(0.0, 8.0)
    playback_delay.setSingleStep(0.5)
    playback_delay.setSuffix(" s")
    playback_delay.setToolTip("Buffers both video and audio together. This uses memory and must be retested on Pi 5.")
    offsets.addWidget(QLabel("Caption offset"))
    offsets.addWidget(caption_offset)
    offsets.addWidget(QLabel("TV playback buffer"))
    offsets.addWidget(playback_delay)
    timing_layout.addRow(offsets)
    visibility = QHBoxLayout()
    show_video = QCheckBox("On-video subtitles"); show_video.setChecked(True)
    show_original = QCheckBox("Original"); show_original.setChecked(True)
    show_translation = QCheckBox("Translation"); show_translation.setChecked(True)
    position = QComboBox(); position.addItems(("bottom", "top"))
    font = QSpinBox(); font.setRange(16, 44); font.setValue(25)
    opacity = QSpinBox(); opacity.setRange(0, 100); opacity.setValue(70); opacity.setSuffix("%")
    for widget in (show_video,show_original,show_translation): visibility.addWidget(widget)
    for name, widget in (("Position",position),("Size",font),("Background",opacity)):
        visibility.addWidget(QLabel(name)); visibility.addWidget(widget)
    timing_layout.addRow(visibility)
    root.addWidget(timing)
    buttons = QHBoxLayout()
    apply = QPushButton("Apply")
    apply.setObjectName("apply")
    reset = QPushButton("Reset")
    pending = QLabel("Applied: broadcaster auto · German → Turkish · video captions ON")
    buttons.addWidget(apply); buttons.addWidget(reset); buttons.addWidget(pending, 1)
    root.addLayout(buttons)

    original = QLabel("Waiting for real Kaffeine DVB stream…")
    original.setObjectName("subtitle"); original.setWordWrap(True)
    translated = QLabel("")
    translated.setObjectName("subtitle"); translated.setWordWrap(True)
    root.addWidget(original); root.addWidget(translated)
    status = QLabel("Whisper captions use 4-second audio chunks plus processing time. "
                    "Audio and video remain synchronized with each other.")
    status.setWordWrap(True)
    root.addWidget(status)

    market = QPushButton("Whisper + Translator Model Market")
    def launch_market():
        import subprocess
        subprocess.Popen(["tihulu-tv-center","ai-market"],close_fds=True)
    market.clicked.connect(launch_market)
    root.addWidget(market)
    phone = QCheckBox("Allow phone/tablet on trusted Wi-Fi (OFF by default)")
    video = QCheckBox("Share the live channel as H.264/AAC HLS (CPU intensive)")
    lan_note = QLabel("Mobile access OFF. No network listener.")
    lan_note.setWordWrap(True)
    root.addWidget(phone); root.addWidget(video); root.addWidget(lan_note)

    pid = int(endpoint.stem.rsplit("-",1)[-1])
    ipc = KaffeineOSD(pid, runtime=endpoint.parent)
    lock = threading.Lock()
    applied = CaptionConfig().validate()
    cues = CueQueue()
    def options():
        with lock:
            return applied.options()
    events = queue.Queue(maxsize=32)
    from .mobile import KaffeineMobile
    mobile = KaffeineMobile(options, lambda msg: events.put(("warning", str(msg))))
    tap = CaptionTap(str(endpoint), options, events, packet_sink=mobile.receive)
    try:
        tap.start()
    except (OSError, RuntimeError) as exc:
        status.setText("Cannot receive Kaffeine DVB stream: "+str(exc))
        window.show()
        return app.exec_()

    current_text = ""
    current_until = 0.0
    last_published = 0.0
    current_cue = None

    def from_controls():
        translation = target.currentData()
        return CaptionConfig(
            mode=mode.currentData(), source=source.currentText(),
            target=(source.currentText() if translation == "off" else translation),
            page=page.value(),
            offset_ms=round(caption_offset.value()*1000),
            playback_delay_ms=round(playback_delay.value()*1000),
            on_video=show_video.isChecked(), show_original=show_original.isChecked(),
            show_translation=show_translation.isChecked(),
            position=position.currentText(),font_px=font.value(),opacity=opacity.value()
        ).validate()

    def set_pending(*_):
        pending.setText("Unsaved changes — press Apply")
        pending.setStyleSheet("color:#f7bf6e")
    for w in (mode,source,target,position):
        w.currentIndexChanged.connect(set_pending)
    for w in (page,caption_offset,playback_delay,font,opacity):
        w.valueChanged.connect(set_pending)
    for w in (show_video,show_original,show_translation):
        w.toggled.connect(set_pending)

    def apply_settings():
        nonlocal applied, current_text, current_until, current_cue
        try:
            selected = from_controls()
            with lock:
                applied = __import__("dataclasses").replace(selected, revision=applied.revision+1)
            cues.clear()
            current_cue = None
            current_text = ""
            current_until = 0.0
            original.setText("Waiting for captions under the new settings…")
            translated.setText("")
            ipc.publish("",applied)
            ipc.set_playback_delay(applied)
            pending.setText("Applied · " + applied.mode + " · " + applied.source.upper() +
                            " → " + applied.target.upper() +
                            " · playback buffer " + str(applied.playback_delay_ms/1000) + " s")
            pending.setStyleSheet("color:#9ed7ba")
            status.setText("Applied. Caption offset: "+str(applied.offset_ms/1000)+
                           "s; TV playback buffer: "+str(applied.playback_delay_ms/1000)+
                           "s. Real ASR timing varies with model CPU/GPU performance.")
        except (ValueError, OSError) as exc:
            status.setText("Settings were not applied: " + str(exc))

    def reset_settings():
        mode.setCurrentIndex(0)
        source.setCurrentText("de"); target.setCurrentIndex(1)
        page.setValue(150)
        caption_offset.setValue(0.0); playback_delay.setValue(0.0)
        show_video.setChecked(True); show_original.setChecked(True)
        show_translation.setChecked(True)
        position.setCurrentText("bottom"); font.setValue(25); opacity.setValue(70)
        set_pending()
    apply.clicked.connect(apply_settings)
    reset.clicked.connect(reset_settings)

    def set_phone(enabled):
        if enabled:
            try:
                data = mobile.enable_lan(lambda num: events.put(("remote_page",int(num))))
                lan_note.setText("Phone: "+data["url"]+" | Pair: "+data["pin"]+
                                  "\nTrusted Wi-Fi only; HTTP is not encrypted.")
            except (OSError, RuntimeError) as exc:
                phone.blockSignals(True); phone.setChecked(False); phone.blockSignals(False)
                lan_note.setText("LAN sharing unavailable: "+str(exc))
        else:
            mobile.stop_lan()
            video.blockSignals(True); video.setChecked(False); video.blockSignals(False)
            lan_note.setText("Mobile access OFF; phone sessions revoked.")

    def set_video(enabled):
        if enabled:
            try:
                mobile.enable_video()
                lan_note.setText(lan_note.text()+"\nLive HLS enabled for paired phones.")
            except (RuntimeError,OSError,ValueError) as exc:
                video.blockSignals(True); video.setChecked(False); video.blockSignals(False)
                lan_note.setText("Mobile HLS unavailable: "+str(exc))
        else:
            mobile.stop_video()
    phone.toggled.connect(set_phone)
    video.toggled.connect(set_video)
    apply_settings()

    def pump():
        nonlocal current_cue, current_text, current_until, last_published
        mobile.expire_if_idle()
        now = time.monotonic()
        for _ in range(8):
            try:
                kind, data = events.get_nowait()
            except queue.Empty:
                break
            if kind == "remote_page":
                mode.setCurrentIndex(3)
                page.setValue(int(data))
                apply_settings()
            elif kind == "caption":
                if data.get("revision") != applied.revision:
                    continue
                if data.get("original"):
                    cue = cues.add(data, applied,
                                   data["captured_start"],data["captured_end"],
                                   data["decoded_at"])
                    status.setText("Real "+data.get("source","unknown")+
                        " | ASR+translate latency: "+
                        f"{int((data['decoded_at']-data['captured_end'])*1000)}ms" +
                        " | Caption lateness vs buffered TV: "+
                        str(cue["lateness_ms"])+"ms" +
                        " | DVB TS packets: "+str(tap.packet_count))
                    if data.get("error"):
                        status.setText(status.text()+"\n"+data["error"])
                elif data.get("error"):
                    status.setText("Caption/translator: "+data["error"])
            elif kind == "warning":
                status.setText(str(data))
        cue = cues.poll(now, applied.revision)
        if cue:
            current_cue = cue
            result = cue["result"]
            mobile.set_caption(result)
            current_text = applied.render(result)
            current_until = cue["expires"]
            original.setText("ORIGINAL: "+result.get("original", ""))
            translated.setText("TRANSLATED: "+(result.get("translated") or
                         ("Not requested" if applied.source == applied.target else
                          result.get("translation_error") or result.get("error") or
                          "Argos DE/EN/TR pack not installed · open Market")))
            ipc.publish(current_text,applied,ttl_ms=3000)
            last_published = now
        elif current_cue and now >= current_until:
            current_cue = None
            current_text = ""
            ipc.publish("",applied)
            original.setText("Waiting for next live phrase…")
            translated.setText("")
        elif current_cue and now-last_published >= 2.0:
            ipc.publish(current_text,applied,ttl_ms=3000)
            last_published = now

    timer = QTimer(window)
    timer.timeout.connect(pump)
    timer.start(120)
    def cleanup():
        mobile.close()
        tap.close()
        ipc.close()
    app.aboutToQuit.connect(cleanup)
    window.show()
    return app.exec_()

if __name__ == "__main__":
    raise SystemExit(main())
