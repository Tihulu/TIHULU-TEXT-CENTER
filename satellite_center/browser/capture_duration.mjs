/* Browser capture duration and storage preflight.
 * Short RF clips remain in memory; larger raw IQ requires a user-selected
 * writable local file in supporting foreground Chromium browsers.
 * This is not an unattended native receiver or a guarantee of signal/data.
 */
export const MEMORY_IQ_BYTES=128*1024*1024;
export const STREAM_IQ_BYTES=2_000_000_000;
export const MAX_BROWSER_CAPTURE_SECONDS=900;
export const SUPPORTED_IQ_RATES=Object.freeze([1024000,2048000]);
export function captureBudget(seconds,rate,raw=true,{fileStreaming=false}={}){
 if(!Number.isInteger(seconds)||seconds<1||seconds>MAX_BROWSER_CAPTURE_SECONDS)
   throw Error("Enter a whole RF sample length from 1 to 900 seconds.");
 if(!SUPPORTED_IQ_RATES.includes(rate))throw Error("Select a supported 1.024 or 2.048 MS/s sample rate.");
 const estimatedBytes=seconds*rate*2;
 if(!Number.isSafeInteger(estimatedBytes))throw Error("Raw IQ estimate overflow");
 if(!raw)return {mode:"levels-only",estimatedBytes:0,seconds,rate,capSeconds:MAX_BROWSER_CAPTURE_SECONDS};
 if(estimatedBytes<=MEMORY_IQ_BYTES)
   return {mode:"memory",estimatedBytes,seconds,rate,capSeconds:Math.floor(MEMORY_IQ_BYTES/(rate*2))};
 const diskMaxSeconds=Math.min(MAX_BROWSER_CAPTURE_SECONDS,Math.floor(STREAM_IQ_BYTES/(rate*2)));
 if(estimatedBytes>STREAM_IQ_BYTES)
   throw Error("Raw IQ would exceed the 2 GB stream cap at "+(rate/1e6)+" MS/s. Maximum here: "+diskMaxSeconds+
     " seconds. Lower the sample rate or use native recording.");
 if(!fileStreaming)throw Error("Long RF samples require streamed local disk saving via a Chromium File System Access picker, or the native receiver. This browser cannot safely hold "+
   Math.ceil(estimatedBytes/1048576)+" MiB in memory.");
 return {mode:"disk-stream",estimatedBytes,seconds,rate,capSeconds:diskMaxSeconds};
}
export function formatCaptureBudget(seconds,rate,raw=true,fileStreaming=false){
 try{
  const plan=captureBudget(seconds,rate,raw,{fileStreaming});
  return {ok:true,...plan,detail:raw?
    plan.mode==="disk-stream"?"Writes "+(plan.estimatedBytes/1e6).toFixed(0)+" MB of CU8 directly to a user-selected disk file (no 128 MiB memory buffer).":
    "About "+(plan.estimatedBytes/1e6).toFixed(0)+" MB of CU8 in browser memory.":
    "Uncalibrated RF level measurements only; no raw IQ/image data saved."};
 }catch(error){return {ok:false,detail:String(error?.message||error)};}
}
