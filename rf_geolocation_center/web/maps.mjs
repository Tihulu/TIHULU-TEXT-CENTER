/* Offline coordinate Earth map + imported SP3 sky geometry.
 * OpenStreetMap tiles fetched ONLY after an explicit user click.
 */
import {DEG,DEFAULT_CENTER,visibleSatellites} from "../core/gnss.mjs";
const $=id=>document.getElementById(id),NS="http://www.w3.org/2000/svg";
const el=(tag,attrs,text)=>{
 const n=document.createElementNS(NS,tag);
 for(const [name,value] of Object.entries(attrs||{}))n.setAttribute(name,String(value));
 if(text!=null)n.textContent=String(text);
 return n;
};
const fmt=(n)=>Number.isFinite(n)?n.toFixed(5):"—";
const pj=(lat,lon,z)=>{
 const clamped=Math.max(-85.0511,Math.min(85.0511,lat))*DEG,n=256*Math.pow(2,z);
 return {x:(lon+180)/360*n,y:(1-Math.asinh(Math.tan(clamped))/Math.PI)/2*n};
};
export function createMaps(state){
 const map=$("earth-map"),canvas=$("earth-overlay");
 let drag=null;
 const sats=()=>state.orbit?visibleSatellites(state.orbit,state.epoch,
   state.position||{lat:DEFAULT_CENTER.lat,lon:DEFAULT_CENTER.lon,alt:0},state.mask):[];
 const renderTiles=()=>{
  const layer=$("osm-tiles");layer.replaceChildren();layer.hidden=!state.osm;
  if(!state.osm)return;
  const w=map.clientWidth,h=map.clientHeight,ctr=pj(state.center.lat,state.center.lon,state.zoom);
  const num=Math.pow(2,state.zoom);
  const minX=Math.floor((ctr.x-w/2)/256),maxX=Math.floor((ctr.x+w/2)/256);
  const minY=Math.floor((ctr.y-h/2)/256),maxY=Math.floor((ctr.y+h/2)/256);
  for(let x=minX;x<=maxX;x++)for(let y=minY;y<=maxY;y++){
   if(y<0||y>=num)continue;
   const tile=document.createElement("img");tile.alt="";tile.loading="lazy";
   tile.referrerPolicy="strict-origin-when-cross-origin";
   tile.src="https://tile.openstreetmap.org/"+state.zoom+"/"+((x%num+num)%num)+"/"+y+".png";
   tile.style.left=(x*256-ctr.x+w/2)+"px";tile.style.top=(y*256-ctr.y+h/2)+"px";
   layer.appendChild(tile);
  }
 };
 const renderEarth=()=>{
  const w=Math.max(1,map.clientWidth),h=Math.max(1,map.clientHeight);
  canvas.setAttribute("viewBox","0 0 "+w+" "+h);
  const grid=$("earth-grid"),markers=$("earth-markers");
  grid.replaceChildren();markers.replaceChildren();
  const center=pj(state.center.lat,state.center.lon,state.zoom),world=256*Math.pow(2,state.zoom);
  const point=(lat,lon)=>{
   const a=pj(lat,lon,state.zoom);let dx=a.x-center.x;
   if(dx>world/2)dx-=world;if(dx< -world/2)dx+=world;
   return {x:w/2+dx,y:h/2+a.y-center.y};
  };
  const add=(lat,lon,color,description,radius=6)=>{
   const p=point(lat,lon);
   if(p.x<0||p.x>w||p.y<0||p.y>h)return;
   const g=el("g");g.appendChild(el("circle",{cx:p.x,cy:p.y,r:radius,fill:color,
     stroke:"#0b1625","stroke-width":2}));g.appendChild(el("title",{},description));
   markers.appendChild(g);
  };
  for(let lon=-180;lon<=180;lon+=10){
   const p=point(state.center.lat,lon);if(p.x<0||p.x>w)continue;
   grid.appendChild(el("line",{x1:p.x,y1:0,x2:p.x,y2:h,stroke:"#51718b","stroke-opacity":".32"}));
  }
  for(let lat=-80;lat<=80;lat+=10){
   const p=point(lat,state.center.lon);if(p.y<0||p.y>h)continue;
   grid.appendChild(el("line",{x1:0,y1:p.y,x2:w,y2:p.y,stroke:"#51718b","stroke-opacity":".32"}));
  }
  if(state.position)add(state.position.lat,state.position.lon,"#6dedd2",
    "Authorized device location, "+state.position.provider,9);
  for(const p of state.references)add(p.lat,p.lon,p.type==="aircraft"?"#f4bf7d":"#adbded",
    "IMPORTED "+p.type+" reference: "+p.name);
  const sky=sats();
  for(const p of sky)add(p.lat,p.lon,"#f0de98","SP3 orbit geometry only: "+p.id,4);
  $("earth-sat-count").textContent=sky.length+" SP3 positions (PREDICTED, NOT RECEIVED)";
  $("earth-ref-count").textContent=state.references.length+" imported, not automatically verified";
  $("earth-center").textContent=fmt(state.center.lat)+", "+fmt(state.center.lon)+
    " / zoom "+state.zoom;
  $("earth-source").textContent=state.position?state.position.provider:
    "Cologne reference center; no actual user location";
  $("map-center-label").textContent=state.manualCenter?"USER SELECTED MAP CENTER":
   state.position?"DEVICE LOCATION CENTER":"COLOGNE REFERENCE · NOT YOUR LOCATION";
  renderTiles();
 };
 const renderSky=()=>{
  const plot=$("sky-plot");plot.replaceChildren();
  const cx=300,cy=300,r=248;
  plot.appendChild(el("circle",{cx,cy,r,fill:"#0c2031",stroke:"#5a8099","stroke-width":2}));
  for(const elevation of [0,30,60]){
   const rad=r*(90-elevation)/90;
   plot.appendChild(el("circle",{cx,cy,r:rad,fill:"none",stroke:"#36566a"}));
   plot.appendChild(el("text",{x:cx+8,y:cy-rad-5,fill:"#8ab1c2","font-size":12},elevation+"°"));
  }
  for(let a=0;a<360;a+=45){
   const ang=a*DEG;
   plot.appendChild(el("line",{x1:cx,y1:cy,x2:cx+Math.sin(ang)*r,
     y2:cy-Math.cos(ang)*r,stroke:"#254354"}));
  }
  for(const [i,t] of ["N","E","S","W"].entries()){
   const a=i*Math.PI/2;
   plot.appendChild(el("text",{x:cx+Math.sin(a)*(r+25),y:cy-Math.cos(a)*(r+25)+5,
    "text-anchor":"middle",fill:"#9ce4d4","font-size":18},t));
  }
  const list=$("sky-list");list.replaceChildren();
  if(!state.orbit){
   list.appendChild(document.createTextNode("Import authentic SP3 data to enable dated orbital geometry."));
   $("dash-visible").textContent="—";$("sky-timestamp").textContent="No orbital data";
   return;
  }
  const items=sats(),above=items.filter(x=>x.visible);
  $("dash-visible").textContent=String(above.length);
  $("sky-timestamp").textContent=new Date(state.epoch).toISOString()+
    " • PREDICTED, NOT ACQUIRED";
  for(const item of items){
   if(item.el>=0){
    const rad=r*(90-item.el)/90,a=item.az*DEG;
    const x=cx+Math.sin(a)*rad,y=cy-Math.cos(a)*rad;
    plot.appendChild(el("circle",{cx:x,cy:y,r:item.visible?7:4,
      fill:item.visible?"#78e8cf":"#959ca5",stroke:"#111b26","stroke-width":2}));
    plot.appendChild(el("text",{x:x+9,y:y-9,fill:"#f5fbff","font-size":13},item.id));
   }
   const info=document.createElement("div");info.className="list-item";
   const name=document.createElement("strong");
   name.textContent=item.id+" • "+item.system+" • "+(item.visible?"ABOVE MASK":"BELOW MASK");
   const detail=document.createElement("small");
   detail.textContent="AZ "+item.az.toFixed(1)+"° / EL "+item.el.toFixed(1)+
     "° / "+item.method+" / NO SIGNAL ACQUISITION";
   info.append(name,detail);list.appendChild(info);
  }
  if(!items.length)list.textContent="No satellite samples at this epoch. Extrapolation disabled.";
 };
 $("osm-load").addEventListener("click",()=>{
  state.osm=!state.osm;$("osm-load").textContent=state.osm?
   "Hide online OSM tiles":"Load OpenStreetMap online (opt-in)";
  renderEarth();
 });
 const zoom=delta=>{state.zoom=Math.max(2,Math.min(16,state.zoom+delta));renderEarth();};
 $("map-zoom-in").addEventListener("click",()=>zoom(1));
 $("map-zoom-out").addEventListener("click",()=>zoom(-1));
 $("earth-reset").addEventListener("click",()=>{
  state.manualCenter=false;
  state.center=state.position?{lat:state.position.lat,lon:state.position.lon}:
   {lat:DEFAULT_CENTER.lat,lon:DEFAULT_CENTER.lon};renderEarth();
 });
 map.addEventListener("pointerdown",e=>{
  drag={x:e.clientX,y:e.clientY,p:pj(state.center.lat,state.center.lon,state.zoom)};
  map.setPointerCapture(e.pointerId);
 });
 map.addEventListener("pointermove",e=>{
  if(!drag)return;
  const n=256*Math.pow(2,state.zoom);
  const x=(drag.p.x+drag.x-e.clientX+n)%n;
  const y=Math.max(.001,Math.min(n-.001,drag.p.y+drag.y-e.clientY));
  state.center={lon:x/n*360-180,
    lat:Math.atan(Math.sinh(Math.PI*(1-2*y/n)))/DEG};
  state.manualCenter=true;renderEarth();
 });
 map.addEventListener("pointerup",()=>{drag=null;});
 map.addEventListener("pointercancel",()=>{drag=null;});
 map.addEventListener("wheel",e=>{e.preventDefault();zoom(e.deltaY<0?1:-1);},{passive:false});
 $("sky-time").addEventListener("input",e=>{
  if(!state.orbit)return;
  state.epoch=state.orbit.first+
    (state.orbit.last-state.orbit.first)*Number(e.target.value)/1000;
  renderSky();renderEarth();
 });
 $("elevation-mask").addEventListener("input",e=>{
  state.mask=Number(e.target.value);$("mask-label").textContent=state.mask+"°";
  renderSky();renderEarth();
 });
 return {renderEarth,renderSky};
}
