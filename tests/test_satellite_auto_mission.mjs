import test from "node:test";
import assert from "node:assert/strict";
import {AUTO_PRESETS,AUTO_TARGETS,selectAutomaticPasses} from "../satellite_center/browser/auto_mission.mjs";

const now=Date.UTC(2026,10,6,18,0,0);
const pass=(id,aos,span=540000,maximum=65)=>({
 id,name:"NORAD "+id,family:id===25544?"iss":"meteor",
 aos:now+aos,los:now+aos+span,maximum
});
test("Single-click image mission selection only chooses supported real frequencies",()=>{
 const p=[pass(57166,3600000),pass(59051,7000000),pass(25544,10000000),pass(99999,15000000)];
 const result=selectAutomaticPasses(p,{mode:"images",now,maxJobs:6});
 assert.equal(result.scheduled.length,3);
 assert.deepEqual(result.scheduled.map(x=>x.missionId),["meteor-m2-3","meteor-m2-4","iss-sstv"]);
 assert.deepEqual(result.scheduled.map(x=>x.frequency),[137900000,137900000,437550000]);
 assert.ok(result.scheduled.every(x=>x.sampleRate===1024000&&x.saveRaw&&x.durationSeconds===60));
});
test("One radio never auto-schedules overlapping missions",()=>{
 const passes=[pass(25544,3600000),pass(57166,3650000),pass(59051,6000000)];
 const result=selectAutomaticPasses(passes,{mode:"all",now,maxJobs:6});
 assert.equal(result.scheduled.length,2);
 assert.equal(result.skipped.length,1);
 assert.match(result.skipped[0].reason,/receiver conflict/);
});
test("Manual pending pass takes priority and all entries remain geometry-only",()=>{
 const result=selectAutomaticPasses([pass(57166,3600000)],{
  now,existingJobs:[{state:"armed",passAos:now+3500000,passLos:now+4000000}]
 });
 assert.equal(result.scheduled.length,0);
 assert.equal(result.skipped.length,1);
 assert.match(result.note,/not.*complete LRPT/);
});
test("APRS UHF is separate from SSTV and no retired/unsupported satellites are armed",()=>{
 const r=selectAutomaticPasses([pass(25544,3600000),pass(57166,4200000)],{now,mode:"messages"});
 assert.equal(r.scheduled.length,1);
 assert.equal(r.scheduled[0].frequency,437825000);
 assert.deepEqual(AUTO_PRESETS.messages,["iss-aprs"]);
 assert.equal(AUTO_TARGETS["iss-aprs"].norad,25544);
 assert.throws(()=>selectAutomaticPasses([],{mode:"noaa",now}),/Unknown/);
 assert.throws(()=>selectAutomaticPasses([],{mode:"images",now,maxJobs:99}),/limits/);
});
