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
from .bridge import (app_data_dir, lock_receiver, unlock_receiver, start_receiver_process,
                     stop_receiver_process, pairing_secret, allowed_origin,
                     local_host_allowed, request_is_remote)

UTC = timezone.utc
DATA = Path(os.getenv("TIHULU_SATELLITE_DATA", str(app_data_dir())))
TEXT_CENTER_LOCK = (Path.home()/".local/share/tihulu-text-center/.receiver-locks/rtl_fm_rds.lock"
                    if os.name != "nt" else DATA/".receiver-locks/rtl_fm_rds.lock")
MAX_IQ_BYTES = 1_073_741_824  # 1 GiB: maximum per captured file
MAX_CAPTURE_SECONDS = 480
SOURCE_URLS = {
    "iss": "https://celestrak.org/NORAD/elements/gp.php?CATNR=25544&FORMAT=TLE",
    "meteor3": "https://celestrak.org/NORAD/elements/gp.php?CATNR=57166&FORMAT=TLE",
    "meteor4": "https://celestrak.org/NORAD/elements/gp.php?CATNR=59051&FORMAT=TLE",
    "amateur": "https://celestrak.org/NORAD/elements/gp.php?GROUP=amateur&FORMAT=TLE",
    "iridium": "https://celestrak.org/NORAD/elements/gp.php?GROUP=iridium-NEXT&FORMAT=TLE",
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
    "iss_uhf": {"label": "ISS repeater vicinity", "range": "437.76M:437.86M:5k", "freq": 437800000, "family": "iss"},
    "meteor": {"label": "Meteor-M LRPT primary (137.900 MHz)", "range": "137.0M:138.0M:12.5k", "freq": 137900000, "family": "meteor"},
    "meteor_backup": {"label": "Meteor-M LRPT alternate (137.100 MHz)", "range": "137.0M:138.0M:12.5k", "freq": 137100000, "family": "meteor"},
    "cubesat_vhf": {"label": "Amateur VHF survey", "range": "145.0M:146.0M:12.5k", "freq": None, "family": "cubesat"},
    "cubesat_uhf": {"label": "Amateur UHF survey", "range": "435.0M:438.0M:25k", "freq": None, "family": "cubesat"},
    "iridium": {"label": "Iridium L-band RF survey", "range": "1616M:1626.5M:50k", "freq": None, "family": "iridium"},
}
MODES = ("survey", "iq", "aprs", "sstv_audio")


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
        profile == "iss_aprs" and mode == "aprs"
    ) or (profile in ("iss_voice", "iss_sstv") and mode == "sstv_audio")


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


def detect_busy():
    """Defensive, best-effort cross-application check; not an OS-wide lease."""
    if platform.system() != "Linux":
        return []  # Windows/macOS: no reliable passive OS-wide process check.
    try:
        from textcenter.conflicts import find_receiver_conflicts
        return find_receiver_conflicts()
    except ImportError:
        return [{"process": "textcenter_conflict_check_unavailable"}]


