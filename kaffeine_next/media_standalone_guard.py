#!/usr/bin/env python3
"""Fail-closed, per-user STAND Media install ledger. No APT, dpkg, legacy import or deletion.

This intentionally does NOT adopt the pre-QA05 "tihulu-media-center" installation.
All writes are under a new namespace; source, ownership and full release hashes
are checked again at activation and before any rollback mutation.
"""
from __future__ import annotations

import argparse
import contextlib
import fcntl
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

APP = "tihulu-media-standalone"
NAMES = ("launcher", "desktop", "cli", "icon")
LOCK_NAME = ".tihulu-media-standalone-transaction.lock"
SHA40 = re.compile(r"[0-9a-f]{40}\Z")


class Hold(RuntimeError):
    """A foreign/modified object requires manual resolution, never overwrite."""


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def safe_parent(path, home):
    home, path = Path(home).absolute(), Path(path).absolute()
    if path == home or not path.is_relative_to(home):
        raise Hold("Path escapes designated HOME")
    parent = home
    if home.is_symlink():
        raise Hold("Symlinked HOME refused")
    for part in path.relative_to(home).parts[:-1]:
        parent = parent / part
        if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
            raise Hold("Foreign/symlinked parent: " + str(parent))


def layout(home):
    home = Path(home).absolute()
    opt = home / ".local/opt" / APP
    state = home / ".local/state" / APP
    return {
        "root": opt,
        "releases": opt / "releases",
        "current": opt / "current",
        "state": state,
        "active": state / "active.json",
        "launcher": home / ".local/bin" / APP,
        "cli": home / ".local/bin" / (APP + "-cli"),
        "desktop": home / ".local/share/applications" / (APP + ".desktop"),
        "icon": home / ".local/share/icons/hicolor/scalable/apps" / (APP + ".svg"),
    }


def verify_source(source, rev):
    if not SHA40.fullmatch(rev):
        raise Hold("Full reviewed 40-character source SHA required")
    source = Path(source).absolute()
    if source.is_symlink():
        raise Hold("Symlinked source checkout refused")
    for f in ("kaffeine_next/patch_upstream.py", "kaffeine_next/media_standalone_guard.py",
              "kaffeine_next/assets/tihulu-media-center.svg", "tv_center/__main__.py"):
        if not (source / f).is_file() or (source / f).is_symlink():
            raise Hold("Incomplete or symlinked source: " + f)
    def git(*args):
        p = subprocess.run(("git", "-C", str(source), *args), capture_output=True,
                           text=True, timeout=25, check=False)
        if p.returncode:
            raise Hold("Git source verification failed: " + " ".join(args))
        return p.stdout.strip()
    if Path(git("rev-parse", "--show-toplevel")).absolute() != source:
        raise Hold("Not a source checkout root")
    if git("rev-parse", "--verify", "HEAD^{commit}") != rev:
        raise Hold("Reviewed source SHA mismatch")
    if git("status", "--porcelain=v1", "--untracked-files=all",
           "--ignore-submodules=none"):
        raise Hold("Dirty/unreviewed source refused")


def items(root):
    """Complete content and mode manifest; never follow a symlink."""
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise Hold("Missing/linked release directory")
    output = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        st = path.lstat()
        if stat.S_ISLNK(st.st_mode):
            target = os.readlink(path)
            if target.startswith("/") or not (path.parent / target).resolve().is_relative_to(root.resolve()):
                raise Hold("Escaping release symlink: " + rel)
            output[rel] = {"type": "link", "target": target}
        elif stat.S_ISREG(st.st_mode) and st.st_nlink == 1:
            output[rel] = {"type": "file", "sha256": digest(path),
                           "executable": bool(st.st_mode & 0o111)}
        elif stat.S_ISDIR(st.st_mode) and not stat.S_ISLNK(st.st_mode):
            output[rel] = {"type": "dir"}
        else:
            raise Hold("Special/hardlinked release object: " + rel)
    return output


def read_json(path, home):
    safe_parent(path, home)
    if path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1:
        raise Hold("Missing/foreign Media transaction receipt: " + str(path))
    if path.stat().st_size > 3000000:
        raise Hold("Oversized ownership receipt")
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_json(path, home, data, *, no_replace=False):
    safe_parent(path, home)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    payload = json.dumps(data, sort_keys=True, indent=2).encode() + b"\n"
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".stand-journal-",
                                     delete=False) as f:
        tmp = Path(f.name)
        f.write(payload)
        f.flush()
        os.fsync(f.fileno())
    os.chmod(tmp, 0o600)
    try:
        if no_replace:
            # Atomic no-clobber publication, including newly arrived symlinks.
            os.link(tmp, path, follow_symlinks=False)
        else:
            os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def abs_destination(home, key):
    return layout(home)[key]


