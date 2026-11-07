"""Live GitHub Pages release smoke: independently fetch the public web edition.

No antenna, USB access, uploaded data or private endpoints. This is an HTTP
deployment verification, not proof of a functional hardware RF decoder.
"""
from __future__ import annotations

import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = "https://tihulu.github.io/TIHULU-TEXT-CENTER/satellite_center/browser/"
RELEASE = "preview6-20261107"
EXPECTATIONS = {
    "index.html": ("Web / PWA · 0.3.0 preview6", "WebUSB", "satellite-tracking-maps"),
    "reception.html": ("Local format labels:", "file-title", "reception.mjs?v=20261107-web-format-inspection-v2"),
    "reception.mjs": ("inspectLocalFormat", "file_format_inspector.mjs", "header-mismatch"),
    "file_format_inspector.mjs": ("export async function inspectLocalFormat", "RAW RF · CU8", "header-mismatch"),
    "browser.css": (".web-runtime-strip",),
    "reception.css": (".file-format-label",),
}


def run() -> int:
    failures = []
    for path, markers in EXPECTATIONS.items():
        url = ROOT + path + "?release=" + RELEASE
        request = Request(url, headers={
            "User-Agent": "TIHULU-Satellite-Center-Release-Smoke/1.0",
            "Cache-Control": "no-cache",
        })
        try:
            with urlopen(request, timeout=15) as response:
                if response.status != 200:
                    raise ValueError(f"HTTP {response.status}")
                data = response.read(2_000_000)
                if not data:
                    raise ValueError("empty response")
                text = data.decode("utf-8")
        except (HTTPError, URLError, TimeoutError, UnicodeError, ValueError, OSError) as exc:
            failures.append(f"{path}: {type(exc).__name__} ({exc})")
            continue
        for marker in markers:
            if marker not in text:
                failures.append(f"{path}: missing expected release marker {marker!r}")
        if not any(path in f for f in failures):
            print(f"PASS {path}: public HTTP 200 and release markers")
    if failures:
        for failure in failures:
            print("FAIL", failure, file=sys.stderr)
        print("Public Pages deployment unverified; do not claim a live release.", file=sys.stderr)
        return 1
    print(f"PUBLIC WEB RELEASE VERIFIED: {ROOT} ({RELEASE})")
    print("Scope: HTTP static deployment only, NOT real RF hardware reception.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
