/* Map-first, three-input geolocation UI.
 * The checkbox options control display/acquisition requests, NOT fabricated position fixes.
 * GPS/OS, RTL-SDR hardware and DVB-T2 service metadata are distinct sources.
 */
import {parseDvbV5Scan} from "../core/dvb_scan.mjs";
const $=id=>document.getElementById(id);
const KEY="tihulu.rfgeo.simple-ui-options.v1";
const TVKEY="tihulu.rfgeo.native-dvb-channel-list.v1";
const METHODS=["simple-gps","simple-sdr","simple-tv"];
const SOURCES=[["simple-ground","layer-stations"],["simple-aircraft","layer-aircraft"],["simple-satellites","layer-orbits"]];
const on=id=>!!$(id)?.checked;
const status=(id,v)=>{const el=$(id);if(el)el.textContent=String(v)};
const gotoRadio=fn=>{fn("radio");$("radio-advanced-tools").open=false};
const persist=()=>{
 try{localStorage.setItem(KEY,JSON.stringify(Object.fromEntries([...METHODS,...SOURCES.map(x=>x[0])].map(id=>[id,on(id)]))))}catch{}
};
function bindHardwareAndSources(state){
 for(const [a,b] of SOURCES){const target=$(b),pick=$(a);
  if(!target||!pick)return;
  target.checked=pick.checked;target.dispatchEvent(new Event("change"));
 }
 // RF-only is a scientifically strict source filter: forbid using device GPS/OS
 // when only radio or DVB hardware methods are selected.
 const pureRF=!on("simple-gps")&&(on("simple-sdr")||on("simple-tv"));
 const rf=$("rf-only");
 if(rf&&rf.checked!==pureRF){rf.checked=pureRF;rf.dispatchEvent(new Event("change"))}
 persist();
}
function explain(state,source){
 const p=source();
 const note=[];
 if(p.validObserver){note.push("YOUR LOCATION · "+p.kind+" · "+p.lat.toFixed(5)+", "+p.lon.toFixed(5));
  if(p.kind.includes("Browser"))note.push("GPS/Wi-Fi/cellular method unknown to browser");
 }else if(state.rfSolution){
  note.push("RF MODEL ONLY · "+state.rfSolution.lat.toFixed(5)+", "+state.rfSolution.lon.toFixed(5)+" · UNVALIDATED");
 }else if(state.cachedPosition&&!state.rfOnly){
  note.push("LAST KNOWN / NOT LIVE · "+state.cachedPosition.recordedAt);
 }else note.push("NO MEASURED LOCATION · map is a REFERENCE, not your coordinates");
 status("simple-result",note.join(" · "));
 const measured=(state.rfRanges||[]).length+(state.rangeInputs||[]).length;
 const tv=(state.dvbChannels||[]).length;
 status("simple-sources",
  "Device: "+(state.serialFix?"GNSS available":state.browser?"Browser fix":"no fresh fix")+
  " · RTL-SDR: "+state.usbStatus+
  " · TV: "+tv+" imported channels"+
  " · Ground: "+((state.catalogTowers||[]).length+(state.rfSources||[]).filter(x=>x.type==="station").length)+
  " · Aircraft: "+((state.catalogAntennaAircraft||[]).length+(state.catalogAircraft||[]).length)+
  " · Satellites: "+(state.autoOrbits||[]).length+" predicted"+
  " · RF range hypotheses: "+measured);
}
function showDvb(channels){
 const list=$("simple-tv-channels");if(!list)return;
 list.replaceChildren();
 const head=document.createElement("p");
 head.textContent=channels.length?channels.length+" imported native DVB channel entries":"No TV metadata imported";
 list.append(head);
 for(const s of channels.slice(0,60)){
  const row=document.createElement("div");row.className="simple-channel";
  const title=document.createElement("strong");title.textContent=s.name;
  const desc=document.createElement("small");
  desc.textContent=s.frequencyMHz.toFixed(3)+" MHz · "+s.deliverySystem+
    " · service ID "+(s.serviceId??"unknown")+
    " · network ID "+(s.networkId??"unknown")+" · SOURCE: FILE / NO TRANSMITTER POSITION";
  row.append(title,desc);list.append(row);
 }
}
function restoreDvb(){
 try{
  const val=JSON.parse(localStorage.getItem(TVKEY)||"null");
  if(val&&Array.isArray(val.channels)&&val.channels.length<=300)return val.channels.filter(x=>x&&Number.isFinite(x.frequencyHz)&&typeof x.name==="string");
 }catch{}
 return [];
}
export function initSimpleUI({state,source,setView,renderEarth,renderPosition,fitRfSurveyMap}){
 const saved=(()=>{try{return JSON.parse(localStorage.getItem(KEY)||"null")}catch{return null}})();
 for(const id of [...METHODS,...SOURCES.map(x=>x[0])]){
  const e=$(id);if(e&&typeof saved?.[id]==="boolean")e.checked=saved[id];
 }
 state.dvbChannels=restoreDvb();showDvb(state.dvbChannels);
 if(state.dvbChannels.length)status("simple-tv-status",state.dvbChannels.length+
  " DVB channel records loaded from locally saved imported scan; not a live tuner scan or location measurement.");
 const nav=$("show-advanced-nav"),advanced=$("advanced-nav");
 nav?.addEventListener("click",()=>{
  const visible=advanced.hasAttribute("hidden");
  if(visible)advanced.removeAttribute("hidden");else advanced.setAttribute("hidden","");
  nav.setAttribute("aria-expanded",String(visible));
 });
 // Hidden demo rings should not appear on the default simplified locator.
 const demo=$("layer-demo");if(demo?.checked){demo.checked=false;demo.dispatchEvent(new Event("change"))}
 const targetSlot=$("radio-usb-slot"),usb=$("usb-select");
 if(targetSlot&&usb)targetSlot.append(usb); // Move EXISTING authorized receiver button, do not fake-click USB permission.
 for(const id of [...METHODS,...SOURCES.map(x=>x[0])]){
  $(id)?.addEventListener("change",()=>{bindHardwareAndSources(state);renderEarth();explain(state,source)});
 }
 bindHardwareAndSources(state);
 $("simple-find")?.addEventListener("click",()=>{
  if(!METHODS.some(on)){status("simple-result","Select at least one hardware or positioning method.");return}
  if(on("simple-gps")){
   window.dispatchEvent(new Event("tihulu:find-request"));
   if(on("simple-sdr")||on("simple-tv"))status("simple-result",
     "Device location requested. Radio/TV source layers are selected separately; scan hardware in Radio / TV Scan. RF-only fix is not yet established.");
   return;
  }
  if(on("simple-sdr")&&state.rfSolution){
   fitRfSurveyMap();explain(state,source);return;
  }
  gotoRadio(setView);
  if(on("simple-tv")&&!on("simple-sdr"))$("simple-tv-guide").open=true;
  status("simple-result","GPS disabled. No current antenna-derived location fix. Scan selected receiver and view actual metadata; transmitter positions or RF strength alone cannot establish your position.");
 });
 $("simple-scan")?.addEventListener("click",()=>{
  if(!on("simple-sdr")&&!on("simple-tv")){
   status("simple-result","Choose RTL-SDR or TV hardware to scan. GPS/device is found via Find My Location.");
   return;
  }
  gotoRadio(setView);
  if(on("simple-tv"))$("simple-tv-guide").open=true;
  if(on("simple-sdr")){
   if(!String(state.usbStatus).includes("CONNECTED")){
    status("quick-radio-status","Connect RTL-SDR using the visible button above, then press Scan FM band. The app cannot bypass the browser's USB chooser.");
   }else $("quick-radio-scan")?.click();
  }
  if(on("simple-tv"))status("simple-tv-status",
    "Hauppauge native DVB tuner selected. Browser-only Pages cannot scan it directly; use the local DVB scan instructions, then import actual DVBv5 channel metadata.");
 });
 $("simple-fit")?.addEventListener("click",()=>{
  if(state.rfRanges.length||state.rfSolution){fitRfSurveyMap();return}
  if(state.rangeInputs.length){setView("earth");$("earth-fit-evidence")?.click();return}
  status("simple-result","No measured/calibrated radio distances to draw. Open Radio / TV Scan; catalog tower positions and aircraft alone are not ranging measurements.");
 });
 $("quick-radio-discover")?.addEventListener("click",()=>{
  window.dispatchEvent(new CustomEvent("tihulu:catalog-map-center",{detail:{lat:state.map.lat,lon:state.map.lon}}));
  $("catalog-discover")?.click();
  status("quick-radio-status","Searching nearby mapped broadcast transmitters. Catalog data is a reference only, not antenna evidence.");
 });
 $("quick-radio-scan")?.addEventListener("click",()=>{
  $("catalog-fm-scan")?.click();
  status("quick-radio-status","Requested a real FM sweep through the connected RTL-SDR. Consult the scan result below; tuner-level energy does not identify a transmitter.");
 });
 $("quick-radio-release")?.addEventListener("click",()=>$("hard-stop")?.click());
 $("simple-dvb-file")?.addEventListener("change",async e=>{
  const file=e.currentTarget.files?.[0];if(!file)return;
  try{
   if(file.size>1024*1024)throw Error("DVB channel file must be 1 MiB or smaller");
   const channels=parseDvbV5Scan(await file.text());
   if(!channels.length)throw Error("No supported DVBv5 channel sections with valid FREQUENCY found. Export a DVBv5 channel list from your Linux DVB scanner.");
   state.dvbChannels=channels;
   try{localStorage.setItem(TVKEY,JSON.stringify({importedAt:new Date().toISOString(),channels}))}catch{}
   showDvb(channels);
   status("simple-tv-status","Imported "+channels.length+" DVB channel entries from "+file.name+
      ". This is native scan metadata, NOT a browser hardware scan; no receiver location or transmitter coordinates are present.");
   window.dispatchEvent(new CustomEvent("tihulu:dvb-metadata-imported",{detail:{channels:channels.length}}));
   explain(state,source);
  }catch(error){status("simple-tv-status","TV import failed: "+String(error.message||error))}
  finally{e.currentTarget.value=""}
 });
 window.addEventListener("tihulu:catalog-updated",e=>{
  const d=e.detail||{};
  status("quick-radio-status",String(d.towers?.length||0)+" mapped broadcasting-site candidates · "+
    String(d.antennaAircraft?.length||0)+" real local ADS-B aircraft · "+
    String(d.aircraft?.length||0)+" internet aircraft · "+
    String(d.fmReadings?.length||0)+" real RF band sample points (not source IDs).");
  explain(state,source);
 });
 window.addEventListener("tihulu:receiver-status",()=>explain(state,source));
 window.addEventListener("tihulu:rf-survey-updated",()=>explain(state,source));
 window.addEventListener("tihulu:simple-refresh",()=>explain(state,source));
 explain(state,source);
}