def public_receipt(home, key):
    path = abs_destination(home, key)
    safe_parent(path, home)
    if not path.exists() and not path.is_symlink():
        return {"type": "absent"}
    st = path.lstat()
    if stat.S_ISLNK(st.st_mode):
        return {"type": "link", "target": os.readlink(path)}
    if stat.S_ISREG(st.st_mode) and st.st_nlink == 1:
        return {"type": "file", "sha256": digest(path),
                "executable": bool(st.st_mode & 0o111)}
    raise Hold("Foreign managed path: " + str(path))


def release_path(home, rev):
    if not SHA40.fullmatch(rev):
        raise Hold("Invalid release SHA")
    return layout(home)["releases"] / rev[:12]


@contextlib.contextmanager
def owner_transaction_lock(home):
    """Cooperative full-transaction serial lock; hostile same-UID attacks HOLD."""
    home = Path(home).absolute()
    parent = home / ".local/opt"
    lock = parent / LOCK_NAME
    safe_parent(lock, home)
    if os.geteuid() == 0:
        raise Hold("Refusing root transaction")
    parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if (parent.is_symlink() or parent.stat().st_uid != os.geteuid()
            or parent.stat().st_mode & 0o022):
        raise Hold("Insecure owner lock parent")
    parentfd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    borrowed = os.environ.get("TIHULU_MEDIA_TRANSACTION_FD")
    fd = -1
    try:
        if borrowed:
            try:
                fd = int(borrowed)
                if fd < 3:
                    raise ValueError("bad fd")
                pinned = os.fstat(fd)
            except (ValueError, OSError):
                raise Hold("Missing inherited transaction lock descriptor")
        else:
            fd = os.open(LOCK_NAME, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW,
                         0o600, dir_fd=parentfd)
            pinned = os.fstat(fd)
        visible = os.stat(LOCK_NAME, dir_fd=parentfd, follow_symlinks=False)
        parent_st = os.fstat(parentfd)
        current_parent = parent.lstat()
        if ((parent_st.st_dev, parent_st.st_ino) !=
                (current_parent.st_dev, current_parent.st_ino)
                or (pinned.st_dev, pinned.st_ino) != (visible.st_dev, visible.st_ino)
                or pinned.st_uid != os.geteuid()
                or not stat.S_ISREG(pinned.st_mode) or pinned.st_nlink != 1
                or stat.S_IMODE(pinned.st_mode) != 0o600):
            raise Hold("Unsafe or replaced transaction lock")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Hold("Competing standalone transaction is active")
        yield fd
    finally:
        if not borrowed and fd >= 0:
            os.close(fd)
        os.close(parentfd)


