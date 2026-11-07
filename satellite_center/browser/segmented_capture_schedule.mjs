/* Deterministic, receive-only WebUSB clip planner.
 * A 300 s REQUEST means 300 s of *planned RF acquisition* split into separate
 * clips. Reopening the USB receiver requires explicit non-recording gaps.
 * The scheduler may miss clips; no seamless IQ continuity is promised.
 */
import {MEMORY_IQ_BYTES,MAX_BROWSER_CAPTURE_SECONDS,captureBudget} from "./capture_duration.mjs";
import {wavOutputPlan} from "./fm_wav_record.mjs";
export const SEGMENT_MAX_SECONDS=60;
export const SEGMENT_GAP_SECONDS=6;
export const MAX_SEGMENT_COUNT=60;
export function secondsFromMinutes(minuteValue,secondValue){
 const m=Number(minuteValue),s=Number(secondValue);
 if(!Number.isInteger(m)||!Number.isInteger(s)||m<0||m>15||s<0||s>59)
   throw Error("Enter whole minutes (0–15) and seconds (0–59).");
 const n=m*60+s;
 if(n<1||n>MAX_BROWSER_CAPTURE_SECONDS)
   throw Error("Select 1–900 seconds (maximum 15 minutes).");
 return n;
}
export function splitDuration(seconds){
 if(!Number.isInteger(seconds)||seconds<0)throw Error("Invalid duration");
 return {minutes:Math.floor(seconds/60),seconds:seconds%60};
}
export function formatRemaining(seconds){
 let n=Math.max(0,Math.ceil(Number.isFinite(Number(seconds))?Number(seconds):0));
 const d=Math.floor(n/86400);n%=86400;
 const h=Math.floor(n/3600);n%=3600;
 const m=Math.floor(n/60),s=n%60;
 return d+"d "+String(h).padStart(2,"0")+"h "+
   String(m).padStart(2,"0")+"m "+String(s).padStart(2,"0")+"s";
}
export function buildSegmentPlan({seconds,sampleRate,saveRaw=true,saveWav=false,
  when,passEnd,gapSeconds=SEGMENT_GAP_SECONDS}){
 if(!Number.isInteger(seconds)||seconds<1||seconds>MAX_BROWSER_CAPTURE_SECONDS)
   throw Error("Requested total length must be 1–900 seconds.");
 if(!Number.isFinite(when)||!Number.isFinite(passEnd)||when>=passEnd)
   throw Error("Invalid satellite pass start/end time.");
 if(!Number.isInteger(gapSeconds)||gapSeconds<2||gapSeconds>15)
   throw Error("Invalid USB reacquisition gap");
 const iqCap=saveRaw?Math.floor(MEMORY_IQ_BYTES/(sampleRate*2)):SEGMENT_MAX_SECONDS;
 if(saveRaw)captureBudget(1,sampleRate,true);
 if(saveWav)wavOutputPlan(1,true);
 const cap=Math.min(SEGMENT_MAX_SECONDS,iqCap);
 if(!Number.isInteger(cap)||cap<1)throw Error("Unsupported recording rate");
 const result=[],count=Math.ceil(seconds/cap);
 if(count>MAX_SEGMENT_COUNT)throw Error("Too many browser recording pieces");
 let cursor=when,remaining=seconds;
 for(let i=0;i<count;i++){
   const durationSeconds=Math.min(cap,remaining);
   captureBudget(durationSeconds,sampleRate,saveRaw,{fileStreaming:false});
   wavOutputPlan(durationSeconds,saveWav,{fileStreaming:false});
   result.push({index:i+1,total:count,when:cursor,
     end:cursor+durationSeconds*1000,durationSeconds,
     saveRaw:Boolean(saveRaw),saveWav:Boolean(saveWav),
     estimatedBytes:(saveRaw?durationSeconds*sampleRate*2:0)+
       (saveWav?44+durationSeconds*48000*2:0)});
   cursor+=durationSeconds*1000+(i===count-1?0:gapSeconds*1000);
   remaining-=durationSeconds;
 }
 if(result[result.length-1].end>passEnd)
   throw Error("Recording plus "+(count-1)+" USB reopen gaps of "+gapSeconds+
     " seconds will exceed predicted satellite LOS by "+
     Math.ceil((result[result.length-1].end-passEnd)/1000)+
     " s. Start earlier or shorten total recording.");
 return {segments:result,count,requestedSeconds:seconds,
   scheduledSpanSeconds:seconds+(count-1)*gapSeconds,
   gapSeconds,recordedSeconds:seconds,expectedGapSeconds:(count-1)*gapSeconds,
   estimatedBytes:result.reduce((sum,x)=>sum+x.estimatedBytes,0),
   maxClipSeconds:cap};
}
