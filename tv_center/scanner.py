"""On-demand country-aware digital TV/radio auto scanner.

DVB-T/T2 aerial and DVB-C cable are distinct scan modes. The source country
selects actual country-specific w_scan_cpp parameters, not a channel catalog.
The tuner is never opened at import and no scan runs in the background.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import threading
import time

PROFILES = {
    "DE": {"name": "Germany", "terrestrial": "DVB-T/T2", "cable": "DVB-C"},
    "TR": {"name": "Türkiye", "terrestrial": "DVB-T/T2", "cable": "DVB-C"},
}
MODES = {"t": "Terrestrial DVB-T/T2", "c": "Cable DVB-C"}


class ScanError(RuntimeError):
    pass


def scan_commands(country: str, medium: str, adapter: int,
                  transponder_file: Path, channel_file: Path) -> tuple[list[str], list[str]]:
    if country not in PROFILES or medium not in MODES or type(adapter) is not int or not 0 <= adapter <= 15:
        raise ValueError("Invalid scan country, delivery mode or DVB adapter")
    return (
        ["w_scan_cpp", "-f", medium, "-c", country, "-a", str(adapter),
         "-R", "1", "-T", "1", "-E", "1", "-x"],
        ["dvbv5-scan", "-a", str(adapter), "-C", country,
         "-T", "5", "-o", str(channel_file), str(transponder_file)],
    )


def check_dependencies() -> dict:
    return {name: bool(shutil.which(name)) for name in
            ("w_scan_cpp", "dvbv5-scan", "fuser")}


class AutoScanner:
    """Single cancellable foreground-initiated scan with atomic result replacement."""

    def __init__(self):
        self.cancelled = threading.Event()
        self.running = False
        self.process = None
        self._mutex = threading.Lock()

    def cancel(self):
        self.cancelled.set()
        with self._mutex:
            proc = self.process
        if proc is not None and proc.poll() is None:
            proc.terminate()

    def _stage(self, args: list[str], stdout: Path, stderr: Path, limit: int):
        if self.cancelled.is_set():
            raise ScanError("Scan cancelled by user")
        with stdout.open("wb") as out, stderr.open("wb") as err:
            proc = subprocess.Popen(args, stdin=subprocess.DEVNULL,
                                    stdout=out, stderr=err, start_new_session=True)
            with self._mutex:
                self.process = proc
            try:
                try:
                    code = proc.wait(timeout=limit)
                except subprocess.TimeoutExpired:
                    proc.terminate()
                    try: proc.wait(timeout=4)
                    except subprocess.TimeoutExpired: proc.kill(); proc.wait()
                    raise ScanError("Scan timed out; no existing channels were replaced")
            finally:
                with self._mutex:
                    self.process = None
        if self.cancelled.is_set():
            raise ScanError("Scan cancelled by user")
        if code != 0:
            message = stderr.read_text(errors="replace")[-700:]
            raise ScanError(f"Scanner exited with code {code}: {message}")

    def run(self, country="DE", medium="t", adapter=0, directory=None, notify=None):
        if self.running:
            raise ScanError("Another scan is already active")
        output = Path(directory or Path.home()/".config/tihulu-tv-center").expanduser()
        output.mkdir(parents=True, exist_ok=True)
        target = output / f"channels-{country}-{medium}.conf"
        if country not in PROFILES or medium not in MODES or type(adapter) is not int or not 0 <= adapter <= 15:
            raise ValueError("Invalid scan settings")
        deps = check_dependencies()
        if not all(deps.values()):
            missing = ", ".join(n for n, ok in deps.items() if not ok)
            raise ScanError("Required scan programs are missing: " + missing)
        frontend = f"/dev/dvb/adapter{adapter}/frontend0"
        if not Path(frontend).exists():
            raise ScanError("No DVB frontend for selected adapter")
        if subprocess.run(["fuser", "-s", frontend], check=False).returncode == 0:
            raise ScanError("Frontend is busy. Close Kaffeine/Tvheadend/other TV applications.")
        self.running = True
        self.cancelled.clear()
        try:
            with tempfile.TemporaryDirectory(prefix="tihulu-dvbscan-") as temp:
                work = Path(temp)
                table = work/"transponders.conf"
                generated = work/"channels.conf"
                first, second = scan_commands(country, medium, adapter, table, generated)
                if notify: notify("step 1/2: searching frequencies and DVB services")
                self._stage(first, table, work/"search.log", 1200)
                if not table.is_file() or table.stat().st_size < 20:
                    raise ScanError("No detected transponders. Existing channels were retained.")
                if notify: notify("step 2/2: resolving channel names and service IDs")
                self._stage(second, work/"parse.stdout", work/"parse.stderr", 600)
                if not generated.is_file() or generated.stat().st_size < 20:
                    raise ScanError("No channel list produced. Existing channels were retained.")
                from .core import read_channels
                channels = read_channels([generated])
                if not channels:
                    raise ScanError("Scanner returned no usable channels. Existing channels were retained.")
                # Keep the previous list until a real, non-empty country/profile scan succeeds.
                staged = output / (target.name + ".staging")
                staged.write_bytes(generated.read_bytes())
                os.replace(staged, target)
                return {"country": country, "medium": medium, "path": str(target),
                        "channels": len(channels),
                        "frequencies": len({c.frequency for c in channels})}
        finally:
            self.running = False