def historical_state(home):
    """Read-only historical ownership check; never adopt unverified state.

    A rolled-back first install can retain a genuine release and transaction
    without active.json. Every known path and hash must be accounted for.
    This is an integrity gate, NOT cryptographic same-UID authentication.
    """
    p = layout(home)
    root, state = p["root"], p["state"]
    if not any(x.exists() or x.is_symlink() for x in (root, state)):
        return {}
    if state.is_symlink() or not state.is_dir():
        raise Hold("Unowned standalone install/state directory")
    for x in (state,):
        st = x.lstat()
        if st.st_uid != os.geteuid() or st.st_mode & 0o022:
            raise Hold("Foreign historical state ownership or permissions")
    if root.exists() or root.is_symlink():
        st = root.lstat()
        if (not stat.S_ISDIR(st.st_mode) or st.st_uid != os.geteuid()
                or st.st_mode & 0o022):
            raise Hold("Unowned standalone install/state directory")
        if {x.name for x in root.iterdir()} - {"releases"}:
            raise Hold("Unexpected standalone root entries after rollback")
    if {x.name for x in state.iterdir()} != {"transactions"}:
        raise Hold("Unowned standalone state/history directory")
    txns = state / "transactions"
    st = txns.lstat()
    if (not stat.S_ISDIR(st.st_mode) or st.st_uid != os.geteuid()
            or st.st_mode & 0o022):
        raise Hold("Untrusted historical journal directory")
    known = {}
    for folder in txns.iterdir():
        if (not SHA40.fullmatch(folder.name) or folder.is_symlink() or
                not folder.is_dir() or
                {x.name for x in folder.iterdir()} != {"journal.json"}):
            raise Hold("Unknown/unsealed historical transaction directory")
        record = journal(home, folder.name)
        pending = record.get("pending")
        expected_pending = str(p["releases"] / (".pending-" + folder.name[:12]))
        if (record.get("phase") != "rolled_back" or
                pending not in ("", None, expected_pending) or
                pending == expected_pending and (Path(pending).exists() or Path(pending).is_symlink())):
            raise Hold("Incomplete or foreign historical transaction")
        new_receipt = record.get("new")
        if (not isinstance(new_receipt, dict) or
                new_receipt.get("owner") != APP or
                new_receipt.get("sha") != folder.name or
                not isinstance(new_receipt.get("release"), dict) or
                new_receipt.get("public", {}).get("current") !=
                {"type": "link", "target": str(release_path(home, folder.name))}):
            raise Hold("Historical release identity mismatch")
        for key in NAMES:
            if new_receipt["public"].get(key) != new_receipt["release"].get("setup/" + key):
                raise Hold("Historical launcher/receipt mismatch")
        if folder.name[:12] in known:
            raise Hold("Ambiguous historical release SHA prefix")
        known[folder.name[:12]] = new_receipt
    if not known:
        raise Hold("Missing installer-owned historical journal")
    releases = p["releases"]
    if releases.exists() or releases.is_symlink():
        if releases.is_symlink() or not releases.is_dir():
            raise Hold("Replaced historical releases root")
        for entry in releases.iterdir():
            if entry.name not in known or entry.is_symlink() or not entry.is_dir():
                raise Hold("Unknown previous release: " + entry.name)
            if items(entry) != known[entry.name]["release"]:
                raise Hold("Historical native release hash mismatch")
    for key in (*NAMES, "current"):
        if public_receipt(home, key)["type"] != "absent":
            raise Hold("Unowned standalone destination after rollback: " + key)
    return known


def journal_for_reentry(home, rev):
    path = journal_path(home, rev)
    if not (path.exists() or path.is_symlink()):
        return None
    record = journal(home, rev)
    if record.get("phase") != "rolled_back":
        return None
    receipt = record.get("new")
    expected_pending = str(layout(home)["releases"] / (".pending-" + rev[:12]))
    pending = record.get("pending")
    if (not isinstance(receipt, dict) or receipt.get("owner") != APP or
            receipt.get("sha") != rev or
            receipt.get("public", {}).get("current") !=
            {"type": "link", "target": str(release_path(home, rev))} or
            pending not in ("", None, expected_pending)):
        raise Hold("Untrusted historical journal")
    if pending == expected_pending and (Path(pending).exists() or Path(pending).is_symlink()):
        raise Hold("Unresolved pending historical stage")
    return record


def current_state(home):
    p = layout(home)
    if not p["active"].exists() and not p["active"].is_symlink():
        return None
    r = read_json(p["active"], home)
    if r.get("owner") != APP or not SHA40.fullmatch(r.get("sha", "")):
        raise Hold("Untrusted active owner ledger")
    expected = r.get("public", {})
    for key in (*NAMES, "current"):
        if public_receipt(home, key) != expected.get(key):
            raise Hold("Media-managed destination changed: " + key)
    root = release_path(home, r["sha"])
    safe_parent(root, home)
    if items(root) != r.get("release"):
        raise Hold("Owned native release changed: " + str(root))
    return r


