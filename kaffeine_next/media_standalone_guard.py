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
    if active is None:
        # Do not silently adopt another application's or a failed preview's
        # user-owned config/data/transaction tree, even when it has no pointer.
        for key in ("root", "state"):
            if p[key].exists() or p[key].is_symlink():
                raise Hold("Unowned standalone install/state directory: " + str(p[key]))
        for key in (*NAMES, "current"):
            if public_receipt(home, key)["type"] != "absent":
                raise Hold("Existing unowned/legacy destination: " + str(p[key]))
    # Never adopt a release from the old project or another installer.
    dest = release_path(home, rev)
    already = bool(active and active["sha"] == rev)
    if dest.exists() or dest.is_symlink():
        if not already:
            raise Hold("Release path already occupied: " + str(dest))
    journal = p["state"] / "transactions" / rev / "journal.json"
    safe_parent(journal, home)
    if journal.parent.exists() or journal.parent.is_symlink():
        if not already:
            raise Hold("Foreign/incomplete transaction directory; run --recover or --rollback")
    return {
        "owner": APP, "source_sha": rev, "dry_run": True,
        "already_active": already, "new_release": str(dest),
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


def write_journal(home, rev, record):
    # First durable receipt is no-clobber; all later writes update only this
    # transaction's known journal. Never overwrite an unexpectedly new file.
    atomic_json(journal_path(home, rev), home, record,
                no_replace=(record["phase"] == "prepared" and
                            not record.get("pending")))


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
    r = {"owner": APP, "sha": rev, "phase": "prepared",
         "prior": old, "new": next_state, "pending": ""}
    write_journal(home, rev, r)  # BEFORE any managed release/file write
    p = layout(home)
    pending = p["releases"] / (".pending-" + rev[:12])
    safe_parent(pending, home)
    if pending.exists() or pending.is_symlink():
        raise Hold("Pending release path occupied")
    r["pending"] = str(pending)
    write_journal(home, rev, r)
    p["releases"].mkdir(parents=True, exist_ok=True)
    try:
        shutil.copytree(stage, pending, symlinks=True)
        if items(pending) != next_state["release"]:
            raise Hold("Staged release altered during copy")
        r["phase"] = "activating"
        write_journal(home, rev, r)
        new_release = release_path(home, rev)
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


def validate_rollback(home, rev):
    r = journal(home, rev)
    if r["phase"] == "rolled_back":
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
    pending = Path(r["pending"]) if r.get("pending") else None
    if pending and (pending.exists() or pending.is_symlink()):
        # A full pending copy is known; partial copies may only contain exact known objects.
        if pending.is_symlink() or not pending.is_dir():
            raise Hold("Foreign pending path")
        partial = items(pending)
        if any(after["release"].get(k) != v for k, v in partial.items()):
            raise Hold("Pending copy modified; refusing cleanup")
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
    # Keep verified historical releases for forensic recovery/previous rollback.
    # Only remove a complete and known scratch tree; never follow links.
    pending = Path(r["pending"]) if r.get("pending") else None
    if pending and pending.is_dir() and not pending.is_symlink():
        shutil.rmtree(pending)
    r["phase"] = "rolled_back"
    write_journal(home, rev, r)
    return {"owner": APP, "sha": rev, "phase": "rolled_back", "package_action": "none"}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("preflight", "dry-run", "activate",
                                            "rollback-plan", "rollback", "recover",
                                            "guarded-script"))
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
        if args.command == "guarded-script":
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
        if args.command in ("preflight", "dry-run"):
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
