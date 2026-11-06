/* TIHULU RF Geolocation Center — scientific geometry and SP3 orbit imports.
 * SP3 = real externally supplied precise orbit positions, NOT SDR reception.
 * No network calls, no extrapolation, no fake ephemerides or GNSS fix.
 */
export const WGS84_A=6378137.0, WGS84_F=1/298.257223563;
export const WGS84_E2=WGS84_F*(2-WGS84_F);
export const DEG=Math.PI/180;
export const DEFAULT_CENTER=Object.freeze({lat:50.93836,lon:6.95997,label:"Cologne reference (not your location)"});

export function validateLLA(lat,lon,alt=0){
 if(![lat,lon,alt].every(Number.isFinite)||lat < -90||lat>90||lon < -180||lon>180||Math.abs(alt)>1e7)throw Error("Invalid WGS84 coordinates");
 return {lat,lon,alt};
}
export function ecefFromLLA(lat,lon,alt=0){
 validateLLA(lat,lon,alt); const p=lat*DEG,l=lon*DEG,sl=Math.sin(p),cl=Math.cos(p);
 const N=WGS84_A/Math.sqrt(1-WGS84_E2*sl*sl);
 return [(N+alt)*cl*Math.cos(l),(N+alt)*cl*Math.sin(l),(N*(1-WGS84_E2)+alt)*sl];
}
export function llaFromECEF(x,y,z){
 if(![x,y,z].every(Number.isFinite)||Math.hypot(x,y,z)<1)throw Error("Invalid ECEF vector");
 const a=WGS84_A,e2=WGS84_E2,p=Math.hypot(x,y);
 const lon=Math.atan2(y,x),b=a*(1-WGS84_F),ep2=(a*a-b*b)/(b*b);
 const t=Math.atan2(z*a,p*b);
 const lat=Math.atan2(z+ep2*b*Math.sin(t)**3,p-e2*a*Math.cos(t)**3);
 const sl=Math.sin(lat),N=a/Math.sqrt(1-e2*sl*sl);
 const alt=Math.abs(Math.cos(lat))<1e-9?Math.abs(z)-b:p/Math.cos(lat)-N;
 if(!Number.isFinite(alt)||Math.abs(alt)>50_000_000)throw Error("Invalid ECEF-derived altitude");
 validateLLA(lat/DEG,lon/DEG,0); // Coordinate bounds; orbit altitude is not a ground-station altitude.
 return {lat:lat/DEG,lon:lon/DEG,alt};
}
export function azElRange(targetECEF,observerLLA){
 const {lat,lon,alt=0}=observerLLA;
 const o=ecefFromLLA(lat,lon,alt),d=targetECEF.map((v,i)=>v-o[i]);
 if(d.length!==3||!d.every(Number.isFinite))throw Error("Invalid target ECEF");
 const p=lat*DEG,l=lon*DEG,sp=Math.sin(p),cp=Math.cos(p),sl=Math.sin(l),cl=Math.cos(l);
 const east=-sl*d[0]+cl*d[1];
 const north=-sp*cl*d[0]-sp*sl*d[1]+cp*d[2];
 const up=cp*cl*d[0]+cp*sl*d[1]+sp*d[2];
 const range=Math.hypot(east,north,up);
 if(range<1)throw Error("Target coincides with receiver");
 return {az:(Math.atan2(east,north)/DEG+360)%360,
         el:Math.atan2(up,Math.hypot(east,north))/DEG,rangeMeters:range};
}
export const GNSS=[
 {id:"G",system:"GPS",operator:"United States",type:"global",signals:[["L1 C/A",1575.42],["L2",1227.60],["L5",1176.45]]},
 {id:"E",system:"Galileo",operator:"European Union",type:"global",signals:[["E1",1575.42],["E5a",1176.45],["E5b",1207.14],["E6",1278.75]]},
 {id:"R",system:"GLONASS",operator:"Russia",type:"global",signals:[["G1 FDMA (channel-dependent)",null],["G2 FDMA (channel-dependent)",null],["G3",1202.025]]},
 {id:"C",system:"BeiDou BDS",operator:"China",type:"global",signals:[["B1C",1575.42],["B1I",1561.098],["B2a",1176.45],["B2b",1207.14],["B3I",1268.52]]},
 {id:"J",system:"QZSS",operator:"Japan",type:"regional",signals:[["L1",1575.42],["L2",1227.60],["L5",1176.45],["L6",1278.75]]},
 {id:"I",system:"NavIC / IRNSS",operator:"India",type:"regional",signals:[["L1 (newer satellites)",1575.42],["L5",1176.45],["S",2498.028]]},
 {id:"S",system:"SBAS (EGNOS, WAAS, MSAS, GAGAN, KASS and other services)",operator:"Regional augmentation providers",type:"augmentation",signals:[["L1",1575.42],["L5",1176.45]]}
];
export const constellationFor=id=>GNSS.find(g=>g.id===String(id)[0])||null;
export function rtlSignalClass(mhz){
 if(mhz==null)return "Channel-dependent; verify receiver and frontend";
 if(mhz < .1||mhz>1750)return "Outside approximate tuner range";
 return "Frequency in nominal tuner range; GNSS antenna, LNA, clock, decoder and tracking NOT verified";
}
export function parseSP3(text){
 if(typeof text!=="string"||text.length>5_000_000)throw Error("SP3 input must be text, max 5 MB");
 const data=new Map(); let epoch=null,epochs=0;
 for(const line of text.split(/\r?\n/)){
   if(line.startsWith("* ")){
     const m=line.match(/^\*\s+(\d{4})\s+(\d{1,2})\s+(\d{1,2})\s+(\d{1,2})\s+(\d{1,2})\s+([\d.]+)/);
     if(!m)throw Error("Malformed SP3 epoch");
     const [y,mo,d,h,mi,sec]=m.slice(1).map(Number);
     if(y<1980||y>2200||mo<1||mo>12||d<1||d>31||h>23||mi>59||sec>=60)throw Error("Invalid SP3 UTC epoch");
     epoch=Date.UTC(y,mo-1,d,h,mi,Math.floor(sec),Math.round((sec%1)*1000));
     const dt=new Date(epoch);
     if(dt.getUTCFullYear()!==y||dt.getUTCMonth()!==mo-1||dt.getUTCDate()!==d)throw Error("Invalid SP3 calendar date");
     if(++epochs>2048)throw Error("SP3 too many epochs");
   }else if(line.startsWith("P")&&epoch!==null){
     const m=line.match(/^P([GRECJIS]\d{2})\s+([-+]?[\d.]+)\s+([-+]?[\d.]+)\s+([-+]?[\d.]+)/);
     if(!m)continue;
     const xyz=m.slice(2).map(Number);
     if(xyz.some(v=>!Number.isFinite(v)||Math.abs(v)>99999)||xyz.every(v=>v===0))continue;
     if(Math.hypot(...xyz)<15000||Math.hypot(...xyz)>50000)continue; // km orbital bounds for GNSS
     if(!data.has(m[1]))data.set(m[1],[]);
     data.get(m[1]).push({t:epoch,xyz:xyz.map(v=>v*1000)});
     if(data.size>160)throw Error("SP3 satellite limit exceeded");
   }
 }
 if(!epochs||!data.size)throw Error("No valid orbital positions in SP3 input");
 for(const [id,rows] of data) data.set(id,rows.sort((a,b)=>a.t-b.t)
     .filter((r,i,arr)=>i===0||r.t!==arr[i-1].t));
 const times=[...data.values()].flatMap(x=>x.map(r=>r.t));
 return {source:"User-imported SP3 orbital file",type:"precise_orbit_samples",data,
   first:Math.min(...times),last:Math.max(...times),satelliteCount:data.size,
   warning:"Orbit geometry only, NOT received GNSS or navigation clock corrections."};
}
export function positionAt(rows,t){
 if(!Array.isArray(rows)||!Number.isFinite(t)||rows.length<2)return null;
 if(t<rows[0].t||t>rows.at(-1).t)return null; // never extrapolate
 let i=rows.findIndex(r=>r.t>=t);
 if(i===-1)return null;
 if(rows[i].t===t)return {xyz:rows[i].xyz,method:"SP3 EPOCH SAMPLE"};
 const start=Math.max(0,Math.min(i-2,rows.length-4)),slice=rows.slice(start,start+4);
 const use=slice.length>=4?slice:rows.slice(Math.max(0,i-1),i+1);
 if(use.length<2)return null;
 if(use.some((r,j)=>j>0&&(r.t-use[j-1].t>1_800_000||r.t<=use[j-1].t)))return null;
 const xyz=[0,1,2].map(axis=>{
   let sum=0;
   for(let j=0;j<use.length;j++){
     let weight=1;
     for(let k=0;k<use.length;k++)if(k!==j)weight*=(t-use[k].t)/(use[j].t-use[k].t);
     sum+=weight*use[j].xyz[axis];
   }
   return sum;
 });
 return {xyz,method:use.length>=4?"SP3 INTERPOLATED (CUBIC)":"SP3 INTERPOLATED (LOW-ORDER)"};
}
export function visibleSatellites(sp3,atMs,observer,elevationMask=5){
 if(!sp3?.data||!Number.isFinite(atMs)||!observer)return [];
 return [...sp3.data.entries()].map(([id,series])=>{
   const pos=positionAt(series,atMs);
   if(!pos)return null;
   const sky=azElRange(pos.xyz,observer);
   const geo=llaFromECEF(...pos.xyz);
   return {id,system:constellationFor(id)?.system||"Other",...sky,
     lat:geo.lat,lon:geo.lon,visible:sky.el>=elevationMask,
     state:"PREDICTED ORBIT GEOMETRY",method:pos.method,
     observedRF:false,usedInFix:false,cnoDbHz:null};
 }).filter(Boolean).sort((a,b)=>b.el-a.el);
}
