import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {analyzeIqWindows,analyzeCu8Blob,parseCu8Filename,fftComplex} from "../satellite_center/browser/iq_analysis.mjs";
const FS=1024000,N=2048;
function tone(bin=128,count=16){
 const frames=[];
 for(let frame=0;frame<count;frame++){
   const data=new Uint8Array(N*2);
   for(let i=0;i<N;i++){
     const phase=2*Math.PI*bin*i/N;
     data[2*i]=Math.round(127.5+55*Math.cos(phase));
     data[2*i+1]=Math.round(127.5+55*Math.sin(phase));
   }
   frames.push(data);
 }
 return frames;
}
test("complex FFT frequency of a known positive-offset IQ tone is grounded in raw samples",()=>{
 const report=analyzeIqWindows(tone(128),{
   centerHz:145800000,sampleRate:FS,totalBytes:FS*2*3
 });
 assert.equal(report.fftSize,2048);
 assert.equal(report.peakOffsetHz,64000);
 assert.equal(report.peakFrequencyHz,145864000);
 assert.ok(report.peakVsMedianDb>20);
 assert.equal(report.totalBytes,FS*2*3);
 assert.equal(report.estimatedSeconds,3);
 assert.equal(report.spectrumDb.length,N);
 assert.equal(report.waterfallDb.length,16);
 assert.equal(report.waterfallDb[0].length,256);
 assert.match(report.warning,/not a confirmed satellite/);
});
test("spectral peak correctly handles negative complex baseband frequencies",()=>{
 const report=analyzeIqWindows(tone(-64,8),{sampleRate:FS,centerHz:137900000});
 assert.equal(report.peakOffsetHz,-32000);
 assert.equal(report.peakFrequencyHz,137868000);
});
test("CU8 file format is metadata-free; only TIHULU file name can supply MHz/rate",()=>{
 assert.deepEqual(parseCu8Filename("TIHULU-scheduled-145800000-1024000-2026-11-06T11-20.cu8"),
  {centerHz:145800000,sampleRate:1024000});
 assert.equal(parseCu8Filename("mystery.cu8"),null);
 assert.equal(parseCu8Filename("TIHULU-9999999999-0-other.cu8"),null);
});
test("large local CU8 blobs are sampled at bounded windows, not read fully into RAM",async()=>{
 const single=tone(32,1)[0];
 const bytes=new Uint8Array(single.length*200);
 for(let i=0;i<200;i++)bytes.set(single,i*single.length);
 const b=new Blob([bytes],{type:"application/octet-stream"});
 const result=await analyzeCu8Blob(b,{centerHz:145800000,sampleRate:FS,maxWindows:8});
 assert.equal(result.windows,8);
 assert.equal(result.sampledBytes,8*4096);
 assert.equal(result.totalBytes,bytes.length);
 assert.equal(result.peakOffsetHz,16000);
 assert.ok(result.sampledFraction<0.05);
});
test("CU8 rejects impossible samples, rates and incomplete I/Q pair",async()=>{
 assert.throws(()=>analyzeIqWindows([new Uint8Array(4096)],{sampleRate:0}),/sample rate/);
 await assert.rejects(analyzeCu8Blob(new Blob([new Uint8Array(4097)]),
  {sampleRate:FS}),/odd number/);
 await assert.rejects(analyzeCu8Blob(new Blob([new Uint8Array(3000)]),
  {sampleRate:FS}),/too short/);
});
test("browser wiring supports latest automatic recorded analysis, prior CU8 import and JSON report",()=>{
 const html=readFileSync(new URL("../satellite_center/browser/index.html",import.meta.url),"utf8");
 const app=readFileSync(new URL("../satellite_center/browser/browser.js",import.meta.url),"utf8");
 const ui=readFileSync(new URL("../satellite_center/browser/iq_analysis_ui.mjs",import.meta.url),"utf8");
 for(const id of ["iq-file","iq-center","iq-rate","iq-analyze-last","iq-analyze-file",
  "iq-spectrum","iq-waterfall","iq-power-time","iq-export-json","iq-analysis-summary"]){
   assert.ok(html.includes('id="'+id+'"'),id);
 }
 assert.ok(app.includes("initIqAnalysisUI({log})"));
 assert.ok(app.includes("iqAnalysisUI.record(blob,name,metadata)"));
 assert.ok(ui.includes("analyzeCu8Blob(blob"));
 assert.ok(ui.includes("file.slice")===false); // file chunking remains inside analysis core
 assert.ok(ui.includes("JSON.stringify("));
 assert.ok(!ui.includes("fetch("));
});
