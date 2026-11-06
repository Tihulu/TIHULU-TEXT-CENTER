"""Explicit, cooperative FM RDS and DAB+ service auto-discovery.

Nothing happens at import or server startup. The FM workflow runs one bounded
rtl_power whole-band survey, then sequentially verifies selected spectral
candidates with the *existing* rtl_fm -> redsea supervisor. No RDS = no
confirmed FM station. The DAB workflow retunes an ALREADY-RUNNING welle-cli
loopback receiver only with explicit user consent, and restores its original
channel unless another client retuned it in the meantime.

This is receive-only. Do not claim an authoritative shared hardware lease:
non-cooperating processes require the existing fail-closed process checks.
"""
from __future__ import annotations

from datetime import datetime, timezone
import math
import re
from threading import Event, Lock, Thread
import time
import urllib.request

from .dab_bridge import DAB_HZ, DABReader, MUX_LIMIT, parse_mux, _local_get, _NoRedirect
from .channel_catalog import ChannelCatalog


class AutoScanError(RuntimeError):
    pass


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def fm_tuning_candidates(peaks: list[dict], maximum: int = 16) -> list[float]:
    """Pick a finite set of actual tuning trials; never call them stations.

    RTL power bin maxima can be offset from an FM transmitter carrier, so
    check both neighboring 100-kHz grid points. Strict bounds, dedup and
    per-request cap keep the operation finite and cancellable.
    """
    if not 1 <= maximum <= 128:
        raise ValueError("FM scan trial limit out of range")
    chosen: list[float] = []
    seen: set[int] = set()
    for peak in peaks[:128]:
        if not isinstance(peak, dict):
            continue
        hz=peak.get("frequency_hz")
        if type(hz) is not int or not 87_500_000 <= hz <= 108_000_000:
            continue
        lower=(hz//100_000)*100_000
        upper=lower+100_000
        for candidate in sorted((lower, upper),key=lambda f:abs(f-hz)):
            if (87_500_000 <= candidate <= 108_000_000
                    and candidate not in seen):
                seen.add(candidate)
                chosen.append(round(candidate/1_000_000,3))
                if len(chosen)>=maximum:
                    return chosen
    return chosen


def _station_from_recent(events: list[dict]) -> str | None:
    # Only accept an actual RDS decoder label, not our synthetic fallback.
    for event in reversed(events):
        station=event.get("station")
        if (isinstance(station,str) and station.strip()
                and not re.fullmatch(r"FM \d+(?:\.\d+)? MHz",station)):
            return station.strip()[:80]
    return None


def dab_channels_from_peaks(peaks:list[dict])->list[str]:
    """Only possible raster matches. An RF peak never confirms an ensemble."""
    selected=set()
    for peak in peaks[:80]:
        hz=peak.get("frequency_hz") if isinstance(peak,dict) else None
        if type(hz) is not int:
            continue
        channel,center=min(DAB_HZ.items(),key=lambda item:abs(item[1]-hz))
        if abs(hz-center)<=768_000:
            selected.add(channel)
    return [channel for channel in DAB_HZ if channel in selected]


def _post_channel(channel:str) -> None:
    """Only the fixed local welle-cli /channel endpoint is writable."""
    if channel not in DAB_HZ:
        raise AutoScanError("Invalid DAB raster channel")
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),_NoRedirect())
    request=urllib.request.Request(
        "http://127.0.0.1:7979/channel",
        data=channel.encode("ascii"),method="POST",
        headers={"Content-Type":"text/plain; charset=ascii"})
    try:
        with opener.open(request,timeout=2.5) as response:
            if response.status!=200:
                raise AutoScanError("Unexpected local DAB retune response")
    except (OSError,ValueError) as exc:
        raise AutoScanError("Cannot retune the existing local welle-cli receiver") from exc


