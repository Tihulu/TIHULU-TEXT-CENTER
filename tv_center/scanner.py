"""Opt-in DVB-T/T2/C/S2 scan, with real progress and passive signal readings.

Country-based terrestrial/cable sweeps use w_scan_cpp. Satellite uses the
selected orbital position and a real DVB-S/S2 frontend, not country
frequencies. A successfully resolved channel file is atomically promoted.
"""
from __future__ import annotations

from pathlib import Path
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time

from .satellite import SATELLITES, satellite_scan_args, satellite_followup_args

PROFILES = {
    "DE": {"name":"Germany"},
    "TR": {"name":"Türkiye"},
}
MODES = {"t":"Antenna · DVB-T/T2", "c":"Cable · DVB-C", "s":"Satellite · DVB-S/S2"}

class ScanError(RuntimeError):
    pass


def scan_commands(country: str, medium: str, adapter: int,
                  transponder_file: Path, channel_file: Path,
                  satellite: str = "S42E0", diseqc_port: int | None = None):
    if country not in PROFILES or medium not in MODES or type(adapter) is not int or not 0 <= adapter <= 15:
        raise ValueError("Invalid scan country, delivery mode or DVB adapter")
    if medium == "s":
        return (satellite_scan_args(adapter, satellite, diseqc_port),
                satellite_followup_args(adapter, transponder_file, channel_file,
                                        diseqc_port=diseqc_port))
    return (
        ["w_scan_cpp", "-f", medium, "-c", country, "-a", str(adapter),
         "-R", "1", "-T", "1", "-E", "1", "-x", "-v"],
        ["dvbv5-scan", "-a", str(adapter), "-C", country,
         "-T", "5", "-o", str(channel_file), str(transponder_file)],
    )


def check_dependencies():
    return {name: bool(shutil.which(name)) for name in
            ("w_scan_cpp", "dvbv5-scan", "fuser")}


def parse_scan_progress(line: str):
    """Return only what the external scanner actually reported."""
    line = re.sub(r"[\x00-\x08\x0b-\x1f\x7f\x1b]", "", line).strip()[-280:]
    if not line:
        return None
    # Frequencies and services must be extracted from the real scan, not a catalog.
    frequency = re.search(r"(?<!\d)(\d{3,12})(?:\s*(?:kHz|MHz|Hz))?(?!\d)", line)
    names = re.search(r"(?:service(?:_name)?|channel|program)\s*[:=]\s*(.{2,90})", line, re.I)
    return {"kind": "log", "text": line,
            "frequency_reported": frequency.group(1) if frequency else None,
            "service_reported": names.group(1).strip() if names else None}


def passive_signal(adapter: int):
    """Best-effort read-only frontend statistic sampling; never retunes."""
    if not shutil.which("dvb-fe-tool"):
        return {"available": False, "reason": "dvb-fe-tool not installed"}
    try:
        p = subprocess.run(["dvb-fe-tool", "-a", str(adapter), "-m"],
                           stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, timeout=1.6, check=False)
        raw = p.stdout.decode("utf-8", "replace")
    except subprocess.TimeoutExpired as exc:
        raw = (exc.stdout or b"").decode("utf-8", "replace")
    except (OSError, ValueError) as exc:
        return {"available": False, "reason": str(exc)[:100]}
    from .core import parse_signal_log
    parsed = parse_signal_log(raw)
    if not parsed["lock_readings"]:
        return {"available": False, "reason": "Driver did not expose usable simultaneous frontend statistics"}
    parsed["available"] = True
    return parsed


