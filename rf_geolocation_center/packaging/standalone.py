"""Reproducible, no-network standalone RF Geolocation SOURCE bundle for Linux.

No subprocess, device enumeration, driver unbind, service control, model download,
global PATH modification, or foreign-application access occurs in this module.
install/rollback require an explicit --apply; defaults are read-only dry runs.
The package is not a native GUI binary or an SDR/GNSS positioning decoder.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import stat
import sys
import tarfile
import tempfile

APP_ID = "tihulu-rf-geolocation-center"
MODULE_DIR = "rf_geolocation_center"
SCHEMA = 1
MAX_FILE = 8 * 1024 * 1024
MAX_TOTAL = 48 * 1024 * 1024
MAX_FILES = 512
ALLOWED_TOP = frozenset({
    "__init__.py", "__main__.py", "native.py", "dvb_bridge.py",
    "radio_metadata.py", "index.html", "sw.js", "manifest.webmanifest",
    "README.md",
})
ALLOWED_DIRS = frozenset({"core", "web", "scripts", "docs", "packaging"})
ALLOWED_SUFFIXES = frozenset({".py", ".mjs", ".js", ".html", ".svg", ".css",
                              ".webmanifest", ".md", ".sh"})
OMIT_DIRS = frozenset({"tests", "__pycache__", ".git", ".pytest_cache"})
REQUIRED = frozenset({
    "__init__.py", "__main__.py", "native.py", "dvb_bridge.py",
    "radio_metadata.py", "index.html", "sw.js", "manifest.webmanifest",
    "web/app.mjs", "web/style.css", "web/icon.svg", "web/usb_sdr.mjs",
    "web/exit_lifecycle.mjs", "web/rf_survey.mjs",
    "web/catalog_discovery.mjs", "web/dvb_bridge_client.mjs",
    "core/gnss.mjs", "core/positioning.mjs", "core/evidence.mjs",
    "core/source_provenance.mjs", "core/rf_ranging.mjs",
    "packaging/__init__.py", "packaging/standalone.py",
})
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
REV_RE = re.compile(r"^[0-9a-f]{40}$")
VERSION_RE = re.compile(r'__version__\s*=\s*"([a-zA-Z0-9][a-zA-Z0-9.+_-]{0,63})"')


class PackagingError(ValueError):
    """Fail closed without silently repairing other application state."""


def _digest(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=True,
                       separators=(",", ":")) + "\n").encode("utf-8")


def _safe_rel(name: str) -> PurePosixPath:
    if not isinstance(name, str) or not name or "\\" in name or "//" in name:
        raise PackagingError("Invalid package path")
    p = PurePosixPath(name)
    if p.is_absolute() or any(part in (".", "..") for part in name.split("/")):
        raise PackagingError("Package traversal or absolute path")
    return p


def _allowed_file(name: str) -> bool:
    p = _safe_rel(name)
    if len(p.parts) == 1:
        return name in ALLOWED_TOP
    return (p.parts[0] in ALLOWED_DIRS and
            p.suffix in ALLOWED_SUFFIXES and
            all(part not in OMIT_DIRS for part in p.parts))


def _source_files(source: Path) -> dict[str, bytes]:
    if source.is_symlink() or not source.is_dir():
        raise PackagingError("Source must be an independent regular directory")
    files: dict[str, bytes] = {}
    total = 0
    for path in sorted(source.rglob("*")):
        rel = path.relative_to(source)
        if any(part in OMIT_DIRS for part in rel.parts):
            continue
        if path.is_symlink():
            raise PackagingError("Symlink in source tree: " + rel.as_posix())
        if path.is_dir():
            if rel.parts[0] not in ALLOWED_DIRS:
                raise PackagingError("Unexpected source directory: " + rel.as_posix())
            continue
        if not path.is_file() or not _allowed_file(rel.as_posix()):
            raise PackagingError("Unrecognized source file: " + rel.as_posix())
        if path.stat().st_size > MAX_FILE:
            raise PackagingError("Oversize source file: " + rel.as_posix())
        blob = path.read_bytes()
        total += len(blob)
        if total > MAX_TOTAL or len(files) >= MAX_FILES:
            raise PackagingError("Source package size/count limit")
        files[rel.as_posix()] = blob
    if not REQUIRED.issubset(files):
        raise PackagingError("Required standalone files missing: " +
                             ", ".join(sorted(REQUIRED.difference(files))))
    return files


def _version(files: dict[str, bytes]) -> str:
    match = VERSION_RE.search(files["__init__.py"].decode("utf-8"))
    if not match:
        raise PackagingError("Version must match the RFGeo Python package")
    return match.group(1)


def _file_metadata(name: str, blob: bytes) -> dict:
    return {"path": name, "sha256": _digest(blob), "bytes": len(blob),
            "mode": 0o755 if name.startswith("scripts/") and name.endswith(".sh") else 0o644}


def _archive_file(name: str, data: bytes, mode: int) -> tuple[tarfile.TarInfo, bytes]:
    info = tarfile.TarInfo(name)
    info.size = len(data)
    info.mtime = 0
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    info.mode = mode
    return info, data


def build_bundle(source: Path, output: Path, revision: str) -> dict:
    """Write a deterministic tar.gz EXCLUSIVELY to a new archive path."""
    if not REV_RE.fullmatch(revision):
        raise PackagingError("Require exact 40-hex source revision, never an unverified tag")
    files = _source_files(Path(source))
    manifest = {
        "schema": SCHEMA, "app_id": APP_ID,
        "source_revision_declared": revision,
        "version": _version(files),
        "format": "standalone-python-web-source",
        "targets": ["linux-x86_64", "linux-aarch64"],
        "optional_apps": ["Flight Radar", "Text Center"],
        "hardware_policy": "OPT_IN_ONLY; EXTERNAL_OWNER_FAIL_CLOSED",
        "files": [_file_metadata(p, files[p]) for p in sorted(files)],
    }
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w", format=tarfile.PAX_FORMAT) as tf:
        for name, blob in [("bundle-manifest.json", _json_bytes(manifest))] + [
            (MODULE_DIR + "/" + n, files[n]) for n in sorted(files)]:
            mode = 0o644 if name == "bundle-manifest.json" else _file_metadata(name.removeprefix(MODULE_DIR + "/"), blob)["mode"]
            info, payload = _archive_file(name, blob, mode)
            tf.addfile(info, io.BytesIO(payload))
    compressed = io.BytesIO()
    with gzip.GzipFile(fileobj=compressed, mode="wb", filename="", mtime=0,
                       compresslevel=9) as g:
        g.write(stream.getvalue())
    destination = Path(output)
    if not destination.parent.is_dir() or destination.is_symlink():
        raise PackagingError("Output parent must already exist; no path repairs")
    try:
        with destination.open("xb") as handle:  # No overwrite, including symlinks
            handle.write(compressed.getvalue())
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise PackagingError("Refuse to replace an existing package") from exc
    return {"archive": str(destination), "sha256": _digest(compressed.getvalue()),
            "manifest": manifest}


def verify_bundle(archive: Path) -> tuple[dict, dict[str, bytes], str]:
    """Read-only verify every byte, identity and member before any extraction."""
    archive = Path(archive)
    if archive.is_symlink() or not archive.is_file() or archive.stat().st_size > MAX_TOTAL + 1024 * 1024:
        raise PackagingError("Archive absent, symlinked or too large")
    assets: dict[str, bytes] = {}
    names: set[str] = set()
    total = 0
    try:
        with tarfile.open(archive, "r:gz") as tf:
            for member in tf:
                if len(names) >= MAX_FILES + 1:
                    raise PackagingError("Archive member limit")
                name = member.name
                _safe_rel(name)
                if name in names or not member.isfile() or member.size > MAX_FILE:
                    raise PackagingError("Duplicate, nonregular or oversize archive member")
                if name != "bundle-manifest.json":
                    if not name.startswith(MODULE_DIR + "/") or not _allowed_file(name[len(MODULE_DIR)+1:]):
                        raise PackagingError("Foreign/unsafe archive member: " + name)
                if member.mode not in (0o644, 0o755):
                    raise PackagingError("Unexpected file permissions")
                total += member.size
                if total > MAX_TOTAL:
                    raise PackagingError("Archive uncompressed size limit")
                reader = tf.extractfile(member)
                if reader is None:
                    raise PackagingError("Unreadable archive member")
                raw = reader.read(MAX_FILE + 1)
                if len(raw) != member.size:
                    raise PackagingError("Archive truncated or oversized")
                assets[name] = raw
                names.add(name)
    except (OSError, EOFError, tarfile.TarError) as exc:
        raise PackagingError("Invalid or truncated tar.gz archive") from exc
    try:
        manifest = json.loads(assets.pop("bundle-manifest.json"))
    except (KeyError, ValueError, UnicodeDecodeError) as exc:
        raise PackagingError("Missing/invalid standalone bundle manifest") from exc
    if not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA or manifest.get("app_id") != APP_ID:
        raise PackagingError("Wrong standalone package identity/schema")
    if not REV_RE.fullmatch(str(manifest.get("source_revision_declared", ""))):
        raise PackagingError("Missing exact source provenance")
    version = manifest.get("version")
    if not isinstance(version, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9.+_-]{0,63}", version):
        raise PackagingError("Invalid package version")
    records = manifest.get("files")
    if not isinstance(records, list) or not records:
        raise PackagingError("Missing package file metadata")
    recorded: dict[str, dict] = {}
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get("path"), str):
            raise PackagingError("Malformed package file metadata")
        path = record["path"]
        if not _allowed_file(path) or path in recorded:
            raise PackagingError("Unsafe/duplicate manifest path")
        recorded[path] = record
    if not REQUIRED.issubset(recorded):
        raise PackagingError("Missing required standalone asset")
    expected = {MODULE_DIR + "/" + name for name in recorded}
    if set(assets) != expected:
        raise PackagingError("Package manifest does not match archive entries")
    for name, record in recorded.items():
        raw = assets[MODULE_DIR + "/" + name]
        if record.get("bytes") != len(raw) or record.get("sha256") != _digest(raw):
            raise PackagingError("Package content hash/length mismatch: " + name)
        if record.get("mode") != (0o755 if name.startswith("scripts/") and name.endswith(".sh") else 0o644):
            raise PackagingError("Package file mode mismatch: " + name)
    return manifest, assets, _digest(archive.read_bytes())


def _home_paths(home: Path) -> dict[str, Path]:
    home = Path(home).absolute()
    return {
        "home": home,
        "install": home / ".local" / "opt" / APP_ID,
        "config": home / ".config" / APP_ID,
        "cache": home / ".cache" / APP_ID,
        "data": home / ".local" / "share" / APP_ID,
    }


def _safe_existing(path: Path, home: Path, *, file: bool = False) -> None:
    """Reject existing symlink ancestors and unexpected file/dir types."""
    home = home.absolute()
    if not path.is_relative_to(home):
        raise PackagingError("Refuse path outside selected user home")
    cur = home
    if cur.is_symlink() or not cur.is_dir():
        raise PackagingError("User home must be a real directory")
    for part in path.relative_to(home).parts:
        cur = cur / part
        if cur.is_symlink():
            raise PackagingError("Symlinked install/config/cache/data path: " + str(cur))
        if cur.exists() and (not cur.is_file() if file and cur == path else not cur.is_dir()):
            raise PackagingError("Wrong path type in app-owned scope: " + str(cur))


def _read_state(root: Path) -> dict | None:
    path = root / "state.json"
    if not path.exists():
        return None
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 100_000:
        raise PackagingError("Unsafe existing installer state")
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise PackagingError("Invalid existing installer state") from exc
    if not isinstance(state, dict) or state.get("app_id") != APP_ID or state.get("schema") != SCHEMA:
        raise PackagingError("Foreign install directory: state identity mismatch")
    if not isinstance(state.get("active"), str) or not re.fullmatch(r"[A-Za-z0-9.+_-]{1,120}", state["active"]):
        raise PackagingError("Invalid existing active version")
    if not isinstance(state.get("previous"), list) or len(state["previous"]) > 50 or any(
        not isinstance(x, str) or not re.fullmatch(r"[A-Za-z0-9.+_-]{1,120}", x)
        for x in state["previous"]
    ):
        raise PackagingError("Invalid existing rollback history")
    bundles = state.get("bundles")
    if not isinstance(bundles, dict) or len(bundles) > 100 or any(
        not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9.+_-]{1,120}", key)
        or not isinstance(value, str) or not SHA_RE.fullmatch(value)
        for key, value in bundles.items()
    ):
        raise PackagingError("Invalid saved full bundle digest history")
    if state["active"] not in bundles or any(x not in bundles for x in state["previous"]):
        raise PackagingError("Missing full digest for active or rollback release")
    if state.get("bundle_sha256") != bundles[state["active"]]:
        raise PackagingError("Inconsistent active bundle digest")
    return state


def _release_name(manifest: dict, sha256: str) -> str:
    return manifest["version"] + "-" + sha256[:16]


def _assert_scope(paths: dict[str, Path]) -> None:
    home = paths["home"]
    for key in ("install", "config", "cache", "data"):
        _safe_existing(paths[key], home)
    root = paths["install"]
    _safe_existing(root / "state.json", home, file=True)
    _safe_existing(root / "bin" / "tihulu-rfgeo", home, file=True)
    state = _read_state(root)
    if state is None and root.exists() and any(
        entry.name != ".operation-lock" for entry in root.iterdir()
    ):
        raise PackagingError("Existing unowned install prefix: refusing to adopt")


def host_capabilities(system: str | None = None, machine: str | None = None) -> dict:
    system = system or platform.system()
    machine = (machine or platform.machine()).lower()
    linux_supported = system == "Linux" and machine in {"x86_64", "amd64", "aarch64", "arm64"}
    return {
        "python": sys.version.split()[0], "system": system, "machine": machine,
        "supported_install_target": linux_supported and sys.version_info >= (3, 11),
        "runtime": "python >=3.11 stdlib + browser; NOT native GUI/RTL-SDR GNSS decoder",
        "optional_browser": "Chromium HTTPS WebUSB, user gesture only; never auto-claim",
        "optional_dvb": "Linux DVBv5 via separately requested user action, not required",
        "other_tihulu_app_required": False,
        "receiver_owner": "UNKNOWN / NO DEVICE ACCESSED",
        "external_services": "UNTOUCHED; no readsb/systemctl/driver action",
    }


def install_plan(archive: Path, *, home: Path | None = None,
                 system: str | None = None, machine: str | None = None) -> dict:
    caps = host_capabilities(system, machine)
    if not caps["supported_install_target"]:
        raise PackagingError("Installer apply supports Linux x64/ARM64 Python >=3.11 only")
    manifest, _files, archive_hash = verify_bundle(archive)
    paths = _home_paths(Path.home() if home is None else Path(home))
    _assert_scope(paths)
    state = _read_state(paths["install"])
    release = _release_name(manifest, archive_hash)
    target = paths["install"] / "releases" / release
    _safe_existing(target, paths["home"])
    if target.exists():
        raise PackagingError("Matching package already staged; never overwrite a release")
    return {
        "dry_run": True, "app_id": APP_ID, "version": manifest["version"],
        "source_revision_declared": manifest["source_revision_declared"],
        "bundle_sha256": archive_hash, "release": release,
        "previous_active": state["active"] if state else None,
        "install_path": str(target),
        "launcher": str(paths["install"] / "bin" / "tihulu-rfgeo"),
        "config": str(paths["config"]), "cache": str(paths["cache"]),
        "data": str(paths["data"]),
        "actions": ["write new versioned app-owned source files exclusively",
                    "create app-specific config/cache/data dirs if absent (never remove contents)",
                    "write application-only receipt and active/rollback manifest atomically",
                    "retain all old release files; no global PATH/desktop/service modifications"],
        "policy": "NO DEVICE, NO DRIVERS, NO READSB, NO FOREIGN APPLICATION ACCESS",
        "status": "PLAN ONLY; no writes performed",
    }


def _atomic_json(path: Path, value: dict) -> None:
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise PackagingError("Unsafe state file")
    data = _json_bytes(value)
    fd, temp = tempfile.mkstemp(prefix=".rfgeo-state-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp, 0o600)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def _launcher() -> str:
    # The launcher uses its own install root; NEVER sets PYTHONPATH or starts
    # readsb/SDR/system services. Browser/USB is still user initiated.
    return (
        "#!/usr/bin/env python3\n"
        "import json, os, pathlib, sys\n"
        "root = pathlib.Path(__file__).resolve().parent.parent\n"
        "state = json.loads((root / 'state.json').read_text(encoding='utf-8'))\n"
        "if state.get('app_id') != 'tihulu-rf-geolocation-center':\n"
        "    raise SystemExit('Unsafe RFGeo launcher state')\n"
        "release = root / 'releases' / state['active']\n"
        "if not release.is_dir() or release.is_symlink() or release.resolve().parent != (root / 'releases').resolve():\n"
        "    raise SystemExit('RFGeo release missing or unsafe')\n"
        "os.chdir(release)\n"
        "os.environ.setdefault('TIHULU_RFGEO_CONFIG_DIR', str(pathlib.Path.home() / '.config' / 'tihulu-rf-geolocation-center'))\n"
        "os.environ.setdefault('TIHULU_RFGEO_CACHE_DIR', str(pathlib.Path.home() / '.cache' / 'tihulu-rf-geolocation-center'))\n"
        "os.environ.setdefault('TIHULU_RFGEO_DATA_DIR', str(pathlib.Path.home() / '.local' / 'share' / 'tihulu-rf-geolocation-center'))\n"
        "os.execv(sys.executable, [sys.executable, '-m', 'rf_geolocation_center', *sys.argv[1:]])\n"
    )


def _verify_release(root: Path, release: str) -> dict:
    target = root / "releases" / release
    for directory in (root, root / "releases", target, target / MODULE_DIR):
        if directory.is_symlink() or not directory.is_dir():
            raise PackagingError("Missing or unsafe rollback release directory")
    if target.resolve().parent != (root / "releases").resolve():
        raise PackagingError("Release path escapes RFGeo installation scope")
    manifest_file = target / "bundle-manifest.json"
    rollback_file = target / "rollback-manifest.json"
    for entry in (manifest_file, rollback_file):
        if entry.is_symlink() or not entry.is_file() or entry.stat().st_size > 150_000:
            raise PackagingError("Missing or unsafe installed/rollback manifest")
    try:
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        rollback_record = json.loads(rollback_file.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise PackagingError("Invalid installed release manifest") from exc
    if (not isinstance(manifest, dict) or manifest.get("app_id") != APP_ID
            or manifest.get("schema") != SCHEMA or not REV_RE.fullmatch(
                str(manifest.get("source_revision_declared", "")))):
        raise PackagingError("Foreign installed release")
    if (not isinstance(rollback_record, dict) or rollback_record.get("app_id") != APP_ID
            or rollback_record.get("schema") != SCHEMA
            or rollback_record.get("new_release") != release
            or rollback_record.get("source_revision_declared") != manifest["source_revision_declared"]
            or not SHA_RE.fullmatch(str(rollback_record.get("bundle_sha256", "")))):
        raise PackagingError("Invalid rollback evidence manifest")
    records = manifest.get("files")
    if not isinstance(records, list) or not records or len(records) > MAX_FILES:
        raise PackagingError("Missing or oversize installed file inventory")
    seen: set[str] = set()
    for entry in records:
        if not isinstance(entry, dict):
            raise PackagingError("Malformed installed file inventory")
        name = entry.get("path")
        if not isinstance(name, str) or not _allowed_file(name) or name in seen:
            raise PackagingError("Invalid or duplicate installed manifest path")
        seen.add(name)
        dest = target / MODULE_DIR
        for component in PurePosixPath(name).parts:
            dest = dest / component
            if dest.is_symlink():  # Includes all directory ancestors, not just the file.
                raise PackagingError("Symlinked installed release path: " + name)
        if (not dest.is_file() or not dest.resolve().is_relative_to(target.resolve())
                or dest.stat().st_size > MAX_FILE):
            raise PackagingError("Installed release changed or missing: " + name)
        if entry.get("bytes") != dest.stat().st_size or entry.get("sha256") != _digest(dest.read_bytes()):
            raise PackagingError("Installed release content changed: " + name)
    if not REQUIRED.issubset(seen):
        raise PackagingError("Required app assets missing in installed release")
    return manifest

def install_bundle(archive: Path, *, apply: bool = False, home: Path | None = None,
                   system: str | None = None, machine: str | None = None) -> dict:
    plan = install_plan(archive, home=home, system=system, machine=machine)
    if not apply:
        return plan
    manifest, assets, _hash = verify_bundle(archive)
    paths = _home_paths(Path.home() if home is None else Path(home))
    root = paths["install"]
    # Fail closed on parallel operations; do not break a stale lock automatically.
    root.mkdir(parents=True, exist_ok=True)
    lock = root / ".operation-lock"
    try:
        lock.mkdir()
    except FileExistsError as exc:
        raise PackagingError("RFGeo package operation already active or needs inspection") from exc
    try:
        _assert_scope(paths)  # Re-check after acquiring lock.
        prior = _read_state(root)
        release = plan["release"]
        target = root / "releases" / release
        target.mkdir(parents=True, exist_ok=False)
        for name, blob in sorted(assets.items()):
            relative = name.removeprefix(MODULE_DIR + "/")
            dest = target / MODULE_DIR / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            with dest.open("xb") as handle:
                handle.write(blob)
            os.chmod(dest, 0o755 if relative.startswith("scripts/") and relative.endswith(".sh") else 0o644)
        with (target / "bundle-manifest.json").open("xb") as handle:
            handle.write(_json_bytes(manifest))
        rollback_manifest = {
            "schema": SCHEMA, "app_id": APP_ID, "new_release": release,
            "previous_release": prior["active"] if prior else None,
            "bundle_sha256": plan["bundle_sha256"],
            "source_revision_declared": manifest["source_revision_declared"],
            "rollback": "Repoint state.json to verified previous release only",
            "deletion_policy": "NEVER DELETE RELEASES, CONFIG, CACHE, DATA OR USER FILES",
        }
        with (target / "rollback-manifest.json").open("xb") as handle:
            handle.write(_json_bytes(rollback_manifest))
        _verify_release(root, release)
        for key in ("config", "cache", "data"):
            paths[key].mkdir(parents=True, exist_ok=True)
        bin_path = root / "bin" / "tihulu-rfgeo"
        bin_path.parent.mkdir(parents=True, exist_ok=True)
        if bin_path.exists():
            if bin_path.is_symlink() or bin_path.read_text(encoding="utf-8") != _launcher():
                raise PackagingError("Refuse to replace an unrecognized launcher")
        else:
            with bin_path.open("x", encoding="utf-8") as handle:
                handle.write(_launcher())
            os.chmod(bin_path, 0o755)
        history = ([prior["active"]] + prior["previous"])[:50] if prior else []
        bundles = dict(prior.get("bundles", {})) if prior else {}
        bundles[release] = plan["bundle_sha256"]
        state = {"schema": SCHEMA, "app_id": APP_ID, "active": release,
                 "previous": history, "bundle_sha256": plan["bundle_sha256"],
                 "bundles": bundles,
                 "source_revision_declared": manifest["source_revision_declared"],
                 "data_paths": {key: str(paths[key]) for key in ("config", "cache", "data")},
                 "rollback_policy": "switch only version pointer; preserve prior releases and ALL user data"}
        _atomic_json(root / "state.json", state)
        return {**plan, "dry_run": False, "status": "STAGED IN EXPLICIT USER SCOPE",
                "rollback": "python -m rf_geolocation_center.packaging.standalone rollback --apply"}
    finally:
        lock.rmdir()


def rollback_plan(*, home: Path | None = None, system: str | None = None,
                  machine: str | None = None) -> dict:
    if not host_capabilities(system, machine)["supported_install_target"]:
        raise PackagingError("Rollback applies only to supported Linux user installs")
    paths = _home_paths(Path.home() if home is None else Path(home))
    _assert_scope(paths)
    state = _read_state(paths["install"])
    if not state or not state["previous"]:
        raise PackagingError("No preceding app-owned release; no rollback performed")
    prior = state["previous"][0]
    _verify_release(paths["install"], prior)
    return {"dry_run": True, "from": state["active"], "to": prior,
            "state_path": str(paths["install"] / "state.json"),
            "policy": "NO FILE DELETION; OTHER APPS, CONFIG/CACHE/DATA AND RECEIVERS UNTOUCHED"}


def rollback(*, apply: bool = False, home: Path | None = None,
             system: str | None = None, machine: str | None = None) -> dict:
    plan = rollback_plan(home=home, system=system, machine=machine)
    if not apply:
        return plan
    paths = _home_paths(Path.home() if home is None else Path(home))
    root = paths["install"]
    lock = root / ".operation-lock"
    try:
        lock.mkdir()
    except FileExistsError as exc:
        raise PackagingError("RFGeo install/rollback lock occupied") from exc
    try:
        again = rollback_plan(home=home, system=system, machine=machine)
        if again["from"] != plan["from"] or again["to"] != plan["to"]:
            raise PackagingError("Rollback target changed during review")
        state = _read_state(root)
        state["active"] = plan["to"]
        state["previous"] = [plan["from"]] + state["previous"][1:]
        chosen = _verify_release(root, state["active"])
        state["source_revision_declared"] = chosen["source_revision_declared"]
        state["bundle_sha256"] = state.get("bundles", {}).get(state["active"])
        if not isinstance(state["bundle_sha256"], str) or not SHA_RE.fullmatch(state["bundle_sha256"]):
            raise PackagingError("Cannot identify rollback release's original full bundle digest")
        _atomic_json(root / "state.json", state)
        return {**plan, "dry_run": False, "status": "ROLLED BACK BY VERSION POINTER ONLY"}
    finally:
        lock.rmdir()


def _emit(record: dict) -> None:
    print(json.dumps(record, sort_keys=True, indent=2))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="RFGeo reproducible source packaging; no automatic devices")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check", help="Read-only host/platform/dependency assessment, never inspect USB")
    build = sub.add_parser("build", help="Deterministic tar.gz from RFGeo folder only")
    build.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1])
    build.add_argument("--output", type=Path, required=True)
    build.add_argument("--revision", required=True, help="Pinned exact reviewed Git SHA")
    plan = sub.add_parser("plan", help="Read-only archive verification and Linux user install plan")
    plan.add_argument("--archive", type=Path, required=True)
    inst = sub.add_parser("install", help="Dry run by default; only --apply stages to user home")
    inst.add_argument("--archive", type=Path, required=True)
    inst.add_argument("--apply", action="store_true")
    undo = sub.add_parser("rollback", help="Dry run by default; --apply changes only app-owned active version")
    undo.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "check":
            _emit(host_capabilities())
        elif args.command == "build":
            _emit(build_bundle(args.source, args.output, args.revision))
        elif args.command == "plan":
            _emit(install_plan(args.archive))
        elif args.command == "install":
            _emit(install_bundle(args.archive, apply=args.apply))
        elif args.command == "rollback":
            _emit(rollback(apply=args.apply))
        else:
            parser.error("Unknown command")
        return 0
    except (PackagingError, OSError) as exc:
        parser.exit(2, "RFGeo package blocked: " + str(exc) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
