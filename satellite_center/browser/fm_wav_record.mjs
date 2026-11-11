/* Receive-only streaming NFM SSTV audio recorder for actual RTL-SDR CU8 blocks.
 * NO arbitrary RF bytes are relabeled as WAV. This demodulates real I/Q,
 * decimates by an integer factor, high-pass removes residual carrier offset
 * and creates a valid 48 kHz mono 16-bit PCM RIFF file incrementally.
 *
 * The detector is experimental and has no automatic Doppler correction.
 * A WAV is evidence of demodulated audio, not verified ISS/Robot36 imagery.
 */
export const SSTV_WAV_RATE=48000;
export const SSTV_WAV_CHANNELS=1;
export const SSTV_WAV_PCM_BITS=16;
export const WAV_RAM_LIMIT=16*1024*1024;
export const WAV_MAX_SECONDS=900;
const WAV_BYTES_PER_SECOND=SSTV_WAV_RATE*2;

export function wavOutputPlan(seconds,enabled,{fileStreaming=false}={}){
 if(!Number.isInteger(seconds)||seconds<1||seconds>WAV_MAX_SECONDS)
   throw Error("WAV recording length must be 1–900 whole seconds");
 if(!enabled)return {enabled:false,mode:"disabled",estimatedBytes:0};
 const estimatedBytes=44+seconds*WAV_BYTES_PER_SECOND;
 if(estimatedBytes<=WAV_RAM_LIMIT)return {enabled:true,mode:"memory",estimatedBytes};
 if(!fileStreaming)throw Error(
   "Long FM WAV recordings require a user-selected disk file in a secure Chromium browser, or the native receiver. "+
   "This session would exceed the 16 MiB WAV memory limit.");
 return {enabled:true,mode:"disk-stream",estimatedBytes};
}

export function createPcmWavHeader(pcmBytes,{sampleRate=SSTV_WAV_RATE}={}){
 if(!Number.isSafeInteger(pcmBytes)||pcmBytes<0||pcmBytes%2||
    pcmBytes>0xFFFFFF00)throw Error("Invalid WAV PCM payload size");
 if(sampleRate!==SSTV_WAV_RATE)throw Error("Only 48 kHz PCM WAV output is supported");
 const bytes=new Uint8Array(44),v=new DataView(bytes.buffer);
 const four=(p,s)=>{for(let i=0;i<4;i++)bytes[p+i]=s.charCodeAt(i);};
 four(0,"RIFF");v.setUint32(4,36+pcmBytes,true);four(8,"WAVE");
 four(12,"fmt ");v.setUint32(16,16,true);v.setUint16(20,1,true);
 v.setUint16(22,SSTV_WAV_CHANNELS,true);v.setUint32(24,sampleRate,true);
 v.setUint32(28,sampleRate*2,true);v.setUint16(32,2,true);
 v.setUint16(34,SSTV_WAV_PCM_BITS,true);four(36,"data");
 v.setUint32(40,pcmBytes,true);
 return bytes;
}

export function createStreamingFmWavEncoder(inputRate,{audioGain=1.8}={}){
 if(![1024000,2048000].includes(inputRate))throw Error("FM WAV needs actual 1.024 or 2.048 MS/s CU8 samples");
 if(!(Number.isFinite(audioGain)&&audioGain>0&&audioGain<=10))throw Error("Invalid FM audio gain");
 // 1.024/2.048 MS/s -> 64 k complex -> 16 k discriminator -> 48 k PCM.
 const iqDecimation=inputRate/64000;
 let accumulatedI=0,accumulatedQ=0,iqCount=0;
 let lastI=0,lastQ=0,havePrevious=false;
 let phaseSum=0,phaseCount=0,dc=0,filtered=0,lastAudio=0,haveAudio=false;
 let leftoverI=null,inputBytes=0,pcmBytes=0,frames=0;
 const sinc=(value)=>Math.max(-1,Math.min(1,value));
 const bytesToPcm=x=>Math.round(sinc(x)*32767);
 function push(chunk){
   if(!(chunk instanceof Uint8Array))throw Error("Streaming FM WAV requires real Uint8Array CU8 samples");
   inputBytes+=chunk.length;
   // Each 64 input complex samples yield three 16-bit PCM frames.
   const capacity=Math.ceil((chunk.length/2+1)/64+2)*6;
   const out=new Uint8Array(capacity);
   const view=new DataView(out.buffer);
   let offset=0;
   function consume(iByte,qByte){
     accumulatedI+=(iByte-127.5)/128;
     accumulatedQ+=(qByte-127.5)/128;
     if(++iqCount<iqDecimation)return;
     const i=accumulatedI/iqDecimation,q=accumulatedQ/iqDecimation;
     accumulatedI=0;accumulatedQ=0;iqCount=0;
     if(havePrevious){
       phaseSum+=Math.atan2(q*lastI-i*lastQ,i*lastI+q*lastQ);
       if(++phaseCount===4){
         const phase=phaseSum/4;
         phaseSum=0;phaseCount=0;
         dc+=0.0004*(phase-dc);
         const wave=phase-dc;
         filtered+=0.65*(wave-filtered);
         const next=bytesToPcm(filtered*audioGain)/32767;
         // Three properly timed PCM frames at 48 kHz from each 16 kHz
         // discriminator sample. Interpolation cannot create new bandwidth.
         const start=haveAudio?lastAudio:next;
         for(let k=0;k<3;k++){
           view.setInt16(offset,bytesToPcm(start+(next-start)*(k+1)/3),true);
           offset+=2;
         }
         lastAudio=next;haveAudio=true;frames+=3;
       }
     }
     lastI=i;lastQ=q;havePrevious=true;
   }
   let j=0;
   if(leftoverI!==null && chunk.length){
     consume(leftoverI,chunk[0]);leftoverI=null;j=1;
   }
   for(;j+1<chunk.length;j+=2)consume(chunk[j],chunk[j+1]);
   if(j<chunk.length)leftoverI=chunk[j];
   pcmBytes+=offset;
   return out.subarray(0,offset);
 }
 function report(){
   return {source:"real RTL2832U unsigned CU8",inputRate,
     outputRate:SSTV_WAV_RATE,channels:1,bitsPerSample:16,
     pcmBytes,frames,sourceBytes:inputBytes,
     durationSeconds:Number((frames/SSTV_WAV_RATE).toFixed(3)),
     verifiedRobot36:false,verifiedSpacecraft:false,
     limitation:"No automatic Doppler tracking; actual signal/synchronization must be validated separately."};
 }
 return {push,report,get pcmBytes(){return pcmBytes;},
   makeHeader(){return createPcmWavHeader(pcmBytes);}};
}
