"""Exact bundled browser presentation + native OS SDR transport.

The HTML/CSS/JS shown by this installed Qt desktop window is the SAME source
as the public website. QWebEngine renders UI only; it never owns a WebUSB SDR.
All native radio calls go through an allowlisted in-process Qt WebChannel
and Station/rtl_sdr. No HTTP listener or standalone browser is started.

This mode necessarily embeds Chromium for the requested pixel-level UI parity.
Use 'desktop-widgets' for the fully Qt-painted, browser-engine-free fallback.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import unquote

from PyQt5.QtCore import (
    QObject,QBuffer,QIODevice,QThreadPool,QRunnable,pyqtSignal,pyqtSlot,QUrl,QTimer,Qt,
)
from PyQt5.QtWidgets import QApplication,QMainWindow,QMessageBox
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtWebEngineCore import QWebEngineUrlScheme,QWebEngineUrlSchemeHandler
from PyQt5.QtWebEngineWidgets import QWebEngineView,QWebEnginePage,QWebEngineProfile
from .__main__ import Station, PROFILES

ASSETS=Path(__file__).resolve().parent/"browser"
SCHEME=b"tihulu"
HOST="desktop"
TYPES={
    ".html":b"text/html; charset=utf-8",
    ".css":b"text/css; charset=utf-8",
    ".js":b"text/javascript; charset=utf-8",
    ".mjs":b"text/javascript; charset=utf-8",
    ".json":b"application/json",
    ".svg":b"image/svg+xml",
    ".png":b"image/png",
    ".jpg":b"image/jpeg",
    ".webp":b"image/webp",
    ".ico":b"image/x-icon",
}

def register_scheme():
    scheme=QWebEngineUrlScheme(SCHEME)
    scheme.setSyntax(QWebEngineUrlScheme.Syntax.HostAndPort)
    scheme.setFlags(QWebEngineUrlScheme.SecureScheme|
                    QWebEngineUrlScheme.LocalScheme|
                    QWebEngineUrlScheme.CorsEnabled|
                    QWebEngineUrlScheme.LocalAccessAllowed)
    QWebEngineUrlScheme.registerScheme(scheme)

def approved_asset(url):
    """Never serve traversal, symlinks outside the bundled web directory."""
    if url.scheme()!="tihulu" or url.host()!=HOST:
        return None
    name=unquote(url.path()).lstrip("/")
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,120}",name) or name.startswith("."):
        return None
    if name=="native_desktop_bridge.js":
        return None
    path=(ASSETS/name).resolve()
    try:path.relative_to(ASSETS.resolve())
    except ValueError:return None
    if path.suffix.lower() not in TYPES or not path.is_file():
        return None
    try:
        if path.stat().st_size>2_000_000:return None
    except OSError:return None
    return path

class BundledAssets(QWebEngineUrlSchemeHandler):
    def requestStarted(self,job):
        path=approved_asset(job.requestUrl())
        if path is None:
            job.fail(job.UrlNotFound)
            return
        try:
            data=path.read_bytes()
            buffer=QBuffer(job)
            buffer.setData(data)
            buffer.open(QIODevice.ReadOnly)
            job.reply(TYPES[path.suffix.lower()],buffer)
        except OSError:
            job.fail(job.RequestFailed)

class RestrictedPage(QWebEnginePage):
    def acceptNavigationRequest(self,url,nav_type,is_main_frame):
        if url.scheme()=="tihulu" and url.host()==HOST:
            return True
        if is_main_frame and nav_type==self.NavigationTypeLinkClicked:
            if url.scheme()=="https":
                QDesktopServices.openUrl(url)
            return False
        return not is_main_frame and url.scheme() in ("https","data","blob")

    def createWindow(self,kind):
        # External links open in the normal system browser, never in a
        # privileged new WebChannel page.
        return None

class RFWork(QRunnable):
    def __init__(self,bridge,request_id,command,args):
        super().__init__()
        self.bridge=bridge
        self.request_id=request_id
        self.command=command
        self.args=args

    def run(self):
        try:
            result=self.bridge.execute(self.command,self.args)
            message={"ok":True,"result":result}
        except Exception as exc:
            message={"ok":False,"error":str(exc)[:650]}
        self.bridge.completed.emit(self.request_id,json.dumps(
            message,ensure_ascii=False,default=str))

class NativeReceiver(QObject):
    completed=pyqtSignal(str,str)
    def __init__(self,station):
        super().__init__()
        self.station=station
        self.pool=QThreadPool(self)
        self.pool.setMaxThreadCount(4)
        self.completed.connect(self._finish)
        self.in_flight=set()
    reply=pyqtSignal(str,str)

    @pyqtSlot(str,str,str)
    def request(self,request_id,method,payload):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}",request_id):
            return
        if method not in {
            "status","connect","usb_open","sample","disconnect","stop",
            "capture","auto","auto_cancel","schedule","refresh","passes",
        }:
            self.reply.emit(request_id,json.dumps({
                "ok":False,"error":"Native command is not allowlisted"}))
            return
        if request_id in self.in_flight or len(self.in_flight)>=8:
            self.reply.emit(request_id,json.dumps({
                "ok":False,"error":"Native request already running or queue full"}))
            return
        try:
            args=json.loads(payload)
            if not isinstance(args,dict) or len(payload)>2048:
                raise ValueError("Native request must be a small JSON object")
        except (ValueError,TypeError) as exc:
            self.reply.emit(request_id,json.dumps({"ok":False,"error":str(exc)}))
            return
        self.in_flight.add(request_id)
        self.pool.start(RFWork(self,request_id,method,args))

    @pyqtSlot(str,str)
    def _finish(self,request_id,result):
        self.in_flight.discard(request_id)
        self.reply.emit(request_id,result)

    def execute(self,command,args):
        st=self.station
        if command=="status":
            data=st.status()
            data["native_webui"]=True
            data["hardware_transport"]="OS rtl_sdr/rtl_fm, not WebUSB"
            return data
        if command=="connect":return st.connect_receiver()
        if command=="usb_open":return st.usb_test()
        if command=="sample":
            return st.sample_test(int(args.get("frequency",137900000)))
        if command=="disconnect":return st.disconnect_receiver()
        if command=="stop":return st.request_stop()
        if command=="refresh":return st.refresh()
        if command=="passes":
            return st.plan_passes(city="Cologne",
                lat=float(args["lat"]),lon=float(args["lon"]),
                hours=int(args.get("hours",24)),
                elevation=float(args.get("elevation",15)))
        if command=="capture":
            frequency=int(args["frequency"])
            profile=next((key for key,setting in PROFILES.items()
                          if setting.get("freq")==frequency),None)
            if not profile:
                raise ValueError("No supported native receiving profile at this frequency")
            raw=args.get("raw") is True
            wav=args.get("wav") is True
            mode=("iq_and_fm_wav" if raw and wav else
                  "iq" if raw else
                  "sstv_audio" if wav and profile=="iss_sstv" else
                  "fm_audio" if wav else "survey")
            seconds=int(args.get("seconds",60))
            rate=int(args.get("rate",1024000))
            return st.capture(profile,mode,seconds,sample_rate=rate)
        if command=="auto":
            groups={
                "iss-images":["iss-sstv"],
                "images":["meteor-m2-3","meteor-m2-4","iss-sstv"],
                "messages":["iss-aprs"],
                "voice":["iss-voice"],
                "all":list(st.AUTO_DOWNLINK_PROFILES) if hasattr(st,"AUTO_DOWNLINK_PROFILES")
                    else ["meteor-m2-3","meteor-m2-4","iss-sstv","iss-aprs","iss-voice"],
            }
            group=args.get("group")
            if group not in groups:raise ValueError("Select a published auto target")
            return st.auto_schedule(
                groups[group],city="Cologne",
                lat=float(args["lat"]),lon=float(args["lon"]),
                hours=int(args.get("hours",24)),elevation=float(args.get("elevation",15)),
                duration_seconds=int(args["seconds"]) if args.get("seconds") else None,
                coverage_goal=args.get("goal","full"),
                iss_record_format=args.get("format","wav"))
        if command=="auto_cancel":return st.cancel_auto_missions()
        if command=="schedule":
            # All scheduled passes must match native TLE-derived geometry.
            data=st.plan_passes(
                city="Cologne",lat=float(args["lat"]),lon=float(args["lon"]),
                hours=int(args.get("hours",24)),elevation=5)
            norad=int(args["norad"])
            at=int(args["aos_millis"])/1000
            from datetime import datetime,timezone
            possible=[p for p in data["predictions"] if p["norad"]==norad
                      and abs(datetime.fromisoformat(p["aos"]).timestamp()-at)<180]
            if not possible:
                raise ValueError("TLE event differs from browser prediction. "
                                 "Refresh TLE and recalculate passes.")
            frequency=int(args["frequency"])
            profile=next((key for key in possible[0]["profiles"]
                          if PROFILES[key].get("freq")==frequency),None)
            if not profile:raise ValueError("No verified matching receiver preset")
            raw=args.get("raw") is True
            wav=args.get("wav") is True
            mode=("iq_and_fm_wav" if raw and wav else
                  "iq" if raw else
                  "sstv_audio" if wav and profile=="iss_sstv" else
                  "fm_audio" if wav else "survey")
            seconds=int(args.get("seconds",60))
            starts=datetime.fromtimestamp(int(args["when_millis"])/1000,timezone.utc).isoformat()
            return st.schedule(possible[0]["id"],profile,mode,starts,seconds,
                               sample_rate=int(args.get("rate",1024000)))
        raise ValueError("Unsupported native operation")

class ExactWebWindow(QMainWindow):
    def __init__(self,station=None):
        super().__init__()
        self.station=station or Station()
        self.setWindowTitle("TIHULU Satellite Center · native SDR · exact web UI")
        self.resize(1340,900)
        self.web=QWebEngineView(self)
        self.setCentralWidget(self.web)
        self.profile=QWebEngineProfile(self)  # ephemeral: no persistent browser profile
        self.assets=BundledAssets(self)
        self.profile.installUrlSchemeHandler(SCHEME,self.assets)
        self.page=RestrictedPage(self.profile,self.web)
        self.web.setPage(self.page)
        self.receiver=NativeReceiver(self.station)
        self.channel=QWebChannel(self.page)
        self.channel.registerObject("nativeReceiver",self.receiver)
        self.page.setWebChannel(self.channel)
        self.load_ok=False
        self.bridge_ready=False
        self.web.loadFinished.connect(self._load_finished)
        self.web.setUrl(QUrl("tihulu://desktop/index.html"))

    def _load_finished(self,ok):
        self.load_ok=bool(ok)
        if not ok:
            QMessageBox.warning(self,"TIHULU native web UI",
                "Bundled local web interface could not be loaded.")
            return
        js=(Path(__file__).parent/"native_desktop_bridge.js").read_text(
            encoding="utf-8")
        self.page.runJavaScript(js)

    def closeEvent(self,event):
        try:
            self.station.close()
        finally:
            super().closeEvent(event)

def main(argv=None):
    register_scheme()
    parser=argparse.ArgumentParser()
    parser.add_argument("--smoke",action="store_true")
    parser.add_argument("--screenshot",default="")
    opts=parser.parse_args(argv)
    app=QApplication.instance() or QApplication(sys.argv[:1])
    window=ExactWebWindow()
    window.show()
    if not opts.smoke:return app.exec_()
    outcome={"ok":False}
    def inspect():
        window.page.runJavaScript(
            "Boolean(document.querySelector('#auto-workflow') && "
            "document.querySelector('#city-query') && "
            "document.querySelector('#passes') && window.nativeWebBridgeReady)",
            lambda result:complete(bool(result)))
    def complete(ok):
        if outcome.get("done"):return
        outcome["done"]=True;outcome["ok"]=ok
        if ok and opts.screenshot:
            window.grab().save(opts.screenshot,"PNG")
        app.exit(0 if ok else 1)
    # The bundled scheme may load before the window is shown; schedule the
    # check independently of loadFinished to avoid race-dependent CI failures.
    QTimer.singleShot(3500,inspect)
    QTimer.singleShot(14000,lambda:complete(False))
    return app.exec_()

if __name__=="__main__":
    sys.exit(main())
