"""STAND-MEDIA fail-closed acceptance gates (NO hardware or model inference).

These *deliberately fail* against original Media PR #67. They test the
standalone application contract, not a claim that it is already fulfilled.
Do NOT mark expectedFailure or silently skip: fixing these tests requires
separately owner-approved production refactoring and a clean standalone
package. This new Draft PR modifies no runtime source.
"""
import ast
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


def foreign_python_imports():
    """AST import graph, including imports deferred until first inference."""
    hits = []
    for package in ("tv_center", "kaffeine_next"):
        for path in sorted((ROOT / package).glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    names = [node.module] if node.module else []
                elif isinstance(node, ast.Import):
                    names = [entry.name for entry in node.names]
                elif (isinstance(node, ast.Call)
                      and isinstance(node.func, ast.Name)
                      and node.func.id == "__import__"
                      and node.args and isinstance(node.args[0], ast.Constant)):
                    names = [node.args[0].value]
                else:
                    names = []
                for name in names:
                    if (isinstance(name, str) and
                            (name == "textcenter" or name.startswith("textcenter."))):
                        hits.append(f"{path.relative_to(ROOT)}:{node.lineno} {name}")
    return hits


class MediaStandaloneImportAndPackageContract(unittest.TestCase):
    def test_no_direct_or_deferred_canonical_text_python_imports(self):
        self.assertEqual(
            foreign_python_imports(), [],
            "STAND-03 requires a Media-owned backend; shared Text modules "
            "cannot be runtime imports in the installed Media package.")

    def test_actual_import_from_clean_media_only_source_tree(self):
        # A subprocess with -I -S plus a temporary copy of JUST Media's
        # Python/native sources: no user's Text package, model, RF or Qt.
        with tempfile.TemporaryDirectory(prefix="stand-media-import-") as tmp:
            root = Path(tmp)
            for package in ("tv_center", "kaffeine_next"):
                shutil.copytree(
                    ROOT / package, root / package,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            script = (
                "import sys; "
                f"sys.path.insert(0, {str(root)!r}); "
                "import tv_center.captions; "
                "print('STAND-MEDIA media-only caption import: OK')"
            )
            result = subprocess.run(
                [sys.executable, "-I", "-S", "-c", script],
                cwd=str(root), stdin=subprocess.DEVNULL,
                capture_output=True, text=True, timeout=15, check=False)
        self.assertEqual(
            result.returncode, 0,
            "STAND-01/03 failed clean single-app Python import. "
            "Diagnostic: " + result.stderr[-1800:])

    def test_debian_companion_excludes_entire_textcenter_package(self):
        package = (ROOT / "tv_center/packaging/build-deb.sh").read_text(
            encoding="utf-8")
        self.assertNotIn(
            '"$ROOT/textcenter"', package,
            "STAND-01/03: packaged Media cannot install an entire other "
            "TIHULU application's Python package as an implicit dependency.")

    def test_installer_no_longer_requires_text_center_repo_checkout(self):
        installer = (ROOT / "kaffeine_next/install.sh").read_text(
            encoding="utf-8")
        self.assertNotIn(
            "Tihulu/TIHULU-TEXT-CENTER.git", installer,
            "STAND-10: standalone versioned Media build must not clone "
            "the canonical Text Center source repository.")
        self.assertNotIn(
            "fix/tihulu-media-radio-dvb-2026-11-08", installer,
            "STAND-10: do not make a floating historical feature branch "
            "the default version of a standalone installer.")

    def test_media_ai_settings_and_model_storage_are_app_namespaced(self):
        ai = (ROOT / "tv_center/ai_settings.py").read_text(encoding="utf-8")
        models = (ROOT / "tv_center/model_market.py").read_text(
            encoding="utf-8")
        self.assertNotIn(
            ".config/tihulu-tv-center/", ai,
            "STAND-05: new Media release needs Media-owned settings; "
            "migrate existing legacy JSON non-destructively.")
        self.assertNotIn(
            ".local/share/tihulu-tv-center/", models,
            "STAND-05: new Media release needs Media-owned model namespace, "
            "without deleting user weights or shared custom paths.")


if __name__ == "__main__":
    unittest.main()
