import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {BrowserTransportCapture} from "../browser-ts-capture.js";
import {sectionWithCRC,TS_SIZE} from "../ts-analyzer.js";

function patPacket(){
  const pat=sectionWithCRC([0,0xb0,0x0d,0,1,0xc1,0,0,0,100,0xe1,0]);
  const packet=new Uint8Array(TS_SIZE).fill(0xff);
  packet.set([0x47,0x40,0x00,0x10,0x00,...pat]);
  return packet;
}
test("captures genuine PAT bytes and reports verified transport only with CRC-valid PSI",async()=>{
  let calls=0;
  const packet=patPacket();
  const session=new BrowserTransportCapture(async limit=>{
    assert.ok(limit<=16384);
    calls++;
    return calls===1?packet:new Uint8Array(0);
  },{maxBytes:188,maxTransfers:4});
  const result=await session.run();
  assert.deepEqual(result.bytes,packet);
  assert.equal(result.bytes.length,188);
  assert.equal(result.summary.packets,1);
  assert.equal(result.summary.programs[0].service,100);
  assert.equal(result.transportVerified,true);
  await assert.rejects(session.run(),/cannot be reused/);
});
test("raw transfer without valid DVB tables cannot claim verified reception",async()=>{
  const session=new BrowserTransportCapture(async()=>Uint8Array.from([2,3,4]),
    {maxBytes:512,maxTransfers:2});
  const result=await session.run();
  assert.equal(result.bytes.length,6);
  assert.equal(result.summary.packets,0);
  assert.equal(result.transportVerified,false);
});
test("stop request halts after current USB read, no further device operations",async()=>{
  let calls=0,session;
  session=new BrowserTransportCapture(async()=>{
    calls++;return Uint8Array.of(0x47,0,0);
  },{maxBytes:1024,maxTransfers:20,onProgress:()=>session.stop()});
  const result=await session.run();
  assert.equal(calls,1);
  assert.equal(result.stopped,true);
  assert.equal(result.bytes.length,3);
});
test("enforces capture budget, read return type and fixed USB max request",async()=>{
  assert.throws(()=>new BrowserTransportCapture(null),/callback/);
  assert.throws(()=>new BrowserTransportCapture(async()=>new Uint8Array(),{maxBytes:9*1024*1024}),RangeError);
  assert.throws(()=>new BrowserTransportCapture(async()=>new Uint8Array(),{maxTransfers:0}),RangeError);
  const short=new BrowserTransportCapture(async size=>new Uint8Array(size),
    {maxBytes:200,maxTransfers:10});
  const exact=await short.run();
  assert.equal(exact.bytes.length,200);
  assert.equal(exact.transfers,1);
  const over=new BrowserTransportCapture(async()=>new Uint8Array(16385));
  await assert.rejects(over.run(),/invalid or oversized/);
});
test("standalone Pages includes capture and stop controls, no native service prerequisite",()=>{
  const html=readFileSync(new URL("../index.html",import.meta.url),"utf8");
  const ui=readFileSync(new URL("../webusb-ui.js",import.meta.url),"utf8");
  for(const id of ["webusb-capture","webusb-capture-stop","webusb-capture-save"])
    assert.ok(html.includes('id="'+id+'"'));
  assert.match(ui,/BrowserTransportCapture/);
  assert.match(ui,/probe\.readBulkBytes/);
  assert.doesNotMatch(ui,/detachKernelDriver|controlTransferOut/);
});
