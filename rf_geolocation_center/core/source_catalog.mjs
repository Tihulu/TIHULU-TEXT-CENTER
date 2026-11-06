/* Public RF source catalogs. Coordinates are only REF DATA and are never receiver fixes.
 * OpenStreetMap masts may not encode channel frequency. OpenSky is internet aircraft,
 * NOT proof of ADS-B reception by the user's SDR.
 */
const R=6371008.8,D=Math.PI/180;
export function distanceMeters(a,b){
 if(!a||!b||![a.lat,a.lon,b.lat,b.lon].every(Number.isFinite))throw Error("Missing coordinates");
 const dlat=(a.lat-b.lat)*D,dlon=(a.lon-b.lon)*D;
 const h=Math.sin(dlat/2)**2+Math.cos(a.lat*D)*Math.cos(b.lat*D)*Math.sin(dlon/2)**2;
 return 2*R*Math.asin(Math.min(1,Math.sqrt(h)));
}
export function fmFrequencies(tags={}){
 // Explicit tagged RF transmitter frequencies ONLY. Missing frequencies remain UNKNOWN.
 const val=Object.entries(tags).filter(([k])=>/^(?:frequency(?::.*)?|broadcast:frequency|fm:frequency)$/.test(k))
   .map(([,v])=>String(v)).join(";");
 const matches=[...val.replace(/,/g,".").matchAll(/(?:^|[\s;|/])(\d{2,4}(?:\.\d{1,4})?)\s*(MHz|kHz)?(?=$|[\s;|/])/gi)];
 const frequencies=[];
 for(const m of matches){
   let f=Number(m[1]);if(m[2]?.toLowerCase()==="khz")f/=1000;
   if(Number.isFinite(f)&&f>=87.5&&f<=108&&!frequencies.some(x=>Math.abs(x-f)<.001))
     frequencies.push(Math.round(f*10000)/10000);
 }
 return frequencies.slice(0,12);
}
export function televisionFrequencies(tags={}){
 // Only directly reported frequency values explicitly tagged in MHz.
 // Regional TV channel numbers (e.g. "K26") are NOT automatically converted to MHz.
 const raw=Object.entries(tags).filter(([k])=>/^(?:frequency(?::.*)?|broadcast:frequency|television:frequency)$/.test(k))
  .map(([,v])=>String(v)).join(";");
 const out=[];
 for(const match of raw.replace(/,/g,".").matchAll(/(?:^|[^0-9])(\d{2,4}(?:\.\d{1,4})?)\s*MHz\b/gi)){
  const mhz=Number(match[1]);
  if(Number.isFinite(mhz)&&mhz>=47&&mhz<=900&&!out.some(v=>Math.abs(v-mhz)<.001))
   out.push(Math.round(mhz*1000)/1000);
 }
 return out.slice(0,12);
}
export function normalizeRadioTowers(response,reference,max=150){
 if(!Array.isArray(response?.elements)||!Number.isFinite(reference?.lat)||!Number.isFinite(reference?.lon))
   throw Error("Invalid OSM Overpass radio tower response");
 const out=[],used=new Set();
 for(const el of response.elements.slice(0,3000)){
   const lat=Number(el.lat??el.center?.lat),lon=Number(el.lon??el.center?.lon);
   if(!Number.isFinite(lat)||!Number.isFinite(lon)||Math.abs(lat)>90||Math.abs(lon)>180)continue;
   const tags=el.tags||{};
   // Only explicitly radio-tagged objects. Generic mobile masts are not FM transmitters.
   const radio=tags["communication:radio"]==="yes"||tags.broadcasting==="radio"||tags["broadcasting:radio"]==="yes";
   const television=tags["communication:television"]==="yes"||tags.broadcasting==="television"||tags["broadcasting:television"]==="yes";
   if(!radio&&!television)continue;
   const id=String(el.type)+"/"+String(el.id);
   if(used.has(id))continue;used.add(id);
   const name=String(tags.name||tags.operator||tags.ref||"Radio mast "+id).slice(0,100);
   let dist;try{dist=distanceMeters(reference,{lat,lon})}catch{continue}
   out.push({id:"osm-"+id,name,type:"station",lat,lon,frequencyMHz:fmFrequencies(tags)[0]??null,
    frequenciesMHz:fmFrequencies(tags),televisionFrequenciesMHz:television?televisionFrequencies(tags):[],
    broadcastType:radio&&television?"radio+television":television?"television":"radio",tvChannelTag:tags.channel||null,
    distanceFromSearchCenterMeters:Math.round(dist),
    catalog:"OpenStreetMap/Overpass",catalogUrl:"https://www.openstreetmap.org/"+id,
    metadataOrigin:"PUBLIC OSM MAPPING",hardwareReceived:false,transmitterIdentityVerified:false,
    confidence:"SITE CANDIDATE / NOT LINKED TO RF SIGNAL",operator:tags.operator||null});
 }
 out.sort((a,b)=>a.distanceFromSearchCenterMeters-b.distanceFromSearchCenterMeters);
 return out.slice(0,Math.max(1,Math.min(250,max)));
}
export function normalizeOpenSkyStates(json,nowMs=Date.now()){
 if(!Array.isArray(json?.states))throw Error("Invalid OpenSky aircraft response");
 const out=[],unique=new Set();
 for(const v of json.states.slice(0,500)){
   if(!Array.isArray(v)||v.length<17)continue;
   const icao=String(v[0]||"").trim().toLowerCase();
   const lon=v[5],lat=v[6],time=Number(v[4]||v[3]||0)*1000;
   if(!/^[0-9a-f]{6}$/.test(icao)||unique.has(icao)||!Number.isFinite(lat)||!Number.isFinite(lon)||
      Math.abs(lat)>90||Math.abs(lon)>180||!Number.isFinite(time)||nowMs-time>120000||time-nowMs>30000)continue;
   unique.add(icao);
   out.push({id:"opensky-"+icao,icao, callsign:String(v[1]||icao).trim().slice(0,25),type:"aircraft",
    lat,lon,altitudeMeters:Number.isFinite(v[13])?v[13]:Number.isFinite(v[7])?v[7]:null,
    observedAt:new Date(time).toISOString(),frequencyMHz:1090,catalog:"OpenSky Network",
    metadataOrigin:"INTERNET / EXTERNAL ADS-B NETWORK",hardwareReceived:false,
    transmitterIdentityVerified:false,
    confidence:"AIRCRAFT POSITION REFERENCE ONLY / NOT A RECEIVER FIX"});
 }
 return out;
}
export function matchFMScanToCatalog(readings,candidates){
 const result=[];
 if(!Array.isArray(readings)||!Array.isArray(candidates))return result;
 for(const r of readings){
  if(!Number.isFinite(r.frequencyMHz)||!Number.isFinite(r.levelDbFS))continue;
  const matched=candidates.filter(c=>c.frequenciesMHz?.some(f=>Math.abs(f-r.frequencyMHz)<.015))
    .slice(0,12);
  result.push({...r,candidateIds:matched.map(c=>c.id),candidateNames:matched.map(c=>c.name),
   matchQuality:matched.length?"FREQUENCY OVERLAP ONLY · IDENTITY NOT DECODED":"RF LEVEL ONLY · UNKNOWN EMITTER"});
 }
 return result;
}
