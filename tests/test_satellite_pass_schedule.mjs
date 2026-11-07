import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import {sortPassList,sortSatelliteList,nextPassForSatellite} from "../satellite_center/browser/pass_sort.mjs";
import {localDateInput,parseLocalScheduleTime,createScheduledPass,evaluateScheduledJob,
 secondsToJob,captureLevelSummary} from "../satellite_center/browser/schedule_controller.mjs";
import {mapShouldFallback} from "../satellite_center/browser/satellite_maps.mjs";

const now=Date.UTC(2026,10,6,10,0);
const passes=[
 {id:1,name:"ISS",family:"iss",aos:now+60000,los:now+240000,maximum:65},
 {id:2,name:"Meteor",family:"meteor",aos:now+900000,los:now+1200000,maximum:22},
 {id:3,name:"IRIDIUM",family:"iridium",aos:now+3600000,los:now+3660000,maximum:47},
 {id:4,name:"CubeSat",family:"cubesat",aos:now+1800000,los:now+1920000,maximum:11}
];
test("sort passes soonest/latest and elevation/duration without mutating orbital records",()=>{
 const before=JSON.stringify(passes);
 assert.deepEqual(sortPassList(passes,"soonest").map(p=>p.id),[1,2,4,3]);
 assert.deepEqual(sortPassList(passes,"latest").map(p=>p.id),[3,4,2,1]);
 assert.deepEqual(sortPassList(passes,"elevation-high").map(p=>p.id),[1,3,2,4]);
 assert.deepEqual(sortPassList(passes,"duration-long").map(p=>p.id),[2,1,4,3]);
 assert.deepEqual(sortPassList(passes,"duration-short").map(p=>p.id),[3,4,1,2]);
 assert.deepEqual(sortPassList(passes,"latest","iridium").map(p=>p.id),[3]);
 assert.equal(JSON.stringify(passes),before);
});
test("sky list next-farthest / nearest dates use pass catalog and keep unknown passes last",()=>{
 const sats=[{id:1,name:"ISS",el:20,rangeKm:1100},{id:2,name:"Meteor",el:40,rangeKm:500},
  {id:3,name:"IRIDIUM",el:-5,rangeKm:2500},{id:99,name:"Unknown",el:-20,rangeKm:3000}];
 assert.deepEqual(sortSatelliteList(sats,"next-soonest",passes,now).map(s=>s.id),[1,2,3,99]);
 assert.deepEqual(sortSatelliteList(sats,"next-latest",passes,now).map(s=>s.id),[3,2,1,99]);
 assert.deepEqual(sortSatelliteList(sats,"elevation-high",passes,now).map(s=>s.id),[2,1,3,99]);
 assert.equal(nextPassForSatellite(sats[3],passes,now),null);
});
test("minute-precision capture scheduling validates real pass bounds",()=>{
 const pass=passes[1],options={frequency:137900000,sampleRate:1024000,durationSeconds:30,saveRaw:true,
 when:pass.aos};
 const job=createScheduledPass(pass,options,now);
 assert.equal(job.when,pass.aos);assert.equal(job.state,"armed");
 assert.equal(job.durationSeconds,30);assert.equal(job.saveRaw,true);
 assert.equal(parseLocalScheduleTime(localDateInput(pass.aos)),pass.aos);
 assert.throws(()=>createScheduledPass(pass,{...options,when:now-60000},now),/past/);
 assert.throws(()=>createScheduledPass(pass,{...options,when:pass.los},now),/pass/);
 assert.throws(()=>createScheduledPass(pass,{...options,when:pass.los-10000},now),/finish before/);
 assert.equal(createScheduledPass(pass,{...options,when:pass.los-30000},now).durationSeconds,30);
 assert.throws(()=>createScheduledPass(pass,{...options,durationSeconds:400},now),/finish before/);
 const longPass={...pass,los:pass.aos+900000};
 assert.throws(()=>createScheduledPass(longPass,{...options,durationSeconds:600},now),/native receiver|disk saving|local disk|Long RF samples/);
 const diskJob=createScheduledPass(longPass,{...options,durationSeconds:600,diskStreamPrepared:true},now);
 assert.equal(diskJob.diskStreamPrepared,true);
 assert.equal(diskJob.durationSeconds,600);
 assert.throws(()=>createScheduledPass(pass,{...options,frequency:5000000000},now),/range/);
});
test("browser foreground, receiver conflicts and missed passes are explicit statuses",()=>{
 const job=createScheduledPass(passes[0],{frequency:145800000,sampleRate:1024000,durationSeconds:15,saveRaw:false,when:passes[0].aos},now);
 assert.equal(evaluateScheduledJob(job,now,{visible:true,receiverBusy:false}),"waiting");
 assert.equal(secondsToJob(job,now),60);
 assert.equal(evaluateScheduledJob(job,job.when,{visible:false,receiverBusy:false}),"waiting-foreground");
 assert.equal(evaluateScheduledJob(job,job.when,{visible:true,receiverBusy:true}),"waiting-receiver");
 assert.equal(evaluateScheduledJob(job,job.when,{visible:true,receiverBusy:false}),"start");
 assert.equal(evaluateScheduledJob(job,job.until-job.durationSeconds*1000,{visible:true,receiverBusy:false}),"start");
 assert.equal(evaluateScheduledJob(job,job.until-job.durationSeconds*1000+1,{visible:true,receiverBusy:false}),"missed");
 assert.equal(evaluateScheduledJob(job,job.until,{visible:true,receiverBusy:false}),"missed");
});
test("measured I/Q summary is uncalibrated and never fabricates decoded satellites",()=>{
 const report=captureLevelSummary([-42,-40,-39,-41],524288,2200);
 assert.equal(report.bytesReceived,524288);
 assert.equal(report.blocksMeasured,4);assert.equal(report.minRelativeDb,-42);
 assert.equal(report.maxRelativeDb,-39);assert.equal(report.levelVariationDb,3);
 assert.match(report.interpretation,/no transmitter identity/);
 assert.equal(captureLevelSummary([],0,0).averageRelativeDb,null);
});
test("map tiles fall back only after failed/no real raster images",()=>{
 assert.equal(mapShouldFallback(0,0,9000),true);
 assert.equal(mapShouldFallback(0,3,1500),true);
 assert.equal(mapShouldFallback(1,30,9000),false);
 assert.equal(mapShouldFallback(0,0,4000),false);
});
test("UI has pass/satellite sorting and actionable scheduler/preflight controls",()=>{
 const html=fs.readFileSync(new URL("../satellite_center/browser/index.html",import.meta.url),"utf8");
 const app=fs.readFileSync(new URL("../satellite_center/browser/browser.js",import.meta.url),"utf8");
 const map=fs.readFileSync(new URL("../satellite_center/browser/satellite_maps.mjs",import.meta.url),"utf8");
 for(const id of ["pass-sort","pass-family","pass-show-more","map-sat-sort","schedule-check",
   "schedule-wake","schedule-readiness","scheduled-report","map-basemap","map-basemap-state"])
   assert.ok(html.includes('id="'+id+'"'),id+" missing");
 assert.ok(app.includes("connectDevice({silent:true})"));
 assert.ok(app.includes("nativeScheduledPass("));
 assert.ok(app.includes('nativeRequest(endpoint')&&app.includes('"/api/schedule-chain"'));
 assert.ok(html.includes('href="http://127.0.0.1:8791/"'));
 assert.ok(app.includes("navigator.usb.getDevices()"));
 assert.ok(app.includes("localDateInput("));
 assert.ok(app.includes("captureLevelSummary("));
 assert.ok(app.includes("passes=found;"));
 assert.ok(app.includes("latest")||html.includes("Latest / farthest date first"));
 assert.ok(map.includes('natural-earth-land-110m.geojson'));
 assert.ok(map.includes('referrerPolicy:"strict-origin-when-cross-origin"'));
});

test("Repeated browser ticks update countdown in place, preserving opened controls",()=>{
 const js=fs.readFileSync(new URL("../satellite_center/browser/browser.js",import.meta.url),"utf8");
 assert.match(js,/signature===lastRenderedJobCardsSignature/);
 assert.match(js,/panel\.querySelector\('\.job-state'\)/);
 assert.match(js,/editingCard&&editedJob\?\.state==='armed'/);
});

test("Native dashboard status polling leaves unchanged options and cards mounted",()=>{
 const native=fs.readFileSync(new URL("../satellite_center/index.html",import.meta.url),"utf8");
 assert.match(native,/document\.activeElement===el/);
 assert.match(native,/signature===lastNativeJobsSignature/);
 assert.match(native,/signature===lastNativeArchiveSignature/);
});

test("Pass list waits for native selector focus to end before replacing its DOM",()=>{
 const js=fs.readFileSync(new URL("../satellite_center/browser/browser.js",import.meta.url),"utf8");
 assert.match(js,/passRenderDeferred=true;return/);
 assert.match(js,/document\.activeElement\.matches\?\.\('select,input,textarea'\)/);
 assert.match(js,/queueMicrotask\(/);
});