class _WorkerState:
    def __init__(self):
        self._mutex=Lock()
        self._stop=Event()
        self._thread:Thread|None=None
        self._last_poll=0.0
        self._state=self._blank()

    def _blank(self)->dict:
        return {
            "status":"idle","active":False,"started_at":None,"ended_at":None,
            "error":None,"completed":0,"total":0,"current":None,"results":[],
            "note":"No automatic scan has been requested"
        }

    def _snapshot(self)->dict:
        return {**self._state,"results":[dict(x) for x in self._state["results"]]}

    def status(self, *, heartbeat=True)->dict:
        with self._mutex:
            if heartbeat and self._state["active"]:
                self._last_poll=time.monotonic()
            return self._snapshot()

    def _initialize(self,**fields):
        self._stop.clear()
        self._last_poll=time.monotonic()
        self._state={**self._blank(),"status":"running","active":True,
                     "started_at":_now(),**fields}

    def _update(self,**fields):
        with self._mutex:
            self._state.update(fields)

    def _end(self,status,error=None, note=None):
        with self._mutex:
            self._state.update(active=False,status=status,ended_at=_now(),error=error)
            if note:
                self._state["note"]=note

    def _poll_guard(self):
        if self._stop.is_set():
            raise AutoScanError("Scan stopped by user")
        with self._mutex:
            idle=time.monotonic()-self._last_poll
        if idle>18:
            raise AutoScanError("Scan stopped because the browser stopped polling")

    def stop(self,*,wait=False):
        with self._mutex:
            self._stop.set()
            result=self._snapshot()
            thread=self._thread
        if wait and thread and thread.is_alive():
            thread.join(timeout=6)
        return result


class FMAutoScanner(_WorkerState):
    """Real 87.5–108 MHz survey, then sequential RDS label verification.

    Quick verifies up to 16 candidate 100-kHz tuning frequencies; extended
    tries up to 48. An energy peak alone never becomes a station.
    """

    def __init__(self,survey,rds):
        super().__init__()
        self.survey=survey
        self.rds=rds
        self.catalog=ChannelCatalog(rds.store) if hasattr(rds,"store") and hasattr(rds.store,"connect") else None

    def start(self,mode="quick",*,consent=False):
        if consent is not True:
            raise AutoScanError("Explicit FM tuner consent required")
        if mode not in ("quick","extended","full"):
            raise ValueError("Choose quick or extended FM scan")
        with self._mutex:
            if self._state["active"]:
                raise AutoScanError("FM auto scan is already running")
            if self.rds.status(heartbeat=False)["active"]:
                raise AutoScanError("An FM RDS decoder is already running")
            if self.survey.status(heartbeat=False)["active"]:
                raise AutoScanError("A spectrum scanner is already running")
            survey_ready=self.survey.availability("fm")
            rds_ready=self.rds.availability()
            if not survey_ready["ready"] or not rds_ready["ready"]:
                raise AutoScanError(survey_ready.get("reason") if not survey_ready["ready"]
                                    else rds_ready.get("reason"))
            self._initialize(mode=mode,phase="band_survey",
                note="Measuring the complete FM band before RDS verification")
            self._thread=Thread(target=self._worker,args=(mode,),daemon=True,
                                name="tihulu-fm-auto-scan")
            self._thread.start()
            return self._snapshot()

    def _worker(self,mode):
        result_status="completed"
        error=None
        try:
            self.survey.start("fm")
            while True:
                self._poll_guard()
                status=self.survey.status(heartbeat=True)
                if not status["active"]:
                    if status["status"]!="completed":
                        raise AutoScanError(status.get("error") or "FM spectrum scan failed")
                    break
                time.sleep(0.15)
            # Expanded candidate list comes from the same genuine rtl_power
            # sweep. Never invent absent RDS names or use an Internet directory.
            peaks=status.get("fm_auto_candidates") or status["candidates"]
            candidates=fm_tuning_candidates(peaks,16 if mode=="quick" else 48 if mode=="extended" else 128)
            self._update(phase="rds_verification",total=len(candidates),
                         note=f"{len(candidates)} FM tuning trials selected from real RF measurements")
            for index, mhz in enumerate(candidates):
                self._poll_guard()
                self._update(current=mhz)
                self.rds.start(frequency_mhz=mhz,duration=10,rds2_images=False)
                while True:
                    if self._stop.is_set():
                        self.rds.stop(wait=True)
                        self._poll_guard()
                    self._poll_guard()
                    rs=self.rds.status(heartbeat=True)
                    if not rs["active"]:
                        break
                    time.sleep(0.2)
                station=_station_from_recent(rs.get("recent",[]))
                if station and rs["received_groups"]>0:
                    if self.catalog is not None:
                        try:
                            self.catalog.save_fm(
                                frequency_hz=round(mhz*1_000_000),
                                name=station,last_text=rs.get("last_text"))
                        except (ValueError,OSError):
                            pass
                    with self._mutex:
                        self._state["results"].append({
                            "frequency_mhz":mhz,"station":station,
                            "rds_verified":True,"received_groups":rs["received_groups"],
                            "last_text":rs.get("last_text"),"source":"rtl_fm_redsea"
                        })
                with self._mutex:
                    self._state["completed"]=index+1
            self._update(current=None,phase="complete",
                         note="Only stations with decoder-supplied RDS labels are listed; weak or non-RDS stations can be missed")
        except (AutoScanError,OSError,ValueError) as exc:
            error=str(exc)[:240]
            result_status="cancelled" if self._stop.is_set() or "browser stopped" in error else "error"
        except Exception:
            error="FM auto scan failed; no unverified stations were added"
            result_status="error"
        finally:
            self.rds.stop(wait=True)
            self.survey.stop(wait=True)
            self._end(result_status,error)


