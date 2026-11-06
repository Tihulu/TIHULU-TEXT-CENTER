/* Three-step satellite workflow. Same module from Pages and local companion.
   No background USB claim, speculative image, or fabricated packet content. */
import {discoverCu8Contents, discoveryReportJson} from "./signal_discovery.mjs";
import {decodeRobot36Audio} from "./sstv_robot36.mjs";

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
 let analysis=null, controller=null, nativeStatus=null, nativeImages=[], nativeText=null;
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
       sessionStorage.setItem("tihulu-auto-start-intent",JSON.stringify({mode,createdAt:Date.now()}));
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
   let file=$("local-file").files?.[0]||null, nativeArchive=null;
   if(!file && nativeOrigin(location.href)){
     const s=await status(),mode=$("auto-mission-group").value;
     const candidates=(s.archive||[]).filter(x=>
       typeof x.file==="string" && /^TIHULU_[A-Za-z0-9_-]+\.(cu8|txt|wav)$/i.test(x.file) &&
       Number(x.bytes)>0 && Number(x.bytes)<=256*1024*1024);
     const priority=x=>{
       if(mode==="messages")return /\.txt$/i.test(x.file)?0:1;
       if(mode==="images")return /\.(cu8|wav)$/i.test(x.file)?0:1;
       return 0;
     };
     candidates.sort((a,b)=>priority(a)-priority(b)||String(b.modified).localeCompare(String(a.modified)));
     nativeArchive=candidates[0]||null;
     if(nativeArchive){
       say("Opening latest relevant native receiver recording: "+nativeArchive.file);
       const response=await fetch("../api/archive/"+encodeURIComponent(nativeArchive.file),{cache:"no-store"});
       if(!response.ok)throw Error("Companion archive HTTP "+response.status);
       const blob=await response.blob();
       if(blob.size!==Number(nativeArchive.bytes))throw Error("Incomplete native recording transfer");
       file=new File([blob],nativeArchive.file,{type:"application/octet-stream"});
     }
   }
   if(!file)throw Error("No real saved recording yet. Let an armed pass complete or select a local .cu8/.wav/.txt file.");
   if(file.size>1024*1024*1024)throw Error("Recording exceeds 1 GiB safe file limit");
   if(/\.txt$/i.test(file.name)){
     if(file.size>2*1024*1024)throw Error("Text decoder output exceeds 2 MiB safety limit");
     return {file,nativeArchive,kind:"text",rawText:await file.text()};
   }
   if(/\.wav$/i.test(file.name))return {file,nativeArchive,kind:"sstv-audio"};
   if(!/\.(cu8|iq|u8)$/i.test(file.name))throw Error("Choose an actual CU8/IQ/WAV or packet text recording.");
   if(file.size<4096)throw Error("I/Q file too short for meaningful spectrum analysis");
   const meta=file.name.match(/_(\d{7,11})Hz(?:_(\d{6,8})SPS)?_/i);
   const enteredRate=$("recorded-rate").value.trim();
   const rate=Number(enteredRate||meta?.[2]||"");
   if(![1024000,2048000].includes(rate))throw Error("Specify actual capture sample rate (1024000 or 2048000 samples/s). It cannot be inferred from CU8 bytes.");
   const enteredMhz=$("recorded-mhz").value.trim();
   const centerHz=enteredMhz?Number(enteredMhz)*1e6:meta?.[1]?Number(meta[1]):null;
   if(centerHz!==null&&(!Number.isFinite(centerHz)||centerHz<=0))throw Error("Invalid center frequency");
   return {file,sampleRate:rate,centerHz,nativeArchive,kind:"iq"};
 }
 $("auto-mission-analyze").addEventListener("click",async()=>{
   const button=$("auto-mission-analyze");button.disabled=true;
   $("auto-mission-extract").disabled=true;
   analysis=null;nativeImages=[];nativeText=null;output.replaceChildren();controller=new AbortController();
   try{
     const selected=await chosenFile();
     const {file,nativeArchive,kind}=selected;
     if(kind==="text"){
       nativeText={filename:file.name,content:selected.rawText,source:"multimon-ng decoder text output; AX.25 CRC NOT independently verified"};
       analysis={format:"TIHULU native decoder evidence",createdUtc:new Date().toISOString(),sourceBytes:file.size,
         conclusion:"Decoder text retained, packet integrity unverified",analysis:{signalCandidates:[]},
         phases:[],stages:[],audioProbes:[],images:[],packetResults:[
           {protocol:"APRS/AX.25",status:"decoder-text-unverified",crcVerified:false,
            reason:"Imported external decoder output; file content alone does not independently prove AX.25 CRC or ISS source."}
         ],notes:"Receiver output only. No CRC-verified packet or satellite attribution is claimed."};
       say("Native decoder output loaded: "+file.name+". Messages are unverified until checked against valid packet framing/CRC.");
     }else if(kind==="sstv-audio"){
       say("Testing actual WAV audio for repeated Robot36 syncs…");
       const AudioCtx=window.AudioContext||window.webkitAudioContext;
       if(!AudioCtx)throw Error("WebAudio decoder unavailable");
       const ctx=new AudioCtx();
       let decoded;
       try{decoded=await ctx.decodeAudioData(await file.arrayBuffer());}
       finally{await ctx.close();}
       const frame=decodeRobot36Audio(decoded.getChannelData(0),decoded.sampleRate);
       analysis={format:"TIHULU actual WAV Robot36 decode",createdUtc:new Date().toISOString(),
         sourceBytes:file.size,conclusion:"Synchronized Robot36 candidate from actual audio",analysis:{signalCandidates:[]},
         phases:[],stages:[],audioProbes:[],images:[{...frame,kind:"Robot36 audio candidate",offsetHz:0}],
         packetResults:[],notes:"Actual Robot36 synchronization; spacecraft and scene independently unverified."};
       say("Real WAV supplied "+frame.alignedLines+" synchronized Robot36 rows; inspect extracted image.");
     }else{
       say("Analyzing actual "+file.name+" in browser. Entire RF file is read locally; no RF upload.");
       analysis=await discoverCu8Contents(file,{
         sampleRate:selected.sampleRate,centerHz:selected.centerHz,signal:controller.signal,
         onProgress:p=>say("Local full-file analysis · "+p.phase+" · "+p.message)
       });
       if(nativeArchive && /^TIHULU_METEOR-/i.test(nativeArchive.file)){
         const found=[];
         for(const variant of ["72k","80k"]){
           if(controller.signal.aborted)break;
           say("Trying native SatDump Meteor LRPT "+variant+" pipeline on the actual saved RF recording…");
           try{
             const decoded=await post("decode",{filename:nativeArchive.file,variant});
             for(const name of decoded.images||[]){
               if(typeof name==="string"&&/^[A-Za-z0-9_./-]+\.(png|jpg)$/i.test(name)&&!name.includes("..")){
                 found.push({filename:name,variant});
               }
             }
             if(found.length)break;
           }catch(e){say("SatDump "+variant+" unavailable/no image: "+e.message);}
         }
         nativeImages=found;
       }
       const items=chooseExtractionEvidence(analysis);
       const summary=document.createElement("p");
       summary.textContent="Measured spectral candidates: "+(analysis.analysis?.signalCandidates?.length||0)+
         " · audio previews: "+items.audio.length+
         " · Robot36 image candidates: "+items.images.length+
         " · actual SatDump LRPT images: "+nativeImages.length+
         " · CRC-verified text frames: "+items.packets.length;
       output.append(summary);
     }
     $("auto-mission-extract").disabled=false;
     say("Real-recording analysis complete. Click Extract Results for evidence and available media (never invented packets/images).");
   }catch(e){say("Analysis stopped / incomplete: "+e.message);}
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
   for(const item of nativeImages){
     const caption=document.createElement("p");
     caption.textContent="Actual SatDump-produced Meteor LRPT image ("+item.variant+") · satellite source targeted, not independently verified";
     const img=document.createElement("img");
     img.alt="Actual SatDump output from local Meteor recording";img.loading="lazy";
     img.src="../api/image/"+item.filename.split("/").map(encodeURIComponent).join("/");
     img.style.maxWidth="100%";
     const link=document.createElement("a");
     link.textContent="Open / save decoded Meteor image";
     link.href=img.src;link.target="_blank";link.rel="noopener noreferrer";
     output.append(caption,img,link);
   }
   if(nativeText){
     const heading=document.createElement("p");
     heading.textContent="Recorded packet decoder text (CRC and ISS source unverified): "+nativeText.filename;
     const block=document.createElement("pre");
     block.textContent=nativeText.content.slice(0,65536);
     output.append(heading,block);
     const button=document.createElement("button");
     button.type="button";button.textContent="Download actual decoder text output";
     button.addEventListener("click",()=>download(new Blob([nativeText.content],{type:"text/plain"}),nativeText.filename));
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
