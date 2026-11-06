import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {PUBLIC_DOWNLINKS,noradFromPass,protocolsForPass,protocolCategories,
  passesFilteredByContent,protocolIsDecodableNow} from "../satellite_center/browser/pass_protocol_catalog.mjs";
import {localDayKey,shiftCalendarDay,scheduleForDay,calendarHourBuckets,jobStart}
  from "../satellite_center/browser/satellite_calendar.mjs";

test("Published multi-satellite protocols are labeled but not conflated with detected radio",()=>{
 const iss={id:25544,name:"ISS"},meteor={id:59051,name:"Meteor"},
   unknown={id:99999,name:"Unknown"},retired={id:25338,name:"NOAA-15"};
 assert.equal(noradFromPass({id:"25544:1762000000"}),25544);
 assert.equal(noradFromPass({id:"not-a-real-catalog-id"}),null);
 assert.deepEqual(protocolCategories(iss),["image","audio","text","video"]);
 assert.deepEqual(protocolCategories(meteor),["image"]);
 assert.deepEqual(protocolCategories(unknown),[]);
 assert.deepEqual(protocolCategories(retired),[]);
 assert.ok(protocolsForPass(iss).some(p=>p.protocol.includes("PD120")&&p.decoder==="external-only"));
 assert.ok(protocolsForPass(iss).some(p=>p.protocol.includes("Robot36")&&p.activity==="event-only"));
 assert.ok(protocolsForPass(meteor).some(p=>p.decoder==="native-satdump"));
 assert.equal(passesFilteredByContent([iss,meteor,unknown],"image").length,2);
 assert.deepEqual(passesFilteredByContent([iss,meteor,unknown],"text"),[iss]);
 assert.deepEqual(passesFilteredByContent([iss,meteor,unknown],"known"),[iss,meteor]);
 assert.equal(protocolIsDecodableNow(protocolsForPass(iss).find(p=>p.id==="iss-hamtv")),false);
 assert.equal(PUBLIC_DOWNLINKS.some(p=>[25338,28654,33591].includes(p.norad)),false);
 assert.throws(()=>passesFilteredByContent([],"private"),/Unknown/);
});
test("24-hour schedule is based on genuine job times and local day",()=>{
 const date="2026-11-06";
 assert.equal(shiftCalendarDay(date,1),"2026-11-07");
 assert.equal(shiftCalendarDay(date,-1),"2026-11-05");
 const time=new Date(date+"T14:22:00");
 const job={id:"job1",when:time.getTime(),name:"Meteor LRPT",state:"armed"};
 assert.equal(localDayKey(time),date);
 assert.equal(jobStart(job).getHours(),14);
 assert.deepEqual(scheduleForDay([job],"2026-11-07"),[]);
 assert.deepEqual(scheduleForDay([job],date),[job]);
 const buckets=calendarHourBuckets([job],date);
 assert.equal(buckets.length,24);
 assert.equal(buckets[14].jobs.length,1);
 assert.equal(buckets[13].jobs.length,0);
 assert.equal(buckets.reduce((sum,b)=>sum+b.jobs.length,0),1);
 assert.throws(()=>scheduleForDay([],"invalid"),/Invalid/);
});

test("Cancelled jobs are absent from the calendar, not deleted from the audit source",()=>{
 const day="2026-11-06";
 const at=new Date(day+"T11:23:00").getTime();
 const jobs=[
  {id:"cancelled",when:at,state:"cancelled",durationSeconds:60},
  {id:"US-spelling",when:at,state:"canceled",durationSeconds:60},
  {id:"live",when:at,state:"armed",durationSeconds:600,missionId:"meteor-m2-4"},
 ];
 assert.deepEqual(scheduleForDay(jobs,day).map(j=>j.id),["live"]);
 assert.equal(calendarHourBuckets(jobs,day)[11].jobs.length,1);
 assert.equal(jobs.length,3);
});
test("Long captures span multiple hours and show exact end with duration",async()=>{
 const {jobEnd,jobTimeRange,jobDurationSeconds,formatDuration}=
   await import("../satellite_center/browser/satellite_calendar.mjs");
 const day="2026-11-06";
 const a=new Date(day+"T11:54:15"),j={when:a.getTime(),durationSeconds:900,state:"armed"};
 assert.equal(jobDurationSeconds(j),900);
 assert.equal(jobEnd(j).getTime(),a.getTime()+900000);
 assert.equal(formatDuration(900),"15m");
 assert.equal(calendarHourBuckets([j],day)[11].jobs.length,1);
 assert.equal(calendarHourBuckets([j],day)[12].jobs.length,1);
 assert.match(jobTimeRange(j),/11:54:15.*12:09:15/);
});
test("Midnight crossings appear on both local days, without cancelled entries",async()=>{
 const {jobTimeRange}=await import("../satellite_center/browser/satellite_calendar.mjs");
 const j={id:"overnight",when:new Date("2026-11-06T23:57:30").getTime(),
  durationSeconds:600,state:"completed"};
 assert.deepEqual(scheduleForDay([j],"2026-11-07"),[j]);
 assert.deepEqual(calendarHourBuckets([j],"2026-11-07")[0].jobs,[j]);
 assert.match(jobTimeRange(j),/next day/);
 const untilHour=new Date("2026-11-06T12:00:00").getTime();
 const exact={when:new Date("2026-11-06T11:59:00").getTime(),durationSeconds:60,state:"armed"};
 assert.equal(calendarHourBuckets([exact],"2026-11-06")[12].jobs.length,0);
});

test("Calendar rows cannot shrink under tall capture cards and overlap other hours",()=>{
 const fs=requireCss();
 assert.match(fs,/\.sat-calendar-grid>\.sat-hour-row\s*\{[^}]*flex:0 0 auto/s);
 assert.match(fs,/\.sat-calendar-grid \.sat-calendar-job\s*\{[^}]*height:auto/s);
});
function requireCss(){
 return readFileSync(new URL("../satellite_center/browser/browser.css",import.meta.url),"utf8");
}
