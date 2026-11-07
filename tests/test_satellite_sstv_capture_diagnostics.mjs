import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {robot36CaptureHint} from "../satellite_center/browser/sstv_capture_diagnostics.mjs";

const name=(stamp,hz,rate,kind,extension)=>
 "TIHULU_ISS-ZARYA-CANDIDATE_"+stamp+"_"+hz+"Hz_"+rate+"SPS_"+kind+"."+extension;
test("uploaded voice-channel WAV clearly explains wrong SSTV band and pre-event date",()=>{
 const hint=robot36CaptureHint(name("20261107T004601Z",145800000,48000,"SSTV-AUDIO","wav"));
 assert.match(hint,/145.800 MHz/);
 assert.match(hint,/437.550 MHz/);
 assert.match(hint,/NOT/);
 assert.match(hint,/outside/);
 assert.match(hint,/9–16/);
});
test("uploaded 1.024MSPS CU8 cannot be retuned to a different band",()=>{
 const hint=robot36CaptureHint(name("20261107T004601Z",145800000,1024000,"SCHEDULED-IQ","cu8"));
 assert.match(hint,/CU8 bandwidth cannot/);
 assert.match(hint,/145.800 MHz/);
});
test("matching date/frequency still requires real line synchronization",()=>{
 const hint=robot36CaptureHint(name("20261110T144601Z",437550000,48000,"SSTV-AUDIO","wav"));
 assert.match(hint,/match the announced/);
 assert.match(hint,/no genuine repeated 1200 Hz/);
 assert.doesNotMatch(hint,/outside/);
});
test("unknown or renamed file avoids inventing tuning or receiver identity",()=>{
 const hint=robot36CaptureHint("recording.wav");
 assert.match(hint,/Verify the original SDR tuning/);
 assert.doesNotMatch(hint,/145.800 MHz/);
});
test("UI and decoder use actionable wrong-band message, preserving decoder failure",()=>{
 const url=new URL("../satellite_center/browser/",import.meta.url);
 const html=readFileSync(new URL("index.html",url),"utf8");
 const app=readFileSync(new URL("satellite_images_ui.mjs",url),"utf8");
 assert.match(html,/145\.800 MHz \(NOT Series 35 SSTV/);
 assert.match(app,/robot36CaptureHint\(file\.name\)/);
 assert.match(app,/robot36CaptureHint\(name\)/);
 assert.match(app,/No credible Robot36 SSTV image produced/);
});
