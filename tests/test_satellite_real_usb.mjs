import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { inspectIqBytes, sampleBytes, probeUsbSamples } from '../satellite_center/browser/usb_live_probe.mjs';

test('real IQ probe measures sample bytes instead of permission grants',()=>{
 const samples=new Uint8Array([127,128,120,137,0,255,255,0]);
 assert.equal(sampleBytes(samples.buffer).length,8);
 assert.equal(sampleBytes({frequency:137900000,directSampling:false,data:samples.buffer}).length,8);
 const report=inspectIqBytes([samples]);
 assert.equal(report.rawBytes,8);
 assert.equal(report.blocks,1);
 assert.equal(report.approximateComplexPairs,4);
 assert.ok(Number.isFinite(report.relativeDigitalLevelDb));
 assert.match(report.interpretation,/no antenna sensitivity/);
 assert.throws(()=>inspectIqBytes([]),/zero USB/);
 assert.throws(()=>inspectIqBytes([new Uint8Array(3)]),/I\/Q/);
});
test('synthetic browser hardware probe calls tuner and actual readSamples (never fake RF)',async()=>{
 const calls=[];
 const device={
  async setSampleRate(rate){calls.push(['rate',rate]);},
  async setCenterFrequency(freq){calls.push(['frequency',freq]);},
  async setGain(gain){calls.push(['gain',gain]);},
  async resetBuffer(){calls.push(['reset']);},
  async readSamples(num){calls.push(['samples',num]);return {frequency:137900000,directSampling:false,data:new Uint8Array([127,127,124,131,170,98,130,125]).buffer};}
 };
 const status=[];
 const report=await probeUsbSamples(device,{frequency:137900000,rate:1024000,durationMs:250,onProgress:m=>status.push(m)});
 assert.ok(report.rawBytes>0);
 assert.equal(report.frequencyHz,137900000);
 assert.ok(calls.some(c=>c[0]==='samples'));
 assert.ok(calls.some(c=>c[0]==='reset'));
 assert.ok(calls.some(c=>c[0]==='frequency'));
 assert.ok(status.some(s=>s.includes('actual I/Q samples')));
 assert.match(report.interpretation,/no antenna sensitivity/);
});
test('USB test rejects invalid frequency, zero data and driver errors',async()=>{
 const device={setSampleRate:async()=>{},setCenterFrequency:async()=>{},setGain:async()=>{},
 resetBuffer:async()=>{},readSamples:async()=>new Uint8Array(0)};
 await assert.rejects(probeUsbSamples(device,{frequency:20000000}),/frequency/);
 await assert.rejects(probeUsbSamples(device,{frequency:137900000,durationMs:250}),/empty I\/Q/);
});
test('map always defaults to bundled land geography and offers a real diagnostic',()=>{
 const html=fs.readFileSync(new URL('../satellite_center/browser/index.html',import.meta.url),'utf8');
 const script=fs.readFileSync(new URL('../satellite_center/browser/satellite_maps.mjs',import.meta.url),'utf8');
 const app=fs.readFileSync(new URL('../satellite_center/browser/browser.js',import.meta.url),'utf8');
 assert.ok(html.includes('<option value="outline" selected>'));
 assert.ok(html.includes('id="map-diagnose"'));
 assert.ok(html.includes('id="earth-world-canvas"'));
 assert.ok(html.includes('id="earth-world-status"'));
 assert.ok(html.includes('id="earth-street-details"'));

 assert.ok(html.includes('id="usb-live-test"'));
 assert.ok(html.includes('id="usb-live-test-report"'));
 assert.ok(script.includes('renderer:leaflet.svg({pane:"world-outline"'));
 assert.ok(script.includes('await useWorldOutline(why,revision)'));
 assert.ok(script.includes('openEarth().then(refresh)'));
 assert.ok(script.includes('earthMap.createPane("world-outline")'));
 assert.ok(script.includes('async function drawWorldCanvas()'));
 assert.ok(script.includes('ctx.fill("evenodd")'));
 assert.ok(script.includes('getWorldOutlineData()'));
 assert.ok(script.includes('mapStarted=true;setView(kind)'));

 assert.ok(app.includes('await probeUsbSamples(device'));
 assert.ok(app.includes('const data=sampleBytes(raw)'));
 assert.ok(app.includes('await connectDevice({silent:true})'));
 assert.ok(app.includes('await closeDevice()'));
});


import { usbInterfaceClaimProbe, webUsbHelp } from '../satellite_center/browser/usb_diagnostics.mjs';

test('low-level USB claim test opens and always releases precisely its own RTL2832U',async()=>{
 const calls=[];
 const d={
   vendorId:0x0bda,productId:0x2838,opened:false,configuration:null,
   async open(){calls.push('open');this.opened=true;},
   async selectConfiguration(n){calls.push('configuration'+n);this.configuration={configurationValue:n};},
   async claimInterface(i){calls.push('claim'+i);},
   async releaseInterface(i){calls.push('release'+i);},
   async close(){calls.push('close');this.opened=false;}
 };
 const result=await usbInterfaceClaimProbe({getDevices:async()=>[d]});
 assert.equal(result.ok,true);
 assert.deepEqual(calls,['open','configuration1','claim0','release0','close']);
 assert.equal(d.opened,false);
});

test('failed claim preserves native browser error and closes its owned handle',async()=>{
 const calls=[];
 const d={
   vendorId:0x0bda,productId:0x2838,opened:false,configuration:{configurationValue:1},
   async open(){this.opened=true;calls.push('open');},
   async claimInterface(i){calls.push('claim'+i);throw Object.assign(new Error('Unable to claim interface.'),{name:'NetworkError'});},
   async releaseInterface(){calls.push('release');},
   async close(){this.opened=false;calls.push('close');}
 };
 const result=await usbInterfaceClaimProbe({getDevices:async()=>[d]});
 assert.equal(result.ok,false);
 assert.equal(result.stage,'claimInterface(0)');
 assert.equal(result.errorName,'NetworkError');
 assert.deepEqual(calls,['open','claim0','close']);
 assert.equal(d.opened,false);
});

test('USB probe never opens an unrelated device without a matching grant',async()=>{
 let opened=false;
 const d={vendorId:0x0abc,productId:0x1234,async open(){opened=true;}};
 const result=await usbInterfaceClaimProbe({getDevices:async()=>[d]});
 assert.equal(result.ok,false);
 assert.equal(opened,false);
});

test('wrapped RTL-SDR claim error exposes browser DOMException cause',()=>{
 const error=new Error('Could not connect to the RTL-SDR stick.');
 error.name='RadioError.UsbTransferError';
 error.cause=Object.assign(new Error('Unable to claim interface.'),{name:'NetworkError'});
 const guidance=webUsbHelp(error,'linux');
 assert.match(guidance,/Underlying WebUSB error: NetworkError/);
 assert.match(guidance,/sudo systemctl stop readsb/);
});
