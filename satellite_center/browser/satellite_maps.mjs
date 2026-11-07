import { sortSatelliteList, nextPassForSatellite } from './pass_sort.mjs';
import { createOrbitClock, shouldRefreshLive, trackCacheSlot, LIVE_REFRESH_MS } from './orbit_clock.mjs?v=20261106-live-v14';
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
 // Persistent Leaflet objects: live updates move existing markers/paths
 // instead of clearing all overlays every second (avoids flicker).
 const markerLayers=new Map(),trackLayers=new Map(),coverageLayers=new Map();
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
 const clock=createOrbitClock();
 let trackSlot=null;
 const trackCache=new Map();
 let mapStarted=false,view="sky",loading=null;
 // Installed desktop uses native Skyfield; web/PWA keeps browser satellite.js.
 let nativeSnapshotPending=false,nativeTrackAt=0;
 const nativeTrackCache=new Map();
 let lastVisibleMarkerCount=0,initialCatalogFitDone=false;
 const status=text=>$("map-state").textContent=String(text);
 const observer=()=>{
  const lat=Number($("lat").value),lon=Number($("lon").value);
  if(!$("lat").value.trim()||!$("lon").value.trim()||!mapValidCoordinates(lat,lon))throw Error("Enter valid ground station latitude and longitude");
  return {lat,lon,station:{longitude:lon*RAD,latitude:lat*RAD,height:0}};
 };
 const mapDate=()=>new Date(clock.time());
 function updateLiveControls(){
   const live=clock.isLive,button=$("map-now");
   button.classList.toggle("active",live);
   button.setAttribute("aria-pressed",String(live));
   $("map-pause").disabled=!live;
   const indicator=$("map-live-state");
   indicator.dataset.mode=live?"live":"paused";
   const message=live?"LIVE · updates every second while this tab is visible":
     "PAUSED / simulated snapshot · press Now / live to resume";
   // Do not re-announce an aria-live message every second.
   if(indicator.textContent!==message)indicator.textContent=message;
 }
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
  selectedId=id;drawList();drawDetail();
  if(view==="sky")drawSky();
  else{
    drawEarth();
    focusSelectedEarth();
  }
 }
 // Leaflet's station-centred viewport can contain zero satellite subpoints
 // even while the TLE catalog contains valid globally distributed satellites.
 // Only camera controls (not orbital geometry) change what can be seen.
 function focusSelectedEarth(){
   if(!earthMap)return false;
   const sat=selected();
   if(!sat||!filtered().some(row=>String(row.id)===String(sat.id))){
     $("map-overlay-count").textContent=
       "Selected satellite is excluded by current filters. Clear family/above-horizon/band filters, then focus again.";
     return false;
   }
   earthMap.setView([sat.lat,sat.lon],Math.max(4,Math.min(6,earthMap.getZoom())),{animate:false});
   updateEarthViewportCount();
   return true;
 }
 function fitTrackedEarth(){
   if(!earthMap)return false;
   const rows=filtered();
   if(!rows.length){
     $("map-overlay-count").textContent="No satellites match filters. Disable 'Only above local horizon' to see global tracks.";
     return false;
   }
   const positions=rows.filter(row=>mapValidCoordinates(row.lat,row.lon))
     .map(row=>[Math.max(-85,Math.min(85,row.lat)),row.lon]);
   if(!positions.length)return false;
   const bounds=leaflet.latLngBounds(positions);
   // At most zoom 5 for one item, and zoom 0–2 for worldwide catalogs.
   earthMap.fitBounds(bounds.pad(0.12),{padding:[20,20],maxZoom:5,animate:false});
   initialCatalogFitDone=true;
   updateEarthViewportCount();
   return true;
 }
 function updateEarthViewportCount(){
   if(!earthMap)return;
   const rows=filtered();
   const bounds=earthMap.getBounds();
   lastVisibleMarkerCount=rows.filter(row=>bounds.contains([row.lat,row.lon])).length;
   const chosen=selected();
   const selectedVisible=chosen&&bounds.contains([chosen.lat,chosen.lon]);
   $("map-overlay-count").textContent=
     lastVisibleMarkerCount+" / "+rows.length+" satellite ground markers in this map viewport. "+
     (chosen?"Selected "+chosen.name+": "+(selectedVisible?"in view.":"outside view — press Focus selected satellite. "):"")+
     "Orbit paths ±45 min and coverage are TLE geometry, not radio detections.";
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
   // Draw the same predicted tracks and coverage as the interactive street
   // map, with a global projection. Geographic edges never connect across
   // the international date line.
   const obs=observer(),displayed=filtered().slice(0,40);
   const active=selected();
   let canvasTracks=0,canvasCoverage=0;
   for(const sat of displayed){
     const chosen=active&&String(active.id)===String(sat.id);
     const coverMode=$("map-coverage-scope").value;
     if(coverMode==="all"||(coverMode==="selected"&&chosen)){
       const bounds=coverageBounds(sat);
       ctx.strokeStyle=labelFor(sat.family);
       ctx.lineWidth=chosen?2.3:1.1;
       ctx.globalAlpha=chosen?0.85:0.38;
       for(const segment of mapSplitDateline(bounds)){
         ctx.beginPath();segment.forEach(([lat,lon],i)=>{
           const [x,y]=geoCanvasXY(lon,lat,W,H);
           if(i===0)ctx.moveTo(x,y);else ctx.lineTo(x,y);
         });ctx.stroke();canvasCoverage++;
       }
       ctx.globalAlpha=1;
     }
     const trackMode=$("map-track-scope").value;
     if(trackMode==="all"||(trackMode==="selected"&&chosen)){
       ctx.strokeStyle=labelFor(sat.family);
       ctx.lineWidth=chosen?2.5:1.25;
       ctx.globalAlpha=chosen?0.96:0.6;
       for(const segment of mapSplitDateline(trackCoordinates(sat,mapDate().getTime(),obs.station))){
         ctx.beginPath();segment.forEach(([lat,lon],i)=>{
           const [x,y]=geoCanvasXY(lon,lat,W,H);
           if(i===0)ctx.moveTo(x,y);else ctx.lineTo(x,y);
         });ctx.stroke();canvasTracks++;
       }
       ctx.globalAlpha=1;
     }
   }
   // Ground station and orbit positions use the same locally calculated
   // coordinates as the pass calendar (never fabricated receptions).
   const o=obs,[gx,gy]=geoCanvasXY(o.lon,o.lat,W,H);
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
     overviewHits.length+" predicted satellite points, "+canvasTracks+
     " trajectory segments and "+canvasCoverage+" coverage outlines. "+
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
 function trackCoordinates(s,when,station){
   if(Array.isArray(s.nativeTrackCoordinates))return s.nativeTrackCoordinates;
   // Orbital ground paths change smoothly. Re-evaluate the expensive ±45min
   // propagation only once per 15 seconds, while marker positions and the
   // coverage footprint update every second in live mode.
   const slot=trackCacheSlot(when,station.latitude/RAD,station.longitude/RAD);
   if(slot!==trackSlot){trackCache.clear();trackSlot=slot;}
   const key=String(s.id);
   const old=trackCache.get(key);
   if(old&&old.line1===s.l1&&old.line2===s.l2)return old.coordinates;
   const coordinates=[];
   for(let m=-45;m<=45;m+=3){
     const pos=propagate(s.lib,s.rec,new Date(when+m*60000),station);
     if(pos)coordinates.push([pos.lat,pos.lon]);
   }
   trackCache.set(key,{line1:s.l1,line2:s.l2,coordinates});
   return coordinates;
 }
 function coverageBounds(s){
   const radius=mapFootprintKm(s.altKm,Number($("elev").value))/6371;
   if(!Number.isFinite(radius)||radius<=0)return [];
   const lat=s.lat*RAD,lon=s.lon*RAD,points=[];
   for(let a=0;a<=360;a+=8){
     const bearing=a*RAD;
     const newLat=Math.asin(Math.sin(lat)*Math.cos(radius)+
       Math.cos(lat)*Math.sin(radius)*Math.cos(bearing));
     const newLon=lon+Math.atan2(Math.sin(bearing)*Math.sin(radius)*Math.cos(lat),
       Math.cos(radius)-Math.sin(lat)*Math.sin(newLat));
     const wrapped=((newLon*DEG+540)%360)-180;
     points.push([newLat*DEG,wrapped]);
   }
   return points;
 }
 function layerCounts(){
   const tracked=filtered();
   return {displayed:tracked.length,total:current.length,
     visible:tracked.filter(s=>s.el>=0).length};
 }
 function syncSegments(layerMap,key,segments,style,type){
   const layers=layerMap.get(key)||[];
   const data=segments.filter(seg=>Array.isArray(seg)&&seg.length>1);
   for(let i=0;i<data.length;i++){
     let layer=layers[i];
     if(!layer){
       layer=type==="polygon"?
         leaflet.polygon(data[i],{pane:"sat-coverage",interactive:false,...style}):
         leaflet.polyline(data[i],{pane:"sat-tracks",interactive:false,...style});
       layer.addTo(tracks);
       layers[i]=layer;
     }else{
       layer.setLatLngs(data[i]);layer.setStyle(style);
     }
   }
   while(layers.length>data.length)tracks.removeLayer(layers.pop());
   if(layers.length)layerMap.set(key,layers);else layerMap.delete(key);
   return data.length;
 }
 function pruneSegments(layerMap,validIds){
   for(const [id,layers] of layerMap){
     if(validIds.has(id))continue;
     for(const layer of layers)tracks.removeLayer(layer);
     layerMap.delete(id);
   }
 }
 function drawEarth(){
   void drawWorldCanvas();
   if(!earthMap)return;
   const now=mapDate().getTime(),o=observer(),rows=filtered().slice(0,40);
   stationPin.setLatLng([o.lat,o.lon]);
   const target=selected();
   if(clock.isLive&&$("map-follow-selected").checked&&target){
     // Optional camera-following: changing marker positions never forces
     // an unsolicited pan while this is disabled.
     earthMap.panTo([target.lat,target.lon],{animate:false});
   }
   const scope=$("map-track-scope").value,coverage=$("map-coverage-scope").value;
   const validMarkerIds=new Set(),validTracks=new Set(),validCoverage=new Set();
   let trackCount=0,coverageCount=0;
   for(const sat of rows){
     const id=String(sat.id),active=target&&String(target.id)===id;
     const color=labelFor(sat.family);
     const showTrack=scope==="all"||(scope==="selected"&&active);
     const showCoverage=coverage==="all"||(coverage==="selected"&&active);
     validMarkerIds.add(id);
     if(showCoverage){
       const style={color,weight:1.5,opacity:active?0.85:0.45,fillColor:color,
         fillOpacity:active?0.13:0.035};
       const segments=mapSplitDateline(coverageBounds(sat));
       coverageCount+=syncSegments(coverageLayers,id,segments,style,"polygon");
       validCoverage.add(id);
     }
     if(showTrack){
       const style={color,weight:active?3.4:1.9,opacity:active?0.96:0.60,
         dashArray:active?null:"5 5"};
       const segments=mapSplitDateline(trackCoordinates(sat,now,o.station));
       trackCount+=syncSegments(trackLayers,id,segments,style,"line");
       validTracks.add(id);
     }
     const style={radius:active?10:6,color:active?"#fff":color,
       weight:active?3:1.5,fillColor:color,fillOpacity:0.95};
     let pin=markerLayers.get(id);
     if(!pin){
       pin=leaflet.circleMarker([sat.lat,sat.lon],{
         pane:"sat-markers",...style
       });
       pin.on("click",()=>choose(id));
       pin.bindTooltip(sat.name+" · "+elFormat(sat.el)+" el · orbital position only");
       pin.addTo(markers);markerLayers.set(id,pin);
     }else{
       pin.setLatLng([sat.lat,sat.lon]);
       pin.setStyle(style);
       pin.setTooltipContent(sat.name+" · "+elFormat(sat.el)+" el · orbital position only");
     }
   }
   for(const [id,layer] of markerLayers){
     if(validMarkerIds.has(id))continue;
     markers.removeLayer(layer);markerLayers.delete(id);
   }
   pruneSegments(trackLayers,validTracks);
   pruneSegments(coverageLayers,validCoverage);
   updateEarthViewportCount();
   const counts=layerCounts();
   $("map-overlay-count").textContent+=" | "+trackCount+" track segments, "+
     coverageCount+" coverage segments, "+counts.visible+" of "+counts.displayed+
     " plotted satellites above local horizon."+
     (clock.isLive?" · LIVE positions refresh every second.":" · Simulation paused.");
 }
 // A page-hosted public-domain Natural Earth outline is a real, usable map
 // background even when Brave Shields or network policy rejects OSM tiles.
 async function getWorldOutlineData(){
   if(worldData)return worldData;
   if(!worldPromise){
     worldPromise=(async()=>{
       let data;
       if(typeof window.nativeWorldOutline==='function'){
         data=await window.nativeWorldOutline();
       }else{
         const response=await fetch("./natural-earth-land-110m.geojson",{cache:"force-cache"});
         if(!response.ok)throw Error("Bundled Natural Earth outlines unavailable: HTTP "+response.status);
         data=await response.json();
       }
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
     minZoom:0,maxZoom:12,updateWhenIdle:true,keepBuffer:1,detectRetina:false,
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
       basemapStatus("OpenStreetMap image requests succeeded ("+tileSuccesses+
         " tile). This does NOT prove the images are visible. If the map looks blank, use Test map background for layer/render diagnostics.");
     } else if(tileSuccesses%8===0){
       basemapStatus("OpenStreetMap returned "+tileSuccesses+" tile images. Predicted satellite positions are not RF detections.");
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
   $("earth-street-details").open=true;
   setView("earth"); // Show container before Leaflet measures its dimensions.
   // Two animation frames let Chromium/Brave and Firefox lay out an expanded
   // <details> before Leaflet reads dimensions and calculates tile positions.
   await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
   earthMap=L.map("earth-map",{worldCopyJump:true,preferCanvas:false,minZoom:0}).setView([10,0],1);
   const worldPane=earthMap.createPane("world-outline");
   worldPane.style.zIndex="350"; // above raster tiles (200), below satellite overlays (400)
   // Explicit panes keep orbit tracks visible above raster tiles and world
   // outlines, while clickable satellite markers stay above coverage fills.
   for(const [name,z] of [["sat-coverage",380],["sat-tracks",420],["sat-markers",450],["sat-station",470]]){
     const pane=earthMap.createPane(name);pane.style.zIndex=String(z);
   }
   markers=L.layerGroup().addTo(earthMap);tracks=L.layerGroup().addTo(earthMap);
   earthMap.on("moveend zoomend",()=>updateEarthViewportCount());
   stationPin=L.circleMarker([o.lat,o.lon],{pane:"sat-station",radius:8,color:"#fff",weight:2,
      fillColor:"#27ddff",fillOpacity:0.9}).bindTooltip("Ground station (manual coordinates)").addTo(earthMap);
   setView("earth");
   earthMap.invalidateSize({pan:false,debounceMoveend:true});
   drawEarth();
   // Display the entire catalog on initial map entry, not an empty station-
   // centered viewport. If TLEs are loaded later, refresh() performs this fit.
   fitTrackedEarth();
   await changeBasemap(basemapChoice.value);
   status("Earth map initialized: orbit predictions only. Check the basemap status below for actual imagery load.");
  })();
  try{await loading;}finally{loading=null;}
 }
 async function refresh(){
  if(!mapStarted)return;
  const native=typeof window.nativeOrbitSnapshot==='function';
  if(native&&nativeSnapshotPending)return; // prevent overlapping 1 Hz native jobs
  const token=++run;
  let o;try{o=observer();}catch(e){status(e.message);return;}
  const catalog=getTles();
  if(!catalog.length){
   current=[];drawList();drawDetail();drawSky();drawEarth();
   status("No TLE catalog loaded. Click Refresh orbit data or import a local TLE file.");
   return;
  }
  const dt=mapDate(),rows=[];
  if(native){
   nativeSnapshotPending=true;
   try{
    const tracksDue=Date.now()-nativeTrackAt>=15000;
    const snapshot=await window.nativeOrbitSnapshot(o.lat,o.lon,dt.getTime(),tracksDue);
    if(token!==run)return;
    if(tracksDue){
     nativeTrackAt=Date.now();
     nativeTrackCache.clear();
     for(const [id,path] of Object.entries(snapshot.track_paths_by_norad||{})){
      if(Array.isArray(path))nativeTrackCache.set(String(id),path);
     }
    }
    const byId=new Map(catalog.map(record=>[String(record.id),record]));
    for(const sat of snapshot.satellites||[]){
     const item=byId.get(String(sat.norad));
     if(!item)continue; // never invent a satellite absent from loaded TLEs
     if(![sat.lat,sat.lon,sat.el,sat.az,sat.alt_km,sat.range_km].every(Number.isFinite))continue;
     rows.push({...item,lat:sat.lat,lon:sat.lon,el:sat.el,az:sat.az,
       altKm:sat.alt_km,rangeKm:sat.range_km,
       ageDays:sat.tle_age_days,
       nativeTrackCoordinates:nativeTrackCache.get(String(sat.norad))||[]});
    }
    if(!rows.length&&catalog.length){
     status("No native Skyfield positions matched the TLE cache. Refresh orbit data; imported browser-only TLEs may need a refreshed native catalog.");
    }
   }catch(e){
    status("Native orbit map unavailable: "+String(e?.message||e)+
      ". Verify downloaded TLEs and installed Skyfield; USB is not required.");
    return;
   }finally{nativeSnapshotPending=false;}
  }else{
   let lib;try{lib=await getSatLib();}
   catch(e){status("Orbital library unavailable: "+e.message);return;}
   if(token!==run)return;
   // Browser edition retains the same local JS orbital propagation.
   for(const item of catalog.slice(0,30)){
    try{
     const id=String(item.id);
     const saved=satrecMap.get(id);
     const rec=saved&&saved.l1===item.l1&&saved.l2===item.l2?
       saved.rec:lib.twoline2satrec(item.l1,item.l2);
     if(rec!==saved?.rec)satrecMap.set(id,{l1:item.l1,l2:item.l2,rec});
     const pos=propagate(lib,rec,dt,o.station);if(!pos)continue;
     const age=Number.isFinite(rec.jdsatepoch)?
       Math.abs(Date.now()-(rec.jdsatepoch-2440587.5)*86400000)/86400000:null;
     rows.push({...item,...pos,rec,lib,ageDays:age});
    }catch(e){/* malformed TLE, no invented satellite position */}
   }
  }
  current=rows;
  if(!rows.some(x=>String(x.id)===String(selectedId)))selectedId=rows[0]?.id??null;
  $("map-time-label").textContent=(clock.isLive?"LIVE / now":"SIMULATION / paused at")+
    " · "+fmtDate(dt)+" · "+dt.toLocaleTimeString();
  updateLiveControls();
  drawList();drawDetail();
  if(view==="sky")drawSky();else drawEarth();
  lastUpdate=Date.now();
  if(earthMap&&view==="earth"&&!initialCatalogFitDone&&rows.length)fitTrackedEarth();
  if(rows.length){
   status(rows.length+" TLE-derived satellites · "+
     rows.filter(s=>s.el>=0).length+" above local horizon"+
     (rows.some(s=>s.ageDays>7)?" · WARNING: stale orbital elements":"")+
     (native?" · Native Skyfield; no browser CDN":" · Browser orbital calculation")+
     " · No received satellite signals verified");
  }
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
 $("earth-street-details").addEventListener("toggle",()=>{
   if(!earthMap||!$("earth-street-details").open)return;
   // The optional map's dimensions change when a <details> element expands.
   // Leaflet does not always detect this itself, particularly in Brave.
   requestAnimationFrame(()=>requestAnimationFrame(()=>{
     if(!earthMap||!$("earth-street-details").open)return;
     earthMap.invalidateSize({pan:false,debounceMoveend:true});
     drawEarth();
   }));
 });
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
       // This test must NEVER switch layers or silently mutate the map.
       const size=earthMap.getSize();
       checks.push("Leaflet viewport: "+size.x+" × "+size.y+" px");
       checks.push("Selected base layer: "+basemapChoice.value);
       checks.push("OSM raster tile events: "+tileSuccesses+" loaded, "+tileFailures+" failed");
       const tileElements=[...document.querySelectorAll("#earth-map img.leaflet-tile")];
       checks.push("DOM raster images: "+tileElements.filter(img=>img.complete&&img.naturalWidth>0).length+
         " / "+tileElements.length+" received with nonzero image dimensions");
       checks.push("World-outline vector layer objects: "+(worldOutline?.getLayers().length||0));
       checks.push("Natural Earth SVG paths: "+document.querySelectorAll("#earth-map .leaflet-world-outline-pane svg path").length);
       checks.push("Satellite/ground marker layers: "+(markers?.getLayers().length||0)+
         " / "+(stationPin?1:0));
       const canvasOverlays=[...document.querySelectorAll("#earth-map .leaflet-pane canvas")];
       const opaque=canvasOverlays.filter(canvas=>{
         const style=getComputedStyle(canvas),color=style.backgroundColor;
         return color!=="transparent"&&color!=="rgba(0, 0, 0, 0)"&&color!=="rgba(0,0,0,0)"&&style.backgroundImage==="none";
       });
       checks.push("Leaflet opaque canvas overlays: "+opaque.length+" / "+canvasOverlays.length+
         (opaque.length?" — likely covering map images":" — no opaque map canvas"));
       if(!size.x||!size.y)checks.push("PROBLEM: Leaflet container has zero dimension; expand the street-map panel.");
     }else checks.push("Optional Leaflet street map not initialized; open the street section and Load / retry OpenStreetMap.");
   }catch(e){checks.push("Map error: "+e.message);}
   const report=checks.join("\n");
   basemapStatus(report);
   status(report); // visible even when optional Leaflet details are collapsed
   log("Map background diagnostic run; no USB activity.");
 });
 $("map-focus-selected").addEventListener("click",()=>{
   if(earthMap){focusSelectedEarth();return;}
   $("earth-street-details").open=true;
   void openEarth().then(()=>{drawEarth();focusSelectedEarth();})
     .catch(e=>status("Could not open map to focus satellite: "+e.message));
 });
 $("map-fit-all").addEventListener("click",()=>{
   if(earthMap){fitTrackedEarth();return;}
   $("earth-street-details").open=true;
   void openEarth().then(()=>{drawEarth();fitTrackedEarth();})
     .catch(e=>status("Could not open map to fit satellites: "+e.message));
 });
 $("map-follow-selected").addEventListener("change",()=>{
   if($("map-follow-selected").checked&&clock.isLive&&earthMap)focusSelectedEarth();
 });
 $("map-recenter").addEventListener("click",()=>{
  if(!earthMap)return;try{const o=observer();earthMap.setView([o.lat,o.lon],Math.max(3,earthMap.getZoom()));}catch(e){status(e.message);}
 });
 for(const id of ["map-family","map-above","map-band","map-sat-sort","map-track-scope","map-coverage-scope"]){
  $(id).addEventListener("change",()=>{drawList();drawDetail();drawSky();drawEarth();});
 }
 for(const id of ["city","lat","lon","elev"]){
  $(id).addEventListener("change",()=>{if(mapStarted)void refresh();});
 }
 $("preset").addEventListener("change",()=>{drawList();drawDetail();drawSky();drawEarth();});
 time.addEventListener("input",()=>{
   // Moving the slider freezes a specific simulated timestamp, rather than
   // silently continuing to advance its offset against wall-clock time.
   clock.seek(Number(time.value));updateLiveControls();void refresh();
 });
 $("map-pause").addEventListener("click",()=>{
   clock.pause();updateLiveControls();void refresh();
 });
 $("map-now").addEventListener("click",()=>{
   time.value="0";clock.resume();lastUpdate=0;
   updateLiveControls();void refresh();
 });
 $("map-reset-selection").addEventListener("click",()=>{
   selectedId=null;drawList();drawDetail();
   if(view==="sky")drawSky();else drawEarth();
 });
 const tick=setInterval(()=>{
   if(shouldRefreshLive({
     live:clock.isLive,visible:!document.hidden,
     started:mapStarted&&getTles().length>0,
     elapsedMs:Date.now()-lastUpdate
   }))void refresh();
 },LIVE_REFRESH_MS);
 const onVisibility=()=>{
   if(!document.hidden&&mapStarted&&clock.isLive){
     // Browser tabs throttle timers in the background; jump back to the
     // real wall clock immediately on return rather than catching up
     // old animation frames or keeping a resident receiver running.
     lastUpdate=0;void refresh();
   }
 };
 document.addEventListener("visibilitychange",onVisibility);
 window.addEventListener("pagehide",()=>{
  clearInterval(tick);
  document.removeEventListener("visibilitychange",onVisibility);
  clearTileDeadline();removeOsm();
  if(earthMap){earthMap.remove();earthMap=null;}
 });
 mapStarted=true;setView("sky");drawList();updateLiveControls();
 status("LIVE orbital geometry updates every second when TLEs are loaded and this tab is visible. USB reception remains opt-in.");
 return {refresh,choose};
}
