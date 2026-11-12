"""STAND-SAT pinned read-only source/package preflight.

This module NEVER installs, stages, copies, removes, opens USB, launches Qt,
starts SatDump or edits another TIHULU application's configuration. It requires
exact immutable, clean Git source checkouts and validates every file before
emitting a *future* staging/rollback plan. It is NOT an installer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys


STAND_DIR = Path(__file__).resolve().parent
REPO_DIR = STAND_DIR.parents[1]
NATIVE_MANIFEST = STAND_DIR / "native_desktop_manifest.json"
WEB_MANIFEST = STAND_DIR / "webusb_pwa_manifest.json"
FOREIGN_PREFIXES = (
    "textcenter/", "tv_center/", "kaffeine_next/", "rf_geolocation_center/",
    "tihulu_flight_radar/", "tihulu_survival_kit/", "ai_tools/",
)
SHA40 = re.compile(r"^[0-9a-f]{40}$")
NATIVE_FILES = {"satellite_center/index.html",
                "satellite_center/native_desktop_bridge.js",
                "satellite_center/README.md"}


class HoldError(ValueError):
    """Fail closed, with no side effects, if provenance/ownership is uncertain."""


def blob_sha(data: bytes) -> str:
    """Git blob SHA-1, not a file's ordinary SHA-1 or its SHA-256."""
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\x00" + data).hexdigest()


def safe_path(path: str) -> str:
    if not isinstance(path, str) or not path or "\\" in path or "\x00" in path:
        raise HoldError(f"Invalid asset name: {path!r}")
    posix = PurePosixPath(path)
    if posix.is_absolute() or str(posix) != path or any(
        x in ("", ".", "..") for x in path.split("/")
    ):
        raise HoldError(f"Path traversal or noncanonical asset: {path!r}")
    if not path.startswith("satellite_center/"):
        raise HoldError(f"Foreign application asset forbidden: {path}")
    if path.startswith("satellite_center/standalone/"):
        raise HoldError("Standalone staging tools are never included in runtime payloads")
    return path


def ensure_regular_in_root(root: Path, path: str) -> Path:
    path = safe_path(path)
    root = root.resolve(strict=True)
    dest = root / path
    for component in (root.joinpath(*Path(path).parts[:i])
                      for i in range(1, len(Path(path).parts) + 1)):
        if component.is_symlink():
            raise HoldError(f"Symlink in source path rejected: {path}")
    if not dest.is_file() or not dest.resolve().is_relative_to(root):
        raise HoldError(f"Missing, escaped or nonregular source file: {path}")
    return dest


def checked_bytes(root: Path, path: str, expected_sha: str) -> int:
    if not isinstance(expected_sha, str) or not SHA40.fullmatch(expected_sha):
        raise HoldError(f"Unverified Git SHA for {path}")
    source = ensure_regular_in_root(root, path)
    data = source.read_bytes()
    if blob_sha(data) != expected_sha:
        raise HoldError(f"Unexpected source bytes: {path}")
    return len(data)


def load_json(path: Path) -> dict:
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise HoldError(f"Invalid manifest JSON root: {path.name}")
    return doc