def preflight(home, source, rev, **optional):
    verify_source(source, rev)
    p = layout(home)
    for key in (*NAMES, "current", "active", "root", "state", "releases"):
        safe_parent(p[key], home)
    active = current_state(home)
    history = historical_state(home) if active is None else {}
    if active is None:
        for key in (*NAMES, "current"):
            if public_receipt(home, key)["type"] != "absent":
                raise Hold("Existing unowned/legacy destination: " + str(p[key]))
    dest = release_path(home, rev)
    already = bool(active and active["sha"] == rev)
    journal_file = journal_path(home, rev)
    safe_parent(journal_file, home)
    reenter = False
    if journal_file.exists() or journal_file.is_symlink():
        old_record = journal_for_reentry(home, rev)
        reenter = old_record is not None
        if not reenter and not already:
            raise Hold("Incomplete owned transaction: run --recover or --rollback")
    if dest.exists() or dest.is_symlink():
        if not (already or reenter):
            raise Hold("Release path already occupied: " + str(dest))
        if reenter and items(dest) != old_record["new"]["release"]:
            raise Hold("Historical native release no longer verifies")
    if active is None and dest.exists() and rev[:12] not in history:
        raise Hold("Previously installed release is not historically verified")
    return {
        "owner": APP, "source_sha": rev, "dry_run": True,
        "already_active": already, "historical_reentry": reenter,
        "new_release": str(dest),
        "managed": {key: str(p[key]) for key in (*NAMES, "current", "active")},
        "system_package_operations": [],
        "legacy_import": False, "automatic_model_install": False,
        "optional": optional,
        "steps": ["verify exact clean source SHA", "inspect every destination and active hashes",
                  "check user-provided preinstalled build dependencies (no APT/dpkg writes)",
                  "build into private temporary staging outside existing Media paths",
                  "seal complete content/hash manifest and prevalidate rollback",
                  "publish owned files and release, no legacy settings import"],
    }


def journal_path(home, rev):
    return layout(home)["state"] / "transactions" / rev / "journal.json"


def journal(home, rev):
    r = read_json(journal_path(home, rev), home)
    if r.get("owner") != APP or r.get("sha") != rev:
        raise Hold("Foreign transaction journal")
    return r


def write_journal(home, rev, record, *, reuse=False):
    # First durable receipt is no-clobber; all later writes update only this
    # transaction's known journal. Never overwrite an unexpectedly new file.
    atomic_json(journal_path(home, rev), home, record,
                no_replace=(record["phase"] == "prepared" and
                            not record.get("pending") and not reuse))


def proposed(home, rev, stage):
    root = release_path(home, rev)
    manifest = items(stage)
    for f in ("bin/kaffeine", "bin/tihulu-media-standalone",
              "share/tv_center/__main__.py",
              "aux/install_welle.sh", "aux/dvb_diagnostics.sh",
              "setup/launcher", "setup/desktop", "setup/cli", "setup/icon"):
        if f not in manifest:
            raise Hold("Missing staged app artifact: " + f)
    r = {"owner": APP, "sha": rev, "release": manifest,
         "public": {"current": {"type": "link", "target": str(root)}}}
    for key in NAMES:
        staged = Path(stage) / "setup" / key
        x = manifest["setup/" + key]
        if x["type"] != "file":
            raise Hold("Invalid public artifact: " + key)
        r["public"][key] = dict(x)
    return r


def verify_destination(path, expected, home):
    """Verify the *previously owned* version immediately before publishing."""
    safe_parent(path, home)
    expected = expected or {"type": "absent"}
    if expected["type"] == "absent":
        if path.exists() or path.is_symlink():
            raise Hold("Foreign destination appeared during transaction: " + str(path))
        return
    if expected["type"] == "file":
        if (path.is_symlink() or not path.is_file()
                or path.stat().st_nlink != 1
                or digest(path) != expected["sha256"]
                or bool(path.stat().st_mode & 0o111) != expected["executable"]):
            raise Hold("Previously owned file changed during transaction: " + str(path))
        return
    if expected["type"] == "link":
        if not path.is_symlink() or os.readlink(path) != expected["target"]:
            raise Hold("Previously owned symlink changed during transaction: " + str(path))
        return
    raise Hold("Unsupported managed destination type")


def write_file(path, payload, executable, home, expected=None):
    safe_parent(path, home)
    path.parent.mkdir(parents=True, exist_ok=True)
    verify_destination(path, expected, home)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".stand-owned-",
                                     delete=False) as out:
        temp = Path(out.name)
        out.write(payload)
        out.flush()
        os.fsync(out.fileno())
    os.chmod(temp, 0o700 if executable else 0o600)
    try:
        if (expected or {"type": "absent"})["type"] == "absent":
            # No-replace link: a new foreign file or symlink cannot be clobbered
            # even if it appears after preflight but before final publication.
            os.link(temp, path, follow_symlinks=False)
        else:
            verify_destination(path, expected, home)
            os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def write_link(path, target, home, expected=None):
    safe_parent(path, home)
    path.parent.mkdir(parents=True, exist_ok=True)
    verify_destination(path, expected, home)
    if (expected or {"type": "absent"})["type"] == "absent":
        os.symlink(target, path)  # O_EXCL-like: never replace a new foreign path
        return
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".stand-link-",
                                     delete=False) as out:
        temp = Path(out.name)
    temp.unlink()
    try:
        os.symlink(target, temp)
        verify_destination(path, expected, home)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def activate(home, source, rev, stage):
    with owner_transaction_lock(home):
        return _activate_locked(home, source, rev, stage)


