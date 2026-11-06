/* TIHULU RF Geolocation Center — browser-only MVP.
   Unavailable RF features must never be reported as acquired signals. */
import {GNSS,DEFAULT_CENTER,parseSP3,visibleSatellites,rtlSignalClass,validateLLA} from "../core/gnss.mjs";
import {parseNMEA,trilaterate2D,tdoaConstraints} from "../core/positioning.mjs";
import {initAutoExplorer} from "./auto_explorer.mjs";
import {initUsbSDR} from "./usb_sdr.mjs";
import {initRFSurvey} from "./rf_survey.mjs";
import {initCatalogDiscovery} from "./catalog_discovery.mjs";
import {initSimpleUI} from "./simple_ui.mjs";
import {initHardwareManager} from "./hardware_manager.mjs";
import {initDVBBridge} from "./dvb_bridge_client.mjs";
import {matchedBroadcastSources,mapBoundsForSources} from "../core/scan_map.mjs";
import {exampleRings,ringPoints,validRangeSources} from "../core/evidence.mjs";
import {LOCATION_LAYERS,layerReadiness,visibleLayerPreferences} from "../core/location_layers.mjs";
import {positionProvenance,radioProvenance,orbitalProvenance,aircraftProvenance} from "../core/source_provenance.mjs";

const $=id=>document.getElementById(id), svgNS="http://www.w3.org/2000/svg";
const state={
  browser:null,networkFix:null,serialFix:null,serialAt:0,receiverHistory:[],gnssFile:null,sp3:null,layerPrefs:null,
  rfOnly:false,rfSources:[],rfRanges:[],rfSolution:null,catalogTowers:[],catalogAircraft:[],catalogAntennaAircraft:[],catalogFM:[],usbStatus:"NOT CONNECTED",usbMessage:"No RF sample from antenna",
  time:null,mask:5,visible:[],autoOrbits:[],references:[],ranges:null,rangeInputs:[],tdoa:[],cachedPosition:null,
  map:{lat:DEFAULT_CENTER.lat,lon:DEFAULT_CENTER.lon,zoom:11,osm:false},
  serialPort:null,serialReader:null,reading:false,usbSelection:null,activeView:"dashboard"
};
const fmt=(n,d=5)=>Number(n).toFixed(d);
const msg=m=>{$("notice").textContent=m;$("foot-status").textContent=m.slice(0,80)};
const safeCoord=(lat,lon)=>{validateLLA(lat,lon);return {lat,lon}};
const make=(tag,cls,text)=>{const e=document.createElement(tag);if(cls)e.className=cls;if(text!=null)e.textContent=text;return e};
function svgel(tag,attrs={},label){
 const e=document.createElementNS(svgNS,tag);
 for(const [k,v] of Object.entries(attrs))e.setAttribute(k,String(v));
 if(label!=null)e.textContent=label;
 return e;
}
const STORAGE_LOCATION="tihulu.rfgeo.last-known-position.v1";
const STORAGE_RANGES="tihulu.rfgeo.measured-ranges.v1";
const STORAGE_REFS="tihulu.rfgeo.reference-points.v1";
const STORAGE_LAYERS="tihulu.rfgeo.location-method-layers.v1";
const store=(key,value)=>{try{localStorage.setItem(key,JSON.stringify(value))}catch{}};
const restore=key=>{try{return JSON.parse(localStorage.getItem(key)||"null")}catch{return null}};
const layerToggle=id=>document.getElementById(({gnss:"layer-gnss",device:"layer-device",gpsfree:"layer-gpsfree",radio:"layer-ranges",aircraft:"layer-aircraft",ground:"layer-stations",satellites:"layer-orbits",cached:"layer-cached",demo:"layer-demo"})[id]);
const layerShown=id=>layerToggle(id)?.checked===true;
const saveLayerPreferences=()=>{state.layerPrefs=Object.fromEntries(LOCATION_LAYERS.map(l=>[l.id,layerShown(l.id)]));store(STORAGE_LAYERS,state.layerPrefs)};
function showOnlyLayers(ids){for(const l of LOCATION_LAYERS){const e=layerToggle(l.id);if(e)e.checked=ids.includes(l.id)}saveLayerPreferences();renderEarth()}
function renderMethodReadiness(orbits){
 const r=layerReadiness({...state,orbits},Date.now());
 if(state.rfRanges.length){r.radio.state=state.rfSolution?"RF MODEL":"RF ESTIMATE";r.radio.count=state.rfRanges.length;r.radio.detail="REAL RTL-SDR I/Q plus external transmitter coordinates and calibration; distance NOT directly measured, accuracy NOT validated";}
 const air=state.rfSources.filter(s=>s.type==="aircraft").length,ground=state.rfSources.filter(s=>s.type==="station").length,satelliteRefs=state.rfSources.filter(s=>s.type==="satellite").length;
 if(state.catalogAircraft.length){r.aircraft.count+=state.catalogAircraft.length;r.aircraft.state="INTERNET REFS";r.aircraft.detail="OpenSky aircraft coordinates from internet, not local RTL-SDR reception"}
 if(state.catalogAntennaAircraft.length){r.aircraft.count+=state.catalogAntennaAircraft.length;r.aircraft.state="RF ADS-B";r.aircraft.detail="CRC-verified aircraft decoded from real 1090 MHz RTL-SDR in Tihulu Flight Radar; not range or receiver fix"}
 if(state.catalogTowers.length){r.ground.count+=state.catalogTowers.length;r.ground.state="OSM CATALOG";r.ground.detail="OpenStreetMap broadcast-site candidates; no verified RF identity or measured range"}
 if(air){r.aircraft.count+=air;r.aircraft.state="REFERENCES";r.aircraft.detail="Imported and user-entered aircraft positions are references; RF energy does not verify source identity";}
 if(ground){r.ground.count+=ground;r.ground.state="REFERENCES";r.ground.detail="Ground station coordinates are external metadata; RF level and calibrated range require actual antenna samples";}
 if(satelliteRefs){r.satellites.detail+=" · "+satelliteRefs+" RF survey satellite coordinate references supplied by user (NOT tracked RF)";}
 if(state.rfOnly){for(const key of ["gnss","device","gpsfree","cached"]){r[key].state="EXCLUDED";r[key].detail="RF-ONLY session explicitly forbids using this source for positioning"}}
 for(const layer of LOCATION_LAYERS){const d=r[layer.id],label=$("layer-status-"+layer.id);
   if(label){label.textContent=d.state+(d.count&&d.count>1?" · "+d.count:"");label.title=d.detail;
     label.dataset.available=String(!["UNAVAILABLE","NO FIX","NO DATA","NO MEASUREMENT"].includes(d.state));}
 }
 const lines=[r.gnss.state==="FIX"?"Dedicated GNSS fix available":"Dedicated GNSS: no current fix",
 r.device.state==="FIX"?"Browser device fix (GPS/network method unknown)":"Browser/device: no current fix",
 state.rfRanges.length?"Radio antenna: "+state.rfRanges.length+" calibrated RSSI distance hypotheses (NOT measured ranges)":r.radio.state==="ESTIMATED"?"Radio: imported measured-range estimate":"Radio: no measured ranges",
 "GPS-free provider: "+r.gpsfree.state.toLowerCase(),
 r.aircraft.count+" aircraft references, "+r.ground.count+" ground stations, "+r.satellites.count+" predicted satellite subpoints"];
 setText("layer-explanation",lines.join(" · "));
 setText("live-method-summary",state.rfOnly?"RF-ONLY HARDWARE SESSION · RTL-SDR antenna observations: "+state.rfSources.filter(s=>s.hasActualRF).length+" · calibrated range hypotheses: "+state.rfRanges.length+" · "+(state.rfSolution?"Experimental RSSI MODEL position":"No RF position")+" · Browser GPS/Wi-Fi/IP excluded":"GPS/GNSS: "+r.gnss.state+" · Device: "+r.device.state+" (method unknown) · GPS-free: "+r.gpsfree.state+" · Radio: "+r.radio.state+" · Aircraft: "+r.aircraft.count+" refs · Satellites: "+r.satellites.count+" predicted");
}
function renderSourceProvenance(){
 const pos=state.rfOnly?{source:"RTL-SDR ANTENNA ONLY",fix:state.rfSolution?"EXPERIMENTAL RSSI ESTIMATE · UNVERIFIED":"NO RF POSITION FIX",acquisition:"Real USB I/Q levels + external user-supplied transmitter coordinates/calibration; no GPS/Wi-Fi/IP",detail:"RF captures are real; ranges are propagation-model hypotheses, not measured distances. Browser geolocation never enters this solver."}:positionProvenance(state),rf=radioProvenance(state.usbStatus,state.usbMessage);
 const orb=orbitalProvenance(!!state.sp3,state.sp3?.satelliteCount??state.autoOrbits.length);
 const air=aircraftProvenance(state.references);
 setText("origin-position",pos.source);
 setText("origin-position-status",pos.fix);
 setText("origin-position-method",pos.acquisition);
 setText("origin-position-detail",pos.detail);
 setText("origin-antenna",rf.source);
 setText("origin-antenna-status",rf.status);
 setText("origin-antenna-method",rf.acquisition);
 setText("origin-antenna-detail",rf.detail);
 setText("origin-orbits",orb.source);
 setText("origin-orbits-method",orb.acquisition);
 setText("origin-orbits-detail",orb.detail);
 setText("origin-aircraft",air.source);
 setText("origin-aircraft-method",air.acquisition);
 setText("origin-aircraft-detail",air.detail);
 setText("source-proof","LOCATION: "+pos.source+" — "+pos.fix+" | ACQUIRED VIA: "+pos.acquisition+
  " | RTL-SDR ANTENNA: "+rf.status+" — "+(rf.hasRF?"RF sample only, NO FIX":"no antenna-derived position")+
  " | SATELLITES: "+orb.source+" (NOT RF) | AIRCRAFT: "+air.source+" (NOT observer position).");
}

