/* Independent antenna-only survey.
 * Hardware measurements = RTL2832U WebUSB I/Q energy only.
 * Source frequency/coords and reference calibration = USER-SUPPLIED external metadata.
 * RSSI-derived range = highly model-dependent HYPOTHESIS, never a direct distance measurement.
 * All data local; no device/browser geolocation APIs are ever invoked from this module.
 */
import {calibratedRange,solveCalibratedRF} from "../core/rf_ranging.mjs";
const $=id=>document.getElementById(id);
const KEY="tihulu.rfgeo.rf-survey.v1";
const FRESH_MAX_MS=10*60*1000;
let sources=[],selected="",rfOnly=false,solution=null,rangeEstimates=[],stopped=false;
function message(id,content){const el=$(id);if(el)el.textContent=content}
function safeLoad(){
 try{
  const x=JSON.parse(localStorage.getItem(KEY)||"null");
  if(!Array.isArray(x)||x.length>60)return [];
  return x.filter(s=>s&&typeof s.id==="string"&&s.id.length<110&&
    ["station","aircraft","satellite"].includes(s.type)&&Number.isFinite(s.lat)&&
    Number.isFinite(s.lon)&&Math.abs(s.lat)<=90&&Math.abs(s.lon)<=180&&
    Number.isFinite(s.frequencyMHz)&&s.frequencyMHz>=24&&s.frequencyMHz<=1766)
   .map(s=>({...s,lastObservation:null,rangeHypothesis:null}));
 }catch{return []}
}
function persist(){
 try{
  localStorage.setItem(KEY,JSON.stringify(sources.map(s=>({
   id:s.id,name:s.name,lat:s.lat,lon:s.lon,type:s.type,catalogId:s.catalogId||null,
   frequencyMHz:s.frequencyMHz,calibration:s.calibration||null,catalog:s.catalog||null,metadataOrigin:s.metadataOrigin||"USER SUPPLIED"
  }))));
 }catch{}
}
function sourceById(){return sources.find(s=>s.id===selected)||null}
function broadcast(){
 if(stopped)return;
 window.dispatchEvent(new CustomEvent("tihulu:rf-survey-updated",{
  detail:{rfOnly,sources:sources.map(s=>({id:s.id,name:s.name,type:s.type,lat:s.lat,lon:s.lon,
   frequencyMHz:s.frequencyMHz,hasActualRF:!!s.lastObservation,catalogId:s.catalogId||null,catalog:s.catalog||null,metadataOrigin:s.metadataOrigin||"USER SUPPLIED",
   calibration:!!s.calibration})),
   ranges:rangeEstimates.map(s=>({...s})),solution:solution?{...solution}:null}
 }));
}
function freshness(s,now){
 return !!(s.rangeHypothesis&&s.lastObservation&&
  Date.parse(s.lastObservation.measuredAt)>=now-FRESH_MAX_MS&&
  Date.parse(s.lastObservation.measuredAt)<=now+30000);
}
function compute(){
 if(stopped||!rfOnly){solution=null;rangeEstimates=[];return;}
 const now=Date.now();
 rangeEstimates=sources.filter(s=>s.type==="station"&&freshness(s,now))
   .map(s=>({id:s.id,name:s.name,type:"station",lat:s.lat,lon:s.lon,frequencyMHz:s.frequencyMHz,
    ...s.rangeHypothesis,modelType:"CALIBRATED_RSSI_ESTIMATE",
    source:"RTL-SDR REAL I/Q + USER-SUPPLIED TRANSMITTER + REFERENCE CALIBRATION",
    measured:false,observedAt:s.lastObservation.measuredAt}));
 // The receiver must be physically at one place while collecting this group.
 const dates=rangeEstimates.map(s=>Date.parse(s.observedAt));
 if(dates.length>=3&&Math.max(...dates)-Math.min(...dates)<=FRESH_MAX_MS){
  try{solution=solveCalibratedRF(rangeEstimates);
   message("rf-solution-report","RF-ONLY HYPOTHESIS ("+rangeEstimates.length+
      " calibrated fixed transmitters) · "+solution.lat.toFixed(6)+", "+solution.lon.toFixed(6)+
      " · model RMS residual "+solution.rmsResidualMeters.toFixed(0)+
      " m (NOT POSITION ACCURACY). Unverified emitter identity, antenna gain, path loss and multipath. Browser GPS/Wi-Fi/IP were NOT used.");
  }catch(e){solution=null;message("rf-solution-report","RF-ONLY SOLVER BLOCKED: "+e.message)}
 }else{
  solution=null;message("rf-solution-report",rangeEstimates.length+" current CALIBRATED RF DISTANCE HYPOTHESES. "+
    "Requires 3+ fixed transmitters measured within 10 minutes at one observer site, with non-degenerate geometry. "+
    "Aircraft/satellites are reference-only; no OS/device location used in RF-only mode.");
 }
 broadcast();
}
function render(){
 const dropdown=$("rf-source-select"),list=$("rf-source-list");
 if(dropdown){dropdown.replaceChildren();
  for(const s of sources){
   const option=document.createElement("option");option.value=s.id;
   option.textContent=s.name+" · "+s.frequencyMHz.toFixed(3)+" MHz · "+s.type;
   dropdown.append(option)
  }
  dropdown.value=selected;
 }
 if(list){list.replaceChildren();
  if(!sources.length){const p=document.createElement("p");p.textContent="No user-defined sources. Add a fixed transmitter for radio ranging or an aircraft/satellite reference.";list.append(p)}
  for(const s of sources){
   const row=document.createElement("div");row.className="rf-source-row";
   const name=document.createElement("strong");name.textContent=s.name+" · "+s.type+" · "+s.frequencyMHz.toFixed(3)+" MHz";
   const desc=document.createElement("span");
   desc.textContent=(s.catalog?"CATALOG site candidate ("+s.catalog+") ":"User-supplied position ")+s.lat.toFixed(5)+", "+s.lon.toFixed(5)+
     " · "+(s.lastObservation?"REAL RF level "+s.lastObservation.levelDbFS.toFixed(2)+" dBFS-like":"NO ANTENNA READING")+
     " · "+(s.calibration?"Reference calibrated":"Not calibrated")+
     (s.rangeHypothesis?" · RANGE HYPOTHESIS "+Math.round(s.rangeHypothesis.rangeMeters)+" m":"")+
     (s.type!=="station"?" · REFERENCE ONLY (not used in 2D RSSI solver)":"");
   row.append(name,desc);list.append(row);
  }
 }
 message("rf-session-status",rfOnly?"RF-ONLY ON · Device GPS, browser location, Wi-Fi/IP and last-known position EXCLUDED from this map's position solve.":"RF-ONLY OFF · The main automatic position may use GNSS/device providers; antenna observations remain separately attributed.");
}
function setRfOnly(enabled){
 if(stopped)return;
 rfOnly=!!enabled;
 if($("rf-only"))$("rf-only").checked=rfOnly;
 solution=null; // explicit solve required after switching mode; never silently mix sources
 render();if(rfOnly)compute();else{solution=null;rangeEstimates=[];broadcast();}
 window.dispatchEvent(new CustomEvent("tihulu:rf-only-mode",{detail:{enabled:rfOnly}}));
}
function addSource(){
 if(stopped)return;
 const name=String($("rf-name")?.value||"").trim();
 const type=$("rf-type")?.value,frequencyMHz=Number($("rf-freq")?.value);
 const lat=Number($("rf-lat")?.value),lon=Number($("rf-lon")?.value);
 if(!name||name.length>100||!["station","aircraft","satellite"].includes(type)||
   !["rf-lat","rf-lon","rf-freq"].every(id=>$(id)?.value.trim())||
   ![lat,lon,frequencyMHz].every(Number.isFinite)||Math.abs(lat)>90||Math.abs(lon)>180||
   frequencyMHz<24||frequencyMHz>1766)throw Error("Name, source type, MHz frequency and valid source coordinates are required");
 if(sources.length>=60)throw Error("Maximum 60 source records per local survey");
 const id="rf-"+Date.now().toString(36)+"-"+sources.length;
 sources.push({id,name,type,frequencyMHz,lat,lon,calibration:null,lastObservation:null,rangeHypothesis:null});
 selected=id;persist();compute();render();
 message("rf-measurement-status","Added USER-SUPPLIED "+type+" source "+name+". Coordinates/frequency are NOT identified or confirmed by the RTL-SDR.");
}
function addCatalogCandidate(candidate){
 if(stopped)return false;
 if(!candidate||candidate.type!=="station"||!String(candidate.id).startsWith("osm-")||
   !Number.isFinite(candidate.lat)||Math.abs(candidate.lat)>90||!Number.isFinite(candidate.lon)||Math.abs(candidate.lon)>180||
   !Number.isFinite(candidate.frequencyMHz)||candidate.frequencyMHz<87.5||candidate.frequencyMHz>108)
  return false;
 if(sources.some(s=>s.catalogId===candidate.id&&Math.abs(s.frequencyMHz-candidate.frequencyMHz)<.001))return false;
 if(sources.length>=60)return false;
 const id="catalog-"+String(candidate.id).slice(0,74)+"-"+String(Math.round(candidate.frequencyMHz*1000));
 if(sources.some(s=>s.id===id))return false;
 sources.push({id,catalogId:candidate.id,name:String(candidate.name||"OSM transmitter").slice(0,100),
  lat:candidate.lat,lon:candidate.lon,type:"station",frequencyMHz:candidate.frequencyMHz,
  catalog:"OpenStreetMap/Overpass",metadataOrigin:"PUBLIC OSM SITE / FREQUENCY TAG · RF IDENTITY NOT DECODED",
  calibration:null,lastObservation:null,rangeHypothesis:null,transmitterIdentityVerified:false});
 selected=id;return true;
}
function capture(){
 const s=sourceById();
 if(!s){message("rf-measurement-status","Select or add a source first.");return}
 message("rf-measurement-status","Requesting actual RTL-SDR I/Q capture at "+s.frequencyMHz.toFixed(3)+" MHz. This does not identify the broadcaster or measure its distance.");
 window.dispatchEvent(new CustomEvent("tihulu:rf-capture-request",{detail:{frequencyMHz:s.frequencyMHz,sourceId:s.id}}));
}
function acceptCapture(event){
 if(stopped)return;
 const observation=event.detail;
 const s=sources.find(source=>source.id===observation?.sourceId);
 if(!s||!observation||observation.hardwareId!=="RTL2832U WebUSB 0bda:2838"||
   Math.abs(observation.frequencyMHz-s.frequencyMHz)>.001)return;
 if(!Number.isFinite(observation.levelDbFS)||observation.sampleBytes<1024||observation.gainDb!==20)return;
 s.lastObservation={...observation};s.rangeHypothesis=null;
 if(s.type==="station"&&s.calibration){
  try{
   if(observation.measuredAt===s.calibration.observedAt)throw Error("Calibration capture cannot be reused as a new-site range measurement");
   s.rangeHypothesis=calibratedRange(observation,s.calibration);
  }catch(e){message("rf-measurement-status","REAL RF CAPTURED, range model blocked: "+e.message)}
 }
 message("rf-measurement-status","HARDWARE RF CAPTURE · "+s.name+" · "+observation.sampleBytes+
   " I/Q bytes · "+observation.levelDbFS.toFixed(2)+" dBFS-like · "+
   observation.measuredAt+" · fixed gain "+observation.gainDb+" dB. "+
   (s.rangeHypothesis?"CALIBRATED DISTANCE HYPOTHESIS "+Math.round(s.rangeHypothesis.rangeMeters)+" m (±factor ~3 illustrative, NOT accuracy).":"No validated distance; calibration required. ")+
   " The emitter identity at this frequency is NOT verified by signal decoding.");
 compute();render();
}
function saveCalibration(){
 const s=sourceById();
 if(!s||s.type!=="station")throw Error("Only fixed ground radio sources can calibrate the 2D RSSI model");
 if(!s.lastObservation)throw Error("First measure actual RF with the connected RTL-SDR at a known-distance site");
 const distance=Number($("rf-cal-distance")?.value),exponent=Number($("rf-exponent")?.value);
 if(!$("rf-cal-distance")?.value.trim()||!Number.isFinite(distance)||distance<1||distance>100000||
     !Number.isFinite(exponent)||exponent<1.5||exponent>6)
  throw Error("Enter a real independently KNOWN distance 1–100000 m and path-loss exponent 1.5–6");
 const o=s.lastObservation;
 s.calibration={referenceLevelDbFS:o.levelDbFS,referenceDistanceMeters:distance,
  pathLossExponent:exponent,referenceFrequencyMHz:o.frequencyMHz,
  referenceGainDb:o.gainDb,referenceSampleRate:o.sampleRate,observedAt:o.measuredAt,
  provenance:"REFERENCE DISTANCE SUPPLIED BY USER · RF LEVEL CAPTURED FROM REAL RTL-SDR"};
 s.rangeHypothesis=null;persist();compute();render();
 message("rf-measurement-status","Calibration saved from real I/Q signal level at independently known "+distance+
   " m for "+s.name+". NEXT: move antenna to unknown position and capture the same frequency with identical hardware settings.");
}
function fitMap(){window.dispatchEvent(new Event("tihulu:rf-fit-map"))}
export function initRFSurvey(){
 if(!$("rf-add"))return;
 sources=safeLoad();selected=sources[0]?.id||"";render();compute();
 $("rf-add").addEventListener("click",()=>{try{addSource()}catch(e){message("rf-measurement-status",e.message)}});
 $("rf-source-select")?.addEventListener("change",v=>{selected=v.target.value;render()});
 window.addEventListener("tihulu:rf-autosource",e=>{
   const ok=addCatalogCandidate(e.detail);
   if(ok){persist();compute();render();message("rf-measurement-status","Imported OSM broadcast SITE CANDIDATE with tagged FM frequency. Antenna reception and source identity NOT verified.")}
   else message("rf-measurement-status","Catalog source not imported: frequency absent/invalid, already listed or 60-source limit reached.");
 });
 window.addEventListener("tihulu:rf-autosources",e=>{
   const candidates=Array.isArray(e.detail)?e.detail:[];
   let added=0;for(const candidate of candidates.slice(0,90)){if(addCatalogCandidate(candidate))added++}
   persist();compute();render();
   message("rf-measurement-status",added+" OSM catalog candidate(s) auto-added with explicit FM frequency. These are EXTERNAL transmitter references, NOT measured RF signals or distance rings.");
 });

 window.addEventListener("tihulu:rf-select-source",event=>{
   const wanted=event.detail||{};
   const matched=sources.find(s=>
     (wanted.id&&s.id===wanted.id)||
     (wanted.catalogId&&s.catalogId===wanted.catalogId&&
       Number.isFinite(wanted.frequencyMHz)&&Math.abs(s.frequencyMHz-wanted.frequencyMHz)<.001));
   if(!matched){
     message("rf-measurement-status","Selected map site has no measured FM source yet. Only frequency-tagged fixed sites are eligible; confirm transmitter and radio identity before calibrating.");
     return;
   }
   selected=matched.id;render();
   message("rf-measurement-status","Selected "+matched.name+" · "+matched.frequencyMHz.toFixed(3)+
     " MHz from "+(matched.metadataOrigin||"external reference")+
     ". Next: Measure RF with antenna, then provide a separately known true transmitter distance for reference calibration. Source identity is UNVERIFIED.");
 });
 $("rf-only")?.addEventListener("change",v=>setRfOnly(v.target.checked));
 $("rf-capture")?.addEventListener("click",capture);
 $("rf-calibrate")?.addEventListener("click",()=>{try{saveCalibration()}catch(e){message("rf-measurement-status",e.message)}});
 $("rf-solve")?.addEventListener("click",()=>{compute();render()});
 $("rf-fit-map")?.addEventListener("click",fitMap);
 $("rf-clear")?.addEventListener("click",()=>{sources=[];selected="";solution=null;rangeEstimates=[];localStorage.removeItem(KEY);compute();render();
   message("rf-measurement-status","Local RF-only survey cleared. No OS location requested.");});
 window.addEventListener("tihulu:rf-observation",acceptCapture);
 window.addEventListener("tihulu:rf-survey-clear-all",()=>{sources=[];selected="";solution=null;rangeEstimates=[];localStorage.removeItem(KEY);compute();render()});
 function stop(){
   if(stopped)return;
   stopped=true;rfOnly=false;solution=null;rangeEstimates=[];
   sources=sources.map(s=>({...s,lastObservation:null,rangeHypothesis:null}));
   const toggle=$("rf-only");if(toggle)toggle.checked=false;
   message("rf-session-status","RF MODULE STOPPED — reload to start a new RF session. Other applications and their SDR leases are unaffected.");
   message("rf-solution-report","No active RF solver or pending radio observation.");
   window.dispatchEvent(new CustomEvent("tihulu:rf-only-mode",{detail:{enabled:false,stopped:true}}));
 }
 return {stop};

}
