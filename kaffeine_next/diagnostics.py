"""Read-only Kaffeine-native receiver and scan diagnostics.

Never opens /dev/dvb, never writes tuner settings, never retunes.
Use this while another Kaffeine might be running to identify the actual
driver, frontend ownership, preserved scan data and installation status.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import shutil
import subprocess

def inspect(home: Path | None = None, dev: Path | None = None):
    home = Path.home() if home is None else Path(home)
    dev = Path("/dev/dvb") if dev is None else Path(dev)
    launcher = home / ".local/bin/tihulu-kaffeine"
    binary = home / ".local/opt/tihulu-kaffeine/bin/kaffeine"
    scan = home / ".local/opt/tihulu-kaffeine/share/kaffeine/scanfile.dvb"
    devices = sorted(dev.glob("adapter*/frontend*")) if dev.is_dir() else []
    paths = [str(p) for p in devices]
    result = {
        "backend": "Kaffeine native Linux DVBv5, not WebUSB or w_scan_cpp",
        "launcher_installed": launcher.is_file(),
        "native_kaffeine_binary": binary.is_file(),
        "native_scanfile": {
            "path": str(scan), "exists": scan.is_file(),
            "bytes": scan.stat().st_size if scan.is_file() else None,
        },
        "frontend_devices": paths,
        "frontend_busy": "unknown",
        "checked_device_files_without_opening": True,
        "expected_test_multiplexes_mhz": [538, 586, 626],
        "config_hint": "TV > Configure Television > DVB-T2 Source: "
          "TIHULU tested: 538 / 586 / 626 MHz, then Television > Channels / Antenna Scan",
        "note": "This inspection does not measure signal strength, lock, C/N or BER",
    }
    if devices and shutil.which("fuser"):
        try:
            p = subprocess.run(["fuser", *paths], text=True, capture_output=True,
                 timeout=4, check=False)
            # A nonzero code from fuser often means no process owns the file.
            pids = [part for part in p.stdout.split() if part.isdecimal()]
            result["frontend_busy"] = bool(pids)
            result["frontend_owner_pids"] = pids
        except (OSError, subprocess.TimeoutExpired):
            result["frontend_busy"] = "unknown"
    if not devices:
        result["hint"] = "No Linux DVB frontend found; check WinTV USB driver, firmware and cable"
    elif result["frontend_busy"] is True:
        result["hint"] = "A tuner is already in use. Close the other TV app before full scan"
    elif not binary.is_file():
        result["hint"] = "Kaffeine-native build is missing; run the one-line Kaffeine installer"
    elif not scan.is_file():
        result["hint"] = "Native scanfile missing; the built-in targeted profile should still be available"
    else:
        result["hint"] = "Launch native Kaffeine and select DVB-T2 native source for scan"
    return result

def main(argv=None):
    print(json.dumps(inspect(), indent=2, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
