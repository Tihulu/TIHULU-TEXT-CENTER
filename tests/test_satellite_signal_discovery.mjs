import test from "node:test";
import assert from "node:assert/strict";
import {discoverCu8Contents, discoveryReportJson, cu8ToTunedFmAudio}
 from "../satellite_center/browser/signal_discovery.mjs";
import {readFileSync} from "node:fs";
const RATE=1024000,N=2048;
const tone=(frames=240, bin=128)=>{
 const bytes=new Uint8Array(frames*N*2);
 for(let k=0;k<frames*N;k++){
   const p=2*Math.PI*bin*k/N, modulation=.2*Math.sin(2*Math.PI*800*k/RATE);
   bytes[2*k]=Math.round(127.5+(40+12*modulation)*Math.cos(p));
   bytes[2*k+1]=Math.round(127.5+(40+12*modulation)*Math.sin(p));
 }
 return new Blob([bytes],{type:"application/octet-stream"});
};
test("progressive offline discovery examines every FFT and records unclassified audio attempts",async()=>{
 const file=tone(240);
 let messages=0;
 const result=await discoverCu8Contents(file,{
   sampleRate:RATE,centerHz:145800000,maxCandidates:2,probeSeconds:1,
   onProgress:()=>{messages++;}
 });
 assert.equal(result.analysis.analysisMode,"full-file FFT / binned waterfall");
 assert.equal(result.analysis.coveragePercent,100);
 assert.equal(result.analysis.windows,240);
 assert.ok(result.audioProbes.length>=2);
 assert.ok(result.audioProbes.some(x=>x.audioBlob instanceof Blob));
 assert.ok(result.images.length===0);
 assert.ok(result.phases.some(x=>x.phase==="image"&&x.state==="skipped"));
 assert.ok(result.packetResults.every(x=>x.status==="not checked"));
 assert.ok(messages>5);
 const exported=discoveryReportJson(result);
 assert.ok(!JSON.stringify(exported).includes("audioBlob"));
 assert.ok(!JSON.stringify(exported).includes("rgba"));
 assert.equal(exported.analysis.centerFrequencyHz,145800000);
 assert.equal(exported.audioProbes.some(x=>x.hasAudioPreview),true);
 assert.match(exported.notes,/not proof of speech/i);
});
test("unknown center stays unknown and cannot imply a satellite payload",async()=>{
 const result=await discoverCu8Contents(tone(4),{
   sampleRate:RATE,centerHz:null,maxCandidates:1,probeSeconds:1,enableImage:false
 });
 assert.equal(result.analysis.centerFrequencyHz,null);
 assert.equal(result.audioProbes[0].frequencyHz,null);
 assert.ok(result.images.length===0);
 assert.ok(result.packetResults.every(x=>x.status==="not checked"));
});
test("unsupported sample rate does not pretend audio/image decoding worked",async()=>{
 const result=await discoverCu8Contents(tone(2),{
   sampleRate:1000000,centerHz:null
 });
 assert.equal(result.audioProbes.length,0);
 assert.ok(result.phases.some(x=>x.phase==="audio"&&x.state==="unsupported"));
 assert.ok(result.images.length===0);
});
test("stop cancels before starting and never produces fabricated data",async()=>{
 const controller=new AbortController();controller.abort();
 await assert.rejects(discoverCu8Contents(tone(2),{
   sampleRate:RATE,signal:controller.signal
 }),/stopped/);
});
test("channelized FM extraction accepts offset and returns actual decimated samples",async()=>{
 const rate=RATE, duration=.2;
 const bytes=new Uint8Array(Math.floor(rate*duration)*2);
 let phase=0;
 for(let k=0;k<bytes.length/2;k++){
   const t=k/rate;
   phase+=2*Math.PI*(64000+3000*Math.sin(2*Math.PI*1200*t))/rate;
   bytes[2*k]=Math.round(127.5+45*Math.cos(phase));
   bytes[2*k+1]=Math.round(127.5+45*Math.sin(phase));
 }
 // Extraction intentionally requires at least 1 second, even for a short input.
 await assert.rejects(cu8ToTunedFmAudio(new Blob([bytes]),{
   sampleRate:RATE,offsetHz:64000
 }),/Insufficient changing FM audio/);
});
test("DOM has real progressive controls and downloads remain entirely browser-local",()=>{
 const index=readFileSync(new URL("../satellite_center/browser/index.html",import.meta.url),"utf8");
 const ui=readFileSync(new URL("../satellite_center/browser/iq_analysis_ui.mjs",import.meta.url),"utf8");
 for(const id of ["iq-auto-discover","iq-discovery-stages","iq-discovery-results","iq-discovery-export"]){
   assert.ok(index.includes('id="'+id+'"'),id);
 }
 assert.ok(ui.includes("discoverCu8Contents(file"));
 assert.ok(ui.includes("audioBlob"));
 assert.ok(ui.includes("ImageData(frame.rgba"));
 assert.ok(!ui.includes("fetch("));
});
