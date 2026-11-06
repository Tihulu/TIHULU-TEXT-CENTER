"""Cross-platform, loopback-only security and RF process helpers.

The public GitHub Pages client never touches USB hardware directly: it sends
explicit requests with a user-paired bearer token to the localhost companion.
"""
from __future__ import annotations

import os
from pathlib import Path
import platform
import secrets
import subprocess

PAGES_ORIGIN = "https://tihulu.github.io"


def app_data_dir() -> Path:
    system = platform.system()
    if system == "Windows":
        return Path(os.environ.get("LOCALAPPDATA", str(Path.home()/"AppData/Local"))) / "Tihulu" / "SatelliteCenter"
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "TihuluSatelliteCenter"
    return Path.home() / ".local" / "share" / "tihulu-satellite-center"


def pairing_secret(directory: Path) -> str:
    """Create one long-lived local secret, readable only to the owner where supported."""
    secret_file = directory / "pages-pairing.key"
    if secret_file.exists():
        if secret_file.is_symlink():
            raise RuntimeError("Refusing symbolic link as pairing secret")
        key = secret_file.read_text("ascii").strip()
        if len(key) != 64 or not all(c in "0123456789abcdef" for c in key):
            raise RuntimeError("Invalid existing pairing secret: reset manually, do not silently replace")
        return key
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    key = secrets.token_hex(32)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(secret_file, flags, 0o600)
    except FileExistsError:
        return pairing_secret(directory)
    with os.fdopen(fd, "w", encoding="ascii") as file:
        file.write(key + "\n")
    return key


def request_is_remote(origin: str | None) -> bool:
    return origin == PAGES_ORIGIN


def local_host_allowed(host: str, port: int) -> bool:
    return host.lower() in {f"127.0.0.1:{port}", f"localhost:{port}"}


def allowed_origin(origin: str | None, host: str) -> bool:
    if not origin:
        return True
    return origin in {PAGES_ORIGIN, f"http://{host.lower()}"}


def lock_receiver(fd: int) -> None:
    if os.name == "nt":
        import msvcrt
        os.lseek(fd, 0, os.SEEK_SET)
        if os.fstat(fd).st_size == 0:
            os.write(fd, b"0")
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
    else:
        import fcntl
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)


def unlock_receiver(fd: int) -> None:
    if os.name == "nt":
        import msvcrt
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(fd, fcntl.LOCK_UN)


def start_receiver_process(cmd: list[str], **kwargs):
    """Launch a specific allowlisted binary, never a shell or caller-supplied command."""
    if os.name == "nt":
        return subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP, **kwargs)
    return subprocess.Popen(cmd, start_new_session=True, **kwargs)


def stop_receiver_process(process) -> None:
    if process is None or process.poll() is not None:
        return
    try:
        if os.name == "nt":
            process.terminate()
        else:
            import signal
            os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=1.5)
    except (ProcessLookupError, OSError, subprocess.TimeoutExpired):
        try:
            if os.name == "nt":
                process.kill()
            else:
                import signal
                os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=1)
        except (ProcessLookupError, OSError, subprocess.TimeoutExpired):
            pass
