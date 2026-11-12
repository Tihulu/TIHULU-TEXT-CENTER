"""Optional CPU whisper.cpp CLI build from a pinned upstream release.

Executed only after owner confirmation from Settings; never during install,
boot, TV playback or model selection. CPU-only, user-owned. Requires git,
cmake and a C++ compiler. Real ARM64 performance not yet benchmarked.
"""
from __future__ import annotations
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path.home()/".local/share/tihulu-tv-center/whisper-runtime"
MARKER = ".tihulu-managed-whisper"
RELEASE = "v1.9.5"
RELEASE_SHA_PREFIX = "d1be6fd"
REPOSITORY = "https://github.com/ggml-org/whisper.cpp.git"

class WhisperRuntimeError(RuntimeError):
    pass

class WhisperRuntime:
    def __init__(self, root=None):
        self.root = Path(root or ROOT).expanduser()

    @property
    def binary(self):
        return self.root/"build/bin/whisper-cli"

    def ready(self):
        return (self.root/MARKER).is_file() and self.binary.is_file() and os.access(self.binary, os.X_OK)

    def _guard(self):
        if self.root.is_symlink():
            raise WhisperRuntimeError("Symlink runtime path refused")
        if not self.root.resolve().is_relative_to(Path.home().resolve()):
            raise WhisperRuntimeError("Managed runtime must be under the user's home")
        if self.root.exists() and any(self.root.iterdir()) and not (self.root/MARKER).is_file():
            raise WhisperRuntimeError("Refusing to modify an unowned Whisper installation")

    def install(self):
        if os.geteuid() == 0:
            raise WhisperRuntimeError("Whisper engine must be built as an ordinary user, not root")
        self._guard()
        if self.ready():
            raise WhisperRuntimeError("Whisper engine already installed. Remove before rebuilding.")
        required = {"git":"git", "cmake":"cmake", "C++ compiler":"c++"}
        missing = [name for name, exe in required.items() if not shutil.which(exe)]
        if missing:
            raise WhisperRuntimeError("Build tools missing: " + ", ".join(missing) +
                                      ". On Debian/Pop!_OS run: sudo apt install git cmake g++")
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root/MARKER).write_text("Managed by TIHULU TV Center\n", encoding="utf-8")
        source = self.root/"source"
        build = self.root/"build"
        try:
            if not source.exists():
                subprocess.run(["git", "clone", "--depth", "1", "--branch", RELEASE,
                                REPOSITORY, str(source)],
                               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                               stderr=subprocess.PIPE, timeout=300, check=True)
            revision = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"],
                                               timeout=10).decode("ascii").strip()
            if not revision.startswith(RELEASE_SHA_PREFIX):
                raise WhisperRuntimeError("Upstream release commit was not the expected verified tag")
            subprocess.run(["cmake", "-S", str(source), "-B", str(build),
                            "-DCMAKE_BUILD_TYPE=Release",
                            "-DWHISPER_BUILD_TESTS=OFF", "-DGGML_CUDA=OFF"],
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                           stderr=subprocess.PIPE, timeout=180, check=True)
            subprocess.run(["cmake", "--build", str(build), "--target", "whisper-cli",
                            "--config", "Release", "-j", "2"],
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                           stderr=subprocess.PIPE, timeout=1800, check=True)
        except (OSError, subprocess.SubprocessError) as exc:
            raise WhisperRuntimeError("Whisper CPU build failed: " + str(exc)[:320]) from exc
        if not self.ready():
            raise WhisperRuntimeError("Compiled whisper-cli executable was not found")
        return "Whisper CPU engine installed. Restart TIHULU TV Center to activate: " + str(self.binary)

    def remove(self):
        self._guard()
        if not (self.root/MARKER).exists():
            return "No managed whisper.cpp engine installed"
        shutil.rmtree(self.root)
        return "Managed whisper.cpp CPU runtime removed; model files preserved"
