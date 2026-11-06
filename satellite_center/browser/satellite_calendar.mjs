/* Shared 24-hour local reception timeline. Every item is an actual saved
 * capture job, never fabricated RF or a TLE-only transmission claim.
 * Cancelled jobs stay in persisted audit history but are not calendar events.
 */
import {protocolCategories,protocolsForPass} from "./pass_protocol_catalog.mjs";

const validDate=value=>{const date=new Date(value);return Number.isFinite(date.getTime())?date:null;};
export function localDayKey(value){
 const date=validDate(value);
 if(!date)throw Error("Invalid calendar date");
 return [date.getFullYear(),String(date.getMonth()+1).padStart(2,"0"),
   String(date.getDate()).padStart(2,"0")].join("-");
}
export function shiftCalendarDay(key,by){
 if(!/^\d{4}-\d{2}-\d{2}$/.test(String(key)))throw Error("Invalid calendar day");
 const date=new Date(key+"T12:00:00");
 if(!Number.isFinite(date.getTime()))throw Error("Invalid calendar day");
 date.setDate(date.getDate()+by);
 return localDayKey(date);
}
const cancelled=job=>["cancelled","canceled"].includes(String(job?.state||"").toLowerCase());
export function jobStart(job){return validDate(job?.run_at??job?.when??job?.aos);}
export function jobEnd(job){
 const start=jobStart(job);
 if(!start)return null;
 const clip=Number(job?.capture_seconds??job?.durationSeconds??job?.duration_seconds);
 if(Number.isFinite(clip)&&clip>0)return new Date(start.getTime()+clip*1000);
 // Legacy scheduled tasks have no capture duration: the LOS is ONLY the
 // predicted pass window, not a claim that RF was recorded for that long.
 const los=validDate(job?.los??job?.passLos??job?.until);
 return los&&los>start?los:start;
}
export function jobDurationSeconds(job){
 const start=jobStart(job),end=jobEnd(job);
 return start&&end?Math.max(0,Math.round((end-start)/1000)):null;
}
export function formatDuration(seconds){
 if(!Number.isFinite(seconds)||seconds<0)return "unknown duration";
 const n=Math.round(seconds),h=Math.floor(n/3600),m=Math.floor((n%3600)/60),s=n%60;
 return [h?h+"h":null,m?m+"m":null,s||(!h&&!m)?s+"s":null].filter(Boolean).join(" ");
}
const stamp=date=>date.toLocaleTimeString([],{hour:"2-digit",minute:"2-digit",second:"2-digit",hour12:false});
export function jobTimeRange(job){
 const start=jobStart(job),end=jobEnd(job);
 if(!start||!end)return "Unknown time";
 return stamp(start)+"–"+stamp(end)+(localDayKey(start)!==localDayKey(end)?" (next day)":"");
}
function dayBounds(key){
 if(!/^\d{4}-\d{2}-\d{2}$/.test(String(key)))throw Error("Invalid calendar day");
 const first=new Date(key+"T00:00:00");
 if(!Number.isFinite(first.getTime())||localDayKey(first)!==key)throw Error("Invalid calendar day");
 const next=new Date(first);next.setDate(next.getDate()+1);
 return [first,next];
}
export function scheduleForDay(jobs,day){
 const [start,end]=dayBounds(day);
 return (jobs||[]).filter(j=>{
  if(cancelled(j))return false;
  const a=jobStart(j),b=jobEnd(j);
  return a&&b&&a<end&&b>=start&&(b>a||a>=start);
 }).sort((a,b)=>jobStart(a)-jobStart(b));
}
export function calendarHourBuckets(jobs,day){
 const entries=scheduleForDay(jobs,day);
 const [start]=dayBounds(day);
 return Array.from({length:24},(_,hour)=>{
  const a=new Date(start);a.setHours(hour,0,0,0);
  const b=new Date(a);b.setHours(hour+1,0,0,0);
  return {hour,start:a,end:b,jobs:entries.filter(j=>{
   const first=jobStart(j),last=jobEnd(j);
   return first<b&&last>=a&&(last>a||first>=a);
  })};
 });
}
function dataKinds(job){
 if(["image","audio","text","video"].includes(job?.data_kind))return [job.data_kind];
 const id=String(job?.mission_id||job?.missionId||"");
 if(id.includes("meteor")||id.includes("sstv"))return ["image"];
 if(id.includes("aprs"))return ["text"];
 if(id.includes("voice"))return ["audio"];
 const source={id:job?.pass_id||job?.passId};
 const protocols=protocolsForPass(source);
 return [...new Set(protocols.length?protocols.map(p=>p.kind):protocolCategories(source))];
}
export function renderSatelliteCalendar(host,jobs,day,{onEdit=null,onCancel=null}={}){
 if(!host)throw Error("Calendar host is required");
 const buckets=calendarHourBuckets(jobs,day);
 const events=scheduleForDay(jobs,day);
 host.replaceChildren();
 const intro=document.createElement("p");intro.className="calendar-summary";
 intro.textContent=day+" · "+events.length+" active/completed job(s) · device local time · cancelled jobs hidden · predicted satellite passes are not RF evidence";
 host.append(intro);
 const names={image:"🖼 Image",audio:"🔊 Audio",text:"✉ Text",video:"🎥 Video"};
 for(const hour of buckets){
  const line=document.createElement("div");line.className="sat-hour-row";
  const time=document.createElement("time");time.className="sat-hour-label";
  time.textContent=String(hour.hour).padStart(2,"0")+":00–"+
    String((hour.hour+1)%24).padStart(2,"0")+":00";
  const column=document.createElement("div");column.className="sat-hour-events";
  if(!hour.jobs.length){
   const empty=document.createElement("span");empty.className="sat-empty-hour";empty.textContent="No recordings planned";
   column.append(empty);
  }
  for(const job of hour.jobs){
   const start=jobStart(job),end=jobEnd(job);
   const firstSegment=start>=hour.start&&start<hour.end;
   const duration=jobDurationSeconds(job);
   const card=document.createElement("article");
   card.className="sat-calendar-job"+(firstSegment?"":" sat-calendar-continued");
   const lineTitle=document.createElement("strong");
   const title=String(job.satellite||job.name||job.mission_id||"Unattributed satellite");
   lineTitle.textContent=title+(firstSegment?"":" · continues");
   const range=document.createElement("time");
   range.className="sat-job-range";range.textContent=jobTimeRange(job);
   card.append(lineTitle,range);
   const track=document.createElement("div");track.className="sat-time-track";
   track.setAttribute("aria-label","Scheduled reception timing within this hour");
   const fill=document.createElement("span");fill.className="sat-time-fill";
   const hourMs=hour.end-hour.start;
   const left=Math.max(0,Math.min(100,100*(Math.max(start,hour.start)-hour.start)/hourMs));
   const right=Math.max(left,Math.min(100,100*(Math.min(end,hour.end)-hour.start)/hourMs));
   fill.style.left=left+"%";fill.style.width=Math.max(1,right-left)+"%";
   track.append(fill);card.append(track);
   if(firstSegment){
    const details=document.createElement("small");details.className="calendar-state";
    const explicitDuration=Number(job.capture_seconds??job.durationSeconds??job.duration_seconds)>0;
    details.textContent=(explicitDuration?"Planned capture: ":"Predicted pass window: ")+
      formatDuration(duration)+" · status: "+String(job.state||"planned")+
      (job.coverage?" · "+job.coverage:"");
    card.append(details);
    const kinds=dataKinds(job);
    const caps=document.createElement("div");caps.className="pass-capability-list";
    for(const kind of kinds){
     if(!names[kind])continue;
     const pill=document.createElement("span");pill.className="pass-capability pass-kind-"+kind;
     pill.textContent=names[kind];caps.append(pill);
    }
    card.append(caps);
    if(job.estimated_bytes||job.estimatedBytes){
     const storage=document.createElement("small");storage.className="calendar-state";
     storage.textContent="Estimated output: "+((job.estimated_bytes||job.estimatedBytes)/1e6).toFixed(1)+" MB";
     card.append(storage);
    }
    if(job.message||job.result){
     const note=document.createElement("small");note.className="calendar-state";
     note.textContent=String(job.message||(typeof job.result==="string"?job.result:
       "Saved recording; satellite source not independently verified")).slice(0,180);
     card.append(note);
    }
    if(typeof onEdit==="function"&&["pending","armed"].includes(job.state)){
     const edit=document.createElement("button");edit.type="button";edit.className="secondary";
     edit.textContent="Edit time / duration / protocol";
     edit.addEventListener("click",()=>onEdit(job,card));card.append(edit);
    }
    if(typeof onCancel==="function"&&["pending","armed"].includes(job.state)){
     const cancel=document.createElement("button");cancel.type="button";cancel.className="secondary";
     cancel.textContent="Cancel job";cancel.addEventListener("click",()=>onCancel(job));card.append(cancel);
    }
   }
   column.append(card);
  }
  line.append(time,column);host.append(line);
 }
 return {day,shown:events.length,total:(jobs||[]).length};
}
