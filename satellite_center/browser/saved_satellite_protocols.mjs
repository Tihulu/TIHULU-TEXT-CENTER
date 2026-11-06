/* Receive-only user profile storage.
 * User-supplied catalog entries are always UNVERIFIED and NEVER activate
 * a decoder or silently add unattended SDR jobs.
 */
export const PROFILE_KEY="tihulu-satellite-user-downlinks-v1";
const LIMIT=32;
const kinds=new Set(["image","audio","text","video"]);

export function parseUserProtocol(record){
 if(!record||typeof record!=="object")throw Error("Satellite protocol must be an object");
 const norad=Number(record.norad),frequencyHz=Number(record.frequencyHz);
 if(!Number.isSafeInteger(norad)||norad<1000||norad>9999999)
   throw Error("NORAD catalog number must be 1000–9999999");
 if(!Number.isInteger(frequencyHz)||frequencyHz<24000000||frequencyHz>1750000000)
   throw Error("Frequency must be supported by RTL-SDR: 24–1750 MHz");
 if(!kinds.has(record.kind))throw Error("Choose image, audio, text or video");
 const protocol=String(record.protocol||"").trim().slice(0,64);
 if(!protocol||/[<>\u0000-\u001f]/.test(protocol))throw Error("Enter a simple, non-HTML protocol name");
 const rawSource=String(record.source||"").trim();
 let source="https://db.satnogs.org/";
 if(rawSource){
   let parsed;
   try{parsed=new URL(rawSource);}catch{throw Error("Source must be a valid HTTPS address");}
   if(parsed.protocol!=="https:"||parsed.username||parsed.password)throw Error("Source URL must use HTTPS without credentials");
   source=parsed.href.slice(0,300);
 }
 const id="user-"+norad+"-"+frequencyHz+"-"+record.kind;
 return {id,norad,kind:record.kind,label:record.kind.toUpperCase()+" · USER",
   protocol,frequencyHz,source,activity:"user-supplied-not-verified",
   decoder:"no-decoder-connected",station:"NORAD "+norad,
   note:"Manually added frequency/mode: NOT independently verified; no automatic decoder or capture enabled.",
   provenance:"user-supplied"};
}
export function validateUserProfiles(records){
 if(!Array.isArray(records)||records.length>LIMIT)throw Error("Import must contain at most "+LIMIT+" satellite profiles");
 const unique=new Map();
 for(const r of records){
   const p=parseUserProtocol(r);
   unique.set(p.id,p);
 }
 return [...unique.values()];
}
export function readUserProfiles(storage=typeof localStorage==="undefined"?null:localStorage){
 if(!storage)return [];
 try{
   const raw=storage.getItem(PROFILE_KEY);
   if(!raw)return [];
   if(raw.length>40000)return [];
   return validateUserProfiles(JSON.parse(raw));
 }catch{return [];}
}
export function saveUserProfiles(records,storage=typeof localStorage==="undefined"?null:localStorage){
 if(!storage)throw Error("Local profile storage unavailable in this browser");
 const data=validateUserProfiles(records);
 storage.setItem(PROFILE_KEY,JSON.stringify(data));
 return data;
}