def tuner_present():
    try:
        from textcenter.receivers import receiver_inventory
        inv = receiver_inventory()
        return inv.get("platform") == "Linux" and inv.get("rtl_usb_count") == 1
    except ImportError:
        return False


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
        self.predicted = {}
        self.wake = threading.Event()
        self.scheduler_thread = None
        if any(j.get("state") == "pending" for j in self.jobs):
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
                    "orbit_cache": cached, "location_presets": LOCATIONS,
                    "profiles": PROFILES, "session": dict(self.session),
                    "jobs": [dict(j) for j in self.jobs[-100:]],
                    "archive": self.records()}

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

    def save_jobs(self):
        safe_write(self.directory/"schedule.json", self.jobs[-150:])

    def schedule(self, pass_id, profile, mode):
        with self.lock:
            event = self.predicted.get(pass_id)
            if not event:
                raise ValueError("Pass not in current prediction results; recalculate")
            if profile not in event["profiles"] or mode not in MODES or not allowed_mode(profile, mode):
                raise ValueError("Unsupported pass/profile/mode combination")
            aos = datetime.fromisoformat(event["aos"])
            los = datetime.fromisoformat(event["los"])
            if aos < now()+timedelta(seconds=12) or aos > now()+timedelta(days=3):
                raise ValueError("Schedule passes starting 12 seconds–3 days from now")
            if (los-aos).total_seconds() > 1500:
                raise ValueError("Predicted pass duration out of range")
            if sum(j["state"] == "pending" for j in self.jobs) >= 24:
                raise ValueError("At most 24 pending captures")
            if any(j.get("pass_id") == pass_id and j["state"] == "pending" for j in self.jobs):
                raise ValueError("This pass already has a pending capture")
            job = {"id": uuid.uuid4().hex[:12], "pass_id": pass_id, "satellite": event["name"],
                   "family": event["family"], "profile": profile, "mode": mode,
                   "aos": event["aos"], "los": event["los"], "state": "pending",
                   "created_at": stamp(), "result": None}
            self.jobs.append(job)
            self.save_jobs()
            self.start_scheduler()
            self.wake.set()
            return job

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
                pending.sort(key=lambda j: j["aos"])
                nearest = pending[0]
                delay = (datetime.fromisoformat(nearest["aos"])-now()).total_seconds()-10
            if delay > 0:
                self.wake.wait(min(delay, 60))
                self.wake.clear()
                continue
            with self.lock:
                if self.closed.is_set():
                    return
                if nearest["state"] != "pending":
                    continue
                if now() > datetime.fromisoformat(nearest["los"]):
                    nearest.update(state="missed", result="Pass elapsed while receiver unavailable")
                    self.save_jobs()
                    continue
                nearest["state"] = "running"
                self.save_jobs()
            try:
                duration = max(12, min(MAX_CAPTURE_SECONDS, int((datetime.fromisoformat(nearest["los"])-now()).total_seconds())))
                result = self.capture(nearest["profile"], nearest["mode"], duration,
                        scheduled=True, satellite=nearest.get("satellite"))
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

    def capture(self, profile, mode="survey", seconds=18, scheduled=False, owner=None, satellite=None):
        if profile not in PROFILES or mode not in MODES or not allowed_mode(profile, mode):
            raise ValueError("Unsupported capture preset")
        if type(seconds) is not int or not 8 <= seconds <= MAX_CAPTURE_SECONDS:
            raise ValueError("Capture duration must be 8–480 seconds")
        if not scheduled and seconds > 240:
            raise ValueError("Manual capture maximum is 240 seconds")
        needed = {"survey": "rtl_power", "iq": "rtl_sdr", "aprs": "rtl_fm", "sstv_audio": "rtl_fm"}[mode]
        if not shutil.which(needed) or (mode == "aprs" and not shutil.which("multimon-ng")):
            raise RuntimeError("Required installed RF decoder missing: " + ("multimon-ng" if mode == "aprs" else needed))
        if owner is not None and (not isinstance(owner, str) or
                not re.fullmatch(r"[A-Za-z0-9_-]{12,80}", owner)):
            raise ValueError("Invalid browser client identifier")
        with self.lock:
            if self.closed.is_set():
                raise RuntimeError("Satellite Center is shutting down")
            if self.session.get("active"):
                raise RuntimeError("Satellite capture already running")
            self.stopping.clear()
            self._acquire()
            self.active_worker = threading.current_thread()
            self.manual_owner = None if scheduled else owner
            self.last_manual_heartbeat = time.monotonic()
            suffix = {"survey": ".json", "iq": ".cu8", "aprs": ".txt", "sstv_audio": ".wav"}[mode]
            candidate = str(satellite or PROFILE_TARGETS.get(profile, "RF-UNATTRIBUTED"))
            if not candidate.upper().endswith(("CANDIDATE", "UNATTRIBUTED")):
                candidate += "-CANDIDATE"
            frequency = int(PROFILES[profile]["freq"] or 0)
            target = self.archive/recording_name(
                satellite=candidate, timestamp=now(), frequency_hz=frequency,
                sample_rate=1024000 if mode == "iq" else 48000 if mode == "sstv_audio" else None,
                kind={"survey":"SURVEY","iq":"IQ","aprs":"APRS","sstv_audio":"SSTV-AUDIO"}[mode],
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
                command += ["-e", f"{min(seconds, 180)}s"] if scheduled else ["-1"]
                import tempfile
                with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as error:
                    proc = self._launch_receiver(command, stdout=output, stderr=error,
                                            stdin=subprocess.DEVNULL)
                    with self.lock: self.process = proc
                    try:
                        until = time.monotonic() + (min(seconds, 180) + 12 if scheduled else 26)
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
                rate = 1024000
                count = min(seconds * rate, MAX_IQ_BYTES//2)
                if shutil.disk_usage(self.archive).free < 2*count+200_000_000:
                    raise RuntimeError("Insufficient free disk space for bounded IQ capture")
                command = [shutil.which("rtl_sdr"), "-d", "0", "-f", str(PROFILES[profile]["freq"]),
                           "-s", str(rate), "-g", "35", "-n", str(count), str(target)]
                self._run_bounded(command, seconds+20)
            elif mode == "aprs":
                cmd1 = [shutil.which("rtl_fm"), "-d", "0", "-f", "145825000", "-M", "fm", "-s", "22050", "-g", "30"]
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
            if path.is_file() and path.suffix in (".json", ".cu8", ".txt", ".wav", ".png", ".jpg"):
                result.append({"file": path.name, "bytes": path.stat().st_size,
                               "modified": datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat(timespec="seconds")})
        return result

    def decode_meteor(self, name):
        if not meteor_capture(name):
            raise ValueError("Select an archived Meteor IQ recording")
        if self.session.get("active"):
            raise RuntimeError("Stop RF acquisition before decoding")
        exe = shutil.which("satdump")
        if not exe:
            raise RuntimeError("SatDump not installed; original .cu8 remains available")
        src = self.archive/name
        if not src.is_file():
            raise ValueError("Recording not found")
        dest = self.archive/(src.stem+"_decoded")
        dest.mkdir(exist_ok=True, mode=0o700)
        cmd = [exe, "pipeline", "meteor_m2-x_lrpt", "baseband", str(src), str(dest),
               "--samplerate", "1024000", "--baseband_format", "cu8", "--dc_block"]
        try:
            result = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True,
                                    timeout=220, check=False)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("SatDump decoder timed out; original capture preserved") from exc
        images = [str(p.relative_to(self.archive)) for p in dest.rglob("*.png") if p.is_file()][:32]
        images += [str(p.relative_to(self.archive)) for p in dest.rglob("*.jpg") if p.is_file()][:32-len(images)]
        return {"decoder_exit": result.returncode, "images": images,
                "result": "actual_decoder_files" if images else "no_images_decoded",
                "note": "No images fabricated. Check pipeline version, frequency and signal quality.",
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
                result = app.schedule(data.get("pass_id"), data.get("profile"), data.get("mode"))
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
                    if not 8 <= seconds <= 240: raise ValueError("Manual duration must be 8–240")
                    app.launching = True
                    threading.Thread(target=self._background_capture,
                                     args=(profile, mode, seconds, owner), daemon=True).start()
                result = {"accepted": True, "note": "Check status; acquisition may fail on busy/missing SDR"}
            elif route == "/api/stop":
                result = app.request_stop()
            elif route == "/api/decode":
                result = app.decode_meteor(data.get("filename"))
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
    ap = argparse.ArgumentParser(description="Receive-only satellite companion: independent local web app")
    ap.add_argument("command", nargs="?", choices=("serve", "doctor"), default="serve")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8791)
    ap.add_argument("--open-browser", action="store_true", help="Open desktop browser after the local server starts")
    args = ap.parse_args()
    if args.host != "127.0.0.1" or not (1024 <= args.port <= 65535):
        ap.error("Loopback-only address 127.0.0.1 and port 1024–65535 required")
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