function source(){
 if(state.rfOnly){
  if($("simple-tv")?.checked&&!$("simple-sdr")?.checked)return {...DEFAULT_CENTER,kind:"TV ONLY / NO RECEIVER POSITION · REFERENCE MAP CENTER",validObserver:false};
  if(state.rfSolution)return {...state.rfSolution,kind:"RF-ONLY CALIBRATED RSSI HYPOTHESIS · NO GPS/OS",validObserver:false};
  return {...DEFAULT_CENTER,kind:"RF-ONLY / NO VALID RADIO FIX · REFERENCE MAP CENTER",validObserver:false};
 }
 if(state.serialFix&&Date.now()-state.serialAt<90000)
  return {...state.serialFix,kind:"NMEA receiver — live",validObserver:true};
 if(state.browser&&Date.now()-Date.parse(state.browser.acquiredAt||0)<5*60*1000)return {...state.browser,kind:"Browser / device location",validObserver:true};
 if(state.ranges)return {...state.ranges,kind:"EXPERIMENTAL 2D RANGE ESTIMATE (UNVERIFIED)",validObserver:false};
 if(state.cachedPosition)return {...state.cachedPosition,kind:"LAST KNOWN (CACHED, NOT LIVE) · "+state.cachedPosition.provider,validObserver:false};
 // Imported aircraft JSON is an untrusted reference, NOT authenticated
 // ADS-B receiver observation. A future trusted Flight Radar adapter must
 // supply verified observations before aircraft-centered fallback is enabled.
 return {...DEFAULT_CENTER,kind:"Cologne reference (NOT your position)",validObserver:false};
}
function distanceRef(p){const a=(p.lat-DEFAULT_CENTER.lat),b=(p.lon-DEFAULT_CENTER.lon)*Math.cos(DEFAULT_CENTER.lat*Math.PI/180);return a*a+b*b}
function setText(id,value){if($(id))$(id).textContent=String(value)}
function renderPosition(recenter=false){
 const p=source();
 setText("position-tag",p.validObserver?"LOCATION: "+p.kind.toUpperCase():p.kind.startsWith("EXPERIMENTAL")?"ESTIMATE · UNVERIFIED":p.kind.startsWith("LAST KNOWN")?"CACHED · NOT LIVE":"REFERENCE ONLY");
 setText("dash-provider",p.kind);
 setText("dash-coordinates",fmt(p.lat,6)+"° · "+fmt(p.lon,6)+"°"+(p.accuracy!=null?" · browser ±"+Math.round(p.accuracy)+" m":""));
 setText("earth-source",p.kind);
 renderFixEvidence(p);
 setText("map-center-label",p.validObserver?"LOCATION / "+p.kind.toUpperCase():p.kind.toUpperCase());
 if(recenter){state.map.lat=p.lat;state.map.lon=p.lon;state.map.zoom=Math.max(state.map.zoom,11)}
 renderEarth();
 window.dispatchEvent(new Event("tihulu:simple-refresh"));
}

function renderFixEvidence(p=source()){
 const pane=$("fix-evidence");if(!pane)return;
 if(state.rfOnly){
  pane.textContent=state.rfSolution&&(!($("simple-tv")?.checked&&!$("simple-sdr")?.checked))?"RF-ONLY HARDWARE-BASED PROPAGATION HYPOTHESIS · "+fmt(state.rfSolution.lat,6)+", "+fmt(state.rfSolution.lon,6)+" · "+state.rfRanges.length+" calibrated radio sources. Antenna IQ measured; transmitter identity/coordinates and calibration external; NO browser/GNSS/IP fallback and NO certified accuracy.":"RF-ONLY ACTIVE · NO RF POSITION FIX. Connect RTL-SDR, enter known fixed stations, capture actual RF, independently calibrate and solve. Device GPS, Wi-Fi, IP, cached coordinates excluded.";
  return;
 }
 const offline=navigator.onLine===false;
 const connection=offline?"OFFLINE · ":"";
 if(state.serialFix&&Date.now()-state.serialAt<90000){
   const s=state.serialFix;
   pane.textContent=connection+"LIVE GNSS RECEIVER FIX · "+fmt(s.lat,6)+", "+fmt(s.lon,6)+
     " · "+(s.usedSatellites??"unknown")+" satellites used (receiver reported)"+
     " · HDOP "+(s.hdop??"not available")+
     " · device/receiver measurement; not obtained by RTL-SDR GNSS demodulation.";
 }else if(p.validObserver&&state.browser){
   const a=state.browser.accuracy;
   pane.textContent=connection+"BROWSER / DEVICE LOCATION · "+fmt(p.lat,6)+", "+fmt(p.lon,6)+
     (Number.isFinite(a)?" · reported horizontal accuracy radius ±"+Math.round(a)+" m":" · accuracy not reported")+
     " · source may be GPS, Wi-Fi, cellular or other OS positioning; the browser does not identify which."+
     " Purple ring: browser-reported uncertainty, not a radio station range.";
 }else if(state.ranges){
   pane.textContent=connection+"EXPERIMENTAL RANGE ESTIMATE, NOT VERIFIED · "+fmt(p.lat,6)+", "+fmt(p.lon,6)+
     " · "+state.rangeInputs.length+" user-imported unverified distance measurements."+
     " No certified accuracy; source ages and calibration must be checked.";
 }else if(state.cachedPosition){
   pane.textContent=connection+"LAST KNOWN LOCATION · "+fmt(p.lat,6)+", "+fmt(p.lon,6)+
     " · saved "+state.cachedPosition.recordedAt+" · CACHED ONLY, NOT A NEW POSITION FIX.";
 }else{
   pane.textContent=connection+"POSITION NOT FOUND · No live GNSS/NMEA fix, browser location, measured ranges or saved position."+
     " Cologne map center is an orientation reference, NOT your location.";
 }
}

