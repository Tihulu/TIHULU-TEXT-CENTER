/* Bounded, opt-in browser USB bulk recorder. No RF tune, vendor OUT,
 * firmware, kernel-driver detach, or background capture is performed.
 * Captures only bytes actually returned by a user-claimed USB endpoint.
 */
import {TransportAnalyzer} from "./ts-analyzer.js";

export class BrowserTransportCapture {
  constructor(read, {maxBytes=4*1024*1024, maxTransfers=256, onProgress=()=>{}}={}) {
    if(typeof read!=="function") throw TypeError("USB read callback required");
    if(!Number.isInteger(maxBytes)||maxBytes<188||maxBytes>8*1024*1024)
      throw RangeError("Capture budget must be 188 bytes..8 MiB");
    if(!Number.isInteger(maxTransfers)||maxTransfers<1||maxTransfers>1024)
      throw RangeError("Capture transfer budget must be 1..1024");
    if(typeof onProgress!=="function")throw TypeError("Progress must be a function");
    this.read=read;this.maxBytes=maxBytes;this.maxTransfers=maxTransfers;
    this.onProgress=onProgress;this.stopped=false;this.running=false;
    this.finished=false;this.analyzer=new TransportAnalyzer();
  }
  stop(){this.stopped=true;}
  async run(){
    if(this.running||this.finished)throw Error("Capture session cannot be reused");
    this.running=true;
    const chunks=[];
    let total=0,reads=0,empty=0;
    try {
      while(!this.stopped&&reads<this.maxTransfers&&total<this.maxBytes){
        const budget=Math.min(16384,this.maxBytes-total);
        const result=await this.read(budget);
        reads++;
        if(!(result instanceof Uint8Array)||result.length>budget)
          throw Error("USB read returned invalid or oversized bytes");
        if(result.length===0){
          empty++;
          if(empty>=3)break;
          continue;
        }
        empty=0;
        const block=result.slice();
        chunks.push(block);
        total+=block.length;
        this.analyzer.feed(block);
        this.onProgress({bytes:total,transfers:reads,summary:this.analyzer.summary()});
      }
      const bytes=new Uint8Array(total);
      let offset=0;
      for(const block of chunks){bytes.set(block,offset);offset+=block.length;}
      const summary=this.analyzer.summary();
      return {bytes,transfers:reads,stopped:this.stopped,
        summary,transportVerified:summary.packets>0&&summary.validSections>0};
    }finally {
      this.running=false;
      this.finished=true;
    }
  }
}