def _activate_locked(home, source, rev, stage):
    plan = preflight(home, source, rev)
    if plan["already_active"]:
        return {"owner": APP, "sha": rev, "phase": "active", "repeat": True}
    stage = Path(stage).absolute()
    if stage.is_symlink() or not stage.is_dir():
        raise Hold("Refusing invalid build staging")
    next_state = proposed(home, rev, stage)
    old = current_state(home)
    previous_record = journal_for_reentry(home, rev) if plan["historical_reentry"] else None
    new_release = release_path(home, rev)
    reuse_release = bool(previous_record and new_release.is_dir())
    if reuse_release:
        # Reuse original hash-verified native bits. Same-source rebuilt native
        # binaries are not assumed reproducible or safe to replace.
        if items(new_release) != previous_record["new"]["release"]:
            raise Hold("Historical release changed before reactivation")
        next_state = previous_record["new"]
    r = {"owner": APP, "sha": rev, "phase": "prepared",
         "prior": old, "new": next_state, "pending": "", "pending_identity": None}
    if previous_record:
        write_journal(home, rev, r, reuse=True)
    else:
        write_journal(home, rev, r)
    p = layout(home)
    pending = p["releases"] / (".pending-" + rev[:12])
    safe_parent(pending, home)
    if pending.exists() or pending.is_symlink():
        raise Hold("Pending release path occupied")
    p["releases"].mkdir(parents=True, exist_ok=True, mode=0o700)
    # Own the exact staging inode BEFORE recursive copy. If killed between
    # mkdir and the durable identity receipt, recovery deliberately HOLDS.
    os.mkdir(pending, 0o700)
    st = pending.lstat()
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.geteuid():
        raise Hold("New pending directory is not an owned inode")
    r["pending"] = str(pending)
    r["pending_identity"] = {"dev": st.st_dev, "ino": st.st_ino, "uid": st.st_uid}
    write_journal(home, rev, r)
    try:
        if not reuse_release:
            shutil.copytree(stage, pending, symlinks=True, dirs_exist_ok=True)
            if items(pending) != next_state["release"]:
                raise Hold("Staged release altered during copy")
        r["phase"] = "activating"
        write_journal(home, rev, r)
        if reuse_release:
            if items(new_release) != next_state["release"]:
                raise Hold("Previously owned release modified before activation")
        else:
            if new_release.exists() or new_release.is_symlink():
                raise Hold("Foreign release appeared after preflight")
            pending.rename(new_release)
        for key in NAMES:
            src = new_release / "setup" / key
            expected = old["public"][key] if old else None
            write_file(p[key], src.read_bytes(),
                       next_state["public"][key]["executable"], home, expected)
        write_link(p["current"], str(new_release), home,
                   old["public"]["current"] if old else None)
        if old and read_json(p["active"], home) != old:
            raise Hold("Prior active journal changed before publication")
        atomic_json(p["active"], home, next_state, no_replace=(old is None))
        r["phase"] = "active"
        write_journal(home, rev, r)
        return {"owner": APP, "sha": rev, "phase": "active", "repeat": False}
    except Exception:
        # Do not delete unknown user content. Journal supports validated recovery.
        raise


def _pinned_pending_parent(home):
    """Pin every canonical owner path before even considering scratch deletion.

    This remains a same-owner cooperative boundary, not an authentication
    mechanism against a malicious process already running with our UID.
    """
    home = Path(home).absolute()
    parent = home
    for element in (".local", "opt", APP, "releases"):
        if element == "opt":
            # the opt dir is beneath .local (the layout's fixed location)
            pass
        parent = parent / element
        st = parent.lstat()
        if (not stat.S_ISDIR(st.st_mode) or st.st_uid != os.geteuid()
                or st.st_mode & 0o022):
            raise Hold("Unsafe owner staging ancestor: " + str(parent))
    return os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)


