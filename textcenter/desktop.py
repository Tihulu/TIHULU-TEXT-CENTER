"""Cross-platform user-local desktop window for the loopback-only Text Center.

Opens a distinct Chromium/Edge app-profile window or an isolated Firefox
window, not a headless background service. The browser owns the window; when
it exits, our own server/receivers shut down. No USB access is attempted until
a user performs an explicit receiver action in the web UI.
"""
from __future__ import annotations

import os
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile
from threading import Thread

from .core import Store
from .http_app import LocalServer


def browser_candidates(system=None, lookup=None):
    system=system or platform.system()
    which=lookup or shutil.which
    options=[]
    if system=="Darwin":
        for root in ("/Applications",str(Path.home()/"Applications")):
            for app in ("Google Chrome","Brave Browser","Microsoft Edge","Chromium"):
                exe=Path(root)/(app+".app")/"Contents"/"MacOS"/app
                if exe.is_file():options.append((str(exe),"chromium"))
    elif system=="Windows":
        for parent in (os.environ.get("PROGRAMFILES",""),
                       os.environ.get("PROGRAMFILES(X86)",""),
                       os.environ.get("LOCALAPPDATA","")):
            if not parent:continue
            for p in ("Microsoft/Edge/Application/msedge.exe",
                      "Google/Chrome/Application/chrome.exe",
                      "BraveSoftware/Brave-Browser/Application/brave.exe"):
                full=Path(parent)/p
                if full.is_file():options.append((str(full),"chromium"))
    else:
        for exe in ("brave-browser","google-chrome","chromium","chromium-browser",
                    "microsoft-edge","firefox"):
            located=which(exe)
            if located:options.append((located,"firefox" if exe=="firefox" else "chromium"))
    return options


def desktop_browser_command(executable,kind,url,profile):
    if not (url.startswith("http://127.0.0.1:") and url.endswith("/")):
        raise ValueError("Only the local Text Center address is allowed")
    if kind=="chromium":
        return [executable,"--no-first-run","--no-default-browser-check",
                "--disable-extensions","--user-data-dir="+str(profile),
                "--app="+url]
    if kind=="firefox":
        return [executable,"--no-remote","--profile",str(profile),"--new-window",url]
    raise ValueError("Unsupported window backend")


def run_desktop(*,db:Path,port:int=8787,choices=None):
    if type(port) is not int or not 1024<=port<=65535:
        raise ValueError("Desktop port must be between 1024 and 65535")
    browsers=choices if choices is not None else browser_candidates()
    if not browsers:
        raise RuntimeError("No supported window browser found. Install Chromium, Chrome, Edge or Firefox, or use python -m textcenter serve.")
    server=LocalServer(("127.0.0.1",port),Store(db))
    worker=Thread(target=server.serve_forever,kwargs={"poll_interval":0.25},
                  daemon=True,name="tihulu-text-center-desktop-server")
    worker.start()
    try:
        with tempfile.TemporaryDirectory(prefix="tihulu-text-browser-") as tmp:
            command=desktop_browser_command(browsers[0][0],browsers[0][1],
                f"http://127.0.0.1:{server.server_port}/",Path(tmp)/"profile")
            print(f"TIHULU TEXT CENTER desktop: {server.server_address[0]}:{server.server_port}")
            with subprocess.Popen(command,stdin=subprocess.DEVNULL) as browser:
                browser.wait()
    finally:
        server.postprocess.stop(wait=True)
        server.live_tv.stop()
        server.live_fm.stop(wait=True)
        server.audio.stop(wait=True)
        server.survey.stop(wait=True)
        server.rds.stop(wait=True)
        server.shutdown()
        server.server_close()
        worker.join(timeout=3)
