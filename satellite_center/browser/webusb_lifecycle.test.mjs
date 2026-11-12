import test from "node:test";
import assert from "node:assert/strict";
import {createOwnedWebUsbGate,captureProgress} from "./webusb_lifecycle.mjs";
import {captureBudget,MEMORY_IQ_BYTES,STREAM_IQ_BYTES} from "./capture_duration.mjs";
import {planChainedCapture} from "./chained_capture.mjs";

test("delayed WebUSB grant cannot claim a receiver after explicit Stop",async()=>{
 const gate=createOwnedWebUsbGate();
 const ticket=gate.begin();
 let resume;
 const delay=new Promise(resolve=>{resume=resolve;});
 let spawned=0;
 const connect=async()=>{await delay;gate.assert(ticket);spawned+=1;};
 const pending=connect();
 gate.cancel();resume();
 await assert.rejects(pending,/cancelled/i);
 assert.equal(spawned,0);
 const newTicket=gate.begin();
 assert.equal(gate.current(newTicket),true);
 assert.equal(gate.current(ticket),false);
});
test("pagehide permanently closes this tab's WebUSB admission",()=>{
 const gate=createOwnedWebUsbGate(),ticket=gate.begin();
 gate.close();
 assert.equal(gate.current(ticket),false);
 assert.equal(gate.closed,true);
 assert.throws(()=>gate.begin(),/closed/);
 assert.throws(()=>gate.assert(ticket),/cancelled/);
});
test("two simultaneous Stop callbacks cannot resurrect a stale USB start",()=>{
 const gate=createOwnedWebUsbGate(),start=gate.begin();
 gate.cancel();gate.cancel();
 assert.equal(gate.current(start),false);
 const manual=gate.begin();
 assert.equal(gate.current(manual),true);
 gate.close();
 assert.equal(gate.current(manual),false);
});
test("progress labels distinguish elapsed estimate from real USB bytes",()=>{
 const progress=captureProgress({startedAt:1000,now:11000,seconds:60,
   observedBytes:65536,rate:1024000});
 assert.equal(progress.percentage,17);
 assert.equal(progress.observedBytes,65536);
 assert.equal(progress.expectedIqBytes,122880000);
 assert.equal(progress.estimateOnly,true);
 assert.equal(progress.complete,false);
 assert.equal(captureProgress({startedAt:0,now:999999,seconds:60,rate:2048000}).percentage,100);
 assert.throws(()=>captureProgress({startedAt:0,now:5,seconds:0,rate:1024000}),/Invalid/);
});
test("CU8 and WAV combination retains explicit segment gaps, rate-specific 128 MiB caps",()=>{
 const plan=planChainedCapture({startMs:1000,totalSeconds:120,rate:2048000,raw:true,wav:true});
 assert.ok(plan.segments.length>=4,"2.048 MS/s needs <=32s in 128 MiB memory");
 assert.equal(plan.totalCaptureSeconds,120);
 assert.ok(plan.totalGapSeconds>0);
 assert.ok(plan.segments.every(x=>x.estimatedRawBytes<=MEMORY_IQ_BYTES));
 assert.ok(plan.segments.every(x=>x.estimatedWavBytes>44));
 assert.match(plan.warning,/NOT continuous/);
 assert.equal(captureBudget(60,1024000,true).mode,"memory");
 assert.throws(()=>captureBudget(60,2048000,true),/streamed local disk/);
 assert.equal(captureBudget(60,2048000,true,{fileStreaming:true}).mode,"disk-stream");
 assert.throws(()=>captureBudget(900,2048000,true,{fileStreaming:true}),/2 GB/);
 assert.ok(STREAM_IQ_BYTES>MEMORY_IQ_BYTES);
});
