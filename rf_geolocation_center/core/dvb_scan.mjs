/* Safe DVBv5 channel-list parser. This is metadata imported from a native DVB scan,
 * not GPS, a unique transmitter identification, or live direct WebUSB tuning.
 */
const ALLOWED=new Set(["DVBT","DVBT2","DVBC/ANNEX_A","DVBC/ANNEX_B","DVBC/ANNEX_C","DVBC_ANNEX_A","DVBC_ANNEX_B","DVBC_ANNEX_C"]);
export function parseDvbV5Scan(input){
 if(typeof input!=="string"||input.length>1024*1024)throw Error("DVB scan file must be plain text no larger than 1 MiB");
 const blocks=[];let current=null;
 const push=()=>{
  if(!current)return;
  const f=Number(current.FREQUENCY);
  if(!Number.isFinite(f)||f<40000000||f>1200000000)return;
  const delivery=String(current.DELIVERY_SYSTEM||"UNKNOWN").toUpperCase();
  const value={name:current._NAME,frequencyHz:f,frequencyMHz:f/1000000,
   deliverySystem:delivery,
   serviceId:Number.isInteger(Number(current.SERVICE_ID))?Number(current.SERVICE_ID):null,
   networkId:Number.isInteger(Number(current.NETWORK_ID))?Number(current.NETWORK_ID):null,
   transportStreamId:Number.isInteger(Number(current.TRANSPORT_ID))?Number(current.TRANSPORT_ID):null,
   provenance:"IMPORTED DVBv5 NATIVE TUNER CHANNEL FILE · NO TRANSMITTER COORDINATES",
   method:"TV TUNER / DVB SERVICE METADATA · NOT GEOLOCATION",
   directBrowserScan:false,
   transmitterIdentified:false};
  if(!ALLOWED.has(delivery)&&delivery!=="UNKNOWN")value.note="Different delivery system; verify the scan source.";
  blocks.push(value);
 };
 for(const raw of input.split(/\r?\n/)){
  const line=raw.trim();
  if(!line||line.startsWith("#")||line.startsWith(";"))continue;
  if(line.startsWith("[")&&line.endsWith("]")){
   push();const name=line.slice(1,-1).trim();
   current=name?{_NAME:name.slice(0,120)}:null;
   continue;
  }
  if(!current)continue;
  const idx=line.indexOf("=");
  if(idx<1)continue;
  const key=line.slice(0,idx).trim().toUpperCase();
  const val=line.slice(idx+1).trim().slice(0,180);
  if(["FREQUENCY","DELIVERY_SYSTEM","SERVICE_ID","NETWORK_ID","TRANSPORT_ID"].includes(key))current[key]=val;
 }
 push();
 const unique=new Map();
 for(const s of blocks){
  if(!s.name||unique.size>=300)break;
  const key=s.name+"|"+s.frequencyHz+"|"+s.serviceId;
  if(!unique.has(key))unique.set(key,s);
 }
 return [...unique.values()];
}
