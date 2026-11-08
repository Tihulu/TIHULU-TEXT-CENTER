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
import time
from datetime import datetime, timezone
from pathlib import Path
import re
import sys
import tempfile
from urllib.parse import unquote, urlencode
from urllib.request import Request, urlopen

from PyQt5.QtCore import (
    QObject,QBuffer,QIODevice,QThreadPool,QRunnable,pyqtSignal,pyqtSlot,QUrl,QTimer,Qt,
)
from PyQt5.QtWidgets import QApplication,QMainWindow,QMessageBox
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtWebEngineCore import QWebEngineUrlScheme,QWebEngineUrlSchemeHandler
from PyQt5.QtWebEngineWidgets import QWebEngineView,QWebEnginePage,QWebEngineProfile
from .__main__ import Station, PROFILES, SOURCE_URLS, parse_tle, family, selectable
from .native_orbit import OrbitEngine

ASSETS=Path(__file__).resolve().parent/"browser"
SCHEME=b"tihulu"
HOST="desktop"
TYPES={
    # Qt WebEngine UrlRequestJob.reply takes a bare MIME type, not an
    # HTTP Content-Type header with parameters. With 'charset=utf-8'
    # appended, Qt rendered HTML as source text instead of a DOM.
    ".html":b"text/html",
    ".css":b"text/css",
    ".js":b"text/javascript",
    ".mjs":b"text/javascript",
    ".json":b"application/json",
    ".geojson":b"application/geo+json",
    ".webmanifest":b"application/manifest+json",
    ".svg":b"image/svg+xml",
    ".png":b"image/png",
    ".jpg":b"image/jpeg",
    ".webp":b"image/webp",
    ".ico":b"image/x-icon",
}

def register_scheme():
    scheme=QWebEngineUrlScheme(SCHEME)
    scheme.setSyntax(QWebEngineUrlScheme.Syntax.HostAndPort)
    # Qt 5.15 refuses HostAndPort schemes without a default port.
    # This port is internal URL parsing only; NO TCP/HTTP listener exists.
    scheme.setDefaultPort(443)
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
        source=job.requestUrl()
        path=approved_asset(source)
        print("TIHULU-ASSET",source.toString(), "host="+source.host(),
              "path="+source.path(),
              "file="+str(path) if path else "BLOCKED",flush=True)
        if path is None:
            job.fail(job.UrlNotFound)
            return
        try:
            data=path.read_bytes()
            buffer=QBuffer(job)
            buffer.setData(data)
            buffer.open(QIODevice.ReadOnly)
            print("TIHULU-ASSET reply",len(data),str(path.suffix),flush=True)
            job.reply(TYPES[path.suffix.lower()],buffer)
        except OSError as exc:
            print("TIHULU-ASSET failure",str(exc),flush=True)
            job.fail(job.RequestFailed)

