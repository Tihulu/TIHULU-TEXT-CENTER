import test from "node:test";
import assert from "node:assert/strict";
import {PROFILE_KEY,parseUserProtocol,readUserProfiles,saveUserProfiles,validateUserProfiles}
 from "../satellite_center/browser/saved_satellite_protocols.mjs";
import {protocolsForPass,protocolCategories} from "../satellite_center/browser/pass_protocol_catalog.mjs";

const example={norad:99991,frequencyHz:435500000,kind:"text",
  protocol:"AFSK1200 published transmitter candidate",source:"https://db.satnogs.org/"};

test("User-supplied public receiver profiles remain unverified and never claim decode",()=>{
 const p=parseUserProtocol(example);
 assert.equal(p.frequencyHz,435500000);
 assert.equal(p.norad,99991);
 assert.equal(p.decoder,"no-decoder-connected");
 assert.equal(p.provenance,"user-supplied");
 assert.equal(p.activity,"user-supplied-not-verified");
 assert.equal(validateUserProfiles([example,example]).length,1);
 assert.throws(()=>parseUserProtocol({...example,frequencyHz:2395000000}),/24–1750/);
 assert.throws(()=>parseUserProtocol({...example,source:"javascript:alert(1)"}),/HTTPS/);
 assert.throws(()=>parseUserProtocol({...example,kind:"transmit"}),/Choose/);
 assert.throws(()=>parseUserProtocol({...example,protocol:"<script>bad</script>"}),/non-HTML/);
 assert.throws(()=>validateUserProfiles(Array.from({length:33},()=>example)),/at most/);
});
test("Settings export/import can move manual entries without web connection",()=>{
 const map=new Map();
 const store={getItem:key=>map.get(key)||null,setItem:(key,val)=>map.set(key,val)};
 assert.deepEqual(readUserProfiles(store),[]);
 const saved=saveUserProfiles([example],store);
 assert.equal(saved.length,1);
 assert.equal(map.has(PROFILE_KEY),true);
 assert.deepEqual(readUserProfiles(store),saved);
 assert.deepEqual(protocolCategories({id:25338}),[]); // retired NOAA APT never activates
 assert.ok(protocolsForPass({id:25544}).some(x=>x.protocol.includes("Robot36")));
});