class AutoScanner:
    def __init__(self):
        self.cancelled = threading.Event()
        self.running = False
        self.process = None
        self._mutex = threading.Lock()
        self._latest = {}

    def cancel(self):
        self.cancelled.set()
        with self._mutex:
            proc = self.process
        if proc is not None and proc.poll() is None:
            proc.terminate()

    def _stage(self, args, stdout: Path, stderr: Path, limit: int,
               notify=None, stage=1, adapter=0, partial_file=None):
        if self.cancelled.is_set():
            raise ScanError("Scan cancelled")
        with stdout.open("wb") as out, stderr.open("wb") as err:
            proc = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=out,
                                    stderr=err, start_new_session=True)
            with self._mutex:
                self.process = proc
            started = time.monotonic()
            last_tail = 0
            last_signal = 0
            last_names = set()
            try:
                while proc.poll() is None:
                    if self.cancelled.is_set():
                        proc.terminate()
                        raise ScanError("Scan cancelled; previous channel list preserved")
                    if time.monotonic() - started > limit:
                        proc.terminate()
                        raise ScanError("Scan timed out; previous channel list preserved")
                    now = time.monotonic()
                    if now - last_tail >= 0.65:
                        last_tail = now
                        # Read bounded log tail. No large stdout/stderr accumulation in RAM.
                        try:
                            with stderr.open("rb") as log:
                                log.seek(max(0, log.seek(0, os.SEEK_END) - 8192))
                                recent = log.read().decode("utf-8", "replace")
                        except OSError:
                            recent = ""
                        if recent:
                            for line in recent.splitlines()[-8:]:
                                obj = parse_scan_progress(line)
                                if obj and obj["text"] != self._latest.get("line"):
                                    self._latest["line"] = obj["text"]
                                    if notify: notify({"stage": stage, **obj})
                                    if obj.get("service_reported") and notify:
                                        notify({"stage": stage, "kind": "found",
                                                "channel": obj["service_reported"],
                                                "frequency": None, "provisional": True})
                        if partial_file and partial_file.is_file():
                            from .core import read_channels
                            for channel in read_channels([partial_file]):
                                key = (channel.name, channel.service_id, channel.frequency)
                                if key not in last_names:
                                    last_names.add(key)
                                    if notify: notify({"stage": stage, "kind":"found",
                                                       "channel": channel.name,
                                                       "frequency": channel.frequency,
                                                       "count": len(last_names)})
                    if now - last_signal >= 5.0:
                        last_signal = now
                        if notify: notify({"stage": stage, "kind":"signal",
                                           "metrics": passive_signal(adapter)})
                    time.sleep(0.35)
                if self.cancelled.is_set():
                    raise ScanError("Scan cancelled; previous channel list preserved")
                if proc.returncode != 0:
                    message = stderr.read_text(errors="replace")[-600:]
                    raise ScanError(f"Scanner exited {proc.returncode}: {message}")
            finally:
                with self._mutex:
                    self.process = None
                if proc.poll() is None:
                    proc.terminate()
                    try: proc.wait(timeout=3)
                    except subprocess.TimeoutExpired: proc.kill(); proc.wait()

    def run(self, country="DE", medium="t", adapter=0, directory=None, notify=None,
            satellite="S42E0", diseqc_port=None):
        if self.running:
            raise ScanError("Another scan is already active")
        if country not in PROFILES or medium not in MODES or type(adapter) is not int or not 0 <= adapter <= 15:
            raise ValueError("Invalid scan profile")
        if medium == "s" and satellite not in SATELLITES:
            raise ValueError("Unsupported satellite")
        deps = check_dependencies()
        if not all(deps.values()):
            raise ScanError("Missing: " + ", ".join(k for k, ok in deps.items() if not ok))
        frontend = f"/dev/dvb/adapter{adapter}/frontend0"
        if not Path(frontend).exists():
            raise ScanError("Selected Linux DVB frontend missing")
        if subprocess.run(["fuser", "-s", frontend], timeout=3,
                          check=False).returncode == 0:
            raise ScanError("Tuner busy. Stop TV/Kaffeine/Tvheadend before scanning.")
        # This is an explicit action. A satellite-mode capable frontend
        # has to be connected; the tuner itself rejects unsupported systems.
        output = Path(directory or Path.home()/".config/tihulu-tv-center").expanduser()
        output.mkdir(parents=True, exist_ok=True)
        suffix = country + "-" + medium + ("-" + satellite if medium == "s" else "")
        target = output / ("channels-" + suffix + ".conf")
        self.running = True
        self.cancelled.clear()
        self._latest.clear()
        try:
            with tempfile.TemporaryDirectory(prefix="tihulu-dvbscan-") as tmp:
                root = Path(tmp)
                initial = root / "transponders.conf"
                channels_file = root / "channels.conf"
                first, second = scan_commands(country, medium, adapter, initial,
                                               channels_file, satellite, diseqc_port)
                if notify: notify({"stage":1, "kind":"status", "text":"Discovering real RF transponders"})
                self._stage(first, initial, root/"search.log", 1200, notify, 1, adapter)
                if not initial.is_file() or initial.stat().st_size < 20:
                    raise ScanError("No real transponders detected. Prior channels retained.")
                if notify: notify({"stage":2, "kind":"status", "text":"Resolving services from discovered transponders"})
                self._stage(second, root/"channels.stdout", root/"channels.log", 900,
                            notify, 2, adapter, channels_file)
                from .core import read_channels
                discovered = read_channels([channels_file])
                if not discovered:
                    raise ScanError("No DVB service list created; prior channels retained")
                for n, c in enumerate(discovered):
                    if notify: notify({"stage":2, "kind":"found", "channel":c.name,
                                       "frequency":c.frequency, "count":n+1})
                # Preserve the owner's channel preferences in a separate file.
                staged = output / (target.name + ".staging")
                staged.write_bytes(channels_file.read_bytes())
                os.replace(staged, target)
                if notify: notify({"stage":3, "kind":"complete", "count":len(discovered)})
                return {"country": country, "medium": medium, "satellite":satellite,
                        "path":str(target), "channels":len(discovered),
                        "frequencies":len({c.frequency for c in discovered})}
        finally:
            self.running = False
