#!/usr/bin/env python3
"""Offline, pinned Text-only bundle and opt-in, app-scoped install preparation.

No network, pip, service, hardware, model download or foreign-app control.
All write-capable deployment commands require --apply. Package always writes
only to its explicitly specified output path.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import re
import shutil
import stat
import sys
import tempfile
import zipfile

APP_ID = "tihulu.text-center"
PIN_FILE = Path(__file__).resolve().parents[1] / "packaging" / "text-only-source-pin.json"
FORMAT = "tihulu-text-only-bundle-v1"
MAX_PACKAGE_BYTES = 12_000_000
MAX_FILE_BYTES = 4_000_000
MAX_TOTAL_BYTES = 14_000_000
BUNDLE_NAME = "source.zip"
HEX64 = re.compile(r"[a-f0-9]{64}\Z")
FOREIGN_ROOT_NAMES = {
    "tihulu-media-center", "tihulu-flight-radar", "tihulu-satellite-center",
    "tihulu-rf-geolocation-center", "tihulu-survival-kit", "tihulu-ai-tools",
}


class InstallerError(RuntimeError):
    """Fail-closed without mutating foreign files."""


def _print(result):
    print(json.dumps(result, sort_keys=True, indent=2))


def pin_from_file(path=PIN_FILE):
    pin = json.loads(Path(path).read_text(encoding="utf-8"))
    if pin.get("format") != "tihulu-text-only-source-pin-v1":
        raise InstallerError("Unsupported Text source pin format")
    if pin.get("application_id") != APP_ID or pin.get("canonical_repository") != "Tihulu/TIHULU-TEXT-CENTER":
        raise InstallerError("Noncanonical Text source pin")
    if not re.fullmatch(r"[a-f0-9]{40}", pin.get("canonical_commit", "")):
        raise InstallerError("Invalid pinned commit")
    files = pin.get("files")
    if not isinstance(files, dict) or not files:
        raise InstallerError("Missing source pin entries")
    for name, blob in files.items():
        _source_name(name)
        if not re.fullmatch(r"[a-f0-9]{40}", blob):
            raise InstallerError("Invalid pinned Git blob")
    return pin


def _source_name(name):
    if not isinstance(name, str) or "\\" in name:
        raise InstallerError("Invalid source filename")
    parts = Path(name).parts
    if len(parts) != 2 or parts[0] not in ("textcenter", "web"):
        raise InstallerError("Bundle must contain only Text runtime and web assets")
    if name in ("textcenter/.", "web/.") or parts[1] in ("", ".", ".."):
        raise InstallerError("Invalid source path")
    if parts[0] == "textcenter" and not parts[1].endswith(".py"):
        raise InstallerError("Unexpected Text backend asset")
    if parts[0] == "web" and parts[1] not in ("app.js", "index.html", "styles.css", "favicon.svg"):
        raise InstallerError("Unexpected web asset")
    return name


def _blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def _strict_file(root, name):
    _source_name(name)
    root = Path(root)
    if root.is_symlink() or any((root / p).is_symlink() for p in (name.split("/")[0], name)):
        raise InstallerError("Symlink in pinned source tree")
    path = root / name
    if not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
        raise InstallerError("Pinned source file missing or oversized: " + name)
    data = path.read_bytes()
    if len(data) > MAX_FILE_BYTES:
        raise InstallerError("Oversized pinned source")
    return data


def _expected_manifest(pin, files):
    return {
        "format": FORMAT, "application_id": APP_ID,
        "canonical_repository": "Tihulu/TIHULU-TEXT-CENTER",
        "canonical_commit": pin["canonical_commit"],
        "version": pin["version"], "minimum_python": pin["minimum_python"],
        "files": {
            name: {"git_blob": pin["files"][name],
                   "sha256": hashlib.sha256(files[name]).hexdigest(),
                   "bytes": len(files[name])}
            for name in sorted(pin["files"])
        },
    }


def _manifest_bytes(manifest):
    return (json.dumps(manifest, sort_keys=True, ensure_ascii=True,
                       separators=(",", ":")) + "\n").encode("utf-8")


def bundle_bytes(source_root, pin):
    sources = {}
    for name in sorted(pin["files"]):
        data = _strict_file(source_root, name)
        if _blob(data) != pin["files"][name]:
            raise InstallerError("Canonical source blob mismatch: " + name)
        sources[name] = data
    manifest = _expected_manifest(pin, sources)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_STORED) as archive:
        for name in ("manifest.json", *sorted(sources)):
            raw = _manifest_bytes(manifest) if name == "manifest.json" else sources[name]
            entry = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            entry.create_system = 3
            entry.external_attr = (stat.S_IFREG | 0o600) << 16
            entry.compress_type = zipfile.ZIP_STORED
            archive.writestr(entry, raw)
    result = buffer.getvalue()
    if len(result) > MAX_PACKAGE_BYTES:
        raise InstallerError("Text-only package exceeds size limit")
    return result


def write_package(source_root, output, pin):
    content = bundle_bytes(source_root, pin)
    target = Path(output).expanduser()
    if target.is_symlink():
        raise InstallerError("Refusing symlink archive destination")
    if not target.parent.is_dir():
        raise InstallerError("Create the package output directory explicitly first")
    if target.exists():
        if target.is_file() and target.read_bytes() == content:
            return {"action": "package", "unchanged": True, "output": str(target),
                    "sha256": hashlib.sha256(content).hexdigest()}
        raise InstallerError("Refusing to overwrite an existing package")
    with target.open("xb") as f:
        f.write(content)
    return {"action": "package", "unchanged": False, "output": str(target),
            "sha256": hashlib.sha256(content).hexdigest(), "source": pin["canonical_commit"],
            "files": len(pin["files"])}


def inspect_bundle(data, pin=None):
    if len(data) > MAX_PACKAGE_BYTES:
        raise InstallerError("Oversized Text bundle")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            items = archive.infolist()
            names = [x.filename for x in items]
            if len(names) != len(set(names)) or "manifest.json" not in names:
                raise InstallerError("Duplicate or absent archive manifest")
            manifest_data = archive.read("manifest.json")
            manifest = json.loads(manifest_data)
            if manifest.get("format") != FORMAT or manifest.get("application_id") != APP_ID:
                raise InstallerError("Wrong application bundle")
            if manifest.get("canonical_repository") != "Tihulu/TIHULU-TEXT-CENTER":
                raise InstallerError("Wrong canonical repository")
            source_entries = manifest.get("files")
            if not isinstance(source_entries, dict) or set(names) != set(source_entries) | {"manifest.json"}:
                raise InstallerError("Unexpected bundle member or missing Text runtime source")
            if len(source_entries) != 24:
                raise InstallerError("Expected exactly 20 Text modules and 4 web assets")
            contents = {}
            total = 0
            for item in items:
                if item.compress_type != zipfile.ZIP_STORED or item.file_size > MAX_FILE_BYTES:
                    raise InstallerError("Unsupported/oversized package entry")
                mode = item.external_attr >> 16
                if item.create_system == 3 and stat.S_IFMT(mode) != stat.S_IFREG:
                    raise InstallerError("Nonregular bundle entry")
                if item.filename == "manifest.json":
                    continue
                _source_name(item.filename)
                raw = archive.read(item)
                total += len(raw)
                if total > MAX_TOTAL_BYTES:
                    raise InstallerError("Oversized bundle total")
                expected = source_entries[item.filename]
                if (not isinstance(expected, dict)
                        or expected.get("bytes") != len(raw)
                        or expected.get("sha256") != hashlib.sha256(raw).hexdigest()
                        or expected.get("git_blob") != _blob(raw)):
                    raise InstallerError("Text bundle contents do not match manifest")
                contents[item.filename] = raw
            if manifest_data != _manifest_bytes(manifest):
                raise InstallerError("Noncanonical manifest serialization")
            if pin is not None:
                if (manifest.get("canonical_commit") != pin["canonical_commit"]
                        or manifest.get("version") != pin["version"]
                        or manifest.get("minimum_python") != pin["minimum_python"]
                        or {k: v["git_blob"] for k, v in source_entries.items()} != pin["files"]):
                    raise InstallerError("Bundle does not match current pinned Text release")
            return manifest, contents
    except (zipfile.BadZipFile, KeyError, ValueError, TypeError, UnicodeError) as e:
        raise InstallerError("Invalid Text-only bundle") from e


def read_bundle(path, pin=None):
    filename = Path(path).expanduser()
    if filename.is_symlink() or not filename.is_file() or filename.stat().st_size > MAX_PACKAGE_BYTES:
        raise InstallerError("Bundle missing, symlinked or oversized")
    data = filename.read_bytes()
    manifest, contents = inspect_bundle(data, pin)
    return data, hashlib.sha256(data).hexdigest(), manifest, contents


def _not_foreign(path):
    if FOREIGN_ROOT_NAMES.intersection(x.lower() for x in Path(path).parts):
        raise InstallerError("Refusing another TIHULU application's path")


def _safe_prefix(prefix):
    p = Path(prefix).expanduser().absolute()
    _not_foreign(p)
    if p in (Path("/"), Path.home(), Path.home().parent):
        raise InstallerError("Prefix must be a dedicated Text-owned subdirectory")
    candidate = p
    while candidate != candidate.parent:
        if candidate.is_symlink():
            raise InstallerError("Symlink in installation prefix")
        candidate = candidate.parent
    return p


def _data_paths(data_root=None):
    root = Path(data_root or (Path.home() / ".local/share/tihulu-text-center")).expanduser().absolute()
    _not_foreign(root)
    return {
        "data_root": str(root),
        "database": str(root / "text-center.db"),
        "recordings": str(root / "recordings"),
        "locks": str(root / ".receiver-locks"),
        "config_root": str(Path.home() / ".config/tihulu-text-center"),
        "cache_root": str(Path.home() / ".cache/tihulu-text-center"),
        "model_policy": "external_paths_preserved_not_copied_moved_or_deleted",
    }


def support(platform_name=None, version=None, lookup=None):
    system = platform_name or platform.system()
    py = version or sys.version_info[:2]
    lookup = lookup or shutil.which
    reasons = []
    if tuple(py) < (3, 11):
        reasons.append("Python 3.11 or newer required")
    if system == "Windows":
        reasons.append("UNSUPPORTED: canonical Text backend imports Unix fcntl unconditionally")
    elif system not in ("Linux", "Darwin"):
        reasons.append("UNSUPPORTED: no Text runtime acceptance on this OS")
    if system == "Darwin":
        reasons.append("PREVIEW ONLY: macOS native runtime and tuner support not installed/tested")
    if system == "Linux":
        reasons.append("SOURCE-SMOKE ONLY: Linux x64 CI; Pi ARM64 and live tuners not verified")
    tools = {x: bool(lookup(x)) for x in
             ("rtl_fm", "redsea", "rtl_power", "ffmpeg", "whisper-cli", "welle-cli")}
    return {"application_id": APP_ID, "platform": system, "python": ".".join(map(str, py)),
            "core_launch_candidate": system in ("Linux", "Darwin") and tuple(py) >= (3, 11),
            "installed_platform_verified": False,
            "native_dvb_tuning": False, "journaline_decoder": False,
            "optional_tools_present_not_live_verified": tools,
            "notes": reasons}


LAUNCHER = '''#!/usr/bin/env python3
"""Text-owned foreground CLI launcher; no autostart, cross-app or hardware work."""
import json
import os
from pathlib import Path
import runpy
import sys
root = Path(__file__).resolve().parents[1]
state = json.loads((root / "state" / "active.json").read_text(encoding="utf-8"))
ident = state["bundle_sha256"]
if state["application_id"] != "tihulu.text-center" or len(ident) != 64 or any(c not in "0123456789abcdef" for c in ident):
    raise SystemExit("Invalid Text-only installation state")
release = root / "releases" / ident
if not (release / "textcenter" / "__main__.py").is_file():
    raise SystemExit("Text-only release missing")
os.environ.setdefault("TIHULU_TEXT_DB", state["database"])
sys.path.insert(0, str(release))
sys.argv = ["textcenter"] + sys.argv[1:]
runpy.run_module("textcenter", run_name="__main__")
'''


def _active(prefix):
    path = prefix / "state" / "active.json"
    if path.is_symlink():
        raise InstallerError("Symlinked Text activation state")
    if not path.exists():
        return None
    state = json.loads(path.read_text(encoding="utf-8"))
    if (state.get("application_id") != APP_ID
            or not HEX64.fullmatch(state.get("bundle_sha256", ""))):
        raise InstallerError("Corrupt Text active-version pointer")
    previous = state.get("previous_bundle_sha256")
    if previous is not None and not HEX64.fullmatch(previous):
        raise InstallerError("Corrupt Text rollback pointer")
    return state


def _owned_prefix(prefix):
    marker = prefix / "owner.json"
    if marker.is_symlink() or not marker.is_file():
        raise InstallerError("Existing directory has no Text-owned marker")
    if json.loads(marker.read_text(encoding="utf-8")) != {
        "application_id": APP_ID, "format": 1}:
        raise InstallerError("Installation directory is owned by another application")
    for name in ("state", "releases", "bin"):
        if (prefix / name).is_symlink():
            raise InstallerError("Symlinked Text installation directory")


@contextmanager
def _lock(prefix):
    # Only loaded on supported Unix; never touches readsb or receiver locks.
    import fcntl
    path = prefix / "state" / ".installer.lock"
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as e:
            raise InstallerError("Another Text installer owns the update lock") from e
        yield
    finally:
        os.close(fd)


def _atomic_json(path, data):
    if path.is_symlink():
        raise InstallerError("Refusing symlink state file")
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8",
                                         dir=path.parent, prefix=".state-",
                                         delete=False) as out:
            tmp = Path(out.name)
            os.chmod(tmp, 0o600)
            out.write(json.dumps(data, sort_keys=True, indent=2) + "\n")
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp, path)
    finally:
        if tmp is not None and tmp.exists():
            tmp.unlink()


def _verify_release(prefix, bundle_id):
    if not HEX64.fullmatch(bundle_id):
        raise InstallerError("Invalid release id")
    folder = prefix / "releases" / bundle_id
    if folder.is_symlink() or not folder.is_dir():
        raise InstallerError("Saved Text release missing or symlinked")
    raw_path = folder / BUNDLE_NAME
    if raw_path.is_symlink() or not raw_path.is_file():
        raise InstallerError("Text release archive missing or symlinked")
    raw = raw_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != bundle_id:
        raise InstallerError("Text release archive hash mismatch")
    manifest, contents = inspect_bundle(raw)  # old versions validate against their own pins
    if (folder / "manifest.json").read_bytes() != _manifest_bytes(manifest):
        raise InstallerError("Installed Text release manifest modified")
    for name, expected in contents.items():
        if _strict_file(folder, name) != expected:
            raise InstallerError("Installed Text release contents modified: " + name)
    return manifest


def _bootstrap(prefix):
    prefix.mkdir(mode=0o700, parents=True, exist_ok=False)
    for name in ("releases", "state", "bin"):
        (prefix / name).mkdir(mode=0o700)
    _atomic_json(prefix / "owner.json", {"application_id": APP_ID, "format": 1})


def _new_release(prefix, identifier, raw, manifest, contents):
    releases = prefix / "releases"
    destination = releases / identifier
    if destination.exists() or destination.is_symlink():
        _verify_release(prefix, identifier)
        return False
    temp = Path(tempfile.mkdtemp(prefix=".staging-", dir=releases))
    try:
        os.chmod(temp, 0o700)
        (temp / BUNDLE_NAME).write_bytes(raw)
        (temp / "manifest.json").write_bytes(_manifest_bytes(manifest))
        for name, data in contents.items():
            file = temp / name
            file.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            file.write_bytes(data)
            os.chmod(file, 0o600)
        _verify_staged(temp, identifier)
        temp.rename(destination)
        return True
    finally:
        if temp.exists():
            shutil.rmtree(temp)  # ONLY our freshly generated staging directory


def _verify_staged(folder, identifier):
    data = (folder / BUNDLE_NAME).read_bytes()
    if hashlib.sha256(data).hexdigest() != identifier:
        raise InstallerError("Staged Text bundle hash mismatch")
    manifest, contents = inspect_bundle(data)
    if (folder / "manifest.json").read_bytes() != _manifest_bytes(manifest):
        raise InstallerError("Staged Text manifest differs")
    for name, raw in contents.items():
        if _strict_file(folder, name) != raw:
            raise InstallerError("Staged Text source differs")


def deploy(archive, prefix, data_root=None, *, apply=False, pin=None, platform_name=None):
    pin = pin or pin_from_file()
    raw, identifier, manifest, contents = read_bundle(archive, pin)
    prefix = _safe_prefix(prefix)
    paths = _data_paths(data_root)
    status = support(platform_name=platform_name)
    if not status["core_launch_candidate"]:
        if apply:
            raise InstallerError("Unsupported core platform; no installation attempted: " + ", ".join(status["notes"]))
    result = {"action": "install", "mode": "APPLY" if apply else "DRY_RUN",
              "application_id": APP_ID, "source": manifest["canonical_commit"],
              "version": manifest["version"], "bundle_sha256": identifier,
              "prefix": str(prefix), "launcher": str(prefix / "bin" / "tihulu-text-center"),
              **paths, "platform": status, "automatic_service_start": False,
              "external_receiver_actions": False, "models_changed": False}
    if not apply:
        return result
    previous_umask = os.umask(0o077)
    try:
        if prefix.exists():
            _owned_prefix(prefix)
        else:
            _bootstrap(prefix)
        with _lock(prefix):
            current = _active(prefix)
            if current:
                _verify_release(prefix, current["bundle_sha256"])
                # Never silently redirect a configured data root during upgrade.
                if current["database"] != paths["database"]:
                    raise InstallerError("Existing Text database path differs; no silent migration")
            _new_release(prefix, identifier, raw, manifest, contents)
            launcher = prefix / "bin" / "tihulu-text-center"
            if launcher.exists() or launcher.is_symlink():
                if launcher.is_symlink() or launcher.read_text(encoding="utf-8") != LAUNCHER:
                    raise InstallerError("Existing Text launcher differs; refusing overwrite")
            else:
                launcher.write_text(LAUNCHER, encoding="utf-8")
                launcher.chmod(0o700)
            if current and current["bundle_sha256"] == identifier:
                result["unchanged"] = True
                return result
            previous = current["bundle_sha256"] if current else None
            _atomic_json(prefix / "state" / "active.json", {
                "application_id": APP_ID, "bundle_sha256": identifier,
                "previous_bundle_sha256": previous, "database": paths["database"],
                "version": manifest["version"], "source": manifest["canonical_commit"],
            })
            result["previous_bundle_sha256"] = previous
            return result
    finally:
        os.umask(previous_umask)


def rollback(prefix, *, apply=False, platform_name=None):
    prefix = _safe_prefix(prefix)
    status = support(platform_name=platform_name)
    if not prefix.is_dir():
        raise InstallerError("No Text installation exists")
    _owned_prefix(prefix)
    current = _active(prefix)
    if current is None or current["previous_bundle_sha256"] is None:
        raise InstallerError("No prior Text source bundle for rollback")
    prior = current["previous_bundle_sha256"]
    old_manifest = _verify_release(prefix, prior)
    _verify_release(prefix, current["bundle_sha256"])
    result = {"action": "rollback", "mode": "APPLY" if apply else "DRY_RUN",
              "from": current["bundle_sha256"], "to": prior,
              "restored_version": old_manifest["version"],
              "data_preserved": True, "models_untouched": True,
              "services_touched": False}
    if not apply:
        return result
    if not status["core_launch_candidate"]:
        raise InstallerError("Rollback activation unsupported on this platform")
    with _lock(prefix):
        latest = _active(prefix)
        if latest != current:
            raise InstallerError("Text active version changed during rollback")
        _verify_release(prefix, prior)
        new = dict(current)
        new.update(bundle_sha256=prior, previous_bundle_sha256=current["bundle_sha256"],
                   version=old_manifest["version"], source=old_manifest["canonical_commit"])
        _atomic_json(prefix / "state" / "active.json", new)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check", help="Read-only platform and optional binary dependency report")
    p = sub.add_parser("package", help="Build deterministic pinned Text-only source ZIP")
    p.add_argument("--source-root", type=Path, default=PIN_FILE.parents[1])
    p.add_argument("--output", type=Path, required=True)
    p = sub.add_parser("install", help="Dry-run by default; --apply creates only a Text-owned runtime")
    p.add_argument("--archive", type=Path, required=True)
    p.add_argument("--prefix", type=Path, default=Path.home() / ".local/share/tihulu-text-center/runtime")
    p.add_argument("--data-root", type=Path)
    p.add_argument("--apply", action="store_true")
    p = sub.add_parser("rollback", help="Dry-run by default; --apply switches only Text version pointer")
    p.add_argument("--prefix", type=Path, default=Path.home() / ".local/share/tihulu-text-center/runtime")
    p.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "check":
            result = support()
        elif args.command == "package":
            result = write_package(args.source_root, args.output, pin_from_file())
        elif args.command == "install":
            result = deploy(args.archive, args.prefix, args.data_root, apply=args.apply)
        else:
            result = rollback(args.prefix, apply=args.apply)
        _print(result)
        return 0
    except (InstallerError, OSError, json.JSONDecodeError, KeyError) as exc:
        print("Text-only installer refused: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
