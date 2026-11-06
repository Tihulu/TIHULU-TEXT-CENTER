"""Block Satellite Center releases when shared Pages/PWA assets diverge.

Run after 'git fetch origin gh-pages:refs/remotes/origin/gh-pages'.
This inspects Git objects locally; no network requests or USB hardware access.
"""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
ASSETS = (
    "index.html",
    "reception.html",
    "reception.css",
    "reception.mjs",
    "user_protocol_ui.mjs",
    "saved_satellite_protocols.mjs",
    "satellite_calendar.mjs",
    "pass_protocol_catalog.mjs",
    "reception_catalog.mjs",
    "auto_mission.mjs",
    "auto_reception_ui.mjs",
    "results_zip.mjs",
    "browser.js",
    "browser.css",
    "manifest.webmanifest",
    "location_search.mjs",
    "satellite_maps.mjs",
    "schedule_controller.mjs",
    "satellite_images_ui.mjs",
    "satellite_imagery.mjs",
    "iq_analysis_ui.mjs",
    "iq_intelligence.mjs",
    "signal_discovery.mjs",
)


def main() -> int:
    failures = []
    for name in ASSETS:
        relative = f"satellite_center/browser/{name}"
        path = ROOT / relative
        if not path.is_file():
            failures.append(f"{relative}: missing from reviewed source")
            continue
        published = subprocess.run(
            ["git", "show", f"refs/remotes/origin/gh-pages:{relative}"],
            cwd=ROOT, capture_output=True, check=False,
        )
        if published.returncode != 0:
            failures.append(f"{relative}: missing from fetched gh-pages")
            continue
        if path.read_bytes() != published.stdout:
            failures.append(f"{relative}: content differs from published Pages")
    if failures:
        print("Satellite Center Pages/source parity FAILED:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        print("Publish the SAME reviewed static files to gh-pages before release.", file=sys.stderr)
        return 1
    print(f"Satellite Center shared UI parity OK ({len(ASSETS)} critical assets match gh-pages).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
