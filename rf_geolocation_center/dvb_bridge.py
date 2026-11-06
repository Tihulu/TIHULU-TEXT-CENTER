"""Loopback-only explicitly authorized DVBv5 scan worker.

Never serves the general filesystem and never executes user-supplied commands.
All tuner access requires a user-initiated authenticated POST from the local UI
or the opt-in official TIHULU Pages origin. Without a Linux DVB frontend,
this bridge truthfully reports unavailable. Scanning is asynchronous and bounded.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import tempfile
import threading
import time

DEFAULT_PROFILE = "eu-uhf-t2"
MAX_SCAN_SECONDS = 240
MAX_CHANNELS = 300
MAX_SCAN_BYTES = 1024 * 1024
SYSTEM_SCAN_ROOTS = (Path("/usr/share/dvb"), Path("/usr/share/dvbv5"), Path("/usr/local/share/dvb"))
VALID_PROFILE_NAME = re.compile(r"^[a-zA-Z0-9_./-]{1,100}$")


def _system_tables():
    profiles = []
    for root in SYSTEM_SCAN_ROOTS:
        if not root.is_dir():
            continue
        for pattern in ("dvb-t/*", "dvb-t2/*", "dvb-c/*", "*dvb-t*", "*dvb-c*"):
            try:
                entries = sorted(root.glob(pattern))[:150]
            except OSError:
                continue
            for path in entries:
                try:
                    resolved = path.resolve(strict=True)
                    if not resolved.is_relative_to(root.resolve()) or not resolved.is_file():
                        continue
                    if resolved.stat().st_size < 20 or resolved.stat().st_size > 256_000:
                        continue
                    # Never expose arbitrary filesystem paths to the requesting web page.
                    label = str(path.relative_to(root))
                    if not VALID_PROFILE_NAME.fullmatch(label):
                        continue
                    profile_id = "system:" + label
                    if any(p["id"] == profile_id for p in profiles):
                        continue
                    profiles.append({"id": profile_id, "name": label,
                                     "description": "Installed regional DVB scan table",
                                     "_path": str(resolved)})
                except (OSError, ValueError):
                    continue
                if len(profiles) >= 80:
                    return profiles
    return profiles


def profiles():
    values = [{"id": DEFAULT_PROFILE, "name": "Europe UHF DVB-T2 • channels 21–48",
               "description": "Standard 474–690 MHz 8 MHz-spaced tuning candidates; not measured services"}]
    for entry in _system_tables():
        values.append({k: v for k, v in entry.items() if k != "_path"})
    return values


def _frontend_usb_metadata(adapter_id):
    """Read actual sysfs USB ancestor, never infer tuner model from adapter index."""
    syspath = Path("/sys/class/dvb") / ("dvb" + str(adapter_id) + ".frontend0") / "device"
    try:
        current = syspath.resolve(strict=True)
        for parent in (current, *current.parents):
            vendor_file, product_file = parent / "idVendor", parent / "idProduct"
            if vendor_file.is_file() and product_file.is_file():
                vendor = vendor_file.read_text().strip().lower()[:4]
                product = product_file.read_text().strip().lower()[:4]
                def read_label(name):
                    path = parent / name
                    return path.read_text(errors="replace").strip()[:90] if path.is_file() else ""
                manufacturer = read_label("manufacturer")
                label = read_label("product")
                return {"usbId": vendor + ":" + product,
                        "manufacturer": manufacturer, "product": label,
                        "likelyHauppauge": vendor == "2040" or
                            "hauppauge" in manufacturer.lower() or "hauppauge" in label.lower()}
    except (OSError, ValueError):
        pass
    return {"usbId": None, "manufacturer": "", "product": "",
            "likelyHauppauge": False}


def adapters():
    found = []
    root = Path("/dev/dvb")
    if not root.is_dir():
        return found
    for folder in sorted(root.glob("adapter[0-9]*"))[:12]:
        try:
            adapter_id = int(folder.name[7:])
            if not (0 <= adapter_id <= 99):
                continue
            if (folder / "frontend0").exists():
                info = _frontend_usb_metadata(adapter_id)
                found.append({"adapter": adapter_id, "device": "Linux DVB adapter " + str(adapter_id),
                              "path": str(folder / "frontend0"), **info,
                              "origin": "REAL OS DVB FRONTEND (not RTL-SDR WebUSB)"})
        except (ValueError, OSError):
            continue
    return found


def _build_uhf_table(path):
    # EU UHF raster, DVB-T2 scan hypotheses; NEVER label these as real channels.
    with path.open("w", encoding="ascii") as out:
        for channel in range(21, 49):
            freq_mhz = 474 + (channel - 21) * 8
            out.write("[SCAN CANDIDATE UHF %s]\n" % channel)
            out.write("DELIVERY_SYSTEM = DVBT2\n")
            out.write("FREQUENCY = %s\n" % (freq_mhz * 1000000))
            out.write("BANDWIDTH_HZ = 8000000\n\n")


def parse_channels(text):
    """Read *actual scan output* only, not synthetic channel guesses."""
    if len(text) > MAX_SCAN_BYTES:
        raise ValueError("DVB scan output exceeds 1 MiB")
    records = []
    current = None

    def save():
        if current is None:
            return
        try:
            f = int(current.get("FREQUENCY", "0"))
        except ValueError:
            return
        if not 40_000_000 <= f <= 1_200_000_000:
            return
        def numeric(key):
            val = str(current.get(key, ""))
            return int(val) if val.isdecimal() else None
        records.append({"name": current["_NAME"], "frequencyHz": f, "frequencyMHz": f/1e6,
                        "deliverySystem": current.get("DELIVERY_SYSTEM", "UNKNOWN"),
                        "serviceId": numeric("SERVICE_ID"),
                        "networkId": numeric("NETWORK_ID"),
                        "transportStreamId": numeric("TRANSPORT_ID"),
                        "transmitterIdentified": False, "hardwareReceived": True,
                        "provenance": "NATIVE LINUX DVBv5 / REAL CHANNEL SCAN",
                        "positionFix": False})
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith(";"):
            continue
        if line.startswith("[") and line.endswith("]"):
            save()
            name = line[1:-1].strip()[:120]
            current = {"_NAME": name} if name else None
            continue
        if current is None or "=" not in line:
            continue
        key, value = (part.strip() for part in line.split("=", 1))
        if key.upper() in {"FREQUENCY", "DELIVERY_SYSTEM", "SERVICE_ID", "NETWORK_ID", "TRANSPORT_ID"}:
            current[key.upper()] = value[:80]
    save()
    seen, unique = set(), []
    for record in records:
        identity = (record["name"], record["frequencyHz"], record["serviceId"])
        if identity in seen:
            continue
        seen.add(identity)
        unique.append(record)
        if len(unique) >= MAX_CHANNELS:
            break
    return unique


class DVBScanBridge:
    def __init__(self):
        self.token = secrets.token_urlsafe(32)
        self._lock = threading.RLock()
        self._process = None
        self._worker = None
        self._cancel = threading.Event()
        self._data = {"state": "IDLE", "channels": [], "startedAt": None,
                      "endedAt": None, "details": "No native DVB scan yet"}

    def capabilities(self):
        return {"platform": os.name, "available": os.name == "posix" and
                shutil.which("dvbv5-scan") is not None and bool(adapters()),
                "scanTool": shutil.which("dvbv5-scan") is not None,
                "adapters": adapters(), "profiles": profiles(),
                "description": "REAL native Linux DVB frontend only. No tuner simulation or location fix.",
                "source": "LOCAL LOOPBACK BRIDGE / NOT WEBUSB"}

    def status(self):
        with self._lock:
            snapshot = dict(self._data)
            snapshot["channels"] = list(self._data["channels"])
            return snapshot

    def start(self, adapter, profile):
        if type(adapter) is not int or not 0 <= adapter <= 99:
            raise ValueError("Choose a valid enumerated DVB adapter")
        if not isinstance(profile, str) or len(profile) > 110:
            raise ValueError("Choose a listed regional scan profile")
        if not any(d["adapter"] == adapter for d in adapters()):
            raise ValueError("Linux DVB frontend not found; connect Hauppauge and install its driver/firmware")
        if not shutil.which("dvbv5-scan"):
            raise ValueError("dvbv5-scan is not installed (install the distribution dvb-tools package)")
        selections = _system_tables()
        if profile != DEFAULT_PROFILE and not any(p["id"] == profile for p in selections):
            raise ValueError("Scan profile must be a listed installed table or standard EU UHF raster")
        with self._lock:
            if self._worker is not None and self._worker.is_alive():
                raise RuntimeError("A native DVB scan is already in progress")
            self._cancel = threading.Event()
            self._data = {"state": "RUNNING", "channels": [], "startedAt": time.time(),
                          "endedAt": None, "details": "Real Linux DVB frontend scanning; waiting for service table data",
                          "adapter": adapter, "profile": profile}
            self._worker = threading.Thread(target=self._run, args=(adapter, profile, selections, self._cancel),
                                            daemon=True, name="tihulu-dvb-scan")
            self._worker.start()
            return self.status()

    def _run(self, adapter, profile, selections, cancel):
        result_state, details, channels = "FAILED", "No tuner data", []
        try:
            with tempfile.TemporaryDirectory(prefix="tihulu-rfgeo-dvb-") as temp:
                root = Path(temp)
                initial = root / "initial.conf"
                output = root / "scanned.conf"
                if profile == DEFAULT_PROFILE:
                    _build_uhf_table(initial)
                else:
                    selected = next(p for p in selections if p["id"] == profile)
                    shutil.copyfile(selected["_path"], initial)
                cmd = [shutil.which("dvbv5-scan"), "-a", str(adapter),
                       "-O", "dvbv5", "-o", str(output), str(initial)]
                process = subprocess.Popen(cmd, cwd=root, stdin=subprocess.DEVNULL,
                                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                           start_new_session=True)
                with self._lock:
                    self._process = process
                try:
                    out, _ = process.communicate(timeout=MAX_SCAN_SECONDS)
                    preview = out[-3500:].decode("utf-8", errors="replace") if out else ""
                    if cancel.is_set():
                        result_state, details = "CANCELLED", "User stopped local DVB scan"
                    elif output.exists() and output.stat().st_size <= MAX_SCAN_BYTES:
                        channels = parse_channels(output.read_text(encoding="utf-8", errors="replace"))
                        result_state = "COMPLETE" if channels else "NO_SERVICES"
                        details = str(len(channels)) + " real DVB services scanned" if channels else "Tuner scan finished; no DVB services detected"
                        if process.returncode and not channels:
                            result_state = "FAILED"
                            details = "Native DVB scanner exited " + str(process.returncode) + ": " + preview[-500:]
                    elif process.returncode:
                        details = "Native tuner scanner failed (exit " + str(process.returncode) + "): " + preview[-500:]
                    else:
                        result_state, details = "NO_SERVICES", "No valid DVBv5 output file returned"
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.communicate()
                    details = "Native DVB scanning exceeded " + str(MAX_SCAN_SECONDS) + " seconds and was stopped"
                finally:
                    with self._lock:
                        self._process = None
        except (OSError, ValueError, StopIteration) as error:
            details = "Native DVB scan error: " + str(error)[:500]
        with self._lock:
            self._data.update({"state": result_state, "details": details,
                               "channels": channels, "endedAt": time.time(),
                               "source": "LINUX DVB-T/T2/C HARDWARE / NO GPS"})
            self._process = None

    def stop(self):
        with self._lock:
            if self._data.get("state") != "RUNNING":
                return self.status()
            self._cancel.set()
            if self._process and self._process.poll() is None:
                try:
                    self._process.terminate()
                except OSError:
                    pass
            return {"state": "STOPPING", "details": "User requested to stop native DVB scan"}