function recordFix(p,provider){
 const item={lat:p.lat,lon:p.lon,provider,observedAt:new Date().toISOString(),alt:p.altEllipsoidMeters??null,accuracyMeters:provider==="Browser / device location"?p.accuracy??null:null};
 state.receiverHistory.push(item);
 if(state.receiverHistory.length>500)state.receiverHistory.shift();
 renderHistory();
 state.cachedPosition={...item,provider,recordedAt:item.observedAt};store(STORAGE_LOCATION,state.cachedPosition);
 window.dispatchEvent(new CustomEvent("tihulu:position",{detail:{lat:p.lat,lon:p.lon,alt:p.altEllipsoidMeters??p.alt??0,provider,accuracy:p.accuracy??null}}));
}
function renderCatalog(){
 const c=$("gnss-catalog");c.replaceChildren();
 for(const s of GNSS){
   const panel=make("article","panel");panel.append(make("h2","",s.system),make("p","muted",s.operator+" · "+s.type));
   const ul=make("ul");
   for(const [signal,mhz] of s.signals){
     const li=make("li",null,signal+" — "+(mhz===null?"frequency depends on channel":mhz.toFixed(3)+" MHz"));
     li.title=rtlSignalClass(mhz);ul.append(li);
   }
   panel.append(ul,make("p","fine muted","Reference catalog only — no RF lock or decoder verified"));c.append(panel);
 }
}
function renderDiagnostics(){
 const c=$("diagnostic-list");c.replaceChildren();
 const rows=[
   ["Browser position",state.browser?"Permission-granted position":"Unavailable"],
   ["Dedicated GNSS NMEA",state.serialFix&&Date.now()-state.serialAt<90000?"Current valid serial receiver fix":state.gnssFile?"Historical receiver import":"Unavailable"],
   ["Precise orbit",state.sp3?state.sp3.satelliteCount+" satellites from imported SP3 file":"No orbit file imported"],
   ["RF acquisition",state.rfSources.filter(s=>s.hasActualRF).length+" actual RTL-SDR frequency readings (NOT decoded station identities); GNSS SDR demodulation unavailable"],
   ["RF-only experiment",state.rfOnly?"ENABLED; "+state.rfRanges.length+" calibrated range hypotheses; "+(state.rfSolution?"uncertified experimental position":"no position"):"OFF; main location sources independent"],
   ["Aircraft reference",state.references.filter(p=>p.type==="aircraft").length+" imported aircraft references (NOT receiver-verified)"],
   ["Measured station ranges",state.ranges?state.ranges.usedRanges+" user-provided measurements":"Unavailable"],
   ["TDOA synchronized constraints",state.tdoa.length?state.tdoa.length+" imported constraints":"Unavailable"]
 ];
 for(const [a,b] of rows)c.append(make("div","list-item",a+" — "+b));
}
function renderHistory(){
 const c=$("history-list");c.replaceChildren();
 if(!state.receiverHistory.length){c.append(make("p","muted","No valid position recorded."));return}
 for(const p of state.receiverHistory.slice(-100).reverse())c.append(make("div","list-item",p.observedAt+" · "+p.provider+" · "+fmt(p.lat,6)+", "+fmt(p.lon,6)));
}
function setView(name){
 state.activeView=name;
 for(const v of document.querySelectorAll(".view"))v.classList.toggle("active",v.id==="view-"+name);
 for(const n of document.querySelectorAll("#nav button"))n.classList.toggle("selected",n.dataset.view===name);
 const chosen=document.querySelector("#nav button[data-view='"+name+"']");
 setText("heading",chosen?chosen.textContent.trim():"Dashboard");
 document.querySelector(".sidebar")?.classList.remove("mobile-open");
 if(name==="earth"){state.map.osm=navigator.onLine!==false;renderEarth()}
 if(name==="sky")renderSky();
 if(name==="radio")window.dispatchEvent(new Event("tihulu:catalog-auto-discover"));
}
for(const btn of document.querySelectorAll("#nav button[data-view]"))btn.addEventListener("click",()=>setView(btn.dataset.view));
for(const btn of document.querySelectorAll("[data-jump]"))btn.addEventListener("click",()=>setView(btn.dataset.jump));
$("mobile-menu")?.addEventListener("click",()=>document.querySelector(".sidebar")?.classList.toggle("mobile-open"));
$("locate")?.addEventListener("click",()=>{
 if(!navigator.geolocation){const fallback=source();renderPosition(true);if(state.ranges)fitEvidence();
 window.dispatchEvent(new CustomEvent("tihulu:reference-position",{detail:{lat:fallback.lat,lon:fallback.lon,kind:fallback.kind}}));
 msg("Browser geolocation unavailable: "+fallback.kind+" · not a live GNSS fix");return}
 msg("Requesting permission for browser/device location…");
 navigator.geolocation.getCurrentPosition(result=>{
   const c=result.coords;state.browser={...safeCoord(c.latitude,c.longitude),accuracy:c.accuracy,alt:c.altitude??null,acquiredAt:new Date(result.timestamp||Date.now()).toISOString()};
   recordFix(state.browser,"Browser / device location");renderPosition(true);renderSky();renderDiagnostics();
   msg("Device location acquired with user permission. Source: browser, NOT SDR.");
 },error=>{const fallback=source();renderPosition(true);if(state.ranges)fitEvidence();
 msg("Browser location unavailable: "+error.message+" · "+fallback.kind+" · "+
 (state.ranges?"Experimental radio-range estimate available on Earth Map.":state.cachedPosition?"Offline last-known location available (not live).":"No offline position measurement currently available."));
 window.dispatchEvent(new CustomEvent("tihulu:reference-position",{detail:{lat:fallback.lat,lon:fallback.lon,kind:fallback.kind}}));
 },{enableHighAccuracy:true,timeout:18000,maximumAge:0});
});
async function importFile(input,maxBytes,handler){
 const file=input.files?.[0];if(!file)return;
 try{if(file.size>maxBytes)throw Error("File exceeds "+Math.round(maxBytes/1024)+" KiB size limit");await handler(await file.text(),file.name)}
 catch(error){msg("Import failed: "+error.message)}finally{input.value=""}
}
$("sp3-file")?.addEventListener("change",e=>importFile(e.target,5_000_000,async(text,name)=>{
 state.sp3=parseSP3(text);state.time=state.sp3.first;
 $("sky-time").disabled=false;$("sky-time").value="0";
 setText("orbit-tag","IMPORTED SP3 / PREDICTED");
 setText("dash-orbits",state.sp3.satelliteCount+" satellites");
 setText("dash-orbit-time",new Date(state.sp3.first).toISOString()+" – "+new Date(state.sp3.last).toISOString());
 renderSky();renderEarth();renderDiagnostics();msg("SP3 orbital samples imported: "+name+". Geometry only; NO RF acquired.");
}));
function loadNMEA(text,origin){
 let valid=0,invalid=0,last=null;
 for(const row of text.split(/\r?\n/).slice(0,12000)){
   if(!row.trim())continue;
   try{
     const p=parseNMEA(row);
     if(p.valid&&(p.kind==="nmea_gga"||p.kind==="nmea_rmc")){valid++;last=p;if(origin==="serial"){state.serialFix=p;state.serialAt=Date.now();recordFix(p,"Dedicated GNSS serial NMEA")}}
   }catch{invalid++}
 }
 if(last){
   state.gnssFile={...last,source:origin};
   setText("receiver-fix",JSON.stringify({source:origin,valid:true,coordinates:{lat:last.lat,lon:last.lon},accuracyMeters:last.accuracyMeters,live:origin==="serial"},null,2));
   setText("stage-fix",origin==="serial"?"VALID NMEA PVT":"HISTORICAL IMPORT");
   if(origin==="serial")renderPosition(true);
 }
 renderDiagnostics();msg(origin+": "+valid+" validated fix sentences, "+invalid+" invalid/unsupported sentences. Imported historical positions are not live.");
}
$("nmea-file")?.addEventListener("change",e=>importFile(e.target,2_000_000,(text,name)=>loadNMEA(text,"Historical NMEA import: "+name)));
$("sky-time")?.addEventListener("input",e=>{
 if(!state.sp3)return;
 state.time=state.sp3.first+(state.sp3.last-state.sp3.first)*Number(e.target.value)/1000;
 renderSky();renderEarth();
});
$("elevation-mask")?.addEventListener("input",e=>{state.mask=Number(e.target.value);setText("mask-label",state.mask+"°");renderSky();renderEarth()});
function renderSky(){
 const sky=$("sky-plot");sky.replaceChildren();
 sky.append(svgel("circle",{cx:300,cy:300,r:250,fill:"#101f31",stroke:"#4f7890","stroke-width":2}));
 for(const el of [30,60])sky.append(svgel("circle",{cx:300,cy:300,r:250*(90-el)/90,fill:"none",stroke:"#31566a","stroke-width":1}));
 for(const a of [0,90,180,270]){const rad=a*Math.PI/180;sky.append(svgel("line",{x1:300,y1:300,x2:300+250*Math.sin(rad),y2:300-250*Math.cos(rad),stroke:"#31566a"}))}
 for(const [txt,x,y] of [["N",300,36],["E",570,305],["S",300,581],["W",30,305]])sky.append(svgel("text",{x,y,fill:"#9ecee0","font-size":20,"text-anchor":"middle"},txt));
 state.visible=state.sp3?visibleSatellites(state.sp3,state.time,source(),state.mask):[];
 const above=state.sp3?state.visible.filter(p=>p.visible):state.autoOrbits.filter(p=>p.el>=state.mask);
 setText("dash-visible",state.sp3||state.autoOrbits.length?above.length:"—");
 setText("sky-timestamp",state.sp3?new Date(state.time).toISOString()+" · imported SP3 geometry only":state.autoOrbits.length?"CelesTrak SGP4 current orbital prediction, NOT received RF":"GNSS orbit download unavailable");
 const c=$("sky-list");c.replaceChildren();
 if(!state.sp3&&!state.autoOrbits.length){c.append(make("p","muted","No GNSS orbit catalog loaded; automatic fetch may be unavailable."));return}
 const colors={G:"#5cbbfc",E:"#70d8ad",R:"#ffbe8b",C:"#f3a6ed",J:"#ffe58e",I:"#ff809c",S:"#e2e2e2",GPS:"#5cbbfc",Galileo:"#70d8ad",GLONASS:"#ffbe8b",BeiDou:"#f3a6ed",QZSS:"#ffe58e",NavIC:"#ff809c",SBAS:"#e2e2e2"};
 for(const p of above){
   const theta=p.az*Math.PI/180,r=250*(90-p.el)/90;
   sky.append(svgel("circle",{cx:300+r*Math.sin(theta),cy:300-r*Math.cos(theta),r:7,fill:colors[p.system||p.group]||colors[p.id[0]]||"#bde"}));
   const text=svgel("text",{x:300+r*Math.sin(theta)+12,y:300-r*Math.cos(theta)-8,fill:"#d8e8f1","font-size":14},p.id);sky.append(text);
   c.append(make("div","list-item",p.id+" · "+(p.system||p.group)+" · az "+fmt(p.az,1)+"° · el "+fmt(p.el,1)+"° · PREDICTED, NOT ACQUIRED"));
 }
 if(!above.length)c.append(make("p","muted","No satellites geometrically above the selected elevation mask. Orbital predictions are not RF reception."));
}
function merc(lat,lon,z){
 const n=256*Math.pow(2,z),l=Math.max(-85.0511,Math.min(85.0511,lat))*Math.PI/180;
 return {x:(lon+180)/360*n,y:(1-Math.log(Math.tan(l)+1/Math.cos(l))/Math.PI)/2*n};
}
function unmerc(x,y,z){
 const n=256*Math.pow(2,z),lat=(Math.atan(Math.sinh(Math.PI*(1-2*y/n)))*180/Math.PI),lon=x/n*360-180;
 return {lat,lon};
}
function project(lat,lon){
 const box=$("earth-map").getBoundingClientRect(),center=merc(state.map.lat,state.map.lon,state.map.zoom),p=merc(lat,lon,state.map.zoom),world=256*Math.pow(2,state.map.zoom);
 let dx=p.x-center.x;
 if(dx>world/2)dx-=world;if(dx<-world/2)dx+=world;
 return {x:box.width/2+dx,y:box.height/2+p.y-center.y};
}
function mapMatches(){
 return matchedBroadcastSources(state.catalogTowers,state.catalogFM,state.dvbChannels||[]);
}
function focusMappedSources(sources,reason){
 const points=Array.isArray(sources)?sources.filter(x=>Number.isFinite(x?.lat)&&Number.isFinite(x?.lon)&&Math.abs(x.lat)<85&&Math.abs(x.lon)<=180):[];
 const bounds=mapBoundsForSources(points);
 if(!bounds){setView("earth");msg("No transmitter coordinates to fit. Frequency/service metadata without a mapped site cannot be placed at an invented location.");return false}
 state.map.lat=(bounds.north+bounds.south)/2;
 state.map.lon=(bounds.east+bounds.west)/2;
 const box=$("earth-map").getBoundingClientRect(),width=Math.max(200,box.width),height=Math.max(240,box.height);
 for(let z=15;z>=3;z--){
  const projection=points.map(p=>merc(p.lat,p.lon,z));
  const deltaX=Math.max(...projection.map(p=>p.x))-Math.min(...projection.map(p=>p.x));
  const deltaY=Math.max(...projection.map(p=>p.y))-Math.min(...projection.map(p=>p.y));
  if(deltaX<width*.76&&deltaY<height*.70){state.map.zoom=z;break}
 }
 if(points.length===1)state.map.zoom=Math.min(state.map.zoom,11);
 setView("earth");renderEarth();
 msg(reason+" · This map shows REFERENCE source positions, not measured distances or an RF-only self-location.");
 return true;
}
function renderScanMapPanel(matches){
 const panel=$("map-scan-results");if(!panel)return;
 panel.replaceChildren();
 const counts={fm:matches.filter(x=>x.kind==="fm").length,tv:matches.filter(x=>x.kind==="tv").length};
 const channels=(state.dvbChannels||[]).length;
 setText("map-scan-status",counts.fm+" FM frequency-overlap source candidates · "+counts.tv+
   " TV frequency-overlap candidates · "+channels+" native/imported DVB services · "+
   state.catalogAntennaAircraft.length+" real antenna ADS-B aircraft · "+state.catalogAircraft.length+
   " Internet aircraft. Matched site coordinates are external OSM references, NOT radio-measured ranges.");
 const shown=matches.slice(0,18);
 for(const m of shown){
  const button=make("button","map-source-result");
  button.type="button";
  const color=make("span","map-source-bullet "+m.kind,m.kind==="fm"?"FM":"TV");
  const name=make("strong",null,m.name+" · "+m.frequencyMHz.toFixed(3)+" MHz");
  const desc=make("small",null,
   m.kind==="tv"?(m.serviceNames||[]).slice(0,3).join(", ")+" · Possible TV site, network may be SFN":
   "Real SDR RF-energy frequency overlap · NOT RDS identification");
  button.append(color,name,desc);
  button.addEventListener("click",()=>focusMappedSources([m],"Selected "+m.kind.toUpperCase()+" frequency-candidate site"));
  panel.append(button);
 }
 if(!matches.length){
  const message=make("p","map-scan-empty",channels?
    channels+" real DVB channels loaded, but no published TV tower MHz matched those channels. Towers cannot be assigned by guesswork.":
    "No actual RF/TV scan-to-site matches yet. Station sites shown on map are public reference data only.");
  panel.append(message);
 }
 for(const a of state.catalogAntennaAircraft.slice(0,5)){
  const button=make("button","map-source-result");button.type="button";
  button.append(make("span","map-source-bullet aircraft","RF"),make("strong",null,a.callsign+" · antenna ADS-B"),
   make("small",null,"Actual Mode S position · not receiver location"));
  button.addEventListener("click",()=>focusMappedSources([a],"Actual antenna-decoded aircraft position"));
  panel.append(button);
 }
}
function renderEarth(){
 renderSourceProvenance();
 const box=$("earth-map");if(!box)return;
 const p=source(),rect=box.getBoundingClientRect();
 const mapWidth=Math.max(1,rect.width),mapHeight=Math.max(1,rect.height);
 // Keep SVG units equal to map CSS pixels. A fixed 900x520 SVG viewBox with
 // preserveAspectRatio=none squeezed circular transmitter icons into ellipses.
 // Tile and marker positions now use the exact same pixel coordinate system.
 $("earth-overlay").setAttribute("viewBox","0 0 "+mapWidth+" "+mapHeight);
 setText("earth-center",fmt(state.map.lat,5)+"° · "+fmt(state.map.lon,5)+"° · map zoom "+state.map.zoom);
 setText("map-center-label",p.validObserver?"MEASURED LOCATION: "+p.kind:p.kind.toUpperCase());
 const grid=$("earth-grid"),rings=$("earth-rings"),markers=$("earth-markers");
 grid.replaceChildren();rings.replaceChildren();markers.replaceChildren();
 const pt=(lat,lon)=>{const v=project(lat,lon);return {x:v.x,y:v.y,inside:v.x>=0&&v.x<=mapWidth&&v.y>=0&&v.y<=mapHeight}};
 // Coordinate grid is built locally, without any online map tiles.
 const center=merc(state.map.lat,state.map.lon,state.map.zoom),w=rect.width,h=rect.height;
 const nw=unmerc(center.x-w/2,center.y-h/2,state.map.zoom);
 const se=unmerc(center.x+w/2,center.y+h/2,state.map.zoom);
 const spanLon=Math.abs(se.lon-nw.lon),spanLat=Math.abs(nw.lat-se.lat);
 const steps=[.005,.01,.02,.05,.1,.25,.5,1,2,5,10,20,45];
 const stepLon=steps.find(v=>spanLon/v<=10)||45,stepLat=steps.find(v=>spanLat/v<=10)||45;
 function line(a,b,label){
   grid.append(svgel("line",{x1:a.x,y1:a.y,x2:b.x,y2:b.y,stroke:"#7596ad","stroke-opacity":".25","stroke-width":1}));
   if(label){grid.append(svgel("text",{x:a.x+3,y:Math.max(12,a.y+13),fill:"#8fb5ca","font-size":12},label))}
 }
 let count=0;
 for(let lon=Math.ceil(nw.lon/stepLon)*stepLon;lon<=se.lon&&count++<24;lon+=stepLon){
   const a=pt(state.map.lat,lon);if(a.x>=0&&a.x<=mapWidth)line({x:a.x,y:0},{x:a.x,y:mapHeight},lon.toFixed(stepLon<1?2:0)+"°");
 }
 count=0;
 for(let lat=Math.ceil(se.lat/stepLat)*stepLat;lat<=nw.lat&&count++<24;lat+=stepLat){
   const a=pt(lat,state.map.lon);if(a.y>=0&&a.y<=mapHeight)line({x:0,y:a.y},{x:mapWidth,y:a.y},lat.toFixed(stepLat<1?2:0)+"°");
 }
 const place=(loc,kind,fill,title,prefix)=>{
   const v=pt(loc.lat,loc.lon);if(!v.inside)return;
   const group=svgel("g");
   group.append(svgel("circle",{cx:v.x,cy:v.y,r:kind==="receiver"||kind==="solution"?9:7,fill,stroke:"#0a192a","stroke-width":2}));
   if(prefix)group.append(svgel("text",{x:v.x,y:v.y+3.7,fill:"#061627","font-size":10,"font-weight":800,"text-anchor":"middle"},prefix));
   const tip=svgel("title",{},title);group.append(tip);
   group.setAttribute("role","button");
   group.setAttribute("tabindex","0");
   group.style.cursor="pointer";
   const show=event=>{
    if(event)event.stopPropagation();
    const popup=$("map-source-popup");if(!popup)return;
    setText("map-source-popup-name",(prefix||kind||"Source")+" · "+kind.toUpperCase());
    setText("map-source-popup-description",title+" · "+loc.lat.toFixed(5)+", "+loc.lon.toFixed(5));
    const px=Math.min(Math.max(v.x+12,8),Math.max(8,mapWidth-350));
    const py=Math.min(Math.max(v.y+14,8),Math.max(8,mapHeight-175));
    popup.style.left=px+"px";popup.style.top=py+"px";popup.hidden=false;
   };
   group.addEventListener("click",show);
   group.addEventListener("keydown",event=>{if(event.key==="Enter"||event.key===" "){event.preventDefault();show(event)}});
   markers.append(group);
 };
 const showGround=layerShown("ground"),showAir=layerShown("aircraft");
 const showOrbits=layerShown("satellites");
 const showReal=layerShown("radio");
 const showDemo=!state.rfOnly&&layerShown("demo")&&!state.rangeInputs.length;
 const demo=showDemo&&Math.abs(p.lat)<=80&&Math.abs(p.lon)<=175?exampleRings(p):null;
 const active=!state.rfOnly&&state.rangeInputs.length>0?{stations:state.rangeInputs,solution:state.ranges,simulated:false}:demo;
 const renderCircle=(s,simulated)=>{
   const samples=ringPoints(s.lat,s.lon,s.rangeMeters,96);
   const path=samples.map((p,i)=>{const v=pt(p.lat,p.lon);return (i?"L":"M")+v.x.toFixed(2)+" "+v.y.toFixed(2)}).join(" ")+" Z";
   const color=simulated?"#f3c779":"#65e2c2";
   rings.append(svgel("path",{d:path,fill:simulated?"#f3c779":"#65e2c2","fill-opacity":".035",stroke:color,"stroke-width":simulated?2:2.7,"stroke-dasharray":simulated?"7 5":"none"}));
 };
 if(active&&(active.simulated||showReal)){
   for(const s of active.stations){if(active.simulated||(s.type==="aircraft"?showAir:showGround))renderCircle(s,active.simulated)}
   const solution=active.solution;
   if(solution&&Number.isFinite(solution.lat)&&Number.isFinite(solution.lon)){
     const q=pt(solution.lat,solution.lon);
     rings.append(svgel("circle",{cx:q.x,cy:q.y,r:18,fill:"none",stroke:active.simulated?"#f3c779":"#65e2c2","stroke-width":2}));
     place(solution,"solution",active.simulated?"#e7b46c":"#65e2c2",active.simulated?"SIMULATED intersection — NOT YOUR POSITION":"Experimental estimate from user-imported measured ranges (unverified)",active.simulated?"D":"X");
   }
   for(let i=0;i<active.stations.length;i++){
     const s=active.stations[i];
     if(!active.simulated&&!(s.type==="aircraft"?showAir:showGround))continue;
     place(s,s.type==="aircraft"?"aircraft":"station",active.simulated?"#e7b46c":"#65e2c2",(s.name||"Source "+(i+1))+
       " · "+(s.rangeMeters/1000).toFixed(2)+" km "+(active.simulated?"SIMULATED":"IMPORTED RANGE")+
       (s.source?" · "+s.source:""),s.type==="aircraft"?"A":"R");
   }
 }

 // RF-source layers are independently sourced from antenna observations and user-entered transmitter metadata.
 // Orange circles = UNVALIDATED RSSI-derived range HYPOTHESES; they are not measured propagation time.
 if(showReal){
  for(const s of state.rfRanges){
   if(s.type!=="station"||!showGround)continue;
   for(const [radius,alpha,dash] of [[s.rangeMeters,".9","8 4"],
     [s.lowerMeters,".34","3 5"],[s.upperMeters,".34","3 5"]]){
    const perimeter=ringPoints(s.lat,s.lon,radius,96).map((v,i)=>{const q=pt(v.lat,v.lon);return (i?"L":"M")+q.x.toFixed(1)+" "+q.y.toFixed(1)}).join(" ")+" Z";
    rings.append(svgel("path",{d:perimeter,fill:"none",stroke:"#ff9472",
      "stroke-opacity":alpha,"stroke-width":radius===s.rangeMeters?2.5:1.3,"stroke-dasharray":dash}));
   }
   place(s,"station","#ff9472",s.name+" · SOURCE COORDINATES USER-SUPPLIED · antenna I/Q captured · "+
      s.rangeMeters.toFixed(0)+" m modeled distance (UNVALIDATED, not measured range). Antenna origin RTL2832U; source identity NOT decoded.","R");
  }
  if(state.rfSolution)place(state.rfSolution,"solution","#ff9472",
     "RF-ONLY ESTIMATED POSITION · "+state.rfRanges.length+" calibrated antenna source hypotheses · NOT A CERTIFIED FIX","F");
 }
 for(const s of state.rfSources){
   if(s.type==="station"&&showGround&&!state.rfRanges.some(x=>x.id===s.id))
     place(s,"station","#92adb9",s.name+" · USER-SUPPLIED TRANSMITTER COORDINATES; "+
       (s.hasActualRF?"actual RTL-SDR I/Q at chosen frequency (source identity not verified)":"NO RF CAPTURE"),"R");
   if(s.type==="aircraft"&&showAir)
     place(s,"aircraft","#efafd0",s.name+" · USER-SUPPLIED MOVING AIRCRAFT REFERENCE; "+
       (s.hasActualRF?"RF energy observed, identity unverified":"NO RF capture")+" · NOT IN 2D RSSI SOLVER","A");
   if(s.type==="satellite"&&showOrbits)
     place(s,"orbit","#8baee8",s.name+" · USER-SUPPLIED SATELLITE COORDINATES; "+
       (s.hasActualRF?"RF energy observed, source identity unverified":"NO RF capture")+" · NOT GNSS TRACKING","S");
 }

 // Mapped broadcast TOWER references are not actual antenna-identified transmitters.
 // Actual frequency overlaps highlight candidates; OSM-only stations remain neutral.
 const matched=mapMatches();
 const drawnTowers=[];
 for(const site of state.catalogTowers){
   if(!showGround||state.rfSources.some(x=>x.catalogId===site.id))continue;
   const pos=pt(site.lat,site.lon);
   if(!pos.inside||drawnTowers.some(p=>Math.hypot(p.x-pos.x,p.y-pos.y)<18))continue;
   drawnTowers.push(pos);
   const linked=matched.filter(m=>m.siteId===site.id);
   const hasTV=linked.some(m=>m.kind==="tv"),hasFM=linked.some(m=>m.kind==="fm");
   place(site,"station",hasTV?"#efc069":hasFM?"#50d0d9":"#8fb8c7",
     site.name+" · "+(hasTV?"NATIVE DVB SERVICE FREQUENCY OVERLAP, TRANSMITTER NOT VERIFIED":hasFM?"RTL-SDR FM ENERGY FREQUENCY OVERLAP, IDENTITY NOT VERIFIED":"OSM PUBLIC CATALOG TOWER, NO RECEIVER ASSOCIATION")+" · "+
     (site.frequencyMHz?site.frequencyMHz.toFixed(3)+" MHz FM tag, RF NOT VERIFIED":site.televisionFrequenciesMHz?.length?"TV MHz tag "+site.televisionFrequenciesMHz.join(", ")+" · DVB SOURCE NOT VERIFIED":site.broadcastType?.includes("television")?"TV BROADCAST TOWER · CHANNEL NOT IDENTIFIED":"NO FREQUENCY TAG")+
     " · distance from SEARCH CENTER "+(site.distanceFromSearchCenterMeters/1000).toFixed(1)+
     " km; this is NOT measured distance from YOU",hasTV?"TV":hasFM?"F":"T");
 }
 // Internet-sourced aircraft must never appear as local RTL-SDR ADS-B frames.
 if(showAir)for(const a of state.catalogAntennaAircraft)place(a,"aircraft","#5be1b2",
   a.callsign+" · LOCAL ANTENNA MODE S ADS-B CRC VERIFIED, "+a.observedAt+
   " · decoded in Tihulu Flight Radar WebUSB tab · NOT receiver position or range","A");
 if(showAir)for(const a of state.catalogAircraft)place(a,"aircraft","#b17eb5",
   a.callsign+" · "+(Date.now()-Date.parse(a.observedAt)>120000?"HISTORICAL CACHED OpenSky":"RECENT OpenSky INTERNET")+" aircraft coordinates at "+a.observedAt+
   " · NOT received by THIS RTL-SDR and NOT USED FOR POSITION","I");
 const liveGnss=!state.rfOnly&&!!(state.serialFix&&Date.now()-state.serialAt<90000);
 const liveDevice=!state.rfOnly&&!!(state.browser&&Date.now()-Date.parse(state.browser.acquiredAt||0)<300000);
 // The browser-provided uncertainty radius is a different constraint from radio ranges.
 // Draw a separate violet dotted circle; never treat browser accuracy as a measured distance to a transmitter.
 const browserAccuracy=liveDevice&&layerShown("device")?state.browser:null;
 if(browserAccuracy&&Number.isFinite(browserAccuracy.accuracy)&&browserAccuracy.accuracy>0&&browserAccuracy.accuracy<=1000000){
   const shape=ringPoints(browserAccuracy.lat,browserAccuracy.lon,browserAccuracy.accuracy,96).map((coord,i)=>{
     const q=pt(coord.lat,coord.lon);
     return (i?"L":"M")+q.x.toFixed(2)+" "+q.y.toFixed(2);
   }).join(" ")+" Z";
   rings.append(svgel("path",{d:shape,fill:"#bd91f3","fill-opacity":".04",stroke:"#bd91f3",
     "stroke-width":2.2,"stroke-dasharray":"3 4"}));
 }
 // Each source has its OWN marker. No predicted orbit or aircraft point is ever the observer fix.
 if(liveGnss&&layerShown("gnss"))place(state.serialFix,"receiver","#5ce1b7","DEDICATED GNSS NMEA FIX · receiver-reported; no RTL-SDR GNSS decode","G");
 if(liveDevice&&layerShown("device"))place(state.browser,"receiver","#bd91f3","BROWSER / DEVICE LOCATION · actual GPS-vs-network provider unknown","B");
 if(!state.rfOnly&&state.networkFix?.verifiedNonGnss===true&&["wifi","cell","ip"].includes(state.networkFix.method)&&layerShown("gpsfree"))
   place(state.networkFix,"receiver","#4bb7d3","VERIFIED NON-GNSS NETWORK FIX · "+state.networkFix.method,"N");
 if(!state.rfOnly&&state.ranges&&showReal)place(state.ranges,"solution","#7de0ac","Experimental 2D radio range estimate (user-imported, unverified)","X");
 if(!state.rfOnly&&state.cachedPosition&&layerShown("cached"))
   place(state.cachedPosition,"receiver","#c9ad76","CACHED previous location · "+state.cachedPosition.recordedAt+" · NOT LIVE","C");
 const anyLocation=state.rfOnly?!!(state.rfSolution&&showReal):liveGnss&&layerShown("gnss")||liveDevice&&layerShown("device")||
   state.ranges&&showReal||state.cachedPosition&&layerShown("cached")||
   state.networkFix?.verifiedNonGnss&&layerShown("gpsfree");
 if(!anyLocation&&!state.rfOnly)place(p,"receiver","#a4b3c3","MAP REFERENCE ONLY · NOT YOUR POSITION","?");
 const orbits=state.sp3?state.visible:state.autoOrbits;
 if(showOrbits)for(const s of orbits)place(s,"orbit","#57bdf4",s.id+" · predicted orbital subpoint; NOT RECEIVED RF","S");
 for(const s of state.references){
   if(s.type==="aircraft"&&showAir)place(s,"aircraft","#f4a5cc",s.name+" · "+s.source+" · AIRCRAFT REFERENCE, NOT OBSERVER FIX","A");
   if(s.type==="station"&&showGround)place(s,"station","#b8a4ef",s.name+" · "+s.source+" · STATION REFERENCE, NO RANGE","R");
 }
 renderScanMapPanel(matched);
 renderMethodReadiness(orbits);
 setText("earth-sat-count",orbits.length+" orbit positions PREDICTED; "+(showOrbits?"shown":"hidden by default"));
 setText("earth-ref-count",(state.references.length+state.rfSources.length+state.catalogTowers.length+state.catalogAircraft.length+state.catalogAntennaAircraft.length)+" external reference coordinates ("+state.catalogTowers.length+" OSM towers, "+state.catalogAircraft.length+" INTERNET aircraft, "+state.catalogAntennaAircraft.length+" LOCAL antenna ADS-B aircraft) · "+state.rangeInputs.length+" imported ranges · "+state.rfRanges.length+" modeled RTL-SDR RSSI hypotheses");
 if(state.rfOnly){
   setText("evidence-report",state.rfSolution?"RF-ONLY / RTL-SDR IQ MEASURED · "+state.rfRanges.length+" CALIBRATED RSSI RANGE HYPOTHESES, unverified. Orange dashed distance circles and faded bounds are propagation-model sensitivity NOT accuracy. No browser or device location was used.":"RF-ONLY / NO FIX · "+state.rfSources.filter(s=>s.hasActualRF).length+" real antenna frequency captures · "+state.rfRanges.length+" calibrated range hypotheses. Transmitter coordinates come from external user input; antenna energy alone is NOT transmitter distance.");
 }else if(state.rangeInputs.length){
   setText("evidence-report",state.rangeInputs.length+" USER-IMPORTED UNVERIFIED RANGES · "+
     "Experimental estimate "+fmt(state.ranges.lat,5)+", "+fmt(state.ranges.lon,5)+
     " · range RMS residual "+state.ranges.rmsResidualMeters.toFixed(1)+" m (NOT location accuracy). "+
     "Solid rings represent entered ranges; satellite predictions are NOT used in this solve.");
 }else if(demo){
   setText("evidence-report","DEMO ONLY — Dashed yellow circles are SIMULATED using three fictional stations. "+
     "Their intersection is NOT your position and was not obtained from the radio. Import 3+ genuine measured ranges for a real experimental solution.");
 }else{
   setText("evidence-report","No measured station ranges. Radio circles cannot be computed from transmitter or aircraft coordinates alone. "+
     "Enable 'Show ring explanation' for a clearly labeled simulated demonstration.");
 }
 const evidenceList=$("evidence-sources");evidenceList.replaceChildren();
 for(const s of state.rfSources){
   const item=make("div","evidence-source");
   item.append(make("strong",null,"RTL-SDR / "+s.name+" · "+s.type+" · "+s.frequencyMHz.toFixed(3)+" MHz"));
   item.append(make("span",null,(s.hasActualRF?"REAL ANTENNA I/Q":"NO ANTENNA OBSERVATION")+
      (s.calibration?" · user-supplied range calibration":" · no calibration")+
      " · transmitter identity/coordinates EXTERNAL"));
   evidenceList.append(item);
 }

 if(active&&(active.simulated||showReal)){
   for(const [i,s] of active.stations.entries()){
     const item=make("div","evidence-source");
     item.append(make("strong",null,(s.type==="aircraft"?"✈ A":"◎ R")+(i+1)+" · "+(s.name||"Source "+(i+1))));
     item.append(make("span",null,(s.rangeMeters/1000).toFixed(2)+" km · "+
       (active.simulated?"SIMULATED, NOT MEASURED":"USER-IMPORTED RANGE, UNVERIFIED")));
     evidenceList.append(item);
   }
 }else{
   evidenceList.append(make("p","muted","No measured range sources are currently used."));
 }
 evidenceList.append(make("p","fine muted","GNSS satellites: geometric predictions only; none have been used in a decoded RTL-SDR GNSS positioning solution. Unmeasured aircraft/ground-station references do not contribute to a fix."));
  renderFixEvidence(p);
 setText("earth-offline-status",(navigator.onLine===false?"OFFLINE: ":"")+
   "Coordinate grid, evidence rings and locally imported references render without map tiles. "+
   (state.cachedPosition?"Last saved position "+state.cachedPosition.recordedAt+" is cached (not live).":"No offline position saved yet."));
 if(state.map.osm&&navigator.onLine!==false)renderTiles();
 else $("osm-tiles").hidden=true;
}
let lastTileViewport="";
function renderTiles(){
 const el=$("osm-tiles");el.hidden=false;
 const box=$("earth-map").getBoundingClientRect(),z=state.map.zoom,world=Math.pow(2,z),c=merc(state.map.lat,state.map.lon,z);
 const minX=Math.floor((c.x-box.width/2)/256),maxX=Math.floor((c.x+box.width/2)/256);
 const minY=Math.max(0,Math.floor((c.y-box.height/2)/256)),maxY=Math.min(world-1,Math.floor((c.y+box.height/2)/256));
 const key=[z,minX,maxX,minY,maxY].join(":");
 if(lastTileViewport===key&&el.childElementCount){
   for(const tile of el.querySelectorAll("img[data-tx][data-ty]")){
     tile.style.left=(Number(tile.dataset.tx)*256-c.x+box.width/2)+"px";
     tile.style.top=(Number(tile.dataset.ty)*256-c.y+box.height/2)+"px";
   }
   return;
 }
 lastTileViewport=key;el.replaceChildren();
 if((maxX-minX+1)*(maxY-minY+1)>40){msg("Zoom in to limit online map tile requests");return}
 for(let tx=minX;tx<=maxX;tx++)for(let ty=minY;ty<=maxY;ty++){
   const x=((tx%world)+world)%world,im=document.createElement("img");
   im.dataset.tx=String(tx);im.dataset.ty=String(ty);
   im.alt="";im.loading="lazy";im.decoding="async";
   im.referrerPolicy="strict-origin-when-cross-origin";
   im.style.left=(tx*256-c.x+box.width/2)+"px";im.style.top=(ty*256-c.y+box.height/2)+"px";
   im.src="https://tile.openstreetmap.org/"+z+"/"+x+"/"+ty+".png";
   el.append(im);
 }
}
$("osm-load")?.addEventListener("click",()=>{state.map.osm=true;renderEarth();msg("OpenStreetMap tiles requested with your consent. Provider receives viewport and network metadata.")});
for(const [id,delta] of [["map-zoom-in",1],["map-zoom-out",-1]]){
 $(id)?.addEventListener("click",()=>{state.map.zoom=Math.max(2,Math.min(18,state.map.zoom+delta));renderEarth()});
}
$("earth-reset")?.addEventListener("click",()=>renderPosition(true));
$("earth-find")?.addEventListener("click",()=>window.dispatchEvent(new Event("tihulu:find-request")));
for(const layer of LOCATION_LAYERS){
 layerToggle(layer.id)?.addEventListener("change",()=>{
   saveLayerPreferences();
   if(layer.id==="demo"&&layerShown("demo")&&!state.rangeInputs.length)fitEvidence();
   else renderEarth();
 });
}
$("layer-only-fixes")?.addEventListener("click",()=>showOnlyLayers(["gnss","device","gpsfree","radio","cached"]));
$("layer-show-references")?.addEventListener("click",()=>showOnlyLayers(["gnss","device","gpsfree","radio","aircraft","ground","satellites","cached"]));
$("layer-defaults")?.addEventListener("click",()=>{
 state.layerPrefs=visibleLayerPreferences(null);
 for(const layer of LOCATION_LAYERS){const input=layerToggle(layer.id);if(input)input.checked=state.layerPrefs[layer.id]}
 saveLayerPreferences();renderEarth();
});
function fitEvidence(){
 const records=state.rangeInputs.length?state.rangeInputs:$("layer-demo")?.checked?exampleRings(source()).stations:[];
 if(!records.length){renderPosition(true);return}
 const coords=[...records,{lat:state.rangeInputs.length?state.ranges.lat:source().lat,lon:state.rangeInputs.length?state.ranges.lon:source().lon}];
 const lat=coords.reduce((v,p)=>v+p.lat,0)/coords.length,lon=coords.reduce((v,p)=>v+p.lon,0)/coords.length;
 state.map.lat=lat;state.map.lon=lon;
 const maxRadius=Math.max(...records.map(p=>p.rangeMeters),1500);
 const box=$("earth-map").getBoundingClientRect(),size=Math.max(240,Math.min(box.width||750,box.height||460));
 let zoom=15;
 while(zoom>2&&maxRadius*2.4*256*Math.pow(2,zoom)/40075017>size*.72)zoom--;
 state.map.zoom=zoom;renderEarth();
}
$("earth-fit-evidence")?.addEventListener("click",fitEvidence);
$("evidence-clear")?.addEventListener("click",()=>{
 state.ranges=null;state.rangeInputs=[];localStorage.removeItem(STORAGE_RANGES);
 state.layerPrefs={...state.layerPrefs,demo:true};saveLayerPreferences();
 $("layer-demo").checked=true;fitEvidence();renderDiagnostics();msg("Range measurements cleared; showing clearly labeled synthetic ring explanation.");
});
let drag=null;
$("earth-map")?.addEventListener("pointerdown",e=>{if(e.button!==0)return;const c=merc(state.map.lat,state.map.lon,state.map.zoom);drag={x:e.clientX,y:e.clientY,c};e.currentTarget.setPointerCapture(e.pointerId)});
$("earth-map")?.addEventListener("pointerup",e=>{if(!drag)return;const p=unmerc(drag.c.x-(e.clientX-drag.x),drag.c.y-(e.clientY-drag.y),state.map.zoom);
 if(p.lat>=-85&&p.lat<=85){state.map.lat=p.lat;state.map.lon=((p.lon+180+360)%360)-180}drag=null;renderEarth()});
