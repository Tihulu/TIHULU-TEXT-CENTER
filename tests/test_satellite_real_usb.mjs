import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { inspectIqBytes, sampleBytes, probeUsbSamples } from '../satellite_center/browser/usb_live_probe.mjs';

test('real IQ probe measures sample bytes instead of permission grants',()=>{
 const samples=new Uint8Array([127,128,120,137,0,255,255,0]);
 assert.equal(sampleBytes(samples.buffer).length,8);
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
  async readSamples(num){calls.push(['samples',num]);return new Uint8Array([127,127,124,131,170,98,130,125]);}
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
 assert.ok(html.includes('id="usb-live-test"'));
 assert.ok(html.includes('id="usb-live-test-report"'));
 assert.ok(script.includes('renderer:leaflet.svg({pane:"world-outline"'));
 assert.ok(script.includes('await useWorldOutline(why,revision)'));
 assert.ok(script.includes('openEarth().then(refresh)'));
 assert.ok(script.includes('earthMap.createPane("world-outline")'));
 assert.ok(app.includes('await probeUsbSamples(device'));
 assert.ok(app.includes('await connectDevice({silent:true})'));
 assert.ok(app.includes('await closeDevice()'));
});
