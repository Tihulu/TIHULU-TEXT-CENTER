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
 assert.equal(result.scheduled.length,1);
 assert.deepEqual(result.scheduled.map(x=>x.missionId),["iss-sstv"]);
 assert.deepEqual(result.scheduled.map(x=>x.frequency),[437550000]);
 assert.equal(result.skipped.length,2);
 assert.ok(result.skipped.every(x=>/native SatDump/.test(x.reason)));
 assert.ok(result.scheduled.every(x=>x.sampleRate===1024000&&x.saveRaw&&x.durationSeconds===60));
});
test("Single receiver still rejects overlap between two ISS passes",()=>{
 const passes=[pass(25544,3600000),pass(25544,3650000),pass(25544,6000000)];
 const result=selectAutomaticPasses(passes,{mode:"all",now,maxJobs:6});
 assert.equal(result.scheduled.length,2);
 assert.equal(result.skipped.length,1);
 assert.match(result.skipped[0].reason,/receiver conflict/);
});
test("Explicit short-sample mode can record Meteor RF but never promise an Earth picture",()=>{
 const result=selectAutomaticPasses([pass(57166,3600000)],{mode:"images",goal:"sample",now});
 assert.equal(result.scheduled.length,1);
 assert.equal(result.scheduled[0].coverage,"partial-pass");
 assert.match(result.scheduled[0].limitation,/RF sample only/);
 assert.equal(result.scheduled[0].estimatedBytes,122880000);
});
test("Manual pending pass takes priority and all entries remain geometry-only",()=>{
 const result=selectAutomaticPasses([pass(25544,3600000)],{
  now,existingJobs:[{state:"armed",passAos:now+3500000,passLos:now+4000000}]
 });
 assert.equal(result.scheduled.length,0);
 assert.equal(result.skipped.length,1);
 assert.match(result.note,/full Meteor imagery needs native/i);
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

test("Automatic 60-second recordings never overrun a predicted pass",()=>{
 const tooShort=pass(25544,3600000,49000);
 const valid=pass(25544,7200000,60000);
 const result=selectAutomaticPasses([tooShort,valid],{mode:"images",now});
 assert.equal(result.skipped.length,1);
 assert.match(result.skipped[0].reason,/too short/);
 assert.deepEqual(result.scheduled.map(x=>x.missionId),["iss-sstv"]);
 assert.ok(result.scheduled.every(x=>x.when+x.durationSeconds*1000<=x.until));
});

test("All mode alternates ISS image and packet frequencies between passes",()=>{
 const twice=[pass(25544,3600000),pass(25544,5400000)];
 const r=selectAutomaticPasses(twice,{mode:"all",now,maxJobs:6});
 assert.deepEqual(r.scheduled.map(x=>x.missionId),["iss-sstv","iss-aprs"]);
 assert.deepEqual(r.scheduled.map(x=>x.frequency),[437550000,437825000]);
});

test("Operator can choose bounded WebUSB duration",()=>{
 const selected=pass(25544,3600000,240000);
 const plan=selectAutomaticPasses([selected],{mode:"images",goal:"sample",durationSeconds:25,now});
 assert.equal(plan.scheduled.length,1);
 assert.equal(plan.scheduled[0].durationSeconds,25);
 assert.equal(plan.scheduled[0].estimatedBytes,51200000);
 assert.equal(plan.scheduled[0].coverage,"partial-pass");
 assert.throws(()=>selectAutomaticPasses([selected],{mode:"images",durationSeconds:61,now}),/8–60/);
 assert.throws(()=>selectAutomaticPasses([selected],{mode:"images",durationSeconds:7,now}),/8–60/);
});

test("ISS-only Series 35 mode selects UHF Robot36 without Meteor or APRS",()=>{
 const passes=[pass(25544,3600000),pass(57166,7200000),pass(25544,10800000)];
 const chosen=selectAutomaticPasses(passes,{mode:"iss-images",now,maxJobs:6});
 assert.deepEqual(chosen.scheduled.map(x=>x.missionId),["iss-sstv","iss-sstv"]);
 assert.ok(chosen.scheduled.every(x=>x.frequency===437550000));
 assert.deepEqual(AUTO_PRESETS["iss-images"],["iss-sstv"]);
});

