/* User-initiated photo sources, experimental Robot36 audio decoding and
 * honest local files. Nothing downloads on page load or acquires the SDR.
 */
import { IMAGE_TARGETS, recordingName, epicEntries, nasaIssEntries } from "./satellite_imagery.mjs";
import { decodeRobot36Audio } from "./sstv_robot36.mjs";
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
   onTune(hz,t);
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
 $("image-decode-sstv").addEventListener("click",async()=>{
   const file=$("image-sstv-file").files?.[0],btn=$("image-decode-sstv");
   if(!file){errorText("image-decode-status","Choose a real narrowband-FM SSTV audio WAV first.");return;}
   if(file.size>60*1024*1024){errorText("image-decode-status","Audio exceeds 60 MiB safe import limit.");return;}
   btn.disabled=true;currentDecode=null;$("image-download-sstv").disabled=true;
   try{
     errorText("image-decode-status","Reading the audio locally and searching for Robot36 synchronization (not raw CU8)…");
     const AudioCtx=window.AudioContext||window.webkitAudioContext;
     if(!AudioCtx)throw Error("WebAudio decoding is unsupported in this browser");
     const audio=new AudioCtx();
     let decoded;
     try{decoded=await audio.decodeAudioData(await file.arrayBuffer());}
     finally{await audio.close();}
     const samples=decoded.getChannelData(0);
     const candidate=decodeRobot36Audio(samples,decoded.sampleRate);
     const canvas=$("image-sstv-canvas"),ctx=canvas.getContext("2d");
     if(!ctx)throw Error("2D Canvas unavailable");
     ctx.putImageData(new ImageData(candidate.rgba,candidate.width,candidate.height),0,0);
     currentDecode=candidate;
     const proposed=getTarget().key==="iss"?"ISS-SSTV-CANDIDATE":"UNATTRIBUTED-SSTV";
     const originalTime=new Date(file.lastModified||Date.now());
     currentName=recordingName({satellite:proposed,at:originalTime,
       frequencyHz:getTarget().frequencies[0],kind:"SSTV-ROBOT36",format:"png"});
     $("image-download-sstv").disabled=false;
     errorText("image-decode-status",candidate.status+" · "+candidate.alignedLines+
       "/240 line syncs · "+candidate.syncCandidates+" sync candidates. "+
       "Experimental audio decode only; image origin/satellite unverified. "+
       "Download as "+currentName+".");
     log("Experimental SSTV audio decoder produced "+candidate.alignedLines+
       " synchronized rows from user's actual local audio.");
   }catch(error){errorText("image-decode-status","No verified Robot36 picture decoded: "+String(error?.message||error));}
   finally{btn.disabled=false;}
 });
 $("image-download-sstv").addEventListener("click",()=>{
   if(!currentDecode||!currentName)return;
   $("image-sstv-canvas").toBlob(blob=>{
     if(!blob)return;
     const url=URL.createObjectURL(blob),a=document.createElement("a");
     a.href=url;a.download=currentName;document.body.append(a);a.click();a.remove();
     setTimeout(()=>URL.revokeObjectURL(url),60000);
     addLocalImage(blob,{satellite:"ISS-SSTV-CANDIDATE",at:new Date(),
       source:"Experimental Robot36 local audio decoder; satellite NOT independently identified",
       caption:"Decoded from user-supplied FM SSTV WAV; "+currentDecode.alignedLines+" synchronized rows",
       kind:"SSTV-ROBOT36",frequencyHz:getTarget().frequencies[0]});
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
 return {getSelectedTarget:getTarget};
}
