import {MISSIONS, missionById, localFileKind, fileEvidence} from "./reception_catalog.mjs";
import {initSatelliteImageUI} from "./satellite_images_ui.mjs";

const byId=id=>document.getElementById(id);
const missionSelect=byId("mission"), categorySelect=byId("category");
const detail=byId("mission-detail"), sourceLink=byId("mission-source");
const openLink=byId("mission-open"), fileInput=byId("local-file");
const preview=byId("file-preview"), fileStatus=byId("file-status");
let selectedFile=null, activeObjectUrl=null;

function appendText(tag,text,parent=detail,className=""){
  const node=document.createElement(tag);
  node.textContent=String(text);
  if(className)node.className=className;
  parent.append(node);
  return node;
}
function currentMission(){return missionById(missionSelect.value);}
function updateOptions(){
  const previous=missionSelect.value;
  const matches=MISSIONS.filter(m=>categorySelect.value==="all"||m.group===categorySelect.value);
  missionSelect.replaceChildren(...matches.map(m=>{
    const opt=document.createElement("option");
    opt.value=m.id;opt.textContent=m.name;
    return opt;
  }));
  if(matches.some(m=>m.id===previous))missionSelect.value=previous;
  updateMission();
}
function updateMission(){
  const mission=currentMission();
  if(!mission)return;
  detail.replaceChildren();
  appendText("h3",mission.name);
  appendText("p",mission.group+" · "+mission.mode,detail,"mission-meta");
  appendText("p",mission.frequencyHz ? "Candidate downlink: "+(mission.frequencyHz/1e6).toFixed(3)+" MHz" : "No RF center frequency; this entry is an online/archive/catalog item.",detail,"mission-meta");
  appendText("p",mission.description);
  appendText("p","Local input: "+mission.input+" · Decoder: "+mission.decoder,detail,"mission-meta");
  const status={
    "event-only":"EVENT ONLY — check ARISS. An ISS pass is not an SSTV event.",
    "verify-current-downlink":"CHECK LIVE DOWNLINK — frequency and modulation may change.",
    "station-mode-dependent":"CHECK CURRENT STATION MODE — not continuously active.",
    "catalog-only":"CATALOG ONLY — no satellite transmission or protocol assumed.",
    "hardware-upgrade":"NEW S-BAND RECEIVER REQUIRED — current NESDR/WinTV cannot tune or decode HamTV.",
    "online-on-demand":"INTERNET IMAGE ARCHIVE — not SDR reception.",
    "retired":"RETIRED — offline archive, do not schedule reception."
  };
  appendText("p",status[mission.availability]||"No activity verified.",detail,"mission-state");
  sourceLink.href=mission.official;
  openLink.href="./"+mission.route;
  if(mission.imageTarget) {
    openLink.href="./index.html?image-target="+encodeURIComponent(mission.imageTarget)+"#satellite-images";
  }
  if(mission.imageTarget) {
    const target=byId("image-target");
    if(target && target.value!==mission.imageTarget) {
      target.value=mission.imageTarget;
      target.dispatchEvent(new Event("change",{bubbles:true}));
    }
  }
  if(selectedFile)void updateFilePreview().catch(e=>{fileStatus.textContent="Metadata error: "+e.message;});
}
function clearPreview(){
  if(activeObjectUrl){URL.revokeObjectURL(activeObjectUrl);activeObjectUrl=null;}
  preview.replaceChildren();
}
function invalidNumber(id,scale=1){
  const raw=byId(id).value.trim();
  if(!raw)return null;
  const num=Number(raw)*scale;
  if(!Number.isFinite(num)||num<=0)throw new Error("Invalid "+id+" value");
  return num;
}
function manifest(){
  if(!selectedFile)throw new Error("No file selected");
  return fileEvidence(selectedFile,currentMission().id,invalidNumber("recorded-mhz",1e6),invalidNumber("recorded-rate"));
}
async function updateFilePreview(){
  const file=selectedFile;
  clearPreview();
  if(!file){appendText("p","No file selected. Nothing is uploaded.",preview);fileStatus.textContent="Idle · no data accessed.";byId("export-evidence").disabled=true;return;}
  const evidence=manifest();
  appendText("h3",evidence.name,preview);
  appendText("p",evidence.format.toUpperCase()+" · "+file.size.toLocaleString()+" bytes · user-imported/unverified",preview,"file-warning");
  if(evidence.durationSeconds!==null)appendText("p","Estimated gapless CU8 duration: "+evidence.durationSeconds.toFixed(2)+" s, assuming unsigned interleaved I/Q (2 bytes/complex sample) and the manually entered sample rate.",preview);
  const kind=localFileKind(file.name);
  if(["image","audio","video"].includes(kind)){
    activeObjectUrl=URL.createObjectURL(file);
    const node=document.createElement(kind==="image"?"img":kind);
    node.src=activeObjectUrl;
    if(kind==="image"){node.alt="Preview of local user-supplied file; spacecraft attribution is not verified";}
    else node.controls=true;
    preview.append(node);
  }else if(kind==="text"){
    if(file.size>2*1024*1024){
      appendText("p","Large text/data file: preview disabled over 2 MiB. Select a smaller file to inspect inline.",preview);
    }else{
      const content=await file.slice(0,64*1024).text();
      if(selectedFile!==file)return;
      appendText("pre",content,preview);
      if(file.size>64*1024)appendText("p","Preview limited to first 64 KiB. Original file is unchanged.",preview);
    }
  }else if(kind==="iq"){
    appendText("p","Raw I/Q cannot be viewed as an image or WAV. Use the full CU8 spectrum/waterfall analyzer or the real SSTV/Meteor decoder workflow. File analysis requires correct acquisition metadata.",preview);
  }else{
    appendText("p","Unsupported browser preview. Original file remains local; no automatic format claims.",preview);
  }
  fileStatus.textContent="Local preview ready · no upload, no RF-source verification.";
  byId("export-evidence").disabled=false;
}
categorySelect.addEventListener("change",updateOptions);
missionSelect.addEventListener("change",updateMission);
fileInput.addEventListener("change",()=>{
  selectedFile=fileInput.files?.[0]||null;
  try{void updateFilePreview().catch(e=>{fileStatus.textContent="Preview error: "+e.message;});}
  catch(e){fileStatus.textContent="Input error: "+e.message;}
});
for(const id of ["recorded-mhz","recorded-rate"]){
  byId(id).addEventListener("change",()=>{
    if(selectedFile)void updateFilePreview().catch(e=>{fileStatus.textContent="Metadata error: "+e.message;});
  });
}
byId("clear-file").addEventListener("click",()=>{
  selectedFile=null;fileInput.value="";clearPreview();
  byId("export-evidence").disabled=true;
  appendText("p","No file selected. Nothing is uploaded.",preview);
  fileStatus.textContent="Cleared local preview.";
});
byId("export-evidence").addEventListener("click",()=>{
  try{
    const data=manifest();
    const blob=new Blob([JSON.stringify(data,null,2)+"\n"],{type:"application/json"});
    const url=URL.createObjectURL(blob);
    const a=document.createElement("a");
    a.href=url;a.download="TIHULU_satellite_local_evidence.json";
    document.body.append(a);a.click();a.remove();
    setTimeout(()=>URL.revokeObjectURL(url),1000);
    fileStatus.textContent="Only file metadata exported. No recording or image uploaded.";
  }catch(e){fileStatus.textContent="Export blocked: "+e.message;}
});
window.addEventListener("pagehide",clearPreview);
// Reuse the production Robot36 decoder and official NASA image downloader
// instead of a second incompatible browser-only decoder implementation.
// Tuning is performed only from the real receiver page on explicit click.
initSatelliteImageUI({
  onTune:(hz,target)=>{
    const key=["iss","meteor3","meteor4"].includes(target.key)?target.key:"iss";
    window.location.assign("./index.html?image-target="+encodeURIComponent(key)+"#satellite-images");
    return false; // Navigation only; do not claim radio hardware was tuned.
  },
  log:(message)=>{fileStatus.textContent=String(message);}
});
updateOptions();
