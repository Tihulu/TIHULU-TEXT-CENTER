"""Explicit, owned receive-only DAB process supervisor.

Only a welle-cli child started by this Text Center server can be stopped
through this module. Never terminate an independent welle-cli, readsb,
Flight Radar, tar1090 or user-owned SDR process. Browser heartbeat failure
releases the child and USB on normal tab close or browser crash.
"""
from __future__ import annotations

import os
import re
import shutil
import signal
import socket
import subprocess
import threading
import time

from .conflicts import find_receiver_conflicts


class ReceiverServiceError(RuntimeError):
    pass


class ManagedDABReceiver:
    def __init__(self, *, which=None, conflicts=None, popen=None,
                 heartbeat_timeout=18):
        self.which=which or shutil.which
        self.conflicts=conflicts or find_receiver_conflicts
        self.popen=popen or subprocess.Popen
        self.timeout=heartbeat_timeout
        self._lock=threading.RLock()
        self._process=None
        self._owner=None
        self._channel=None
        self._last_seen=0.0
        self._stop_watcher=threading.Event()
        self._watcher=threading.Thread(
            target=self._watch,daemon=True,name="tihulu-managed-dab-heartbeat")
        self._watcher.start()

    def _snapshot(self):
        process=self._process
        active=process is not None and process.poll() is None
        return {
            "active":active,
            "channel":self._channel if active else None,
            "pid":process.pid if active else None,
            "ownership":"this_text_center_server" if active else "none",
            "external_welle_untouched":True,
            "heartbeat_seconds":self.timeout,
            "note":("Only this app-owned DAB decoder will be stopped on exit."
                    if active else "No managed DAB process running. An external welle-cli is never stopped."),
        }

    def status(self, *, owner=None):
        with self._lock:
            if owner and owner==self._owner and self._process and self._process.poll() is None:
                self._last_seen=time.monotonic()
            return self._snapshot()

    @staticmethod
    def _port_busy():
        try:
            with socket.create_connection(("127.0.0.1",7979),timeout=0.2):
                return True
        except OSError:
            return False

    def start(self, channel, *, owner):
        if not isinstance(owner,str) or not 8<=len(owner)<=128 or not re.fullmatch(r"[a-zA-Z0-9_-]+",owner):
            raise ReceiverServiceError("A valid browser-owned receiver session is required")
        if not isinstance(channel,str) or not re.fullmatch(r"(?:[5-9]|1[0-3])[A-F]",channel):
            raise ReceiverServiceError("Select a valid DAB Band III block")
        with self._lock:
            if self._process is not None and self._process.poll() is None:
                raise ReceiverServiceError("This Text Center already owns a DAB receiver. Stop it first.")
            if self._port_busy():
                raise ReceiverServiceError("Port 7979 is already in use; external welle-cli must not be preempted.")
            processes=self.conflicts()
            if processes:
                names=", ".join(sorted({p.get("process","receiver") for p in processes}))[:180]
                raise ReceiverServiceError("RTL-SDR is busy: "+names+". Stop it in its own application first.")
            binary=self.which("welle-cli")
            if not binary:
                raise ReceiverServiceError("welle-cli not installed; no receiver was opened")
            options={
                "stdin":subprocess.DEVNULL,
                "stdout":subprocess.DEVNULL,
                "stderr":subprocess.DEVNULL,
                "close_fds":True,
            }
            if os.name=="nt":
                options["creationflags"]=getattr(subprocess,"CREATE_NEW_PROCESS_GROUP",0)
            else:
                options["start_new_session"]=True
            try:
                process=self.popen([binary,"-c",channel,"-PC","1","-w","7979"],**options)
            except OSError as exc:
                raise ReceiverServiceError("Could not start the installed welle-cli executable") from exc
            self._process=process
            self._owner=owner
            self._channel=channel
            self._last_seen=time.monotonic()
            return self._snapshot()

    def _stop_locked(self):
        process=self._process
        if process is not None and process.poll() is None:
            try:
                if os.name!="nt":
                    os.killpg(process.pid,signal.SIGTERM)
                else:
                    process.terminate()
                process.wait(timeout=4)
            except (ProcessLookupError,OSError,subprocess.TimeoutExpired):
                if process.poll() is None:
                    try:
                        if os.name!="nt":os.killpg(process.pid,signal.SIGKILL)
                        else:process.kill()
                        process.wait(timeout=2)
                    except (ProcessLookupError,OSError,subprocess.TimeoutExpired):
                        raise ReceiverServiceError("Could not terminate owned DAB decoder; inspect PID manually")
        self._process=None
        self._owner=None
        self._channel=None

    def stop(self, *, owner=None, owner_only=False):
        with self._lock:
            if owner_only and (not owner or owner!=self._owner):
                return {"stopped":False,"reason":"This browser tab did not start the receiver",
                        **self._snapshot()}
            running=self._process is not None and self._process.poll() is None
            self._stop_locked()
            return {"stopped":running,**self._snapshot()}

    def _watch(self):
        while not self._stop_watcher.wait(0.75):
            with self._lock:
                if self._process is None:
                    continue
                if self._process.poll() is not None:
                    self._stop_locked()
                    continue
                if time.monotonic()-self._last_seen>self.timeout:
                    try:self._stop_locked()
                    except ReceiverServiceError:pass

    def close(self):
        self._stop_watcher.set()
        self.stop()
        self._watcher.join(timeout=2)
