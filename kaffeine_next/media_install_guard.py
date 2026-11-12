#!/usr/bin/env python3
"""Standalone Media installer ownership/rollback guard; stdlib, no host changes on preflight."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile

APP = "tihulu-media-center"
PACKAGE = "tihulu-media-center-ai"
H40 = re.compile(r"[0-9a-f]{40}\Z")
H64 = re.compile(r"[0-9a-f]{64}\Z")


class GuardError(RuntimeError):
    pass


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as inp:
        for piece in iter(lambda: inp.read(1024 * 1024), b""):
            h.update(piece)
    return h.hexdigest()


def parents_safe(path, home):
    path, home = Path(path).absolute(), Path(home).absolute()
    if not path.is_relative_to(home):
        raise GuardError("Media write outside HOME")
    parent = home
    for item in path.relative_to(home).parts[:-1]:
        parent = parent / item
        try:
            st = parent.lstat()
        except FileNotFoundError:
            continue
        if not stat.S_ISDIR(st.st_mode) or stat.S_ISLNK(st.st_mode):
            raise GuardError("Foreign/symlinked Media parent: " + str(parent))


def paths(home):
    base = Path(home) / ".local/share/tihulu-media-center/native"
    return dict(base=base, launch=Path(home)/".local/bin/tihulu-kaffeine",
                alias=Path(home)/".local/bin/tihulu-media-center",
                desktop=Path(home)/".local/share/applications/tihulu-media-center.desktop",
                launch_mark=base/".tihulu-owned-launcher",
                alias_mark=base/".tihulu-owned-alias",
                desktop_mark=base/".tihulu-owned-desktop",
                current=Path(home)/".local/opt/tihulu-media-center/current")


def _regular(path, home, marker):
    parents_safe(path, home)
    parents_safe(marker, home)
    if not path.exists() and not path.is_symlink():
        if marker.exists() or marker.is_symlink():
            raise GuardError("Stale Media marker: " + str(marker))
        return {"kind": "absent"}
    st = path.lstat()
    if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
        raise GuardError("Foreign Media file: " + str(path))
    if marker.is_symlink() or not marker.is_file() or marker.stat().st_size > 128:
        raise GuardError("Missing trusted per-file Media marker: " + str(path))
    expected = marker.read_text(encoding="ascii").strip()
    observed = sha(path)
    if not H64.fullmatch(expected) or expected != observed:
        raise GuardError("Media file modified or foreign: " + str(path))
    return {"kind": "file", "sha256": observed}


def _link(path, home, marker, exact):
    parents_safe(path, home)
    if not path.exists() and not path.is_symlink():
        if marker is not None and (marker.exists() or marker.is_symlink()):
            raise GuardError("Stale alias ownership marker")
        return {"kind": "absent"}
    if not path.is_symlink() or os.readlink(path) != exact:
        raise GuardError("Foreign regular file or symlink: " + str(path))
    if marker is not None:
        parents_safe(marker, home)
        if (marker.is_symlink() or not marker.is_file() or
                marker.stat().st_size > 128 or
                marker.read_text(encoding="ascii").strip() != exact):
            raise GuardError("Unowned Media alias")
    return {"kind": "link", "target": exact}


def owned(home):
    p = paths(home)
    release = p["current"]
    parents_safe(release, home)
    if release.exists() or release.is_symlink():
        if not release.is_symlink():
            raise GuardError("Foreign regular Media current link")
        target = Path(os.readlink(release))
        folder = Path(home)/".local/opt/tihulu-media-center/releases"
        marker = target / ".tihulu-media-owned-release"
        if not target.is_absolute() or target.parent != folder:
            raise GuardError("Unverified current Media release")
        parents_safe(marker, home)
        if marker.is_symlink() or not marker.is_file() or marker.stat().st_nlink != 1:
            raise GuardError("Foreign/symlinked current release marker")
        revision = marker.read_text(encoding="ascii").strip()
        if not H40.fullmatch(revision) or target.name != revision[:12]:
            raise GuardError("Incorrect Media release marker")
        current = {"kind": "link", "target": str(target)}
    else:
        current = {"kind": "absent"}
    return dict(launch=_regular(p["launch"], home, p["launch_mark"]),
                desktop=_regular(p["desktop"], home, p["desktop_mark"]),
                alias=_link(p["alias"], home, p["alias_mark"], "tihulu-kaffeine"),
                current=current)


def git_source(source, expected):
    source = Path(source).absolute()
    if not H40.fullmatch(expected) or source.is_symlink():
        raise GuardError("Clean pinned Git checkout and full SHA required")
    for part in ("tv_center/__main__.py", "kaffeine_next/patch_upstream.py",
                 "kaffeine_next/media_install_guard.py"):
        if not (source/part).is_file():
            raise GuardError("Incomplete standalone Media source")
    def git(*argv):
        result = subprocess.run(["git", "-C", str(source), *argv], capture_output=True,
                                text=True, timeout=20, check=False)
        if result.returncode:
            raise GuardError("Unable to verify source Git history")
        return result.stdout.strip()
    if Path(git("rev-parse", "--show-toplevel")).absolute() != source:
        raise GuardError("Source is not checkout root")
    if git("rev-parse", "--verify", "HEAD^{commit}") != expected:
        raise GuardError("Reviewed source SHA mismatch")
    if git("status", "--porcelain=v1", "--untracked-files=all",
           "--ignore-submodules=none"):
        raise GuardError("Dirty staged/unstaged/untracked source refused")


def package_version():
    response = subprocess.run(["dpkg-query", "-W", "-f=" + "$" + "{Version}",
                               PACKAGE], capture_output=True, text=True,
                              timeout=5, check=False)
    return response.stdout.strip() if response.returncode == 0 else ""


def previous_deb(home, own, version):
    if not version:
        return ""
    if own["current"]["kind"] != "link":
        raise GuardError("Previously installed companion is not Media-owned")
    target = Path(own["current"]["target"])
    deb = target / "companion.deb"
    receipt = target / ".tihulu-media-companion.sha256"
    for path in (deb, receipt):
        parents_safe(path, home)
        if path.is_symlink() or not path.is_file():
            raise GuardError("Previous Media companion backup missing")
    if receipt.read_text().strip() != sha(deb):
        raise GuardError("Previous Media package receipt mismatch")
    return str(deb)


def preflight(home, source, commit, ai=False, dab=False, analog=False):
    git_source(source, commit)
    original = owned(home)
    installed = package_version()
    old_pkg = previous_deb(home, original, installed)
    release = Path(home)/".local/opt/tihulu-media-center/releases"/commit[:12]
    parents_safe(release, home)
    if release.exists() or release.is_symlink():
        raise GuardError("Exact release already exists; do not overwrite")
    return {"owner": APP, "sha": commit, "dry_run": True, "source": str(source),
            "existing": original, "previous_package": installed,
            "previous_deb": old_pkg, "new_release": str(release),
            "new_companion_deb": str(release / "companion.deb"),
            "new_launcher": str(paths(home)["launch"]),
            "new_alias": str(paths(home)["alias"]),
            "new_desktop": str(paths(home)["desktop"]),
            "new_current_pointer": str(paths(home)["current"]),
            "companion_package_action": "reinstall exact local Media-only deb",
            "companion_rollback": ("reinstall verified previous owned deb" if old_pkg
                                   else "remove only newly installed Media-only deb"),
            "system_dependencies": [
                "git", "cmake", "g++", "make", "extra-cmake-modules",
                "qtbase5-dev", "libqt5x11extras5-dev", "libkf5coreaddons-dev",
                "libkf5dbusaddons-dev", "libkf5i18n-dev", "libkf5kio-dev",
                "libkf5solid-dev", "libkf5widgetsaddons-dev",
                "libkf5windowsystem-dev", "libkf5xmlgui-dev", "libvlc-dev",
                "libx11-dev", "libdvbv5-dev", "ffmpeg", "dvb-tools", "psmisc",
            ],
            "steps": ["inspect clean SHA-pinned Media checkout",
                      "verify every launcher/desktop/alias/current owner",
                      "APT build dependencies; no model unless --with-ai",
                      "compile pinned Kaffeine and optional radio backends",
                      "build independent Media companion .deb",
                      "snapshot previous owned Media files and package",
                      "install companion and publish atomically",
                      "retain snapshots for explicit rollback"],
            "optional": {"ai_download": ai, "dab": dab, "analog": analog}}


def record_path(home, commit):
    if not H40.fullmatch(commit):
        raise GuardError("Invalid release SHA")
    return paths(home)["base"] / "transactions" / commit / "journal.json"


def write_record(path, data):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                     prefix=".media-journal-", delete=False) as fh:
        staged = Path(fh.name)
        json.dump(data, fh, sort_keys=True)
        fh.flush()
        os.fsync(fh.fileno())
    os.chmod(staged, 0o600)
    os.replace(staged, path)


def read_record(home, commit):
    path = record_path(home, commit)
    parents_safe(path, home)
    if path.is_symlink() or not path.is_file():
        raise GuardError("Missing Media-owned rollback journal")
    data = json.loads(path.read_text())
    if data.get("sha") != commit or data.get("owner") != APP:
        raise GuardError("Foreign transaction journal")
    return data


def snapshot(home, source, commit):
    # A native build has already populated this versioned release prefix.
    # Recheck source and existing ownership without treating that new build
    # as a forbidden pre-existing release.
    git_source(source, commit)
    original = owned(home)
    installed = package_version()
    prior_deb = previous_deb(home, original, installed)
    release = Path(home)/".local/opt/tihulu-media-center/releases"/commit[:12]
    parents_safe(release, home)
    marker = release/".tihulu-media-owned-release"
    if (release.is_symlink() or marker.is_symlink() or not marker.is_file()
        or marker.read_text().strip() != commit):
        raise GuardError("Built Media release lacks verified source marker")
    plan = {"existing": original, "previous_deb": prior_deb}
    location = record_path(home, commit)
    parents_safe(location, home)
    if location.parent.exists() or location.parent.is_symlink():
        raise GuardError("Media transaction already exists")
    location.parent.mkdir(parents=True, mode=0o700)
    old = plan["existing"]
    p = paths(home)
    for key in ("launch", "desktop"):
        if old[key]["kind"] == "file":
            backup = location.parent / (key + ".old")
            shutil.copyfile(p[key], backup)
            if sha(backup) != old[key]["sha256"]:
                raise GuardError("Rollback backup hash mismatch")
    state = {"owner": APP, "sha": commit, "phase": "snapshot",
             "prior": old, "prior_deb": plan["previous_deb"],
             "new": {}}
    write_record(location, state)
    return state


def atomic_file(path, content, executable=False):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".media-install-",
                                     delete=False) as fh:
        staged = Path(fh.name)
        fh.write(content)
        fh.flush()
        os.fsync(fh.fileno())
    os.chmod(staged, 0o700 if executable else 0o600)
    os.replace(staged, path)


def atomic_link(path, target):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    staged = path.parent / (".media-link-" + str(os.getpid()))
    if staged.exists() or staged.is_symlink():
        raise GuardError("Media staging name occupied")
    os.symlink(str(target), staged)
    try:
        os.replace(staged, path)
    finally:
        if staged.is_symlink():
            staged.unlink()


def activate(home, commit, launcher, desktop, release, deb):
    state = read_record(home, commit)
    if state["phase"] != "snapshot" or owned(home) != state["prior"]:
        raise GuardError("Media files changed since snapshot")
    root = Path(home)/".local/opt/tihulu-media-center/releases"/commit[:12]
    if Path(release) != root or (root/".tihulu-media-owned-release").read_text().strip() != commit:
        raise GuardError("Native build ownership differs from reviewed SHA")
    sources = (Path(launcher), Path(desktop), Path(deb))
    if any(x.is_symlink() or not x.is_file() for x in sources):
        raise GuardError("Staged installer output is missing/untrusted")
    content = [x.read_bytes() for x in sources]
    new = {"launch": hashlib.sha256(content[0]).hexdigest(),
           "desktop": hashlib.sha256(content[1]).hexdigest(),
           "alias": "tihulu-kaffeine", "current": str(root),
           "package_sha256": hashlib.sha256(content[2]).hexdigest()}
    state["phase"], state["new"] = "activating", new
    write_record(record_path(home, commit), state)
    atomic_file(root/"companion.deb", content[2])
    atomic_file(root/".tihulu-media-companion.sha256",
                (new["package_sha256"] + "\n").encode())
    p = paths(home)
    for key, index in (("launch", 0), ("desktop", 1)):
        atomic_file(p[key], content[index], executable=(key == "launch"))
        atomic_file(p[key + "_mark"], (new[key] + "\n").encode())
    atomic_link(p["alias"], new["alias"])
    atomic_file(p["alias_mark"], b"tihulu-kaffeine\n")
    atomic_link(p["current"], str(root))
    state["phase"] = "active"
    write_record(record_path(home, commit), state)
    return state


def rollback_plan(home, commit):
    state = read_record(home, commit)
    if state["phase"] not in ("snapshot", "activating", "active"):
        raise GuardError("No active Media transaction to roll back")
    prior = state["prior_deb"]
    if prior and (Path(prior).is_symlink() or not Path(prior).is_file()):
        raise GuardError("Prior companion package backup unavailable")
    return {"package_action": "restore" if prior else "remove",
            "previous_deb": prior, "package": PACKAGE}


def rollback_files(home, commit):
    state = read_record(home, commit)
    rollback_plan(home, commit)
    p = paths(home)
    old, new = state["prior"], state["new"]
    for key in ("launch", "desktop"):
        path = p[key]
        parents_safe(path, home)
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise GuardError("Foreign file replaced " + key)
        current = sha(path) if path.is_file() else None
        if current not in (None, old[key].get("sha256"), new.get(key)):
            raise GuardError("User-modified file: refusing rollback")
    for key in ("alias", "current"):
        path = p[key]
        parents_safe(path, home)
        if path.exists() or path.is_symlink():
            if not path.is_symlink() or os.readlink(path) not in (
                    old[key].get("target"), new.get(key)):
                raise GuardError("Foreign symlink; refusing rollback")
    for key in ("launch", "desktop"):
        path = p[key]
        if old[key]["kind"] == "file":
            backup = record_path(home, commit).parent / (key + ".old")
            if sha(backup) != old[key]["sha256"]:
                raise GuardError("Backup changed; refusing rollback")
            atomic_file(path, backup.read_bytes(), executable=(key == "launch"))
            atomic_file(p[key + "_mark"], (old[key]["sha256"] + "\n").encode())
        elif path.is_file() and sha(path) == new.get(key):
            path.unlink()
            p[key + "_mark"].unlink(missing_ok=True)
    for key in ("alias", "current"):
        path = p[key]
        if old[key]["kind"] == "link":
            atomic_link(path, old[key]["target"])
            if key == "alias":
                atomic_file(p["alias_mark"], (old[key]["target"] + "\n").encode())
        elif path.is_symlink() and os.readlink(path) == new.get(key):
            path.unlink()
            if key == "alias":
                p["alias_mark"].unlink(missing_ok=True)
    state["phase"] = "rolled_back"
    write_record(record_path(home, commit), state)
    return {"rolled_back": True, "source_sha": commit}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("preflight", "dry-run", "snapshot",
                                           "activate", "rollback-plan", "rollback-files"))
    parser.add_argument("--source")
    parser.add_argument("--sha", required=True)
    parser.add_argument("--with-ai", action="store_true")
    parser.add_argument("--with-dab", action="store_true")
    parser.add_argument("--with-analog", action="store_true")
    parser.add_argument("--launcher")
    parser.add_argument("--desktop")
    parser.add_argument("--release")
    parser.add_argument("--companion")
    args = parser.parse_args(argv)
    home = Path.home()
    try:
        if args.action in ("preflight", "dry-run"):
            output = preflight(home, Path(args.source), args.sha,
                               args.with_ai, args.with_dab, args.with_analog)
        elif args.action == "snapshot":
            output = snapshot(home, Path(args.source), args.sha)
        elif args.action == "activate":
            output = activate(home, args.sha, args.launcher, args.desktop,
                              args.release, args.companion)
        elif args.action == "rollback-plan":
            output = rollback_plan(home, args.sha)
        else:
            output = rollback_files(home, args.sha)
    except (GuardError, OSError, ValueError) as exc:
        print("MEDIA_INSTALL_HOLD: " + str(exc), file=sys.stderr)
        return 2
    print(json.dumps(output, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
