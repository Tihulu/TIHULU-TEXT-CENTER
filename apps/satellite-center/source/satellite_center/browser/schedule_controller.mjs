// Browser-only opt-in RF capture schedules. No closed-tab execution promises.
import {captureBudget,MAX_BROWSER_CAPTURE_SECONDS} from './capture_duration.mjs';
import {wavOutputPlan} from './fm_wav_record.mjs';
export const MAX_SCHEDULE_SECONDS = MAX_BROWSER_CAPTURE_SECONDS;
export const DEFAULT_SAMPLE_RATE = 1024000;
export function localDateInput(time){
 const d=new Date(time);
 if(!Number.isFinite(d.getTime()))return "";
 const pad=x=>String(x).padStart(2,"0");
 return d.getFullYear()+"-"+pad(d.getMonth()+1)+"-"+pad(d.getDate())+
  "T"+pad(d.getHours())+":"+pad(d.getMinutes());
}
export function parseLocalScheduleTime(text){
 if(typeof text!=="string"||!/^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}$/.test(text))
  throw Error("Choose a valid local date and minute (YYYY-MM-DD HH:mm).");
 const ms=new Date(text).getTime();
 if(!Number.isFinite(ms))throw Error("The chosen date/time cannot be parsed.");
 return ms;
}
export function createScheduledPass(pass,choices,now=Date.now()){
 if(!pass||!Number.isFinite(Number(pass.aos))||!Number.isFinite(Number(pass.los))||
 Number(pass.los)<=Number(pass.aos))throw Error("Invalid satellite pass window.");
 const when=Number(choices.when),until=Number(pass.los);
 const duration=Number(choices.durationSeconds),sampleRate=Number(choices.sampleRate);
 const frequency=Number(choices.frequency);
 if(!Number.isFinite(when)||when<now-15000)throw Error("Scheduled start is in the past. Choose a future minute.");
 if(when<Number(pass.aos)-120000 || when>=until)
  throw Error("Scheduled minute must fall during this satellite pass (or up to 2 minutes before its start).");
 // A legal start minute is not enough: the entire recording must still fit
 // within the predicted pass. Never arm an overrun past line-of-sight loss.
 if(when+duration*1000>until)
  throw Error("Scheduled recording must finish before this satellite pass ends.");
 const {mode}=captureBudget(duration,sampleRate,Boolean(choices.saveRaw),
   {fileStreaming:Boolean(choices.diskStreamPrepared)});
 const wav=wavOutputPlan(duration,Boolean(choices.saveWav),
   {fileStreaming:Boolean(choices.wavDiskPrepared)});
 if(![1024000,2048000].includes(sampleRate))throw Error("Unsupported sample rate.");
 if(!Number.isFinite(frequency)||frequency<24000000||frequency>1750000000)
  throw Error("Receiver frequency is out of RTL-SDR range.");
 const id=String(pass.id)+":"+Number(pass.aos)+":"+when+":"+frequency;
 return {
  id,passId:pass.id,name:String(pass.name).slice(0,100),
  family:pass.family, when,until,
  passAos:Number(pass.aos),passLos:until,
  frequency,sampleRate,durationSeconds:duration,
  saveRaw:Boolean(choices.saveRaw),saveWav:Boolean(choices.saveWav),
  diskStreamPrepared:mode==="disk-stream",wavDiskPrepared:wav.mode==="disk-stream",state:"armed",
  createdAt:now,report:null,message:"Waiting for scheduled minute; browser must remain open and foreground."
 };
}
export function evaluateScheduledJob(job,now,{visible,receiverBusy}){
 if(!job||job.state!=="armed")return "none";
 if(now>=job.until)return "missed";
 // Browser tabs may wake late or SDRs may be busy: never start a full clip
 // if its actual start would extend beyond predicted LOS, even if armed earlier.
 const clipMilliseconds=Number(job.durationSeconds)*1000;
 if(!Number.isFinite(clipMilliseconds)||clipMilliseconds<=0||
    Math.max(now,Number(job.when))+clipMilliseconds>Number(job.until))return "missed";
 if(now<job.when)return "waiting";
 if(!visible)return "waiting-foreground";
 if(receiverBusy)return "waiting-receiver";
 return "start";
}
export function secondsToJob(job,now=Date.now()){
 return Math.max(0,Math.ceil((job.when-now)/1000));
}
export function captureLevelSummary(levels,bytes,elapsedMs){
 if(!Number.isFinite(bytes)||bytes<0)throw Error("Invalid sample count");
 const values=(Array.isArray(levels)?levels:[]).filter(Number.isFinite);
 const average=values.length?values.reduce((a,b)=>a+b,0)/values.length:null;
 const min=values.length?Math.min(...values):null;
 const max=values.length?Math.max(...values):null;
 return {
  bytesReceived:bytes,
  blocksMeasured:values.length,
  minRelativeDb:min==null?null:Number(min.toFixed(2)),
  averageRelativeDb:average==null?null:Number(average.toFixed(2)),
  maxRelativeDb:max==null?null:Number(max.toFixed(2)),
  levelVariationDb:max==null?null:Number((max-min).toFixed(2)),
  elapsedSeconds:Number((Math.max(0,elapsedMs)/1000).toFixed(2)),
  interpretation:"Uncalibrated sample-level statistics only; no transmitter identity, decoded message or satellite detection."
 };
}
