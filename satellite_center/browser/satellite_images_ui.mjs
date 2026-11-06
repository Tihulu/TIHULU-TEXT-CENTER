/* User-initiated photo sources, experimental Robot36 audio decoding and
 * honest local files. Nothing downloads on page load or acquires the SDR.
 */
import { IMAGE_TARGETS, recordingName, parseRecordingName, epicEntries, nasaIssEntries } from "./satellite_imagery.mjs?v=20261106-images-v15";
import { cu8ToFmAudio } from "./fm_iq_demod.mjs?v=20261106-images-v15";
import { decodeRobot36Audio } from "./sstv_robot36.mjs?v=20261106-images-v15";
const $=id=>document.getElementById(id);
function imgCard({source,satellite,timestamp,caption,imageUrl,archiveUrl},cleanup){
 const card=document.createElement("article");card.className="photo-card";
 const image=document.createElement("img");image.loading="lazy";
 image.referrerPolicy="strict-origin-when-cross-origin";
 image.alt=caption||"Image with provider attribution";image.src=imageUrl;
 image.onerror=()=>{image.alt="Provider image did not load; use source link";};
 const meta=document.createElement("div");meta.className="photo-meta";
 const label=document.createElement("strong");
 label.textContent=satellite+" · "+timestamp;
 const type=document.createElement("small");type.textContent=source;
 const description=document.createElement("p");description.textContent=caption||"";
 meta.append(label,type,description);
 if(archiveUrl){
   const link=document.createElement("a");
   link.href=archiveUrl;link.target="_blank";link.rel="noopener noreferrer";
   link.textContent="Open original at source";meta.append(link);
   const save=document.createElement("button");save.type="button";
   save.className="secondary";save.textContent="Save image (satellite + UTC)";
   save.addEventListener("click",async()=>{
     save.disabled=true;
     try{
       const observed=new Date(String(timestamp).replace(" UTC","Z").replace(" ","T"));
       if(!Number.isFinite(observed.getTime()))throw Error("Provider timestamp invalid; cannot attribute image date.");
       const response=await fetch(imageUrl,{mode:"cors",cache:"no-cache"});
       if(!response.ok)throw Error("Provider image HTTP "+response.status);
       const blob=await response.blob();
       if(!["image/png","image/jpeg"].includes(blob.type)||blob.size>30_000_000)
         throw Error("Provider did not return a supported PNG/JPEG under 30 MB.");
       const name=recordingName({satellite,at:observed,frequencyHz:0,
         kind:"NASA-ONLINE",format:blob.type==="image/png"?"png":"jpg"});
       const uri=URL.createObjectURL(blob),a=document.createElement("a");
       a.href=uri;a.download=name;document.body.append(a);a.click();a.remove();
       setTimeout(()=>URL.revokeObjectURL(uri),60000);
     }catch(error){
       save.textContent="Download unavailable; open original";
       save.title=String(error?.message||error)+". NASA may restrict cross-origin downloads.";
     }finally{save.disabled=false;}
   });
   meta.append(save);
 }
 card.append(image,meta);if(cleanup)card.addEventListener("remove",cleanup,{once:true});
 return card;
}
function imageClear(container){
 for(const child of container.children)child.dispatchEvent(new Event("remove"));
 container.replaceChildren();
}
function errorText(target,message){$(target).textContent=String(message);}
export function initSatelliteImageUI({onTune=()=>{},onTargetChange=()=>{},log=()=>{}}={}){
 let currentDecode=null,currentName=null,importUrls=[];
 let lastCu8Blob=null,lastCu8Name=null,lastCu8Metadata=null,lastDecodeSource="";
 let lastWavBlob=null,lastWavName=null;
 let decodedAt=null,decodedFrequencyHz=0,decodedSatellite="ISS-SSTV-CANDIDATE";
 const targetSelect=$("image-target"),getTarget=()=>IMAGE_TARGETS.find(t=>t.key===targetSelect.value)||IMAGE_TARGETS[0];
 function guide(){
   const t=getTarget();
   errorText("image-reception-guide",t.name+" · "+t.kind+" · "+
     t.frequencies.map(f=>(f/1e6).toFixed(3)+" MHz").join(" / ")+
     " · "+t.mode+". "+t.details+" "+t.reception);
   onTargetChange(t);
 }
 targetSelect.addEventListener("change",guide);guide();
 $("image-reception-open").addEventListener("click",()=>{
   window.open(getTarget().statusUrl,"_blank","noopener,noreferrer");
 });
 $("image-tune").addEventListener("click",()=>{
   const t=getTarget(),hz=t.frequencies[0];
   const tuned=onTune(hz,t);
   if(tuned===false){
     errorText("image-decode-status","Opening receiver controls for "+t.name+"; no SDR was tuned in this tab.");
     return;
   }
   errorText("image-decode-status","Tuned the RF candidate preset to "+(hz/1e6).toFixed(3)+
     " MHz for "+t.name+". This does not start a receiver or prove the satellite is transmitting.");
 });
 async function fetchOnline(){
   const source=$("image-online-source").value;
   const gallery=$("image-gallery"),button=$("image-fetch-online");
   button.disabled=true;imageClear(gallery);
   errorText("image-online-status","Contacting official NASA catalog on demand…");
   try{
     const url=source==="epic"?
       "https://api.nasa.gov/EPIC/api/natural/images?api_key=DEMO_KEY":
       "https://images-api.nasa.gov/search?q=earth%20from%20international%20space%20station&media_type=image&page_size=25";
     const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),12000);
     let response;
     try{response=await fetch(url,{mode:"cors",signal:controller.signal,cache:"no-cache"});}
     finally{clearTimeout(timeout);}
     if(!response.ok)throw Error("NASA catalog HTTP "+response.status);
     const json=await response.json();
     const entries=source==="epic"?epicEntries(json):nasaIssEntries(json);
     if(!entries.length)throw Error("NASA returned no verified image metadata entries.");
     for(const entry of entries)gallery.append(imgCard(entry));
     errorText("image-online-status",entries.length+" images with provider-supplied dates and captions. "+
       "These are official NASA online/archive photos, NOT received through the USB antenna. "+
       (source==="iss"?"ISS results are historical, not a live stream.":"EPIC is DSCOVR, not the ISS."));
     log("NASA "+source+" catalog fetched on demand: "+entries.length+" metadata records.");
   }catch(error){
     const link=document.createElement("a");
     link.href=source==="epic"?"https://epic.gsfc.nasa.gov/":"https://images.nasa.gov/";
     link.target="_blank";link.rel="noopener noreferrer";link.textContent="Open provider gallery";
     imageClear(gallery);gallery.append(link);
     errorText("image-online-status","Online NASA image request failed: "+String(error?.message||error)+
       ". Possible CORS/network/key restriction. Use the official provider gallery link below.");
   }finally{button.disabled=false;}
 }
 $("image-fetch-online").addEventListener("click",()=>{void fetchOnline();});
 $("image-clear-online").addEventListener("click",()=>{
   imageClear($("image-gallery"));errorText("image-online-status","Gallery cleared; no active network polling.");
 });
 function addLocalImage(blob,{satellite,at,source,caption,kind,frequencyHz}){
   if(blob.size>50*1024*1024)throw Error("Image exceeds 50 MiB limit.");
   const localName=recordingName({satellite,at,frequencyHz,kind,format:"png"});
   const url=URL.createObjectURL(blob),gallery=$("image-local-gallery");
   gallery.prepend(imgCard({
     source,satellite,timestamp:new Date(at).toISOString(),
     caption,imageUrl:url,archiveUrl:null
   },()=>URL.revokeObjectURL(url)));
   while(gallery.children.length>12){
     const last=gallery.lastElementChild;last.dispatchEvent(new Event("remove"));last.remove();
   }
   return localName;
 }
 function drawDecodedAudio(samples,rate,file,sourceLabel){
   const candidate=decodeRobot36Audio(samples,rate);
   const canvas=$("image-sstv-canvas"),ctx=canvas.getContext("2d");
   if(!ctx)throw Error("2D Canvas unavailable");
   ctx.putImageData(new ImageData(candidate.rgba,candidate.width,candidate.height),0,0);
   currentDecode=candidate;
   lastDecodeSource=sourceLabel;
   const sourceMeta=parseRecordingName(file.name||"");
   const proposed=sourceMeta?.satellite||
     (getTarget().key==="iss"?"ISS-SSTV-CANDIDATE":"UNATTRIBUTED-SSTV");
   const originalUtc=sourceMeta?.timestamp?new Date(sourceMeta.timestamp):
     new Date(file.lastModified||Date.now());
   const originalHz=sourceMeta?.frequencyHz||getTarget().frequencies[0];
   decodedAt=originalUtc;decodedFrequencyHz=originalHz;decodedSatellite=proposed;
   currentName=recordingName({satellite:proposed,at:originalUtc,
     frequencyHz:originalHz,kind:"SSTV-ROBOT36",format:"png"});
   $("image-download-sstv").disabled=false;
   errorText("image-decode-status",candidate.status+" · "+candidate.alignedLines+
     "/240 verified line syncs · "+candidate.syncCandidates+" sync candidates. "+
     "Source: "+sourceLabel+". Satellite origin/visual fidelity NOT verified. "+
     "Save as "+currentName+".");
   log("Real local SSTV audio synchronization: "+candidate.alignedLines+
     " lines ("+sourceLabel+").");
 }
 async function decodeImportedWav(file,btn){
   if(!file){errorText("image-decode-status","Choose a real narrowband-FM SSTV audio WAV first.");return;}
   if(file.size>60*1024*1024){errorText("image-decode-status","Audio exceeds 60 MiB safe import limit.");return;}
   btn.disabled=true;currentDecode=null;$("image-download-sstv").disabled=true;
   try{
     errorText("image-decode-status","Reading WAV audio locally and checking for Robot36 1200 Hz syncs…");
     const AudioCtx=window.AudioContext||window.webkitAudioContext;
     if(!AudioCtx)throw Error("WebAudio decoding is unsupported");
     const context=new AudioCtx();
     let decoded;
     try{decoded=await context.decodeAudioData(await file.arrayBuffer());}
     finally{await context.close();}
     drawDecodedAudio(decoded.getChannelData(0),decoded.sampleRate,file,"user WAV FM-demodulated audio");
   }catch(error){errorText("image-decode-status",
     "No credible Robot36 SSTV image produced: "+String(error?.message||error));}
   finally{btn.disabled=false;}
 }
 $("image-decode-sstv").addEventListener("click",async()=>{
   await decodeImportedWav($("image-sstv-file").files?.[0],$("image-decode-sstv"));
 });
 $("image-decode-last-wav")?.addEventListener("click",async()=>{
   if(lastWavBlob)await decodeImportedWav(lastWavBlob,$("image-decode-last-wav"));
 });
 async function decodeRF(blob,name,metadata){
   const buttons=[$("image-decode-cuiq"),$("image-decode-last")];
   for(const b of buttons)b.disabled=true;
   currentDecode=null;$("image-download-sstv").disabled=true;
   try{
     const parsed=parseRecordingName(name);
     const rate=metadata?.sampleRate||parsed?.sampleRate||Number($("rate").value);
     errorText("image-decode-status","Demodulating real raw CU8 into FM audio locally (no upload). "+
       "Then the decoder checks for 1200 Hz Robot36 line syncs; no image is assumed.");
     const audio=await cu8ToFmAudio(blob,{sampleRate:rate,
       onProgress:(done,total)=>errorText("image-decode-status",
         "FM demodulation: "+Math.round(100*done/total)+"% of raw RF bytes read locally…")});
     drawDecodedAudio(audio.samples,audio.rate,
       {lastModified:blob.lastModified||Date.now(),name},
       "user-provided CU8 → narrowband FM → Robot36 candidate");
   }catch(error){
     errorText("image-decode-status","No credible Robot36 image obtained from RF CU8: "+
       String(error?.message||error)+
       ". Verify ISS SSTV event, sample rate, receiving frequency, FM quality and antenna.");
   }finally{
     $("image-decode-cuiq").disabled=false;
     $("image-decode-last").disabled=!lastCu8Blob;
   }
 }
 $("image-decode-cuiq").addEventListener("click",()=>{
   const file=$("image-cuiq-file").files?.[0];
   if(!file){errorText("image-decode-status","Select a .cu8 RF recording first.");return;}
   void decodeRF(file,file.name,null);
 });
 $("image-decode-last").addEventListener("click",()=>{
   if(lastCu8Blob)void decodeRF(lastCu8Blob,lastCu8Name,lastCu8Metadata);
 });
 $("image-download-sstv").addEventListener("click",()=>{
   if(!currentDecode||!currentName)return;
   $("image-sstv-canvas").toBlob(blob=>{
     if(!blob)return;
     const url=URL.createObjectURL(blob),a=document.createElement("a");
     a.href=url;a.download=currentName;document.body.append(a);a.click();a.remove();
     setTimeout(()=>URL.revokeObjectURL(url),60000);
     addLocalImage(blob,{satellite:decodedSatellite,at:decodedAt||new Date(),
       source:"Experimental Robot36 local audio decoder; satellite NOT independently identified",
       caption:"Source "+lastDecodeSource+"; "+currentDecode.alignedLines+" synchronized rows",
       kind:"SSTV-ROBOT36",frequencyHz:decodedFrequencyHz});
   },"image/png");
 });
 $("image-import").addEventListener("change",()=>{
   const file=$("image-import").files?.[0];if(!file)return;
   if(!["image/png","image/jpeg"].includes(file.type)||file.size>50*1024*1024){
     errorText("image-decode-status","Only PNG/JPEG images under 50 MiB can be imported.");return;
   }
   const url=URL.createObjectURL(file),gallery=$("image-local-gallery");
   const record=imgCard({satellite:"USER-IMPORTED",timestamp:new Date(file.lastModified||Date.now()).toISOString(),
     source:"User-supplied decoded image, RF origin not verified",
     caption:file.name,imageUrl:url,archiveUrl:null},()=>URL.revokeObjectURL(url));
   gallery.prepend(record);
   while(gallery.children.length>12){const last=gallery.lastElementChild;last.dispatchEvent(new Event("remove"));last.remove();}
 });
 return {
   getSelectedTarget:getTarget,
   recordCapture(blob,name,metadata){
     if(!blob||typeof blob.slice!=="function"||!blob.size||!String(name).endsWith(".cu8"))return;
     lastCu8Blob=blob;lastCu8Name=name;lastCu8Metadata=metadata;
     $("image-decode-last").disabled=false;
     errorText("image-decode-status","Latest real WebUSB CU8 available: "+name+
       ". To attempt actual ISS SSTV from its raw I/Q choose Decode last USB CU8 capture. "+
       "No decoder is started automatically, no image is claimed.");
   },
   recordAudioCapture(blob,name){
     if(!blob||typeof blob.slice!=="function"||blob.size<44||!String(name).endsWith(".wav"))return;
     lastWavBlob=blob;lastWavName=name;
     if($("image-decode-last-wav"))$("image-decode-last-wav").disabled=false;
     errorText("image-decode-status","Real browser FM-demodulated WAV available: "+name+
       ". Choose Decode last captured FM WAV to check 1200 Hz Robot36 synchronization. Audio does not prove ISS reception.");
   }
 };
}
