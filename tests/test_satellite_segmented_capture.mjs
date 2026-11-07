import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {durationToSeconds,formatCountdown,segmentedCapturePlan,browserClipCap}
 from "../satellite_center/browser/segmented_capture.mjs";

const t=Date.UTC(2026,10,10,1,0);
const plan=(total,rate=1024000,extra={})=>segmentedCapturePlan({
 startMs:t,totalSeconds:total,rate,saveRaw:true,saveWav:false,
 passEndMs:t+900000,...extra
});
test("300 s at 1.024 MS/s becomes five separately timed 60 s CU8 files, not a 614 MB buffer",()=>{
 const p=plan(300);
 assert.deepEqual(p.segments.map(s=>s.durationSeconds),[60,60,60,60,60]);
 assert.equal(p.segmentCount,5);
 assert.equal(p.estimatedBytes,614400000);
 assert.equal(p.unrecordedGapSeconds,8);
 assert.equal(p.wallSeconds,308);
 assert.deepEqual(p.segments.map(s=>(s.when-t)/1000),[0,62,124,186,248]);
 assert.equal(p.segments[4].end-t,308000);
 for(const clip of p.segments)assert.ok(clip.durationSeconds*1024000*2<=128*1024*1024);
});
test("2.048 MS/s raw CU8 is capped at 32 s to remain below 128 MiB",()=>{
 const p=plan(300,2048000);
 assert.equal(browserClipCap(2048000,true),32);
 assert.equal(p.segmentCount,10);
 assert.deepEqual(p.segments.map(s=>s.durationSeconds),Array(10).fill(30));
 assert.equal(p.unrecordedGapSeconds,18);
 assert.equal(p.wallSeconds,318);
 for(const s of p.segments)assert.ok(s.estimatedBytes<=128*1024*1024);
});
test("small remainder is balanced instead of spawning a one-second tail",()=>{
 assert.deepEqual(plan(61).segments.map(p=>p.durationSeconds),[31,30]);
 assert.equal(plan(60).segments.length,1);
 assert.equal(plan(1).segments.length,1);
 const audio=plan(300,2048000,{saveRaw:false,saveWav:true});
 assert.equal(audio.segmentCount,5);
 assert.equal(audio.segments[0].estimatedBytes,5760044);
});
test("minutes and seconds represent exact intended RF acquisition lengths",()=>{
 assert.equal(durationToSeconds(300,"seconds"),300);
 assert.equal(durationToSeconds(5,"minutes"),300);
 assert.equal(durationToSeconds(.5,"minutes"),30);
 assert.equal(durationToSeconds(.283333,"minutes"),17);
 assert.throws(()=>durationToSeconds(0,"minutes"),/positive/);
 assert.throws(()=>durationToSeconds(15.01,"minutes"),/900/);
 assert.throws(()=>plan(901),/900/);
});
test("series refuses to record beyond predicted pass or overlap arbitrary unsafe caps",()=>{
 assert.throws(()=>plan(300,1024000,{passEndMs:t+307000}),/receiver reset gaps/);
 assert.throws(()=>plan(300,1024000,{gapSeconds:-1}),/gap/);
 assert.throws(()=>plan(300,123456),/sample rate/);
});
test("every scheduled countdown explicitly shows days, hours, minutes, seconds",()=>{
 assert.equal(formatCountdown(0),"0d 00h 00m 00s");
 assert.equal(formatCountdown(300000),"0d 00h 05m 00s");
 assert.equal(formatCountdown(90061000),"1d 01h 01m 01s");
});
test("all browser surfaces expose grouped scheduling, time units and calendar part labels",()=>{
 const base=new URL("../satellite_center/browser/",import.meta.url);
 const source=name=>readFileSync(new URL(name,base),"utf8");
 const index=source("index.html"),main=source("browser.js"),
       reception=source("reception.html"),receptionJs=source("auto_reception_ui.mjs"),
       cal=source("satellite_calendar.mjs"),auto=source("auto_mission.mjs");
 for(const id of ["duration-unit","auto-browser-unit","auto-browser-seconds","browser-calendar-grid"])
   assert.match(index,new RegExp('id="'+id+'"'));
 assert.match(reception,/id="auto-recording-unit"/);
 assert.match(receptionJs,/readAutoLength/);
 assert.match(main,/scheduleBrowserSegments/);
 assert.match(main,/addScheduledBatch\(batch\)/);
 assert.match(main,/formatCountdown\(job.when-now\)/);
 assert.match(main,/job.segmentIndex/);
 assert.match(cal,/Part /);
 assert.match(auto,/durationSeconds>900/);
 assert.match(main,/\/api\/schedule-series/);
});
