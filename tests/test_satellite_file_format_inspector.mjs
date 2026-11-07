import test from "node:test";
import assert from "node:assert/strict";
import {inspectLocalFormat} from "../satellite_center/browser/file_format_inspector.mjs";

const file=(name,bytes)=>Object.assign(new Blob([Uint8Array.from(bytes)]),{name});

test("real PNG/JPEG/WAV headers receive typed labels but not satellite provenance",async()=>{
  for(const [name,magic,label] of [
    ["frame.png",[137,80,78,71,13,10,26,10],"IMAGE · PNG"],
    ["frame.jpg",[255,216,255,224],"IMAGE · JPEG"],
    ["sample.wav",[82,73,70,70,0,0,0,0,87,65,86,69],"AUDIO · WAV"],
    ["radio.ogg",[79,103,103,83],"AUDIO · OGG"],
    ["video.webm",[26,69,223,163],"VIDEO · WEBM"]
  ]){
    const result=await inspectLocalFormat(file(name,magic));
    assert.equal(result.label,label);
    assert.equal(result.status,"header-match");
    assert.equal(result.verifiedHeader,true);
    assert.match(result.explanation,/satellite source remain unverified/);
  }
});

test("invalid magic never lets a .png or .wav masquerade as decoded output",async()=>{
  for(const name of ["fake.png","fake.wav","fake.mp3","fake.webp"]){
    const result=await inspectLocalFormat(file(name,[1,2,3,4,5]));
    assert.equal(result.status,"header-mismatch");
    assert.equal(result.verifiedHeader,false);
    assert.match(result.explanation,/Do not call it a decoded/);
  }
});

test("raw CU8 format is not self-describing; odd byte count is flagged",async()=>{
  const valid=await inspectLocalFormat(file("capture.cu8",[127,127,42,88]));
  assert.equal(valid.label,"RAW RF · CU8");
  assert.equal(valid.status,"raw-unverified");
  assert.match(valid.explanation,/no embedded frequency/);
  const partial=await inspectLocalFormat(file("capture.cu8",[0,1,2]));
  assert.equal(partial.status,"size-warning");
  assert.equal(partial.verifiedHeader,false);
});

test("JSON/TXT/CSV previews remain extension-only, not packet authenticity",async()=>{
  for(const [name,label] of [["metadata.json","DATA · JSON"],["log.txt","TEXT · TXT"],["spectrum.csv","TABLE · CSV"]]){
    const result=await inspectLocalFormat(file(name,[123,125]));
    assert.equal(result.label,label);
    assert.equal(result.status,"extension-only");
    assert.equal(result.verifiedHeader,false);
  }
});
test("invalid and missing input rejected without uploading or reading entire file",async()=>{
  await assert.rejects(inspectLocalFormat(null),/Select a readable/);
  await assert.rejects(inspectLocalFormat({name:"foo.png",size:2}),/Select a readable/);
});
