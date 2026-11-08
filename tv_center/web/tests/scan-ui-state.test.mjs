import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {fileURLToPath} from "node:url";
import {scanFields,scanRequest,scanTitle,scanControls} from "../scan-ui-state.js";
const root=fileURLToPath(new URL("../",import.meta.url));

test("antenna and cable use a country frequency plan, never show a satellite",()=>{
  for(const medium of ["t","c"]){
    const fields=scanFields(medium);
    assert.equal(fields.showCountry,true);
    assert.equal(fields.showSatellite,false);
    const req=scanRequest({country:"DE",medium,satellite:"S42E0"});
    assert.deepEqual(req,{country:"DE",medium});
  }
});
test("satellite profile hides the country and derives the saved-list region",()=>{
  const fields=scanFields("s");
  assert.equal(fields.showCountry,false);
  assert.equal(fields.showSatellite,true);
  assert.equal(fields.countryUsedForFrequencies,false);
  const turksat=scanRequest({country:"DE",medium:"s",satellite:"S42E0"});
  assert.deepEqual(turksat,{country:"TR",medium:"s",satellite:"S42E0"});
  assert.match(scanTitle(turksat),/Türksat 42°E/);
  assert.deepEqual(scanRequest({country:"TR",medium:"s",satellite:"S19E2"}),
    {country:"DE",medium:"s",satellite:"S19E2"});
  assert.throws(()=>scanRequest({country:"DE",medium:"s",satellite:"WRONG"}),RangeError);
  assert.throws(()=>scanFields("invalid"),RangeError);
});
test("disconnected native tuner makes all RF, model and scan commands unavailable",()=>{
  for(const medium of ["t","c","s"]){
    const s=scanControls({connected:false,medium});
    for(const key of ["scanEnabled","cancelEnabled","stopEnabled","refreshEnabled","captionEnabled"]){
      assert.equal(s[key],false,key);
    }
    assert.match(s.statusText,/Open Local TV/i);
    assert.match(s.signalText,/No RF measurement/i);
    assert.match(s.explanation,/WebUSB/i);
  }
});
test("connected local app without DVB hardware must not enable scan",()=>{
  const state=scanControls({connected:true,frontendAvailable:false,medium:"t"});
  assert.equal(state.scanEnabled,false);
  assert.match(state.backendText,/frontend\/DVR not detected/i);
  assert.match(state.statusText,/Check USB\/firmware/i);
});

test("idle native tuner allows a scan, without inventing signal measurements",()=>{
  const s=scanControls({connected:true,medium:"t",scanning:false,playing:false});
  assert.equal(s.scanEnabled,true);
  assert.equal(s.stopEnabled,false);
  assert.equal(s.cancelEnabled,false);
  assert.match(s.signalText,/No RF readings yet/i);
});
test("a real running scan can be cancelled but cannot start a competing scan",()=>{
  const s=scanControls({connected:true,medium:"s",scanning:true,
    signal:"C/N 22.0 dB",scanMessage:"538 MHz · KiKA HD"});
  assert.equal(s.scanEnabled,false);
  assert.equal(s.cancelEnabled,true);
  assert.equal(s.stopEnabled,false);
  assert.equal(s.satelliteEnabled,false);
  assert.equal(s.deliveryEnabled,false);
  assert.match(s.statusText,/Scanning actual DVB frequencies/);
  assert.equal(s.signalText,"C/N 22.0 dB");
});
test("a playing tuner can be stopped before a scan is started",()=>{
  const playing=scanControls({connected:true,medium:"t",playing:true});
  assert.equal(playing.scanEnabled,false);
  assert.equal(playing.stopEnabled,true);
  assert.equal(playing.cancelEnabled,false);
  const pending=scanControls({connected:true,medium:"t",playing:true,pending:true});
  assert.equal(pending.scanEnabled,false);
  assert.equal(pending.stopEnabled,false);
});
test("both web clients use the same reactive module and clear their state on disconnect",()=>{
  const pages=readFileSync(new URL("../index.html",import.meta.url),"utf8");
  const mobile=readFileSync(new URL("../mobile.html",import.meta.url),"utf8");
  const pagesBridge=readFileSync(new URL("../app.js",import.meta.url),"utf8");
  const mobileBridge=readFileSync(new URL("../mobile.js",import.meta.url),"utf8");
  const controls=readFileSync(new URL("../web-controls.js",import.meta.url),"utf8");
  for(const page of [pages,mobile]){
    assert.match(page,/id="web-control-root"/);
    assert.match(page,/type="module" src="(?:\.\/|\/)web-controls\.js/);
  }
  assert.match(controls,/id="web-satellite-field" hidden/);
  assert.match(controls,/countryField\.hidden=!state\.showCountry/);
  assert.match(controls,/\$\("web-scan-start"\)\.disabled=!state\.scanEnabled/);
  assert.match(controls,/tihulu-tv-disconnected/);
  assert.match(pagesBridge,/tihulu-tv-disconnected/);
  assert.doesNotMatch(pagesBridge,/location\.replace\(LOOPBACK/);
  assert.match(pagesBridge,/WEBUSB · BROWSER-ONLY/);
  assert.match(mobileBridge,/tihulu-tv-disconnected/);
});
