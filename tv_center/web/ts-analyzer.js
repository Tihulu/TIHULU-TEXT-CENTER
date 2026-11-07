/* MPEG-TS (188-byte) analyzer for WebUSB and local transport recordings.
 * Does not tune DVB hardware, synthesize stations, or decode HEVC video.
 * Parse *real* PAT/PMT with MPEG-2 CRC before reporting a program.
 */
export const TS_SIZE = 188;
export function crc32Mpeg(input) {
  let c=0xffffffff;
  for(const byte of input){
    c^=byte<<24;
    for(let bit=0;bit<8;bit++) c=((c<<1)^(c&0x80000000?0x04c11db7:0))>>>0;
  }
  return c>>>0;
}
export function sectionWithCRC(input) {
  const data = Uint8Array.from(input);
  const crc=crc32Mpeg(data);
  return Uint8Array.from([...data,(crc>>>24)&255,(crc>>>16)&255,(crc>>>8)&255,crc&255]);
}
export class TransportAnalyzer {
  constructor(){
    this.packetCount=0;this.syncErrors=0;this.continuityErrors=0;
    this.crcErrors=0;this.validSections=0;this.teiErrors=0;
    this.bytes=0;this.programs=new Map();this.pmts=new Map();
    this.continuity=new Map();this.sections=new Map();this.packetTypes=new Map();
    this.pending=new Uint8Array(0);
  }
  feed(chunk){
    if(!(chunk instanceof Uint8Array))throw TypeError("Expected Uint8Array MPEG-TS data");
    if(chunk.byteLength>1024*1024)throw RangeError("Use chunks of at most 1 MiB");
    this.bytes+=chunk.byteLength;
    const incoming=new Uint8Array(this.pending.length+chunk.length);
    incoming.set(this.pending,0);incoming.set(chunk,this.pending.length);
    let offset=0;
    while(offset+TS_SIZE<=incoming.length){
      if(incoming[offset]!==0x47 ||
         (offset+TS_SIZE*2<=incoming.length&&incoming[offset+TS_SIZE]!==0x47)){
        offset++;this.syncErrors++;continue;
      }
      this.packet(incoming.subarray(offset,offset+TS_SIZE));
      offset+=TS_SIZE;
    }
    // Bounded resync buffer; never hold unbounded USB data in the browser.
    this.pending=incoming.slice(offset);
    if(this.pending.length>TS_SIZE*2)
      this.pending=this.pending.slice(-TS_SIZE*2);
    return this.summary();
  }
  packet(p){
    this.packetCount++;
    const tei=(p[1]&0x80)!==0,pusi=(p[1]&0x40)!==0;
    const pid=((p[1]&31)<<8)|p[2],afc=(p[3]>>4)&3,cc=p[3]&15;
    this.packetTypes.set(pid,(this.packetTypes.get(pid)||0)+1);
    if(tei){this.teiErrors++;return;}
    if(afc===0)return;
    let pos=4;
    if(afc&2){
      const adaptation=p[pos];
      if(adaptation>183)return;
      pos+=1+adaptation;
    }
    if(!(afc&1)||pos>=188)return;
    const previous=this.continuity.get(pid);
    if(previous!==undefined&&cc!==((previous+1)&15)&&pid!==8191){
      if(cc!==previous)this.continuityErrors++;
      this.sections.delete(pid);
    }
    this.continuity.set(pid,cc);
    const relevant=pid===0||pid===0x11||[...this.programs.values()].includes(pid);
    if(!relevant)return;
    if(pusi){
      const pointer=p[pos++];
      if(pos+pointer>188){this.sections.delete(pid);return;}
      if(pointer&&this.sections.has(pid)){
        this.append(pid,p.subarray(pos,pos+pointer));
      }
      this.sections.set(pid,new Uint8Array(0));
      pos+=pointer;
    }
    if(!this.sections.has(pid))return;
    this.append(pid,p.subarray(pos));
  }
  append(pid,payload){
    let prior=this.sections.get(pid)||new Uint8Array(0);
    const buf=new Uint8Array(prior.length+payload.length);
    buf.set(prior);buf.set(payload,prior.length);
    let at=0;
    while(buf.length-at>=3){
      if(buf[at]===0xff){at=buf.length;break;}
      const length=((buf[at+1]&15)<<8)|buf[at+2];
      if(length<4||length>1021){at=buf.length;break;}
      const end=at+3+length;
      if(end>buf.length)break;
      this.parseSection(pid,buf.subarray(at,end));
      at=end;
    }
    const remain=buf.slice(at);
    this.sections.set(pid,remain.length<1024?remain:new Uint8Array(0));
  }
  parseSection(pid,sec){
    if(crc32Mpeg(sec)!==0){this.crcErrors++;return;}
    const table=sec[0];
    if(pid===0&&table===0x00){
      if(sec.length<12)return;
      const next=new Map();
      for(let at=8;at+4<=sec.length-4;at+=4){
        const service=(sec[at]<<8)|sec[at+1];
        const pmt=((sec[at+2]&31)<<8)|sec[at+3];
        if(service)next.set(service,pmt);
      }
      this.programs=next;this.validSections++;
    }else if(table===0x02 && [...this.programs.values()].includes(pid)){
      if(sec.length<16)return;
      const service=(sec[3]<<8)|sec[4];
      if(this.programs.get(service)!==pid)return;
      const pcr=((sec[8]&31)<<8)|sec[9];
      let at=12+(((sec[10]&15)<<8)|sec[11]);
      const streams=[];
      while(at+5<=sec.length-4){
        const type=sec[at],streamPid=((sec[at+1]&31)<<8)|sec[at+2];
        const descriptors=((sec[at+3]&15)<<8)|sec[at+4];
        if(at+5+descriptors>sec.length-4)return;
        streams.push({pid:streamPid,type,codec:({
          0x02:"MPEG-2 video",0x03:"MPEG audio",0x04:"MPEG audio",
          0x06:"Private DVB (may contain Teletext/subtitles)",
          0x0f:"AAC",0x11:"LATM AAC",0x1b:"H.264",0x24:"HEVC"
        })[type]||"0x"+type.toString(16).padStart(2,"0")});
        at+=5+descriptors;
      }
      this.pmts.set(service,{service,pmtPid:pid,pcrPid:pcr,streams});
      this.validSections++;
    }
  }
  summary(){
    return {
      bytes:this.bytes,packets:this.packetCount,
      syncErrors:this.syncErrors,teiErrors:this.teiErrors,
      continuityErrors:this.continuityErrors,crcErrors:this.crcErrors,
      validSections:this.validSections,
      programs:[...this.programs.entries()].map(([service,pmtPid])=>({
        service,pmtPid,details:this.pmts.get(service)||null
      })).sort((a,b)=>a.service-b.service),
      topPids:[...this.packetTypes.entries()].sort((a,b)=>b[1]-a[1])
       .slice(0,12).map(([pid,count])=>({pid,count}))
    };
  }
}