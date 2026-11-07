"""Standalone local satellite pass planner and bounded RTL-SDR capture service.

No RF or Internet activity until an operator requests a scan/refresh or
explicitly schedules a pass. No satellite signal is identified by RF energy.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
import platform
import webbrowser
from pathlib import Path
import re
import secrets
import shutil
import signal
import subprocess
import threading
import time
from urllib.request import urlopen
from urllib.parse import urlsplit
import uuid
import wave

from . import __version__
from .capture_naming import recording_name, PROFILE_TARGETS, meteor_capture
from .capture_budget import (MAX_IQ_BYTES, MAX_CAPTURE_SECONDS,
                             plan_capture_budget, END_MARGIN_SECONDS)
from .sstv_series35 import extract_robot36_wav
from .compute_backends import compute_capabilities, resolve_compute_backend
from .bridge import (app_data_dir, lock_receiver, unlock_receiver, start_receiver_process,
                     stop_receiver_process, pairing_secret, allowed_origin,
                     local_host_allowed, request_is_remote)

UTC = timezone.utc
DATA = Path(os.getenv("TIHULU_SATELLITE_DATA", str(app_data_dir())))
TEXT_CENTER_LOCK = (Path.home()/".local/share/tihulu-text-center/.receiver-locks/rtl_fm_rds.lock"
                    if os.name != "nt" else DATA/".receiver-locks/rtl_fm_rds.lock")
SOURCE_URLS = {
    "iss": "https://celestrak.org/NORAD/elements/gp.php?CATNR=25544&FORMAT=TLE",
    "meteor3": "https://celestrak.org/NORAD/elements/gp.php?CATNR=57166&FORMAT=TLE",
    "meteor4": "https://celestrak.org/NORAD/elements/gp.php?CATNR=59051&FORMAT=TLE",
    "amateur": "https://celestrak.org/NORAD/elements/gp.php?GROUP=amateur&FORMAT=TLE",
    "iridium": "https://celestrak.org/NORAD/elements/gp.php?GROUP=iridium-NEXT&FORMAT=TLE",
}
AUTO_DOWNLINK_PROFILES = {
    "iss-sstv": (25544, "iss_sstv", "sstv_audio"),
    "iss-aprs": (25544, "iss_aprs_uhf", "aprs"),
    "iss-voice": (25544, "iss_uhf", "fm_audio"),
    "meteor-m2-3": (57166, "meteor", "iq"),
    "meteor-m2-4": (59051, "meteor", "iq"),
}

LOCATIONS = {
    "Cologne": (50.938, 6.960), "Berlin": (52.520, 13.405),
    "Hamburg": (53.551, 9.993), "Munich": (48.137, 11.576),
    "Izmir": (38.423, 27.143), "Istanbul": (41.009, 28.978),
    "Ankara": (39.933, 32.859), "Brussels": (50.850, 4.351),
    "Paris": (48.857, 2.352), "Rome": (41.902, 12.496),
    "Stockholm": (59.329, 18.069),
}
# Frequency presets are receive-only targets, not promises of an active downlink.
PROFILES = {
    "iss_voice": {"label": "ISS voice / SSTV vicinity", "range": "145.76M:145.85M:5k", "freq": 145800000, "family": "iss"},
    "iss_sstv": {"label": "ISS SSTV · event-only 437.550 MHz Robot36 (confirm ARISS)", "range": "437.50M:437.60M:5k", "freq": 437550000, "family": "iss"},
    "iss_aprs": {"label": "ISS AX.25/APRS vicinity", "range": "145.78M:145.87M:5k", "freq": 145825000, "family": "iss"},
    "iss_aprs_uhf": {"label": "ISS UHF AX.25/APRS 437.825 MHz (check ARISS)", "range": "437.78M:437.87M:5k", "freq": 437825000, "family": "iss"},
    "iss_uhf": {"label": "ISS repeater vicinity", "range": "437.76M:437.86M:5k", "freq": 437800000, "family": "iss"},
    "meteor": {"label": "Meteor-M LRPT primary (137.900 MHz)", "range": "137.0M:138.0M:12.5k", "freq": 137900000, "family": "meteor"},
    "meteor_backup": {"label": "Meteor-M LRPT alternate (137.100 MHz)", "range": "137.0M:138.0M:12.5k", "freq": 137100000, "family": "meteor"},
    "cubesat_vhf": {"label": "Amateur VHF survey", "range": "145.0M:146.0M:12.5k", "freq": None, "family": "cubesat"},
    "cubesat_uhf": {"label": "Amateur UHF survey", "range": "435.0M:438.0M:25k", "freq": None, "family": "cubesat"},
    "iridium": {"label": "Iridium L-band RF survey", "range": "1616M:1626.5M:50k", "freq": None, "family": "iridium"},
    "iridium_rf_iq": {"label": "Iridium L-band 1620 MHz raw IQ candidate only; no message decode", "range": "1616M:1626.5M:50k", "freq": 1620000000, "family": "iridium"},
}
MODES = ("survey", "iq", "iq_and_fm_wav", "aprs", "sstv_audio", "fm_audio")


def now():
    return datetime.now(UTC)


def stamp(dt=None):
    return (dt or now()).isoformat(timespec="seconds")


def safe_write(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.chmod(temp, 0o600)
    temp.replace(path)


def safe_read(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return fallback


def parse_tle(text, limit=200):
    """Return only valid three-line TLE records with matching NORAD numbers."""
    lines = [x.strip() for x in text.splitlines() if x.strip()]
    entries = []
    for i in range(1, len(lines)-1):
        a, b = lines[i:i+2]
        if not (re.match(r"^1 (\d{5})[A-Z ]", a) and re.match(r"^2 (\d{5})\s", b)):
            continue
        if a[2:7] != b[2:7] or len(a) < 65 or len(b) < 65:
            continue
        name = lines[i-1].removeprefix("0 ") if not lines[i-1].startswith(("1 ", "2 ")) else f"NORAD {a[2:7]}"
        entries.append({"id": int(a[2:7]), "name": name[:96], "l1": a, "l2": b})
        if len(entries) >= limit:
            break
    return entries


def family(source, item):
    if source == "iridium":
        return "iridium"
    if source in ("meteor3", "meteor4"):
        return "meteor"
    if source == "iss":
        return "iss"
    if source == "amateur":
        return "cubesat"
    return "unknown"


def selectable(source, item):
    if source == "amateur":
        # Opt-in, bounded subset of orbit candidates; RF activity is unverified.
        return item["id"] in {27607, 43017, 43678, 44909} or (
            len(item["name"]) < 48 and "CUBESAT" in item["name"].upper()
        )
    return source != "iridium" or "IRIDIUM" in item["name"].upper()


def profiles_for(fam):
    return [k for k, v in PROFILES.items() if v["family"] == fam]


def allowed_mode(profile, mode):
    return mode == "survey" or (mode == "iq" and PROFILES[profile]["freq"] is not None) or (
        mode == "iq_and_fm_wav" and profile in ("iss_voice","iss_sstv","iss_uhf")
        ) or (
        profile in ("iss_aprs", "iss_aprs_uhf") and mode == "aprs"
    ) or (profile in ("iss_voice", "iss_sstv") and mode == "sstv_audio") or (profile in ("iss_voice", "iss_uhf") and mode == "fm_audio")


def topocentric_elevation_deg(observed_position):
    """Skyfield's altaz() is (altitude, azimuth, distance), not (azimuth, altitude, distance)."""
    altitude, _, _ = observed_position.altaz()
    value = float(altitude.degrees)
    if not math.isfinite(value) or not -90.0 <= value <= 90.0:
        raise ValueError("Invalid topocentric elevation from orbital calculation")
    return value


def parse_power(raw, profile):
    """Keep measured bins; never identify an Iridium or other satellite by power."""
    import csv
    import io
    values = []
    for row in csv.reader(io.StringIO(raw)):
        if len(row) < 7:
            continue
        try:
            start, step = float(row[2]), float(row[4])
            for i, value in enumerate(row[6:]):
                val = float(value)
                if math.isfinite(val) and 1000 <= step <= 500000:
                    values.append([int(start+(i+0.5)*step), round(val, 2)])
        except ValueError:
            continue
        if len(values) > 12000:
            break
    return {"profile": profile, "measured_bins": values[:12000],
            "measurement": "relative_radio_power_only",
            "warning": "Energy peaks are NOT proven satellite detections; Iridium bursts may be missed by a sweep."}


def _linux_receiver_processes(proc=Path("/proc")):
    """Passive, no root, no kill. Check executable NAME only to avoid false hits
    from arguments (such as this module's own test script)."""
    names = {"rtl_sdr", "rtl_fm", "rtl_power", "rtl_test", "readsb", "dump1090",
             "rtl_433", "gqrx", "welle-io", "welle.io"}
    hits = []
    try:
        for entry in proc.iterdir():
            if not entry.name.isdecimal() or int(entry.name) == os.getpid():
                continue
            try:
                cmd = (entry/"cmdline").read_bytes().split(b"\\0", 1)[0]
                name = os.fsdecode(cmd).rsplit("/", 1)[-1].lower()
                if name in names:
                    hits.append({"process": name, "pid": int(entry.name)})
            except (OSError, ValueError):
                pass
    except OSError:
        pass
    return sorted(hits, key=lambda entry: entry['pid'])[:20]


def detect_busy():
    """Best effort passive busy check; OS radio lock + rtl_test remain authoritative."""
    if platform.system() != "Linux":
        return []
    try:
        from textcenter.conflicts import find_receiver_conflicts
        return find_receiver_conflicts()
    except ImportError:
        # Debian standalone .deb deliberately does NOT depend on Text Center.
        # Missing optional app modules must never mean the SDR is 'busy'.
        return _linux_receiver_processes()


def _linux_usb_receiver_inventory(sysfs=Path("/sys/bus/usb/devices")):
    """Passive user-readable hardware IDs. Never opens USB or detaches drivers.

    RTL2832U and Hauppauge DVB-T/T2 devices are kept distinct; a TV tuner
    is NOT represented as a generic RTL-SDR raw I/Q receiver.
    """
    result = []
    try:
        devices = list(sysfs.iterdir())
    except OSError:
        return result
    for device in devices:
        try:
            vid = (device/"idVendor").read_text(encoding="ascii").strip().lower()
            pid = (device/"idProduct").read_text(encoding="ascii").strip().lower()
        except (OSError, UnicodeError):
            continue
        rtl = (vid, pid) in (("0bda","2838"), ("0bda","2832"))
        television = vid == "2040"
        if not rtl and not television:
            continue
        def read_label(field):
            try:
                return (device/field).read_text(encoding="utf-8",errors="replace").strip()[:70]
            except OSError:
                return ""
        result.append({
            "vendor_id":vid, "product_id":pid,
            "name":read_label("product") or ("RTL2832U compatible SDR" if rtl else "Hauppauge TV tuner"),
            "manufacturer":read_label("manufacturer"),
            "sysfs_device":device.name[:30],
            "receiver_type":"rtl_sdr" if rtl else "dvb_tv_not_generic_iq",
            "usb_present":True,
        })
    return result[:12]


