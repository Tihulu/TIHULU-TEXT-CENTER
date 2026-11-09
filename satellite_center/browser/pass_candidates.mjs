/* RF-independent, local-only planning candidates for predicted satellite passes.
 * NEVER creates an armed capture or claims the SDR. This is a calendar note,
 * not an RF execution scheduler. The satellite's TLE provenance stays explicit.
 */
export const CANDIDATE_STORAGE_KEY="tihulu-satellite-pass-planning-v1";
const LIMIT=180;
let sessionFallback=[];
function safeStorage(){
 try{return globalThis.localStorage??null;}catch{return null;}
}
function cleanName(value){return String(value||"Satellite").slice(0,96);}
function validEpoch(value){return Number.isFinite(value)&&value>1000000000000;}
export function candidateFromPass(pass,{observer=null,now=Date.now()}={}){
 const aos=Number(pass?.aos),los=Number(pass?.los);
 const norad=Number(pass?.id??pass?.norad);
 if(!Number.isInteger(norad)||norad<=0||!validEpoch(aos)||!validEpoch(los)||
    los<=aos||los<now-60000)throw Error("Select a real current or future TLE-predicted pass.");
 const lat=Number(observer?.lat),lon=Number(observer?.lon);
 const groundStation=Number.isFinite(lat)&&lat>=-90&&lat<=90&&
   Number.isFinite(lon)&&lon>=-180&&lon<=180?{lat,lon}:null;
 return {id:norad+"_"+Math.round(aos/1000),norad,name:cleanName(pass.name),
  family:String(pass.family||"unknown").slice(0,30),
  aos,los,maximum:Number.isFinite(Number(pass.maximum))?Number(pass.maximum):null,
  observer:groundStation,status:"planning-only",radioArmed:false,
  actualRecording:false,createdAt:now,
  note:"Orbital calendar candidate only. No SDR required; NO RF receiver scheduled."};
}
export function readPlanningCandidates(storage=undefined){
 const store=storage===undefined?safeStorage():storage;
 if(!store)return sessionFallback.slice();
 try{
  const parsed=JSON.parse(store.getItem(CANDIDATE_STORAGE_KEY)||"[]");
  if(!Array.isArray(parsed))return [];
  return parsed.filter(x=>x&&x.status==="planning-only"&&x.radioArmed===false&&
    validEpoch(x.aos)&&validEpoch(x.los)&&x.los>x.aos&&x.id&&x.norad)
    .slice(-LIMIT).sort((a,b)=>a.aos-b.aos);
 }catch{return sessionFallback.slice();}
}
export function savePlanningCandidate(entry,storage=undefined){
 if(!entry||entry.status!=="planning-only"||entry.radioArmed!==false)
  throw Error("Planning entries cannot arm a receiver.");
 const store=storage===undefined?safeStorage():storage;
 const rows=readPlanningCandidates(store).filter(x=>x.id!==entry.id);
 rows.push(entry);rows.sort((a,b)=>a.aos-b.aos);
 const next=rows.slice(-LIMIT);
 sessionFallback=next.slice();
 if(store)try{store.setItem(CANDIDATE_STORAGE_KEY,JSON.stringify(next));}
 catch{/* Restricted storage: caller still has an in-memory candidate. */}
 return next;
}
export function removePlanningCandidate(id,storage=undefined){
 const store=storage===undefined?safeStorage():storage;
 const rows=readPlanningCandidates(store).filter(x=>x.id!==id);
 sessionFallback=rows.slice();
 if(store)try{store.setItem(CANDIDATE_STORAGE_KEY,JSON.stringify(rows));}catch{}
 return rows;
}
