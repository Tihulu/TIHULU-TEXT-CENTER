"""Reproducible, offline RFGeo source package and non-mutating installer plans.

This module NEVER installs, uninstalls, migrates, opens receivers, unbinds USB
drivers, stops services or accesses GNSS/SDR hardware. It contains no network IO.
It deliberately does not execute either bundled Linux receiver helper.
"""
from __future__ import annotations

import ast
import gzip
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import platform
import sys
import tarfile
from typing import Mapping

FORMAT = "tihulu-rfgeo-source-package-v1"
APP_ID = "tihulu.rf-geolocation-center"
VERSION = "0.1.0-dev"
NAME = "tihulu-rfgeo-0.1.0-dev-linux-python-any.tar.gz"
MAX_ARCHIVE_BYTES = 16 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 24 * 1024 * 1024
PY_FILES = ("__init__.py", "__main__.py", "native.py", "dvb_bridge.py", "radio_metadata.py")
BUNDLE_LAUNCHER = "bin/tihulu-rfgeo"
LAUNCHER = (
    "#!/bin/sh\n"
    "set -eu\n"
    'APP_ROOT=$(CDPATH="" cd -- "$(dirname -- "$0")/.." && pwd -P)\n'
    'cd "$APP_ROOT"\n'
    'exec python3 -m rf_geolocation_center "$@"\n'
).encode("utf-8")


class PackageError(ValueError):
    """A packaging, manifest, ownership or compatibility gate failed."""


def _canonical_json(data: object) -> bytes:
    return (json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
            + "\n").encode("utf-8")


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_member(name: str) -> bool:
    path = PurePosixPath(name)
    return (bool(name) and not name.startswith("/") and "\\" not in name
            and ":" not in name and all(part not in ("", ".", "..") for part in name.split("/"))
            and str(path) == name
            and (name in (BUNDLE_LAUNCHER, "package-manifest.json")
                 or (name.startswith("rf_geolocation_center/")
                     and len(path.parts) >= 2)))


def _source_inventory(source_root: Path) -> dict[str, bytes]:
    """Derive the static closure from the launcher allowlist without importing it.

    Importing native.py is unnecessary and must not become a backend probe.
    Packaging scripts and tests are intentionally excluded from the payload.
    """
    source_root = Path(source_root)
    if not source_root.is_dir() or source_root.is_symlink():
        raise PackageError("source root must be a real RFGeo directory")
    tree = ast.parse((source_root / "native.py").read_text(encoding="utf-8"))
    allowlist = None
    for statement in tree.body:
        if isinstance(statement, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "ASSETS"
            for target in statement.targets
        ):
            allowlist = ast.literal_eval(statement.value)
            break
    if not isinstance(allowlist, dict) or len(allowlist) < 25:
        raise PackageError("native asset allowlist is missing or incomplete")
    selected = set(PY_FILES)
    selected.update(item[0] for item in allowlist.values())
    result = {}
    root = source_root.resolve(strict=True)
    for relative in sorted(selected):
        if not isinstance(relative, str) or not _safe_member("rf_geolocation_center/" + relative):
            raise PackageError("unsafe asset path in native allowlist")
        candidate = source_root / relative
        if any(part.is_symlink() for part in (candidate, *candidate.parents)
               if part != source_root and part.is_relative_to(source_root)):
            raise PackageError("symlinked payload file or directory")
        if not candidate.is_file() or not candidate.resolve(strict=True).is_relative_to(root):
            raise PackageError("missing or escaping RFGeo asset: " + relative)
        content = candidate.read_bytes()
        if len(content) > MAX_UNCOMPRESSED_BYTES:
            raise PackageError("oversized asset: " + relative)
        result["rf_geolocation_center/" + relative] = content
    result[BUNDLE_LAUNCHER] = LAUNCHER
    return result