class RestrictedPage(QWebEnginePage):
    def javaScriptConsoleMessage(self,level,message,line,source):
        # Actionable GUI CI messages, including missing JS modules or
        # WebChannel transport. Native RF bytes never enter this log.
        print("TIHULU-WEB-UI JS",int(level),str(source)[-130:],
              line,str(message)[:450],flush=True)

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
    def __init__(self,station,parent=None):
        super().__init__(parent)
        self.station=station
        self.orbit_engine=OrbitEngine(station)
        self.pool=QThreadPool(self)
        self.pool.setMaxThreadCount(4)
        self.completed.connect(self._finish)
        self.in_flight=set()
        self.radio_request=None
    reply=pyqtSignal(str,str)

    @pyqtSlot(str,str,str)
    def request(self,request_id,method,payload):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}",request_id):
            return
        if method not in {
            "status","connect","usb_open","sample","disconnect","stop",
            "capture","auto","auto_cancel","schedule","refresh","passes","geocode",
            "tle_catalog","orbit_snapshot","pass_preview","tle_custom","world_outline","tle_import",
            "cancel_schedule",
        }:
            self.reply.emit(request_id,json.dumps({
                "ok":False,"error":"Native command is not allowlisted"}))
            return
        radio_methods={"connect","usb_open","sample","capture","auto","schedule"}
        if method in radio_methods and self.radio_request is not None:
            self.reply.emit(request_id,json.dumps({
                "ok":False,"error":"Another native SDR operation is still running. "
                "Finish Connect/Verify before opening a second USB test. "
                "Use Stop if necessary, then refresh receiver status."}))
            return
        if request_id in self.in_flight or len(self.in_flight)>=8:
            self.reply.emit(request_id,json.dumps({
                "ok":False,"error":"Native request already running or queue full"}))
            return
        try:
            args=json.loads(payload)
            if not isinstance(args,dict) or len(payload)>(400000 if method=="tle_import" else 2048):
                raise ValueError("Native request must be a small JSON object")
        except (ValueError,TypeError) as exc:
            self.reply.emit(request_id,json.dumps({"ok":False,"error":str(exc)}))
            return
        # A remote JS import cannot silently cause hardware acquisition:
        # every operation that enables/starts or schedules physical receiver
        # acquisition requires an actual OS-native user confirmation.
        if method in ("connect","capture","auto","schedule"):
            description={
                "connect":"Verify USB + real IQ and enable future RF reception",
                "capture":"Start physical radio acquisition and write local data",
                "auto":"Schedule future automatic real SDR recordings",
                "schedule":"Schedule a specific TLE-backed RF pass recording",
            }[method]
            if QMessageBox.question(
                self.parent(),"Native RTL-SDR authorization",
                description+"?\n\nThis uses OS tools and local storage, "
                "not WebUSB or an Internet receiver.\n"
                "No satellite transmission or decoded media is presumed.",
                QMessageBox.Yes|QMessageBox.No,QMessageBox.No
            )!=QMessageBox.Yes:
                self.reply.emit(request_id,json.dumps({
                    "ok":False,"error":"Native RF action canceled by operator"}))
                return
        self.in_flight.add(request_id)
        if method in radio_methods:
            self.radio_request=request_id
        self.pool.start(RFWork(self,request_id,method,args))

    @pyqtSlot(str,str)
    def _finish(self,request_id,result):
        self.in_flight.discard(request_id)
        if self.radio_request==request_id:
            self.radio_request=None
        self.reply.emit(request_id,result)

    def _cache_manual_tles(self,text):
        """Bounded, explicitly operator-imported TLEs; never antenna evidence."""
        if not isinstance(text,str) or not text or len(text.encode("utf-8"))>350000:
            raise ValueError("Imported local TLE text must be 1–350000 bytes")
        incoming=parse_tle(text,limit=200)
        if not incoming:raise ValueError("No valid matching TLE line pairs found")
        target=self.station.directory/"manual.tle"
        with self.station.lock:
            previous=[]
            if target.is_file() and target.stat().st_size<=350000:
                previous=parse_tle(target.read_text(encoding="ascii",errors="replace"),limit=200)
            chosen={}
            for record in incoming+previous:
                chosen.setdefault(record["id"],record)
                if len(chosen)>=80:break
            content="".join(row["name"].encode("ascii","replace").decode("ascii")+"\n"+
                            row["l1"]+"\n"+row["l2"]+"\n"
                            for row in chosen.values())
            tmp=None
            try:
                with tempfile.NamedTemporaryFile(
                    mode="w",encoding="ascii",dir=self.station.directory,
                    prefix=".manual-tle-",delete=False
                ) as handle:
                    tmp=Path(handle.name)
                    handle.write(content)
                os.chmod(tmp,0o600)
                os.replace(tmp,target)
            finally:
                if tmp is not None:tmp.unlink(missing_ok=True)
        self.orbit_engine.invalidate()
        return {"count":len(incoming),"cached_norad_ids":list(chosen.keys()),
                "source":"operator-imported-local-TLE",
                "note":"Local orbital catalog only. Does not receive RF or identify satellites via antenna."}

    def execute(self,command,args):
        st=self.station
        if command=="status":
            data=st.status()
            data["native_webui"]=True
            data["hardware_transport"]="OS rtl_sdr/rtl_fm, not WebUSB"
            return data
        if command=="tle_import":
            return self._cache_manual_tles(args.get("text"))
        if command=="world_outline":
            # Load the packaged public-domain world map directly from disk.
            # This is needed when Chromium disallows fetch() from tihulu://.
            path=ASSETS/"natural-earth-land-110m.geojson"
            if not path.is_file() or path.stat().st_size>350000:
                raise RuntimeError("Bundled Natural Earth land map missing or oversized")
            data=json.loads(path.read_text(encoding="utf-8"))
            if data.get("type")!="FeatureCollection" or not isinstance(data.get("features"),list) or len(data["features"])<100:
                raise ValueError("Bundled Natural Earth map data is invalid")
            return data
        if command=="tle_catalog":
            # The desktop is NOT a website: never fetch CelesTrak from a
            # tihulu:// web page. Use bounded native HTTPS and local cache.
            refresh_report=st.refresh()  # explicit user action only
            result=[]
            errors=[]
            sources={}
            caps={"iss":1,"meteor3":1,"meteor4":1,
                  "amateur":80,"iridium":24}
            for source in SOURCE_URLS:
                path=st.directory/(source+".tle")
                report=refresh_report.get(source,{})
                age_days=None
                if path.is_file():
                    age_days=max(0,(time.time()-path.stat().st_mtime)/86400)
                sources[source]={"downloaded":bool(report.get("cached")),
                                 "cached":path.is_file(),
                                 "age_days":round(age_days,2) if age_days is not None else None,
                                 "error":report.get("error")}
                if not path.is_file() or (age_days is not None and age_days>7):
                    errors.append(source+": no fresh orbital elements available")
                    continue
                try:
                    text=path.read_text(encoding="ascii",errors="replace")
                    items=parse_tle(text,limit=300)
                    accepted=0
                    for item in items:
                        if not selectable(source,item):continue
                        result.append({**item,"family":family(source,item)})
                        accepted+=1
                        if accepted>=caps[source]:break
                    if accepted==0:errors.append(source+": no eligible TLEs")
                except (OSError,ValueError) as exc:
                    errors.append(source+": "+str(exc)[:100])
                if report.get("error"):
                    errors.append(source+": native HTTPS failed; using last valid cache ("+
                                  str(report["error"])[:90]+")")
            manual=st.directory/"manual.tle"
            if manual.is_file() and manual.stat().st_size<=350000:
                age_days=max(0,(time.time()-manual.stat().st_mtime)/86400)
                sources["manual"]={"downloaded":False,"cached":True,
                                   "age_days":round(age_days,2),"error":None}
                if age_days<=7:
                    for item in parse_tle(manual.read_text(encoding="ascii",errors="replace"),limit=80):
                        result.append({**item,"family":family("manual",item)})
                else:errors.append("manual: imported TLE cache is over 7 days old")
            self.orbit_engine.invalidate()
            return {"entries":result,"sources":sources,"warnings":errors,
                    "source":"native_https_celestrak_and_disk_cache",
                    "note":"Orbital predictions only. No RF data or satellite images were received."}
        if command=="tle_custom":
            norad=args.get("norad")
            if type(norad) is not int or not 1000<=norad<=99999:
                raise ValueError("Native custom TLE lookup requires a five-digit NORAD ID")
            url="https://celestrak.org/NORAD/elements/gp.php?CATNR="+str(norad)+"&FORMAT=TLE"
            with urlopen(Request(url,headers={"User-Agent":"TIHULU-Satellite-Center/0.3"}),timeout=10) as response:
                if response.geturl().split("/")[2].lower() not in ("celestrak.org","www.celestrak.org"):
                    raise ValueError("Unapproved CelesTrak redirect")
                content=response.read(70001)
            if len(content)>70000:raise ValueError("Custom TLE response exceeds 70 kB")
            rows=[row for row in parse_tle(content.decode("ascii","strict"),limit=100)
                  if row["id"]==norad]
            if not rows:raise ValueError("No matching current TLE at CelesTrak")
            self._cache_manual_tles(content.decode("ascii","strict"))
            return {"entries":[{**row,"family":family("manual",row)} for row in rows[:1]],
                    "source":"native_celestrak_custom_norad"}
        if command=="cancel_schedule":
            job_id=args.get("job_id")
            if not isinstance(job_id,str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,40}",job_id):
                raise ValueError("Select a valid native pending job")
            return st.cancel(job_id)
        if command=="pass_preview":
            lat=float(args.get("lat"));lon=float(args.get("lon"))
            norad=args.get("norad")
            aos_ms=args.get("aos_ms");los_ms=args.get("los_ms")
            if type(norad) is not int or not 1000<=norad<=99999:
                raise ValueError("Selected satellite NORAD number required")
            if type(aos_ms) not in (int,float) or type(los_ms) not in (int,float):
                raise ValueError("AOS and LOS must be numeric UTC milliseconds")
            if not 0 < los_ms-aos_ms <= 1500000:
                raise ValueError("Pass preview limited to a real 25 minute window")
            if abs(time.time()*1000-aos_ms)>86400000*4:
                raise ValueError("Pass preview must be within four days of now")
            start=datetime.fromtimestamp(aos_ms/1000,timezone.utc)
            end=datetime.fromtimestamp(los_ms/1000,timezone.utc)
            return self.orbit_engine.preview_pass(lat,lon,norad,start,end)
        if command=="orbit_snapshot":
            lat=float(args.get("lat"))
            lon=float(args.get("lon"))
            at_ms=args.get("at_ms")
            if type(at_ms) not in (int,float) or not -86400000*365*1000<at_ms<4102444800000:
                raise ValueError("Invalid orbital observation timestamp")
            if abs(time.time()*1000-at_ms)>86400000*2:
                raise ValueError("Orbit simulation limited to ±48 hours from current UTC")
            at=datetime.fromtimestamp(at_ms/1000,timezone.utc)
            with_tracks=args.get("tracks") is True
            return self.orbit_engine.snapshot(
                lat,lon,at,family_filter="all",minimum_el=-90,
                with_track=with_tracks,track_scope="all")
        if command=="geocode":
            # Explicit operator-initiated worldwide search; no GPS lookup.
            # Provider coordinates are passed through, never inferred.
            name=args.get("name")
            country=args.get("country","all")
            if not isinstance(name,str) or not 2<=len(name.strip())<=100:
                raise ValueError("Geocoding requires a place name (2–100 characters)")
            if not isinstance(country,str) or country not in ("all","DE","TR"):
                raise ValueError("Unsupported geocoding country filter")
            params={"name":name.strip(),"count":10,"language":"en","format":"json"}
            if country!="all":params["countryCode"]=country
            url="https://geocoding-api.open-meteo.com/v1/search?"+urlencode(params)
            request=Request(url,headers={"User-Agent":"TIHULU-Satellite-Center/0.3"})
            try:
                with urlopen(request,timeout=9) as response:
                    if response.status!=200:raise ValueError("Geocoding HTTP "+str(response.status))
                    raw=response.read(131073)
                if len(raw)>131072:raise ValueError("Geocoding response too large")
                payload=json.loads(raw.decode("utf-8"))
            except Exception as exc:
                raise ValueError("Open-Meteo geocoding HTTPS request failed: "+str(exc)[:180]) from exc
            if not isinstance(payload,dict):raise ValueError("Invalid geocoding response")
            if payload.get("error"):raise ValueError(str(payload.get("reason","Geocoding provider error"))[:180])
            return {"results":payload.get("results",[])[:10]}
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
                elevation=float(args.get("elevation",15)),
                window=args.get("window"))
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
            # Match the exact elevation cutoff used by the displayed pass
            # planner. Hardcoding 5 degrees shifted AOS by minutes when the
            # user planned at 15/20/30 degrees and rejected valid schedules.
            elevation=float(args.get("elevation",5))
            if not 0<=elevation<=75:
                raise ValueError("Native schedule elevation must be 0–75 degrees")
            data=st.plan_passes(
                city="Cologne",lat=float(args["lat"]),lon=float(args["lon"]),
                hours=int(args.get("hours",24)),elevation=elevation)
            norad=int(args["norad"])
            at=int(args["aos_millis"])/1000
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
        self.receiver=NativeReceiver(self.station,self)
        self.channel=QWebChannel(self.page)
        self.channel.registerObject("nativeReceiver",self.receiver)
        self.page.setWebChannel(self.channel)
        self.load_ok=False
        self.bridge_ready=False
        self.web.loadFinished.connect(self._load_finished)
        self.web.setUrl(QUrl("tihulu://desktop/index.html"))

    def _load_finished(self,ok):
        print("TIHULU-WEB-UI loaded",bool(ok),flush=True)
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
    check_script="""JSON.stringify({
        loaded:document.readyState,
        title:document.title,
        htmlLen:document.documentElement?.outerHTML?.length || 0,
        bodyLen:document.body?.innerHTML?.length || 0,
        url:location.href,
        auto:!!document.getElementById('auto-workflow'),
        city:!!document.getElementById('city-query'),
        passes:!!document.getElementById('passes'),
        nativeReady:!!window.nativeWebBridgeReady,
        transport:!!window.qt?.webChannelTransport,
        channelScript:!!window.QWebChannel,
        log:document.getElementById('log')?.textContent?.slice(0,900)
    })"""
    def inspect():
        window.page.runJavaScript(check_script,report)
    def report(serialized):
        if outcome.get("done"):return
        try:data=json.loads(serialized)
        except (TypeError,ValueError):data={"error":"empty JS response","raw":str(serialized)}
        print("TIHULU-WEB-UI diagnostics",json.dumps(data),flush=True)
        ready=all(data.get(k) is True for k in
                  ("auto","city","passes","nativeReady","transport","channelScript"))
        if ready:
            complete(True)
    def complete(ok):
        if outcome.get("done"):return
        outcome["done"]=True;outcome["ok"]=ok
        if opts.screenshot:
            window.grab().save(opts.screenshot,"PNG")
            print("TIHULU-WEB-UI screenshot",opts.screenshot,flush=True)
        app.exit(0 if ok else 1)
    QTimer.singleShot(2500,inspect)
    QTimer.singleShot(5500,inspect)
    QTimer.singleShot(11000,inspect)
    QTimer.singleShot(14000,lambda:complete(False))
    return app.exec_()

if __name__=="__main__":
    sys.exit(main())
