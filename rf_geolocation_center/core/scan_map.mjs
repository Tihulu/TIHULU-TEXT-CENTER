/* Receiver observations joined to public reference coordinates.
 * Frequency overlap is only a CANDIDATE, not emitter identification or range.
 * Sources without explicit tagged frequency are never matched by proximity.
 */
export function matchedBroadcastSources(towers=[],fmReadings=[],dvbChannels=[]){
 const out=[],seen=new Set();
 if(!Array.isArray(towers)||!Array.isArray(fmReadings)||!Array.isArray(dvbChannels))return out;
 for(const site of towers.slice(0,250)){
  if(!Number.isFinite(site.lat)||!Number.isFinite(site.lon)||Math.abs(site.lat)>90||Math.abs(site.lon)>180)continue;
  for(const freq of (site.frequenciesMHz||[]).slice(0,20)){
   if(!Number.isFinite(freq))continue;
   const readings=fmReadings.filter(m=>Number.isFinite(m.frequencyMHz)&&Number.isFinite(m.levelDbFS)&&
       Math.abs(m.frequencyMHz-freq)<=.101);
   if(!readings.length)continue;
   const highest=readings.reduce((a,b)=>a.levelDbFS>=b.levelDbFS?a:b);
   const key=site.id+"|FM|"+freq.toFixed(3);
   if(seen.has(key))continue;seen.add(key);
   out.push({id:key,siteId:site.id,name:site.name||"Mapped FM site",lat:site.lat,lon:site.lon,
     kind:"fm",frequencyMHz:freq,signalLevelDbFS:highest.levelDbFS,measuredAt:highest.measuredAt||null,
     metadataOrigin:"ACTUAL RTL-SDR RF POWER + EXTERNAL OSM FM FREQUENCY TAG",
     match:"FREQUENCY OVERLAP ONLY · SIGNAL IDENTITY UNVERIFIED",distanceMeters:null,receiverPosition:false});
  }
  for(const freq of (site.televisionFrequenciesMHz||[]).slice(0,20)){
   if(!Number.isFinite(freq))continue;
   const channels=dvbChannels.filter(m=>Number.isFinite(m.frequencyMHz)&&Math.abs(m.frequencyMHz-freq)<=.011);
   if(!channels.length)continue;
   const key=site.id+"|TV|"+freq.toFixed(3);
   if(seen.has(key))continue;seen.add(key);
   out.push({id:key,siteId:site.id,name:site.name||"Mapped TV site",lat:site.lat,lon:site.lon,
     kind:"tv",frequencyMHz:freq,serviceNames:channels.slice(0,12).map(c=>c.name),
     metadataOrigin:"ACTUAL DVBv5 SERVICE SCAN + EXTERNAL OSM TV FREQUENCY TAG",
     match:"FREQUENCY OVERLAP ONLY · DVB-T2 SFN MAY HAVE MULTIPLE TRANSMITTERS",
     distanceMeters:null,receiverPosition:false});
  }
 }
 out.sort((a,b)=>a.kind===b.kind?a.frequencyMHz-b.frequencyMHz:a.kind==="tv"?-1:1);
 return out.slice(0,150);
}
export function mapBoundsForSources(items=[]){
 const valid=items.filter(x=>x&&Number.isFinite(x.lat)&&Number.isFinite(x.lon)&&Math.abs(x.lat)<=85&&Math.abs(x.lon)<=180);
 if(!valid.length)return null;
 const lats=valid.map(x=>x.lat),lons=valid.map(x=>x.lon);
 return {south:Math.min(...lats),north:Math.max(...lats),
   west:Math.min(...lons),east:Math.max(...lons),count:valid.length};
}
