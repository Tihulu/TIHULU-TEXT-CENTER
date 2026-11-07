/* Opt-in segmented satellite RF recording schedule for foreground WebUSB.
 * Each segment fits the browser's 128 MiB CU8 buffer and 60-second safety
 * policy. Reopening the receiver introduces unrecorded gaps; DO NOT claim
 * that separate CU8 files form one continuous baseband acquisition.
 */
import {MEMORY_IQ_BYTES,SUPPORTED_IQ_RATES} from "./capture_duration.mjs";

export const MAX_SEGMENTED_TOTAL_SECONDS=900;
export const WEB_SEGMENT_LIMIT_SECONDS=60;
export const BETWEEN_SEGMENTS_SECONDS=2;
export const MAX_SEGMENT_JOBS=30;

export function durationToSeconds(value,unit="seconds",{min=1,max=MAX_SEGMENTED_TOTAL_SECONDS}={}){
 const amount=Number(value);
 if(!Number.isFinite(amount)||amount<=0||!["seconds","minutes"].includes(unit))
   throw Error("Enter a positive duration in seconds or minutes.");
 const seconds=Math.round(amount*(unit==="minutes"?60:1));
 if(seconds<min||seconds>max||Math.abs(seconds-amount*(unit==="minutes"?60:1))>.001)
   throw Error("Choose "+min+"–"+max+" whole seconds (or the equivalent minutes).");
 return seconds;
}
export function formatCountdown(ms){
 const n=Math.max(0,Math.ceil(Number(ms)/1000)||0);
 const d=Math.floor(n/86400),h=Math.floor(n%86400/3600),
       m=Math.floor(n%3600/60),s=n%60;
 return d+"d "+String(h).padStart(2,"0")+"h "+
   String(m).padStart(2,"0")+"m "+String(s).padStart(2,"0")+"s";
}
export function browserClipCap(rate,raw){
 if(!SUPPORTED_IQ_RATES.includes(rate))throw Error("Unknown SDR sample rate");
 return raw?
   Math.min(WEB_SEGMENT_LIMIT_SECONDS,Math.floor(MEMORY_IQ_BYTES/(rate*2))):
   WEB_SEGMENT_LIMIT_SECONDS;
}
export function segmentedCapturePlan({startMs,totalSeconds,rate,saveRaw=true,saveWav=false,
  passEndMs,gapSeconds=BETWEEN_SEGMENTS_SECONDS,
  maxClipSeconds=null}={}){
 if(!Number.isFinite(startMs)||!Number.isFinite(passEndMs)||startMs>=passEndMs)
   throw Error("Choose a future start time inside the predicted satellite pass.");
 if(!Number.isInteger(totalSeconds)||totalSeconds<1||totalSeconds>MAX_SEGMENTED_TOTAL_SECONDS)
   throw Error("Total recording duration must be 1–900 whole seconds.");
 if(!Number.isInteger(gapSeconds)||gapSeconds<0||gapSeconds>15)
   throw Error("Choose a safe inter-segment gap of 0–15 seconds.");
 const cap=Math.min(browserClipCap(rate,Boolean(saveRaw)),
   maxClipSeconds===null?WEB_SEGMENT_LIMIT_SECONDS:maxClipSeconds);
 if(!Number.isInteger(cap)||cap<8)throw Error("Segment length must be at least 8 seconds.");
 // Spread the requested RF seconds evenly: 61s => 31+30, never 60+1.
 const count=Math.ceil(totalSeconds/cap);
 if(count>MAX_SEGMENT_JOBS)throw Error("Too many WebUSB downloads. Lower the requested duration.");
 const base=Math.floor(totalSeconds/count),extra=totalSeconds%count;
 let cursor=startMs;
 const groupId="segments:"+String(startMs)+":"+String(totalSeconds)+":"+
   String(rate)+":"+String(saveRaw)+":"+String(saveWav);
 const segments=[];
 for(let i=0;i<count;i++){
   const seconds=base+(i<extra?1:0);
   if(seconds<1||seconds>cap)throw Error("Unsafe WebUSB clip size");
   segments.push({index:i+1,count,groupId,
     when:cursor,durationSeconds:seconds,end:cursor+seconds*1000,
     estimatedBytes:(saveRaw?seconds*rate*2:0)+(saveWav?44+seconds*96000:0)});
   cursor+=(seconds+(i<count-1?gapSeconds:0))*1000;
 }
 if(segments[segments.length-1].end>passEndMs)
   throw Error("Requested "+totalSeconds+" RF seconds plus "+
     ((count-1)*gapSeconds)+" seconds of receiver reset gaps cannot fit before predicted LOS. "+
     "Reduce duration, move the start earlier or use native continuous capture.");
 return {groupId,requestedSeconds:totalSeconds,segmentCount:count,
   captureSeconds:totalSeconds,gapSeconds,unrecordedGapSeconds:(count-1)*gapSeconds,
   wallSeconds:totalSeconds+(count-1)*gapSeconds,
   estimatedBytes:segments.reduce((sum,p)=>sum+p.estimatedBytes,0),
   segments,capacitySeconds:cap};
}
