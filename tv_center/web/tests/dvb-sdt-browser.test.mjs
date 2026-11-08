import test from "node:test";
import assert from "node:assert/strict";
import {TransportAnalyzer,sectionWithCRC,dvbName,TS_SIZE} from "../ts-analyzer.js";
const tsPacket=(pid,section,cc=0)=>{
  const payload=Uint8Array.from([0x47,0x40|((pid>>8)&31),pid&255,0x10|cc,0,...section]);
  assert.ok(payload.length<=TS_SIZE);
  const full=new Uint8Array(TS_SIZE).fill(255);
  full.set(payload);return full;
};
test("DVB service descriptor (SDT 0x42) provides real broadcaster names",()=>{
  const provider=new TextEncoder().encode("ZDF");
  const title=new TextEncoder().encode("KiKA HD");
  const serviceDesc=Uint8Array.from([
    0x48,3+provider.length+title.length,0x01,provider.length,...provider,
    title.length,...title
  ]);
  const length=17+serviceDesc.length;
  const sdt=sectionWithCRC(Uint8Array.from([
    0x42,0xf0|((length>>8)&15),length&255,
    0x01,0x23,0xc1,0,0,0,0x01,0xff,
    0,100,0xff,0xf0|((serviceDesc.length>>8)&15),serviceDesc.length&255,
    ...serviceDesc
  ]));
  const pat=sectionWithCRC(Uint8Array.from([
    0,0xb0,0x0d,0,1,0xc1,0,0,0,100,0xe1,0
  ]));
  const analyzer=new TransportAnalyzer();
  const stat=analyzer.feed(Uint8Array.from([
    ...tsPacket(0,pat),...tsPacket(0x11,sdt)
  ]));
  assert.equal(stat.transportId,0x0123);
  assert.equal(stat.programs.length,1);
  assert.equal(stat.programs[0].name,"KiKA HD");
  assert.equal(stat.programs[0].provider,"ZDF");
  assert.equal(stat.programs[0].kind,"tv");
  assert.equal(stat.crcErrors,0);
});
test("DVB UTF-8 selector decodes umlauts and never accepts malformed table CRC",()=>{
  const text=Uint8Array.from([0x15,...new TextEncoder().encode("Köln")]);
  assert.equal(dvbName(text),"Köln");
  const analyzer=new TransportAnalyzer();
  const bad=sectionWithCRC([0x42,0xf0,17,0,1,0xc1,0,0,0,1,0xff,0,1,0xff,0xf0,0]);
  bad[bad.length-1]^=0xff;
  const s=analyzer.feed(tsPacket(0x11,bad));
  assert.equal(s.crcErrors,1);
  assert.equal(s.transportId,null);
});
test("browser-only driver and WASM preview are actually included in both CI and Pages",async()=>{
  const fs=await import("node:fs");
  const html=fs.readFileSync(new URL("../index.html",import.meta.url),"utf8");
  const js=fs.readFileSync(new URL("../app.js",import.meta.url),"utf8");
  for(const id of ["browser-driver-center","dvb-driver-preview","dvb-driver-fw",
    "wasm-ts-file","wasm-ts-start","wasm-ts-video"]){
    assert.ok(html.includes('id="'+id+'"'));

  }
  for(const module of ["webusb-driver-ui.js","wasm-ts-preview.js"]){
    assert.ok(html.includes(module));
  }
  const driverUI=fs.readFileSync(new URL("../webusb-driver-ui.js",import.meta.url),"utf8");
  assert.ok(driverUI.includes("em28xx-driver-plan.js"));
  assert.doesNotMatch(js,/location\.replace\(LOOPBACK/);
  assert.match(js,/WEBUSB · BROWSER-ONLY/);
});
