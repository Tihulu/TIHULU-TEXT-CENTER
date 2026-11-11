import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
const read=path=>readFileSync(new URL("../"+path,import.meta.url),"utf8");
test("antenna-only mode has explicit source-provenance and named hardware controls",()=>{
 const html=read("index.html"),app=read("web/app.mjs"),ui=read("web/rf_survey.mjs");
 for(const id of ["rf-only","rf-source-select","rf-type","rf-freq","rf-lat","rf-lon",
  "rf-capture","rf-calibrate","rf-cal-distance","rf-exponent","rf-solve","rf-fit-map",
  "rf-session-status","rf-measurement-status","rf-source-provenance","rf-source-list",
  "live-rf-only"]){
   assert.ok(html.includes('id="'+id+'"'),"Missing RF hardware UI "+id);
 }
 assert.match(app,/if\(state\.rfOnly\)/);
 assert.match(app,/tihulu:rf-survey-updated/);
 assert.match(app,/RF-ONLY CALIBRATED RSSI HYPOTHESIS/);
 assert.match(ui,/tihulu:rf-capture-request/);
 assert.match(ui,/tihulu:rf-observation/);
 assert.match(read("web/usb_sdr.mjs"),/sourceIdentityVerified:false/);
});
test("WebUSB measurements read sample block data, use fixed gain and preserve selected source",()=>{
 const usb=read("web/usb_sdr.mjs");
 assert.match(usb,/const raw=block\?\.data/);
 assert.match(usb,/const gainDb=20,sampleRate=1024000/);
 assert.match(usb,/relativePowerDbFS\(bytes\)/);
 assert.match(usb,/sourceId:String\(sourceId\|\|""\)/);
 assert.match(usb,/tihulu:rf-observation/);
 assert.match(usb,/no (?:GPS|GNSS) fix|NOT GNSS SIGNAL LOCK/i);
});
test("RF-only model and hardware survey modules are offline application-shell assets",()=>{
 const sw=read("sw.js");
 assert.match(sw,/core\/rf_ranging\.mjs/);
 assert.match(sw,/web\/rf_survey\.mjs/);
});
