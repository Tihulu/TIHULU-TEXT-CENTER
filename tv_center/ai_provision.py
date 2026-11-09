"""Owner-initiated first-run offline AI starter bundle + model-market backend.

A normal TV session never downloads or compiles anything. A confirmed
installation (CLI or Market button) provisions a removable local CPU engine,
a SHA-256 verified multilingual model, and DE/EN/TR Argos pairs. Once
installed, recognition/translation work without Internet.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import subprocess
import sys

from .ai_settings import AISettings
from .model_market import ModelLibrary, argos_installed_pairs
from .runtime import AIRuntime
from .whisper_engine import WhisperRuntime

# Default offline translation mesh: any pair can route via English.
# Bidirectional FR is important for multilingual German/NRW broadcasts.
PAIRS = (("de", "en"), ("en", "de"), ("en", "tr"), ("tr", "en"),
         ("fr", "en"), ("en", "fr"))
LANGUAGES = ("de", "en", "tr", "fr")

def translate_ready(pairs):
    """All installed DE/EN/TR/FR paths must work in BOTH directions."""
    graph = {x: set() for x in LANGUAGES}
    for item in pairs:
        source, target = item["source"], item["target"]
        if source in graph and target in graph:
            graph[source].add(target)
    for language in LANGUAGES:
        seen, pending = {language}, [language]
        while pending:
            for nxt in graph[pending.pop()]:
                if nxt not in seen:
                    seen.add(nxt)
                    pending.append(nxt)
        if len(seen) != len(LANGUAGES):
            return False
    return True

def translate_ready_three(pairs):
    graph={code:set() for code in ("de","en","tr")}
    for item in pairs:
        a,b=item["source"],item["target"]
        if a in graph and b in graph:
            graph[a].add(b)
    for code in graph:
        seen,pending={code},[code]
        while pending:
            for nxt in graph[pending.pop()]:
                if nxt not in seen:
                    seen.add(nxt)
                    pending.append(nxt)
        if len(seen)!=3:
            return False
    return True


class StarterAI:
    def __init__(self, ai=None, library=None, runtime=None, whisper=None):
        self.ai = ai or AISettings()
        self.library = library or ModelLibrary(self.ai.values["model_dir"] or None)
        self.runtime = runtime or AIRuntime()
        self.whisper = whisper or WhisperRuntime()

    def status(self):
        # Market and live subtitles must use the SAME installed-pack source.
        # A system Argos installation can differ from the private runtime;
        # never report its packs as live-caption-ready when managed Argos
        # exists. Run subprocess discovery only on an explicit inventory
        # worker (the Qt first-paint path is deferred).
        managed = self.runtime.status()["installed"]
        if managed:
            from .argos_market_bridge import run as argos_market
            try:
                pairs = argos_market("installed",installed_timeout=9)
            except (ImportError, OSError, RuntimeError, ValueError,
                    subprocess.TimeoutExpired):
                pairs = []
        else:
            try:
                pairs = argos_installed_pairs()
            except (ImportError, OSError, RuntimeError):
                pairs = []
        model = self.library._path("tiny")
        active = self.ai.values.get("model_path", "")
        return {
            "whisper_engine_ready": self.whisper.ready(),
            "tiny_model_ready": model.is_file(),
            "tiny_model": str(model),
            "active_model": active,
            "argos_runtime_ready": managed,
            "installed_pairs": [p["source"] + "→" + p["target"] for p in pairs],
            # Preserve the legacy trio for older callers; full profile
            # readiness now additionally checks French in both directions.
            "translation_three_languages_ready": translate_ready_three(pairs),
            "translation_four_languages_ready": translate_ready(pairs),
            "enabled_asr": self.ai.values["asr_enabled"],
            "enabled_translation": self.ai.values["translation_enabled"],
            "storage": str(self.library.root),
        }

    def install(self, *, progress=None):
        """Explicit starter-bundle installation; no elevated privileges.

        Individual steps are recoverable. A rerun resumes already installed
        engines/packs without deleting owner-provided files.
        """
        if os.geteuid() == 0:
            raise RuntimeError("Install local AI as your user, not root")
        def show(message):
            if progress:
                progress(message)
        show("1/3 · Setting up Whisper CPU runtime (user-owned)")
        if not self.whisper.ready():
            self.whisper.install()
        show("2/3 · Downloading SHA-256 verified Whisper Tiny multilingual (~78 MB)")
        model = self.library._path("tiny")
        if not model.is_file():
            self.library.download("tiny", progress=lambda got, size:
                show(f"Whisper Tiny: {got//1048576} MiB received"))
        if not model.is_file():
            raise RuntimeError("Verified Whisper model unavailable")
        show("3/3 · Creating offline Argos runtime and installing six bidirectional DE/EN/TR/FR language packs")
        if not self.runtime.status()["installed"]:
            self.runtime.install_argos()
        packages = self._setup_argos_packs(progress=show)
        ready = translate_ready(packages)
        # These features are installed but idle until a caption source is
        # selected. Users can disable either toggle in the market at any time.
        self.ai.update({
            "model_path": str(model),
            "model_dir": str(self.library.root),
            "backend": "auto",
            "asr_enabled": True,
            "translation_enabled": ready,
        })
        self.ai.configure_environment()
        status = self.status()
        if not ready:
            status["warning"] = ("Some translation packs are unavailable. "
                "Use the Translator Market to retry; existing packs are preserved.")
        show("Starter bundle installed; video subtitles remain OFF until selected")
        return status

    def _setup_argos_packs(self, progress=None):
        """Use the newly installed venv, not the system Python process."""
        python = Path(self.runtime.status()["python"])
        if not python.is_file():
            raise RuntimeError("Managed Argos Python runtime not installed")
        # Run only fixed module commands. No shell, arbitrary model URL or user code.
        env = os.environ.copy()
        workroot = str(Path(__file__).resolve().parent.parent)
        env["PYTHONPATH"] = workroot + os.pathsep + env.get("PYTHONPATH", "")
        proc = subprocess.run(
            [str(python), "-m", "tv_center.ai_provision", "--argos-worker"],
            cwd=workroot, env=env, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=1800, check=False)
        if proc.returncode:
            error = proc.stderr.decode("utf-8", "replace")[-750:]
            raise RuntimeError("Offline translation packs: " + error)
        try:
            result = json.loads(proc.stdout.decode("utf-8", "replace"))
        except (ValueError, UnicodeError) as exc:
            raise RuntimeError("Invalid translation pack setup response") from exc
        if progress:
            progress("Language packs: " + ", ".join(result["installed"]))
            if result["errors"]:
                progress("Pack catalog limitations: " + "; ".join(result["errors"])[:220])
        return result["pairs"]

def argos_worker():
    """Run inside the user-owned Argos virtual environment."""
    from argostranslate import package
    from .model_market import argos_installed_pairs
    package.update_package_index()
    available = {(p.from_code, p.to_code): p for p in package.get_available_packages()
                 if p.from_code in LANGUAGES and p.to_code in LANGUAGES}
    installed = {(p["source"], p["target"]) for p in argos_installed_pairs()}
    done, errors = [], []
    for source, target in PAIRS:
        if (source, target) in installed:
            done.append(source + "→" + target)
            continue
        p = available.get((source, target))
        if p is None:
            errors.append(source + "→" + target + " absent from official Argos index")
            continue
        try:
            archive = p.download()
            package.install_from_path(archive)
            done.append(source + "→" + target)
        except (OSError, RuntimeError, ValueError) as exc:
            errors.append(source + "→" + target + ": " + str(exc)[:120])
    if any(item not in installed for item in PAIRS if
           item[0]+"→"+item[1] in done):
        from .argos_generation import changed
        changed()
    print(json.dumps({"installed": done, "errors": errors,
                      "pairs": argos_installed_pairs()}, ensure_ascii=False))

def main(args=None):
    args = list(sys.argv[1:] if args is None else args)
    if args == ["--argos-worker"]:
        argos_worker()
        return 0
    if args == ["--argos-status-worker"]:
        print(json.dumps(argos_installed_pairs(), ensure_ascii=False))
        return 0
    starter = StarterAI()
    if args in ([], ["status"]):
        print(json.dumps(starter.status(), indent=2, ensure_ascii=False))
        return 0
    if args == ["install"]:
        print("Installing default multilingual Whisper + Argos DE/EN/TR bundle.", flush=True)
        result = starter.install(progress=lambda msg: print(msg, flush=True))
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    print("Usage: tihulu-tv-center ai [status|install]", file=sys.stderr)
    return 2

if __name__ == "__main__":
    raise SystemExit(main())
