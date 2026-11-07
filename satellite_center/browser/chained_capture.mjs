/* Opt-in segmented browser capture plan: every segment becomes a real job.
 * Splitting protects RAM but is NOT lossless: each RTL-SDR reopen/re-tune and
 * browser download can introduce gaps. Never silently claim continuous RF.
 */
import {MEMORY_IQ_BYTES,MAX_BROWSER_CAPTURE_SECONDS,SUPPORTED_IQ_RATES} from "./capture_duration.mjs";
export const WEB_CHAIN_MAX_SEGMENT_SECONDS=60;
export const WEB_CHAIN_GAP_SECONDS=6;
export const MAX_CHAIN_SEGMENTS=120;
export function humanCountdown(seconds){
 const n=Math.max(0,Math.ceil(Number(seconds)||0));
 const d=Math.floor(n/86400),h=Math.floor(n%86400/3600),
       m=Math.floor(n%3600/60),s=n%60;
 return [d+"d",String(h).padStart(2,"0")+"h",
         String(m).padStart(2,"0")+"m",String(s).padStart(2,"0")+"s"].join(" ");
}
export function secondsFromEntry(amount,unit="seconds"){
 const n=Number(amount);
 if(!Number.isFinite(n)||n<=0||!Number.isInteger(n))throw Error("Enter a positive whole number of seconds or minutes.");
 if(!["seconds","minutes"].includes(unit))throw Error("Choose seconds or minutes.");
 const seconds=n*(unit==="minutes"?60:1);
 if(!Number.isSafeInteger(seconds)||seconds>7200)throw Error("The chained capture maximum is 120 minutes.");
 return seconds;
}
export function planChainedCapture({startMs,totalSeconds,rate,raw=true,wav=false,
  maxSegmentSeconds=WEB_CHAIN_MAX_SEGMENT_SECONDS,gapSeconds=WEB_CHAIN_GAP_SECONDS,
  untilMs=Infinity,allowDisk=false}={}){
 if(!Number.isFinite(startMs)||!Number.isSafeInteger(totalSeconds)||totalSeconds<1||totalSeconds>7200)
   throw Error("Enter 1–7200 whole seconds and a valid scheduled start.");
 if(!SUPPORTED_IQ_RATES.includes(rate))throw Error("Unsupported RTL-SDR sample rate.");
 if(!Number.isInteger(gapSeconds)||gapSeconds<0||gapSeconds>60)
   throw Error("The inter-segment buffer must be 0–60 seconds.");
 if(!Number.isInteger(maxSegmentSeconds)||maxSegmentSeconds<1||maxSegmentSeconds>180)
   throw Error("Invalid per-file duration.");
 const memoryLimit=raw&&!allowDisk?Math.floor(MEMORY_IQ_BYTES/(rate*2)):maxSegmentSeconds;
 const cap=Math.min(maxSegmentSeconds,MAX_BROWSER_CAPTURE_SECONDS,memoryLimit);
 if(cap<1)throw Error("The selected sample rate cannot fit in browser memory.");
 const result=[];
 let remaining=totalSeconds,offset=0;
 while(remaining>0){
   if(result.length>=MAX_CHAIN_SEGMENTS)throw Error("Too many consecutive recordings; shorten the request or increase segment size.");
   const durationSeconds=Math.min(cap,remaining);
   const when=startMs+offset*1000,end=when+durationSeconds*1000;
   if(end>untilMs)throw Error("Segments would extend beyond the satellite pass. Shorten recording or schedule earlier.");
   result.push({index:result.length+1,when,end,durationSeconds,
     estimatedRawBytes:raw?rate*2*durationSeconds:0,
     estimatedWavBytes:wav?44+durationSeconds*96000:0});
   remaining-=durationSeconds;
   offset+=durationSeconds+(remaining>0?gapSeconds:0);
 }
 return {segments:result,totalCaptureSeconds:totalSeconds,
   elapsedSeconds:offset,totalGapSeconds:offset-totalSeconds,
   gapsPossible:true,rate,raw,wav,
   warning:"Separate WebUSB recordings are NOT continuous: SDR re-open/tune, file downloads and tab scheduling may lose RF samples."};
}
export function scheduledOverlap(a,b,{guardSeconds=0}={}){
 return a.when<(b.when+b.durationSeconds*1000)+guardSeconds*1000&&
   a.when+a.durationSeconds*1000>b.when-guardSeconds*1000;
}
