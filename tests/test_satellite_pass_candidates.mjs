import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {candidateFromPass,readPlanningCandidates,savePlanningCandidate,
 removePlanningCandidate,CANDIDATE_STORAGE_KEY} from '../satellite_center/browser/pass_candidates.mjs';
const root=new URL('../satellite_center/',import.meta.url);
const read=name=>readFileSync(new URL(name,root),'utf8');
function storage(){
 const data=new Map();
 return {getItem:key=>data.get(key)??null,setItem:(key,value)=>data.set(key,value)};
}
test("TLE-only pass plans do not arm or require receiver",()=>{
 const now=Date.now(),aos=now+600000;
 const p={id:59051,name:'METEOR M2-4',family:'meteor',aos,los:aos+800000,maximum:48};
 const entry=candidateFromPass(p,{observer:{lat:50.938,lon:6.96},now});
 assert.equal(entry.status,'planning-only');
 assert.equal(entry.radioArmed,false);
 assert.equal(entry.actualRecording,false);
 assert.match(entry.note,/No SDR required/);
 const st=storage();
 let rows=savePlanningCandidate(entry,st);
 assert.equal(rows.length,1);
 assert.equal(readPlanningCandidates(st)[0].norad,59051);
 rows=savePlanningCandidate(entry,st);
 assert.equal(rows.length,1);
 assert.equal(removePlanningCandidate(entry.id,st).length,0);
});
test("Do not allow arbitrary bogus, expired or RF-armed calendar entries",()=>{
 const now=Date.now();
 assert.throws(()=>candidateFromPass({id:0,aos:now+60000,los:now+120000},{now}));
 assert.throws(()=>candidateFromPass({id:59051,aos:now-7200000,los:now-7000000},{now}));
 assert.throws(()=>savePlanningCandidate({status:'armed',radioArmed:true},storage()));
 assert.deepEqual(readPlanningCandidates({getItem:()=>'not json'}),[]);
});
test("Native Qt schedule candidates and map/compute UI are independent of WebUSB",()=>{
 const frontend=read('browser/browser.js');
 const bridge=read('native_desktop_bridge.js');
 const native=read('native_web_shell.py');
 const html=read('browser/index.html');
 const compute=read('browser/compute_selector.mjs');
 assert.match(frontend,/Add planning candidate · no antenna/);
 assert.match(frontend,/Add to planning calendar/);
 assert.match(frontend,/planningCandidates=savePlanningCandidate/);
 assert.match(frontend,/nativeListPlanningCandidates/);
 assert.match(bridge,/window.nativeSavePlanningCandidate=/);
 assert.match(bridge,/window.nativeDeletePlanningCandidate=/);
 assert.match(native,/if command=="plan_candidate_add":/);
 assert.match(native,/if command=="plan_candidates":/);
 assert.match(html,/id="candidate-calendar-list"/);
 assert.match(html,/id="native-compute-inventory"/);
 assert.match(compute,/nativeSystem\?\.hardware/);
 assert.doesNotMatch(read('browser/pass_candidates.mjs'),/\.open\(|USBDevice|rtl_sdr|fetch\(/);
});
