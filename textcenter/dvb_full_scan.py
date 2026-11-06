"""User-approved, real Linux DVB-T/T2 scan through installed dvbv5-scan.

No fabricated TV channels. Never kills external DVB tasks or touches RTL-SDR.
The operator must select a locally installed regional scan table and a frontend.
"""
from __future__ import annotations
from datetime import datetime,timezone
from pathlib import Path
from threading import Lock,Event,Thread,current_thread
import os
import platform
import re
import shutil
import signal
import subprocess
import tempfile
import time

from .channel_center import ChannelCenter


def scan_plans(roots=None):
    roots=roots if roots is not None else (
        Path("/usr/share/dvb/dvb-t"),
        Path("/usr/share/dtv-scan-tables/dvb-t"),
        Path("/usr/share/dvb"),
    )
    result={}
    for root in roots:
        folder=Path(root)
        if not folder.is_dir():continue
        for file in sorted(folder.iterdir()):
            if not file.is_file() or file.is_symlink():continue
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,119}",file.name):continue
            if not (file.name.lower().startswith(("de-","eu-","tr-","at-","be-","nl-","fr-","uk-"))):
                continue
            if file.stat().st_size>80_000:continue
            result[file.name]=str(file.resolve())
            if len(result)>=120:return result
    return result


class DVBScanError(RuntimeError):
    pass


class DVBFullScanner:
    def __init__(self, center:ChannelCenter, *, plans=None, frontend_root=None,
                 lookup=None, platform_name=None, max_seconds=360):
        self.center=center
        self.plans=plans
        self.frontend_root=Path(frontend_root) if frontend_root else Path("/dev/dvb")
        self.lookup=lookup or shutil.which
        self.platform_name=platform_name or platform.system()
        self.max_seconds=max(10,min(600,int(max_seconds)))
        self._lock=Lock()
        self._stop=Event()
        self._thread=None
        self._process=None
        self._last_seen=0
        self._state={"active":False,"status":"idle","plan":None,"adapter":None,
                    "frontend":None,"added":0,"error":None,
                    "note":"TV scan only after a real compatible DVB frontend is selected"}

    def available(self):
        plans=self.plans if self.plans is not None else scan_plans()
        devices=[]
        if self.platform_name=="Linux":
            for path in sorted(self.frontend_root.glob("adapter*/frontend*"))[:24]:
                m=re.fullmatch(r"adapter(\d+)/frontend(\d+)",str(path.relative_to(self.frontend_root)))
                if m and path.exists():
                    devices.append({"adapter":int(m.group(1)),"frontend":int(m.group(2)),
                                    "name":str(path.relative_to(self.frontend_root))})
        tool=self.lookup("dvbv5-scan")
        return {"ready":bool(tool and plans and devices),"scanning_tool":bool(tool),
                "frontends":devices,"plans":list(plans)[:120],
                "scope":"regional_dvb_t_t2_plan",
                "note":"Physical DVB-T/T2 plan scan only. Requires Linux frontend, dvbv5-scan and preinstalled regional multiplex table; no TV playback relay is created."}

    def status(self):
        with self._lock:
            if self._state["active"]:
                self._last_seen=time.monotonic()
            return dict(self._state)

    def start(self,*,plan,adapter,frontend,consent=False):
        if consent is not True:raise DVBScanError("Explicit permission to retune DVB frontend required")
        if type(adapter) is not int or type(frontend) is not int or not 0<=adapter<=15 or not 0<=frontend<=7:
            raise ValueError("Invalid DVB frontend")
        available=self.available()
        plans=self.plans if self.plans is not None else scan_plans()
        if plan not in plans or not isinstance(plan,str):
            raise DVBScanError("Select an installed regional DVB-T/T2 scan table")
        if not any(x["adapter"]==adapter and x["frontend"]==frontend for x in available["frontends"]):
            raise DVBScanError("Selected DVB frontend is no longer present")
        if not available["ready"]:raise DVBScanError("DVB scan dependencies unavailable")
        with self._lock:
            if self._state["active"]:raise DVBScanError("DVB scan already active")
            self._stop.clear()
            self._last_seen=time.monotonic()
            self._state={"active":True,"status":"scanning","plan":plan,
                         "adapter":adapter,"frontend":frontend,"added":0,
                         "error":None,"started_at":datetime.now(timezone.utc).isoformat(timespec="seconds"),
                         "note":"Scanning actual multiplexes in selected regional table"}
            self._thread=Thread(target=self._run,args=(plans[plan],plan,adapter,frontend),
                                daemon=True,name="tihulu-real-dvb-scan")
            self._thread.start()
            return dict(self._state)

    def _run(self,plan_path,plan_name,adapter,frontend):
        status="completed";error=None;added=0
        try:
            with tempfile.TemporaryDirectory(prefix="tihulu-dvbscan-") as folder:
                target=Path(folder)/"channels.conf"
                args=[self.lookup("dvbv5-scan"),"-a",str(adapter),"-f",str(frontend),
                      "-O","dvbv5","-o",str(target),plan_path]
                proc=subprocess.Popen(args,stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                    start_new_session=True,close_fds=True)
                with self._lock:self._process=proc
                deadline=time.monotonic()+self.max_seconds
                while proc.poll() is None:
                    if self._stop.is_set():raise DVBScanError("Cancelled by user")
                    with self._lock:last_seen=self._last_seen
                    if time.monotonic()-last_seen>18:
                        raise DVBScanError("TV scan stopped: browser heartbeat expired")
                    if time.monotonic()>deadline:raise DVBScanError("DVB scan timed out")
                    time.sleep(0.2)
                if proc.returncode!=0:raise DVBScanError("dvbv5-scan failed; no services stored")
                if not target.is_file() or target.stat().st_size>2_000_000:
                    raise DVBScanError("DVB scanner produced no valid bounded service file")
                data=target.read_text(encoding="utf-8",errors="replace")
                added=self.center.ingest_tv_scan(data,scan_plan=plan_name,adapter=adapter)
                if not added:raise DVBScanError("No verified DVB-T/T2 audio/video services found")
        except (DVBScanError,OSError,ValueError,subprocess.SubprocessError) as exc:
            error=str(exc)[:180]
            status="cancelled" if self._stop.is_set() else "error"
        except Exception:
            status="error";error="DVB scan failed; no assumed channels were saved"
        finally:
            with self._lock:proc=self._process;self._process=None
            if proc and proc.poll() is None:
                try:
                    os.killpg(proc.pid,signal.SIGTERM)
                    proc.wait(timeout=1.5)
                except (ProcessLookupError,ChildProcessError,OSError,subprocess.TimeoutExpired):
                    try:os.killpg(proc.pid,signal.SIGKILL)
                    except (ProcessLookupError,OSError):pass
            with self._lock:
                self._state.update(active=False,status=status,error=error,added=added,
                                   note="Scanned DVB services are historical discoveries; playback requires an authorized MPEG-TS relay")

    def stop(self,*,wait=False):
        self._stop.set()
        with self._lock:proc=self._process;thread=self._thread
        if proc and proc.poll() is None:
            try:os.killpg(proc.pid,signal.SIGTERM)
            except (ProcessLookupError,OSError):pass
        if wait and thread and thread.is_alive() and current_thread()!=thread:
            thread.join(timeout=3)
        return self.status()