def _linux_rtl_usb_count(sysfs=Path("/sys/bus/usb/devices")):
    """Read-only Linux sysfs enumeration; no USB reset or driver detach."""
    count = 0
    try:
        for dev in sysfs.iterdir():
            try:
                vendor = (dev/"idVendor").read_text(encoding="ascii").strip().lower()
                product = (dev/"idProduct").read_text(encoding="ascii").strip().lower()
                if (vendor, product) == ("0bda", "2838"):
                    count += 1
            except (OSError, UnicodeError):
                continue
    except OSError:
        pass
    return count


def tuner_present():
    if platform.system() != "Linux":
        return False
    try:
        from textcenter.receivers import receiver_inventory
        inventory = receiver_inventory()
        if inventory.get("platform") == "Linux" and inventory.get("rtl_usb_count") is not None:
            return inventory["rtl_usb_count"] == 1
    except ImportError:
        pass
    # No dependency on main Text Center: native Debian receiver works alone.
    return _linux_rtl_usb_count() == 1


def stop_process(process):
    stop_receiver_process(process)


class Station:
    def __init__(self, directory=DATA):
        self.directory = Path(directory)
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.pairing_token = pairing_secret(self.directory)
        self.archive = self.directory/"captures"
        self.archive.mkdir(exist_ok=True, mode=0o700)
        self.lock = threading.RLock()
        self.device_lock = None
        self.process = None
        self.owned_processes = set()  # Only processes launched by Satellite Center.
        self.active_worker = None
        self.manual_owner = None
        self.last_manual_heartbeat = 0.0
        self.closed = threading.Event()
        self.stopping = threading.Event()
        self.session = {"state": "idle", "active": False, "message": "No RF acquisition attempted"}
        self.jobs = safe_read(self.directory/"schedule.json", [])
        self.jobs = self.jobs if isinstance(self.jobs, list) else []
        for j in self.jobs:
            if j.get("state") == "running":
                j.update(state="interrupted", result="Server restarted during capture; check archive")
        self.launching = False
        saved_hardware = safe_read(self.directory/"hardware.json", {})
        if not isinstance(saved_hardware, dict):
            saved_hardware = {}
        # Preserve existing opt-in schedules on upgraded installations.
        # A user's explicit Disconnect is persisted and overrides auto jobs
        # until another positive physical USB test enables capture.
        self.receiver_enabled = saved_hardware.get("receiver_enabled", True) is True
        self.receiver_generation = 0
        self.receiver_test = None
        self.receiver_last_sample = None
        self.receiver_last_release = None
        self.predicted = {}
        self.wake = threading.Event()
        self.scheduler_thread = None
        if self.receiver_enabled and any(j.get("state") == "pending" for j in self.jobs):
            self.start_scheduler()

    def status(self):
        with self.lock:
            cached = {}
            for key in SOURCE_URLS:
                path = self.directory/(key+".tle")
                cached[key] = {"present": path.is_file(),
                               "age_hours": round((time.time()-path.stat().st_mtime)/3600, 1) if path.is_file() else None}
            return {"version": __version__, "platform": platform.system(),
                    "tuner_present": tuner_present() if platform.system() == "Linux" else None,
                    "receiver_detection": ("passive_linux_usb" if platform.system() == "Linux"
                                           else "not_passively_verified_on_this_os"),
                    "busy": detect_busy(), "tools": {n: bool(shutil.which(n)) for n in
                    ("rtl_test", "rtl_power", "rtl_sdr", "rtl_fm", "multimon-ng", "satdump", "qsstv")},
                    "compute": compute_capabilities(),
                    "hardware": {
                        "receiver_enabled": self.receiver_enabled,
                        "usb_rtl_count": _linux_rtl_usb_count() if platform.system() == "Linux" else None,
                        "usb_devices": _linux_usb_receiver_inventory() if platform.system() == "Linux" else [],
                        "lease_held": self.device_lock is not None,
                        "opening": self.launching,
                        "owned_processes_running": sum(p.poll() is None for p in self.owned_processes),
                        "app_released": (self.device_lock is None and
                                         not self.launching and
                                         not self.session.get("active") and
                                         all(p.poll() is not None for p in self.owned_processes)),
                        "last_usb_test": self.receiver_test,
                        "last_real_sample": self.receiver_last_sample,
                        "last_disconnect": self.receiver_last_release,
                        "pending_schedules": sum(j.get("state") == "pending" for j in self.jobs),
                        "usb_power_control": False,
                    },
                    "orbit_cache": cached, "location_presets": LOCATIONS,
                    "profiles": PROFILES, "session": dict(self.session),
                    "jobs": [dict(j) for j in self.jobs[-100:]],
                    "archive": self.records()}

    def sample_test(self, frequency_hz=137900000):
        """Explicit real-IQ probe. Does NOT create a recording or decode a satellite.

        Independent of a normal capture, temporary rtl_sdr process and receiver
        lock are released in every outcome. No USB power/reset is attempted.
        """
        hz=int(frequency_hz)
        if hz not in {137900000,137100000,145800000,145825000,
                      437550000,437800000,437825000,1620000000}:
            raise ValueError("Select a published receive-only diagnostic frequency")
        tool=shutil.which("rtl_sdr")
        if not tool:
            raise RuntimeError("rtl_sdr not installed. Install rtl-sdr tools.")
        with self.lock:
            if self.closed.is_set() or self.session.get("active") or self.launching:
                raise RuntimeError("Receiver in use; stop current activity before sampling")
            self.launching=True
            proc=None
            try:
                self.stopping.clear()
                self._acquire()
                # Exactly 524288 complex samples = 1 MiB unsigned CU8; bounded.
                proc=self._launch_receiver([
                    tool,"-d","0","-f",str(hz),"-s","1024000",
                    "-n","524288","-"
                ],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
                   stderr=subprocess.PIPE)
                self.process=proc
            except BaseException:
                self.launching=False
                self._release()
                raise
        try:
            try:
                raw,errors=proc.communicate(timeout=8)
            except subprocess.TimeoutExpired as exc:
                stop_process(proc)
                raise RuntimeError("Physical SDR sample test timed out") from exc
            if proc.returncode != 0 or len(raw) < 32768 or len(raw)%2:
                message=errors.decode("utf-8","replace")[-320:]
                raise RuntimeError(
                    "Physical SDR did not produce usable complex IQ samples. "+
                    re.sub(r"[\x00-\x1f\x7f]+"," ",message))
            # Efficient bounded subsampling; voltage-relative digital metrics.
            counts=raw[::64]
            minimum=min(counts);maximum=max(counts)
            mean=sum(counts)/len(counts)
            rms=(sum((v-127.5)**2 for v in counts)/len(counts))**0.5
            clipped=sum(v<3 or v>252 for v in counts)
            with self.lock:
                self.receiver_last_sample={
                    "verified_at":stamp(),"frequency_hz":hz,
                    "sample_bytes":len(raw)}
            return {
                "state":"real_iq_samples_received",
                "sample_bytes":len(raw),
                "complex_samples":len(raw)//2,
                "frequency_hz":hz, "sample_rate_sps":1024000,
                "digital_min":minimum,"digital_max":maximum,
                "digital_mean":round(mean,2),
                "digital_rms_from_midpoint":round(rms,2),
                "sampled_clip_fraction":round(clipped/len(counts),5),
                "signal_decoded":False,"satellite_identified":False,
                "evidence":"physical rtl_sdr process emitted CU8 complex I/Q bytes",
                "note":"Actual USB IQ acquisition verified. No calibrated dBm, station identity, usable antenna or satellite signal implied."
            }
        finally:
            stop_process(proc)
            with self.lock:
                if self.process is proc:self.process=None
                self.owned_processes.discard(proc)
                self.launching=False
                self._release()

    def connect_receiver(self):
        """Prove physical RTL-SDR open, release it, then arm future RF jobs.

        Enabling is forbidden without a positive rtl_test result. The device is
        not held open when idle; 'connected' means verified availability.
        """
        with self.lock:
            if self.closed.is_set():
                raise RuntimeError("Satellite Center is closing")
            generation = self.receiver_generation
        result = self.usb_test()
        if result.get("state") != "usb_receiver_opened":
            raise RuntimeError("No successful physical USB-open evidence")
        sampling = self.sample_test()
        if sampling.get("state") != "real_iq_samples_received":
            raise RuntimeError("Physical USB opened, but no real IQ samples were verified")
        with self.lock:
            if self.closed.is_set() or self.receiver_generation != generation:
                raise RuntimeError("Receiver was disconnected while verifying; RF stays disabled")
            self.receiver_enabled = True
            self.receiver_test = {"state": "usb_and_iq_verified_then_released",
                                  "verified_at": stamp(),
                                  "sample_bytes": sampling["sample_bytes"],
                                  "evidence": sampling["evidence"]}
            safe_write(self.directory/"hardware.json", {"receiver_enabled": True})
            if any(j.get("state") == "pending" for j in self.jobs):
                self.start_scheduler()
                self.wake.set()
        return {"receiver_enabled": True, "usb_test": result,
                "sample_test": sampling,
                "connection": "usb_and_iq_verified_then_released",
                "note": "Physical rtl_test and rtl_sdr sample acquisition succeeded. Both processes/leases released; no SDR remains open while idle."}

    def disconnect_receiver(self):
        """Explicit persistent RF disarm; only Satellite Center's own children.

        Pending jobs are *paused*, never silently executed after disconnect
        (including after application restart). No USB power/reset occurs.
        """
        with self.lock:
            self.receiver_enabled = False
            self.receiver_generation += 1
            safe_write(self.directory/"hardware.json", {"receiver_enabled": False})
            self.wake.set()
        requested = self.request_stop()
        # Workers still unwinding may briefly retain the cooperative lock.
        # Never report released until *all* owned processes and lease exit.
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            with self.lock:
                released = (not self.session.get("active") and not self.launching and
                            self.device_lock is None and
                            all(p.poll() is not None for p in self.owned_processes))
                if released:
                    self.receiver_last_release = stamp()
                    break
            time.sleep(0.05)
        with self.lock:
            if not released:
                # Preserve the disarm, but truthfully report incomplete release.
                self.receiver_last_release = None
            return {
                "receiver_enabled": False,
                "app_released": released,
                "owned_processes_stop_requested": requested["owned_processes_stop_requested"],
                "pending_jobs_paused": sum(j.get("state") == "pending" for j in self.jobs),
                "usb_still_physically_present": tuner_present() if platform.system()=="Linux" else None,
                "last_disconnect": self.receiver_last_release,
                "note": ("Satellite Center released its SDR processes and lock. "
                         "USB remains plugged/powered; unrelated SDR apps are untouched."
                         if released else
                         "RF disarmed, but an owned process/lease is still stopping. Check status again.")
            }

    def usb_test(self):
        """Opt-in bounded USB *open* test; does not tune to a station or transmit.

        This temporarily leases the receiver and never stops another program.
        rtl_test -t on R820T may exit with a nonzero E4000 tuner test result,
        so report USB-open evidence separately from success of that feature.
        """
        tool = shutil.which("rtl_test")
        if not tool:
            raise RuntimeError("rtl_test is missing. Install rtl-sdr tools first; the USB is not verified")
        with self.lock:
            if self.closed.is_set() or self.session.get("active") or self.launching:
                raise RuntimeError("An SDR job is active or queued; USB test blocked")
            self.launching = True
            proc = None
            try:
                self.stopping.clear()
                self._acquire()
                proc = self._launch_receiver([tool, "-t"], stdin=subprocess.DEVNULL,
                                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                self.process = proc
            except BaseException:
                self.launching = False
                self._release()
                raise
        try:
            try:
                out, err = proc.communicate(timeout=7)
            except subprocess.TimeoutExpired:
                stop_process(proc)
                out, err = proc.communicate(timeout=2)
            messages = (out + b"\n" + err).decode("utf-8", "replace")[-5000:]
            low = messages.lower()
            opened = ("using device" in low or "found rafael" in low or
                      "found e4000 tuner" in low) and not any(
                       warning in low for warning in
                       ("libusb_open error", "usb_claim_interface error", "failed to open",
                        "permission denied", "device or resource busy"))
            if not opened:
                raise RuntimeError("Receiver not opened. Check USB, drivers, permissions and other SDR applications. " +
                                   "rtl_test: " + re.sub(r"[\x00-\x1f\x7f]+", " ", messages[-240:]))
            return {"state": "usb_receiver_opened", "evidence": "rtl_test device access",
                    "platform": platform.system(),
                    "signal_decoded": False, "satellite_identified": False,
                    "note": "USB receiver successfully opened then released. Antenna quality and RF reception remain unverified.",
                    "rtl_test_output": re.sub(r"[\x00-\x1f\x7f]+", " ", messages[-500:])}
        finally:
            stop_process(proc)
            with self.lock:
                if self.process is proc:
                    self.process = None
                self.owned_processes.discard(proc)
                self.launching = False
                self._release()

    def refresh(self):
        """Only called by explicit operator action. Whitelisted HTTPS sources."""
        result = {}
        for key, url in SOURCE_URLS.items():
            try:
                with urlopen(url, timeout=9) as response:
                    if urlsplit(response.url).hostname not in {"celestrak.org", "www.celestrak.org"}:
                        raise ValueError("Unexpected orbit data redirect")
                    payload = response.read(350001)
                if len(payload) > 350000:
                    raise ValueError("TLE response too large")
                content = payload.decode("ascii", "strict")
                count = len(parse_tle(content, 200))
                if count < 1:
                    raise ValueError("No valid TLE entries")
                dest = self.directory/(key+".tle")
                dest.write_text(content, encoding="ascii")
                os.chmod(dest, 0o600)
                result[key] = {"cached": count, "fetched_at": stamp(), "source": url}
            except (OSError, ValueError, UnicodeError) as exc:
                result[key] = {"error": str(exc)[:150], "cached": False}
        return result

    def plan_passes(self, **kwargs):
        """Desktop-only explicit planning with truthful first-run TLE readiness.

        Fresh local TLEs always win (including user-imported offline TLEs).
        Only when *none* are usable does the operator's Calculate action
        attempt an on-demand public refresh. Never silently invent passes.
        """
        now_time=time.time()
        fresh=[]
        for source in SOURCE_URLS:
            target=self.directory/(source+".tle")
            try:
                if target.is_file() and now_time-target.stat().st_mtime <= 7*86400:
                    fresh.append(source)
            except OSError:
                continue
        refresh_result = None
        if not fresh:
            refresh_result=self.refresh()
        report=self.passes(**kwargs)
        if refresh_result is not None:
            report["automatic_tle_refresh"]=refresh_result
            if not report.get("predictions"):
                report["warnings"].append(
                    "No passes predicted after on-demand TLE refresh. "
                    "Check HTTPS access, source errors, location/time filters, "
                    "or import a local .tle file.")
        if not report.get("predictions") and not report.get("warnings"):
            report["warnings"]=["No above-horizon passes in the selected period. "
                                "Try a longer lookahead or lower elevation."]
        return report

    def passes(self, *, city="Cologne", lat=None, lon=None, hours=24, elevation=15):
        try:
            from skyfield.api import EarthSatellite, load, wgs84
        except ImportError as exc:
            raise ValueError("Install optional orbit dependency: pip install skyfield") from exc
        if type(hours) is not int or not 1 <= hours <= 72:
            raise ValueError("hours must be 1–72")
        if not isinstance(elevation, (float, int)) or not 5 <= elevation <= 75:
            raise ValueError("minimum elevation must be 5–75 degrees")
        if lat is None or lon is None:
            if city not in LOCATIONS:
                raise ValueError("Unknown location preset")
            lat, lon = LOCATIONS[city]
        else:
            lat, lon = float(lat), float(lon)
            if not -90 <= lat <= 90 or not -180 <= lon <= 180:
                raise ValueError("Invalid latitude or longitude")
        clock = load.timescale()
        observer = wgs84.latlon(lat, lon)
        t_start = now()
        a = clock.from_datetime(t_start)
        b = clock.from_datetime(t_start+timedelta(hours=hours))
        events = []
        warnings = []
        for source in SOURCE_URLS:
            file = self.directory/(source+".tle")
            if not file.is_file():
                warnings.append(f"{source}: orbit data not downloaded")
                continue
            age = (time.time()-file.stat().st_mtime)/86400
            if age > 7:
                warnings.append(f"{source}: TLE cache too old ({age:.1f} days); refresh required")
                continue
            if age > 2:
                warnings.append(f"{source}: TLE cache {age:.1f} days old; predictions less reliable")
            entries = parse_tle(file.read_text(encoding="ascii", errors="ignore"))
            if source == "amateur":
                entries = [it for it in entries if selectable(source, it)][:15]
            for item in entries:
                if not selectable(source, item):
                    continue
                try:
                    sat = EarthSatellite(item["l1"], item["l2"], item["name"], clock)
                    times, codes = sat.find_events(observer, a, b, altitude_degrees=float(elevation))
                    rising = peak = None
                    for event_time, code in zip(times, codes):
                        when = event_time.utc_datetime().astimezone(UTC)
                        if code == 0:
                            rising, peak = when, None
                        elif code == 1:
                            peak = when
                        elif code == 2 and rising is not None:
                            end = when
                            if peak is None:
                                rising = None
                                continue
                            peak_elevation = topocentric_elevation_deg(
                                (sat-observer).at(clock.from_datetime(peak)))
                            if peak_elevation >= elevation:
                                key = f"{item['id']}:{int(rising.timestamp())}"
                                event = {"id": key, "norad": item["id"], "name": item["name"],
                                         "family": family(source, item), "aos": stamp(rising),
                                         "peak": stamp(peak), "los": stamp(end),
                                         "max_elevation_deg": round(peak_elevation, 1),
                                         "profiles": profiles_for(family(source, item)),
                                         "status": "PREDICTED_GEOMETRY_NOT_SIGNAL",
                                         "tle_source": SOURCE_URLS[source], "tle_age_days": round(age, 2)}
                                events.append(event)
                            rising = None
                except (ValueError, OverflowError, RuntimeError):
                    continue
        events.sort(key=lambda x: x["aos"])
        events = events[:400]
        with self.lock:
            self.predicted = {x["id"]: x for x in events}
        return {"observer": {"label": city if lat is None else city, "lat": lat, "lon": lon},
                "predictions": events, "warnings": warnings,
                "as_of": stamp(), "note": "Potential passes only. TLE geometry cannot establish any active transmission."}

    def sky(self, city="Cologne", lat=None, lon=None):
        """Observed sky positions calculated from cached orbits, not RF identification."""
        try:
            from skyfield.api import EarthSatellite, load, wgs84
        except ImportError as exc:
            raise ValueError("Install skyfield for satellite sky positions") from exc
        if lat is None or lon is None:
            if city not in LOCATIONS:
                raise ValueError("Unknown location preset")
            lat, lon = LOCATIONS[city]
        else:
            lat, lon = float(lat), float(lon)
            if not -90 <= lat <= 90 or not -180 <= lon <= 180:
                raise ValueError("Invalid latitude or longitude")
        clock = load.timescale()
        t = clock.from_datetime(now())
        observer = wgs84.latlon(lat, lon)
        visible = []
        warnings = []
        for source in SOURCE_URLS:
            file = self.directory/(source+".tle")
            if not file.is_file() or time.time()-file.stat().st_mtime > 7*86400:
                warnings.append(source+": no usable fresh cache")
                continue
            entries = parse_tle(file.read_text(encoding="ascii", errors="ignore"))
            if source == "amateur":
                entries = [it for it in entries if selectable(source, it)][:15]
            for item in entries:
                if not selectable(source, item): continue
                try:
                    sat = EarthSatellite(item["l1"], item["l2"], item["name"], clock)
                    az, el, distance = None, None, None
                    el, az, distance = (sat-observer).at(t).altaz()
                    if el.degrees >= 5:
                        visible.append({"name":item["name"], "norad":item["id"],
                                        "family":family(source,item),
                                        "azimuth_deg":round(az.degrees,1),
                                        "elevation_deg":round(el.degrees,1),
                                        "range_km":round(distance.km),
                                        "status":"ORBITAL_POSITION_ONLY"})
                except (ValueError, OverflowError, RuntimeError):
                    continue
        visible.sort(key=lambda x: -x["elevation_deg"])
        return {"observed_at":stamp(), "observer":{"city":city,"lat":lat,"lon":lon},
                "above_5_degrees":visible[:160], "warnings":warnings,
                "note":"Geometric position only; RF presence, antenna visibility and transmissions are unverified"}

    def import_tle(self, path, source="amateur"):
        """Explicit local, bounded TLE import, shared with native predictions.

        User imports for a named catalog source replace only that source's
        cached orbit text. No USB capture or Internet access.
        """
        if source not in SOURCE_URLS:
            raise ValueError("Choose a supported orbit family/source")
        file=Path(path).expanduser()
        if not file.is_file() or file.stat().st_size>1048576:
            raise ValueError("TLE file missing or larger than 1 MiB")
        data=file.read_text(encoding="utf-8",errors="replace")
        entries=parse_tle(data,limit=200)
        if not entries:
            raise ValueError("No matching two-line orbital element pairs in file")
        expected={"iss":25544,"meteor3":57166,"meteor4":59051}
        if source in expected and not any(row["id"]==expected[source] for row in entries):
            raise ValueError("Selected satellite family does not match TLE NORAD ID")
        target=self.directory/(source+".tle")
        temporary=target.with_suffix(".tle.import")
        try:
            with temporary.open("x",encoding="utf-8") as output:
                output.write(data)
            os.chmod(temporary,0o600)
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
        return {
            "source":source,"tle_count":len(entries),
            "norad_ids":[row["id"] for row in entries[:20]],
            "cache":str(target),"provenance":"user_imported_orbital_elements",
            "radio_signal_verified":False,
            "note":"Import only updates orbital elements. Recalculate passes; an orbit is not a received signal."
        }

    def save_jobs(self):
        safe_write(self.directory/"schedule.json", self.jobs[-150:])

    def schedule(self, pass_id, profile, mode, run_at=None, seconds=None, *, automatic=False, sample_rate=1024000):
        """Explicit native RF pass schedule (Firefox-compatible, no WebUSB/FSA).

        Enforces server-predicted public TLE event/profile and local disk
        budget. The client may not supply arbitrary USB commands or pass
        geometry. Iridium IQ is RF only, with no private message decoder.
        """
        if type(seconds) is not int and seconds is not None:
            raise ValueError("Capture seconds must be a whole number")
        if type(sample_rate) is not int or sample_rate not in (1024000,2048000):
            raise ValueError("IQ sample rate must be 1.024 or 2.048 MS/s")
        with self.lock:
            if not self.receiver_enabled:
                raise RuntimeError("Receiver disabled in Hardware. Connect & verify USB before scheduling RF.")
            event = self.predicted.get(pass_id)
            if not event:
                raise ValueError("Pass not in native prediction results; refresh local TLE and recalculate")
            if profile not in event["profiles"] or mode not in MODES or not allowed_mode(profile, mode):
                raise ValueError("Unsupported pass/profile/mode combination")
            if mode not in ("iq", "survey"):
                # Manual users may explicitly choose the catalogued pass
                # receiver profile and the matching approved audio/packet
                # mode. This is still receive-only, not arbitrary USB code.
                if not allowed_mode(profile, mode):
                    raise ValueError("Unsupported named audio/packet receiver mode")
            aos = datetime.fromisoformat(event["aos"]).astimezone(UTC)
            los = datetime.fromisoformat(event["los"]).astimezone(UTC)
            if aos < now()+timedelta(seconds=12) or aos > now()+timedelta(days=3):
                raise ValueError("Schedule passes beginning 12 seconds–3 days from now")
            if (los-aos).total_seconds() > 1500:
                raise ValueError("Predicted pass duration out of range")
            if run_at is None:
                chosen = aos
            else:
                if not isinstance(run_at, str) or len(run_at)>70:
                    raise ValueError("UTC ISO start required")
                try:
                    chosen = datetime.fromisoformat(run_at)
                except ValueError as exc:
                    raise ValueError("Invalid native scheduled start") from exc
                if chosen.tzinfo is None:
                    raise ValueError("Scheduled start must include UTC offset")
                chosen = chosen.astimezone(UTC)
            if not automatic and chosen<aos and chosen>=aos-timedelta(seconds=120):
                # Browser pass planners display minute resolution. Align an
                # early start within two minutes to the server's exact AOS.
                chosen=aos
            duration = 60 if seconds is None else seconds
            if type(duration) is not int or not 8 <= duration <= MAX_CAPTURE_SECONDS:
                raise ValueError("Native recording must be 8–900 whole seconds")
            if mode == "survey" and duration > 180:
                raise ValueError("Spectrum-only survey is limited to 180 s; select IQ disk recording for longer windows")
            earliest = aos-timedelta(seconds=10) if automatic else aos
            if chosen < max(earliest, now()+timedelta(seconds=8)):
                raise ValueError("Native start must be in the future and inside predicted pass")
            if chosen+timedelta(seconds=duration+END_MARGIN_SECONDS)>los:
                raise ValueError("Insufficient predicted LOS time for the full requested native recording")
            free = shutil.disk_usage(self.archive).free
            reserve = sum(int(other.get("estimated_bytes") or 0) for other in self.jobs
                          if other.get("state") in ("pending","running"))
            estimate = ((2*sample_rate+64000)*duration if mode == "iq_and_fm_wav"
                        else 2*sample_rate*duration if mode == "iq"
                        else 96_000*duration if mode in ("sstv_audio", "fm_audio")
                        else 1_000_000)
            if estimate>MAX_IQ_BYTES or free-reserve<estimate+200_000_000:
                raise ValueError("Insufficient local disk space for raw IQ and safety reserve")
            if sum(j.get("state")=="pending" for j in self.jobs)>=24:
                raise ValueError("At most 24 pending captures")
            for other in self.jobs:
                if other.get("state") not in ("pending","running"):
                    continue
                a=datetime.fromisoformat(other.get("run_at") or other["aos"]).astimezone(UTC)
                b=a+timedelta(seconds=int(other.get("capture_seconds") or 900))
                if chosen<b+timedelta(seconds=20) and chosen+timedelta(seconds=duration)>a-timedelta(seconds=20):
                    raise ValueError("Single RTL-SDR already reserved for overlapping capture")
            job = {"id": uuid.uuid4().hex[:12], "pass_id": pass_id,
                   "satellite": event["name"], "family": event["family"],
                   "profile": profile, "mode": mode,
                   "aos": event["aos"], "los": event["los"],
                   "run_at": stamp(chosen), "capture_seconds": duration,
                   "sample_rate": sample_rate,
                   "estimated_bytes": estimate,
                   "data_kind": "raw RF energy" if event["family"]=="iridium" else "unclassified IQ",
                   "coverage": "full-pass-attempt" if chosen+timedelta(seconds=duration)>=los-timedelta(seconds=END_MARGIN_SECONDS+5) else "partial-pass",
                   "state": "pending", "created_at": stamp(), "result": None}
            self.jobs.append(job)
            self.save_jobs()
            self.start_scheduler()
            self.wake.set()
            return dict(job)

    def auto_schedule(self, mission_ids, *, city="Cologne", lat=None, lon=None,
                      hours=24, elevation=20, max_jobs=6, coverage_goal="full",
                      duration_seconds=None, compute_mode="auto", compute_targets=None,
                      event_window_only=False, iss_record_format="wav"):
        """Explicit one-click receive-only mission planning with a single RTL-SDR.

        TLE passes are geometry, never proof of active transmitters. Mutating
        schedules is opt-in and uses the same persisted scheduler as manual jobs.
        """
        candidates = AUTO_DOWNLINK_PROFILES
        if iss_record_format not in ("wav","cu8","both"):
            raise ValueError("ISS recording choice must be wav, cu8 or both")
        if not self.receiver_enabled:
            raise RuntimeError("Receiver disabled in Hardware. Connect & verify USB first.")
        if not isinstance(mission_ids, list) or not mission_ids or len(mission_ids) > len(candidates):
            raise ValueError("Select one to five supported public downlink targets")
        if any(not isinstance(mid, str) or mid not in candidates for mid in mission_ids):
            raise ValueError("Unknown, retired, Internet-only or unsupported satellite target")
        if type(hours) is not int or not 1 <= hours <= 72:
            raise ValueError("Lookahead must be 1–72 hours")
        if type(max_jobs) is not int or not 1 <= max_jobs <= 12:
            raise ValueError("Choose at most 12 jobs per request")
        if coverage_goal not in ("full", "sample"):
            raise ValueError("Coverage goal must be full or sample")
        if duration_seconds is not None:
            if type(duration_seconds) is not int or not 8 <= duration_seconds <= MAX_CAPTURE_SECONDS:
                raise ValueError("Native recording duration must be 8–900 seconds or auto")
            if coverage_goal == "sample" and duration_seconds > 60:
                raise ValueError("Quick RF sample must not exceed 60 seconds")
        # Validate hardware choices before arming any RF job.
        compute_plan = resolve_compute_backend(compute_mode, compute_targets)
        if type(event_window_only) is not bool:
            raise ValueError("Event window gating must be a boolean")
        chosen = dict.fromkeys(mission_ids)
        # Missing optional decoders must not block other user-approved media.
        requested_targets = list(chosen)
        missing_per_mission = {}
        for mid in chosen:
            _norad, _profile, required_mode = candidates[mid]
            required = (["rtl_sdr"] if required_mode == "iq" or
                        (mid == "iss-sstv" and iss_record_format in ("cu8","both")) else
                        ["rtl_fm", "multimon-ng"] if required_mode == "aprs" else
                        ["rtl_fm"])
            absent = [tool for tool in required if not shutil.which(tool)]
            if absent:
                missing_per_mission[mid] = absent
        chosen = dict.fromkeys(mid for mid in chosen if mid not in missing_per_mission)
        if not chosen:
            raise RuntimeError("No selected mode has installed receiver/decoder tools: " +
                               "; ".join(k+": "+", ".join(v) for k,v in missing_per_mission.items()))
        # The single click authorizes bounded on-demand orbit refresh, never
        # auto-starts a receiver or changes unrelated services.
        sources = {"iss" if mid.startswith("iss") else
                   "meteor3" if mid == "meteor-m2-3" else "meteor4" for mid in chosen}
        missing_tle = [source for source in sources if not
                       (self.directory/(source+".tle")).is_file() or
                       time.time()-(self.directory/(source+".tle")).stat().st_mtime > 7*86400]
        refresh_report = self.refresh() if missing_tle else {}
        prediction = self.passes(city=city, lat=lat, lon=lon, hours=hours, elevation=elevation)
        existing = []
        mission_counts = {mid: 0 for mid in chosen}
        with self.lock:
            for job in self.jobs:
                if job.get("state") not in ("pending", "running"):
                    continue
                if job.get("mission_id") in mission_counts:
                    mission_counts[job["mission_id"]] += 1
                try:
                    existing.append((datetime.fromisoformat(job["aos"]),
                                     datetime.fromisoformat(job["los"])))
                except (KeyError, ValueError):
                    continue
        new_jobs = []
        skipped = [mid+": missing tools "+", ".join(absent)
                   for mid, absent in missing_per_mission.items()]
        now_utc = now()
        free_on_disk = shutil.disk_usage(self.archive).free
        reserved_bytes = sum(int(j.get("estimated_bytes") or 0) for j in self.jobs
                             if j.get("state") in ("pending", "running"))
        events = prediction["predictions"]
        for event in events:
            if len(new_jobs) >= max_jobs:
                break
            aos = datetime.fromisoformat(event["aos"])
            los = datetime.fromisoformat(event["los"])
            if aos <= now_utc+timedelta(seconds=60):
                continue
            if any(aos < b+timedelta(seconds=20) and los > a-timedelta(seconds=20)
                   for a, b in existing):
                skipped.append(event["name"]+": shared receiver time conflict")
                continue
            # Prefer a complete predicted window when multiple formats are selected.
            # Do not change a user-requested images-only category.
            eligible = [mid for mid in chosen if event["norad"] == candidates[mid][0]]
            if event_window_only and "iss-sstv" in eligible and not (
                    datetime(2026, 11, 9, tzinfo=UTC) <= aos < datetime(2026, 11, 17, tzinfo=UTC)):
                eligible.remove("iss-sstv")
                skipped.append(event["name"]+": ISS Series 35 SSTV is limited to the 9–16 November event date envelope; actual activation TBD")
            plans = {mid: plan_capture_budget(aos, los, mid,
                     free_bytes=max(0, free_on_disk-reserved_bytes),
                     goal=coverage_goal, requested_seconds=duration_seconds)
                     for mid in eligible}
            viable = [mid for mid in eligible if plans[mid]["feasible"]]
            if not viable:
                if eligible:
                    skipped.append(event["name"]+": too little predicted time or free disk for this format")
                continue
            mission = min(viable, key=lambda mid: (
                plans[mid]["coverage"] != "full-pass-attempt",
                mission_counts[mid], eligible.index(mid)))
            plan = plans[mission]
            _, profile, mode = candidates[mission]
            estimate_for_mode = plan["estimated_bytes"]
            if mission == "iss-sstv" and iss_record_format != "wav":
                mode = "iq" if iss_record_format == "cu8" else "iq_and_fm_wav"
                estimate_for_mode = ((2048000+64000) if iss_record_format == "both"
                                     else 2048000)*plan["capture_seconds"]
                if estimate_for_mode>MAX_IQ_BYTES or free_on_disk-reserved_bytes<estimate_for_mode+200_000_000:
                    skipped.append(event["name"]+": insufficient disk for selected CU8/WAV outputs")
                    continue
            try:
                job = self.schedule(event["id"], profile, mode,
                                    stamp(aos-timedelta(seconds=10)),
                                    plan["capture_seconds"], automatic=True)
            except (ValueError, RuntimeError) as error:
                skipped.append(event["name"]+": "+str(error)[:90])
                continue
            job.update(run_at=stamp(aos-timedelta(seconds=10)),
                       mission_id=mission, capture_seconds=plan["capture_seconds"],
                       requested_seconds=duration_seconds,
                       estimated_bytes=estimate_for_mode, coverage=plan["coverage"],
                       data_kind=plan["data_kind"], target_seconds=plan["target_seconds"],
                       shortfall_seconds=plan["shortfall_seconds"],
                       pass_visible_seconds=plan["pass_visible_seconds"],
                       coverage_goal=coverage_goal, capture_note=plan["note"],
                       compute_mode=compute_mode, compute_targets=compute_plan["requested_targets"],
                       event_window_only=event_window_only,
                       iss_record_format=iss_record_format)
            with self.lock:
                for stored in self.jobs:
                    if stored["id"] == job["id"]:
                        stored.update({key: job[key] for key in (
                            "mission_id", "run_at", "capture_seconds",
                            "requested_seconds", "estimated_bytes",
                            "coverage", "data_kind", "target_seconds",
                            "shortfall_seconds", "pass_visible_seconds",
                            "coverage_goal", "capture_note", "compute_mode", "compute_targets",
                            "event_window_only","iss_record_format")})
                self.save_jobs()
            new_jobs.append(dict(job))
            if plan["coverage"] != "full-pass-attempt":
                skipped.append(event["name"]+": "+str(plan["shortfall_seconds"])+
                               " seconds of predicted coverage missing; partial data only")
            mission_counts[mission] += 1
            reserved_bytes += estimate_for_mode
            existing.append((aos, los))
        return {"scheduled": new_jobs, "scheduled_count": len(new_jobs),
                "skipped": skipped[:20], "requested_targets": requested_targets,
                "disabled_targets": list(missing_per_mission),
                "receiver_claimed": False,
                "status": "armed_not_received" if new_jobs else "no_eligible_nonoverlapping_passes",
                "warnings": prediction["warnings"] +
                    [k+": "+str(v.get("error")) for k,v in refresh_report.items() if v.get("error")],
                "note": "Only geometry and an opt-in future recording schedule. The local companion must remain running, the single receiver must be free, and the spacecraft must actually transmit. No message or image is yet decoded."}

    def edit_auto_schedule(self, job_id, run_at, mission_id, duration_seconds=None):
        """Change an owned pending job inside its original geometric pass.

        Changes never move a task to another spacecraft, claim USB, affect
        manual schedules, or create an overlapping single-receiver conflict.
        """
        if not isinstance(job_id, str) or not re.fullmatch(r"[a-f0-9]{12}", job_id):
            raise ValueError("Invalid auto schedule identifier")
        if not isinstance(run_at, str) or len(run_at) > 60:
            raise ValueError("Provide a local-time converted ISO UTC scheduled start")
        try:
            selected = datetime.fromisoformat(run_at)
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid ISO scheduled start") from exc
        if selected.tzinfo is None:
            raise ValueError("Scheduled start requires explicit UTC offset")
        if duration_seconds is not None:
            if type(duration_seconds) is not int or not 8 <= duration_seconds <= MAX_CAPTURE_SECONDS:
                raise ValueError("Edited recording duration must be 8–900 seconds or auto")
        selected = selected.astimezone(UTC)
        if not isinstance(mission_id, str) or mission_id not in AUTO_DOWNLINK_PROFILES:
            raise ValueError("Unsupported or unverified satellite protocol")
        target_norad, target_profile, target_mode = AUTO_DOWNLINK_PROFILES[mission_id]
        tools = {"iq": ["rtl_sdr"], "aprs": ["rtl_fm", "multimon-ng"], "sstv_audio": ["rtl_fm"], "fm_audio": ["rtl_fm"]}[target_mode]
        missing = [tool for tool in tools if not shutil.which(tool)]
        if missing:
            raise RuntimeError("Required receiver/decoder not installed: " + ", ".join(missing))
        with self.lock:
            job = next((j for j in self.jobs if j.get("id") == job_id
                        and j.get("mission_id") and j.get("state") == "pending"), None)
            if not job:
                raise ValueError("Editable pending automatic task not found")
            pass_norad = int(str(job["pass_id"]).split(":")[0])
            if target_norad != pass_norad:
                raise ValueError("Protocol belongs to another spacecraft; recalculate its pass first")
            if not allowed_mode(target_profile, target_mode):
                raise ValueError("Receiver does not support requested protocol")
            aos = datetime.fromisoformat(job["aos"]).astimezone(UTC)
            los = datetime.fromisoformat(job["los"]).astimezone(UTC)
            if not (max(aos, now()+timedelta(seconds=20)) <= selected <= los-timedelta(seconds=12)):
                raise ValueError("Start must remain inside the future predicted pass with time left to record")
            for other in self.jobs:
                if other is job or other.get("state") not in ("pending", "running"):
                    continue
                try:
                    start = datetime.fromisoformat(other.get("run_at") or other["aos"]).astimezone(UTC)
                    end = datetime.fromisoformat(other["los"]).astimezone(UTC)
                except (KeyError, TypeError, ValueError):
                    continue
                if selected < end+timedelta(seconds=20) and los > start-timedelta(seconds=20):
                    raise ValueError("An existing job needs the same receiver during this pass")
            reserved_by_others = sum(int(other.get("estimated_bytes") or 0)
                                     for other in self.jobs if other is not job and
                                     other.get("state") in ("pending", "running"))
            plan = plan_capture_budget(aos, los, mission_id,
                         free_bytes=max(0, shutil.disk_usage(self.archive).free-
                                        reserved_by_others),
                         goal=job.get("coverage_goal", "full"),
                         start_at=selected,
                         requested_seconds=duration_seconds)
            if not plan["feasible"]:
                raise ValueError("Edited pass has too little time or free disk for this data type")
            job.update(run_at=stamp(selected), mission_id=mission_id,
                       profile=target_profile, mode=target_mode,
                       capture_seconds=plan["capture_seconds"],
                       requested_seconds=duration_seconds,
                       coverage=plan["coverage"], data_kind=plan["data_kind"],
                       target_seconds=plan["target_seconds"],
                       shortfall_seconds=plan["shortfall_seconds"],
                       estimated_bytes=plan["estimated_bytes"],
                       edited_at=stamp(), result=None)
            self.save_jobs()
            self.wake.set()
            return dict(job)

    def cancel_auto_missions(self):
        """Cancel only this app's explicitly auto-armed pending/running jobs."""
        with self.lock:
            active_auto = any(j.get("state") == "running" and j.get("mission_id")
                              for j in self.jobs)
            cancelled = 0
            for job in self.jobs:
                if job.get("mission_id") and job.get("state") == "pending":
                    job.update(state="cancelled", result="Cancelled via Auto Mission stop")
                    cancelled += 1
            if cancelled:
                self.save_jobs()
                self.wake.set()
        if active_auto:
            # Stops only Satellite Center's currently owned receiver process;
            # unrelated readsb, Gqrx, welle.io and manual sessions survive.
            self.request_stop()
        return {"auto_jobs_cancelled": cancelled, "owned_auto_capture_stop_requested": active_auto,
                "other_programs_stopped": False,
                "note": "No non-auto schedules or third-party SDR processes were changed."}

    def cancel(self, job_id):
        with self.lock:
            for j in self.jobs:
                if j["id"] == job_id and j["state"] == "pending":
                    j["state"] = "cancelled"
                    self.save_jobs()
                    self.wake.set()
                    return j
            raise ValueError("Pending schedule not found")

    def start_scheduler(self):
        if self.closed.is_set():
            return
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            return
        self.scheduler_thread = threading.Thread(target=self._schedule_loop, name="satellite-opt-in-scheduler", daemon=True)
        self.scheduler_thread.start()

    def _schedule_loop(self):
        while not self.closed.is_set():
            with self.lock:
                pending = [j for j in self.jobs if j["state"] == "pending"]
                if not pending:
                    return
                if not self.receiver_enabled:
                    # Explicit disconnect pauses even scheduled captures.
                    disarmed = True
                else:
                    disarmed = False
                pending.sort(key=lambda j: j.get("run_at") or j["aos"])
                nearest = pending[0]
                target = datetime.fromisoformat(nearest.get("run_at") or nearest["aos"])
                # Explicit edits and auto jobs use their exact start time.
                # Only old manual jobs without run_at start 10 s before AOS.
                lead = 0 if nearest.get("run_at") else 10
                delay = (target-now()).total_seconds()-lead
            if disarmed:
                self.wake.wait(60)
                self.wake.clear()
                continue
            if delay > 0:
                self.wake.wait(min(delay, 60))
                self.wake.clear()
                continue
            with self.lock:
                if self.closed.is_set():
                    return
                if not self.receiver_enabled or nearest["state"] != "pending":
                    continue
                remaining = int((datetime.fromisoformat(nearest["los"])-now()).total_seconds())-END_MARGIN_SECONDS
                duration = min(MAX_CAPTURE_SECONDS, remaining,
                               int(nearest.get("capture_seconds") or MAX_CAPTURE_SECONDS))
                if duration < 8:
                    nearest.update(state="missed", result="Insufficient time before predicted LOS")
                    self.save_jobs()
                    continue
                nearest["state"] = "running"
                self.save_jobs()
            try:
                kwargs = {}
                if int(nearest.get("sample_rate") or 1024000) != 1024000:
                    kwargs["sample_rate"] = int(nearest["sample_rate"])
                result = self.capture(nearest["profile"], nearest["mode"], duration,
                        scheduled=True, satellite=nearest.get("satellite"), **kwargs)
                # The receiver is already released by capture(). A full-pass
                # ISS SSTV WAV can contain several separate Robot36 images.
                # Decode only actual PCM samples; never infer imagery from
                # a predicted pass, filename, or RF level alone.
                wav_name = result.get("wav") or (
                    result.get("file") if str(result.get("file","")).endswith(".wav") else None)
                if nearest.get("mission_id") == "iss-sstv" and wav_name:
                    try:
                        result["sstv"] = extract_robot36_wav(
                            self.archive / wav_name,
                            compute_mode=nearest.get("compute_mode", "auto"),
                            compute_targets=nearest.get("compute_targets"))
                    except Exception as exc:
                        # Decoder failures, including a removed CUDA device,
                        # must not orphan a completed, genuine RF recording.
                        result["sstv"] = {
                            "status": "decoder_failed_original_wav_preserved",
                            "images": [], "reason": str(exc)[:240],
                        }
                with self.lock:
                    nearest.update(state="completed", result=result)
                    self.save_jobs()
            except (ValueError, RuntimeError, OSError) as exc:
                with self.lock:
                    nearest.update(state="blocked", result=str(exc)[:180])
                    self.save_jobs()

    def _acquire(self):
        # Mac/Windows cannot use the Linux sysfs inventory.
        # Platform-native rtl-sdr tools report actual device errors.
        if platform.system() == "Linux" and not tuner_present():
            raise RuntimeError("Exactly one Linux RTL2832U must be present")
        if detect_busy():
            raise RuntimeError("Another receiver appears active; scan not started")
        TEXT_CENTER_LOCK.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(TEXT_CENTER_LOCK, os.O_CREAT|os.O_RDWR|getattr(os, "O_CLOEXEC", 0)|getattr(os, "O_NOFOLLOW", 0), 0o600)
        try:
            lock_receiver(fd)
            if detect_busy():
                raise RuntimeError("Receiver occupied during preflight")
        except (RuntimeError, OSError):
            os.close(fd)
            raise RuntimeError("RTL-SDR receiver lease unavailable")
        self.device_lock = fd

    def _release(self):
        if self.device_lock is not None:
            try:
                unlock_receiver(self.device_lock)
            finally:
                os.close(self.device_lock)
                self.device_lock = None

    def _launch_receiver(self, command, **kwargs):
        """Atomically own a child before another thread can request shutdown."""
        with self.lock:
            if self.stopping.is_set() or self.closed.is_set():
                raise RuntimeError("Receiver session is stopping")
            process = start_receiver_process(command, **kwargs)
            self.owned_processes.add(process)
            return process

    def heartbeat(self, client_id):
        if not isinstance(client_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{12,80}", client_id):
            return False
        with self.lock:
            if client_id == self.manual_owner and self.session.get("active"):
                self.last_manual_heartbeat = time.monotonic()
                return True
        return False

    def leave(self, client_id):
        """Closing a tab stops only its manual capture, never scheduled passes."""
        if not isinstance(client_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{12,80}", client_id):
            raise ValueError("Invalid browser client identifier")
        with self.lock:
            stop = (self.manual_owner == client_id and self.session.get("active"))
        if stop:
            self.request_stop()
        return {"manual_capture_stop_requested": bool(stop),
                "scheduled_jobs_preserved": True}

    def _manual_watchdog(self, client_id):
        """Fallback for crashed tabs where pagehide/keepalive is dropped."""
        while not self.closed.wait(1):
            with self.lock:
                if self.manual_owner != client_id or not self.session.get("active"):
                    return
                stale = time.monotonic() - self.last_manual_heartbeat > 14
            if stale:
                self.request_stop()
                return

    def close(self):
        """Idempotent graceful shutdown, preserving unrelated SDR programs."""
        self.closed.set()
        self.wake.set()
        self.request_stop()
        with self.lock:
            worker = self.active_worker
            scheduler = self.scheduler_thread
        for thread in (worker, scheduler):
            if thread is not None and thread is not threading.current_thread() and thread.is_alive():
                thread.join(timeout=4)
        self.request_stop()

    def capture_dual(self,profile,seconds=60,scheduled=False,owner=None,satellite=None,
                     sample_rate=1024000):
        """Receive physical CU8 once, then demodulate its *same samples* to WAV.

        Native hardware backend, not WebUSB. The 32-kHz WAV is a derived
        FM-demodulated audio track; a saved WAV does not prove speech or SSTV.
        Never hide/lose a valid CU8 file on a decoder error.
        """
        if profile not in ("iss_voice","iss_sstv","iss_uhf"):
            raise ValueError("Dual CU8 + FM WAV requires a catalogued ISS audio profile")
        iq=self.capture(profile,"iq",seconds,scheduled=scheduled,owner=owner,
                        satellite=satellite,sample_rate=sample_rate)
        from .native_signal_tools import fm_to_wav
        try:
            report=fm_to_wav(
                self.archive/iq["file"],self.archive,sample_rate,
                int(PROFILES[profile]["freq"]),0)
            iq["wav"]=Path(report["output_wav"]).name
            iq["wav_format"]="32kHz 16-bit PCM mono (native CPU demodulation after RF capture)"
            iq["audio_authenticity"]="unverified_fm_demodulation_from_same_real_iq"
            iq["mode"]="iq_and_fm_wav"
        except (OSError,ValueError,RuntimeError) as exc:
            iq["wav_error"]=str(exc)[:240]
            iq["mode"]="iq_and_fm_wav_partial"
            iq["note"]="Real CU8 preserved; derived FM WAV failed"
        return iq

    def capture(self, profile, mode="survey", seconds=18, scheduled=False, owner=None,
                satellite=None, sample_rate=1024000):
        if profile not in PROFILES or mode not in MODES or not allowed_mode(profile, mode):
            raise ValueError("Unsupported capture preset")
        if type(seconds) is not int or not 8 <= seconds <= MAX_CAPTURE_SECONDS:
            raise ValueError("Capture duration must be 8–900 seconds")
        if not self.receiver_enabled:
            raise RuntimeError("Receiver disabled in Hardware. Connect & verify USB to enable RF.")
        if type(sample_rate) is not int or sample_rate not in (1024000,2048000):
            raise ValueError("IQ sample rate must be 1.024 or 2.048 MS/s")
        if mode in ("iq","iq_and_fm_wav"):
            bytes_per_second=2*sample_rate + (64000 if mode=="iq_and_fm_wav" else 0)
            if bytes_per_second*seconds>MAX_IQ_BYTES:
                raise ValueError(
                    "Selected IQ/WAV duration and rate exceed safe 2 GB total disk limit")
        if mode == "iq_and_fm_wav":
            return self.capture_dual(profile,seconds,scheduled,owner,satellite,sample_rate)
        # Explicit manual requests use the same 8–900 s/2 GB native disk
        # safety budget as scheduled captures. No browser IQ memory buffer.
        if mode == "survey" and seconds > 180:
            raise ValueError("Native RF spectrum surveys are limited to 180 s; use raw IQ for longer intervals")
        needed = {"survey": "rtl_power", "iq": "rtl_sdr", "aprs": "rtl_fm", "sstv_audio": "rtl_fm", "fm_audio": "rtl_fm"}[mode]
        if not shutil.which(needed) or (mode == "aprs" and not shutil.which("multimon-ng")):
            raise RuntimeError("Required installed RF decoder missing: " + ("multimon-ng" if mode == "aprs" else needed))
        if owner is not None and (not isinstance(owner, str) or
                not re.fullmatch(r"[A-Za-z0-9_-]{12,80}", owner)):
            raise ValueError("Invalid browser client identifier")
        with self.lock:
            if self.closed.is_set():
                raise RuntimeError("Satellite Center is shutting down")
            if not self.receiver_enabled:
                raise RuntimeError("Receiver disabled in Hardware. Connect & verify USB to enable RF.")
            if self.session.get("active"):
                raise RuntimeError("Satellite capture already running")
            self.stopping.clear()
            self._acquire()
            self.active_worker = threading.current_thread()
            self.manual_owner = None if scheduled else owner
            self.last_manual_heartbeat = time.monotonic()
            suffix = {"survey": ".json", "iq": ".cu8", "aprs": ".txt", "sstv_audio": ".wav", "fm_audio": ".wav"}[mode]
            candidate = str(satellite or PROFILE_TARGETS.get(profile, "RF-UNATTRIBUTED"))
            if not candidate.upper().endswith(("CANDIDATE", "UNATTRIBUTED")):
                candidate += "-CANDIDATE"
            frequency = int(PROFILES[profile]["freq"] or 0)
            target = self.archive/recording_name(
                satellite=candidate, timestamp=now(), frequency_hz=frequency,
                sample_rate=sample_rate if mode == "iq" else 48000 if mode in ("sstv_audio", "fm_audio") else None,
                kind={"survey":"SURVEY","iq":"IQ","aprs":"APRS","sstv_audio":"SSTV-AUDIO","fm_audio":"VOICE-AUDIO"}[mode],
                extension=suffix)
            if target.exists():
                raise RuntimeError("Capture for this satellite already exists at this UTC second")
            self.session = {"state": "running", "active": True, "profile": profile, "mode": mode,
                            "started_at": stamp(), "path": target.name, "message": "Physical receiver requested; acquisition pending",
                            "scheduled": scheduled}
        if self.manual_owner:
            threading.Thread(target=self._manual_watchdog, args=(self.manual_owner,),
                             name="satellite-browser-watchdog", daemon=True).start()
        try:
            if mode == "survey":
                command = [shutil.which("rtl_power"), "-d", "0", "-f", PROFILES[profile]["range"], "-i", "2s"]
                command += ["-e", f"{seconds}s"]  # honor selected full survey length
                import tempfile
                with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as error:
                    proc = self._launch_receiver(command, stdout=output, stderr=error,
                                            stdin=subprocess.DEVNULL)
                    with self.lock: self.process = proc
                    try:
                        until = time.monotonic() + seconds + 12
                        while proc.poll() is None and not self.stopping.is_set() and time.monotonic() < until:
                            time.sleep(0.2)
                        if self.stopping.is_set() or proc.poll() is None:
                            raise RuntimeError("Spectrum survey stopped or timed out")
                        if proc.returncode:
                            error.seek(0)
                            raise RuntimeError("rtl_power exited with error: " + error.read(200).decode("utf-8", "replace"))
                        output.seek(0)
                        raw = output.read(800001)
                    finally:
                        stop_process(proc)
                        with self.lock: self.process = None
                if len(raw) > 800000:
                    raise RuntimeError("Spectrum output exceeded size cap")
                data = parse_power(raw.decode("utf-8", "replace"), profile)
                if not data["measured_bins"]:
                    raise RuntimeError("No usable RF readings")
                data.update(started_at=self.session["started_at"], observed_at=stamp(),
                            source="rtl_power/physical_usb", satellite_verified=False)
                safe_write(target, data)
            elif mode == "iq":
                rate = sample_rate
                count = seconds*rate
                if shutil.disk_usage(self.archive).free < 2*count+200_000_000:
                    raise RuntimeError("Insufficient free disk space for bounded IQ capture")
                command = [shutil.which("rtl_sdr"), "-d", "0", "-f", str(PROFILES[profile]["freq"]),
                           "-s", str(rate), "-g", "35", "-n", str(count), str(target)]
                self._run_bounded(command, seconds+20)
            elif mode == "aprs":
                cmd1 = [shutil.which("rtl_fm"), "-d", "0", "-f", str(PROFILES[profile]["freq"]), "-M", "fm", "-s", "22050", "-g", "30"]
                cmd2 = [shutil.which("multimon-ng"), "-t", "raw", "-a", "AFSK1200", "-"]
                with target.open("xb") as out:
                    rx = self._launch_receiver(cmd1, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                    try:
                        decode = self._launch_receiver(cmd2, stdin=rx.stdout, stdout=out, stderr=subprocess.DEVNULL)
                        rx.stdout.close()
                        self._wait_decode([rx, decode], seconds)
                    finally:
                        stop_process(rx)
                        if "decode" in locals(): stop_process(decode)
            else:
                cmd = [shutil.which("rtl_fm"), "-d", "0", "-f", str(PROFILES[profile]["freq"]),
                       "-M", "fm", "-s", "48000", "-g", "30"]
                rx = self._launch_receiver(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                try:
                    with wave.open(str(target), "wb") as wav:
                        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(48000)
                        finish = time.monotonic()+seconds
                        while time.monotonic() < finish and not self.stopping.is_set():
                            block = rx.stdout.read(9600)
                            if not block: break
                            wav.writeframesraw(block)
                finally:
                    stop_process(rx)
            if self.stopping.is_set():
                raise RuntimeError("Capture cancelled by operator")
            if not target.exists() or target.stat().st_size == 0:
                raise RuntimeError("No actual RF data captured")
            size = target.stat().st_size
            result = {"file": target.name, "bytes": size, "mode": mode,
                      "sample_rate":sample_rate if mode=="iq" else None,
                      "profile": profile, "observed_at": stamp(),
                      "status": "recorded_unverified_rf"}
            if mode == "survey": result["status"] = "relative_spectrum_measurement"
            with self.lock:
                self.session.update(state="completed", message="Capture saved; never guarantees satellite origin")
            return result
        except (OSError, subprocess.TimeoutExpired, RuntimeError) as exc:
            with self.lock:
                self.session.update(state="error", message=str(exc)[:200])
            raise RuntimeError(str(exc)) from exc
        finally:
            with self.lock:
                self.session["active"] = False
                self.session["ended_at"] = stamp()
                self.manual_owner = None
                self.active_worker = None
                self.process = None
                self.owned_processes = {p for p in self.owned_processes if p.poll() is None}
                self._release()

    def _run_bounded(self, command, timeout):
        proc = self._launch_receiver(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        with self.lock: self.process = proc
        try:
            until = time.monotonic()+timeout
            while proc.poll() is None and not self.stopping.is_set() and time.monotonic()<until:
                time.sleep(0.2)
            if self.stopping.is_set() or proc.poll() is None:
                raise RuntimeError("Receiver stopped or timed out")
            if proc.returncode:
                raise RuntimeError("RF recorder exited unsuccessfully (device busy, permission or signal)")
        finally:
            stop_process(proc)
            with self.lock: self.process = None

    def _wait_decode(self, procs, seconds):
        finish = time.monotonic()+seconds
        while time.monotonic()<finish and not self.stopping.is_set():
            if any(p.poll() is not None for p in procs):
                break
            time.sleep(0.2)
        for proc in procs: stop_process(proc)

    def request_stop(self):
        self.stopping.set()
        with self.lock:
            processes = set(self.owned_processes)
            if self.process is not None:
                processes.add(self.process)
        # Do not hold the station mutex while waiting for child process exit.
        # Only processes launched by this Station are stopped (never readsb).
        for proc in processes:
            stop_process(proc)
        with self.lock:
            self.owned_processes.difference_update(p for p in processes if p.poll() is not None)
        return {"requested": True, "owned_processes_stop_requested": len(processes)}

    def records(self):
        result = []
        for path in sorted(self.archive.iterdir(), reverse=True)[:100]:
            if path.is_file() and path.suffix.lower() in (
                ".json", ".cu8", ".txt", ".wav", ".png", ".jpg", ".jpeg",
                ".mp4", ".m4v", ".mov", ".webm", ".gif", ".webp",
                ".mp3", ".ogg", ".flac", ".csv", ".geojson"):
                result.append({"file": path.name, "bytes": path.stat().st_size,
                               "modified": datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat(timespec="seconds")})
        return result

    def decode_meteor(self, name, variant="72k"):
        if not meteor_capture(name):
            raise ValueError("Select an archived Meteor IQ recording")
        if self.session.get("active"):
            raise RuntimeError("Stop RF acquisition before decoding")
        exe = shutil.which("satdump")
        if not exe:
            raise RuntimeError("SatDump not installed; original .cu8 remains available")
        if variant not in ("72k", "80k"):
            raise ValueError("Supported Meteor LRPT decoder variants: 72k or 80k")
        src = self.archive/name
        if not src.is_file():
            raise ValueError("Recording not found")
        dest = self.archive/(src.stem+"_decoded")
        dest.mkdir(exist_ok=True, mode=0o700)
        cmd = [exe, "pipeline",
               "meteor_m2-x_lrpt_80k" if variant=="80k" else "meteor_m2-x_lrpt",
               "baseband", str(src), str(dest),
               "--samplerate", "1024000", "--baseband_format", "cu8", "--dc_block"]
        try:
            result = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True,
                                    timeout=220, check=False)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("SatDump decoder timed out; original capture preserved") from exc
        # Only real SatDump-created files can become photo-gallery items.
        # Copies receive satellite + capture UTC + frequency filenames; no
        # decoded image is invented if the decoder fails or has no lock.
        image_files = sorted(
            (p for p in dest.rglob("*") if p.is_file() and
             p.suffix.lower() in (".png", ".jpg") and not p.name.startswith("TIHULU_")
             and p.stat().st_size <= 15_000_000),
            key=lambda p:str(p))[:32]
        match = re.search(r"_(\d{8}T\d{6}Z)_(\d{7,11})Hz", name)
        original_time = (datetime.strptime(match.group(1), "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
                         if match else datetime.fromtimestamp(src.stat().st_mtime, UTC))
        original_freq = int(match.group(2)) if match else 137900000
        original_satellite = name.split("_")[1] if name.startswith("TIHULU_") else "METEOR-UNVERIFIED"
        images = []
        for idx, image in enumerate(image_files, start=1):
            output_name = recording_name(
                satellite=original_satellite, timestamp=original_time,
                frequency_hz=original_freq, kind="LRPT-IMAGE-"+str(idx).zfill(2),
                extension=image.suffix.lower())
            output = dest/output_name
            if image.resolve() != output.resolve():
                shutil.copyfile(image,output)
            images.append(str(output.relative_to(self.archive)))
        return {"decoder_exit": result.returncode, "images": images, "variant": variant,
                "result": "actual_decoder_files" if images else "no_images_decoded",
                "note": "Only actual SatDump-created image files are shown; satellite source is a target candidate, not independently verified.",
                "stderr": result.stderr.decode("utf-8", "replace")[-500:]}


PAGE = Path(__file__).with_name("index.html")
# The installed Windows/macOS/Linux/Raspberry Pi app serves the SAME
# browser-only live map and imagery modules that GitHub Pages serves.
# Static serving never takes ownership of a USB device or launches a service.
WEB_ASSETS = PAGE.parent/"browser"
WEB_TYPES = {
    ".html":"text/html; charset=utf-8", ".js":"text/javascript; charset=utf-8",
    ".mjs":"text/javascript; charset=utf-8", ".css":"text/css; charset=utf-8",
    ".json":"application/json", ".geojson":"application/geo+json",
    ".webmanifest":"application/manifest+json", ".svg":"image/svg+xml",
    ".png":"image/png", ".jpg":"image/jpeg", ".ico":"image/x-icon"
}


class Handler(BaseHTTPRequestHandler):
    server: "Server"

    def guard(self):
        if not local_host_allowed(self.headers.get("Host", ""), self.server.server_port):
            self.reply(403, {"error": "Unexpected Host; localhost only"})
            return False
        origin = self.headers.get("Origin")
        site = self.headers.get("Sec-Fetch-Site", "")
        if not allowed_origin(origin, self.headers.get("Host", "")):
            self.reply(403, {"error": "Origin not allowed"})
            return False
        if site == "cross-site" and not origin:
            self.reply(403, {"error": "Cross-site browser resource blocked"})
            return False
        if request_is_remote(origin):
            bearer = self.headers.get("Authorization", "")
            if not secrets.compare_digest(bearer, "Bearer " + self.server.station.pairing_token):
                self.reply(401, {"error": "Enter the pairing token from your local Satellite Center"})
                return False
        return True

    def do_OPTIONS(self):
        if not local_host_allowed(self.headers.get("Host", ""), self.server.server_port):
            return self.reply(403, {"error": "Host rejected"})
        if not request_is_remote(self.headers.get("Origin")):
            return self.reply(403, {"error": "Cross-origin access denied"})
        self.send_response(204)
        self.cors_headers()
        if self.headers.get("Access-Control-Request-Private-Network") == "true":
            self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.send_header("Access-Control-Max-Age", "300")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def cors_headers(self):
        if request_is_remote(self.headers.get("Origin")):
            self.send_header("Access-Control-Allow-Origin", "https://tihulu.github.io")
            self.send_header("Vary", "Origin")

    def send_bytes(self, code, content, mime="application/json; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", mime)
        self.cors_headers()
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self' http://127.0.0.1:8791 http://localhost:8791; img-src 'self' data:; frame-src 'self'; form-action 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(content)

    def reply(self, code, data):
        self.send_bytes(code, json.dumps(data, ensure_ascii=False).encode(), "application/json; charset=utf-8")

    def browser_static(self, route):
        """Same-origin, path-confined read-only browser modules shared with Pages."""
        name = route.removeprefix("/browser/")
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", name) or name.startswith("."):
            return self.reply(400, {"error": "Invalid bundled browser resource"})
        path = WEB_ASSETS/name
        if path.suffix not in WEB_TYPES or not path.is_file() or path.stat().st_size > 2_000_000:
            return self.reply(404, {"error": "Browser resource not found"})
        raw = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", WEB_TYPES[path.suffix])
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header("Permissions-Policy", "usb=(self), geolocation=(self)")
        self.send_header("Content-Security-Policy",
            "default-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'self'; "
            "script-src 'self' https://cdn.jsdelivr.net https://esm.sh; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "img-src 'self' https: blob: data:; "
            "connect-src 'self' https://api.nasa.gov https://images-api.nasa.gov "
            "https://geocoding-api.open-meteo.com https://celestrak.org https://esm.sh; "
            "media-src 'self' blob:; worker-src 'self' blob:")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if not self.guard():
            return
        route = urlsplit(self.path).path
        try:
            if route == "/":
                return self.send_bytes(200, PAGE.read_bytes(), "text/html; charset=utf-8")
            if route.startswith("/browser/"):
                return self.browser_static(route)
            if route == "/api/status":
                from urllib.parse import parse_qs
                client = parse_qs(urlsplit(self.path).query).get("client", [None])[0]
                if client:
                    self.server.station.heartbeat(client)
                return self.reply(200, {**self.server.station.status(), "csrf": self.server.csrf})
            if route == "/api/sky":
                from urllib.parse import parse_qs
                q = parse_qs(urlsplit(self.path).query)
                return self.reply(200, self.server.station.sky(city=q.get("city", ["Cologne"])[0],
                    lat=q.get("lat", [None])[0], lon=q.get("lon", [None])[0]))
            if route == "/api/passes":
                from urllib.parse import parse_qs
                q = parse_qs(urlsplit(self.path).query)
                city = q.get("city", ["Cologne"])[0]
                return self.reply(200, self.server.station.passes(city=city, hours=int(q.get("hours", ["24"])[0]),
                    elevation=float(q.get("elev", ["15"])[0]),
                    lat=q.get("lat", [None])[0], lon=q.get("lon", [None])[0]))
            if route.startswith("/api/image/"):
                sub = route.removeprefix("/api/image/")
                # Only locally generated, fixed-name Robot36 candidate PNGs.
                # Keep existing path-restricted SatDump handling unchanged.
                if re.fullmatch(r"TIHULU_[A-Za-z0-9_-]+_ROBOT36_[0-9]{2}\.png", sub):
                    path = self.server.station.archive/sub
                    if not path.is_file() or not 0 < path.stat().st_size <= 15_000_000:
                        return self.reply(404, {"error": "Robot36 image unavailable"})
                    return self.send_bytes(200, path.read_bytes(), "image/png")
                match = re.fullmatch(r"([A-Za-z0-9_.-]+)_decoded/([A-Za-z0-9_./-]+\.(png|jpg|jpeg))", sub)
                if not match or ".." in sub or not meteor_capture(match.group(1)+".cu8"):
                    return self.reply(400, {"error": "Invalid image path"})
                path = (self.server.station.archive/sub).resolve()
                if not path.is_relative_to(self.server.station.archive.resolve()) or not path.is_file() or path.stat().st_size > 15_000_000:
                    return self.reply(404, {"error": "Image unavailable"})
                return self.send_bytes(200, path.read_bytes(), "image/png" if path.suffix == ".png" else "image/jpeg")
            if route.startswith("/api/archive/"):
                file = route.removeprefix("/api/archive/")
                if not re.fullmatch(r"[a-zA-Z0-9_\-]+\.(json|txt|wav|cu8)", file):
                    return self.reply(400, {"error": "Invalid archive filename"})
                path = self.server.station.archive/file
                if not path.is_file(): return self.reply(404, {"error": "Not found"})
                # Allow explicit download, not unchecked in-browser rendering.
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Disposition", f'attachment; filename="{file}"')
                self.send_header("Content-Length", str(path.stat().st_size))
                self.cors_headers()
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Referrer-Policy", "no-referrer")
                self.end_headers()
                with path.open("rb") as fp:
                    while data := fp.read(65536): self.wfile.write(data)
                return
            return self.reply(404, {"error": "Not found"})
        except (ValueError, OSError) as exc:
            return self.reply(400, {"error": str(exc)[:240]})

    def do_POST(self):
        if not self.guard():
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 2 or length > 4096:
                return self.reply(413, {"error": "Invalid request size"})
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict) or data.get("csrf") != self.server.csrf:
                return self.reply(403, {"error": "CSRF token required"})
            route = urlsplit(self.path).path
            app = self.server.station
            if route == "/api/pair":
                if request_is_remote(self.headers.get("Origin")):
                    return self.reply(403, {"error": "Pair locally at http://127.0.0.1:8791"})
                result = {"token": app.pairing_token, "warning": "Keep private; anyone with it and Pages origin can operate the local receiver"}
            elif route == "/api/leave":
                result = app.leave(data.get("client_id"))
            elif route == "/api/quit":
                # Owner requested shutting down companion, including pending pass worker.
                threading.Thread(target=self._shutdown_companion, daemon=True).start()
                result = {"closing": True, "note": "Stopping owned SDR processes; future schedules require restarting the companion"}
            elif route == "/api/usb-test":
                result = app.usb_test()
            elif route == "/api/refresh":
                result = app.refresh()
            elif route == "/api/schedule":
                result = app.schedule(data.get("pass_id"), data.get("profile"), data.get("mode"),
                                      data.get("run_at"), data.get("duration_seconds"))
            elif route == "/api/auto-schedule":
                result = app.auto_schedule(data.get("missions"), city=data.get("city", "Cologne"),
                    lat=data.get("lat"), lon=data.get("lon"),
                    hours=data.get("hours", 24), elevation=data.get("elevation", 20),
                    max_jobs=data.get("max_jobs", 6), coverage_goal=data.get("coverage_goal", "full"),
                    duration_seconds=data.get("duration_seconds"),
                    compute_mode=data.get("compute_mode", "auto"),
                    compute_targets=data.get("compute_targets"),
                    event_window_only=data.get("event_window_only", False))
            elif route == "/api/auto-edit":
                result = app.edit_auto_schedule(data.get("job_id"), data.get("run_at"),
                                                data.get("mission_id"), data.get("duration_seconds"))
            elif route == "/api/auto-cancel":
                result = app.cancel_auto_missions()
            elif route == "/api/cancel":
                result = app.cancel(data.get("job_id"))
            elif route == "/api/capture":
                # Must not block request thread for full capture; result via status and archive.
                seconds = data.get("seconds", 18)
                if type(seconds) is not int:
                    raise ValueError("seconds must be integer")
                with app.lock:
                    if app.session.get("active") or app.launching:
                        raise RuntimeError("Receiver already active")
                    profile, mode = data.get("profile"), data.get("mode", "survey")
                    owner = data.get("client_id")
                    if owner is not None and (not isinstance(owner, str) or not re.fullmatch(r"[A-Za-z0-9_-]{12,80}", owner)):
                        raise ValueError("Invalid browser client identifier")
                    if profile not in PROFILES or not allowed_mode(profile, mode):
                        raise ValueError("Invalid profile/mode")
                    if not 8 <= seconds <= MAX_CAPTURE_SECONDS:
                        raise ValueError("Manual duration must be 8–900 seconds")
                    app.launching = True
                    threading.Thread(target=self._background_capture,
                                     args=(profile, mode, seconds, owner), daemon=True).start()
                result = {"accepted": True, "note": "Check status; acquisition may fail on busy/missing SDR"}
            elif route == "/api/stop":
                result = app.request_stop()
            elif route == "/api/decode":
                result = app.decode_meteor(data.get("filename"), data.get("variant", "72k"))
            else:
                return self.reply(404, {"error": "Not found"})
            return self.reply(200, result)
        except (ValueError, RuntimeError, OSError, json.JSONDecodeError) as exc:
            return self.reply(400, {"error": str(exc)[:240]})

    def _shutdown_companion(self):
        self.server.station.close()
        self.server.shutdown()

    def _background_capture(self, profile, mode, seconds, owner=None):
        try:
            self.server.station.capture(profile, mode, seconds, owner=owner)
        except (ValueError, RuntimeError, OSError) as exc:
            with self.server.station.lock:
                self.server.station.session.update(state="error", active=False,
                                                   message=str(exc)[:200])
        finally:
            with self.server.station.lock:
                self.server.station.launching = False

    def log_message(self, fmt, *args):
        return


class Server(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, address, station):
        self.station = station
        self.csrf = secrets.token_urlsafe(32)
        super().__init__(address, Handler)

    def server_close(self):
        self.station.close()
        super().server_close()


def main():
    ap = argparse.ArgumentParser(description="Native Qt Widgets SDR desktop (legacy HTTP service opt-in)")
    ap.add_argument("command", nargs="?", choices=("desktop", "serve", "doctor", "cleanup-shortcuts"), default="desktop")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8791)
    ap.add_argument("--open-browser", action="store_true", help="Open desktop browser after the local server starts")
    ap.add_argument("--apply", action="store_true",
                    help="With cleanup-shortcuts, archive old user-local Satellite Center icons")
    args = ap.parse_args()
    if args.host != "127.0.0.1" or not (1024 <= args.port <= 65535):
        ap.error("Loopback-only address 127.0.0.1 and port 1024–65535 required")
    if args.command == "cleanup-shortcuts":
        from .desktop_shortcuts import cleanup
        return cleanup(apply=args.apply)
    if args.command == "desktop":
        # Native Qt Widgets only. No HTTP listener, browser, Chromium or WebView.
        try:
            from .desktop import main as launch_native
        except ImportError as exc:
            raise SystemExit("Native Qt GUI requires PyQt5. Debian/Pop!_OS: sudo apt install python3-pyqt5 python3-numpy") from exc
        return launch_native()
    station = Station()
    if args.command == "doctor":
        print(json.dumps(station.status(), ensure_ascii=False, indent=2))
    else:
        print(f"TIHULU Satellite Center: http://127.0.0.1:{args.port}/ (receiver idle)")
        with Server((args.host, args.port), station) as server:
            if args.open_browser:
                threading.Thread(target=lambda: webbrowser.open(f"http://127.0.0.1:{args.port}/"), daemon=True).start()
            previous_term = signal.getsignal(signal.SIGTERM)
            def terminate(_signum, _frame):
                # shutdown() must run on a different thread than serve_forever().
                threading.Thread(target=server.shutdown, daemon=True).start()
            signal.signal(signal.SIGTERM, terminate)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
            finally:
                signal.signal(signal.SIGTERM, previous_term)
                station.close()

if __name__ == "__main__":
    main()
