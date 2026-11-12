"""Owner-triggered, local-first, replaceable Whisper + Argos model library.

No background downloads. Only checked HTTPS upstream Whisper files in this
curated list are downloadable. Own files are never touched: removal is limited
to files directly inside the app-managed model directory.
"""
from __future__ import annotations
import hashlib
import json
import re
import os
from pathlib import Path
from .paths import media_paths, validate_storage_directory
import shutil
import tempfile
import urllib.request

CATALOG = {
    "tiny": {
        "name": "Whisper Tiny multilingual", "size_mb": 78, "backend": "whisper.cpp CPU",
        "url": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin",
        "sha256": "be07e048e1e599ad46341c8d2a135645097a538221678b7acdd1b1919c6e1b21",
        "filename": "ggml-tiny.bin", "max_bytes": 90000000,
    },
    "small": {
        "name": "Whisper Small multilingual", "size_mb": 488, "backend": "whisper.cpp CPU",
        "url": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin",
        "sha256": "1be3a9b2063867b937e64e2ec7483364a79917e157fa98c5d94b5c1fffea987b",
        "filename": "ggml-small.bin", "max_bytes": 550000000,
    },
}


class ModelError(RuntimeError):
    pass


class ModelLibrary:
    def __init__(self, root=None):
        self.root = validate_storage_directory(
            Path(root or media_paths().model_root()).expanduser())
        # Explicit alternate folder can be selected for external SSDs.
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.root = self.root.resolve()
        self.catalog = dict(CATALOG)
        self.manifest = self.root / ".tihulu-verified-market.json"
        if self.manifest.is_file() and not self.manifest.is_symlink():
            try:
                if self.manifest.stat().st_size <= 80_000:
                    saved = json.loads(self.manifest.read_text(encoding="utf-8"))
                    if isinstance(saved, dict):
                        from .online_models import ALLOWED, BASE
                        for key, desc in saved.items():
                            if (key in ALLOWED and isinstance(desc, dict)
                                and desc.get("filename") == f"ggml-{key}.bin"
                                and desc.get("url") == BASE + f"ggml-{key}.bin"
                                and isinstance(desc.get("sha256"), str)
                                and re.fullmatch(r"[a-f0-9]{64}", desc["sha256"])
                                and type(desc.get("max_bytes")) is int
                                and 1_000_000 < desc["max_bytes"] <= 4_200_000_000):
                                self.catalog[key] = desc
            except (OSError, ValueError, UnicodeError):
                pass

    def refresh_online(self, query=""):
        from .online_models import search_official_models
        results = search_official_models(query)
        if not results:
            return []
        self.catalog.update(results)
        # Remember trusted checksum metadata so a downloaded model remains
        # selectable after restarting without network access.
        metadata = {key: value for key,value in self.catalog.items()
                    if key not in CATALOG}
        tmp = self.manifest.with_suffix(".tmp")
        tmp.write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding="utf-8")
        os.chmod(tmp,0o600)
        os.replace(tmp,self.manifest)
        return list(results)

    def _path(self, key):
        if key not in self.catalog:
            raise ModelError("Unknown curated/verified model")
        return self.root / self.catalog[key]["filename"]

    def installed(self):
        return [
            {"id": key, "name": desc["name"], "size_mb": desc["size_mb"],
             "path": str(self._path(key)), "installed": self._path(key).is_file()}
            for key, desc in self.catalog.items()
        ]

    def add_local(self, key, file):
        src = Path(file).expanduser().resolve(strict=True)
        dest = self._path(key)
        if src.is_dir() or src.stat().st_size > self.catalog[key]["max_bytes"]:
            raise ModelError("Invalid Whisper model size")
        if src == dest:
            return str(dest)
        self._copy_verified(src, key)
        return str(dest)

    def _copy_verified(self, source, key):
        desc = self.catalog[key]
        # A previously Media-owned receipt can outlive a file manually removed
        # by the user. It must be authenticated before any replacement;
        # arbitrary or symlinked receipt metadata cannot be overwritten.
        receipt_path = self._receipt(key)
        stale_receipt = False
        if receipt_path.exists() or receipt_path.is_symlink():
            if receipt_path.is_symlink() or not receipt_path.is_file():
                raise ModelError("Untrusted model receipt already exists")
            if receipt_path.stat().st_size > 2048:
                raise ModelError("Untrusted oversized model receipt")
            try:
                old_receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise ModelError("Untrusted model receipt") from exc
            if (old_receipt.get("owner") != "tihulu-media-center"
                or old_receipt.get("filename") != self._path(key).name):
                raise ModelError("Existing model receipt belongs to another owner")
            stale_receipt = True
        digest = hashlib.sha256()
        with tempfile.NamedTemporaryFile(dir=self.root, prefix=".tihulu-model-",
                                         delete=False) as out:
            staged = Path(out.name)
            try:
                with Path(source).open("rb") as inp:
                    total = 0
                    while chunk := inp.read(1024 * 1024):
                        total += len(chunk)
                        if total > desc["max_bytes"]:
                            raise ModelError("Model exceeds size limit")
                        digest.update(chunk)
                        out.write(chunk)
            except Exception:
                staged.unlink(missing_ok=True)
                raise
        if digest.hexdigest() != desc["sha256"]:
            staged.unlink(missing_ok=True)
            raise ModelError("SHA-256 mismatch: refusing unverified model")
        os.chmod(staged, 0o600)
        target = self._path(key)
        # Hard-linking a verified staged inode is atomic no-overwrite. Neither
        # symlinks nor an existing borrowed GGML file can be replaced.
        try:
            os.link(staged, target, follow_symlinks=False)
        except FileExistsError as exc:
            raise ModelError("Existing/borrowed model cannot be overwritten") from exc
        finally:
            staged.unlink(missing_ok=True)
        identity = target.stat()
        receipt = {
            "owner": "tihulu-media-center", "filename": target.name,
            "sha256": digest.hexdigest(), "dev": identity.st_dev,
            "ino": identity.st_ino,
        }
        try:
            if stale_receipt:
                with tempfile.NamedTemporaryFile("w", encoding="utf-8",
                    dir=self.root, prefix=".tihulu-receipt-", delete=False) as out:
                    new_receipt = Path(out.name)
                    json.dump(receipt, out, sort_keys=True)
                os.chmod(new_receipt, 0o600)
                # Only a previously validated Media-owned stale receipt is
                # updated; never replace an unknown model or owner marker.
                os.replace(new_receipt, receipt_path)
            else:
                with receipt_path.open("x", encoding="utf-8") as out:
                    os.chmod(receipt_path, 0o600)
                    json.dump(receipt, out, sort_keys=True)
        except (OSError, ValueError) as exc:
            # Fail closed. Model remains installed but not removable unless
            # a proper ownership receipt is independently present.
            raise ModelError("Model installed but ownership receipt failed; preserve file") from exc

    def download(self, key, progress=None):
        desc = self.catalog.get(key)
        if desc is None:
            raise ModelError("Unknown model catalog entry")
        if self._path(key).exists():
            raise ModelError("This model is already installed")
        # Only a fixed, vetted HTTPS source; redirects may go to a CDN.
        req = urllib.request.Request(desc["url"], headers={"User-Agent":"TIHULU-TV-Center/0.1"})
        tmp = None
        try:
            with urllib.request.urlopen(req, timeout=20) as response:
                if response.url.split("/")[0] != "https:":
                    raise ModelError("Insecure model download redirect")
                # Max_bytes is a safety cap, NOT the content's true size.
                # Only display a percentage when the server supplies a
                # plausible Content-Length; otherwise show bytes received.
                raw_length = response.headers.get("Content-Length")
                try:
                    expected = int(raw_length)
                except (TypeError, ValueError):
                    expected = None
                if expected is not None and not 0 < expected <= desc["max_bytes"]:
                    expected = None
                with tempfile.NamedTemporaryFile(dir=self.root, prefix=".tihulu-download-",
                                                 delete=False) as out:
                    tmp = Path(out.name)
                    total = 0
                    while chunk := response.read(256 * 1024):
                        total += len(chunk)
                        if total > desc["max_bytes"]:
                            raise ModelError("Download exceeds size limit")
                        out.write(chunk)
                        if progress:
                            progress(total, expected)
            self._copy_verified(tmp, key)
            return str(self._path(key))
        except (OSError, TimeoutError, ValueError) as exc:
            raise ModelError(str(exc)) from exc
        finally:
            if tmp:
                tmp.unlink(missing_ok=True)

    def _receipt(self, key):
        return self.root / (".tihulu-media-owned-" + self._path(key).name + ".json")

    def remove(self, key, *, allow_external_delete=False):
        import stat
        file = self._path(key)
        owned_root = media_paths().data
        # External SSD/user-selected directories can be read and used, but
        # deletion is forbidden by default even if Media installed a copy.
        if not file.is_relative_to(owned_root) and not allow_external_delete:
            raise ModelError("Shared/external model root: deletion is not authorized")
        validate_storage_directory(file.parent)
        try:
            identity = file.lstat()
        except FileNotFoundError:
            return str(file)
        if not stat.S_ISREG(identity.st_mode):
            raise ModelError("Only regular owned model files may be removed")
        receipt_path = self._receipt(key)
        if receipt_path.is_symlink() or not receipt_path.is_file():
            raise ModelError("Borrowed/unmarked model: deletion is not authorized")
        try:
            if receipt_path.stat().st_size > 2048:
                raise ValueError("Oversized ownership receipt")
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ModelError("Invalid model ownership receipt") from exc
        if (receipt.get("owner") != "tihulu-media-center"
            or receipt.get("filename") != file.name
            or receipt.get("dev") != identity.st_dev
            or receipt.get("ino") != identity.st_ino):
            raise ModelError("Model provenance changed; refusing deletion")
        digest = hashlib.sha256()
        # Pin opened inode, preventing immediate inode reuse in a concurrent
        # foreign delete/recreate operation; no symlink follow.
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(file, flags)
        try:
            opened = os.fstat(fd)
            if (opened.st_dev, opened.st_ino) != (identity.st_dev, identity.st_ino):
                raise ModelError("Model changed during ownership verification")
            with os.fdopen(os.dup(fd), "rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
            current = file.lstat()
            if (current.st_dev, current.st_ino) != (opened.st_dev, opened.st_ino):
                raise ModelError("Model changed during deletion; preserving")
            if digest.hexdigest() != receipt.get("sha256"):
                raise ModelError("Model hash differs from receipt; preserving")
            file.unlink()
        finally:
            os.close(fd)
        # Preserve the receipt if cleanup fails; it cannot authorize a
        # differently-created inode and can be reviewed manually.
        try:
            receipt_path.unlink()
        except OSError:
            pass
        return str(file)

    def capability(self):
        from tv_center.media_backend.compute import detect_devices
        from tv_center.media_backend.translation import installed_translation_pairs
        profile = detect_devices()
        return {
            "devices": profile["devices"],
            "speech": profile["speech"],
            "argos_pairs": installed_translation_pairs(),
            "models": self.installed(),
        }


def argos_available_pairs(refresh=False):
    try:
        from argostranslate import package
    except ImportError as exc:
        raise ModelError("Argos Translate Python package unavailable") from exc
    if refresh:
        package.update_package_index()  # only after explicit user click
    try:
        found = package.get_available_packages()
    except Exception as exc:
        raise ModelError("Argos catalog not available") from exc
    return [{"source": p.from_code, "target": p.to_code,
             "version": getattr(p, "package_version", ""),
             "name": str(p)}
            for p in found if p.from_code in ("tr", "de", "en")
            and p.to_code in ("tr", "de", "en") and p.from_code != p.to_code
            and getattr(p, "type", "translate") == "translate"]


def argos_install(source, target):
    if source not in ("de", "en", "tr") or target not in ("de", "en", "tr") or source == target:
        raise ModelError("Invalid Argos language pair")
    from argostranslate import package
    found = next((p for p in package.get_available_packages()
                  if p.from_code == source and p.to_code == target
                  and getattr(p, "type", "translate") == "translate"), None)
    if found is None:
        raise ModelError("Requested translation package is unavailable from official Argos index")
    # Never overwrite an installed/borrowed pair.
    if any(p.from_code == source and p.to_code == target
           for p in package.get_installed_packages()):
        raise ModelError("Argos pair already installed; preserve existing package")
    # Official Argos download + install; only after interactive confirmation.
    path = found.download()
    package.install_from_path(path)
    # Do not presume system/global Argos packages are Media-owned.
    # An ownership record is possible only when the package landed inside
    # the Media-owned model namespace and was absent before this invocation.
    matches = [p for p in package.get_installed_packages()
               if p.from_code == source and p.to_code == target]
    if len(matches) == 1:
        location = Path(matches[0].package_path)
        owned = media_paths().data
        if location.is_relative_to(owned) and not location.is_symlink():
            validate_storage_directory(location)
            stat_info = location.lstat()
            receipt_dir = owned / "argos-ownership"
            validate_storage_directory(receipt_dir)
            receipt_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
            receipt = receipt_dir / (source + "-" + target + ".json")
            record = {"owner": "tihulu-media-center", "source": source,
                      "target": target, "path": str(location),
                      "dev": stat_info.st_dev, "ino": stat_info.st_ino}
            try:
                with receipt.open("x", encoding="utf-8") as out:
                    os.chmod(receipt, 0o600)
                    json.dump(record, out, sort_keys=True)
            except FileExistsError:
                # Existing receipt is not proof this invocation owns it.
                pass
    return f"{source} -> {target}"


def argos_installed_pairs():
    try:
        from argostranslate import package
    except ImportError:
        return []
    return [{"source": p.from_code, "target": p.to_code,
             "name": str(p), "path": str(p.package_path)}
            for p in package.get_installed_packages()
            if p.from_code in ("tr", "de", "en") and p.to_code in ("tr", "de", "en")]


def argos_remove(source, target):
    import stat
    if (source not in ("tr", "de", "en") or target not in ("tr", "de", "en")
        or source == target):
        raise ModelError("Invalid Argos language pair")
    from argostranslate import package
    installed = [p for p in package.get_installed_packages()
                 if p.from_code == source and p.to_code == target]
    if len(installed) != 1:
        raise ModelError("Expected exactly one installed Argos package for this language pair")
    location = Path(installed[0].package_path)
    owned = media_paths().data
    receipt_dir = owned / "argos-ownership"
    receipt = receipt_dir / (source + "-" + target + ".json")
    # A path under HOME, a matching language pair, or an external SSD are
    # NOT ownership evidence. Borrowed/shared packages stay installed.
    if not location.is_relative_to(owned):
        raise ModelError("Borrowed Argos pack: outside Media-owned data")
    validate_storage_directory(receipt_dir)
    validate_storage_directory(location)
    if receipt.is_symlink() or not receipt.is_file():
        raise ModelError("Argos package lacks a Media ownership receipt")
    try:
        if receipt.stat().st_size > 2048:
            raise ValueError("Oversized receipt")
        provenance = json.loads(receipt.read_text(encoding="utf-8"))
        identity = location.lstat()
    except (OSError, ValueError) as exc:
        raise ModelError("Argos provenance cannot be verified") from exc
    if (provenance.get("owner") != "tihulu-media-center" or
        provenance.get("source") != source or provenance.get("target") != target or
        provenance.get("path") != str(location) or
        (identity.st_dev, identity.st_ino) !=
        (provenance.get("dev"), provenance.get("ino")) or
        not stat.S_ISDIR(identity.st_mode)):
        raise ModelError("Argos pack identity changed; preserve borrowed files")
    package.uninstall(installed[0])
    receipt.unlink()
    return f"{source} -> {target}"
