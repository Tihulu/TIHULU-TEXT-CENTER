import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {analyzeFullCu8Blob,detectSpectralCandidates,demodulateCu8Preview} from "../satellite_center/browser/iq_intelligence.mjs";

const RATE=1024000,N=2048;
function tone(blocks=160,bin=128){
 const bytes=new Uint8Array(blocks*N*2);
 for(let k=0;k<blocks*N;k++){
   const phase=2*Math.PI*bin*k/N;
   bytes[2*k]=Math.round(127.5+50*Math.cos(phase));
   bytes[2*k+1]=Math.round(127.5+50*Math.sin(phase));
 }
 return bytes;
}
test("full IQ analysis processes ALL complete blocks with bounded slices",async()=>{
 const bytes=tone(160,128),blob=new Blob([bytes]);
 let largest=0,totalRead=0;
 const monitored={size:blob.size,slice:(a,b)=>{
   largest=Math.max(largest,b-a);totalRead+=b-a;return blob.slice(a,b);
 }};
 const report=await analyzeFullCu8Blob(monitored,{sampleRate:RATE,centerHz:145800000,
   maxWaterfallRows:24});
 assert.equal(report.analysisMode,"full-file FFT / binned waterfall");
 assert.equal(report.windows,160);
 assert.equal(report.coveragePercent,100);
 assert.equal(report.sampledBytes,blob.size);
 assert.equal(totalRead,blob.size);
 assert.ok(largest<=64*N*2);
 assert.equal(report.peakOffsetHz,64000);
 assert.equal(report.peakFrequencyHz,145864000);
 assert.ok(report.peakVsMedianDb>15);
 assert.equal(report.waterfallDb.length,24);
 assert.equal(report.waterfallDb[0].length,256);
 assert.ok(report.signalCandidates.length>0);
 assert.equal(report.signalCandidates[0].classification,"Unclassified spectral energy");
});
test("trailing partial FFT is excluded without claiming perfect coverage",async()=>{
 const b=new Blob([tone(3),new Uint8Array(200)]);
 const r=await analyzeFullCu8Blob(b,{sampleRate:RATE});
 assert.equal(r.windows,3);assert.equal(r.ignoredTrailingBytes,200);
 assert.ok(r.coveragePercent<100);
});
test("unknown center stays unknown in spectral candidate output",()=>{
 const spectrum=Array(2048).fill(-72);
 for(let k=1300;k<1330;k++)spectrum[k]=-35;
 const a=detectSpectralCandidates(spectrum,RATE);
 assert.ok(a.length>0);
 assert.equal(a[0].peakFrequencyHz,null);
 assert.ok(a[0].peakOffsetHz>0);
});
test("full analysis stops when requested and validates CU8 input",async()=>{
 const ctrl=new AbortController();ctrl.abort();
 await assert.rejects(analyzeFullCu8Blob(new Blob([tone(3)]),
  {sampleRate:RATE,signal:ctrl.signal}),/stopped/);
 await assert.rejects(analyzeFullCu8Blob(new Blob([new Uint8Array(4097)]),
  {sampleRate:RATE}),/missing a complete/);
});
test("experimental analog AM preview produces playable PCM WAV without uploads",async()=>{
 const bytes=new Uint8Array(N*40*2);
 for(let k=0;k<N*40;k++){
   const env=.48+.18*Math.sin(2*Math.PI*1100*k/RATE);
   bytes[k*2]=Math.round(127.5+100*env);bytes[k*2+1]=128;
 }
 const result=await demodulateCu8Preview(new Blob([bytes]),{
   sampleRate:RATE,mode:"am",offsetHz:0,durationSec:1
 });
 assert.ok(result.seconds>.05);
 assert.equal(result.mode,"am");
 const header=new Uint8Array(await result.blob.slice(0,12).arrayBuffer());
 assert.equal(String.fromCharCode(...header.slice(0,4)),"RIFF");
 assert.equal(String.fromCharCode(...header.slice(8,12)),"WAVE");
});
test("browser UI has explicit full scan, abort, candidate selection, metadata and audio playback",()=>{
 const html=readFileSync(new URL("../satellite_center/browser/index.html",import.meta.url),"utf8");
 const ui=readFileSync(new URL("../satellite_center/browser/iq_analysis_ui.mjs",import.meta.url),"utf8");
 for(const id of ["iq-analyze-full","iq-stop-analysis","iq-candidates","iq-audio-offset",
 "iq-audio-mode","iq-audio-preview","iq-audio-player","iq-export-metadata"]){
   assert.ok(html.includes('id="'+id+'"'),id);
 }
 assert.match(ui,/analyzeFullCu8Blob/);
 assert.match(ui,/demodulateCu8Preview/);
 assert.match(ui,/activeController\.abort/);
 assert.ok(!ui.includes("fetch(")); // data stay on the device
});
