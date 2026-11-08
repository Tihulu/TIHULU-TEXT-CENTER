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

# Longer contiguous phrases improve Whisper context; overlap covers words
# spanning boundaries. Queued capture lets CPU inference finish without
# *immediately* discarding the next 6-second segment.
CHUNK_SECONDS = 6
OVERLAP_SECONDS = 1.0
MAX_TS_BYTES = 24 * 1024 * 1024
LANGS = ("de", "en", "tr", "fr")

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
        from .continuous_captions import BufferedCaptionQueue
        from .transport_health import TransportContinuityMeter
        from .subtitle_tracks import TeletextSubtitleDiscovery
        self.transport_health = TransportContinuityMeter()
        self.subtitle_discovery = TeletextSubtitleDiscovery()
        self.program_epoch = 0
        self.recv_buffer_bytes = None
        self.work_queue = BufferedCaptionQueue(
            maximum_bytes=(48 if Path("/proc/device-tree/model").is_file()
                           else 96) * 1024 * 1024, max_clips=24)
        self.thread = None
        self.worker = None
        self.previous_original = ""
        self.previous_revision = -1
        self.program_id = None
        self.sock = None
        self.packet_count = 0
        self.bad_packets = 0
        self._rate_start = None
        self._rate_bytes = 0
        self.bytes_per_second = None

    def start(self):
        if self.path.exists():
            raise RuntimeError("Another captions window uses this Kaffeine socket")
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.sock.bind(str(self.path))
        os.chmod(self.path, 0o600)
        # No sysctl changes: Linux clamps SO_RCVBUF to a safe local maximum.
        try:
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4*1024*1024)
        except OSError:
            pass
        self.recv_buffer_bytes = self.sock.getsockopt(
            socket.SOL_SOCKET, socket.SO_RCVBUF)
        self.sock.settimeout(0.3)
        self.thread = threading.Thread(target=self._reader, name="tihulu-kaffeine-ts",
                                       daemon=True)
        self.thread.start()
        self.worker = threading.Thread(target=self._worker,
            name="tihulu-kaffeine-caption-worker", daemon=True)
        self.worker.start()

    def _worker(self):
        from .continuous_captions import remove_repeated_prefix
        while not self.stop.is_set():
            clip = self.work_queue.get(timeout=0.3)
            if clip is None:
                continue
            try:
                self._decode(clip.data, clip.options, clip.started, clip.ended)
            except Exception as error:
                self._note_warning("Caption worker failed: "+str(error)[:120])

    def _note_warning(self, message):
        try:
            self.events.put_nowait(("warning", str(message)[:240]))
        except queue.Full:
            pass

    def _reader(self):
        chunks = bytearray()
        last = time.monotonic()
        last_revision = -1
        previous_segment = b""
        previous_duration = 0.0
        from .continuous_captions import CapturedClip, prepended_overlap
        from .mpegts import current_program_id
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
            self.transport_health.inspect(data)
            rate_now = time.monotonic()
            if self._rate_start is None:
                self._rate_start = rate_now
            self._rate_bytes += len(data)
            if rate_now - self._rate_start >= 8.0:
                measured_rate = self._rate_bytes / (rate_now - self._rate_start)
                # Smooth the actual forwarded selected-service TS bitrate;
                # overhead and bursts mean this is only a safety estimate.
                if self.bytes_per_second is None:
                    self.bytes_per_second = measured_rate
                else:
                    self.bytes_per_second = 0.7 * self.bytes_per_second + 0.3 * measured_rate
                self._rate_start = rate_now
                self._rate_bytes = 0
            # Kaffeine may switch services without reopening this sidecar.
            # Never concatenate clips or deduplicate speech across TV channels.
            observed_program = current_program_id(data)
            if observed_program and observed_program != self.program_id:
                if self.program_id is not None:
                    chunks.clear()
                    self.work_queue.clear()
                    last = time.monotonic()
                    previous_segment = b""
                    previous_duration = 0.0
                    self.previous_original = ""
                    self.previous_revision = -1
                    self.transport_health.reset()
                    self.subtitle_discovery.clear()
                    self.program_epoch += 1
                    self._note_warning(
                        "TV service changed; cleared previous-channel ASR queue.")
                self.program_id = observed_program
            if self.subtitle_discovery.offer(data, preferred_service_id=self.program_id):
                try:
                    self.events.put_nowait((
                        "teletext_tracks",
                        {"service_id":self.subtitle_discovery.service_id,
                         "tracks":self.subtitle_discovery.snapshot(),
                         "audio_tracks":self.subtitle_discovery.snapshot_audio()}))
                except queue.Full:
                    self._note_warning("Teletext subtitle channel list refresh delayed")
            if self.packet_sink:
                try:
                    self.packet_sink(data)
                except (OSError, RuntimeError, ValueError) as exc:
                    self._note_warning("Mobile packet relay: "+str(exc)[:100])
            options = self.current_options()
            if options.get("revision", 0) != last_revision:
                chunks.clear()
                self.work_queue.clear()
                last_revision = options.get("revision", 0)
                last = time.monotonic()
                previous_segment = b""
                previous_duration = 0.0
            if options["mode"] == "off":
                chunks.clear()
                last = time.monotonic()
                continue
            if len(chunks) + len(data) > MAX_TS_BYTES:
                chunks.clear()
                self._note_warning(
                    "RF caption capture exceeded 24 MiB; audio may be incomplete")
                last = time.monotonic()
                previous_segment = b""
                previous_duration = 0.0
            chunks.extend(data)
            now = time.monotonic()
            if now - last >= CHUNK_SECONDS and len(chunks) >= 188 * 300:
                raw = bytes(chunks)
                capture = prepended_overlap(
                    raw, previous_segment, previous_duration, OVERLAP_SECONDS)
                started = last - (OVERLAP_SECONDS if previous_segment else 0)
                previous_segment = raw
                previous_duration = max(0.5, now-last)
                chunks.clear()
                last = now
                captured_options = dict(options)
                captured_options["service_id"] = self.program_id
                captured_options["program_epoch"] = self.program_epoch
                queued = self.work_queue.offer(
                    CapturedClip(capture, captured_options, started, now))
                if not queued:
                    health = self.work_queue.snapshot()
                    self._note_warning(
                        "Whisper slower than live TV: queue full; "
                        f"{health['missed_seconds']:.1f} s of captions could not "
                        "be retained. Select CUDA GPU/smaller model or fewer translations.")

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
            targets = tuple(options.get("targets", ()))
            enabled = targets if ai.values["translation_enabled"] else ()
            primary = targets[0] if targets else source
            previous = (self.previous_original
                        if self.previous_revision == options.get("revision", 0)
                        else "")
            result = decode_segment(capture, mode=selected, page=options["page"],
                source=source, target=primary, targets=enabled,
                model=ai.values["model_path"],
                service_id=options.get("service_id"),
                teletext_pid=(options.get("teletext_pid")
                              if selected in ("auto", "teletext", "page") else None),
                audio_pid=(options.get("audio_pid")
                           if selected in ("auto", "asr") else None),
                audio_source=(options.get("audio_source")
                              if selected in ("auto", "asr") else None),
                speaker_enabled=bool(options.get("speaker_enabled",False))
                                and selected in ("auto","asr"),
                speaker_provider=options.get("speaker_provider","resemblyzer"),
                previous_text=previous)
            if options.get("program_epoch") != self.program_epoch:
                return  # old channel's caption must never appear on new TV
            if result.get("source") == "local_asr" and result.get("original"):
                # The decoder must remove duplicated overlap before translation.
                self.previous_original = result["original"]
                self.previous_revision = options.get("revision", 0)
            if targets and not ai.values["translation_enabled"]:
                result["translation_errors"] = {
                    lang: "Translation disabled in Model Market." for lang in targets}
            if targets and not result.get("translations"):
                result["translation_error"] = (
                    next(iter(result.get("translation_errors", {}).values()), None)
                    or result.get("error") or
                    "Language packs unavailable. Install via Model Market.")
            result["captured_start"] = captured_start
            result["captured_end"] = captured_end
            result["decoded_at"] = time.monotonic()
            result["revision"] = options.get("revision", 0)
            try:
                self.events.put_nowait(("caption", result))
            except queue.Full:
                self._note_warning("Caption UI event backlog full; output delayed")
        except (OSError, RuntimeError, ImportError, ValueError) as error:
            self._note_warning(str(error)[:180])

    def close(self):
        self.stop.set()
        if self.sock:
            self.sock.close()
        self.work_queue.close()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)
        if self.worker and self.worker.is_alive():
            self.worker.join(timeout=2)
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
    from .caption_control import CaptionServiceControl
    from tv_center.language_codes import language_code
    from textcenter.compute import LANGUAGES as WHISPER_LANGUAGES
    pid = int(endpoint.stem.rsplit("-", 1)[-1])
    if CaptionServiceControl.request_show(endpoint.parent, pid):
        # Reopening the TIHULU AI menu focuses the existing controller.
        # Do not create a competing DVB/Whisper reader.
        return 0
    from .caption_timing import (CaptionConfig, CueQueue, KaffeineOSD,
                                 AutoSyncEstimator, AutoSyncController,
                                 effective_cue_config)
    from .word_cues import enqueue_word_cues
    from PyQt5.QtCore import Qt, QTimer
    from PyQt5.QtGui import QColor
    from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QComboBox, QPushButton, QSpinBox, QDoubleSpinBox,
        QCheckBox, QGroupBox, QFormLayout, QLineEdit, QColorDialog,
        QScrollArea, QFrame, QGridLayout)
    app = QApplication.instance() or QApplication(["TIHULU Kaffeine Live Captions"])
    # Hiding the only QWidget must NOT quit the Qt event loop: audio capture,
    # auto-sync and video-overlay publishing continue independently of UI.
    app.setQuitOnLastWindowClosed(False)

    class CaptionSettingsWindow(QWidget):
        terminating = False
        def closeEvent(self, event):
            if self.terminating:
                event.accept()
                return
            self.hide()
            event.ignore()

    window = CaptionSettingsWindow()
    window.setWindowTitle(
        "TIHULU · Live captions · GPU Whisper + translation failover")
    window.setMinimumWidth(780)
    window.setStyleSheet(
        "QWidget{background:#0c1722;color:#e8f3fa;font-size:13px}"
        "QGroupBox{border:1px solid #304b63;border-radius:8px;margin-top:14px;padding:10px}"
        "QGroupBox::title{subcontrol-origin:margin;left:12px;padding:0 5px}"
        "QComboBox,QSpinBox,QDoubleSpinBox,QPushButton{background:#173449;"
        "border:1px solid #356784;border-radius:6px;padding:7px}"
        "QPushButton#apply{background:#207796;font-weight:700}"
        "QLabel#subtitle{font-size:20px;max-height:86px}"
    )
    window.resize(940, 810)
    root = QVBoxLayout(window)
    root.setContentsMargins(12,10,12,10)
    root.setSpacing(8)
    control_body = QWidget()
    control_layout = QVBoxLayout(control_body)
    control_layout.setContentsMargins(6,8,6,8)
    control_layout.setSpacing(12)

    settings = QGroupBox("Live caption source & language")
    settings_layout = QFormLayout(settings)
    settings_layout.setRowWrapPolicy(QFormLayout.WrapLongRows)
    settings_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
    row = QHBoxLayout()
    mode = QComboBox()
    mode.addItem("Teletext subtitles → Whisper fallback", "auto")
    mode.addItem("Broadcaster Teletext subtitles", "teletext")
    mode.addItem("Whisper live transcription", "asr")
    mode.addItem("Manual Teletext page", "page")
    mode.addItem("Off", "off")
    source = QComboBox()
    source.setEditable(True)
    source.addItems(LANGS)
    source.setCurrentText("de")
    source.setToolTip(
        "Type an ISO code such as pl, es, ja, ar. Broadcast Teletext "
        "can be displayed in its original language; 100 source-language "
        "codes are supported by multilingual Whisper, provided the chosen "
        "speech model and runtime are installed.")
    page = QSpinBox(); page.setRange(100, 899); page.setValue(150)
    for name, widget in (("Source",mode),("Spoken",source),("Teletext",page)):
        row.addWidget(QLabel(name)); row.addWidget(widget, 1)
    settings_layout.addRow(row)
    output_row = QHBoxLayout()
    display_mode = QComboBox()
    display_mode.addItem("Original only", "original")
    display_mode.addItem("Original + translations", "both")
    display_mode.addItem("Translations only", "translated")
    display_mode.setCurrentIndex(1)
    output_row.addWidget(QLabel("Display"))
    output_row.addWidget(display_mode, 2)
    output_row.addWidget(QLabel("Output languages"))
    language_boxes = {lang: QCheckBox(lang.upper()) for lang in LANGS}
    for lang, check in language_boxes.items():
        check.setChecked(lang == "tr")
        output_row.addWidget(check)
    settings_layout.addRow(output_row)
    extra_targets = QLineEdit()
    extra_targets.setPlaceholderText(
        "Optional extra target codes: es, pl, ar, ja or zho_Hant")
    extra_targets.setToolTip(
        "Up to three different targets including checked presets. "
        "Actual translation requires a matching installed Argos pack or "
        "NLLB model. Missing packs never hide the source captions.")
    settings_layout.addRow("Additional translation languages", extra_targets)
    translation_health = QLabel(
        "Translation model: selected in AI Model Market. "
        "NLLB errors trigger installed Argos backup; subtitles stay visible.")
    translation_health.setWordWrap(True)
    settings_layout.addRow("Translation status", translation_health)
    def update_language_choices(*_):
        for lang, check in language_boxes.items():
            check.setEnabled(True)
            check.setToolTip(
                ("Same as spoken language · display original under " +
                 lang.upper() + " label (no translator needed)"
                 if lang == source.currentText() else
                 "Translate to " + lang.upper() + " when a local model exists; "
                 "otherwise keep the original readable"))
    source.currentTextChanged.connect(update_language_choices)
    update_language_choices()
    tracks_row = QHBoxLayout()
    tracks_row.addWidget(QLabel("Broadcast subtitle channel"))
    subtitle_track = QComboBox()
    subtitle_track.addItem("Automatic broadcaster subtitles (no selected page)", None)
    subtitle_track.setToolTip(
        "Detected from the tuned TV service's DVB Teletext descriptor. "
        "Only actual signalled subtitle pages are offered. Select a "
        "language/page, then Apply. Whisper mode transcribes audio instead.")
    tracks_row.addWidget(subtitle_track, 1)
    track_status = QLabel("Scanning this channel's real DVB subtitle descriptors…")
    track_status.setWordWrap(True)
    settings_layout.addRow(tracks_row)
    settings_layout.addRow(track_status)
    audio_row = QHBoxLayout()
    audio_row.addWidget(QLabel("Whisper source audio channel"))
    audio_track = QComboBox()
    audio_track.addItem("Automatic · prefer spoken language / regular audio", None)
    audio_track.setToolTip(
        "Real audio elementary streams signalled in the tuned DVB service. "
        "Choose a PID for Whisper transcription; TV audio playback remains "
        "under Kaffeine's own control. No second tuner is opened.")
    audio_row.addWidget(audio_track, 1)
    settings_layout.addRow(audio_row)
    audio_track_status = QLabel("Scanning broadcaster audio track descriptors…")
    audio_track_status.setWordWrap(True)
    settings_layout.addRow(audio_track_status)
    control_layout.addWidget(settings)

    timing = QGroupBox("Synchronization & video overlay")
    timing_layout = QFormLayout(timing)
    timing_layout.setRowWrapPolicy(QFormLayout.WrapLongRows)
    timing_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
    offsets = QHBoxLayout()
    caption_offset = QDoubleSpinBox()
    caption_offset.setRange(-10.0, 10.0)
    caption_offset.setSingleStep(0.1)
    caption_offset.setSuffix(" s")
    caption_offset.setToolTip("Positive = later subtitle; negative = earlier. Cannot show before decoding completes.")
    playback_delay = QDoubleSpinBox()
    playback_delay.setRange(0.0, 20.0)
    playback_delay.setSingleStep(0.5)
    playback_delay.setSuffix(" s")
    playback_delay.setToolTip("Buffers audio and video together (0–20 s). Long buffers consume RAM; "
                               "use CUDA models to reduce lag rather than excessive buffering.")
    offsets.addWidget(QLabel("Caption offset"))
    offsets.addWidget(caption_offset)
    offsets.addWidget(QLabel("TV playback buffer"))
    offsets.addWidget(playback_delay)
    timing_layout.addRow(offsets)
    auto_row = QHBoxLayout()
    automatic = QCheckBox("Automatic sync · detect caption lag & adjust safe TV buffer")
    automatic.setChecked(False)
    automatic.setToolTip(
        "OFF by default. After 3 real Whisper samples, estimates speech-caption "
        "availability and suggests a conservative delay. When enabled and Applied, "
        "adjusts TV delay gradually. Does not detect exact spoken-word timestamps.")
    auto_row.addWidget(automatic)
    timing_layout.addRow(auto_row)
    speakers_row = QHBoxLayout()
    speaker_enabled = QCheckBox(
        "Auto-label distinct voices · Speaker 1, Speaker 2, …")
    speaker_enabled.setChecked(True)
    speaker_enabled.setToolTip(
        "Checked by default. Install the public Resemblyzer model in "
        "Model Market to activate local offline voice clustering. "
        "No token required, no microphone or remote voice API. Labels "
        "are automatically generated and provisional; gender and age "
        "cannot be identified reliably from audio alone.")
    speakers_row.addWidget(speaker_enabled)
    timing_layout.addRow(speakers_row)
    speaker_provider = QComboBox()
    speaker_provider.addItem(
        "Resemblyzer · public pretrained model · no token", "resemblyzer")
    speaker_provider.addItem(
        "pyannote Community-1 · requires HF model access", "pyannote")
    speaker_provider.setToolTip(
        "You can switch auto-labeling OFF. Resemblyzer "
        "runs locally without any Hugging Face token. It estimates "
        "voice similarity, not real identity, gender or age.")
    timing_layout.addRow("Speaker model", speaker_provider)
    speaker_health = QLabel(
        "Auto labels: checking installed local speaker model…")
    speaker_health.setWordWrap(True)
    timing_layout.addRow("Voice status", speaker_health)
    # Automatic speaker names are generated by the local detector.
    # No user-entered labels are required or offered by default.
    sync_estimate = QLabel("Automatic timing: collecting real ASR samples (0/3). "
                           "Live TV and manually entered delay are unchanged.")
    sync_estimate.setWordWrap(True)
    timing_layout.addRow(sync_estimate)
    effective_status = QLabel("Native TV delay: waiting for Kaffeine's applied buffer status…")
    effective_status.setWordWrap(True)
    timing_layout.addRow(effective_status)
    visibility = QHBoxLayout()
    show_video = QCheckBox("On-video subtitles"); show_video.setChecked(True)
    position = QComboBox(); position.addItems(("bottom", "top"))
    font = QSpinBox(); font.setRange(16, 44); font.setValue(25)
    opacity = QSpinBox(); opacity.setRange(0, 100); opacity.setValue(70); opacity.setSuffix("%")
    text_opacity = QSpinBox()
    text_opacity.setRange(0, 100); text_opacity.setValue(100)
    text_opacity.setSuffix("%")
    visibility.addWidget(show_video)
    for name, widget in (("Position",position),("Size",font)):
        visibility.addWidget(QLabel(name)); visibility.addWidget(widget)
    timing_layout.addRow(visibility)
    appearance_row = QGridLayout()
    appearance_row.addWidget(QLabel("Background opacity"),0,0)
    appearance_row.addWidget(opacity,0,1)
    appearance_row.addWidget(QLabel("Text opacity"),0,2)
    appearance_row.addWidget(text_opacity,0,3)
    background_button = QPushButton("Background · #000000")
    text_button = QPushButton("Text · #FFFFFF")
    active_colors = {"background":"#000000", "text":"#FFFFFF"}
    background_button.setToolTip(
        "Choose the solid subtitle backing color; opacity is independent "
        "and supports 0% (completely transparent)")
    text_button.setToolTip(
        "Choose the text color separately from its opacity (0–100%)")
    appearance_row.addWidget(background_button,1,0,1,2)
    appearance_row.addWidget(text_button,1,2,1,2)
    timing_layout.addRow("Subtitle appearance", appearance_row)
    preset_row = QHBoxLayout()
    presets = QComboBox()
    presets.addItem("White text · translucent black", ("#FFFFFF","#000000",70,100))
    presets.addItem("Yellow text · black", ("#FFE45C","#000000",75,100))
    presets.addItem("Cyan text · navy", ("#6EE7F8","#0B2540",60,100))
    presets.addItem("White text · no background", ("#FFFFFF","#000000",0,100))
    presets.addItem("Fully transparent text + background", ("#FFFFFF","#000000",0,0))
    presets.addItem("Custom colors / transparency", None)
    presets.setToolTip(
        "A preset can be changed with either color picker, or "
        "use individual background and text transparency controls.")
    preset_row.addWidget(presets,1)
    appearance_preview = QLabel("DE: Guten Morgen   ·   TR: Günaydın")
    appearance_preview.setAlignment(Qt.AlignCenter)
    appearance_preview.setMinimumHeight(55)
    appearance_preview.setWordWrap(True)
    preset_row.addWidget(appearance_preview,2)
    timing_layout.addRow("Appearance presets", preset_row)

    def update_appearance_preview(*_):
        fg = QColor(active_colors["text"])
        bg = QColor(active_colors["background"])
        bg.setAlpha(round(opacity.value()*255/100))
        fg.setAlpha(round(text_opacity.value()*255/100))
        appearance_preview.setStyleSheet(
            "QLabel{border:1px solid #36556a;border-radius:8px;"
            f"background-color:rgba({bg.red()},{bg.green()},{bg.blue()},{bg.alpha()});"
            f"color:rgba({fg.red()},{fg.green()},{fg.blue()},{fg.alpha()});"
            "font-weight:700;padding:8px;}")
        background_button.setText("Background · "+active_colors["background"])
        text_button.setText("Text · "+active_colors["text"])

    def apply_appearance_preset(*_):
        selected = presets.currentData()
        if selected is None:
            return
        foreground, background, back_alpha, text_alpha = selected
        active_colors["text"] = foreground
        active_colors["background"] = background
        opacity.setValue(back_alpha)
        text_opacity.setValue(text_alpha)
        update_appearance_preview()

    def pick_appearance_color(which):
        selected = QColorDialog.getColor(
            QColor(active_colors[which]), window,
            "Choose subtitle " + which + " color",
            QColorDialog.DontUseNativeDialog)
        if not selected.isValid():
            return
        active_colors[which] = selected.name().upper()
        presets.setCurrentIndex(presets.count()-1)
        update_appearance_preview()
        set_pending()

    background_button.clicked.connect(lambda: pick_appearance_color("background"))
    text_button.clicked.connect(lambda: pick_appearance_color("text"))
    presets.currentIndexChanged.connect(apply_appearance_preset)
    opacity.valueChanged.connect(update_appearance_preview)
    text_opacity.valueChanged.connect(update_appearance_preview)
    update_appearance_preview()
    control_layout.addWidget(timing)
    control_layout.addStretch(1)
    control_scroll = QScrollArea()
    control_scroll.setWidgetResizable(True)
    control_scroll.setFrameShape(QFrame.NoFrame)
    control_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    control_scroll.setWidget(control_body)
    root.addWidget(control_scroll, 1)
    buttons = QHBoxLayout()
    apply = QPushButton("Apply")
    apply.setObjectName("apply")
    reset = QPushButton("Reset")
    pending = QLabel("Applied: broadcaster auto · German → Turkish · video captions ON")
    buttons.addWidget(apply); buttons.addWidget(reset); buttons.addWidget(pending, 1)
    root.addLayout(buttons)
    behavior = QHBoxLayout()
    hide_panel = QPushButton("Hide settings · keep subtitles")
    stop_subtitles = QPushButton("Stop subtitles & Exit")
    behavior.addWidget(hide_panel)
    behavior.addWidget(stop_subtitles)
    root.addLayout(behavior)
    persistence = QLabel("Closing this settings panel keeps on-video subtitles, "
                         "Whisper and translation running. Reopen with Kaffeine → "
                         "TIHULU AI → Live Teletext / Whisper subtitles. "
                         "Only Stop subtitles & Exit ends the service.")
    persistence.setWordWrap(True)
    root.addWidget(persistence)

    original = QLabel("Waiting for real Kaffeine DVB stream…")
    original.setObjectName("subtitle"); original.setWordWrap(True)
    original.setMaximumHeight(68)
    translated = QLabel("")
    translated.setObjectName("subtitle"); translated.setWordWrap(True)
    translated.setMaximumHeight(80)
    translated.setToolTip(
        "Translations are computed offline. Missing or broken NLLB "
        "automatically uses installed Argos language packs. Model errors "
        "are never shown as captions.")
    root.addWidget(original); root.addWidget(translated)
    status = QLabel("Whisper captions use 6-second overlapping audio chunks plus processing time. "
                    "Audio and video remain synchronized with each other.")
    status.setWordWrap(True)
    status.setMaximumHeight(76)
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

    ipc = KaffeineOSD(pid, runtime=endpoint.parent)
    events = queue.Queue(maxsize=32)
    control = CaptionServiceControl(endpoint.parent, pid, events)
    try:
        control.start()
    except (OSError, RuntimeError) as exc:
        raise RuntimeError("Cannot start private caption controller: " + str(exc)) from exc
    lock = threading.Lock()
    applied = CaptionConfig().validate()
    cues = CueQueue(maximum=32)
    # A six-second Whisper clip plus inference/translation may arrive more
    # than six seconds after speaking began. On desktop allow up to 15s,
    # but still obey the measured 48 MiB memory budget and native FIFO cap.
    # Raspberry Pi 5 stays at a conservative six-second maximum.
    pi5 = False
    try:
        model = Path("/proc/device-tree/model")
        pi5 = model.is_file() and "Raspberry Pi 5" in model.read_bytes().decode(
            "utf-8", "replace")
    except OSError:
        pass
    estimator = AutoSyncEstimator(ceiling_ms=6000 if pi5 else 15000)
    auto_controller = AutoSyncController()
    last_service_id = None
    last_effective_check = 0.0
    def options():
        with lock:
            return applied.options()
    from .mobile import KaffeineMobile
    mobile = KaffeineMobile(options, lambda msg: events.put(("warning", str(msg))))
    tap = CaptionTap(str(endpoint), options, events, packet_sink=mobile.receive)
    try:
        tap.start()
    except (OSError, RuntimeError) as exc:
        control.close()
        # No receiver means nothing to preserve in the background.
        # Let the error window close normally instead of leaving an
        # invisible Qt process running forever with no subtitle source.
        window.terminating = True
        app.setQuitOnLastWindowClosed(True)
        status.setText("Cannot receive Kaffeine DVB stream: "+str(exc))
        window.show()
        return app.exec_()

    current_text = ""
    current_until = 0.0
    last_published = 0.0
    current_cue = None

    def from_controls():
        selected = subtitle_track.currentData()
        # A Teletext subtitle channel's language is signalled by the
        # broadcaster. Never run French captions through a German
        # translator merely because the prior Spoken box said 'de'.
        chosen_track = (selected if isinstance(selected, dict) and
                        mode.currentData() in ("auto","teletext","page") else None)
        selected_audio = audio_track.currentData()
        chosen_audio = (selected_audio if isinstance(selected_audio, dict) and
                        mode.currentData() in ("asr", "auto") else None)
        hinted = (chosen_track.get("source_hint") or
                  chosen_track.get("language") if chosen_track else
                  chosen_audio.get("source_hint") or
                  chosen_audio.get("language") if chosen_audio else None)
        spoken = language_code(hinted or source.currentText())
        raw_targets = [
            lang for lang, check in language_boxes.items() if check.isChecked()]
        raw_targets.extend(x.strip() for x in extra_targets.text().replace(
            ";", ",").split(",") if x.strip())
        # Never remove the explicitly checked EN/TR checkbox when the
        # broadcaster changes its actual Teletext or audio source language:
        # requested output EN is valid even when EN is already the original.
        target_langs = tuple(dict.fromkeys(
            language_code(lang, nllb=True) for lang in raw_targets))
        output = display_mode.currentData()
        return CaptionConfig(
            mode=mode.currentData(), source=spoken,
            target=target_langs[0] if target_langs else spoken,
            target_languages=target_langs if output != "original" else (),
            page=chosen_track["page"] if chosen_track else page.value(),
            teletext_pid=chosen_track["pid"] if chosen_track else None,
            audio_pid=chosen_audio["pid"] if chosen_audio else None,
            audio_language=(language_code(chosen_audio.get("source_hint") or
                                chosen_audio.get("language"))
                            if chosen_audio and (chosen_audio.get("source_hint") or
                                                 chosen_audio.get("language")) not in (None, "und")
                            else None),
            speaker_enabled=speaker_enabled.isChecked(),
            speaker_provider=speaker_provider.currentData(),
            speaker_aliases=(),
            offset_ms=round(caption_offset.value()*1000),
            playback_delay_ms=round(playback_delay.value()*1000),
            automatic_sync=automatic.isChecked(),
            on_video=show_video.isChecked(),
            show_original=output in ("original","both"),
            show_translation=output in ("translated","both"),
            position=position.currentText(),font_px=font.value(),
            opacity=opacity.value(),text_opacity=text_opacity.value(),
            text_color=active_colors["text"],
            background_color=active_colors["background"]
        ).validate()

    def set_pending(*_):
        pending.setText("Unsaved changes — press Apply")
        pending.setStyleSheet("color:#f7bf6e")
    for w in (mode,source,display_mode,position,subtitle_track,
              audio_track,speaker_provider):
        w.currentIndexChanged.connect(set_pending)
    def subtitle_source_selected(*_):
        selected = subtitle_track.currentData()
        if isinstance(selected,dict):
            language = selected.get("source_hint")
            if mode.currentData() in ("auto","teletext","page"):
                chosen = selected.get("source_hint") or selected.get("language")
                if chosen:
                    source.setCurrentText(language_code(chosen))
                if language not in LANGS:
                    track_status.setText(
                        "Original broadcaster subtitles remain available. "
                        "Choose a matching language pack in Model Market if "
                        "you also want these captions translated.")
        set_pending()
    subtitle_track.currentIndexChanged.connect(subtitle_source_selected)
    def audio_source_selected(*_):
        selected = audio_track.currentData()
        if isinstance(selected, dict):
            language = selected.get("source_hint")
            if mode.currentData() in ("asr", "auto"):
                chosen = selected.get("source_hint") or selected.get("language")
                if chosen and chosen != "und":
                    source.setCurrentText(language_code(chosen))
                detected = selected.get("source_hint") or selected.get("language")
                if (not detected or
                        language_code(detected) not in WHISPER_LANGUAGES):
                    audio_track_status.setText(
                        "This audio language is not in Whisper's supported "
                        "language set. You can display broadcast Teletext "
                        "instead or select another available soundtrack.")
        set_pending()
    audio_track.currentIndexChanged.connect(audio_source_selected)
    extra_targets.textChanged.connect(set_pending)
    presets.currentIndexChanged.connect(set_pending)
    source.currentTextChanged.connect(set_pending)
    for w in (page,caption_offset,playback_delay,font,opacity,text_opacity):
        w.valueChanged.connect(set_pending)
    for w in (show_video,automatic,speaker_enabled,*language_boxes.values()):
        w.toggled.connect(set_pending)

    def apply_settings():
        nonlocal applied, current_text, current_until, current_cue
        try:
            selected = from_controls()
            previous = applied
            if selected.mode != previous.mode or selected.source != previous.source or (
                    selected.target_languages != previous.target_languages) or (
                    selected.speaker_enabled != previous.speaker_enabled or
                    selected.speaker_provider != previous.speaker_provider or
                    selected.speaker_aliases != previous.speaker_aliases):
                estimator.clear()
            # Switching automatic control ON starts the calibration afresh.
            if selected.automatic_sync != previous.automatic_sync:
                auto_controller.reset()
            with lock:
                applied = __import__("dataclasses").replace(
                    selected, revision=applied.revision+1)
            cues.clear()
            current_cue = None
            current_text = ""
            current_until = 0.0
            original.setText("Waiting for captions under the new settings…")
            translated.setText("")
            ipc.publish("",applied)
            ipc.set_playback_delay(applied)
            automatic_active = applied.automatic_sync and applied.mode not in ("off","page","teletext")
            sync_estimate.setText(
                ("Automatic timing enabled · collecting live Whisper samples ("
                 + str(len(estimator.values)) + "/3); conservative maximum "
                 + str(estimator.ceiling_ms / 1000) + " s.")
                if automatic_active else
                "Automatic timing OFF; measured recommendations will not change playback.")
            pending.setText("Applied · " + applied.mode + " · " + applied.source.upper() +
                            " → " + (" + ".join(lang.upper() for lang in
                                applied.target_languages) or "original only") +
                            " · playback buffer " + str(applied.playback_delay_ms/1000) + " s")
            from tv_center.ai_settings import AISettings
            from tv_center.free_speakers import FreeSpeakerMarket
            from tv_center.speaker_market import SpeakerMarket
            active_ai = AISettings().values
            provider_ready = (FreeSpeakerMarket().status()["installed"]
                              if applied.speaker_provider == "resemblyzer"
                              else SpeakerMarket().status()["installed"])
            speaker_health.setText(
                ("Automatic voice labels ON · installed offline " +
                 applied.speaker_provider + " model" if (
                    applied.speaker_enabled and provider_ready) else
                 "Auto labels selected, but "+applied.speaker_provider+
                 " is NOT installed: open Model Market → Speaker separation"
                 if applied.speaker_enabled else "Voice labels OFF"))
            translation_health.setText(
                "Selected translator: " +
                (active_ai.get("translation_model","argos").upper()
                 if active_ai.get("translation_enabled") else "OFF") +
                " · waiting for real subtitle/translation status")
            pending.setStyleSheet("color:#9ed7ba")
            status.setText("Applied. Caption offset: "+str(applied.offset_ms/1000)+
                           "s; TV playback buffer: "+str(applied.playback_delay_ms/1000)+
                           "s. Real ASR timing varies with model CPU/GPU performance.")
        except (ValueError, OSError) as exc:
            status.setText("Settings were not applied: " + str(exc))

    def reset_settings():
        mode.setCurrentIndex(0)
        source.setCurrentText("de"); display_mode.setCurrentIndex(1)
        for lang, check in language_boxes.items():
            check.setChecked(lang == "tr")
        subtitle_track.setCurrentIndex(0)
        audio_track.setCurrentIndex(0)
        extra_targets.clear()
        page.setValue(150)
        caption_offset.setValue(0.0); playback_delay.setValue(0.0)
        automatic.setChecked(False)
        speaker_enabled.setChecked(True)
        speaker_provider.setCurrentIndex(0)
        show_video.setChecked(True)
        position.setCurrentText("bottom"); font.setValue(25)
        presets.setCurrentIndex(0)
        apply_appearance_preset()
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
        nonlocal applied, last_service_id, last_effective_check
        # Kaffeine is the DVB owner. Terminate sidecar when it disappears,
        # including when the settings window has been hidden.
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            window.terminating = True
            app.quit()
            return
        except PermissionError:
            pass
        mobile.expire_if_idle()
        now = time.monotonic()
        if now - last_effective_check >= 1.0:
            last_effective_check = now
            effective = ipc.read_effective_delay()
            if effective is None:
                effective_status.setText(
                    "Native TV delay: Kaffeine has not reported its active MPEG-TS "
                    "buffer yet; requested value is not confirmed.")
            else:
                actual = effective["effective_ms"] / 1000
                requested = effective["requested_ms"] / 1000
                rate = effective["ts_bytes_per_second"] / 1024 / 1024
                effective_status.setText(
                    f"Native TV delay: {actual:.1f} s applied / "
                    f"{requested:.1f} s requested · TS {rate:.2f} MiB/s" +
                    (" · Limited by memory, timeshift or recovery cooldown."
                     if effective["capped"] else " · Within native safety budget."))
        # Never reuse an ASR processing estimate across distinct TV services.
        if mobile.service_id != last_service_id:
            if last_service_id is not None:
                estimator.clear()
                auto_controller.reset()
                sync_estimate.setText("Channel changed · recalibrating automatic sync.")
            last_service_id = mobile.service_id
        for _ in range(8):
            try:
                kind, data = events.get_nowait()
            except queue.Empty:
                break
            if kind == "show_settings":
                window.showNormal()
                window.raise_()
                window.activateWindow()
            elif kind == "teletext_tracks":
                selected = subtitle_track.currentData()
                previous_identity = ((selected.get("pid"),selected.get("page"),
                                      selected.get("language"))
                                     if isinstance(selected,dict) else None)
                subtitle_track.blockSignals(True)
                subtitle_track.clear()
                subtitle_track.addItem(
                    "Automatic broadcaster subtitles (no selected page)", None)
                current = 0
                for desc in data.get("tracks", ()):
                    if not isinstance(desc,dict):
                        continue
                    item = dict(desc)
                    subtitle_track.addItem(item["label"], item)
                    if (item["pid"],item["page"],item["language"]) == previous_identity:
                        current = subtitle_track.count()-1
                subtitle_track.setCurrentIndex(current)
                subtitle_track.blockSignals(False)
                old_audio = audio_track.currentData()
                previous_audio_pid = (
                    old_audio.get("pid") if isinstance(old_audio, dict) else None)
                audio_track.blockSignals(True)
                audio_track.clear()
                audio_track.addItem(
                    "Automatic · prefer spoken language / regular audio", None)
                selected_audio_index = 0
                for desc in data.get("audio_tracks", ()):
                    if not isinstance(desc, dict):
                        continue
                    item = dict(desc)
                    audio_track.addItem(item["label"], item)
                    if item.get("pid") == previous_audio_pid:
                        selected_audio_index = audio_track.count()-1
                audio_track.setCurrentIndex(selected_audio_index)
                audio_track.blockSignals(False)
                audio_count = audio_track.count()-1
                audio_track_status.setText(
                    f"{audio_count} broadcast-signalled audio channel(s). "
                    "Choose a PID for Whisper, then Apply. "
                    "The speaker source language may also need setting.")
                if previous_audio_pid is not None and selected_audio_index == 0:
                    with lock:
                        applied = __import__("dataclasses").replace(
                            applied, audio_pid=None, revision=applied.revision+1)
                    cues.clear()
                    set_pending()
                count = subtitle_track.count()-1
                track_status.setText(
                    (f"{count} broadcast-signalled Teletext subtitle "
                     f"channel(s) detected. Choose one, then Apply."
                     if count else
                     "No Teletext subtitle descriptor detected on this service. "
                     "You can still use Whisper or manual page mode."))
                if previous_identity is not None and current == 0:
                    # On a channel change, never reuse stale PID/page settings.
                    # Revert the applied subtitle selection immediately to
                    # neutral while preserving other active user settings.
                    with lock:
                        applied = __import__("dataclasses").replace(
                            applied, teletext_pid=None, revision=applied.revision+1)
                    cues.clear()
                    set_pending()
            elif kind == "remote_page":
                subtitle_track.setCurrentIndex(0)
                mode.setCurrentIndex(3)
                page.setValue(int(data))
                apply_settings()
            elif kind == "caption":
                if data.get("revision") != applied.revision:
                    continue
                if data.get("original"):
                    real_source = data.get("source", "")
                    estimator.observe(
                        data["captured_start"], data["captured_end"],
                        data["decoded_at"], real_source)
                    recommendation = estimator.recommend(
                        bytes_per_second=tap.bytes_per_second)
                    if recommendation:
                        sync_estimate.setText(
                            recommendation.summary +
                            (" · AUTO ACTIVE" if applied.automatic_sync else
                             " · automatic OFF; manual playback unchanged") +
                            " · This is a chunk-based estimate, not exact word alignment.")
                        active_auto = applied.automatic_sync and applied.mode in ("asr","auto")
                        desired = auto_controller.next_delay(
                            recommendation, applied.playback_delay_ms, now, active_auto)
                        if desired is not None:
                            revised = __import__("dataclasses").replace(
                                applied, playback_delay_ms=desired)
                            try:
                                ipc.set_playback_delay(revised)
                            except OSError as error:
                                status.setText("Automatic playback adjustment failed: " + str(error))
                            else:
                                with lock:
                                    applied = revised
                                # The text field mirrors the *active* delay,
                                # not an uncommitted manual change.
                                playback_delay.blockSignals(True)
                                playback_delay.setValue(desired / 1000)
                                playback_delay.blockSignals(False)
                                pending.setText("Auto sync active · TV buffer " +
                                                f"{desired/1000:.1f} s")
                    else:
                        sync_estimate.setText(
                            f"Automatic timing: {len(estimator.values)}/3 real Whisper "
                            "samples. No recommendation yet; playback unchanged.")
                    # The native 64-MiB MPEG-TS FIFO may apply less delay
                    # than the UI requested. Schedule text against the
                    # confirmed playback delay when its status matches the
                    # current request; never reuse a stale channel setting.
                    cue_config = effective_cue_config(
                        applied, ipc.read_effective_delay())
                    cue = enqueue_word_cues(
                        cues, data, cue_config,
                        data["captured_start"],data["captured_end"],
                        data["decoded_at"])
                    if cue is None:
                        cue = cues.add(data, cue_config,
                                       data["captured_start"],data["captured_end"],
                                       data["decoded_at"])
                    delay_verified = (
                        cue_config.playback_delay_ms != applied.playback_delay_ms or
                        (ipc.read_effective_delay() or {}).get("requested_ms")
                        == applied.playback_delay_ms)
                    actual_backend = data.get("asr_backend")
                    backend_info = (
                        " | Whisper: "+actual_backend.upper() +
                        " · "+str(data.get("asr_model") or "unknown model") +
                        (" ("+str(data["asr_engine"])+")" if data.get("asr_engine") else "")
                        if actual_backend else "")
                    status.setText("Real "+data.get("source","unknown")+backend_info+
                        " | ASR+translate latency: "+
                        f"{int((data['decoded_at']-data['captured_end'])*1000)}ms" +
                        " | Caption lateness vs "+(
                            "applied TV delay: " if delay_verified else
                            "requested TV delay (unconfirmed): ") +
                        str(cue["lateness_ms"])+"ms" +
                        " | DVB TS packets: "+str(tap.packet_count) +
                        " | Backlog: "+str(tap.work_queue.snapshot()["queued_clips"]) +
                        " clips ("+str(tap.work_queue.snapshot()["queued_mib"])+" MiB)")
                    timing = data.get("processing_ms") or {}
                    if timing:
                        status.setText(status.text() +
                            " | Stages: TT "+str(timing.get("teletext",0))+"ms"+
                            " / ASR "+str(timing.get("asr",0))+"ms"+
                            " / translation "+str(timing.get("translation",0))+"ms")
                    ts_health = tap.transport_health.snapshot()
                    status.setText(status.text()+
                        " | TS continuity gaps: "+str(ts_health["continuity_gaps"])+
                        " (RF or nonblocking sidecar loss; not distinguished)")
                    if data.get("word_timing_source"):
                        status.setText(status.text() +
                            " | Speech-follow: real GPU word timestamps; "
                            "translated word pacing is approximate")
                    if data.get("speaker_error"):
                        status.setText(status.text() +
                            " | Diarization unavailable: " +
                            str(data["speaker_error"]))
                    elif data.get("speaker_turns"):
                        status.setText(status.text() +
                            " | Offline speakers: " +
                            str(data.get("speaker_engine") or "local model") +
                            " · provisional voice clusters")
                    if data.get("audio_notice"):
                        status.setText(status.text() + "\n" + data["audio_notice"])
                    failures = data.get("translation_errors") or {}
                    backup = data.get("translation_warnings") or {}
                    actual_engines = data.get("translation_engines") or {}
                    if actual_engines:
                        translation_health.setText(
                            "Live translation: " +
                            " · ".join(lang.upper()+" → "+
                                str(engine).replace("-", " ")
                                for lang, engine in actual_engines.items()))
                    elif failures:
                        translation_health.setText(
                            "Requested translation unavailable: " +
                            ", ".join(sorted(failures)).upper() +
                            " · showing original " +
                            str(data.get("source_language") or applied.source).upper())
                    if backup:
                        status.setText(status.text() +
                            " | Translator: Argos fallback (" +
                            ", ".join(sorted(backup)).upper() + ")")
                    elif failures:
                        status.setText(status.text() +
                            " | Translation unavailable (" +
                            ", ".join(sorted(failures)).upper() +
                            ") · original speech retained")
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
            source_language = str(result.get("source_language") or applied.source).upper()
            original.setText("ORIGINAL [" + source_language + "]: " +
                             result.get("original", ""))
            translations = result.get("translations") or {}
            failures = result.get("translation_errors") or {}
            fallback = result.get("translation_warnings") or {}
            if applied.show_translation and applied.target_languages:
                available = [
                    lang.upper() + ": " + translations[lang]
                    for lang in applied.target_languages
                    if isinstance(translations.get(lang), str) and
                    translations[lang].strip()]
                if available:
                    heading = ("TRANSLATIONS · Argos backup: " if fallback else
                               "TRANSLATIONS: ")
                    missing = [
                        lang.upper() for lang in applied.target_languages
                        if lang in failures and lang not in translations]
                    translated.setText(
                        heading + " · ".join(available) +
                        (" · " + ", ".join(missing) + " unavailable"
                         if missing else ""))
                else:
                    requested = ", ".join(applied.target_languages).upper()
                    translated.setText(
                        "Translation unavailable for " + requested +
                        " · original " + source_language +
                        " subtitles remain visible.")
                if failures:
                    translated.setToolTip(
                        "Offline translator diagnostics (not subtitles):\n" +
                        "\n".join(lang.upper()+": "+str(message)[:180]
                                  for lang,message in failures.items()))
                elif fallback:
                    translated.setToolTip(
                        "NLLB could not produce output; the installed Argos "
                        "language pack handled this phrase.")
                else:
                    translated.setToolTip("Translation output is local/offline.")
            else:
                translated.setText("")
                translated.setToolTip("Translations are not selected.")
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
    # The small status area or tray can reopen a hidden panel; the main
    # Kaffeine menu can always do this even on COSMIC without a system tray.
    from PyQt5.QtGui import QIcon
    from PyQt5.QtWidgets import QSystemTrayIcon, QMenu, QApplication as QtApplication, QStyle
    tray = None
    if QSystemTrayIcon.isSystemTrayAvailable():
        tray = QSystemTrayIcon(QIcon.fromTheme("video-display",
            app.style().standardIcon(QStyle.SP_MediaPlay)), window)
        tray.setToolTip("TIHULU subtitles active · click to reopen settings")
        menu = QMenu()
        reopen_action = menu.addAction("Show subtitle settings")
        reopen_action.triggered.connect(
            lambda: (window.showNormal(), window.raise_(), window.activateWindow()))
        quit_action = menu.addAction("Stop subtitles & Exit")
        quit_action.triggered.connect(app.quit)
        tray.setContextMenu(menu)
        tray.activated.connect(lambda reason: (
            window.showNormal(), window.raise_(), window.activateWindow())
            if reason == QSystemTrayIcon.Trigger else None)
        tray.show()

    def stop_caption_service():
        window.terminating = True
        app.quit()

    hide_panel.clicked.connect(window.hide)
    stop_subtitles.clicked.connect(stop_caption_service)

    def cleanup():
        if tray:
            tray.hide()
        mobile.close()
        tap.close()
        ipc.close()
        control.close()
    app.aboutToQuit.connect(cleanup)
    window.show()
    return app.exec_()

if __name__ == "__main__":
    raise SystemExit(main())
