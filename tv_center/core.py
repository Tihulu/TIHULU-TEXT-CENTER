"""Linux DVB receiver controller, without WebUSB, VLC or an RTL-SDR dependency.

The TV frontend and the unrelated RTL-SDR receiver are never conflated.
All tuning is owner-triggered. Capture writes short bounded temporary TS
segments only while captions/Teletext are explicitly enabled.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import fcntl
import os
import queue
import re
import select
import shutil
import subprocess
import tempfile
import threading
import time

@dataclass(frozen=True)
class Channel:
    name: str
    path: Path
    frequency: int
    service_id: int | None
    encrypted: bool = False

def read_channels(files: list[Path]) -> list[Channel]:
    result = []
    seen = set()
    for path in files:
        path = Path(path).expanduser()
        if not path.is_file() or path.stat().st_size > 2_000_000:
            continue
        name = None
        attrs = {}
        def commit():
            if not name or not attrs:
                return
            try:
                freq = int(attrs.get("FREQUENCY", "0"), 0)
                sid = int(attrs["SERVICE_ID"], 0) if "SERVICE_ID" in attrs else None
            except ValueError:
                return
            if freq < 40_000_000 or freq > 1_000_000_000:
                return
            key = (freq, sid, name)
            if key not in seen:
                seen.add(key)
                result.append(Channel(name, path, freq, sid,
                          attrs.get("SCRAMBLED", "0") not in ("0", "FALSE", "NO")))
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            s = line.strip()
            if s.startswith("[") and s.endswith("]") and len(s) < 140:
                commit()
                name, attrs = s[1:-1].strip(), {}
            elif "=" in s and name:
                k, v = s.split("=", 1)
                attrs[k.strip().upper()] = v.strip()
        commit()
    return result

def discover_channels() -> list[Channel]:
    home = Path.home()
    files = sorted(home.glob("tv-*-channels.conf"))
    extra = home / ".config/tihulu-tv-center/channels.conf"
    if extra.is_file():
        files.append(extra)
    return read_channels(files)

def zap_argv(channel: Channel, adapter: int = 0) -> list[str]:
    if adapter not in range(0, 16):
        raise ValueError("Adapter must be between 0 and 15")
    if not re.fullmatch(r"[\w .+()/-]{1,120}", channel.name, flags=re.UNICODE):
        raise ValueError("Unsupported channel name")
    return ["dvbv5-zap", "-a", str(adapter), "-c", str(channel.path),
            "-p", "-P", "-r", channel.name]

def player_argv(channel: Channel, window_id: int, hwdec: str = "no") -> list[str]:
    if hwdec not in ("no", "auto-safe"):
        raise ValueError("Unsupported hardware decoding mode")
    if not isinstance(window_id, int) or window_id < 1:
        raise ValueError("A native X11 window ID is required")
    args = ["mpv", "--no-config", "--no-terminal", "--force-window=no",
            "--cache=yes", "--cache-secs=2", "--hwdec=" + hwdec,
            "--wid=" + str(window_id), "--audio-spdif=no"]
    if channel.service_id is not None:
        args.append("--program=" + str(channel.service_id))
    return args + ["-"]

def receiver_status(adapter: int = 0) -> dict:
    root = Path(f"/dev/dvb/adapter{adapter}")
    frontend, dvr = root / "frontend0", root / "dvr0"
    return {
        "adapter": adapter,
        "frontend": str(frontend),
        "frontend_present": frontend.exists(),
        "dvr_present": dvr.exists(),
        "dvbv5_zap": bool(shutil.which("dvbv5-zap")),
        "mpv": bool(shutil.which("mpv")),
        "ffmpeg": bool(shutil.which("ffmpeg")),
        "ffprobe": bool(shutil.which("ffprobe")),
        "other_sdr_touched": False,
        "dvb_firmware_note": "For WinTV-soloHD verify em28xx/Si2168-D60 and dvb-demod-si2168-d60-01.fw."
    }

class ReceiverBusy(RuntimeError):
    pass

class TVCapture:
    """One reader owns a DVB DVR fd and fans TS out to mpv + bounded workers."""
    def __init__(self, adapter: int = 0):
        self.adapter = adapter
        self.channel = None
        self.zap = None
        self.player = None
        self.thread = None
        self.stop_flag = threading.Event()
        self.events = queue.Queue(maxsize=24)
        self.lockfile = None
        self.caption_mode = "off"
        self.page = 150
        self.source_lang, self.target_lang = "de", "tr"
        self.model = ""
        self.hwdec = "no"
        self._lock = threading.Lock()
        self._pending = False

    def emit(self, kind, value):
        try:
            self.events.put_nowait((kind, value))
        except queue.Full:
            pass

    def set_captions(self, mode: str, page=150, source="de", target="tr", model=""):
        if mode not in ("off", "teletext", "asr", "auto", "page"):
            raise ValueError("Invalid caption mode")
        if type(page) is not int or not (100 <= page <= 899):
            raise ValueError("Teletext page must be 100-899")
        if source not in ("tr", "de", "en") or target not in ("tr", "de", "en"):
            raise ValueError("Unsupported language")
        with self._lock:
            self.caption_mode, self.page = mode, page
            self.source_lang, self.target_lang, self.model = source, target, model

    def _lease(self):
        frontend = f"/dev/dvb/adapter{self.adapter}/frontend0"
        if not Path(frontend).exists():
            raise ReceiverBusy("DVB frontend is not connected")
        # Check non-cooperating programs too (Kaffeine, Tvheadend, dvbv5-zap).
        if shutil.which("fuser"):
            check = subprocess.run(["fuser", "-s", frontend], timeout=3, check=False)
            if check.returncode == 0:
                raise ReceiverBusy("Frontend already opened by another TV application")
        lock = Path(os.environ.get("XDG_RUNTIME_DIR", tempfile.gettempdir())) / f"tihulu-tv-adapter{self.adapter}-{os.getuid()}.lock"
        fd = os.open(lock, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            os.close(fd)
            raise ReceiverBusy("Another TIHULU TV session owns this adapter") from exc
        self.lockfile = fd

    def start(self, channel: Channel, window_id: int, hwdec: str = "no"):
        if self.thread and self.thread.is_alive():
            raise ReceiverBusy("Stop the current TV session before changing channel")
        st = receiver_status(self.adapter)
        if not all(st[k] for k in ("frontend_present", "dvr_present", "dvbv5_zap", "mpv")):
            raise RuntimeError("Missing DVB device or required dvb-tools/mpv dependency")
        self._lease()
        self.stop_flag.clear()
        self.channel = channel
        self.hwdec = hwdec
        try:
            self.zap = subprocess.Popen(zap_argv(channel, self.adapter),
                              stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, start_new_session=True)
            time.sleep(0.8)
            if self.zap.poll() is not None:
                raise RuntimeError("dvbv5-zap exited before tuning; inspect channel and tuner")
            self.player = subprocess.Popen(player_argv(channel, window_id, hwdec),
                              stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, start_new_session=True)
            os.set_blocking(self.player.stdin.fileno(), False)
            self.thread = threading.Thread(target=self._pump, daemon=True, name="tihulu-tv-dvb")
            self.thread.start()
            self.emit("status", "Tuned to " + channel.name + "; receiving live transport stream")
        except BaseException:
            self.stop()
            raise

    def _pump(self):
        dvr = None
        try:
            dvr = os.open(f"/dev/dvb/adapter{self.adapter}/dvr0", os.O_RDONLY | os.O_NONBLOCK)
            with tempfile.TemporaryDirectory(prefix="tihulu-tv-") as tmp:
                clip = None
                start = time.monotonic()
                total = 0
                while not self.stop_flag.is_set():
                    if self.zap.poll() is not None:
                        raise RuntimeError("DVB tuner process stopped")
                    readable, _, _ = select.select([dvr], [], [], 0.25)
                    if not readable:
                        continue
                    try:
                        buf = os.read(dvr, 188 * 512)
                    except BlockingIOError:
                        continue
                    if not buf:
                        continue
                    if self.player and self.player.poll() is None:
                        try:
                            os.write(self.player.stdin.fileno(), buf)
                        except (BlockingIOError, BrokenPipeError):
                            # Drop packets rather than block the tuner indefinitely.
                            self.emit("warning", "Player backpressure: video packets dropped")
                    with self._lock:
                        mode, page = self.caption_mode, self.page
                        source, target, model = self.source_lang, self.target_lang, self.model
                    if mode == "off":
                        if clip:
                            clip.close()
                            clip = None
                        continue
                    if clip is None:
                        clip = open(Path(tmp) / "segment.ts", "wb")
                        start, total = time.monotonic(), 0
                    clip.write(buf)
                    total += len(buf)
                    if time.monotonic() - start >= 12 or total >= 24 * 1024 * 1024:
                        clip.close()
                        clip = None
                        if not self._pending:
                            self._pending = True
                            path = str(Path(tmp) / "segment.ts")
                            data = Path(path).read_bytes()
                            threading.Thread(target=self._decode, args=(data, mode, page, source, target, model),
                                             daemon=True, name="tihulu-tv-captions").start()
                        # If analysis is slower than reception, skip this segment.
                if clip:
                    clip.close()
        except (OSError, RuntimeError) as exc:
            self.emit("error", str(exc))
        finally:
            if dvr is not None:
                os.close(dvr)
            self.emit("status", "TV capture ended")

    def _decode(self, data, mode, page, source, target, model):
        try:
            from .captions import decode_segment
            result = decode_segment(data, mode=mode, page=page, source=source,
                                    target=target, model=model)
            if result.get("original"):
                self.emit("caption", result)
            elif result.get("error"):
                self.emit("warning", result["error"])
        except Exception as exc:
            self.emit("warning", "Caption engine: " + str(exc)[:180])
        finally:
            self._pending = False

    def stop(self):
        self.stop_flag.set()
        for proc in (self.player, self.zap):
            if proc is not None and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=1.5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=1)
        self.player, self.zap = None, None
        if self.thread and self.thread.is_alive() and threading.current_thread() != self.thread:
            self.thread.join(timeout=1.0)
        if self.lockfile is not None:
            fcntl.flock(self.lockfile, fcntl.LOCK_UN)
            os.close(self.lockfile)
            self.lockfile = None
        self.emit("status", "Receiver released")