def _validated_pending(home, rev, record):
    """Return (canonical path, pinned-parent fd, inode receipt) or None.

    Never trust the journal's pending string as a filesystem operation target.
    A missing identity from older journals cannot authorize *any* deletion.
    """
    raw = record.get("pending")
    marker = record.get("pending_identity")
    if raw in ("", None):
        if marker is not None:
            raise Hold("Pending identity without a staging path")
        return None
    if not isinstance(raw, str) or not SHA40.fullmatch(rev):
        raise Hold("Invalid pending transaction path")
    expected = layout(home)["releases"] / (".pending-" + rev[:12])
    if raw != str(expected):
        raise Hold("Noncanonical or foreign journal pending path")
    next_receipt = record.get("new")
    if (record.get("owner") != APP or record.get("sha") != rev
            or not isinstance(next_receipt, dict)
            or next_receipt.get("owner") != APP
            or next_receipt.get("sha") != rev
            or not isinstance(next_receipt.get("release"), dict)
            or next_receipt.get("public", {}).get("current") !=
            {"type": "link", "target": str(release_path(home, rev))}):
        raise Hold("Pending does not belong to reviewed release receipt")
    if (not isinstance(marker, dict) or set(marker) != {"dev", "ino", "uid"}
            or any(not isinstance(marker[x], int) or isinstance(marker[x], bool)
                   or marker[x] < 0 for x in marker)
            or marker["uid"] != os.geteuid()):
        raise Hold("Missing verified installer-created pending inode receipt")
    fd = _pinned_pending_parent(home)
    try:
        # stat with NOFOLLOW under the pinned releases directory; reject a
        # symlink even if is_dir() might otherwise follow it.
        try:
            st = os.stat(expected.name, dir_fd=fd, follow_symlinks=False)
        except FileNotFoundError:
            st = None
        if st is None:
            # A successfully renamed pending tree has the SAME inode under
            # the owned version directory. It needs no recursive deletion.
            release = release_path(home, rev)
            safe_parent(release, home)
            if not release.is_symlink() and release.is_dir():
                completed = release.lstat()
                if (completed.st_dev == marker["dev"]
                        and completed.st_ino == marker["ino"]
                        and completed.st_uid == marker["uid"]
                        and stat.S_ISDIR(completed.st_mode)
                        and items(release) == next_receipt["release"]):
                    return None
            raise Hold("Owned pending inode vanished without verified publication")
        if (not stat.S_ISDIR(st.st_mode) or st.st_uid != marker["uid"]
                or st.st_dev != marker["dev"] or st.st_ino != marker["ino"]
                or st.st_mode & 0o022):
            raise Hold("Pending staging inode replaced or not owned")
        # The directory may contain only whole/partial expected release
        # entries, never unrecognized files or special nodes.
        partial = items(expected)
        if any(next_receipt["release"].get(k) != v for k, v in partial.items()):
            raise Hold("Pending staging contains foreign or changed bytes")
        return expected, fd, marker
    except Exception:
        os.close(fd)
        raise


def validate_rollback(home, rev):
    r = journal(home, rev)
    if r["phase"] == "rolled_back":
        if current_state(home) is None:
            historical_state(home)
        return {"owner": APP, "sha": rev, "phase": "rolled_back", "repeat": True}
    if r["phase"] not in ("prepared", "activating", "active"):
        raise Hold("Transaction state requires manual inspection")
    before, after = r["prior"], r["new"]
    for key in (*NAMES, "current"):
        observed = public_receipt(home, key)
        previous = before["public"][key] if before else {"type": "absent"}
        if observed not in (previous, after["public"][key]):
            raise Hold("User/foreign change before rollback: " + key)
    active_path = layout(home)["active"]
    if active_path.exists() or active_path.is_symlink():
        current = read_json(active_path, home)
        if current not in (after, before):
            raise Hold("Active state edited after install")
    elif before:
        raise Hold("Previous owner receipt missing")
    if before and items(release_path(home, before["sha"])) != before["release"]:
        raise Hold("Prior owned release no longer verifies")
    newroot = release_path(home, rev)
    if newroot.exists() or newroot.is_symlink():
        if items(newroot) != after["release"]:
            raise Hold("New release modified; refusing rollback")
    # This validates the path *and* exact owner inode even if the journal
    # is syntactically valid and a foreign directory contains matching bytes.
    pending_proof = _validated_pending(home, rev, r)
    if pending_proof:
        os.close(pending_proof[1])
    return {"owner": APP, "sha": rev, "phase": r["phase"],
            "package_action": "none", "prevalidated": True}