def _package_manifest(contents: Mapping[str, bytes]) -> dict:
    return {
        "format": FORMAT,
        "app_id": APP_ID,
        "version": VERSION,
        "payload": "source-only-offline-localhost-Python3.11",
        "supported_linux_architectures": ["aarch64", "x86_64"],
        "minimum_python": "3.11",
        "required_python_dependencies": ["Python standard library"],
        "optional_capabilities": ["Web Serial NMEA (browser+consent)",
                                  "WebUSB RTL-SDR (Chromium+consent)",
                                  "Linux DVBv5 scan (owned receiver+consent)",
                                  "online OSM/TLE/ADS-B (optional)"],
        "hardware_verified": False,
        "native_desktop_binary": False,
        "real_install_performed": False,
        "owned_files": {name: {"sha256": _digest(data), "size": len(data)}
                        for name, data in sorted(contents.items())},
    }


def _tar_bytes(entries: Mapping[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        for name, data in sorted(entries.items()):
            if not _safe_member(name):
                raise PackageError("unsafe member name: " + name)
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mtime = 0
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            info.mode = 0o755 if name == BUNDLE_LAUNCHER else 0o644
            tar.addfile(info, io.BytesIO(data))
    out = io.BytesIO()
    with gzip.GzipFile(fileobj=out, mode="wb", filename="", mtime=0, compresslevel=9) as compressed:
        compressed.write(buffer.getvalue())
    return out.getvalue()


def build_bytes(source_root: Path) -> tuple[bytes, dict]:
    """Same source bytes produce identical .tar.gz bytes and checksums."""
    contents = _source_inventory(source_root)
    manifest = _package_manifest(contents)
    entries = dict(contents)
    entries["package-manifest.json"] = _canonical_json(manifest)
    payload = _tar_bytes(entries)
    if len(payload) > MAX_ARCHIVE_BYTES:
        raise PackageError("archive exceeds size cap")
    return payload, manifest


def build_to(source_root: Path, out_dir: Path) -> dict:
    """Explicit artifact output only, exclusive create; never overwrites files."""
    out_dir = Path(out_dir)
    if not out_dir.is_absolute() or out_dir.is_symlink():
        raise PackageError("explicit absolute, non-symlink artifact directory required")
    payload, manifest = build_bytes(source_root)
    if not out_dir.is_dir():
        raise PackageError("output directory must already exist; no implicit mkdir")
    target = out_dir / NAME
    if target.exists() or target.is_symlink():
        raise PackageError("refusing to overwrite any existing archive")
    try:
        with target.open("xb") as out:
            out.write(payload)
            out.flush()
            os.fsync(out.fileno())
    except FileExistsError as error:
        raise PackageError("archive already exists") from error
    return {"archive": str(target), "sha256": _digest(payload),
            "size": len(payload), "manifest": manifest}


def verify_bytes(payload: bytes) -> dict:
    """Strict file-only archive validation; never extract or execute members."""
    if len(payload) > MAX_ARCHIVE_BYTES:
        raise PackageError("oversized package")
    try:
        archive = tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz")
    except (OSError, tarfile.TarError) as error:
        raise PackageError("invalid compressed package") from error
    files: dict[str, bytes] = {}
    total = 0
    with archive:
        for member in archive.getmembers():
            if (not member.isfile() or not _safe_member(member.name)
                    or member.name in files or member.size > MAX_UNCOMPRESSED_BYTES):
                raise PackageError("unsafe, duplicated or non-regular package member")
            total += member.size
            if total > MAX_UNCOMPRESSED_BYTES:
                raise PackageError("excessive uncompressed payload")
            stream = archive.extractfile(member)
            if stream is None:
                raise PackageError("unreadable archive member")
            files[member.name] = stream.read()
    raw_manifest = files.pop("package-manifest.json", None)
    if raw_manifest is None:
        raise PackageError("missing package manifest")
    try:
        manifest = json.loads(raw_manifest)
    except (ValueError, UnicodeError) as error:
        raise PackageError("invalid manifest JSON") from error
    if (not isinstance(manifest, dict) or manifest.get("format") != FORMAT
            or manifest.get("app_id") != APP_ID or manifest.get("version") != VERSION
            or manifest.get("owned_files") != _package_manifest(files)["owned_files"]
            or manifest.get("native_desktop_binary") is not False
            or manifest.get("hardware_verified") is not False):
        raise PackageError("untrusted package metadata/checksum mismatch")
    if (set(files) != set(_source_inventory_from_manifest_paths(files))
            or BUNDLE_LAUNCHER not in files
            or files[BUNDLE_LAUNCHER] != LAUNCHER):
        raise PackageError("incomplete or extra package files")
    return manifest


def _source_inventory_from_manifest_paths(files: Mapping[str, bytes]) -> list[str]:
    """Forbid docs/tests/other apps and executable helper additions in payload."""
    result = []
    for name in files:
        if name == BUNDLE_LAUNCHER:
            result.append(name)
            continue
        parts = PurePosixPath(name).parts
        if parts[0] != "rf_geolocation_center" or len(parts) > 3:
            raise PackageError("foreign package member")
        rel = parts[1:]
        if len(parts) == 2 and parts[1] in (
                *PY_FILES, "index.html", "manifest.webmanifest", "sw.js"):
            result.append(name)
        elif len(parts) == 3 and parts[1] in ("core", "web", "scripts"):
            if parts[1] == "scripts" and parts[2] not in (
                "dvb_scan_linux.sh", "usb_prepare_linux.sh"):
                raise PackageError("unapproved executable helper")
            result.append(name)
        else:
            raise PackageError("foreign path in package")
    if not all("rf_geolocation_center/" + name in files for name in PY_FILES):
        raise PackageError("missing required Python source")
    return result


def verify_path(archive_path: Path) -> dict:
    archive_path = Path(archive_path)
    if archive_path.is_symlink() or not archive_path.is_file():
        raise PackageError("archive must be a local, regular, non-symlinked file")
    if archive_path.stat().st_size > MAX_ARCHIVE_BYTES:
        raise PackageError("oversized archive")
    return verify_bytes(archive_path.read_bytes())


def linux_data_roots(home: Path, env: Mapping[str, str] | None = None) -> dict[str, str]:
    """Pure path calculation, never create a directory or inspect its contents."""
    home = Path(home)
    if not home.is_absolute():
        raise PackageError("absolute user home required")
    env = {} if env is None else env
    def base(key: str, fallback: str) -> Path:
        candidate = Path(env.get(key) or str(home / fallback))
        if not candidate.is_absolute() or ".." in candidate.parts:
            raise PackageError("invalid XDG base " + key)
        return candidate
    app = Path("tihulu") / "rf-geolocation-center"
    data = base("XDG_DATA_HOME", ".local/share") / app
    return {
        "config": str(base("XDG_CONFIG_HOME", ".config") / app),
        "cache": str(base("XDG_CACHE_HOME", ".cache") / app),
        "data": str(data),
        "recordings": str(data / "recordings"),
        "exports": str(data / "exports"),
        "models_reserved_not_implemented": str(data / "models"),
        "logs": str(base("XDG_STATE_HOME", ".local/state") / app / "logs"),
    }


def compatibility_report(system: str | None = None, machine: str | None = None,
                         python_version: tuple[int, int] | None = None) -> dict:
    system = platform.system() if system is None else system
    machine = platform.machine() if machine is None else machine
    python_version = sys.version_info[:2] if python_version is None else python_version
    normalized = {"amd64": "x86_64", "arm64": "aarch64"}.get(machine.lower(), machine.lower())
    supported = system == "Linux" and normalized in ("x86_64", "aarch64") and python_version >= (3, 11)
    return {
        "os": system, "architecture": normalized,
        "python": ".".join(str(v) for v in python_version),
        "linux_portable_source_eligible": supported,
        "native_gui_binary_installed": False,
        "receiver_ownership_verified": False,
        "manual_receiver_actions_allowed": False,
        "required": ["Python >=3.11 (stdlib-only)", "local browser for UI"],
        "optional_linux_dvb": ["user-granted /dev/dvb access", "dvbv5-scan",
                               "exclusive available tuner with explicit consent"],
        "unverified": ["physical receiver", "WebUSB/browser permission", "Windows installer",
                       "macOS signed app", "ARM device performance"],
    }


def _reject_symlink_ancestors(path: Path) -> None:
    current = path
    while True:
        if current.is_symlink():
            raise PackageError("symlinked install target/parent forbidden")
        if current == current.parent:
            break
        current = current.parent


def plan_install(archive_path: Path, prefix: Path, home: Path,
                 env: Mapping[str, str] | None = None) -> dict:
    """Read-only dry-run; refuse every pre-existing owned destination file."""
    manifest = verify_path(archive_path)
    prefix = Path(prefix)
    home = Path(home)
    if not prefix.is_absolute() or ".." in prefix.parts or prefix == Path("/") or prefix == home:
        raise PackageError("explicit dedicated absolute install prefix required")
    _reject_symlink_ancestors(prefix)
    roots = linux_data_roots(home, env)
    for root in roots.values():
        data = Path(root)
        if prefix == data or prefix.is_relative_to(data) or data.is_relative_to(prefix):
            raise PackageError("install prefix overlaps reserved user data")
    planned = []
    for name, info in sorted(manifest["owned_files"].items()):
        target = prefix / name
        if target.exists() or target.is_symlink():
            raise PackageError("refusing to overwrite existing app/foreign file: " + str(target))
        planned.append({"path": str(target), "sha256": info["sha256"], "size": info["size"],
                        "created_only_after_user_approved_installer": True})
    return {
        "schema": "rfgeo-install-dry-run-v1",
        "app_id": APP_ID, "version": VERSION, "mode": "DRY_RUN_ONLY",
        "archive_sha256": _digest(Path(archive_path).read_bytes()),
        "prefix": str(prefix), "planned_created_files": planned,
        "preserve_user_data_roots": roots,
        "foreign_apps_required": [],
        "receiver_claims": False, "driver_changes": False, "service_changes": False,
        "network_listeners_started": False, "install_executed": False,
        "rollback_instruction": "Future installer may remove ONLY unchanged files listed in this plan; NEVER delete user data.",
    }


def review_rollback(plan: Mapping, prefix: Path) -> dict:
    """Read-only rollback assessment, never deletes or rewrites even one file."""
    prefix = Path(prefix)
    if plan.get("schema") != "rfgeo-install-dry-run-v1" or plan.get("prefix") != str(prefix):
        raise PackageError("wrong app/rollback manifest prefix")
    if plan.get("app_id") != APP_ID or plan.get("mode") != "DRY_RUN_ONLY":
        raise PackageError("wrong app/rollback manifest")
    _reject_symlink_ancestors(prefix)
    removable, protected = [], []
    for item in plan.get("planned_created_files", []):
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise PackageError("malformed rollback entry")
        name = Path(item["path"])
        if not name.is_relative_to(prefix) or not _safe_member(name.relative_to(prefix).as_posix()):
            raise PackageError("rollback entry escapes app prefix")
        if name.is_symlink():
            protected.append({"path": str(name), "reason": "symlink"});
        elif name.exists():
            if not name.is_file() or _digest(name.read_bytes()) != item.get("sha256"):
                protected.append({"path": str(name), "reason": "modified-or-unowned"})
            else:
                removable.append(str(name))
    return {"mode": "REVIEW_ONLY", "eligible_owned_unchanged_files": removable,
            "protected_modified_or_foreign_files": protected,
            "data_roots_untouched": plan.get("preserve_user_data_roots", {}),
            "deletion_executed": False}