$("earth-map")?.addEventListener("pointercancel",()=>{drag=null});
$("earth-map")?.addEventListener("wheel",e=>{e.preventDefault();state.map.zoom=Math.max(2,Math.min(18,state.map.zoom+(e.deltaY<0?1:-1)));renderEarth()},{passive:false});
window.addEventListener("resize",()=>{if(state.activeView==="earth")renderEarth()});
async function disconnect(){
 state.reading=false;
 const reader=state.serialReader;state.serialReader=null;
 if(reader){try{await reader.cancel()}catch{}}
 if(state.serialPort){try{await state.serialPort.close()}catch{}state.serialPort=null}
 state.serialFix=null;state.serialAt=0;
 setText("serial-state","DISCONNECTED");setText("stage-device","UNAVAILABLE");
 setText("rf-state","NO RF RECEIVER OPEN");renderPosition(true);renderDiagnostics();
}
$("serial-connect")?.addEventListener("click",async()=>{
 if(!("serial" in navigator)){msg("Web Serial unavailable. Use supported desktop Chromium or import a receiver log.");return}
 try{
   if(state.serialPort)return;
   const port=await navigator.serial.requestPort();
   await port.open({baudRate:9600});
   state.serialPort=port;state.reading=true;setText("serial-state","CONNECTED / LIVE NMEA");
   setText("stage-device","NMEA SERIAL CONNECTED");setText("rf-state","GNSS SERIAL OPEN (NO SDR CLAIM)");
   msg("GNSS serial connected. No RTL-SDR claimed.");
   let buf="";
   while(state.reading&&port.readable){
     const reader=port.readable.getReader();state.serialReader=reader;
     try{
       while(state.reading){
         const r=await reader.read();if(r.done)break;
         buf+=new TextDecoder().decode(r.value||new Uint8Array());
         if(buf.length>10000)buf=buf.slice(-2000);
         const lines=buf.split(/\r?\n/);buf=lines.pop()||"";
         if(lines.length)loadNMEA(lines.join("\n"),"serial");
       }
     }finally{try{reader.releaseLock()}catch{}if(state.serialReader===reader)state.serialReader=null}
   }
 }catch(e){msg("Serial receiver unavailable: "+e.message)}
 finally{await disconnect()}
});
$("serial-disconnect")?.addEventListener("click",()=>{disconnect();msg("Own NMEA serial port released")});
$("hard-stop")?.addEventListener("click",()=>{
 disconnect();state.usbSelection=null;setText("usb-state","No USB device selected; no RF capture started");
 setText("stage-device","UNAVAILABLE");msg("HARD STOP: only this page's own serial reader was stopped; readsb/Gqrx not touched");
});
window.addEventListener("pagehide",()=>{disconnect()});
$("refs-file")?.addEventListener("change",e=>importFile(e.target,100_000,async text=>{
 const list=JSON.parse(text);if(!Array.isArray(list)||list.length>200)throw Error("Expected <= 200 source-attributed reference points");
 const results=list.map(p=>{
   if(!["aircraft","station"].includes(p.type)||!p.source||!p.name)throw Error("Reference requires name, type and source");
   const loc=safeCoord(p.lat,p.lon);return {...loc,name:String(p.name).slice(0,100),source:String(p.source).slice(0,180),type:p.type,sourceClaimsObservation:p.observedByReceiver===true};
 });
 state.references=results;store(STORAGE_REFS,results);const c=$("refs-list");c.replaceChildren();
 for(const p of results)c.append(make("div","list-item",p.name+" · "+p.type+" · "+p.source));
 renderPosition(true);renderSky();renderDiagnostics();msg(results.length+" external references imported; they are NOT receiver positions");
}));
$("ranges-file")?.addEventListener("change",e=>importFile(e.target,100_000,async text=>{
 const json=JSON.parse(text),data=Array.isArray(json)?json:json.stations;
 if(!validRangeSources(data))throw Error("At least 3 valid measured ranges required. RSSI and station coverage do not qualify.");
 const fix=trilaterate2D(data);
 state.ranges=fix;state.rangeInputs=data.map((s,i)=>({...s,type:s.type==="aircraft"?"aircraft":"station",name:String(s.name||s.station||"Station "+(i+1)).slice(0,90),source:String(s.source||"User-supplied; not independently verified").slice(0,180)}));
 store(STORAGE_RANGES,state.rangeInputs);
 $("layer-demo").checked=false;$("layer-ranges").checked=true;
 saveLayerPreferences();
 setText("radio-result",JSON.stringify({...fix,stationList:state.rangeInputs.map(s=>({name:s.name,type:s.type,rangeMeters:s.rangeMeters,source:s.source}))},null,2));
 fitEvidence();renderDiagnostics();
 msg("Measured-range rings shown on Earth Map. Experimental residual is NOT coordinate accuracy.");
}));
$("tdoa-file")?.addEventListener("change",e=>importFile(e.target,100_000,async text=>{
 const json=JSON.parse(text),data=Array.isArray(json)?json:json.receivers;
 state.tdoa=tdoaConstraints(data);setText("tdoa-result",JSON.stringify(state.tdoa,null,2));renderDiagnostics();
 msg("Synchronized TDOA constraints computed; no position fix inferred.");
}));
$("clear-local")?.addEventListener("click",async()=>{
 // Keep the PWA application shell installed for offline startup; clear user data only.
 for(const key of [STORAGE_LOCATION,STORAGE_RANGES,STORAGE_REFS,STORAGE_LAYERS,"tihulu.rfgeo.gnss-orbits.v1"])try{localStorage.removeItem(key)}catch{}
 state.sp3=null;state.time=null;state.visible=[];state.references=[];state.ranges=null;state.rangeInputs=[];state.cachedPosition=null;state.tdoa=[];
 state.browser=null;state.gnssFile=null;state.receiverHistory=[];await disconnect();
 $("layer-demo").checked=true;
 $("sky-time").disabled=true;setText("orbit-tag","EPHEMERIS MISSING");setText("dash-orbits","Not imported");
 renderHistory();renderDiagnostics();renderSky();renderEarth();msg("Local map/orbit view cleared. No unrelated software or data modified.");
});
const escaped=raw=>String(raw).replace(/[&<>"']/g,ch=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&apos;"}[ch]));
function exportData(type){
 const h=state.receiverHistory;
 if(!h.length){msg("No genuine device / receiver positions to export");return}
 let data,mime="text/plain",ext=type;
 if(type==="json"){data=JSON.stringify({type:"PositionHistory",positions:h},null,2);mime="application/json"}
 else if(type==="geojson"){data=JSON.stringify({type:"FeatureCollection",features:h.map(p=>({type:"Feature",geometry:{type:"Point",coordinates:[p.lon,p.lat]},properties:{provider:p.provider,observedAt:p.observedAt,accuracyMeters:p.accuracyMeters}}))},null,2);mime="application/geo+json"}
 else if(type==="csv"){data="timestamp,provider,latitude,longitude,accuracy_m\n"+h.map(p=>[p.observedAt,JSON.stringify(p.provider),p.lat,p.lon,p.accuracyMeters??""].join(",")).join("\n");mime="text/csv"}
 else if(type==="gpx"){data='<?xml version="1.0" encoding="UTF-8"?><gpx version="1.1" creator="TIHULU RF Geolocation Center" xmlns="http://www.topografix.com/GPX/1/1"><trk><name>Verified device observations</name><trkseg>'+h.map(p=>'<trkpt lat="'+p.lat+'" lon="'+p.lon+'"><time>'+p.observedAt+'</time></trkpt>').join("")+"</trkseg></trk></gpx>";mime="application/gpx+xml"}
 else if(type==="kml"){data='<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document>'+h.map(p=>'<Placemark><name>'+escaped(p.provider)+'</name><Point><coordinates>'+p.lon+','+p.lat+',0</coordinates></Point></Placemark>').join("")+"</Document></kml>";mime="application/vnd.google-earth.kml+xml"}
 const blob=new Blob([data],{type:mime}),a=document.createElement("a"),url=URL.createObjectURL(blob);
 a.href=url;a.download="tihulu-geolocation."+ext;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1500);
}
for(const t of ["json","geojson","csv","gpx","kml"])$( "export-"+t)?.addEventListener("click",()=>exportData(t));
function capabilities(){
 const c=$("capabilities");c.replaceChildren();
 for(const [a,b] of [
   ["WebUSB",("usb" in navigator)?"RTL-SDR USB claim + uncalibrated GNSS-L1 RF sample; GNSS decoding NOT implemented":"Unavailable"],
   ["Web Serial",("serial" in navigator)?"NMEA receiver selection supported":"Unavailable"],
   ["Browser Geolocation",navigator.geolocation?"Available with permission":"Unavailable"],
   ["Local offline shell",("serviceWorker" in navigator)?"Supported by browser":"Unavailable"],
   ["Native GNSS-SDR pipeline","NOT IMPLEMENTED"],
   ["Multi-band synchronized GNSS","NOT IMPLEMENTED"]]){
   const row=make("span");row.append(make("span",null,a),make("b",null,b));c.append(row);
 }
 setText("dashboard-platform",navigator.userAgent.includes("Mobile")?"Mobile web: maps, imports and browser GPS; native USB features depend on browser":"Desktop web: maps, imports, browser GPS; optional Web Serial/WebUSB selection");
}
if("serviceWorker" in navigator&&location.protocol==="https:"){
 navigator.serviceWorker.register("./sw.js").catch(()=>{});
}
function fitRfSurveyMap(){
 const sources=state.rfRanges.length?state.rfRanges:state.rfSources;
 if(!sources.length){setView("radio");msg("Add station coordinates to the RF-only source list first.");return}
 setView("earth");
 const points=[...sources];
 if(state.rfSolution)points.push(state.rfSolution);
 const lat=points.reduce((a,p)=>a+p.lat,0)/points.length;
 const lon=points.reduce((a,p)=>a+p.lon,0)/points.length;
 if(!Number.isFinite(lat)||!Number.isFinite(lon))return;
 state.map.lat=lat;state.map.lon=lon;
 const maxMeters=Math.max(...sources.map(s=>Math.max(s.rangeMeters||0,s.upperMeters||0)),2000);
 const box=$("earth-map").getBoundingClientRect(),size=Math.max(240,Math.min(box.width||720,box.height||460));
 let zoom=15;
 while(zoom>2&&maxMeters*2.5*256*Math.pow(2,zoom)/40075017>size*.78)zoom--;
 state.map.zoom=zoom;
 renderEarth();
 msg("Earth Map centered on user-supplied transmitter locations and RF-only hypothetical rings; NO OS/device coordinates used.");
}
window.addEventListener("tihulu:rf-only-mode",e=>{
 state.rfOnly=!!e.detail?.enabled;
 renderPosition(false);renderDiagnostics();renderSourceProvenance();
 msg(state.rfOnly?"RF-ONLY session: GNSS/browser/device/cached locations excluded from the selected position.":"RF-ONLY disabled; source provenance remains separate.");
});
window.addEventListener("tihulu:rf-survey-updated",e=>{
 const d=e.detail||{};
 state.rfSources=Array.isArray(d.sources)?d.sources.slice(0,60):[];
 state.rfRanges=Array.isArray(d.ranges)?d.ranges.slice(0,32):[];
 state.rfSolution=d.solution&&Number.isFinite(d.solution.lat)&&Number.isFinite(d.solution.lon)?d.solution:null;
 if(state.rfOnly){renderPosition(false)}else if(state.activeView==="earth")renderEarth();
 renderSourceProvenance();renderDiagnostics();
});
window.addEventListener("tihulu:rf-fit-map",fitRfSurveyMap);
$("map-source-popup-close")?.addEventListener("click",()=>{$("map-source-popup").hidden=true});
window.addEventListener("tihulu:show-tv-on-map",()=>{
 const matches=mapMatches().filter(m=>m.kind==="tv");
 if(matches.length)focusMappedSources(matches,"TV channels with frequency-matched public broadcasting sites");
 else if((state.dvbChannels||[]).length){
  setView("earth");
  msg(state.dvbChannels.length+" actual DVB channels are available, but no broadcast site's exact MHz is catalogued. No tower or receiver position can be assigned from service metadata alone.");
 }else focusMappedSources(state.catalogTowers.filter(s=>s.broadcastType?.includes("television")),
   "Mapped OSM television sites only; no actual TV scan result exists");
});
$("map-focus-scan")?.addEventListener("click",()=>{
 const matches=mapMatches();
 if(matches.length)focusMappedSources(matches,"Actual scanned FM/TV frequencies matched to published transmitter candidates");
 else focusMappedSources(state.catalogTowers,"OSM catalog sites only; scan-to-site identification not available");
});
window.addEventListener("tihulu:tv-channels-updated",e=>{
 if(state.activeView==="earth")renderEarth();
 const match=mapMatches().filter(m=>m.kind==="tv");
 if(e.detail?.fromNative&&match.length)focusMappedSources(match,"New real DVB scan channels and matching OSM TV site frequencies");
});
window.addEventListener("tihulu:rf-scan-finished",()=>{
 const fm=mapMatches().filter(m=>m.kind==="fm");
 if(fm.length)focusMappedSources(fm,"Real RTL-SDR FM energy overlap and OSM frequency catalog");
 else{setView("earth");msg("Actual FM receiver spectrum scanned, but no identified transmitter site has a matching published frequency. No false map position created.")}
});
window.addEventListener("tihulu:catalog-updated",e=>{
 const data=e.detail||{};
 state.catalogTowers=Array.isArray(data.towers)?data.towers.slice(0,150):[];
 state.catalogAircraft=Array.isArray(data.aircraft)?data.aircraft.slice(0,150):[];
 state.catalogAntennaAircraft=Array.isArray(data.antennaAircraft)?data.antennaAircraft.slice(0,150):[];
 state.catalogFM=Array.isArray(data.fmReadings)?data.fmReadings.slice(0,130):[];
 if(state.activeView==="earth")renderEarth();
 else renderMethodReadiness(state.sp3?state.visible:state.autoOrbits);
});
window.addEventListener("tihulu:catalog-use-map-center",()=>{
 window.dispatchEvent(new CustomEvent("tihulu:catalog-map-center",{detail:{lat:state.map.lat,lon:state.map.lon}}));
});
window.addEventListener("tihulu:catalog-fit-map",()=>{
 const sites=state.catalogTowers.length?state.catalogTowers:state.catalogAircraft;
 if(!sites.length){setView("radio");msg("First discover some published transmitters or online aircraft to show on the map.");return}
 state.map.lat=sites.reduce((t,p)=>t+p.lat,0)/sites.length;
 state.map.lon=sites.reduce((t,p)=>t+p.lon,0)/sites.length;
 state.map.zoom=10;setView("earth");
 msg("Map centered on EXTERNAL CATALOG coordinates, NOT a calculated receiver fix.");
});

