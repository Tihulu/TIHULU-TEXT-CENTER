import { sortSatelliteList, nextPassForSatellite } from './pass_sort.mjs';
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
export function mapShouldFallback(successfulTiles,failedTiles,elapsedMs=0){
 return successfulTiles===0&&(failedTiles>=3||elapsedMs>=9000);
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
 let osmTiles=null,worldOutline=null,worldData=null,worldPromise=null;
 let overviewDrawVersion=0,overviewHits=[];
 let worldAttributionAdded=false;
 let tileDeadline=null,tileFailures=0,tileSuccesses=0,basemapRevision=0;
 const basemapChoice=$("map-basemap");
 const basemapStatus=message=>{$("map-basemap-state").textContent=String(message);};
 function clearTileDeadline(){
   if(tileDeadline!==null){clearTimeout(tileDeadline);tileDeadline=null;}
 }
 let current=[],satrecMap=new Map(),selectedId=null,skyHit=[],run=0,lastUpdate=0;
 let mapStarted=false,view="sky",loading=null;
 const status=text=>$("map-state").textContent=String(text);
 const observer=()=>{
  const lat=Number($("lat").value),lon=Number($("lon").value);
  if(!$("lat").value.trim()||!$("lon").value.trim()||!mapValidCoordinates(lat,lon))throw Error("Enter valid ground station latitude and longitude");
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
 const filtered=()=>sortSatelliteList(
   current.filter(x=>(family.value==="all"||family.value===x.family)&&(!showAbove.checked||x.el>=0)&&bandMatch(x)),
   $("map-sat-sort").value,getPasses()
 ).slice(0,40);
 function setView(kind){
  view=kind;$("map-sky-pane").hidden=kind!=="sky";$("map-earth-pane").hidden=kind!=="earth";
  for(const name of ["sky","earth"]){
   const b=$("map-tab-"+name);b.classList.toggle("active",name===kind);
   b.setAttribute("aria-selected",name===kind?"true":"false");
  }
  if(view==="sky")drawSky();
  else{
    void drawWorldCanvas();
    if(earthMap){setTimeout(()=>earthMap.invalidateSize(),25);drawEarth();}
  }
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
   const next=nextPassForSatellite(s,getPasses());
   const sub=detailsNode("small",s.family.toUpperCase()+" · "+(s.el>=0?"el "+elFormat(s.el)+" · az "+elFormat(s.az):"below horizon")+
      (next!==null?" · next "+fmtDate(next):" · no calculated next pass")+" · orbital estimate");
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
 function geoCanvasXY(lon,lat,W,H){
   return [(lon+180)/360*W,(90-lat)/180*H];
 }
 async function drawWorldCanvas(){
   const canvas=$("earth-world-canvas"),readout=$("earth-world-status");
   if(!canvas)return;
   const ctx=canvas.getContext("2d");
   if(!ctx){readout.textContent="Canvas 2D unavailable. Use a compatible browser.";return;}
   const version=++overviewDrawVersion,W=canvas.width,H=canvas.height;
   ctx.fillStyle="#0a1f35";ctx.fillRect(0,0,W,H);
   ctx.lineWidth=1;ctx.strokeStyle="#34516a";
   for(let lon=-150;lon<=150;lon+=30){
     const [x]=geoCanvasXY(lon,0,W,H);
     ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,H);ctx.stroke();
   }
   for(let lat=-60;lat<=60;lat+=30){
     const [,y]=geoCanvasXY(0,lat,W,H);
     ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(W,y);ctx.stroke();
   }
   let geo;
   try{geo=await getWorldOutlineData();}
   catch(e){
     readout.textContent="Bundled Earth land data failed to load: "+e.message+
       ". Satellite positions are still listed at right.";
     log("World Canvas geography error: "+e.message);return;
   }
   if(version!==overviewDrawVersion||view!=="earth")return;
   ctx.lineWidth=1.05;ctx.strokeStyle="#a2bfc9";
   ctx.fillStyle="#286d83";
   let polygons=0;
   for(const feature of geo.features){
     const g=feature?.geometry;
     if(!g)continue;
     const groups=g.type==="Polygon"?[g.coordinates]:g.type==="MultiPolygon"?g.coordinates:[];
     for(const polygon of groups){
       ctx.beginPath();let containsPath=false;
       for(const ring of polygon){
         let prior=null,hasFirst=false;
         for(const vertex of ring){
           if(!Array.isArray(vertex)||vertex.length<2)continue;
           const [lon,lat]=vertex;
           if(!mapValidCoordinates(Number(lat),Number(lon)))continue;
           const [x,y]=geoCanvasXY(lon,lat,W,H);
           if(!hasFirst || (prior!==null&&Math.abs(lon-prior)>180)){
             if(hasFirst)ctx.closePath();
             ctx.moveTo(x,y);hasFirst=true;
           }else ctx.lineTo(x,y);
           containsPath=true;prior=lon;
         }
         if(hasFirst)ctx.closePath();
       }
       if(containsPath){ctx.fill("evenodd");ctx.stroke();polygons++;}
     }
   }
   // Ground station and orbit positions use the same locally calculated
   // coordinates as the pass calendar (never fabricated receptions).
   const o=observer(),[gx,gy]=geoCanvasXY(o.lon,o.lat,W,H);
   ctx.beginPath();ctx.arc(gx,gy,8,0,2*Math.PI);ctx.fillStyle="#00d5ff";ctx.fill();
   ctx.lineWidth=2;ctx.strokeStyle="#fff";ctx.stroke();
   ctx.textAlign="left";ctx.font="13px system-ui";ctx.fillStyle="#d8f1fc";
   ctx.fillText("Ground station",Math.min(W-120,gx+11),Math.max(14,gy-12));
   overviewHits=[];
   for(const sat of filtered().slice(0,40)){
     const [x,y]=geoCanvasXY(sat.lon,sat.lat,W,H);
     const chosen=String(sat.id)===String(selectedId);
     ctx.beginPath();ctx.arc(x,y,chosen?9:5,0,2*Math.PI);
     ctx.fillStyle=labelFor(sat.family);ctx.fill();
     if(chosen){
       ctx.lineWidth=2;ctx.strokeStyle="#fff";ctx.stroke();
       ctx.fillStyle="#f4fbff";ctx.font="bold 13px system-ui";
       ctx.fillText(sat.name.slice(0,28),Math.min(W-160,x+12),Math.max(16,y-12));
     }
     overviewHits.push({id:sat.id,x,y});
   }
   readout.textContent="Map drawn locally: "+geo.features.length+
     " Natural Earth land features ("+polygons+" polygons), "+
     overviewHits.length+" predicted satellite points. "+
     "Click a satellite dot to select it. No OSM raster or USB permission needed.";
 }
 $("earth-world-canvas").addEventListener("click",event=>{
   const canvas=$("earth-world-canvas"),rect=canvas.getBoundingClientRect();
   const x=(event.clientX-rect.left)*canvas.width/rect.width,
         y=(event.clientY-rect.top)*canvas.height/rect.height;
   const nearest=overviewHits.map(p=>({...p,dist:Math.hypot(p.x-x,p.y-y)}))
     .sort((a,b)=>a.dist-b.dist)[0];
   if(nearest&&nearest.dist<20)choose(nearest.id);
 });
 function drawEarth(){
  void drawWorldCanvas();
  if(!earthMap)return;
  markers.clearLayers();tracks.clearLayers();
  const selectedSat=selected(),now=mapDate(),o=observer();
  stationPin.setLatLng([o.lat,o.lon]);
  for(const s of filtered().slice(0,28)){
   const active=selectedSat&&String(s.id)===String(selectedSat.id);
   const pin=leaflet.circleMarker([s.lat,s.lon],{radius:active?10:7,
      color:active?"#fff":labelFor(s.family),weight:active?3:2,
      fillColor:labelFor(s.family),fillOpacity:0.84});
   const tooltip=document.createElement("span");
   tooltip.textContent=s.name+" · "+elFormat(s.el)+" el · TLE estimate";
   pin.bindTooltip(tooltip);
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
 // A page-hosted public-domain Natural Earth outline is a real, usable map
 // background even when Brave Shields or network policy rejects OSM tiles.
 async function getWorldOutlineData(){
   if(worldData)return worldData;
   if(!worldPromise){
     worldPromise=(async()=>{
       const response=await fetch("./natural-earth-land-110m.geojson",{cache:"force-cache"});
       if(!response.ok)throw Error("Bundled Natural Earth outlines unavailable: HTTP "+response.status);
       const data=await response.json();
       if(data?.type!=="FeatureCollection"||!Array.isArray(data.features)||data.features.length<100)
         throw Error("Invalid Natural Earth map data");
       worldData=data;
       return worldData;
     })();
   }
   try{return await worldPromise;}catch(error){worldPromise=null;throw error;}
 }
 function removeOsm(){
   clearTileDeadline();
   if(osmTiles&&earthMap?.hasLayer(osmTiles))earthMap.removeLayer(osmTiles);
   if(osmTiles){osmTiles.off();osmTiles=null;}
 }
 async function useWorldOutline(reason,revision){
   try{
     const features=await getWorldOutlineData();
     if(revision!==basemapRevision||!earthMap)return;
     if(!worldOutline){
       // A dedicated SVG renderer prevents Leaflet's preferCanvas setting
       // from placing the land polygons under its tile/canvas layers.
       worldOutline=leaflet.geoJSON(features,{
         renderer:leaflet.svg({pane:"world-outline",padding:0.3}),
         pane:"world-outline",
         interactive:false,
         style:{stroke:true,color:"#a3c9d8",weight:1.25,opacity:0.96,
                fillColor:"#266a83",fillOpacity:0.88}
       });
     }
     if(basemapChoice.value==="outline")removeOsm();
     if(!earthMap.hasLayer(worldOutline))worldOutline.addTo(earthMap);
     worldOutline.setStyle({
       fillOpacity:basemapChoice.value==="osm"?0.28:0.88,
       opacity:basemapChoice.value==="osm"?0.65:0.96,
       color:basemapChoice.value==="osm"?"#bce7f2":"#a3c9d8"
     });
     earthMap.invalidateSize();
     if(!worldAttributionAdded){
       earthMap.attributionControl.addAttribution(
         'World outlines: <a href="https://www.naturalearthdata.com/" target="_blank" rel="noopener noreferrer">Natural Earth (public domain)</a>'
       );
       worldAttributionAdded=true;
     }
     const numFeatures=worldOutline.getLayers().length;
     basemapStatus(reason ? "OSM failed ("+reason+"). Showing "+numFeatures+
       " land shapes from the bundled Natural Earth map. Satellite overlays are retained." :
       (basemapChoice.value==="outline"?"World map OK: ":"World background ready: ")+
       numFeatures+" real land polygons loaded from GitHub Pages. "+(basemapChoice.value==="osm"?
       "OSM raster tiles are optional and may still be blocked.":"No third-party tile server required."));
     log("Earth map: bundled Natural Earth fallback active; no external map tile download needed.");
   }catch(error){
     basemapStatus("Both map backgrounds failed: "+error.message+". Satellite positions may still appear over a plain background.");
     log("Earth fallback: "+error.message);
   }
 }
 function useOSMTiles(revision){
   removeOsm();
   // Keep world coastlines even if the raster server returns blank/blocked tiles.
   // OSM tiles appear behind the country/continent outlines.
   if(revision!==basemapRevision||basemapChoice.value!=="osm")return;
   tileFailures=0;tileSuccesses=0;
   basemapStatus("Requesting OpenStreetMap tiles for the visible viewport… This is not confirmation that tiles loaded.");
   const layer=leaflet.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png",{
     minZoom:2,maxZoom:12,updateWhenIdle:true,keepBuffer:1,detectRetina:false,
     // OSMF tile policy (2026): do not strip the public website origin Referer.
     referrerPolicy:"strict-origin-when-cross-origin",
     attribution:'&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap contributors</a>'
   });
   osmTiles=layer;
   const fallBack=reason=>{
     if(revision!==basemapRevision||basemapChoice.value!=="osm"||tileSuccesses>0)return;
     basemapChoice.value="outline";
     const nextRevision=++basemapRevision;
     clearTileDeadline();
     void useWorldOutline(reason,nextRevision);
   };
   layer.on("tileload",()=>{
     if(revision!==basemapRevision)return;
     tileSuccesses++;
     if(tileSuccesses===1){
       clearTileDeadline();
       basemapStatus("OpenStreetMap tiles loaded. Ground and satellite locations are predicted from orbit data, not detected by USB.");
     }
   });
   layer.on("tileerror",()=>{
     if(revision!==basemapRevision)return;
     tileFailures++;
     if(mapShouldFallback(tileSuccesses,tileFailures))fallBack("multiple tile request errors");
     else if(tileSuccesses>0)basemapStatus("OpenStreetMap partially loaded: "+tileFailures+
       " tile request error(s). Check Brave Shields/network or choose World outlines.");
   });
   layer.addTo(earthMap);
   // Some privacy extensions prevent tile events entirely. Never report success
   // until at least one real tileload; switch to a usable local map after 9s.
   tileDeadline=setTimeout(()=>{
     if(mapShouldFallback(tileSuccesses,tileFailures,9000))fallBack("no tiles loaded within 9 seconds");
   },9000);
 }
 async function changeBasemap(mode,why=""){
   if(!earthMap)return;
   basemapChoice.value=mode;
   const revision=++basemapRevision;
   clearTileDeadline();
   // Always have a functioning map first, before external tile requests.
   await useWorldOutline(why,revision);
   if(revision!==basemapRevision)return;
   if(mode==="osm")useOSMTiles(revision);
 }
 async function openEarth(){
  if(earthMap){setView("earth");return;}
  if(loading)return loading;
  loading=(async()=>{
   status("Loading built-in land geography; OSM tiles are optional.");
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
   const worldPane=earthMap.createPane("world-outline");
   worldPane.style.zIndex="350"; // above raster tiles (200), below satellite overlays (400)
   markers=L.layerGroup().addTo(earthMap);tracks=L.layerGroup().addTo(earthMap);
   stationPin=L.circleMarker([o.lat,o.lon],{radius:8,color:"#fff",weight:2,
      fillColor:"#27ddff",fillOpacity:0.9}).bindTooltip("Ground station (manual coordinates)").addTo(earthMap);
   setView("earth");earthMap.invalidateSize();drawEarth();
   await changeBasemap(basemapChoice.value);
   status("Earth map initialized: orbit predictions only. Check the basemap status below for actual imagery load.");
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
   if(kind==="earth"&&!earthMap){
     // The main view is self-contained Canvas; never block it on Leaflet/CDN.
     void drawWorldCanvas();
     status("Local world map drawing from bundled Natural Earth. Optional detailed Leaflet map can be opened separately.");
   }
   void refresh();
  });
 }
 $("map-load").addEventListener("click",()=>{
   mapStarted=true;
   $("earth-street-details").open=true;
   const existed=!!earthMap;
   basemapChoice.value="osm";
   void openEarth().then(async()=>{
     if(existed)await changeBasemap("osm");
     await refresh();
   }).catch(e=>{
     basemapStatus("Earth map unavailable: "+e.message+". Try bundled outlines in the Base map menu.");
     log("OSM map: "+e.message);
   });
 });
 basemapChoice.addEventListener("change",()=>{
  mapStarted=true;
  $("earth-street-details").open=true;
  const existed=!!earthMap,choice=basemapChoice.value;
  void openEarth().then(async()=>{
    if(existed)await changeBasemap(choice);
    await refresh();
  }).catch(e=>basemapStatus("Basemap unavailable: "+e.message));
 });
 $("map-diagnose").addEventListener("click",async()=>{
   const checks=[];
   await drawWorldCanvas();
   checks.push($("earth-world-status").textContent);
   checks.push("Optional Leaflet engine: "+(earthMap?"initialized":"not loaded (not required for world geography)"));
   try{
     const data=await getWorldOutlineData();
     checks.push("Bundled land data: "+data.features.length+" Natural Earth features loaded");
     if(earthMap){
       await changeBasemap("outline");
       checks.push("Vector land polygons mounted: "+(worldOutline?.getLayers().length||0));
       checks.push("Actual Leaflet land SVG paths: "+document.querySelectorAll("#earth-map .leaflet-world-outline-pane svg path").length);
       checks.push("Map size: "+earthMap.getSize().x+" × "+earthMap.getSize().y);
     }else checks.push("Choose Earth and then Load / retry OpenStreetMap to initialize Leaflet.");
   }catch(e){checks.push("Map error: "+e.message);}
   const report=checks.join("\n");
   basemapStatus(report);
   status(report); // visible even when optional Leaflet details are collapsed
   log("Map background diagnostic run; no USB activity.");
 });
 $("map-recenter").addEventListener("click",()=>{
  if(!earthMap)return;try{const o=observer();earthMap.setView([o.lat,o.lon],Math.max(3,earthMap.getZoom()));}catch(e){status(e.message);}
 });
 for(const id of ["map-family","map-above","map-band","map-sat-sort","map-tracks","map-footprint"]){
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
 window.addEventListener("pagehide",()=>{
  clearInterval(tick);clearTileDeadline();removeOsm();
  if(earthMap){earthMap.remove();earthMap=null;}
 });
 mapStarted=true;setView("sky");drawList();
 status("Load TLE data, then use Sky or Earth. Tracking is geometric; USB permission alone does not prove reception.");
 return {refresh,choose};
}
