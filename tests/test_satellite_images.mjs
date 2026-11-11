import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {recordingName,parseRecordingName,epicEntries,nasaIssEntries,
 IMAGE_TARGETS,isoUtcCompact} from "../satellite_center/browser/satellite_imagery.mjs";
import {decodeRobot36Audio,robot36Mode,findRobot36Syncs,frequencyTrace} from "../satellite_center/browser/sstv_robot36.mjs";
import {cu8ToFmAudio} from "../satellite_center/browser/fm_iq_demod.mjs";
test("filename includes satellite candidate UTC Hz sample rate and archive remains parseable",()=>{
 const name=recordingName({satellite:"ISS (ZARYA) SSTV candidate",
  at:new Date("2026-11-06T10:15:19Z"),frequencyHz:437550000,
  sampleRate:1024000,kind:"IQ",format:"cu8"});
 assert.equal(name,"TIHULU_ISS-ZARYA-SSTV-CANDIDATE_20261106T101519Z_437550000Hz_1024000SPS_IQ.cu8");
 const parsed=parseRecordingName(name);
 assert.equal(parsed.frequencyHz,437550000);
 assert.equal(parsed.sampleRate,1024000);
 assert.equal(parsed.timestamp,"2026-11-06T10:15:19.000Z");
 assert.equal(parsed.satellite,"ISS-ZARYA-SSTV-CANDIDATE");
 assert.equal(parseRecordingName("../evil.png"),null);
 assert.throws(()=>recordingName({satellite:"test",at:"oops",frequencyHz:0}),/UTC/);
});
test("NASA EPIC metadata yields real provider URL and date, never claims SDR",()=>{
 const catalog=epicEntries([{image:"epic_1b_20151031074844",date:"2015-10-31 07:48:44",caption:"Earth"}]);
 assert.equal(catalog.length,1);
 assert.match(catalog[0].imageUrl,/api\.nasa\.gov\/EPIC\/archive\/natural\/2015\/10\/31\/jpg/);
 assert.match(catalog[0].source,/NOT this RTL-SDR/);
 assert.throws(()=>epicEntries({}),/valid image catalog/);
 assert.equal(epicEntries([{image:"../../evil",date:"2015-10-31 07:48:44"}]).length,0);
});
test("NASA ISS archive images retain timestamp and provenance",()=>{
 const payload={collection:{items:[
  {data:[{media_type:"image",title:"Earth from ISS",date_created:"2023-01-02T04:05:06Z",nasa_id:"iss-123"}],
   links:[{href:"https://images-assets.nasa.gov/image/iss-123/test.jpg"}]},
  {data:[{media_type:"video"}],links:[{href:"https://evil.example/x.jpg"}]}
 ]}};
 const records=nasaIssEntries(payload);
 assert.equal(records.length,1);
 assert.match(records[0].source,/historical/);
 assert.equal(records[0].timestamp,"2023-01-02T04:05:06Z");
 assert.equal(IMAGE_TARGETS[0].frequencies[0],437550000);
});
test("real Robot36 audio with 240 synchronized lines reconstructs a 320x240 image",()=>{
 const sr=16000,num=Math.floor(sr*36.2),samples=new Float32Array(num);
 let phase=0;
 for(let i=0;i<num;i++){
  const t=i/sr,line=Math.floor(t/.15),x=t-line*.15;
  const freq=x<.009?1200:x<.012?1500:x<.100?1900:
   x<.1045?(line%2?2300:1500):1900;
  phase+=2*Math.PI*freq/sr;
  samples[i]=.6*Math.sin(phase);
 }
 const result=decodeRobot36Audio(samples,sr);
 assert.equal(result.width,320);
 assert.equal(result.height,240);
 assert.ok(result.alignedLines>=225);
 assert.equal(result.rgba.length,320*240*4);
 assert.match(result.warning,/satellite origin.*not independently verified/);
});
test("no image without a real Robot36 synchronized audio train",()=>{
 const quiet=new Float32Array(16000*36);
 assert.throws(()=>decodeRobot36Audio(quiet,16000),/sync|Robot36/);
 assert.throws(()=>decodeRobot36Audio(quiet.slice(0,16000),16000),/36 seconds/);
});
test("CU8 FM demod rejects inadequate duration, malformed format, and incompatible sample rate",async()=>{
 await assert.rejects(cu8ToFmAudio(new Blob([new Uint8Array(4096)]),{sampleRate:1024000}),/at least 32/);
 await assert.rejects(cu8ToFmAudio(new Blob([new Uint8Array(4097)]),{sampleRate:1024000}),/complete unsigned/);
 await assert.rejects(cu8ToFmAudio(new Blob([new Uint8Array(4096)]),{sampleRate:1000000}),/1\.024 or 2\.048/);
});
test("cross-platform browser UI actually wires online imagery, SSTV audio/RF and UTC file metadata",()=>{
 const base=new URL("../satellite_center/browser/",import.meta.url);
 const ui=readFileSync(new URL("satellite_images_ui.mjs",base),"utf8");
 const html=readFileSync(new URL("index.html",base),"utf8");
 const app=readFileSync(new URL("browser.js",base),"utf8");
 for(const id of ["satellite-images","image-fetch-online","image-gallery","image-target",
  "image-sstv-file","image-decode-sstv","image-cuiq-file","image-decode-cuiq",
  "image-decode-last","image-sstv-canvas","image-download-sstv"])
  assert.ok(html.includes('id="'+id+'"'),id);
 assert.match(ui,/cu8ToFmAudio\(blob/);
 assert.match(ui,/decodeRobot36Audio\(samples,rate\)/);
 assert.match(ui,/epicEntries\(json\)/);
 assert.match(ui,/nasaIssEntries\(json\)/);
 assert.match(app,/recordingName\(\{satellite:targetName/);
 assert.match(app,/satelliteImageUI\.recordCapture\(blob,name,metadata\)/);
});
