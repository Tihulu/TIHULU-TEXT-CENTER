/* Time-of-day calendar for actual scheduled captures. Runs entirely in browser.
 * Rows are real jobs, never fake or synthetic predicted transmissions.
 */
import {protocolCategories,protocolsForPass} from "./pass_protocol_catalog.mjs";

export function localDayKey(value){
 const date=new Date(value);
 if(!Number.isFinite(date.getTime()))throw Error("Invalid calendar date");
 return [date.getFullYear(),String(date.getMonth()+1).padStart(2,"0"),
   String(date.getDate()).padStart(2,"0")].join("-");
}
export function shiftCalendarDay(key,by){
 if(!/^\d{4}-\d{2}-\d{2}$/.test(String(key)))throw Error("Invalid calendar day");
 const d=new Date(key+"T12:00:00");
 if(!Number.isFinite(d.getTime()))throw Error("Invalid calendar day");
 d.setDate(d.getDate()+by);
 return localDayKey(d);
}
export function jobStart(job){
 const date=new Date(job?.run_at||job?.when||job?.aos);
 return Number.isFinite(date.getTime())?date:null;
}
export function scheduleForDay(jobs,day){
 if(!/^\d{4}-\d{2}-\d{2}$/.test(String(day)))throw Error("Invalid calendar day");
 return (jobs||[]).filter(j=>{const d=jobStart(j);return d&&localDayKey(d)===day;})
   .sort((a,b)=>jobStart(a)-jobStart(b));
}
export function calendarHourBuckets(jobs,day){
 const days=scheduleForDay(jobs,day);
 return Array.from({length:24},(_,hour)=>({
   hour,jobs:days.filter(j=>jobStart(j).getHours()===hour)
 }));
}
export function renderSatelliteCalendar(host,jobs,day,{onEdit=null,onCancel=null}={}){
 if(!host)throw Error("Calendar host is required");
 const buckets=calendarHourBuckets(jobs,day);
 host.replaceChildren();
 const scheduled=buckets.reduce((n,row)=>n+row.jobs.length,0);
 const intro=document.createElement("p");intro.className="calendar-summary";
 intro.textContent=day+" · "+scheduled+" scheduled/recorded job(s) · local device time. Calendar does not claim RF reception.";
 host.append(intro);
 for(const row of buckets){
   const line=document.createElement("div");line.className="sat-hour-row";
   const hour=document.createElement("time");hour.className="sat-hour-label";
   hour.textContent=String(row.hour).padStart(2,"0")+":00";
   const events=document.createElement("div");events.className="sat-hour-events";
   if(!row.jobs.length){
     const empty=document.createElement("span");empty.className="sat-empty-hour";empty.textContent="—";
     events.append(empty);
   }
   for(const job of row.jobs){
     const card=document.createElement("article");card.className="sat-calendar-job";
     const title=document.createElement("strong");
     const start=jobStart(job);
     title.textContent=start.toLocaleTimeString([],{hour:"2-digit",minute:"2-digit"})+" · "+
       String(job.satellite||job.name||job.mission_id||"Unattributed satellite");
     card.append(title);
     const type=job.mission_id?
       protocolsForPass({id:job.pass_id}).filter(p=>p.id.includes(String(job.mission_id).includes("aprs")?"aprs":String(job.mission_id).includes("sstv")?"sstv":String(job.mission_id).includes("meteor")?"lrpt":"-"))
       :[];
     const kinds=type.length?[...new Set(type.map(x=>x.kind))]:protocolCategories({id:job.pass_id||job.passId});
     const names={image:"🖼 Image",audio:"🔊 Audio",text:"✉ Text",video:"🎥 Video"};
     const caps=document.createElement("div");caps.className="pass-capability-list";
     for(const kind of kinds){
       const p=document.createElement("span");p.className="pass-capability pass-kind-"+kind;p.textContent=names[kind];
       caps.append(p);
     }
     card.append(caps);
     const state=document.createElement("small");state.className="calendar-state";
     state.textContent="Status: "+String(job.state||"planned")+" · "+
       String(job.mode||job.mission_id||((job.frequency||0)?((job.frequency/1e6).toFixed(3)+" MHz"):"protocol not confirmed"));
     card.append(state);
     if(job.message||job.result){
       const note=document.createElement("small");note.className="calendar-state";
       note.textContent=String(job.message||(typeof job.result==="string"?job.result:"Recorded data, not verified satellite origin")).slice(0,160);
       card.append(note);
     }
     if(typeof onEdit==="function"&&["pending","armed"].includes(job.state)){
       const edit=document.createElement("button");edit.type="button";edit.className="secondary";
       edit.textContent="Edit time / protocol";edit.addEventListener("click",()=>onEdit(job,card));card.append(edit);
     }
     if(typeof onCancel==="function"&&["pending","armed"].includes(job.state)){
       const cancel=document.createElement("button");cancel.type="button";cancel.className="secondary";
       cancel.textContent="Cancel job";cancel.addEventListener("click",()=>onCancel(job));card.append(cancel);
     }
     events.append(card);
   }
   line.append(hour,events);host.append(line);
 }
 return {day,shown:scheduled,total:(jobs||[]).length};
}
