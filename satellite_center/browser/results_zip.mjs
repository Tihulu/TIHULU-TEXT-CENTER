/* Streaming-memory ZIP32 archive for real local decoded results.
 * Stored (uncompressed): avoids external CDNs, network uploads and false
 * "verified" claims. Raw multi-gigabyte CU8 recordings are not bundled.
 */
const encoder=new TextEncoder();
const table=new Uint32Array(256);
for(let i=0;i<256;i++){
 let c=i;for(let k=0;k<8;k++)c=c&1?0xedb88320^(c>>>1):c>>>1;
 table[i]=c>>>0;
}
const MAX_RESULTS_BYTES=256*1024*1024;
export function zipEntryName(value){
 const original=String(value||"");
 if(!original||original.startsWith("/")||original.includes("\\")||
    original.split("/").some(p=>p===".."||p==="."||!p)||/^[A-Za-z]:/.test(original))
   throw Error("Unsafe archive entry path");
 const name=original.replace(/[^a-zA-Z0-9._/-]/g,"_");
 if(name.length>180||name.startsWith("."))throw Error("Invalid archive name");
 return name;
}
const u16=(view,at,value)=>view.setUint16(at,value,true);
const u32=(view,at,value)=>view.setUint32(at,value>>>0,true);
function dosDate(date){
 const t=date instanceof Date?date:new Date(date);
 if(!Number.isFinite(t.getTime()))throw Error("Invalid archive timestamp");
 const year=Math.min(2107,Math.max(1980,t.getFullYear()));
 return {time:(t.getHours()<<11)|(t.getMinutes()<<5)|Math.floor(t.getSeconds()/2),
   date:((year-1980)<<9)|((t.getMonth()+1)<<5)|t.getDate()};
}
function crcStep(crc,bytes){
 let c=crc;for(const byte of bytes)c=(c>>>8)^table[(c^byte)&255];
 return c>>>0;
}
export async function createResultsZip(entries,{maxBytes=MAX_RESULTS_BYTES,onProgress=()=>{},signal=null}={}){
 if(!Array.isArray(entries)||!entries.length||entries.length>200)
   throw Error("ZIP needs 1–200 actual output files");
 if(!Number.isSafeInteger(maxBytes)||maxBytes<=0||maxBytes>0xffffffff)
   throw Error("Invalid bounded ZIP limit");
 const names=new Set(),sources=[];
 let total=0;
 for(const item of entries){
  const name=zipEntryName(item?.name);
  if(names.has(name))throw Error("Duplicate ZIP path: "+name);
  names.add(name);
  const blob=item?.blob instanceof Blob?item.blob:new Blob([item?.data??""],{type:"application/octet-stream"});
  if(blob.size>0xffffffff)throw Error("ZIP32 does not support files >4 GiB");
  total+=blob.size;
  if(total>maxBytes)throw Error("Analyzed outputs exceed the "+Math.floor(maxBytes/1048576)+" MiB ZIP safety limit; export large recordings separately");
  sources.push({name,blob});
 }
 const files=[],central=[];
 const clock=dosDate(new Date());
 let position=0;
 for(let i=0;i<sources.length;i++){
  if(signal?.aborted)throw Error("ZIP creation cancelled");
  const {name,blob}=sources[i],bytes=encoder.encode(name);
  if(bytes.length>65535)throw Error("ZIP entry name too long");
  let crc=0xffffffff;
  for(let off=0;off<blob.size;off+=1048576){
   if(signal?.aborted)throw Error("ZIP creation cancelled");
   const chunk=new Uint8Array(await blob.slice(off,off+1048576).arrayBuffer());
   crc=crcStep(crc,chunk);
  }
  crc=(crc^0xffffffff)>>>0;
  const local=new Uint8Array(30+bytes.length),v=new DataView(local.buffer);
  u32(v,0,0x04034b50);u16(v,4,20);u16(v,6,0x0800);u16(v,8,0);
  u16(v,10,clock.time);u16(v,12,clock.date);u32(v,14,crc);
  u32(v,18,blob.size);u32(v,22,blob.size);u16(v,26,bytes.length);
  u16(v,28,0);local.set(bytes,30);
  files.push(local,blob);
  const c=new Uint8Array(46+bytes.length),w=new DataView(c.buffer);
  u32(w,0,0x02014b50);u16(w,4,20);u16(w,6,20);u16(w,8,0x0800);
  u16(w,10,0);u16(w,12,clock.time);u16(w,14,clock.date);
  u32(w,16,crc);u32(w,20,blob.size);u32(w,24,blob.size);
  u16(w,28,bytes.length);u16(w,30,0);u16(w,32,0);u16(w,34,0);
  u16(w,36,0);u32(w,38,0);u32(w,42,position);c.set(bytes,46);
  central.push(c);
  position+=local.length+blob.size;
  onProgress({done:i+1,total:sources.length,bytes:total});
 }
 const directory=central.reduce((sum,c)=>sum+c.length,0);
 if(position+directory+22>0xffffffff)throw Error("ZIP32 offsets exceeded");
 const footer=new Uint8Array(22),e=new DataView(footer.buffer);
 u32(e,0,0x06054b50);u16(e,4,0);u16(e,6,0);u16(e,8,sources.length);
 u16(e,10,sources.length);u32(e,12,directory);u32(e,16,position);u16(e,20,0);
 return new Blob([...files,...central,footer],{type:"application/zip"});
}
