/* GNSS orbital discovery. A CelesTrak TLE prediction is not received RF or a location fix.
   Page load reads one bounded source/catalog (or daily cache), never opens the SDR. */
import {DEFAULT_CENTER} from "../core/gnss.mjs";
const SOURCE="https://celestrak.org/NORAD/elements/gp.php?GROUP=gnss&FORMAT=TLE";
const STORAGE="tihulu.rfgeo.gnss-orbits.v1",DAY=86400000;
const $=id=>document.getElementById(id),RAD=Math.PI/180,DEG=180/Math.PI;
export function tleCatalog(data){
 if(typeof data!=="string"||data.length>900000)throw Error("Orbital catalog exceeds size limit");
 const lines=data.split(/\r?\n/).filter(x=>x.trim());
 const result=[];let name="";
 for(let i=0;i<lines.length;i++){
  const row=lines[i].trim();
  if(row.startsWith("1 ")&&i+1<lines.length&&lines[i+1].startsWith("2 ")){
   const two=lines[++i].trim();
   if(row.length<63||two.length<63||row.slice(2,7)!==two.slice(2,7))continue;
   const yr=Number(row.slice(18,20)),day=Number(row.slice(20,32));
   const epoch=Date.UTC(yr>=57?1900+yr:2000+yr,0,1)+(day-1)*DAY;
   if(!Number.isFinite(epoch))continue;
   result.push({name:(name.replace(/^0\s+/,"").trim()||"GNSS "+row.slice(2,7)).slice(0,90),
    line1:row,line2:two,id:row.slice(2,7).trim(),epoch});
   name="";
  }else if(!row.startsWith("2 "))name=row;
 }
 if(result.length===0)throw Error("No valid CelesTrak TLE records; network/API response may be unavailable");
 return result.slice(0,450);
}
export function constellation(name){
 const n=String(name).toUpperCase();
 if(/GALILEO|GSAT0[12]/.test(n))return "Galileo";
 if(/GLONASS|COSMOS 2|KOSMOS 2/.test(n))return "GLONASS";
 if(/BEIDOU|COMPASS|BDS[- ]/.test(n))return "BeiDou";
 if(/QZSS|MICHIBIKI/.test(n))return "QZSS";
 if(/NAVIC|IRNSS|NVS[- ]/.test(n))return "NavIC";
 if(/WAAS|EGNOS|MSAS|GAGAN|KASS|SBAS/.test(n))return "SBAS";
 if(/GPS|NAVSTAR/.test(n))return "GPS";
 return "Other";
}
export function predictedSatellite(lib,rec,when,loc){
 const p=lib.propagate(rec,when);
 if(!p?.position||!Number.isFinite(p.position.x))return null;
 const gmst=lib.gstime(when),ecf=lib.eciToEcf(p.position,gmst);
 const look=lib.ecfToLookAngles({latitude:loc.lat*RAD,longitude:loc.lon*RAD,height:(loc.alt||0)/1000},ecf);
 const geo=lib.eciToGeodetic(p.position,gmst);
 const [az,el,lat,lon]=[(look.azimuth*DEG+360)%360,look.elevation*DEG,lib.degreesLat(geo.latitude),lib.degreesLong(geo.longitude)];
 return [az,el,lat,lon].every(Number.isFinite)&&el>=-90&&el<=90?{az,el,lat,lon}:null;
}
const colors={GPS:"#68c5ee",Galileo:"#62deb3",GLONASS:"#ffbf82",BeiDou:"#d7a4ef",QZSS:"#f9dc6e",NavIC:"#ff8099",SBAS:"#c6d3f1",Other:"#a1b3c2"};
function circle(tag,props,text){
 const el=document.createElementNS("http://www.w3.org/2000/svg",tag);
 for(const [k,v] of Object.entries(props))el.setAttribute(k,String(v));
 if(text!==undefined)el.textContent=String(text);return el;
}
function cached(){
 try{const v=JSON.parse(localStorage.getItem(STORAGE)||"null");
 if(v&&Date.now()-v.time<7*DAY&&v.raw?.length<900000){tleCatalog(v.raw);return v}}catch{}
 return null;
}
export function initAutoExplorer(){
 if(!$("live-find"))return;
 const state={pos:{lat:DEFAULT_CENTER.lat,lon:DEFAULT_CENTER.lon,measured:false,source:"Cologne reference (not your position)"},
 raw:null,lib:null,satellites:[],visible:[],loading:false};
 let mapSrc="";
 function updateMap(){
  const p=state.pos,span=Math.min(1.8,.30/Math.max(.25,Math.cos(p.lat*RAD)));
  const bbox=[p.lon-span,p.lat-.21,p.lon+span,p.lat+.21].join(",");
  const marker=p.measured?"&marker="+encodeURIComponent(p.lat+","+p.lon):"";
  const url="https://www.openstreetmap.org/export/embed.html?bbox="+encodeURIComponent(bbox)+"&layer=mapnik"+marker;
  if(mapSrc!==url){$("live-osm").src=url;mapSrc=url}
  $("live-pos-type").textContent=p.measured?"DEVICE POSITION":"REFERENCE ONLY";
  $("live-pos-label").textContent=p.source+" · "+p.lat.toFixed(5)+"°, "+p.lon.toFixed(5)+"°";
  $("live-earth-source").textContent=p.measured?"MEASURED LOCATION":"COLOGNE REFERENCE";
  $("live-open-osm").href="https://www.openstreetmap.org/#map=11/"+p.lat+"/"+p.lon;
 }
 function drawSky(){
  const sky=$("live-sky-svg");sky.replaceChildren();
  const base={cx:230,cy:192,r:151};
  sky.append(circle("circle",{...base,fill:"#102133",stroke:"#4d7188","stroke-width":2}));
  for(const elev of [30,60])sky.append(circle("circle",{cx:230,cy:192,r:151*(90-elev)/90,stroke:"#32546b",fill:"none"}));
  for(let az=0;az<360;az+=45){const a=az*RAD;
   sky.append(circle("line",{x1:230,y1:192,x2:230+151*Math.sin(a),y2:192-151*Math.cos(a),stroke:"#294b60"}));
  }
  for(const [name,x,y] of [["N",230,24],["E",404,197],["S",230,363],["W",56,197]])
    sky.append(circle("text",{x,y,"text-anchor":"middle",fill:"#b6d8e8","font-size":17},name));
  const above=state.visible.filter(s=>s.el>=0).sort((a,b)=>b.el-a.el);
  for(const s of above.slice(0,90)){
   const a=s.az*RAD,r=151*(90-s.el)/90;
   const dot=circle("circle",{cx:230+r*Math.sin(a),cy:192-r*Math.cos(a),r:5.5,fill:colors[s.group]||colors.Other});
   dot.append(circle("title",{},s.name+" · "+s.group+" · "+s.el.toFixed(1)+"° predicted"));
   sky.append(dot);
  }
  const list=$("live-satellite-list");list.replaceChildren();
  const counts={};
  for(const s of above)counts[s.group]=(counts[s.group]||0)+1;
  for(const [name,n] of Object.entries(counts).sort((a,b)=>b[1]-a[1])){
   const row=document.createElement("div");row.className="live-sat-row";
   const swatch=document.createElement("i");swatch.style.backgroundColor=colors[name]||colors.Other;
   const text=document.createElement("strong");text.textContent=name;
   const num=document.createElement("span");num.textContent=n+" above horizon";
   row.append(swatch,text,num);list.append(row);
  }
  if(!above.length){const p=document.createElement("p");p.textContent=state.satellites.length?"No GNSS satellites predicted above horizon.":"No orbital predictions available; click Refresh Satellites.";list.append(p)}
  $("live-above").textContent=state.satellites.length?String(above.length):"—";
  $("live-sky-source").textContent=state.satellites.length?"SGP4 PREDICTION":"ORBITS UNAVAILABLE";
 }
 function recalc(){
  if(!state.lib||!state.satellites.length){state.visible=[];drawSky();return}
  const now=new Date();
  state.visible=state.satellites.map(s=>{
   try{const p=predictedSatellite(state.lib,s.rec,now,state.pos);return p?{...s,...p}:null}catch{return null}
  }).filter(Boolean);
  drawSky();
  window.dispatchEvent(new CustomEvent("tihulu:orbit",{detail:{source:"CelesTrak SGP4 / PREDICTED",satellites:state.visible.map(s=>({lat:s.lat,lon:s.lon,az:s.az,el:s.el,id:s.id,group:s.group,name:s.name}))}}));
  const ages=state.satellites.map(s=>Math.abs(Date.now()-s.epoch)/DAY).sort((a,b)=>a-b);
  const median=ages.length?ages[Math.floor(ages.length/2)]:0;
  $("live-epoch").textContent="Median orbit epoch age "+median.toFixed(1)+" days"+(median>7?" · STALE":"");
 }
 async function ingest(raw,label,time){
  const parsed=tleCatalog(raw);
  if(!state.lib)state.lib=await import("https://esm.sh/satellite.js@6.0.1?bundle");
  state.satellites=parsed.map(s=>{
    try{const rec=state.lib.twoline2satrec(s.line1,s.line2);
      return !rec||rec.error?null:{...s,rec,group:constellation(s.name)}
    }catch{return null}
  }).filter(Boolean);
  if(!state.satellites.length)throw Error("No usable orbital records");
  $("live-total").textContent=state.satellites.length+" tracked";
  $("live-orbit-status").textContent=label+" · "+new Date(time).toLocaleString()+" · SGP4 only, not received RF.";
  recalc();
 }
 async function fetchCatalog(force=false){
  if(state.loading)return;
  state.loading=true;$("live-refresh").disabled=true;
  const cache=cached();
  try{
   if(cache&&!state.satellites.length){
    try{await ingest(cache.raw,"CelesTrak cache",cache.time)}catch(error){
      $("live-orbit-status").textContent="Cache could not be propagated: "+error.message;
    }
   }
   if(cache&&!force&&Date.now()-cache.time<DAY)return;
   $("live-orbit-status").textContent="Automatically fetching current GNSS orbital data from CelesTrak…";
   const ctrl=new AbortController(),timer=setTimeout(()=>ctrl.abort(),13000);
   let response;
   try{response=await fetch(SOURCE,{mode:"cors",cache:"no-store",signal:ctrl.signal})}finally{clearTimeout(timer)}
   if(!response.ok)throw Error("HTTP "+response.status);
   const raw=await response.text();
   if(tleCatalog(raw).length<10)throw Error("GNSS catalog unexpectedly small");
   await ingest(raw,"CelesTrak updated",Date.now());
   try{localStorage.setItem(STORAGE,JSON.stringify({time:Date.now(),raw}))}catch{}
  }catch(error){
   $("live-orbit-status").textContent=cache&&state.satellites.length?
    "Online refresh failed ("+error.message+"); using cached orbits.":
    "GNSS orbit download failed: "+error.message+". Retry when online.";
   if(!state.satellites.length){$("live-total").textContent="Unavailable";drawSky()}
  }finally{state.loading=false;$("live-refresh").disabled=false}
 }
 $("live-refresh").addEventListener("click",()=>{void fetchCatalog(true)});
 $("live-find").addEventListener("click",()=>{
   $("live-position-status").textContent="Checking measured GNSS/browser position sources; aircraft or station coordinates alone cannot locate you.";
   window.dispatchEvent(new Event("tihulu:find-request"));
 });
 $("live-connect").addEventListener("click",()=>{$("usb-select")?.click()});
 window.addEventListener("tihulu:position",e=>{
   const p=e.detail;if(!p||![p.lat,p.lon].every(Number.isFinite)||Math.abs(p.lat)>90||Math.abs(p.lon)>180)return;
   state.pos={lat:p.lat,lon:p.lon,alt:p.alt||0,source:p.provider||"Device location",measured:true};
   $("live-position-status").textContent="Position acquired: "+state.pos.source+"; sky recalculated.";
   updateMap();recalc();
 });
 window.addEventListener("tihulu:receiver-status",e=>{
   $("live-usb-status").textContent=e.detail?.status||"Not connected";
   $("live-usb-detail").textContent=e.detail?.message||"No radio activity";
 });
 const dashboard=$("view-dashboard"),legacyMetrics=dashboard?.querySelector(":scope > .metrics"),legacyCards=dashboard?.querySelector(":scope > .panel-grid");
 if(dashboard&&legacyMetrics&&legacyCards){
   const extra=document.createElement("details");extra.className="live-advanced";
   const summary=document.createElement("summary");summary.textContent="Advanced tools · Import NMEA / SP3 / Hardware diagnostics";
   extra.append(summary);dashboard.insertBefore(extra,legacyMetrics);extra.append(legacyMetrics,legacyCards);
 }
 updateMap();drawSky();void fetchCatalog();
 // Periodic geometry recalculation only; no network refresh, new permissions or RF scan.
 setInterval(()=>{if(document.visibilityState==="visible"&&state.satellites.length)recalc()},60000);
}
