import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {planChainedCapture,secondsFromEntry,humanCountdown,scheduledOverlap}
  from "../satellite_center/browser/chained_capture.mjs";
const root=new URL("../satellite_center/browser/",import.meta.url);
const file=x=>readFileSync(new URL(x,root),"utf8");
const start=Date.UTC(2026,10,7,1,41,0);

test("300s Meteor at 1.024 MSPS = five 60s independent CU8 jobs in calendar",()=>{
 const plan=planChainedCapture({startMs:start,totalSeconds:300,rate:1024000,
  raw:true,wav:false,untilMs:start+360000});
 assert.deepEqual(plan.segments.map(s=>s.durationSeconds),[60,60,60,60,60]);
 assert.deepEqual(plan.segments.map(s=>(s.when-start)/1000),[0,66,132,198,264]);
 assert.equal(plan.elapsedSeconds,324);
 assert.equal(plan.totalGapSeconds,24);
 assert.equal(plan.segments.reduce((n,s)=>n+s.estimatedRawBytes,0),614400000);
 assert.ok(plan.segments.every(s=>s.estimatedRawBytes<=128*1024*1024));
 assert.ok(plan.gapsPossible);
 assert.match(plan.warning,/NOT continuous/);
});

test("2.048 MSPS automatically reduces each browser CU8 part below 128 MiB",()=>{
 const plan=planChainedCapture({startMs:start,totalSeconds:300,rate:2048000,
  raw:true,wav:true});
 assert.equal(plan.segments.length,10);
 assert.equal(plan.segments[0].durationSeconds,32);
 assert.ok(plan.segments.every(s=>s.estimatedRawBytes<=128*1024*1024));
 assert.ok(plan.segments.every(s=>s.durationSeconds<=60));
});

test("WAV-only also splits above 60s and both formats keep separate accurate budgets",()=>{
 const plan=planChainedCapture({startMs:start,totalSeconds:125,rate:1024000,raw:true,wav:true});
 assert.deepEqual(plan.segments.map(s=>s.durationSeconds),[60,60,5]);
 assert.equal(plan.segments.length,3);
 assert.ok(plan.segments.every(s=>s.estimatedRawBytes>0&&s.estimatedWavBytes>0));
});

test("minutes / seconds input supports 5 minutes, bounds and clear countdown",()=>{
 assert.equal(secondsFromEntry(5,"minutes"),300);
 assert.equal(secondsFromEntry(300,"seconds"),300);
 assert.equal(secondsFromEntry(120,"minutes"),7200);
 assert.throws(()=>secondsFromEntry(121,"minutes"),/120 minutes/);
 assert.throws(()=>secondsFromEntry(1.5,"minutes"),/whole/);
 assert.equal(humanCountdown(93784),"1d 02h 03m 04s");
 assert.equal(humanCountdown(0),"0d 00h 00m 00s");
});

test("pass LOS is enforced against full wall-clock time including restart gaps",()=>{
 assert.throws(()=>planChainedCapture({startMs:start,totalSeconds:300,
   rate:1024000,untilMs:start+310000}),/beyond/);
 assert.equal(planChainedCapture({startMs:start,totalSeconds:300,
   rate:1024000,untilMs:start+324000}).segments.length,5);
});

test("new planned chain cannot overlap an armed receiver from another pass",()=>{
 const a={when:start,durationSeconds:60},b={when:start+66000,durationSeconds:60};
 assert.equal(scheduledOverlap(a,b),false);
 assert.equal(scheduledOverlap(a,{when:start+59000,durationSeconds:60}),true);
 assert.equal(scheduledOverlap(a,b,{guardSeconds:7}),true);
});

test("manual, auto and editable calendar all rely on same bounded chain plan",()=>{
 const app=file("browser.js"),index=file("index.html"),
   images=file("reception.html"),external=file("auto_reception_ui.mjs");
 for(const id of ["duration-unit","auto-browser-unit","browser-calendar-grid"])
   assert.match(index,new RegExp('id="'+id+'"'),id);
 assert.match(images,/id="auto-recording-unit"/);
 assert.match(app,/function buildBrowserChain/);
 assert.match(app,/function addBrowserChain/);
 assert.match(app,/planChainedCapture\(\{startMs:Date\.now\(\)\+1500/);
 assert.match(app,/humanCountdown\(secondsToJob\(job,now\)\)/);
 assert.match(app,/oldGroup=jobs\.filter/);
 assert.match(app,/selectedRaw=item\.missionId==='iss-sstv'/);
 assert.match(external,/tihulu-auto-browser-unit/);
 assert.match(app,/Downloads may require multiple-file approval/);
 assert.match(index,/128 MiB/);
});