def rollback(home, rev):
    with owner_transaction_lock(home):
        return _rollback_locked(home, rev)


def _rollback_locked(home, rev):
    plan = validate_rollback(home, rev)  # ALL paths before FIRST write
    if plan["phase"] == "rolled_back":
        return plan
    r = journal(home, rev)
    before, after = r["prior"], r["new"]
    p = layout(home)
    for key in NAMES:
        previous = before["public"][key] if before else {"type": "absent"}
        path = p[key]
        if previous["type"] == "absent":
            if path.is_file() and public_receipt(home, key) == after["public"][key]:
                path.unlink()
        else:
            src = release_path(home, before["sha"]) / "setup" / key
            write_file(path, src.read_bytes(), previous["executable"], home,
                       public_receipt(home, key))
    if before:
        write_link(p["current"], str(release_path(home, before["sha"])), home,
                   public_receipt(home, "current"))
        atomic_json(p["active"], home, before)
    else:
        if public_receipt(home, "current") == after["public"]["current"]:
            p["current"].unlink()
        p["active"].unlink(missing_ok=True)
    # A journal string is NEVER sufficient deletion authority. Revalidate
    # the owned staging inode after all public writes and unlink by name
    # relative to the pinned releases directory (fd-safe rmtree on Linux).
    proof = _validated_pending(home, rev, r)
    if proof is not None:
        pending, parent_fd, identity = proof
        try:
            st = os.stat(pending.name, dir_fd=parent_fd, follow_symlinks=False)
            if (not stat.S_ISDIR(st.st_mode) or
                    st.st_dev != identity["dev"] or
                    st.st_ino != identity["ino"] or
                    st.st_uid != identity["uid"] or st.st_mode & 0o022):
                raise Hold("Pending inode changed before scratch removal")
            if not shutil.rmtree.avoids_symlink_attacks:
                raise Hold("FD-safe recursive removal not available")
            shutil.rmtree(pending.name, dir_fd=parent_fd)
        finally:
            os.close(parent_fd)
    r["phase"] = "rolled_back"
    write_journal(home, rev, r)
    return {"owner": APP, "sha": rev, "phase": "rolled_back", "package_action": "none"}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("preflight", "dry-run", "activate",
                                            "rollback-plan", "rollback", "recover",
                                            "guarded-script", "verify-lock"))
    parser.add_argument("--sha", required=True)
    parser.add_argument("--source")
    parser.add_argument("--artifact")
    parser.add_argument("--script")
    parser.add_argument("--with-dab", action="store_true")
    parser.add_argument("--with-ai", action="store_true")
    args, trailing = parser.parse_known_args(argv)
    if trailing and args.command != "guarded-script":
        parser.error("Unexpected command arguments")
    try:
        home = Path.home()
        if args.command == "verify-lock":
            with owner_transaction_lock(home):
                value = {"owner": APP, "lock_valid": True}
        elif args.command == "guarded-script":
            source = Path(args.source).absolute()
            script = Path(args.script).absolute()
            if script != source / "kaffeine_next/media_standalone_install.sh" or script.is_symlink():
                raise Hold("Refusing arbitrary installer child script")
            verify_source(source, args.sha)
            with owner_transaction_lock(home) as fd:
                env = dict(os.environ)
                env["TIHULU_MEDIA_TRANSACTION_FD"] = str(fd)
                child_args = trailing[1:] if trailing and trailing[0] == "--" else trailing
                return subprocess.run(
                    ["/bin/bash", str(script), *child_args], env=env,
                    pass_fds=(fd,), check=False).returncode
        elif args.command in ("preflight", "dry-run"):
            value = preflight(home, args.source, args.sha, ai=args.with_ai, dab=args.with_dab)
        elif args.command == "activate":
            value = activate(home, args.source, args.sha, args.artifact)
        elif args.command == "rollback-plan":
            value = validate_rollback(home, args.sha)
        else:
            value = rollback(home, args.sha)
    except (Hold, ValueError, OSError, subprocess.SubprocessError, KeyError, TypeError) as exc:
        print("MEDIA_STANDALONE_HOLD: " + str(exc), file=sys.stderr)
        return 2
    print(json.dumps(value, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
