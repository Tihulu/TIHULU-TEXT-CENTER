import test from "node:test";
import assert from "node:assert/strict";
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
