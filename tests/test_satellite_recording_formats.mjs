import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {captureBudget} from "../satellite_center/browser/capture_duration.mjs";
import {wavOutputPlan,createStreamingFmWavEncoder,createPcmWavHeader}
 from "../satellite_center/browser/fm_wav_record.mjs";

const root=new URL("../satellite_center/browser/",import.meta.url);
const source=name=>readFileSync(new URL(name,root),"utf8");

test("manual receiver has independent checkboxes and an explicit BOTH selector with confirmation",()=>{
 const html=source("index.html"),js=source("browser.js");
 for(const id of ["record","wav-record","record-both","record-wav-only",
                   "record-cu8-only","capture-format-summary"])
   assert.match(html,new RegExp('id="'+id+'"'),id);
 assert.match(html,/Recording file formats · select one or both/);
 assert.match(html,/type="checkbox" id="record"/);
 assert.match(html,/type="checkbox" id="wav-record"/);
 assert.match(js,/setManualOutputSelection\(true,true\)/);
 assert.match(js,/record-both'\)\.addEventListener\('click'/);
 assert.match(js,/outputSelectionText\(recording,recordingWav\)/);
 assert.match(js,/report\.outputFiles=savedNames/);
});

test("same WebUSB RF block feeds independent CU8 and WAV writers, with real file names",()=>{
 const js=source("browser.js");
 assert.match(js,/if\(fmWav\)\{/);
 assert.match(js,/const pcm=fmWav\.push\(data\)/);
 assert.match(js,/if\(recording\)\{/);
 assert.match(js,/prepared\.writable\.write\(new Uint8Array\(data\)\)/);
 assert.match(js,/prepared\.wavWritable\.write\(pcm\)/);
 assert.match(js,/if\(plan\.rawDisk&&plan\.wavDisk\)/);
 assert.match(js,/showDirectoryPicker/);
 assert.match(js,/getFileHandle\(rawName,\{create:true\}\)/);
 assert.match(js,/getFileHandle\(wavName,\{create:true\}\)/);
 assert.match(js,/CU8: '\+rawFileName/);
 assert.match(js,/WAV: '\+report\.wav\.name/);
});

test("full browser ISS auto workflow exposes user-selected both formats and two-file estimate",()=>{
 const html=source("index.html"),js=source("browser.js");
 for(const id of ["auto-save-raw","auto-save-wav","auto-format-summary"])
   assert.match(html,new RegExp('id="'+id+'"'),id);
 assert.match(js,/saveRaw:item\.missionId==='iss-sstv'\?autoRaw/);
 assert.match(js,/saveWav:item\.missionId==='iss-sstv'\?autoWav/);
 assert.match(js,/saveRaw:item\.missionId==='iss-sstv'\?autoRaw/);
 assert.match(js,/estimatedBytes/);
 assert.match(js,/scheduleBrowserSegments/);
});

test("Satellite Images & Data transfers both choices to the main WebUSB planner",()=>{
 const html=source("reception.html"),reception=source("auto_reception_ui.mjs"),
   main=source("browser.js"),index=source("index.html");
 for(const id of ["reception-auto-wav","reception-auto-raw","reception-format-summary"])
   assert.match(html,new RegExp('id="'+id+'"'),id);
 assert.match(reception,/sessionStorage\.setItem\("tihulu-auto-formats"/);
 assert.match(main,/sessionStorage\.getItem\('tihulu-auto-formats'\)/);
 assert.match(main,/\$\('auto-save-raw'\)\.checked=choice\.raw/);
 assert.match(main,/\$\('auto-save-wav'\)\.checked=choice\.wav/);
 assert.match(html,/Native unattended long jobs split at 180 s/);
 assert.match(index,/WAV · FM audio for Robot36/);
});

test("two-file output sizes fit short RAM budgets and require disk for long captures",()=>{
 const rate=1024000,seconds=60;
 const cu8=captureBudget(seconds,rate,true,{fileStreaming:false});
 const wav=wavOutputPlan(seconds,true,{fileStreaming:false});
 assert.equal(cu8.mode,"memory");
 assert.equal(wav.mode,"memory");
 assert.equal(cu8.estimatedBytes,122880000);
 assert.equal(wav.estimatedBytes,5760044);
 const bigIq=captureBudget(600,rate,true,{fileStreaming:true});
 const bigWav=wavOutputPlan(600,true,{fileStreaming:true});
 assert.equal(bigIq.mode,"disk-stream");
 assert.equal(bigWav.mode,"disk-stream");
 assert.throws(()=>captureBudget(600,rate,true,{fileStreaming:false}),/disk/);
 assert.throws(()=>wavOutputPlan(600,true,{fileStreaming:false}),/disk/);
});

test("synthetic continuous CU8 is preserved while a separate valid FM WAV is computed",()=>{
 const source=new Uint8Array(65536);
 for(let i=0;i<source.length/2;i++){
   const p=2*Math.PI*i/160;
   source[2*i]=Math.round(127.5+60*Math.cos(p));
   source[2*i+1]=Math.round(127.5+60*Math.sin(p));
 }
 const pristine=Uint8Array.from(source);
 const enc=createStreamingFmWavEncoder(1024000);
 const pcm=enc.push(source);
 const wav=new Uint8Array(44+pcm.byteLength);
 wav.set(createPcmWavHeader(pcm.byteLength));
 wav.set(pcm,44);
 const v=new DataView(wav.buffer);
 assert.deepEqual(source,pristine);
 assert.ok(pcm.byteLength>0);
 assert.equal(v.getUint32(40,true),pcm.byteLength);
 assert.equal(v.getUint16(20,true),1);
 assert.equal(v.getUint32(24,true),48000);
 assert.equal(v.getUint16(22,true),1);
 assert.equal(enc.report().verifiedSpacecraft,false);
});
