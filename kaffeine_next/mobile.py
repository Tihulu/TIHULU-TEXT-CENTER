# SPDX-License-Identifier: GPL-2.0-or-later
"""Explicit PIN-paired phone access using Kaffeine's *current* MPEG-TS stream.

No separate DVB frontend, no remote channel tuning, no cloud service. HTTP
is only for trusted LAN; do not forward the exposed port.
"""
from __future__ import annotations
from threading import RLock
from .mpegts import current_program_id
from tv_center.lan import MobileLAN
from tv_center.streaming import HLSStreamer

class KaffeineMobile:
    def __init__(self, options, notify, caption=None):
        self.options = options
        self.notify = notify
        self.caption = caption or {"original":"", "translated":"", "source":"none"}
        self.service_id = None
        self.http = None
        self.hls = None
        self.lock = RLock()

    def receive(self, datagram: bytes):
        pid = current_program_id(datagram)
        stream_to_stop = None
        with self.lock:
            if pid is not None and self.service_id != pid:
                if self.hls is not None:
                    stream_to_stop = self.hls
                    self.hls = None
                self.service_id = pid
            active = self.hls
        # Channel switching cannot relay the former service to phones.
        if stream_to_stop:
            stream_to_stop.stop()
            self.notify("Live channel changed; restart mobile video deliberately.")
        if active and active is not stream_to_stop:
            active.offer(datagram)

    def snapshot(self):
        with self.lock:
            sid = self.service_id
            streaming = self.hls is not None and self.hls.get_dir() is not None
            caption = dict(self.caption)
        return {
            "source": "live_native_dvb" if sid else "offline",
            "channel": "Kaffeine DVB service "+str(sid) if sid else None,
            "caption": caption,
            "mobile_video": streaming,
            "subtitle_mode": self.options()["mode"],
            "teletext_page": self.options()["page"],
            "supported_languages":["de","en","tr"],
            "web_video":"local_hls_from_Kaffeine_only",
            "pi5_hardware_verified":False,
        }

    def set_caption(self, result):
        with self.lock:
            self.caption = dict(result)

    def enable_lan(self, change_page):
        with self.lock:
            if self.http is not None:
                raise RuntimeError("Phone sharing already enabled")
            server = MobileLAN(self.snapshot, change_page, self.stream_dir)
            data = server.start()
            self.http = server
        return data

    def enable_video(self):
        with self.lock:
            if self.http is None:
                raise RuntimeError("Enable trusted Wi-Fi sharing before video")
            if not self.service_id:
                raise RuntimeError("Watch a TV channel first; no genuine MPEG-TS PAT detected")
            if self.hls is not None:
                return
            runner = HLSStreamer(lambda kind, detail: self.notify(str(detail)))
            runner.start(self.service_id)
            self.hls = runner

    def stop_video(self):
        with self.lock:
            runner = self.hls
            self.hls = None
        if runner:
            runner.stop()

    def stream_dir(self):
        with self.lock:
            runner = self.hls
        return runner.get_dir() if runner else None

    def stop_lan(self):
        # Ensure HLS is stopped before revoking phone sessions.
        self.stop_video()
        with self.lock:
            http = self.http
            self.http = None
        if http:
            http.stop()

    def close(self):
        self.stop_lan()
