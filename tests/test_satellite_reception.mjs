import test from "node:test";
import assert from "node:assert/strict";
import {MISSIONS,missionById,localFileKind,fileEvidence} from "../satellite_center/browser/reception_catalog.mjs";

test("Receive-only catalog includes real and online data sources with explicit limits",()=>{
  assert.ok(MISSIONS.length>=8);
  for(const m of MISSIONS){
    assert.ok(m.id&&m.name&&m.official&&m.input&&m.decoder&&m.description&&m.availability);
    assert.equal(missionById(m.id),m);
    if(m.frequencyHz!==null)assert.ok(m.frequencyHz>0);
  }
  const iss=missionById("iss-sstv");
  assert.equal(iss.frequencyHz,437550000);
  assert.equal(iss.availability,"event-only");
  assert.match(iss.description,/NOT live Earth photographs/);
  assert.equal(missionById("meteor-m2-3").receiver,"rtlsdr-native-decode");
  assert.equal(missionById("meteor-m2-4").receiver,"rtlsdr-native-decode");
  assert.equal(missionById("nasa-online").receiver,"internet");
  assert.equal(missionById("legacy-noaa").availability,"retired");
  assert.equal(missionById("no-such-satellite"),null);
});

test("User files are unverified; do not infer a downlink from file extensions",()=>{
  assert.equal(localFileKind("earth.PNG"),"image");
  assert.equal(localFileKind("ISS-voice.WAV"),"audio");
  assert.equal(localFileKind("pass.MP4"),"video");
  assert.equal(localFileKind("packet.json"),"text");
  assert.equal(localFileKind("pass.CU8"),"iq");
  assert.equal(localFileKind("file.zip"),"unknown");
  const evidence=fileEvidence(
    {name:"ISS_candidate.cu8",size:2048000,lastModified:Date.UTC(2026,10,6)},
    "iss-sstv",437550000,1024000
  );
  assert.equal(evidence.source,"user-imported_unverified");
  assert.equal(evidence.catalogTargetIsVerifiedTransmitter,false);
  assert.equal(evidence.durationSeconds,1);
  assert.equal(evidence.fileModifiedUtc,"2026-11-06T00:00:00.000Z");
  assert.equal(evidence.selectedFrequencyHz,437550000);
  assert.equal(evidence.sampleRateSps,1024000);
  assert.ok(!("decodedImage" in evidence));
  assert.throws(()=>fileEvidence({name:"a.cu8",size:20},"fake"),/valid catalog/);
  assert.throws(()=>fileEvidence({name:"a.cu8",size:20},"iss-sstv",null,0),/sample rate/);
});