def _git(root: Path, *args: str) -> bytes:
    try:
        p = subprocess.run(["git", "-C", str(root), *args],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           timeout=15, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise HoldError("Git inspection unavailable or timed out") from exc
    if p.returncode:
        raise HoldError(f"Git source verification failed for {args[0]}")
    return p.stdout


def pinned_tree(root: Path, expected_head: str) -> dict[str, tuple[str, str]]:
    """Inspect an existing source checkout; never fetch or mutate its refs."""
    if not SHA40.fullmatch(expected_head):
        raise HoldError("Ref must be a full immutable Git commit SHA")
    if not root.is_dir() or root.is_symlink():
        raise HoldError("Only an existing real source checkout is accepted")
    root = root.resolve(strict=True)
    top = Path(_git(root, "rev-parse", "--show-toplevel").decode().strip()).resolve()
    if top != root:
        raise HoldError("Source root must be the top-level pinned checkout")
    head = _git(root, "rev-parse", "HEAD").decode().strip()
    if head != expected_head:
        raise HoldError(f"Source HEAD mismatch: expected {expected_head}, got {head}")
    if _git(root, "status", "--porcelain", "--untracked-files=normal").strip():
        raise HoldError("Dirty source tree: never package an unknown source snapshot")
    raw = _git(root, "ls-tree", "-r", "-z", expected_head, "--", "satellite_center")
    out: dict[str, tuple[str, str]] = {}
    for rec in raw.split(b"\x00"):
        if not rec:
            continue
        meta, path_b = rec.split(b"\t", 1)
        mode, kind, obj_sha = meta.decode().split()
        path = safe_path(path_b.decode("utf-8"))
        if kind != "blob" or mode not in ("100644", "100755"):
            raise HoldError(f"Nonregular source entry forbidden: {path}")
        if path in out:
            raise HoldError(f"Duplicate source entry: {path}")
        out[path] = (mode, obj_sha)
    return out


def is_native_payload(path: str) -> bool:
    p = PurePosixPath(safe_path(path))
    if path in NATIVE_FILES:
        return True
    if len(p.parts) == 2 and p.suffix == ".py":
        return True
    return (path.startswith("satellite_center/assets/") or
            path.startswith("satellite_center/browser/"))


def checked_native(root: Path, manifest: dict, tree: dict[str, tuple[str, str]]):
    if manifest.get("schema") != "tihulu-stand-sat-native-manifest-v1":
        raise HoldError("Unknown native manifest schema")
    required = manifest.get("required_blobs", [])
    if not required or len({x["path"] for x in required}) != len(required):
        raise HoldError("Missing or duplicated pinned native critical source files")
    for entry in required:
        path = safe_path(entry["path"])
        git_sha = entry["git_blob_sha1"]
        if path not in tree or tree[path][1] != git_sha:
            raise HoldError(f"Native critical Git tree contract differs: {path}")
        checked_bytes(root, path, git_sha)

    selected = sorted(x for x in tree if is_native_payload(x))
    if not selected or "satellite_center/__main__.py" not in selected:
        raise HoldError("Missing native application entrypoint")
    if not any(x.startswith("satellite_center/browser/") for x in selected):
        raise HoldError("Native Qt bundled browser UI is absent")
    if not any(x.startswith("satellite_center/assets/") for x in selected):
        raise HoldError("Native icons/assets are absent")
    output = []
    for path in selected:
        mode, sha = tree[path]
        size = checked_bytes(root, path, sha)
        output.append({"path": path, "git_blob_sha1": sha, "bytes": size,
                       "mode": mode, "action": "STAGE_APP_FILE_ONLY"})
    return output


def checked_web(root: Path, manifest: dict, index: dict,
                tree: dict[str, tuple[str, str]]):
    if manifest.get("schema") != "tihulu-stand-sat-webusb-manifest-v1":
        raise HoldError("Unknown WebUSB manifest schema")
    index_spec = manifest["assets"]
    if index.get("schema") != "satellite-pages-atomic-prepublication-v1":
        raise HoldError("Unknown 50-asset Pages schema")
    rows = index.get("files", [])
    if len(rows) != 50 or len({x["path"] for x in rows}) != 50:
        raise HoldError("Missing/duplicate WebUSB asset in required 50-file closure")
    if sum(bool(r["strict_31"]) for r in rows) != 31:
        raise HoldError("Strict 31-asset parity contract changed")
    if sum(bool(r["critical"]) for r in rows) != 42:
        raise HoldError("Critical PWA import closure changed")
    if sum(bool(r["optional"]) for r in rows) != 7:
        raise HoldError("Optional PWA asset closure changed")
    if sorted(r["order"] for r in rows) != list(range(1, 51)):
        raise HoldError("Publication order not fully enumerated")
    if index_spec["cache_version"] != index["contract"]["service_worker_version"]:
        raise HoldError("Worker cache version and manifest disagree")
    if index["pinned"]["pwa_pr101"] != manifest["source_commit"]:
        raise HoldError("WebUSB candidate source commit mismatch")
    output = []
    for row in sorted(rows, key=lambda x: x["order"]):
        path = safe_path(row["path"])
        if not path.startswith("satellite_center/browser/"):
            raise HoldError("WebUSB payload contains nonbrowser path")
        sha = row["source_pr101_blob_sha1"]
        if path not in tree or tree[path][1] != sha:
            raise HoldError(f"WebUSB asset SHA differs from pinned source: {path}")
        size = checked_bytes(root, path, sha)
        output.append({"path": path, "git_blob_sha1": sha, "bytes": size,
                       "copy_order": row["order"], "critical": row["critical"],
                       "parity_31": row["strict_31"],
                       "action": "STAGE_STATIC_FILE_ONLY"})
    return output


def plan(mode: str, root: Path, *, manifest_override: dict | None = None,
         asset_index_override: dict | None = None,
         tree_override: dict[str, tuple[str, str]] | None = None) -> dict:
    """Generate validated read-only plan; overrides ONLY support synthetic QA."""
    if mode not in ("native", "webusb"):
        raise HoldError("Only independent native/webusb profiles; combined installer is not authorized")
    mf = NATIVE_MANIFEST if mode == "native" else WEB_MANIFEST
    manifest = manifest_override if manifest_override is not None else load_json(mf)
    source_sha = manifest.get("source_commit", "")
    if not SHA40.fullmatch(source_sha):
        raise HoldError("Manifest lacks a pinned source commit")
    tree = tree_override if tree_override is not None else pinned_tree(root, source_sha)
    if mode == "native":
        files = checked_native(root, manifest, tree)
    else:
        assets = manifest["assets"]
        asset_file = REPO_DIR / assets["index_path"]
        index = asset_index_override if asset_index_override is not None else load_json(asset_file)
        if asset_index_override is None:
            checked_bytes(REPO_DIR, assets["index_path"], assets["index_git_blob_sha1"])
        files = checked_web(root, manifest, index, tree)
    protected = ("captures/", "*.cu8", "*.wav", "*.png", "*.jpg", "*.tle",
                 "schedule.json", "hardware.json", "pages-pairing.key",
                 "user_downlinks.json", "planning_candidates.json",
                 "other TIHULU app directories", "shared readsb/tar1090",
                 "cooperative Text-center-namespaced SDR lock")
    return {
        "schema": "tihulu-stand-sat-dry-run-plan-v1",
        "mode": mode,
        "source_commit": source_sha,
        "source_files": files,
        "file_count": len(files),
        "bytes_total": sum(x["bytes"] for x in files),
        "install_performed": False,
        "release_allowed": False,
        "destination_repo_initialized": False,
        "staging_instructions": [
            "COPY reviewed application-owned files from verified pinned commit into an ISOLATED DISPOSABLE staging tree only AFTER owner authorization",
            "Do not copy, move, change, or delete any other TIHULU application file",
            "Native #92 and WebUSB #101 are separate Git snapshots; run combined integration tests before declaring parity",
        ],
        "rollback_manifest": {
            "state": "PLAN_ONLY_NOT_EXECUTABLE",
            "must_record_preexisting_owned_installed_blobs_before_upgrade": True,
            "restore_scope": "exactly application-owned code/shortcut files in an approved prior package manifest",
            "never_remove_or_overwrite": list(protected),
            "other_apps": "never touch, stop, unbind, reset or modify",
            "cooperative_sdr_lock": "preserve legacy Text-namespaced shared coordination until neutral protocol approved",
        },
        "unresolved_gates": [
            "No independent destination repo installation or signed one-line installer",
            "No installed Qt and Windows/macOS/Pi hardware proof",
            "No native #92 plus WebUSB #101 integration execution",
            "No real RTL-SDR/SatDump or foreign-service coexistence proof",
            "Native capture 2.048 MS/s versus SatDump 1.024 MS/s REG-06 unresolved",
            "No authorized Pages publication; existing 31-asset parity remains RED",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only pinned Satellite source packaging preflight. NEVER installs.")
    parser.add_argument("--mode", choices=("native", "webusb"), required=True)
    parser.add_argument("--source-root", type=Path, required=True,
                        help="EXISTING CLEAN Git checkout at the exact pinned source commit")
    args = parser.parse_args(argv)
    try:
        output = plan(args.mode, args.source_root)
    except (HoldError, OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"STAND-SAT HOLD: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