$("live-rf-only")?.addEventListener("click",()=>{
 const input=$("rf-only");if(input&&!input.checked){input.checked=true;input.dispatchEvent(new Event("change"))}
 setView("radio");msg("Antenna-only RF positioning: choose a source, connect RTL-SDR, capture and calibrate. OS GPS/Wi-Fi/IP excluded.");
});
window.addEventListener("tihulu:find-request",()=>{ if(state.rfOnly){setView("radio");msg("RF-ONLY: browser/GPS ignored. Capture known fixed transmitter signals using WebUSB and a user-provided calibration.");return} if(state.serialFix&&Date.now()-state.serialAt<90000){ window.dispatchEvent(new CustomEvent("tihulu:position",{detail:{lat:state.serialFix.lat,lon:state.serialFix.lon,alt:state.serialFix.altEllipsoidMeters??0,provider:"Dedicated GNSS serial NMEA"}})); msg("Using fresh receiver-provided NMEA position; browser location not requested."); }else{$("locate")?.click()}});
window.addEventListener("tihulu:orbit",e=>{
  if(!Array.isArray(e.detail?.satellites))return;
  state.autoOrbits=e.detail.satellites.slice(0,450);
  renderMethodReadiness(state.sp3?state.visible:state.autoOrbits);
  renderSourceProvenance();
  if(state.activeView==="sky"&&!state.sp3)renderSky();
  if(state.activeView==="earth"&&!state.sp3)renderEarth();
  if(!state.sp3){setText("dash-orbits",state.autoOrbits.length+" CelesTrak satellites");setText("orbit-tag","AUTO ORBITS / PREDICTED")}
});
state.layerPrefs=visibleLayerPreferences(restore(STORAGE_LAYERS));
for(const layer of LOCATION_LAYERS){const input=layerToggle(layer.id);if(input)input.checked=state.layerPrefs[layer.id]}
window.addEventListener("tihulu:receiver-status",event=>{
 const detail=event.detail||{};
 state.usbStatus=typeof detail.status==="string"?detail.status:"UNKNOWN";
 state.usbMessage=typeof detail.message==="string"?detail.message:"";
 renderSourceProvenance();
});
const savedFix=restore(STORAGE_LOCATION);
if(savedFix&&Number.isFinite(savedFix.lat)&&Number.isFinite(savedFix.lon)&&Math.abs(savedFix.lat)<=90&&Math.abs(savedFix.lon)<=180&&savedFix.recordedAt){
 state.cachedPosition=savedFix;
}
const savedRanges=restore(STORAGE_RANGES);
if(validRangeSources(savedRanges)){
 try{state.ranges=trilaterate2D(savedRanges);state.rangeInputs=savedRanges;$("layer-demo").checked=false;state.layerPrefs.demo=false}
 catch{state.ranges=null;state.rangeInputs=[]}
}
const savedRefs=restore(STORAGE_REFS);
if(Array.isArray(savedRefs)&&savedRefs.length<=200){
 state.references=savedRefs.filter(p=>p&&Number.isFinite(p.lat)&&Number.isFinite(p.lon)&&["aircraft","station"].includes(p.type)&&p.name&&p.source);
}
renderCatalog();renderHistory();renderDiagnostics();renderPosition(true);renderSky();capabilities();
initAutoExplorer();
initUsbSDR(msg);
initRFSurvey();
initCatalogDiscovery();
initSimpleUI({state,source,setView,renderEarth,renderPosition,fitRfSurveyMap});
initHardwareManager({setView});
initDVBBridge();
if(typeof ResizeObserver==="function"){
 const mapElement=$("earth-map");
 if(mapElement){
  let pending=false;
  const observer=new ResizeObserver(()=>{
   if(pending||state.activeView!=="earth")return;
   pending=true;
   requestAnimationFrame(()=>{pending=false;if(state.activeView==="earth")renderEarth()});
  });
  observer.observe(mapElement);
 }
}

setView("earth"); // Clean, map-first experience; original science workbench remains under Advanced Tools.

setInterval(()=>{
 if(state.serialFix&&Date.now()-state.serialAt>90000){state.serialFix=null;renderPosition(false);renderDiagnostics();msg("Stale serial NMEA fix expired")}
 if(state.browser&&Date.now()-Date.parse(state.browser.acquiredAt||0)>=5*60*1000){
   state.browser=null;renderPosition(false);renderDiagnostics();
   const p=source();window.dispatchEvent(new CustomEvent("tihulu:reference-position",{detail:{lat:p.lat,lon:p.lon,kind:p.kind}}));
   msg("Browser location older than 5 minutes. Last-known position now labeled CACHED, NOT LIVE.");
 }
},10000);
