/* TIHULU satellite tracking maps: browser-only TLE geometry, never RF identity.
 * OSM tiles requested only when the operator opens the Earth map. */
const $ = id => document.getElementById(id);
const RAD=Math.PI/180, DEG=180/Math.PI;
const COLORS={iss:"#61e5fa",meteor:"#72eea3",cubesat:"#f9c679",iridium:"#c29aff"};
const BANDS={iss:145800000,meteor:137900000,iridium:1620000000};
const RADIO_NOTES={
 iss:"145.800 MHz voice/SSTV or 145.825 MHz APRS; ISS radio modes can be inactive",
 meteor:"137.900 MHz or 137.100 MHz LRPT candidate; use a 137 MHz satellite antenna",
 cubesat:"Satellite-specific VHF/UHF frequencies are not determined by TLE alone",
 iridium:"1616–1626.5 MHz L-band energy survey only; no private messages"
};
export function mapValidCoordinates(lat,lon){return Number.isFinite(lat)&&Number.isFinite(lon)&&lat>=-90&&lat<=90&&lon>=-180&&lon<=180;}
export function mapSkyPoint(az,elev,cx,cy,radius){
 const r=(90-Math.max(0,Math.min(90,elev)))*radius/90;
 return [cx+r*Math.sin(az*RAD),cy-r*Math.cos(az*RAD)];
}
export function mapFootprintKm(altKm,el){
 if(!Number.isFinite(altKm)||altKm<0)return 0;
 const R=6371,angle=Math.min(90,Math.max(0,el))*RAD;
 return R*Math.max(0,Math.acos(Math.max(-1,Math.min(1,R/(R+altKm)*Math.cos(angle))))-angle);
}
export function mapSplitDateline(points){
 const result=[];let segment=[];
 for(const point of points){
   if(segment.length && Math.abs(point[1]-segment[segment.length-1][1])>180){
     if(segment.length>1)result.push(segment);
     segment=[];
   }
   segment.push(point);
 }
 if(segment.length>1)result.push(segment);
 return result;
}
function propagate(lib,rec,time,observer){
 const state=lib.propagate(rec,time);
 if(!state || !state.position || !Number.isFinite(state.position.x))return null;
 const gmst=lib.gstime(time),geo=lib.eciToGeodetic(state.position,gmst);
 const look=lib.ecfToLookAngles(observer,lib.eciToEcf(state.position,gmst));
 const lat=lib.degreesLat(geo.latitude),lon=lib.degreesLong(geo.longitude);
 const el=look.elevation*DEG,az=(look.azimuth*DEG+360)%360;
 if(!mapValidCoordinates(lat,lon)||!Number.isFinite(geo.height)||
 !Number.isFinite(el)||el<-90||el>90||!Number.isFinite(az)||!Number.isFinite(look.rangeSat))return null;
 return {lat,lon,altKm:geo.height,el,az,rangeKm:look.rangeSat};
}
function elFormat(value){return value.toFixed(1)+"°";}
function fmtDate(value){return new Date(value).toLocaleString(undefined,{dateStyle:"short",timeStyle:"short"});}
function labelFor(cat){return COLORS[cat]||"#ffffff";}
function detailsNode(tag,content,cls){
 const n=document.createElement(tag);n.textContent=content;if(cls)n.className=cls;return n;
}
export function createSatelliteMaps({getTles,getSatLib,getPasses,getLastCapture,onTune,log}){
 const family=$("map-family"),showAbove=$("map-above"),time=$("map-time");
 const ground=$("earth-map"),sky=$("sky-chart"),info=$("map-detail"),list=$("map-list");
 let leaflet=null,earthMap=null,markers=null,tracks=null,stationPin=null;
 let current=[],satrecMap=new Map(),selectedId=null,skyHit=[],run=0,lastUpdate=0;
 let mapStarted=false,view="sky",loading=null;
 const status=text=>$("map-state").textContent=String(text);
 const observer=()=>{
  const lat=Number($("lat").value),lon=Number($("lon").value);
  if(!mapValidCoordinates(lat,lon))throw Error("Invalid ground station coordinates");
  return {lat,lon,station:{longitude:lon*RAD,latitude:lat*RAD,height:0}};
 };
 const mapDate=()=>new Date(Date.now()+Number(time.value)*60000);
 const selected=()=>current.find(x=>String(x.id)===String(selectedId));
 const bandMatch=(x)=>{
  if(!$("map-band").checked)return true;
  const f=Number($("preset").value);
  if([145800000,145825000,437800000].includes(f))return x.family==="iss";
  if([137900000,137100000].includes(f))return x.family==="meteor";
  if(f===436000000)return x.family==="cubesat"; // survey vicinity only; not an assigned frequency
  if(f===1620000000)return x.family==="iridium";
  return false;
 };
 const filtered=()=>current.filter(x=>(family.value==="all"||family.value===x.family)&&(!showAbove.checked||x.el>=0)&&bandMatch(x))
   .sort((a,b)=>b.el-a.el).slice(0,40);
 function setView(kind){
  view=kind;$("map-sky-pane").hidden=kind!=="sky";$("map-earth-pane").hidden=kind!=="earth";
  for(const name of ["sky","earth"]){
   const b=$("map-tab-"+name);b.classList.toggle("active",name===kind);
   b.setAttribute("aria-selected",name===kind?"true":"false");
  }
  if(view==="sky")drawSky();
  else if(earthMap){setTimeout(()=>earthMap.invalidateSize(),25);drawEarth();}
 }
 function choose(id){
  selectedId=id;drawList();drawDetail();if(view==="sky")drawSky();else drawEarth();
 }
 function drawList(){
  list.replaceChildren();
  const rows=filtered();
  if(!rows.length){
   list.append(detailsNode("p",getTles().length?"No satellites match the filters at this time.":"Load TLE data using Refresh orbit data or Import local TLE file.","hint"));
   return;
  }
  for(const s of rows){
   const b=detailsNode("button",s.name,"sat-row"+(String(s.id)===String(selectedId)?" selected":""));
   b.type="button";b.style.borderLeftColor=labelFor(s.family);
   const sub=detailsNode("small",s.family.toUpperCase()+" · "+(s.el>=0?"el "+elFormat(s.el)+" · az "+elFormat(s.az):"below horizon")+" · predicted geometry");
   b.append(sub);b.addEventListener("click",()=>choose(s.id));list.append(b);
  }
 }
 function drawDetail(){
  info.replaceChildren();
  const s=selected();
  if(!s){info.append(detailsNode("p","Select a satellite to see azimuth, elevation, ground track and compatible receiver band.","hint"));return;}
  info.append(detailsNode("h3",s.name+" · NORAD "+s.id));
  info.append(detailsNode("p","Azimuth "+elFormat(s.az)+" · Elevation "+elFormat(s.el)+
    " · range "+Math.round(s.rangeKm)+" km · orbital altitude "+Math.round(s.altKm)+" km.","hint"));
  info.append(detailsNode("p","Ground subpoint: "+s.lat.toFixed(3)+"°, "+s.lon.toFixed(3)+
    "°. "+(s.el>=0?"Above local horizon (geometry only).":"Below your local horizon."),"hint"));
  info.append(detailsNode("p",RADIO_NOTES[s.family]||"No frequency profile available.","hint"));
  if(s.ageDays!=null){
   info.append(detailsNode("p","TLE orbital epoch "+s.ageDays.toFixed(1)+" days old"+
      (s.ageDays>7?" — stale; refresh before scheduling.":"."),
      s.ageDays>7?"map-warning":"hint"));
  }
  if(s.family==="cubesat"){
   info.append(detailsNode("p","No satellite-specific downlink has been verified. A generic 436 MHz survey is NOT proof that this CubeSat transmits there.","map-warning"));
  }else{
   const btn=detailsNode("button","Select "+(BANDS[s.family]/1e6).toFixed(3)+" MHz in SDR");btn.type="button";
   btn.addEventListener("click",()=>{
    onTune(BANDS[s.family]);log("Selected candidate "+s.family+" band for "+s.name+"; RF capture has NOT started.");
    status("Frequency selected. Start real USB capture to acquire samples; a TLE position does not identify received RF.");
   });
   info.append(btn);
  }
  const match=getPasses().find(p=>String(p.id)===String(s.id)&&p.los>Date.now());
  if(match)info.append(detailsNode("p","Next predicted pass: "+fmtDate(match.aos)+" → "+fmtDate(match.los)+
   " · maximum elevation "+elFormat(match.maximum)+".","hint"));
  const previous=getLastCapture();
  if(previous){
   info.append(detailsNode("p","Last measured USB sample: "+(previous.frequency_hz/1e6).toFixed(3)+
    " MHz at "+fmtDate(previous.observedAt)+". NOT attributed to "+s.name+".","hint"));
  }
  const link=detailsNode("a","Compare predictions on Heavens-Above");
  link.href="https://www.heavens-above.com/";link.rel="noopener noreferrer";link.target="_blank";info.append(link);
 }
 function drawSky(){
  const ctx=sky.getContext("2d");if(!ctx)return;
  const W=sky.width,H=sky.height,cx=W/2,cy=H/2,R=Math.min(W,H)*.38;
  ctx.fillStyle="#08182b";ctx.fillRect(0,0,W,H);ctx.strokeStyle="#355472";ctx.lineWidth=2;
  for(const elev of [0,30,60]){
   ctx.beginPath();ctx.arc(cx,cy,R*(90-elev)/90,0,Math.PI*2);ctx.stroke();
  }
  for(let az=0;az<360;az+=45){
   const [x,y]=mapSkyPoint(az,0,cx,cy,R);
   ctx.beginPath();ctx.moveTo(cx,cy);ctx.lineTo(x,y);ctx.stroke();
  }
  ctx.font="bold 24px system-ui";ctx.textAlign="center";ctx.fillStyle="#d7eaff";
  for(const [az,name] of [[0,"N"],[90,"E"],[180,"S"],[270,"W"]]){
   const [x,y]=mapSkyPoint(az,0,cx,cy,R+30);ctx.fillText(name,x,y+7);
  }
  ctx.font="16px system-ui";ctx.fillText("ZENITH · 90°",cx,cy-10);
  const s=selected();
  if(s&&s.el>=0){
   let started=false;ctx.strokeStyle="#f0f8ff";ctx.lineWidth=3;ctx.beginPath();
   const o=observer().station;
   for(let minute=-15;minute<=15;minute++){
    const p=propagate(s.lib,s.rec,new Date(mapDate().getTime()+minute*60000),o);
    if(!p||p.el<0){started=false;continue;}
    const [x,y]=mapSkyPoint(p.az,p.el,cx,cy,R);
    if(!started){ctx.moveTo(x,y);started=true;}else ctx.lineTo(x,y);
   }
   ctx.stroke();
  }
  skyHit=[];
  for(const s of filtered().filter(x=>x.el>=0).slice(0,30)){
   const [x,y]=mapSkyPoint(s.az,s.el,cx,cy,R),active=String(s.id)===String(selectedId);
   ctx.beginPath();ctx.fillStyle=labelFor(s.family);ctx.arc(x,y,active?9:6,0,Math.PI*2);ctx.fill();
   if(active){
    ctx.strokeStyle="#fff";ctx.lineWidth=2;ctx.stroke();
    ctx.textAlign="left";ctx.font="bold 15px system-ui";ctx.fillStyle="#fff";
    ctx.fillText(s.name.slice(0,23),Math.min(W-180,x+13),Math.max(25,y-12));
   }
   skyHit.push({x,y,id:s.id});
  }
  if(!skyHit.length){
   ctx.fillStyle="#c5d9ef";ctx.font="16px system-ui";ctx.textAlign="center";
   ctx.fillText(getTles().length?"No satellites above horizon in this subset.":"Load orbital elements to display the sky.",cx,H-24);
  }
 }
 sky.addEventListener("click",e=>{
  const bounds=sky.getBoundingClientRect();
  const x=(e.clientX-bounds.left)*sky.width/bounds.width,y=(e.clientY-bounds.top)*sky.height/bounds.height;
  const nearest=skyHit.map(item=>({...item,dist:Math.hypot(item.x-x,item.y-y)})).sort((a,b)=>a.dist-b.dist)[0];
  if(nearest&&nearest.dist<26)choose(nearest.id);
 });
 function drawEarth(){
  if(!earthMap)return;
  markers.clearLayers();tracks.clearLayers();
  const selectedSat=selected(),now=mapDate(),o=observer();
  stationPin.setLatLng([o.lat,o.lon]);
  for(const s of filtered().slice(0,28)){
   const active=selectedSat&&String(s.id)===String(selectedSat.id);
   const pin=leaflet.circleMarker([s.lat,s.lon],{radius:active?10:7,
      color:active?"#fff":labelFor(s.family),weight:active?3:2,
      fillColor:labelFor(s.family),fillOpacity:0.84});
   pin.bindTooltip(s.name+" · "+elFormat(s.el)+" el · TLE estimate");
   pin.addTo(markers);pin.on("click",()=>choose(s.id));
   if(active&&$("map-tracks").checked){
    const pts=[];
    for(let m=-45;m<=45;m+=3){
     const p=propagate(s.lib,s.rec,new Date(now.getTime()+m*60000),o.station);
     if(p)pts.push([p.lat,p.lon]);
    }
    mapSplitDateline(pts).forEach(segment=>{
     leaflet.polyline(segment,{color:labelFor(s.family),weight:3,opacity:0.84,
      dashArray:"5 5"}).addTo(tracks);
    });
   }
   if(active&&$("map-footprint").checked){
    leaflet.circle([s.lat,s.lon],{radius:mapFootprintKm(s.altKm,Number($("elev").value))*1000,
     color:labelFor(s.family),weight:1,opacity:.6,dashArray:"4 6",
     fillColor:labelFor(s.family),fillOpacity:0.05}).addTo(tracks);
   }
  }
 }
 async function openEarth(){
  if(earthMap){setView("earth");return;}
  if(loading)return loading;
  loading=(async()=>{
   status("Loading OpenStreetMap only for the visible viewport (no bulk or offline tile download)...");
   const css=document.createElement("link");css.rel="stylesheet";
   css.href="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css";
   css.crossOrigin="anonymous";css.integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=";
   document.head.append(css);
   const L=await new Promise((resolve,reject)=>{
    if(window.L)return resolve(window.L);
    const script=document.createElement("script");script.crossOrigin="anonymous";
    script.integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=";
    script.src="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js";
    script.onload=()=>resolve(window.L);
    script.onerror=()=>reject(Error("Leaflet unavailable: check network/CDN"));document.head.append(script);
   });
   if(!L)throw Error("Leaflet did not initialize");
   leaflet=L;const o=observer();
   setView("earth"); // Show container before Leaflet measures its dimensions.
   earthMap=L.map("earth-map",{worldCopyJump:true,preferCanvas:true}).setView([o.lat,o.lon],3);
   L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png",{
    minZoom:2,maxZoom:12,updateWhenIdle:true,keepBuffer:1,detectRetina:false,
    attribution:'&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap contributors</a>'
   }).addTo(earthMap);
   markers=L.layerGroup().addTo(earthMap);tracks=L.layerGroup().addTo(earthMap);
   stationPin=L.circleMarker([o.lat,o.lon],{radius:8,color:"#fff",weight:2,
      fillColor:"#27ddff",fillOpacity:0.9}).bindTooltip("Ground station (manual coordinates)").addTo(earthMap);
   setView("earth");earthMap.invalidateSize();drawEarth();
   status("OSM Earth map ready · orbit predictions only; map tiles are requested for the visible area.");
  })();
  try{await loading;}finally{loading=null;}
 }
 async function refresh(){
  if(!mapStarted)return;
  const token=++run;
  let o;try{o=observer();}catch(e){status(e.message);return;}
  const catalog=getTles();
  if(!catalog.length){
   current=[];drawList();drawDetail();drawSky();drawEarth();
   status("No TLE catalog loaded. Click Refresh orbit data or import a local TLE file.");
   return;
  }
  let lib;try{lib=await getSatLib();}catch(e){status("Orbital library unavailable: "+e.message);return;}
  if(token!==run)return;
  const dt=mapDate(),rows=[];
  for(const item of catalog.slice(0,30)){
   try{
    const rec=lib.twoline2satrec(item.l1,item.l2);
    const pos=propagate(lib,rec,dt,o.station);if(!pos)continue;
    const age=Number.isFinite(rec.jdsatepoch)?Math.abs(Date.now()-(rec.jdsatepoch-2440587.5)*86400000)/86400000:null;
    rows.push({...item,...pos,rec,lib,ageDays:age});
   }catch(e){/* bad TLE, no fictional coordinate fallback */}
  }
  current=rows;
  if(!rows.some(x=>String(x.id)===String(selectedId)))selectedId=rows[0]?.id??null;
  $("map-time-label").textContent=(Number(time.value)===0?"LIVE / now":(Number(time.value)>0?"+":"")+time.value+" min simulated")+" · "+fmtDate(dt);
  drawList();drawDetail();drawSky();drawEarth();lastUpdate=Date.now();
  status(rows.length+" TLE-derived satellites · "+rows.filter(s=>s.el>=0).length+" above local horizon"+
   (rows.some(s=>s.ageDays>7)?" · WARNING: stale orbital elements":"")+
   " · No received satellite signals verified");
 }
 for(const kind of ["sky","earth"]){
  $("map-tab-"+kind).addEventListener("click",()=>{
   mapStarted=true;setView(kind);
   if(kind==="earth"&&!earthMap)status("Click Load OpenStreetMap to fetch map tiles on demand.");
   else void refresh();
  });
 }
 $("map-load").addEventListener("click",()=>{
  mapStarted=true;void openEarth().then(refresh).catch(e=>{
   status("Earth map unavailable: "+e.message+"; sky chart still works.");log("OSM map: "+e.message);
  });
 });
 $("map-recenter").addEventListener("click",()=>{
  if(!earthMap)return;try{const o=observer();earthMap.setView([o.lat,o.lon],Math.max(3,earthMap.getZoom()));}catch(e){status(e.message);}
 });
 for(const id of ["map-family","map-above","map-band","map-tracks","map-footprint"]){
  $(id).addEventListener("change",()=>{drawList();drawDetail();drawSky();drawEarth();});
 }
 for(const id of ["city","lat","lon","elev"]){
  $(id).addEventListener("change",()=>{if(mapStarted)void refresh();});
 }
 $("preset").addEventListener("change",()=>{drawList();drawDetail();drawSky();drawEarth();});
 time.addEventListener("input",()=>{void refresh();});
 $("map-now").addEventListener("click",()=>{time.value="0";void refresh();});
 $("map-reset-selection").addEventListener("click",()=>{selectedId=null;drawList();drawDetail();drawSky();drawEarth();});
 const tick=setInterval(()=>{
  if(mapStarted&&!document.hidden&&Number(time.value)===0&&Date.now()-lastUpdate>15000)void refresh();
 },18000);
 window.addEventListener("pagehide",()=>{clearInterval(tick);if(earthMap)earthMap.remove();});
 mapStarted=true;setView("sky");drawList();
 status("Load TLE data, then use Sky or Earth. Tracking is geometric; USB permission alone does not prove reception.");
 return {refresh,choose};
}
