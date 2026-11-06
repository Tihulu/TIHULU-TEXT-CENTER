import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
const src=readFileSync(new URL("../web/usb_sdr.mjs",import.meta.url),"utf8");
function section(from,to){
 const a=src.indexOf(" async function "+from+"("),b=src.indexOf(" async function "+to+"(",a);
 assert.ok(a>=0&&b>a,"Missing named USB lifecycle section "+from);
 return src.slice(a,b);
}
test("setSampleRate writes resampler register only at initial connect, not on RF scans",()=>{
 const connect=section("connect","scan"),scan=section("scan","captureRF"),capture=section("captureRF","selfTest");
 assert.match(connect,/await receiver\.setSampleRate\(1024000\)/);
 assert.doesNotMatch(scan,/\bsetSampleRate\s*\(/);
 assert.doesNotMatch(capture,/\bsetSampleRate\s*\(/);
 assert.match(scan,/configuredRate!==1024000/);
 assert.match(capture,/configuredRate!==sampleRate/);
});
test("samples never race with another USB operation and release waits for in-flight read",()=>{
 const release=section("release","connect");
 const scan=section("scan","captureRF"),capture=section("captureRF","selfTest");
 assert.match(scan,/if\(busy\|\|sampling\)/);
 assert.match(scan,/sampling=true;busy=true;stopping=false;beginSample\(\)/);
 assert.match(capture,/if\(busy\|\|sampling\)/);
 assert.match(capture,/busy=true;sampling=true;stopping=false;beginSample\(\)/);
 assert.match(scan,/finally\{sampling=false;busy=false;endSample\(\)\}/);
 assert.match(capture,/finally\{sampling=false;busy=false;endSample\(\)\}/);
 assert.match(release,/const inFlight=pendingSample/);
 assert.match(release,/await Promise\.race\(\[inFlight/);
 assert.match(release,/configuredRate=0;configuredFrequencyHz=0;configuredGain=null/);
});
test("GNSS scan returns real I/Q from library SampleBlock.data, never claims GNSS fix",()=>{
 const scan=section("scan","captureRF");
 assert.match(scan,/const raw=block\?\.data/);
 assert.match(scan,/UNCALIBRATED; NOT GNSS SIGNAL LOCK/);
 assert.match(scan,/if\(configuredFrequencyHz!==1575420000\)/);
});
