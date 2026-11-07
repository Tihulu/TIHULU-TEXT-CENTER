/* Same-origin local companion OR static Pages three-step UX.
 * Never fake a successful scan, CRC packet or satellite Earth image.
 * Decoding is local to this browser, except for explicitly authorized
 * companion SatDump/APRS archived products on localhost.
 */
import {AUTO_PRESETS} from "./auto_mission.mjs?v=20261106-iss-npu-release-v1";
import {discoverCu8Contents,discoveryReportJson} from "./signal_discovery.mjs";
import {parseRecordingName} from "./satellite_imagery.mjs";
import {decodeRobot36WithCompute} from "./compute_backends.mjs";
import {initComputeSelector} from "./compute_selector.mjs";
import {initStationLocationUI} from "./location_search.mjs";
import {localDayKey,shiftCalendarDay,renderSatelliteCalendar} from "./satellite_calendar.mjs?v=20261106-calendar-zip-v2";
import {createResultsZip} from "./results_zip.mjs";
import {durationToSeconds} from "./segmented_capture.mjs?v=20261107-segments-v1";

const $=id=>document.getElementById(id);
const nativeHost=()=>window.location.protocol==="http:" && window.location.port==="8791" && ["127.0.0.1","localhost"].includes(window.location.hostname);
const signalMax=128*1024*1024;
const fileType=name=>String(name||"").toLowerCase().split(".").pop();
const textNode=(tag,value,parent,cls)=>{
  const e=document.createElement(tag);e.textContent=String(value);
  if(cls)e.className=cls;if(parent)parent.append(e);return e;
};
function postFile(blob,name){
  const uri=URL.createObjectURL(blob);
  const a=document.createElement("a");a.href=uri;a.download=name;
  document.body.append(a);a.click();a.remove();
  setTimeout(()=>URL.revokeObjectURL(uri),30000);
}
async function nativeApi(path,data=null){
  if(!nativeHost())throw Error("The optional native service is not accessible from this hosted Pages tab.");
  const options={cache:"no-store"};
  if(data!==null){
    const auth=await fetch("/api/status",{cache:"no-store"});
    if(!auth.ok)throw Error("Local receiver status HTTP "+auth.status);
    const info=await auth.json();
    if(!info.csrf)throw Error("Local receiver CSRF token unavailable");
    options.method="POST";
    options.headers={"Content-Type":"application/json"};
    options.body=JSON.stringify({csrf:info.csrf,...data});
  }
  const response=await fetch(path,options);
  const payload=await response.json();
  if(!response.ok||payload.error)throw Error(payload.error||"HTTP "+response.status);
  return payload;
}
export function initAutoReceptionUI({getSelectedFile=()=>null,fileInput=$("local-file")}={}){
  let controller=null,busy=false,waitingForSelection=false;
  const audioPreviewUrls=[];
  const releasePreviews=()=>{for(const url of audioPreviewUrls)URL.revokeObjectURL(url);audioPreviewUrls.length=0;};
  window.addEventListener("pagehide",releasePreviews);
  const state={discovery:[],actualImages:[],nativeDecodeReports:[],packetText:[],audioFiles:[],warnings:[],name:""};
  const autoLength=$("auto-recording-seconds"),autoUnit=$("auto-recording-unit");
  let priorLengthUnit="seconds";
  autoUnit.addEventListener("change",()=>{
    const raw=autoLength.value.trim();
    if(raw){
      const previous=Number(raw)*(priorLengthUnit==="minutes"?60:1);
      autoLength.value=autoUnit.value==="minutes"?
        String(Number((previous/60).toFixed(6))):String(Math.round(previous));
    }
    priorLengthUnit=autoUnit.value;
    autoLength.max=autoUnit.value==="minutes"?"15":"900";
    autoLength.min=autoUnit.value==="minutes"?"0.133334":"8";
    autoLength.step=autoUnit.value==="minutes"?"0.000001":"1";
  });
  const readAutoLength=({blank=null}={})=>{
    const raw=autoLength.value.trim();
    return raw?durationToSeconds(raw,autoUnit.value,{min:8,max:900}):blank;
  };
  const message=value=>{$("auto-mission-status").textContent=String(value);};
  const jobs=$("auto-mission-jobs"),output=$("auto-mission-output");
  const computeSelector=initComputeSelector("auto",{
    capabilitiesProvider:nativeHost()?async()=>{
      const info=await nativeApi("/api/status");return info.compute;
    }:null
  });

  const runtime=$("auto-runtime"),receiver=$("auto-receiver"),decoders=$("auto-decoders");
  const formatGroup=$("reception-browser-formats"),formatNote=$("reception-native-format-note");
  const selectedFormats=()=>({raw:$("reception-auto-raw").checked,
                             wav:$("reception-auto-wav").checked});
  const updateFormatSummary=()=>{
    const {raw,wav}=selectedFormats();
    $("reception-format-summary").textContent=
      raw&&wav?"CU8 + WAV selected · TWO separate files from ONE real WebUSB recording.":
      raw?"CU8 only · one raw RF/IQ file.":
      wav?"WAV only · one FM-demodulated audio file.":
      "No file selected · choose WAV or CU8 to save a real ISS recording.";
  };
  for(const id of ["reception-auto-raw","reception-auto-wav"]){
    $(id).addEventListener("change",updateFormatSummary);
  }
  updateFormatSummary();
  if(nativeHost()){
    formatGroup.hidden=true;
    formatNote.hidden=false;
  }
  if(nativeHost()){
    runtime.textContent="Native companion · persistent scheduler";
    receiver.textContent="Receiver: checking physical SDR status…";
    decoders.textContent="Decoders: checking installed tools…";
    void nativeApi("/api/status").then(s=>{
      receiver.textContent="Receiver: "+(s.session?.active?"busy capturing":s.busy?"busy or external process":"idle / not claimed");
      decoders.textContent="SatDump: "+(s.tools?.satdump?"installed":"missing")+
        " · APRS: "+(s.tools?.["multimon-ng"]?"installed":"missing")+
        " · Robot36: browser experimental";
    }).catch(()=>{receiver.textContent="Receiver: companion unavailable";});
  }else{
    runtime.textContent="Web / PWA · foreground-only scheduler";
    receiver.textContent=(window.isSecureContext&&navigator.usb)?
      "WebUSB API available; receiver permission NOT yet granted":
      "No direct WebUSB (Firefox/Safari or unsupported platform)";
    decoders.textContent="Robot36 experimental · Meteor LRPT needs local SatDump · APRS requires native decoder";
  }

  const analyze=$("auto-mission-analyze"),extract=$("auto-mission-extract");
  const zipButton=$("auto-mission-zip"),zipStatus=$("auto-mission-zip-status");
  const cancel=$("auto-mission-cancel");

  function begin(){
    if(busy)throw Error("Analysis already in progress");
    busy=true;controller=new AbortController();
    analyze.disabled=true;extract.disabled=true;zipButton.disabled=true;cancel.disabled=false;
    zipStatus.textContent="Analysis running; results archive is not ready.";
    jobs.hidden=false;output.replaceChildren();
    state.discovery=[];state.actualImages=[];state.nativeDecodeReports=[];state.packetText=[];state.audioFiles=[];state.warnings=[];
  }
  function finish(){
    busy=false;controller=null;
    analyze.disabled=false;cancel.disabled=true;
    extract.disabled=!(state.discovery.length||state.actualImages.length||state.nativeDecodeReports.length||state.packetText.length||state.audioFiles.length||state.warnings.length);
    zipButton.disabled=extract.disabled;
    zipStatus.textContent=zipButton.disabled?
      "No extracted media/data yet; original recordings remain available separately.":
      "Results ready to inspect in Step 3 and export together as ZIP (including source evidence).";
  }
  function station(){
    const lat=Number($("auto-lat").value),lon=Number($("auto-lon").value);
    if(!$("auto-lat").value.trim()||!$("auto-lon").value.trim()||
      !Number.isFinite(lat)||!Number.isFinite(lon)||Math.abs(lat)>90||Math.abs(lon)>180)
      throw Error("Enter a valid latitude and longitude or use device location.");
    return {lat,lon};
  }
  initStationLocationUI({
    ids:{city:"auto-city-mode",lat:"auto-lat",lon:"auto-lon"},
    onStationChanged:()=>message("Station updated. Existing future schedules retain their original observer and must be edited or re-planned explicitly."),
    log:()=>{}
  });

  // Live only while this tab is displayed; refreshing does not claim the SDR.
  const calendarDay=$("auto-calendar-date");
  const calendarGrid=$("auto-calendar-grid");
  let calendarJobs=[];
  calendarDay.value=localDayKey(new Date());
  const calendarChoices={
    "25544":[["iss-sstv","ISS SSTV · event only"],["iss-aprs","ISS APRS messages"],["iss-voice","ISS FM voice"]],
    "57166":[["meteor-m2-3","Meteor-M2-3 LRPT Earth image"]],
    "59051":[["meteor-m2-4","Meteor-M2-4 LRPT Earth image"]]
  };
  function startLocal(date){
    const d=new Date(date);
    return localDayKey(d)+"T"+String(d.getHours()).padStart(2,"0")+":"+String(d.getMinutes()).padStart(2,"0");
  }
  function editNativeAutoJob(job,card){
    if(!nativeHost()||job.state!=="pending"||!job.mission_id){
      message("Only pending automatic native capture tasks can change time/protocol. Browser jobs are editable on the receiver page.");
      return;
    }
    const old=card.querySelector(".calendar-edit");
    if(old){old.remove();return;}
    const form=document.createElement("form");form.className="calendar-edit";
    const when=document.createElement("input");when.type="datetime-local";when.required=true;
    when.value=startLocal(job.run_at||job.aos);
    const protocols=document.createElement("select");
    for(const [id,label] of calendarChoices[String(job.pass_id||"").split(":")[0]]||[]){
      const option=document.createElement("option");option.value=id;option.textContent=label;
      protocols.append(option);
    }
    protocols.value=job.mission_id;
    if(!protocols.value&&protocols.options.length)protocols.selectedIndex=0;
    const lbl=(name,control)=>{
      const label=document.createElement("label");label.textContent=name;label.append(control);form.append(label);
    };
    lbl("Start time · local, inside original pass",when);
    lbl("Published receiver protocol",protocols);
    const seconds=document.createElement("input");seconds.type="number";seconds.min="8";seconds.max="900";
    seconds.step="1";seconds.inputMode="numeric";
    seconds.placeholder="Auto: remaining pass";seconds.value=job.requested_seconds==null?"":String(job.requested_seconds);
    lbl("Record duration · 8–900 seconds, empty = auto",seconds);
    const note=document.createElement("small");
    note.textContent="Original pass: "+new Date(job.aos).toLocaleTimeString()+"–"+
      new Date(job.los).toLocaleTimeString()+" (local). Changing satellite requires a new pass.";
    form.append(note);
    const save=document.createElement("button");save.type="submit";save.textContent="Save changes";form.append(save);
    const error=document.createElement("p");error.className="status";error.setAttribute("role","status");form.append(error);
    form.addEventListener("submit",async e=>{
      e.preventDefault();save.disabled=true;
      try{
        const date=new Date(when.value);
        if(!Number.isFinite(date.getTime()))throw Error("Invalid local start time");
        const raw=seconds.value.trim();
        const duration_seconds=raw?Number(raw):null;
        if(raw&&(!Number.isInteger(duration_seconds)||duration_seconds<8||duration_seconds>900))
          throw Error("Choose 8–900 whole seconds or blank for auto.");
        await nativeApi("/api/auto-edit",{
          job_id:job.id,run_at:date.toISOString(),mission_id:protocols.value,
          duration_seconds
        });
        message("Saved native automatic job changes without touching unrelated SDR processes.");
        await refreshNativeCalendar();
      }catch(err){error.textContent="Not saved: "+err.message;}
      finally{save.disabled=false;}
    });
    card.append(form);
  }
  async function refreshNativeCalendar(){
    if(!nativeHost()){
      calendarGrid.textContent="WebUSB schedules run only on Receiver & pass planner while that browser tab is open. Open that page to see and edit its live 24-hour calendar.";
      return;
    }
    const status=await nativeApi("/api/status");
    calendarJobs=(status.jobs||[]).filter(x=>x?.id&&(x.aos||x.run_at));
    paintCalendar();
  }
  function paintCalendar(){
    renderSatelliteCalendar(calendarGrid,calendarJobs,calendarDay.value,{
      onEdit:editNativeAutoJob,
      onCancel:async job=>{
        if(!nativeHost())return;
        try{
          await nativeApi("/api/cancel",{job_id:job.id});
          message("Cancelled only "+job.satellite+"'s pending capture.");
          await refreshNativeCalendar();
        }catch(e){message("Unable to cancel job: "+e.message);}
      }
    });
  }
  calendarDay.addEventListener("change",paintCalendar);
  $("auto-calendar-prev").addEventListener("click",()=>{
    calendarDay.value=shiftCalendarDay(calendarDay.value,-1);paintCalendar();
  });
  $("auto-calendar-next").addEventListener("click",()=>{
    calendarDay.value=shiftCalendarDay(calendarDay.value,1);paintCalendar();
  });
  $("auto-calendar-refresh").addEventListener("click",()=>{
    void refreshNativeCalendar().catch(e=>message("Calendar refresh unavailable: "+e.message));
  });
  void refreshNativeCalendar().catch(e=>message("Calendar unavailable: "+e.message));

  $("auto-mission-arm").addEventListener("click",async()=>{
    const mode=$("auto-mission-group").value;
    if(!Object.hasOwn(AUTO_PRESETS,mode))return;
    const btn=$("auto-mission-arm");btn.disabled=true;
    try{
      const {lat,lon}=station();
      const hours=Number($("auto-hours").value),elevation=Number($("auto-elev").value);
      if(!nativeHost()){
        const requestedSeconds=readAutoLength({blank:60});
        const {raw,wav}=selectedFormats();
        message("Opening the browser RF scheduler. ISS selected files: "+
          (raw&&wav?"CU8 + WAV (two separate files)":raw?"CU8 only":wav?"WAV only":"none")+
          ". Grant the RTL-SDR WebUSB permission there. No capture starts until an eligible pass.");
        // The destination may only silently reopen previously granted WebUSB;
        // a new permission requires a fresh user gesture on that page.
        // Carry station coordinates only through same-tab session storage,
        // not a public URL, Referrer, or any Internet request.
        try{
          sessionStorage.setItem("tihulu-auto-station",JSON.stringify({
            lat,lon,hours,elevation,createdAt:Date.now()
          }));
          sessionStorage.setItem("tihulu-auto-start-intent",JSON.stringify({
            mode,createdAt:Date.now()
          }));
          sessionStorage.setItem("tihulu-auto-coverage-goal",$("auto-coverage-goal").value);
          sessionStorage.setItem("tihulu-auto-browser-seconds",String(requestedSeconds));
          const format=selectedFormats();
          if(["iss-images","images","all"].includes(mode)&&!format.raw&&!format.wav)
            throw Error("Select WAV, CU8, or both for ISS SSTV reception.");
          sessionStorage.setItem("tihulu-auto-formats",JSON.stringify({...format,createdAt:Date.now()}));
          sessionStorage.setItem("tihulu-auto-compute",JSON.stringify(computeSelector.getSelection()));
        }catch(error){
          throw Error("Browser blocked same-tab station transfer. Open the receiver page and set your coordinates there before scheduling.");
        }
        window.location.assign("./index.html?auto-mission="+encodeURIComponent(mode)+"#auto-workflow");
        return;
      }
      message("Requesting fresh-or-cached TLE geometry and checking native decoder availability…");
      const duration_seconds=readAutoLength({blank:null});
      if($("auto-coverage-goal").value==="sample"&&duration_seconds>60)
        throw Error("Quick sample is limited to 60 s; use full coverage for longer captures.");
      await computeSelector.ready;
      await computeSelector.plan(180); // reject explicitly unavailable GPU/NPU
      const processing=computeSelector.getSelection();
      const result=await nativeApi("/api/auto-schedule",{
        missions:[...AUTO_PRESETS[mode]],lat,lon,city:"Custom",hours,
        elevation,max_jobs:6,coverage_goal:$("auto-coverage-goal").value,
        duration_seconds,
        compute_mode:processing.mode,compute_targets:processing.targets,
        event_window_only:true
      });
      jobs.replaceChildren();
      textNode("h3","Native receiver queue",jobs);
      if(!result.scheduled_count)textNode("p","No eligible non-overlapping satellite passes in the selected window. Check TLE cache, transmitter status and minimum elevation.",jobs);
      for(const job of result.scheduled){
        const size=job.estimated_bytes?
          " · ~"+(job.estimated_bytes/1e9).toFixed(2)+" GB of raw IQ":" · packet/text output";
        textNode("p",job.satellite+" · "+job.data_kind+" · "+
          new Date(job.aos).toLocaleString()+" · planned "+job.capture_seconds+
          " s"+size+" · "+job.coverage+
          (job.shortfall_seconds?" · "+job.shortfall_seconds+" s outside planned capture":"")+
          " · ARMED (not received)",jobs,"mission-job");
      }
      await refreshNativeCalendar();
      if(result.skipped?.length)textNode("p",result.skipped.length+
        " pass(es) skipped due to conflict, unsupported mode or timing.",jobs);
      message(result.scheduled_count+" native duration-aware capture(s) queued. Disk estimates and incomplete passes are listed above. "+(result.disabled_targets?.length?"Unavailable formats: "+result.disabled_targets.join(", ")+". ":"")+"The companion must remain RUNNING and the single RTL-SDR free. A predicted pass does not guarantee complete data, a transmission or a decoded image. "+
        (result.warnings?.length?"Warnings: "+result.warnings.slice(0,2).join("; "):""));
    }catch(e){message("Auto schedule not armed: "+String(e?.message||e));}
    finally{btn.disabled=false;}
  });
  cancel.addEventListener("click",()=>{controller?.abort();message("Cancellation requested; running local FFT/decoder will stop at its next safe checkpoint. Native SatDump jobs are not killed by this button.");});
  $("auto-mission-stop").addEventListener("click",async()=>{
    if(!nativeHost()){
      message("Open the WebUSB receiver page (Receiver & pass planner) and click Cancel Auto Missions there. A different tab cannot take over its USB device.");
      return;
    }
    try{
      const result=await nativeApi("/api/auto-cancel",{});
      message(result.auto_jobs_cancelled+" native automatic jobs cancelled. "+
        (result.owned_auto_capture_stop_requested?"Stopped the currently owned automatic capture. ":"")+
        "Other applications and manual jobs remain untouched.");
      jobs.replaceChildren();
      await refreshNativeCalendar();
    }catch(e){message("Cancel failed: "+String(e?.message||e));}
  });
  function currentMetadata(name){
    const parsed=parseRecordingName(name)||{};
    const rateValue=$("recorded-rate").value.trim();
    const hzValue=$("recorded-mhz").value.trim();
    const sampleRate=rateValue?Number(rateValue):parsed.sampleRate;
    const centerHz=hzValue?Number(hzValue)*1000000:(parsed.frequencyHz??null);
    if(![1024000,2048000].includes(Number(sampleRate)))
      throw Error("CU8 needs the actual acquisition sample rate (1,024,000 or 2,048,000 samples/s). Enter it in the file panel; do not guess.");
    if(centerHz!==null&&(!Number.isFinite(centerHz)||centerHz<24000000||centerHz>1750000000))
      throw Error("Recorded center frequency is invalid; enter the actual MHz or clear it.");
    return {sampleRate:Number(sampleRate),centerHz};
  }
  async function analyzeCu8(blob,name){
    if(blob.size>2_000_000_000)throw Error("Recording exceeds the 2 GB supported IQ safety cap. Keep raw IQ separate and use offline SatDump for larger files.");
    const {sampleRate,centerHz}=currentMetadata(name);
    message("Scanning the REAL "+(blob.size/1048576).toFixed(1)+" MiB CU8: FFT → audio → Robot36 sync → packet decoder availability…");
    const selected=computeSelector.getSelection();
    const result=await discoverCu8Contents(blob,{
      sampleRate,centerHz,signal:controller?.signal,computePolicy:selected,
      onProgress:evt=>{if(evt.state!=="running")message(evt.phase+": "+evt.message);}
    });
    state.discovery.push({name,result});
    state.name=name;
    message("RF analysis complete: "+result.conclusion+
      ". Packet/text extraction is reported only when an actual supported decoder validates it.");
  }
  async function readCompanionArchive(record){
    const path="/api/archive/"+encodeURIComponent(record.file);
    const response=await fetch(path,{cache:"no-store"});
    if(!response.ok)throw Error("Cannot access native capture "+record.file+" (HTTP "+response.status+")");
    return response.blob();
  }
  async function decodeMeteorFile(filename){
    const results=[];
    // Only actual, owned, on-disk captures are passed to installed SatDump.
    for(const variant of ["72k","80k"]){
      if(controller?.signal.aborted)throw Error("Analysis stopped");
      message("Native SatDump Meteor LRPT "+variant+" · checking actual "+filename);
      try{
        const r=await nativeApi("/api/decode",{filename,variant});
        for(const image of r.images||[])if(!results.includes(image))results.push(image);
        if(results.length)break;
      }catch(e){
        state.warnings.push("Meteor "+variant+": "+String(e?.message||e));
      }
    }
    for(const path of results)state.actualImages.push({
      nativePath:path,name:path.split("/").pop(),source:"Native SatDump LRPT output (RF target candidate, not independently verified spacecraft)"
    });
    return results.length;
  }
  async function analyzeAudio(blob,name){
    if(blob.size>100*1024*1024){state.warnings.push(name+": audio file over 100 MiB decoder limit");return;}
    const AudioContext=window.AudioContext||window.webkitAudioContext;
    if(!AudioContext){state.warnings.push("WebAudio not supported");return;}
    const ctx=new AudioContext();
    try{
      const data=await ctx.decodeAudioData(await blob.arrayBuffer());
      const result=await decodeRobot36WithCompute(data.getChannelData(0),data.sampleRate,
        {...computeSelector.getSelection(),signal:controller?.signal});
      state.actualImages.push({rgba:result.rgba,width:result.width,height:result.height,
        name:name.replace(/\.[^.]+$/,"")+"-Robot36.png",
        source:"Actual WAV Robot36 sync candidate (satellite identity not independently verified)",
        alignedLines:result.alignedLines,compute:result.compute});
    }catch(e){state.warnings.push(name+": no valid Robot36 image: "+String(e?.message||e));}
    finally{await ctx.close();}
  }
  async function analyzeOther(blob,name){
    const ext=fileType(name);
    if(["txt","log","aprs","json","csv"].includes(ext)){
      if(blob.size>2*1024*1024){state.warnings.push(name+": text too large for inline preview");return;}
      state.packetText.push({name,body:await blob.text(),
        source:"Actual recorded or imported text. Packet CRC/source identity not reverified here."});
    }else if(["wav","mp3","ogg"].includes(ext)){
      state.audioFiles.push({name,blob,source:"Actual recorded/imported audio; speech or satellite origin NOT verified"});
      if(!/VOICE[-_ ]?AUDIO/i.test(name))await analyzeAudio(blob,name);
    }else if(["png","jpg","jpeg"].includes(ext)){
      state.warnings.push(name+": image already exists; import/preview below. Source is not verified from the filename.");
    }else state.warnings.push(name+": protocol not supported by available decoders.");
  }
  async function analyzeFile(file,name){
    if(!file)throw Error("No capture file available");
    if(controller?.signal.aborted)throw Error("Analysis stopped");
    if(["cu8","iq","u8"].includes(fileType(name)))await analyzeCu8(file,name);
    else await analyzeOther(file,name);
  }
  async function analyzeCollection(file=null){
    begin();
    try{
      if(file){
        await analyzeFile(file,file.name||"user-file");
      }else if(nativeHost()){
        const info=await nativeApi("/api/status");
        // The local scheduler has already analyzed its REAL full-pass WAV, even
        // if the browser was closed. Show those images first without
        // rerunning a 240-second-limited browser decoder on a 900 s file.
        const decodedWavs=new Set();
        const imageNames=new Set();
        for(const job of info.jobs||[]){
          const actual=job?.result?.sstv;
          if(job?.state!=="completed"||!actual)continue;
          state.nativeDecodeReports.push({jobId:job.id,report:actual,source:job.result.file});
          if(actual.images?.length)decodedWavs.add(job.result.file);
          for(const frame of actual.images||[]){
            if(!/^[A-Za-z0-9_-]+_ROBOT36_[0-9]{2}\.png$/.test(frame.file)||imageNames.has(frame.file))continue;
            imageNames.add(frame.file);
            state.actualImages.push({
              nativePath:frame.file,name:frame.file,
              alignedLines:frame.aligned_lines,
              source:"Actual local WAV → Robot36 line-sync candidate ("+frame.aligned_lines+
                "/240 aligned lines); ISS source NOT independently authenticated"
            });
          }
        }
        const records=(info.archive||[]).filter(r=>/\.(cu8|wav|txt)$/i.test(r.file))
          .sort((a,b)=>String(b.modified).localeCompare(String(a.modified))).slice(0,6);
        if(!records.length)throw Error("Native companion has no received recordings yet; schedule/complete a pass first.");
        for(const r of records){
          if(controller?.signal.aborted)break;
          const ext=fileType(r.file);
          if(ext==="cu8" && /METEOR/i.test(r.file)){
            await decodeMeteorFile(r.file);
            if(r.bytes>signalMax){state.warnings.push(r.file+": native full-pass LRPT attempted; large CU8 was not transferred into the browser.");continue;}
          }
          if(r.bytes>signalMax){
            state.warnings.push(r.file+": larger than safe inline fetch; download locally for separate chunked analysis.");
            continue;
          }
          message("Reading archived real capture "+r.file+" …");
          const blob=await readCompanionArchive(r);
          // Native decoder output is the authoritative candidate for this
          // captured long WAV; retain playback/original export only.
          if(ext==="wav"&&decodedWavs.has(r.file)){
            state.audioFiles.push({name:r.file,blob,source:"Original native full-pass ISS SSTV WAV; transmitter unverified"});
          }else await analyzeFile(blob,r.file);
        }
      }else{
        throw Error("Select your downloaded .cu8/.wav/.txt file using the file chooser. Browsers cannot silently read your Downloads folder.");
      }
      const count=state.discovery.length+state.actualImages.length+state.packetText.length+state.audioFiles.length;
      message(count+" real file/result group(s) analyzed. "+state.warnings.length+
        " unsupported/failed decoding notice(s). Press 3 · Extract Results to inspect and save verified outputs.");
    }catch(e){message("Analysis incomplete: "+String(e?.message||e));}
    finally{finish();}
  }
  analyze.addEventListener("click",()=>{
    if(busy)return;
    const local=getSelectedFile();
    if(local){void analyzeCollection(local);return;}
    if(nativeHost()){void analyzeCollection();return;}
    waitingForSelection=true;
    message("Choose a downloaded real recording; browser security prevents unattended access to Downloads.");
    fileInput.click();
  });
  fileInput.addEventListener("change",()=>{
    if(!waitingForSelection)return;
    waitingForSelection=false;
    const selected=getSelectedFile();
    if(selected)void analyzeCollection(selected);
  });
  function makeNativeImg(item){
    const frame=document.createElement("article");frame.className="mission-result";
    textNode("p",item.source,frame);
    let url=null,saveBlob=null;
    if(item.nativePath){
      url="/api/image/"+item.nativePath.split("/").map(encodeURIComponent).join("/");
      const img=document.createElement("img");img.src=url;
      img.alt="Image actually extracted by native decoder from an RF capture; source candidate, not authenticated";
      frame.append(img);
    }else{
      const canvas=document.createElement("canvas");canvas.width=item.width;canvas.height=item.height;
      const ctx=canvas.getContext("2d");
      if(ctx){ctx.putImageData(new ImageData(item.rgba,item.width,item.height),0,0);frame.append(canvas);}
    }
    const save=document.createElement("button");save.type="button";
    save.textContent="Save actual decoded image";
    save.addEventListener("click",async()=>{
      try{
        let blob;
        if(url){const response=await fetch(url);if(!response.ok)throw Error("HTTP "+response.status);blob=await response.blob();}
        else{
          const canvas=frame.querySelector("canvas");
          blob=await new Promise(resolve=>canvas.toBlob(resolve,"image/png"));
        }
        if(!blob)throw Error("No image pixels available");
        postFile(blob,item.name||"decoded-satellite-candidate.png");
      }catch(e){message("Image download failed: "+e.message);}
    });
    frame.append(save);return frame;
  }
  // The ZIP is produced entirely on this device after a real file has been
  // analyzed. No raw gigabyte IQ capture, assumed spacecraft data or invented
  // image/audio is included.
  async function pngFromRgba(item){
    if(!Number.isInteger(item.width)||!Number.isInteger(item.height)||
       item.width<1||item.height<1||item.width*item.height>8_000_000)
      throw Error("Decoded image dimensions exceed export safety limits");
    const canvas=document.createElement("canvas");canvas.width=item.width;canvas.height=item.height;
    const ctx=canvas.getContext("2d");if(!ctx)throw Error("PNG conversion canvas unavailable");
    ctx.putImageData(new ImageData(item.rgba,item.width,item.height),0,0);
    const blob=await new Promise(resolve=>canvas.toBlob(resolve,"image/png"));
    if(!blob)throw Error("Could not encode actual decoded image pixels");
    return blob;
  }
  async function imageResultBlob(item){
    if(!item.nativePath)return pngFromRgba(item);
    if(!nativeHost())throw Error("Native decoded image is unavailable on the hosted web origin");
    const path="/api/image/"+item.nativePath.split("/").map(encodeURIComponent).join("/");
    const response=await fetch(path,{cache:"no-store"});
    if(!response.ok)throw Error("Cannot fetch actual native image (HTTP "+response.status+")");
    const blob=await response.blob();
    if(blob.size>15_000_000||!blob.size)throw Error("Native image exceeds size cap or is empty");
    return blob;
  }
  zipButton.addEventListener("click",async()=>{
    if(busy||zipButton.disabled)return;
    zipButton.disabled=true;
    const entries=[],index=[],warnings=[...state.warnings];
    const save=(path,blob,kind,source,verification)=>{
      entries.push({name:path,blob});
      index.push({path,kind,bytes:blob.size,source,verification});
    };
    const asJson=obj=>new Blob([JSON.stringify(obj,null,2)],{type:"application/json"});
    const asText=text=>new Blob([String(text)],{type:"text/plain;charset=utf-8"});
    try{
      zipStatus.textContent="Collecting genuine decoded outputs and provenance…";
      for(let i=0;i<state.discovery.length;i++){
        const {name,result}=state.discovery[i],k=i+1;
        save("analysis/discovery_"+k+".json",asJson(discoveryReportJson(result)),
          "analysis evidence",name,"RF candidate; satellite origin not independently confirmed");
        for(let j=0;j<(result.images||[]).length;j++){
          try{
            const frame=result.images[j],blob=await pngFromRgba(frame);
            save("images/robot36_candidate_"+k+"_"+(j+1)+".png",blob,"image",name,
              "Real Robot36 line-sync candidate; spacecraft not confirmed");
          }catch(err){warnings.push("Discovery image "+k+"/"+(j+1)+": "+err.message);}
        }
        for(let j=0;j<(result.audioProbes||[]).length&&j<8;j++){
          const probe=result.audioProbes[j];
          if(probe.audioBlob instanceof Blob)
            save("audio/probe_"+k+"_"+(j+1)+".wav",probe.audioBlob,
              "audio candidate",name,"Demodulated RF candidate; voice/content not established");
        }
      }
      for(let i=0;i<state.actualImages.length;i++){
        const item=state.actualImages[i];
        try{
          const blob=await imageResultBlob(item);
          save("images/decoded_candidate_"+(i+1)+(blob.type==="image/jpeg"?".jpg":".png"),
            blob,"image",item.source||item.name,"Decoder output; spacecraft origin not independently verified");
        }catch(err){warnings.push("Image "+(i+1)+" omitted: "+err.message);}
      }
      for(let i=0;i<state.nativeDecodeReports.length;i++){
        const item=state.nativeDecodeReports[i];
        save("analysis/native_robot36_"+(i+1)+".json",asJson(item),
          "decoder evidence",item.source,"Real WAV sync analysis; satellite identity unverified");
      }
      for(let i=0;i<state.audioFiles.length;i++){
        const file=state.audioFiles[i];
        const ext=["wav","mp3","ogg"].includes(fileType(file.name))?fileType(file.name):"wav";
        if(file.blob.size>24*1024*1024){
          warnings.push(file.name+": long original WAV omitted from bounded ZIP; download it separately from the native archive.");
          continue;
        }
        save("audio/recorded_"+(i+1)+"."+ext,file.blob,"original recorded audio",
          file.source||file.name,"Real imported/native recording; contents/source not verified");
      }
      for(let i=0;i<state.packetText.length;i++){
        const item=state.packetText[i];
        save("text/data_"+(i+1)+".txt",asText(item.body),"text/data",
          item.source||item.name,"Actual file contents; packet CRC/source not reverified");
      }
      const manifest={
        format:"tihulu-satellite-analysis-results-v1",
        createdUtc:new Date().toISOString(),
        contentStatus:"Real locally analyzed/imported files. Decode candidates are NOT verified downlinks.",
        rawIqIncluded:false,
        dataCompleteness:"No claim that the complete satellite dataset was downlinked.",
        files:index,
        warnings
      };
      entries.unshift({name:"manifest.json",blob:asJson(manifest)});
      entries.push({name:"README.txt",blob:asText(
        "TIHULU Satellite Center\nReal decoded/imported results with provenance.\n"+
        "Candidate signal, Robot36 sync or SatDump image does not prove a spacecraft ID.\n"+
        "Full recorded pass is not all onboard data. Raw CU8 IQ is excluded for size.\n"
      )});
      if(warnings.length)entries.push({name:"warnings.txt",blob:asText(warnings.join("\n"))});
      zipStatus.textContent="Packaging "+index.length+" output file(s) and provenance in ZIP…";
      const archive=await createResultsZip(entries,{
        onProgress:({done,total})=>{
          if(done===total||done%10===0)zipStatus.textContent="Preparing ZIP "+done+"/"+total+" files";
        }
      });
      const name="TIHULU_satellite_results_"+new Date().toISOString().replace(/[:.]/g,"-")+".zip";
      postFile(archive,name);
      zipStatus.textContent="ZIP download requested: "+name+" · "+index.length+
        " output(s) · "+warnings.length+" warning(s). Check your browser Downloads; no source claims fabricated.";
    }catch(error){
      zipStatus.textContent="ZIP not generated: "+String(error?.message||error)+
        ". Existing recordings and individual decoded output downloads remain available.";
    }finally{
      zipButton.disabled=busy||!(
        state.discovery.length||state.actualImages.length||state.nativeDecodeReports.length||state.packetText.length||state.audioFiles.length||state.warnings.length);
    }
  });
  extract.addEventListener("click",()=>{
    if(busy)return;
    releasePreviews();
    output.replaceChildren();
    let any=false;
    for(const {name,result} of state.discovery){
      any=true;const section=document.createElement("article");section.className="mission-result";
      textNode("h3",name+" · Signal discovery",section);
      textNode("p",result.conclusion+" · "+result.analysis.windows+" complete FFT windows",section);
      for(const img of result.images){
        section.append(makeNativeImg({...img,name:name.replace(/\.[^.]+$/,"")+"-Robot36.png",
          source:"Actual 1200 Hz Robot36 sync candidate; "+img.alignedLines+" aligned lines; satellite identity not established"}));
      }
      for(const probe of result.audioProbes.filter(x=>x.audioBlob).slice(0,8)){
        const wrap=document.createElement("div");
        textNode("p","Actual "+probe.mode.toUpperCase()+" audio candidate · "+
          probe.offsetHz+" Hz offset · human speech/content unverified",wrap);
        const uri=URL.createObjectURL(probe.audioBlob);
        audioPreviewUrls.push(uri);
        const audio=document.createElement("audio");audio.controls=true;audio.src=uri;
        const save=document.createElement("button");save.type="button";save.textContent="Save audio WAV";
        save.addEventListener("click",()=>postFile(probe.audioBlob,"TIHULU_audio_candidate.wav"));
        wrap.append(audio,save);section.append(wrap);
        audio.addEventListener("ended",()=>{}, {once:true});
      }
      for(const p of result.packetResults)textNode("p",p.protocol+": "+p.status+" — "+p.reason,section);
      const save=document.createElement("button");save.type="button";
      save.textContent="Save analysis evidence JSON";
      save.addEventListener("click",()=>postFile(new Blob([JSON.stringify(discoveryReportJson(result),null,2)],{type:"application/json"}),"TIHULU_satellite_analysis.json"));
      section.append(save);output.append(section);
    }
    for(const recording of state.audioFiles){
      any=true;const card=document.createElement("article");card.className="mission-result";
      textNode("h3",recording.name+" · Recorded audio",card);
      textNode("p",recording.source,card);
      const url=URL.createObjectURL(recording.blob);audioPreviewUrls.push(url);
      const player=document.createElement("audio");player.controls=true;player.src=url;
      const save=document.createElement("button");save.type="button";
      save.textContent="Save original recorded audio";
      save.addEventListener("click",()=>postFile(recording.blob,recording.name));
      card.append(player,save);output.append(card);
    }
    for(const frame of state.actualImages){any=true;output.append(makeNativeImg(frame));}
    for(const item of state.packetText){
      any=true;const card=document.createElement("article");card.className="mission-result";
      textNode("h3",item.name+" · Native data/text archive",card);
      textNode("p",item.source,card);
      textNode("pre",item.body.slice(0,40000),card);
      const save=document.createElement("button");save.type="button";save.textContent="Save original data/text";
      save.addEventListener("click",()=>postFile(new Blob([item.body],{type:"text/plain"}),item.name));
      card.append(save);output.append(card);
    }
    for(const warning of state.warnings)textNode("p",warning,output,"file-warning");
    if(!any)textNode("p","No actual decodable results available. RF energy is not automatically an image, audio program or APRS message.",output);
    output.scrollIntoView({behavior:"smooth",block:"start"});
  });
}
