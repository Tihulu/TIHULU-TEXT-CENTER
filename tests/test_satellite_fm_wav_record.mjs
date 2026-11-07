import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {createStreamingFmWavEncoder,createPcmWavHeader,wavOutputPlan}
 from "../satellite_center/browser/fm_wav_record.mjs";

function modulatedRealCu8(rate,seconds,tone=1200){
 const count=Math.round(rate*seconds),bytes=new Uint8Array(count*2);
 let phase=0;
 for(let i=0;i<count;i++){
   const audio=Math.sin(2*Math.PI*tone*i/rate);
   phase+=2*Math.PI*(2300*audio)/rate;
   bytes[2*i]=Math.round(127.5+88*Math.cos(phase));
   bytes[2*i+1]=Math.round(127.5+88*Math.sin(phase));
 }
 return bytes;
}
function fmSamples(pcm){
 const v=new DataView(pcm.buffer,pcm.byteOffset,pcm.byteLength);
 return Float32Array.from({length:pcm.length/2},(_,i)=>v.getInt16(2*i,true)/32768);
}
function syncZeros(samples,rate,startSeconds){
 let n=0;
 for(let i=Math.floor(rate*startSeconds)+1;i<samples.length;i++)
   if(samples[i-1]<0&&samples[i]>=0)n++;
 return n/((samples.length/rate)-startSeconds);
}

test("WAV stream budget allows short clips and safely streams long full-pass files",()=>{
 assert.equal(wavOutputPlan(60,true).mode,"memory");
 assert.equal(wavOutputPlan(900,true,{fileStreaming:true}).mode,"disk-stream");
 assert.equal(wavOutputPlan(900,false).mode,"disabled");
 assert.throws(()=>wavOutputPlan(900,true),/disk file/);
 assert.throws(()=>wavOutputPlan(901,true),/1–900/);
});

test("48 kHz RIFF header has real correct mono 16-bit PCM parameters",()=>{
 const wav=createPcmWavHeader(48000*2);
 const v=new DataView(wav.buffer);
 assert.equal(String.fromCharCode(...wav.slice(0,4)),"RIFF");
 assert.equal(String.fromCharCode(...wav.slice(8,12)),"WAVE");
 assert.equal(String.fromCharCode(...wav.slice(36,40)),"data");
 assert.equal(v.getUint32(4,true),36+96000);
 assert.equal(v.getUint16(20,true),1);
 assert.equal(v.getUint16(22,true),1);
 assert.equal(v.getUint32(24,true),48000);
 assert.equal(v.getUint32(28,true),96000);
 assert.equal(v.getUint16(34,true),16);
 assert.equal(v.getUint32(40,true),96000);
 assert.throws(()=>createPcmWavHeader(-1),/Invalid/);
});

test("actual phase-modulated CU8 produces nonzero WAV samples at the original audio tone",()=>{
 const rate=1024000,iq=modulatedRealCu8(rate,.6,1200);
 const encoder=createStreamingFmWavEncoder(rate);
 const pcm=encoder.push(iq);
 const out=fmSamples(pcm),report=encoder.report();
 assert.equal(report.outputRate,48000);
 assert.ok(report.durationSeconds>.59&&report.durationSeconds<=.6,JSON.stringify(report));
 assert.ok(out.some(v=>Math.abs(v)>.02),"Real RF audio must contain an actual waveform");
 const hz=syncZeros(out,48000,.2);
 assert.ok(hz>1130&&hz<1270,"Expected 1.2 kHz FM SSTV tone; got "+hz);
 assert.equal(encoder.pcmBytes,pcm.length);
 assert.equal(new DataView(encoder.makeHeader().buffer).getUint32(40,true),pcm.length);
 assert.equal(report.verifiedRobot36,false);
 assert.equal(report.verifiedSpacecraft,false);
});

test("odd-length USB packet splits preserve continuous decoder phase and PCM without gaps",()=>{
 const rate=2048000,iq=modulatedRealCu8(rate,.17,1900);
 const single=createStreamingFmWavEncoder(rate).push(iq);
 const split=createStreamingFmWavEncoder(rate);
 const frames=[split.push(iq.subarray(0,999)),split.push(iq.subarray(999,2746)),
   split.push(iq.subarray(2746,40002)),split.push(iq.subarray(40002))];
 const all=new Uint8Array(frames.reduce((n,p)=>n+p.length,0));
 let at=0;for(const p of frames){all.set(p,at);at+=p.length;}
 assert.deepEqual(all,single);
});

test("unmodulated radio carrier does not fabricate an image",()=>{
 const bytes=new Uint8Array(1024000*2/4);bytes.fill(128);
 const encoder=createStreamingFmWavEncoder(1024000);
 const pcm=encoder.push(bytes);
 const peak=Math.max(...fmSamples(pcm).subarray(0,2000).map(Math.abs));
 assert.ok(peak<.03,"Static IQ should not synthesize loud FM");
 assert.equal(encoder.report().verifiedRobot36,false);
});

test("web UI exposes manual, scheduled and automatic ISS WAV modes",()=>{
 const root=new URL("../satellite_center/browser/",import.meta.url);
 const html=readFileSync(new URL("index.html",root),"utf8");
 const app=readFileSync(new URL("browser.js",root),"utf8");
 const native=readFileSync(new URL("schedule_controller.mjs",root),"utf8");
 for(const id of ["record","wav-record","image-decode-last-wav"])
   assert.ok(html.includes('id="'+id+'"'),id);
 assert.match(app,/createStreamingFmWavEncoder/);
 assert.match(app,/await finalizeWav\(\)/);
 assert.match(app,/wavDiskPrepared/);
 assert.match(app,/selectedWav=item\.missionId==='iss-sstv'/);
 assert.match(native,/wavOutputPlan/);
});
