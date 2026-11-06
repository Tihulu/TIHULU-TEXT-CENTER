import test from "node:test";
import assert from "node:assert/strict";
import {captureBudget,formatCaptureBudget,MEMORY_IQ_BYTES,STREAM_IQ_BYTES} from "../satellite_center/browser/capture_duration.mjs";
test("Long image capture uses disk streaming, not memory or pretend 60-second scan",()=>{
 const p=captureBudget(600,1024000,true,{fileStreaming:true});
 assert.equal(p.mode,"disk-stream");
 assert.equal(p.estimatedBytes,1228800000);
 assert.ok(p.estimatedBytes>MEMORY_IQ_BYTES);
 assert.ok(p.estimatedBytes<STREAM_IQ_BYTES);
});
test("Short capture remains memory buffered and duration is editable",()=>{
 assert.equal(captureBudget(15,1024000,true).mode,"memory");
 assert.equal(captureBudget(60,1024000,true).mode,"memory");
 assert.equal(captureBudget(60,2048000,true,{fileStreaming:true}).mode,"disk-stream");
 assert.throws(()=>captureBudget(60,2048000,true,{fileStreaming:false}),/native receiver/);
});
test("Manual duration enforces 2 GB rate limit and browser capability",()=>{
 assert.throws(()=>captureBudget(900,2048000,true,{fileStreaming:true}),/Maximum here: 488 seconds/);
 assert.throws(()=>captureBudget(901,1024000,true,{fileStreaming:true}),/1 to 900/);
 assert.throws(()=>captureBudget(0,1024000),/1 to 900/);
 assert.equal(captureBudget(900,1024000,true,{fileStreaming:true}).mode,"disk-stream");
 assert.equal(captureBudget(900,2048000,false).mode,"levels-only");
 assert.equal(formatCaptureBudget(480,1024000,true,false).ok,false);
});