class DABAutoScanner(_WorkerState):
    """Sequential FIC/mux discovery through an explicitly owned welle-cli UI.

    No process launching, USB opening, port binding or unconditional preemption.
    Only POST /channel when the user selects an opt-in scan. Restore original
    channel if still owned; do not override another client that retuned.
    """

    def __init__(self,reader:DABReader,*,fetcher=None,poster=None):
        super().__init__()
        self.reader=reader
        self.catalog=ChannelCatalog(reader.store) if hasattr(reader.store,"connect") else None
        self.fetcher=fetcher or _local_get
        self.poster=poster or _post_channel
        self._original=None
        self._last_tuned=None

    def start(self,mode="full",*,dwell_seconds=8, candidates=None, consent=False):
        if consent is not True:
            raise AutoScanError("Explicit permission to retune the existing DAB receiver required")
        if mode not in ("full","detected"):
            raise ValueError("DAB scan mode must be full or detected")
        if type(dwell_seconds) not in (int,float) or not 4<=dwell_seconds<=18 or not math.isfinite(dwell_seconds):
            raise ValueError("DAB dwell must be 4–18 seconds")
        with self._mutex:
            if self._state["active"]:
                raise AutoScanError("DAB auto scan already running")
            current=self.fetcher("/channel",64).decode("ascii","replace").strip().upper()
            if current not in DAB_HZ:
                raise AutoScanError("welle-cli is not tuned to a recognized DAB Band III block")
            # Validate endpoint authenticity before we ever POST.
            parse_mux(self.fetcher("/mux.json",MUX_LIMIT),current)
            if mode=="detected":
                channels=[x for x in (candidates or []) if x in DAB_HZ]
                channels=list(dict.fromkeys(channels))[:38]
                if not channels:
                    raise AutoScanError("No DAB spectrum-block hints saved; choose full-band scan")
            else:
                channels=list(DAB_HZ)
            self._initialize(mode=mode,phase="retuning",
                total=len(channels),origin=current,current=None,restored=False,
                note="Explicitly authorized retuning of the existing local welle-cli receiver")
            self._original=current
            self._last_tuned=current
            self._thread=Thread(target=self._worker,args=(channels,float(dwell_seconds)),
                                daemon=True,name="tihulu-dab-auto-scan")
            self._thread.start()
            return self._snapshot()

    def tune(self,channel,*,consent=False):
        """Explicit user action: tune a previously decoded block for listening."""
        if consent is not True:
            raise AutoScanError("Explicit consent to retune DAB for listening is required")
        if channel not in DAB_HZ:
            raise ValueError("Unknown DAB block")
        with self._mutex:
            if self._state["active"]:
                raise AutoScanError("Cannot tune while DAB auto scanning is running")
            seen=any(row["channel"]==channel for row in self._state["results"])
            saved=bool(self.catalog and any(r["channel"]==channel
                for r in self.catalog.list(medium="dab")))
            if not seen and not saved:
                raise AutoScanError("Only a previously FIC-decoded block may be tuned")
        current=self.fetcher("/channel",64).decode("ascii","replace").strip().upper()
        parse_mux(self.fetcher("/mux.json",MUX_LIMIT),current)
        self.poster(channel)
        return {
            "channel":channel,"frequency_hz":DAB_HZ[channel],
            "receiver":"already_running_welle_cli","retuned_by_explicit_user":True,
            "player_url":"http://127.0.0.1:7979/",
            "note":"Allow DAB lock, then select Play in welle-cli for the chosen service"
        }

    def _worker(self,channels,dwell):
        status="completed"
        error=None
        externally_retuned=False
        try:
            for index,channel in enumerate(channels):
                self._poll_guard()
                # Catch external UI retuning before sending any new POST.
                current=self.fetcher("/channel",64).decode("ascii","replace").strip().upper()
                if current!=self._last_tuned:
                    externally_retuned=True
                    raise AutoScanError("DAB receiver was retuned by another client; scan stopped")
                self._update(current=channel,phase="retuning")
                self.poster(channel)
                self._last_tuned=channel
                self._update(phase="checking_fic")
                deadline=time.monotonic()+dwell
                verified=None
                while time.monotonic()<deadline:
                    self._poll_guard()
                    tuned=self.fetcher("/channel",64).decode("ascii","replace").strip().upper()
                    if tuned!=channel:
                        # Immediately after a POST, the prior channel may
                        # appear briefly; only fail after a short grace period.
                        if time.monotonic()<deadline-(dwell-2):
                            time.sleep(0.2)
                            continue
                        externally_retuned=True
                        raise AutoScanError("DAB channel changed externally during scanning")
                    try:
                        decoded=parse_mux(self.fetcher("/mux.json",MUX_LIMIT),channel)
                        if decoded["services"] and decoded["ensemble"]:
                            verified=decoded
                    except (ValueError,RuntimeError,OSError):
                        pass
                    time.sleep(0.2)
                if verified:
                    # Recheck the tuned channel before recording the services.
                    current=self.fetcher("/channel",64).decode("ascii","replace").strip().upper()
                    if current!=channel:
                        externally_retuned=True
                        raise AutoScanError("DAB changed externally; discarding candidate data")
                    with self._mutex:
                        self._state["results"].append({
                            "channel":channel,"frequency_hz":DAB_HZ[channel],
                            "ensemble":verified["ensemble"],
                            "services":verified["services"],
                            "service_count":len(verified["services"]),
                            "verification":"welle_cli_decoded_fic"
                        })
                    # Save actual FIC-decoded service metadata for the
                    # persistent local channel directory, including data services.
                    if self.catalog is not None:
                        for svc in verified["services"][:48]:
                            try:
                                self.catalog.save_dab(
                                    channel=channel,frequency_hz=DAB_HZ[channel],
                                    service_id=svc["sid"],name=svc["name"],
                                    ensemble=verified["ensemble"],
                                    audio_advertised=svc["audio_advertised"],
                                    last_text=svc["dls"])
                            except (ValueError,OSError):
                                pass
                    # Archive only actual broadcaster DLS with a decoder time.
                    for svc in verified["services"][:48]:
                        if svc["dls"] and svc["dls_received_at"]:
                            try:
                                self.reader.store.import_data({
                                    "schema_version":1,
                                    "events":[{
                                        "source_id":f"welle:{channel}:{svc['sid']}",
                                        "title":"DAB+ DLS dynamic label",
                                        "body":svc["dls"],"station":svc["name"],
                                        "language":"und","frequency_hz":DAB_HZ[channel],
                                        "medium":"dab_dls",
                                        "provenance":"welle-cli verified FIC; explicit user-approved DAB block scan",
                                        "received_at":svc["dls_received_at"]
                                    }]
                                })
                            except (OSError,ValueError):
                                pass
                self._update(completed=index+1)
            self._update(phase="complete",
                note="Actual decoded DAB services listed; MOT requires an image-bearing service and separate receiver refresh")
        except AutoScanError as exc:
            error=str(exc)[:240]
            status="cancelled" if self._stop.is_set() or "browser stopped" in error else "error"
        except (OSError,ValueError) as exc:
            error=str(exc)[:240]
            status="error"
        except Exception:
            error="DAB scan failed; no unverified services were added"
            status="error"
        finally:
            restored=False
            if not externally_retuned and self._original in DAB_HZ:
                try:
                    current=self.fetcher("/channel",64).decode("ascii","replace").strip().upper()
                    if current==self._last_tuned:
                        if current!=self._original:
                            self.poster(self._original)
                        restored=True
                except (AutoScanError,OSError,ValueError):
                    pass
            self._update(current=None,restored=restored)
            self._end(status,error,
                note="Receiver restored to original channel" if restored
                else "Receiver not restored: inspect welle-cli current channel manually")

