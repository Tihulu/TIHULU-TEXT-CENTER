/* Three-step satellite workflow. Same module from Pages and local companion.
   No background USB claim, speculative image, or fabricated packet content. */
import {discoverCu8Contents, discoveryReportJson} from "./signal_discovery.mjs";
import {selectAutomaticPasses} from "./auto_mission.mjs";

export function nativeOrigin(url) {
 const u=new URL(url);
 return (u.protocol==="http:" && (u.hostname==="127.0.0.1"||u.hostname==="localhost") && u.port==="8791");
}
export function missionSelection(mode) {
 if(mode==="images")return ["meteor-m2-3","meteor-m2-4","iss-sstv"];
 if(mode==="messages")return ["iss-aprs"];
 if(mode==="all")return ["meteor-m2-3","meteor-m2-4","iss-sstv","iss-aprs"];
 throw Error("Unknown satellite mission selection");
}
export function chooseExtractionEvidence(result) {
 if(!result)return {images:[],audio:[],packets:[],report:null};
 return {
   images:(result.images||[]).filter(im=>im.rgba&&im.width===320&&im.height===240&&im.alignedLines>=225),
   audio:(result.audioProbes||[]).filter(p=>p.audioBlob instanceof Blob),
   packets:(result.packetResults||[]).filter(p=>p.status==="crc-verified"&&p.crcVerified===true),
   report:discoveryReportJson(result)
 };
}
export function initReceptionWorkflow() {
 const $=id=>document.getElementById(id);
 const message=$("auto-mission-status"), output=$("auto-mission-output"), jobArea=$("auto-mission-jobs");
 let analysis=null, controller=null, nativeStatus=null;
 const say=s=>{message.textContent=String(s);};
 function getCoords(){
   const lat=Number($("auto-lat").value),lon=Number($("auto-lon").value);
   if(!$("auto-lat").value||!$("auto-lon").value||!Number.isFinite(lat)||!Number.isFinite(lon)||Math.abs(lat)>90||Math.abs(lon)>180)throw Error("Enter valid station latitude and longitude");
   return {lat,lon};
 }
 function renderJobs(jobs){
   jobArea.replaceChildren();
   if(!jobs?.length){jobArea.textContent="No active auto-scheduled passes.";return;}
   for(const j of jobs.slice(0,12)){
     const p=document.createElement("p");
     const utc=j.aos||j.when;
     p.textContent=String(j.satellite||j.name||j.mission_id||"Mission")+" · "+String(utc||"")+
       " · "+String(j.state||"armed")+
       " · "+String(j.profile||j.frequency||"")+
       " · predicted pass, RF not verified";
     jobArea.append(p);
   }
 }
 async function status(){
   if(!nativeOrigin(location.href))throw Error("Native companion is not running on this page origin");
   const response=await fetch("../api/status",{cache:"no-store"});
   if(!response.ok)throw Error("Local native status HTTP "+response.status);
   nativeStatus=await response.json();
   if(!nativeStatus.csrf)throw Error("Missing companion session CSRF");
   return nativeStatus;
 }
 async function post(route,data={}){
   const state=await status();
   const r=await fetch("../api/"+route,{method:"POST",headers:{"Content-Type":"application/json"},
     body:JSON.stringify({csrf:state.csrf,...data}),cache:"no-store"});
   const reply=await r.json();
   if(!r.ok)throw Error(reply.error||"Native service rejected "+route);
   return reply;
 }
 $("auto-gps").addEventListener("click",()=>{
   if(!navigator.geolocation){say("Geolocation unavailable; enter coordinates.");return;}
   navigator.geolocation.getCurrentPosition(
     pos=>{$("auto-lat").value=pos.coords.latitude.toFixed(5);$("auto-lon").value=pos.coords.longitude.toFixed(5);say("GPS selected locally. No capture or scheduling started.");},
     e=>say("GPS unavailable: "+e.message),{enableHighAccuracy:false,timeout:12000,maximumAge:60000});
 });
 $("auto-mission-arm").addEventListener("click",async()=>{
   const button=$("auto-mission-arm");button.disabled=true;
   try{
     const station=getCoords(),hours=Number($("auto-hours").value),mode=$("auto-mission-group").value;
     if(nativeOrigin(location.href)){
       say("Requesting fresh orbital pass predictions and persistent native receive-only schedules…");
       const reply=await post("auto-schedule",{
         missions:missionSelection(mode),lat:station.lat,lon:station.lon,
         hours,elevation:20,max_jobs:6
       });
       renderJobs(reply.scheduled);
       say("Native auto schedules: "+reply.scheduled_count+" candidate pass(es). "+
         "Keep the companion service running. A TLE pass is not proof of an active transmission. "+
         (reply.warnings||[]).join(" "));
     }else{
       // Pages cannot run Python or promise unattended capture. Transfer station
       // in same-origin sessionStorage, without putting its GPS in URL.
       sessionStorage.setItem("tihulu-auto-station",JSON.stringify({...station,hours,createdAt:Date.now()}));
       say("Opening the real WebUSB scheduler. Confirm the single USB permission/capture action in that tab; the browser must stay visible and awake.");
       location.assign("./index.html?auto-mission="+encodeURIComponent(mode)+"#auto-center");
     }
   }catch(e){say("Auto reception not armed: "+e.message);}
   finally{button.disabled=false;}
 });
 $("auto-mission-stop").addEventListener("click",async()=>{
   if(nativeOrigin(location.href)){
     try{const r=await post("auto-cancel");renderJobs([]);say("Cancelled "+r.auto_jobs_cancelled+" native auto job(s); unrelated receivers unchanged.");}
     catch(e){say("Could not cancel native auto jobs: "+e.message);}
   }else{
     say("Use Stop Auto Missions on the foreground receiver tab to cancel its local browser jobs; no unrelated SDR process was touched.");
     location.assign("./index.html#auto-center");
   }
 });
 $("auto-mission-cancel").addEventListener("click",()=>{
   if(controller)controller.abort();
   say("Requested cancellation of app-owned file analysis. No receiver service stopped.");
 });
 async function chosenFile(){
   const input=$("local-file");
   const file=input.files?.[0];
   if(!file)throw Error("Choose an actual .cu8 recording in the Local file section first. The application will not invent data.");
   if(!/\.(cu8|iq|u8)$/i.test(file.name))throw Error("Automatic RF analysis needs raw .cu8/.iq/.u8 samples; other files remain previewable.");
   if(file.size<4096||file.size>1024*1024*1024)throw Error("Recording is empty or exceeds the 1 GiB safety limit");
   const rate=Number($("recorded-rate").value);
   const mhz=$("recorded-mhz").value.trim();
   if(![1024000,2048000].includes(rate))throw Error("Enter the real capture sample rate (1024000 or 2048000 samples/s)");
   const centerHz=mhz?Number(mhz)*1e6:null;
   if(centerHz!==null&&(!Number.isFinite(centerHz)||centerHz<=0))throw Error("Invalid center frequency");
   return {file,sampleRate:rate,centerHz};
 }
 $("auto-mission-analyze").addEventListener("click",async()=>{
   const button=$("auto-mission-analyze");button.disabled=true;
   $("auto-mission-extract").disabled=true;
   analysis=null;output.replaceChildren();controller=new AbortController();
   try{
     const {file,sampleRate,centerHz}=await chosenFile();
     say("Analyzing "+file.name+" locally. Inspecting the full RF recording; no upload.");
     analysis=await discoverCu8Contents(file,{sampleRate,centerHz,signal:controller.signal,
       onProgress:p=>say("Local analysis · "+p.phase+" · "+p.message)});
     const selected=chooseExtractionEvidence(analysis);
     const summary=document.createElement("p");
     summary.textContent="Measured candidate regions: "+(analysis.analysis?.signalCandidates?.length||0)+
       " · audio previews: "+selected.audio.length+
       " · synchronized Robot36 image candidates: "+selected.images.length+
       " · CRC-verified text packets: "+selected.packets.length;
     output.append(summary);
     $("auto-mission-extract").disabled=false;
     say("Analysis complete. Press Extract Results to view/save only generated evidence; no unsupported packet content asserted.");
   }catch(e){say("Analysis did not complete: "+e.message);}
   finally{controller=null;button.disabled=false;}
 });
 function download(blob,name){
   const url=URL.createObjectURL(blob),a=document.createElement("a");
   a.href=url;a.download=name;document.body.append(a);a.click();a.remove();
   setTimeout(()=>URL.revokeObjectURL(url),60000);
 }
 $("auto-mission-extract").addEventListener("click",()=>{
   if(!analysis){say("Analyze an actual file first.");return;}
   const result=chooseExtractionEvidence(analysis);output.replaceChildren();
   const info=document.createElement("p");
   info.textContent="Verified-data policy: Robot36 requires synchronized lines; audio is demodulated but not identified; APRS text is unavailable without verified packet frames. Source spacecraft is not established from RF energy.";
   output.append(info);
   for(let i=0;i<result.images.length;i++){
     const frame=result.images[i],canvas=document.createElement("canvas");
     canvas.width=frame.width;canvas.height=frame.height;
     canvas.getContext("2d").putImageData(new ImageData(frame.rgba,frame.width,frame.height),0,0);
     const button=document.createElement("button");
     button.type="button";button.textContent="Save actual synchronized Robot36 candidate PNG #"+(i+1);
     button.addEventListener("click",()=>canvas.toBlob(blob=>{if(blob)download(blob,"TIHULU_RF-UNATTRIBUTED_ROBOT36_"+(i+1)+".png");},"image/png"));
     const label=document.createElement("p");label.textContent="Robot36 synchronized candidate · satellite not independently verified";
     output.append(label,canvas,button);
   }
   for(let i=0;i<result.audio.length;i++){
     const item=result.audio[i],button=document.createElement("button");
     button.type="button";button.textContent="Save demodulated "+item.mode.toUpperCase()+" audio candidate #"+(i+1);
     button.addEventListener("click",()=>download(item.audioBlob,"TIHULU_AUDIO-CANDIDATE_"+(i+1)+".wav"));
     output.append(button);
   }
   if(!result.images.length&&!result.audio.length&&!result.packets.length){
     const p=document.createElement("p");p.textContent="No verified image, audio preview or CRC-validated packet was produced. The RF evidence report remains available.";output.append(p);
   }
   const button=document.createElement("button");button.type="button";button.textContent="Export spectral/decoder evidence JSON";
   button.addEventListener("click",()=>download(new Blob([JSON.stringify(result.report,null,2)],{type:"application/json"}),"TIHULU_RF_ANALYSIS_EVIDENCE.json"));
   output.append(button);
   say("Extraction results generated from the real analyzed file. No synthetic Earth images or messages.");
 });
 // Read-only refresh: nothing claims SDR merely from opening the tab.
 if(nativeOrigin(location.href)){
   void status().then(s=>{
     const jobs=(s.jobs||[]).filter(j=>j.mission_id&&["pending","running"].includes(j.state));
     renderJobs(jobs);
     if(jobs.length)say(jobs.length+" previously authorized native pass(es) pending/running. Companion must remain active.");
   }).catch(()=>{});
 }
}
