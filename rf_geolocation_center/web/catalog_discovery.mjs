/* User-initiated RF source discovery without browser/device geolocation.
 * OSM Overpass = public radio-site REFERENCES, sometimes with a tagged FM frequency.
 * OpenSky = INTERNET aircraft states, never claims antenna receipt.
 * Actual FM scan reports UNCALIBRATED RF ENERGY only, not RDS station identity.
 */
import {normalizeRadioTowers,normalizeOpenSkyStates,matchFMScanToCatalog} from "../core/source_catalog.mjs";
const $=id=>document.getElementById(id);
const TOWER_KEY="tihulu.rfgeo.catalog.towers.v1";
const AIR_KEY="tihulu.rfgeo.catalog.aircraft.v1";
let towers=[],aircraft=[],antennaAircraft=[],antennaAt=0,fmReadings=[],busy=false,controller=null,initialDiscoveryDone=false;
const txt=(id,value)=>{const e=$(id);if(e)e.textContent=String(value)};
function cached(key){
 try{
  const entry=JSON.parse(localStorage.getItem(key)||"null");
  return entry&&Array.isArray(entry.entries)&&Number.isFinite(entry.at)&&Date.now()-entry.at<30*86400000?entry:null;
 }catch{return null}
}
function save(key,list,search){
 try{localStorage.setItem(key,JSON.stringify({at:Date.now(),search,entries:list.slice(0,150)}))}catch{}
}
function reference(){
 const lat=Number($("catalog-center-lat")?.value),lon=Number($("catalog-center-lon")?.value);
 const km=Number($("catalog-radius")?.value);
 if(!Number.isFinite(lat)||Math.abs(lat)>85||!Number.isFinite(lon)||Math.abs(lon)>180||
   ![20,50,100].includes(km))throw Error("Enter a valid approximate reference-region center and 20, 50 or 100 km search radius");
 return {lat,lon,km};
}
function sync(){
 window.dispatchEvent(new CustomEvent("tihulu:catalog-updated",{
  detail:{towers:towers.slice(0,150),aircraft:aircraft.slice(0,150),antennaAircraft:antennaAircraft.slice(0,150),fmReadings:fmReadings.slice(0,130)}
 }));
}
function buildRow(target,entry,kind){
 const row=document.createElement("div");row.className="rf-catalog-row";
 const heading=document.createElement("strong");
 heading.textContent=(kind==="aircraft"?"✈ ":"⌁ ")+entry.name+
  (entry.frequencyMHz?" · "+entry.frequencyMHz.toFixed(3)+" MHz":"");
 const desc=document.createElement("small");
 desc.textContent=kind==="aircraft"?
  (Date.now()-Date.parse(entry.observedAt)>120000?"HISTORICAL/CACHED INTERNET aircraft":"RECENT INTERNET aircraft")+
  " position · "+entry.icao+" · "+entry.observedAt+" · NOT received via RTL-SDR":
  "OSM mapped broadcast site · "+entry.lat.toFixed(5)+", "+entry.lon.toFixed(5)+
  " · "+Math.round(entry.distanceFromSearchCenterMeters/1000)+" km from search CENTER (not your location) · "+
  (entry.frequenciesMHz?.length?"FM tag "+entry.frequenciesMHz.join(", ")+" MHz · SIGNAL UNVERIFIED":
   entry.televisionFrequenciesMHz?.length?"TV frequency tag "+entry.televisionFrequenciesMHz.join(", ")+" MHz · TRANSMITTER UNVERIFIED":
   (entry.broadcastType==="television"?"TV broadcast tower · service frequency not tagged":"NO FREQUENCY IN CATALOG"));
 row.append(heading,desc);
 if(kind!=="aircraft"){
   const add=document.createElement("button");add.type="button";add.className="secondary";
   add.textContent=entry.frequencyMHz?"Add to RF survey":"Reference only · frequency unknown";
   add.disabled=!entry.frequencyMHz;
   if(entry.frequencyMHz)add.addEventListener("click",()=>{
     window.dispatchEvent(new CustomEvent("tihulu:rf-autosource",{detail:entry}));
     txt("catalog-status","Added "+entry.name+" to the RF survey as an OSM catalog candidate; RF identity and distance still UNVERIFIED.");
   });
   row.append(add);
 }
 target.append(row);
}
function render(){
 const towerList=$("catalog-tower-list"),airList=$("catalog-aircraft-list");
 if(towerList){
  towerList.replaceChildren();
  const head=document.createElement("p");head.textContent="Mapped broadcast site candidates: "+towers.length+
    " · FM frequency tagged: "+towers.filter(s=>s.frequenciesMHz?.length).length+
    " · TV broadcast candidates: "+towers.filter(s=>s.broadcastType?.includes("television")).length;
  towerList.append(head);
  for(const s of towers.slice(0,80))buildRow(towerList,s,"tower");
 }
 const antennaList=$("catalog-antenna-aircraft-list");
 if(antennaList){
  antennaList.replaceChildren();
  const header=document.createElement("p");
  header.textContent="Actual RTL-SDR ADS-B decoded aircraft: "+antennaAircraft.length+
    " (shared by Flight Radar, CRC-verified 1090 MHz; local browser, not Internet)";
  antennaList.append(header);
  for(const p of antennaAircraft.slice(0,80)){
   const row=document.createElement("div");row.className="rf-catalog-row";
   const a=document.createElement("strong");a.textContent="✈ "+p.callsign+" · "+p.icao;
   const b=document.createElement("small");b.textContent=p.lat.toFixed(5)+", "+p.lon.toFixed(5)+
     " · "+p.observedAt+" · REAL ANTENNA ADS-B MESSAGE; observer range NOT known";
   row.append(a,b);antennaList.append(row);
  }
 }
 if(airList){
  airList.replaceChildren();
  const head=document.createElement("p");head.textContent="Internet-only aircraft references: "+aircraft.length+
    " · NOT RTL-SDR ADS-B decoding";airList.append(head);
  for(const a of aircraft.slice(0,30))buildRow(airList,a,"aircraft");
 }
 sync();
}
async function discover(){
 if(busy)return;
 let area;try{area=reference()}catch(e){txt("catalog-status",e.message);return}
 const cacheKey=JSON.stringify(area);
 if(navigator.onLine===false){
  const previous=cached(TOWER_KEY);
  if(previous){towers=previous.entries;render();txt("catalog-status","OFFLINE: cached tower references from "+new Date(previous.at).toLocaleString()+". Catalog frequency/coordinates may be outdated.");return}
  txt("catalog-status","Offline and no saved transmitter-site catalog. Connect once to download references; manual records remain usable.");return;
 }
 busy=true;controller=new AbortController();
 txt("catalog-status","Searching OpenStreetMap broadcast tower tags near the chosen REFERENCE center. No browser GPS lookup.");
 try{
  const radius=area.km*1000;
  const query='[out:json][timeout:30];('+
    'nwr(around:'+radius+','+area.lat+','+area.lon+')["communication:radio"="yes"];'+
    'nwr(around:'+radius+','+area.lat+','+area.lon+')["broadcasting"="radio"];'+
    'nwr(around:'+radius+','+area.lat+','+area.lon+')["broadcasting:radio"="yes"];'+
    'nwr(around:'+radius+','+area.lat+','+area.lon+')["communication:television"="yes"];'+
    'nwr(around:'+radius+','+area.lat+','+area.lon+')["broadcasting"="television"];'+
    'nwr(around:'+radius+','+area.lat+','+area.lon+')["broadcasting:television"="yes"];'+
    ');out center 200;';
  const response=await fetch("https://overpass-api.de/api/interpreter",{
    method:"POST",headers:{"Content-Type":"application/x-www-form-urlencoded;charset=UTF-8"},
    body:"data="+encodeURIComponent(query),signal:controller.signal,cache:"no-store"});
  if(!response.ok)throw Error("OpenStreetMap Overpass HTTP "+response.status);
  const body=await response.text();
  if(body.length>2000000)throw Error("Oversized tower catalog response");
  const result=normalizeRadioTowers(JSON.parse(body),area,150);
  towers=result;
  save(TOWER_KEY,towers,area);
  render();
  txt("catalog-status","CATALOG ONLY · "+towers.length+" OSM broadcast sites discovered near the selected reference center. "+
    towers.filter(s=>s.frequenciesMHz?.length).length+" include an explicit FM frequency tag. "+
    "Published site positions and channel tags are NOT verified by RF. Select a frequency-tagged source for antenna sampling.");
 }catch(e){
  if(e.name==="AbortError"){txt("catalog-status","Catalog discovery stopped.");return}
  const previous=cached(TOWER_KEY);
  if(previous){towers=previous.entries;render();txt("catalog-status","Live Overpass unavailable ("+e.message+"). Using OFFLINE CACHE from "+new Date(previous.at).toLocaleString()+".");}
  else txt("catalog-status","Catalog request unavailable: "+e.message+
     ". Endpoint may be busy, blocked by CORS or offline. Manual source entry still works.");
 }finally{busy=false;controller=null}
}
async function discoverAircraft(){
 if(busy)return;
 let area;try{area=reference()}catch(e){txt("catalog-status",e.message);return}
 const previous=cached(AIR_KEY);
 if(navigator.onLine===false){
   aircraft=previous?.entries||[];render();
   txt("catalog-status",aircraft.length?"OFFLINE: saved OpenSky aircraft positions are HISTORICAL and no longer live.":"Offline: cannot fetch new internet aircraft. Local ADS-B requires an actual decoder.");
   return;
 }
 busy=true;controller=new AbortController();
 try{
  // Small regional bbox: never transmit device GPS; limited credit/area and no polling.
  const extent=Math.min(1,area.km/110),deltaLon=extent/Math.max(.25,Math.cos(area.lat*Math.PI/180));
  const q=new URLSearchParams({lamin:String(area.lat-extent),lamax:String(area.lat+extent),
    lomin:String(area.lon-deltaLon),lomax:String(area.lon+deltaLon)});
  txt("catalog-status","Requesting INTERNET aircraft positions from OpenSky (not antenna reception)...");
  const response=await fetch("https://opensky-network.org/api/states/all?"+q,{signal:controller.signal,cache:"no-store"});
  if(!response.ok)throw Error("OpenSky HTTP "+response.status);
  const body=await response.text();if(body.length>1500000)throw Error("Aircraft response too large");
  aircraft=normalizeOpenSkyStates(JSON.parse(body),Date.now()).slice(0,150);
  save(AIR_KEY,aircraft,area);render();
  txt("catalog-status",aircraft.length+" online aircraft references from OpenSky. All are INTERNET-only: NOT received or decoded by this antenna and NEVER used as RF ranging sources.");
 }catch(e){
  if(e.name==="AbortError"){txt("catalog-status","Aircraft lookup stopped.");return}
  aircraft=previous?.entries||[];render();
  txt("catalog-status","OpenSky unavailable ("+e.message+"); "+
    (aircraft.length?"saved aircraft reference records shown as STALE":"no aircraft available")+
    ". Regional ADS-B antenna decoding is not yet integrated into this module.");
 }finally{busy=false;controller=null}
}
function showScan(result){
 // Single-channel spot probes update the matching frequency without erasing a prior full FM survey.
 const combined=result.length===1?[...fmReadings.filter(r=>Math.abs(r.frequencyMHz-result[0].frequencyMHz)>.005),...result]:result;
 fmReadings=matchFMScanToCatalog(combined,towers);
 const peaks=fmReadings.slice().sort((a,b)=>b.levelDbFS-a.levelDbFS).slice(0,16);
 const lines=peaks.map(r=>r.frequencyMHz.toFixed(1)+" MHz · "+r.levelDbFS.toFixed(1)+
  " dBFS-like · "+(r.candidateNames.length?"possible OSM frequency overlap: "+r.candidateNames.join(", "):"NO transmitter ID"));
 txt("catalog-fm-status",fmReadings.length+" REAL tuner-frequency samples · strongest relative levels:\n"+
   lines.join("\n")+"\nNo RDS/PI or signal identity decoded. Level peaks alone do not locate the observer.");
 sync();
 if(fmReadings.length)window.dispatchEvent(new CustomEvent("tihulu:rf-scan-finished",{detail:{count:fmReadings.length,method:"LIVE RTL-SDR TUNER ENERGY"}}));
}
function acceptAntennaAircraft(message){
 if(!message||message.app!=="tihulu-flight-radar"||
   !Number.isFinite(message.timestamp)||Math.abs(Date.now()-message.timestamp)>15000)return;
 if(message.type==="stopped"){
  antennaAircraft=[];antennaAt=0;
  txt("catalog-adsb-status","Flight Radar stopped its direct RTL-SDR reception; no live antenna aircraft. Internet aircraft remain separately labeled.");
  render();return;
 }
 if(message.type!=="actual_adsb"||!Array.isArray(message.aircraft))return;
 antennaAt=Date.now();
 const fresh=[],seen=new Set();
 for(const a of message.aircraft.slice(0,150)){
  const icao=String(a.hex||"").toLowerCase();
  if(!/^[0-9a-f]{6}$/.test(icao)||seen.has(icao)||!Number.isFinite(a.lat)||Math.abs(a.lat)>90||
    !Number.isFinite(a.lon)||Math.abs(a.lon)>180||!Number.isFinite(a.seen_pos)||
    a.seen_pos<0||a.seen_pos>60)continue;
  seen.add(icao);
  fresh.push({id:"adsb-local-"+icao,icao,callsign:String(a.flight||icao).slice(0,25),
   lat:a.lat,lon:a.lon,altitudeMeters:Number.isFinite(a.alt_baro)?a.alt_baro*0.3048:null,
   frequencyMHz:1090,observedAt:new Date(message.timestamp).toISOString(),
   catalog:"Tihulu Flight Radar WebUSB",hardwareReceived:true,metadataOrigin:"REAL RTL-SDR MODE S ADS-B",
   confidence:"CRC-VERIFIED ANTENNA AIRCRAFT POSITION · NOT RECEIVER POSITION"});
 }
 antennaAircraft=fresh;
 txt("catalog-adsb-status","LIVE antenna ADS-B from Tihulu Flight Radar: "+fresh.length+
   " position-bearing aircraft · decoder CRC-verified; "+
   Math.max(0,Number(message.messages)||0)+" total RF messages. This does NOT locate the ground receiver.");
 render();
}
export function initCatalogDiscovery(){
 if(!$("catalog-discover"))return;
 if(typeof BroadcastChannel!=="undefined"){
  const channel=new BroadcastChannel("tihulu.rfgeo.adsb.v1");
  channel.addEventListener("message",e=>acceptAntennaAircraft(e.data));
  window.addEventListener("pagehide",()=>channel.close(),{once:true});
  // Last live snapshot is never persisted; expire stale browser-to-browser RF observations.
  setInterval(()=>{
   if(antennaAt&&Date.now()-antennaAt>20000){
    antennaAt=0;antennaAircraft=[];
    txt("catalog-adsb-status","Direct antenna aircraft feed became stale; no live Flight Radar snapshot received in 20 seconds.");
    render();
   }
  },5000);
 }else txt("catalog-adsb-status","BroadcastChannel unavailable: live Flight Radar antenna sharing is unsupported in this browser.");

 const prior=cached(TOWER_KEY);
 if(prior)towers=prior.entries;
 const lastAircraft=cached(AIR_KEY);
 if(lastAircraft)aircraft=lastAircraft.entries;
 render();
 $("catalog-map-center")?.addEventListener("click",()=>window.dispatchEvent(new Event("tihulu:catalog-use-map-center")));
 window.addEventListener("tihulu:catalog-auto-discover",()=>{
   if(initialDiscoveryDone)return;
   initialDiscoveryDone=true;
   if(navigator.onLine!==false)void discover();
 });

 $("catalog-discover")?.addEventListener("click",()=>void discover());
 $("catalog-add-frequencies")?.addEventListener("click",()=>{
   const entries=towers.flatMap(s=>(s.frequenciesMHz||[]).filter(f=>f>=87.5&&f<=108).map(f=>({...s,frequencyMHz:f}))).slice(0,90);
   if(!entries.length){txt("catalog-status","No cached catalog sites with explicit FM frequencies to import. Run Discover first; missing station frequencies must not be invented.");return}
   window.dispatchEvent(new CustomEvent("tihulu:rf-autosources",{detail:entries}));
   txt("catalog-status","Sent "+entries.length+" frequency-tagged OSM site candidates to the RF survey. Tagged frequency does NOT verify RF reception or emitter identity.");
 });

 $("catalog-aircraft")?.addEventListener("click",()=>void discoverAircraft());
 $("catalog-fm-scan")?.addEventListener("click",()=>{
  txt("catalog-fm-status","FM SWEEP REQUESTED: real RTL-SDR 87.5–108 MHz frequency levels. Receiver must be connected. No RDS source ID or range will be decoded.");
  window.dispatchEvent(new CustomEvent("tihulu:rf-fm-sweep-request",{detail:{startMHz:87.5,stopMHz:108,stepMHz:.1}}));
 });
 $("catalog-cancel")?.addEventListener("click",()=>{
  controller?.abort();window.dispatchEvent(new Event("tihulu:rf-fm-sweep-stop"));
  txt("catalog-fm-status","Stop requested for bounded FM sweep. Receiver remains connected.");
 });
 $("catalog-fit-map")?.addEventListener("click",()=>window.dispatchEvent(new Event("tihulu:catalog-fit-map")));
 window.addEventListener("tihulu:catalog-map-center",e=>{
  const p=e.detail;
  if(!p||![p.lat,p.lon].every(Number.isFinite))return;
  $("catalog-center-lat").value=p.lat.toFixed(6);$("catalog-center-lon").value=p.lon.toFixed(6);
  txt("catalog-status","Search center set from Earth Map viewport (reference only, NOT your actual location).");
 });
 window.addEventListener("tihulu:rf-fm-sweep-progress",e=>{
  const d=e.detail||{};
  txt("catalog-fm-status",Math.round(d.completed||0)+"/"+Math.round(d.total||0)+
     " actual frequencies scanned with RTL-SDR · "+(d.frequencyMHz||0).toFixed(1)+" MHz. NOT station identity.");
 });
 window.addEventListener("tihulu:rf-fm-sweep-results",e=>showScan(e.detail?.readings||[]));
 window.addEventListener("tihulu:rf-fm-sweep-failed",e=>txt("catalog-fm-status",
  "REAL RF sweep failed: "+String(e.detail?.message||"Unknown USB error")+
  ". No fake frequency levels inserted. Other SDR processes or USB transfers may be blocking the receiver."));
 window.addEventListener("tihulu:rf-survey-clear-all",()=>{
  towers=[];aircraft=[];fmReadings=[];localStorage.removeItem(TOWER_KEY);localStorage.removeItem(AIR_KEY);render();
 });
}
