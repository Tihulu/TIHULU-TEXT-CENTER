import test from "node:test";
import assert from "node:assert/strict";
import {TransportAnalyzer,crc32Mpeg,sectionWithCRC,TS_SIZE} from "../ts-analyzer.js";
import {WinTVProbe,supportedUSB,bulkCandidates,WINTV} from "../webusb-em28xx.js";

function psiPacket(pid, table, cc=0) {
  const data=Uint8Array.from([0x47,0x40|((pid>>8)&31),pid&255,0x10|cc,0x00,...table]);
  assert.ok(data.length<=TS_SIZE);
  const full=new Uint8Array(TS_SIZE).fill(0xff);full.set(data);return full;
}
function nullPacket(cc=0){
  const b=new Uint8Array(TS_SIZE).fill(0xff);
  b.set([0x47,0x1f,0xff,0x10|cc]);return b;
}
function mockDevice(){
  return {
    vendorId:WINTV.vendorId, productId:WINTV.productId, opened:true,
    configuration:{configurationValue:1},
    configurations:[{configurationValue:1,interfaces:[
      {interfaceNumber:0,alternates:[{alternateSetting:0,endpoints:[
        {type:"bulk",direction:"in",endpointNumber:2,packetSize:512}
      ]}]}
    ]}],
    async controlTransferIn(setup,length){
      assert.equal(setup.requestType,"vendor");
      assert.equal(setup.recipient,"device");
      assert.equal(setup.request,0);
      assert.equal(setup.index,0x0a);
      assert.equal(length,1);
      return {status:"ok",data:new DataView(Uint8Array.of(0x68).buffer)};
    },
    async claimInterface(){this.claimed=true},
    async releaseInterface(){this.claimed=false},
    async close(){this.opened=false},
    async transferIn(endpoint,length){
      assert.equal(endpoint,2);
      assert.equal(length,16384);
      const buffer=psiPacket(0, sectionWithCRC([
        0,0xb0,0x0d,0,1,0xc1,0,0,0,100,0xe1,0
      ]));
      return {status:"ok",data:new DataView(buffer.buffer)};
    }
  };
}
test("reference MPEG-2 CRC-32 and checksum validation",()=>{
  assert.equal(crc32Mpeg(Buffer.from("123456789")),0x0376e6e7);
  const pat=sectionWithCRC([0,0xb0,0x0d,0,1,0xc1,0,0,0,100,0xe1,0]);
  assert.equal(crc32Mpeg(pat),0);
});
test("parse genuine PAT and PMT into service and video/audio PIDs",()=>{
  const analyzer=new TransportAnalyzer();
  const pat=psiPacket(0,sectionWithCRC([0,0xb0,0x0d,0,1,0xc1,0,0,0,100,0xe1,0]));
  const pmt=psiPacket(0x100,sectionWithCRC([
    0x02,0xb0,0x17,0,100,0xc1,0,0,0xe2,0,0xf0,0,
    0x24,0xe2,0,0xf0,0,0x0f,0xe2,1,0xf0,0
  ]));
  let summary=analyzer.feed(new Uint8Array([...pat.slice(0,61)]));
  assert.equal(summary.packets,0);
  summary=analyzer.feed(new Uint8Array([...pat.slice(61),...pmt,...nullPacket()]));
  assert.equal(summary.packets,3);
  assert.equal(summary.programs.length,1);
  assert.equal(summary.programs[0].service,100);
  assert.equal(summary.programs[0].pmtPid,0x100);
  assert.deepEqual(summary.programs[0].details.streams.map(x=>x.codec),["HEVC","AAC"]);
  assert.equal(summary.validSections,2);
  assert.equal(summary.crcErrors,0);
});
test("reject corrupt PAT CRC and never invent channels",()=>{
  const analyzer=new TransportAnalyzer();
  const bad=sectionWithCRC([0,0xb0,0x0d,0,1,0xc1,0,0,0,100,0xe1,0]);
  bad[bad.length-1]^=0xff;
  const x=analyzer.feed(psiPacket(0,bad));
  assert.equal(x.programs.length,0);
  assert.equal(x.crcErrors,1);
});
test("continuity discontinuity is visible, not silently discarded",()=>{
  const analyzer=new TransportAnalyzer();
  const x=analyzer.feed(new Uint8Array([
    ...psiPacket(0,sectionWithCRC([0,0xb0,0x0d,0,1,0xc1,0,0,0,100,0xe1,0]),0),
    ...psiPacket(0,sectionWithCRC([0,0xb0,0x0d,0,1,0xc1,0,0,0,100,0xe1,0]),3)
  ]));
  assert.equal(x.continuityErrors,1);
});
test("WebUSB only recognizes exact Hauppauge VID/PID and descriptors",()=>{
  const fake=mockDevice();
  assert.equal(supportedUSB(fake),true);
  assert.equal(bulkCandidates(fake).length,1);
  assert.equal(bulkCandidates(fake)[0].number,2);
  assert.equal(supportedUSB({...fake,productId:0x1234}),false);
  assert.throws(()=>bulkCandidates({...fake,productId:0x1234}));
});
test("read-only EM28xx register and one bounded genuine TS bulk transfer",async()=>{
  const fake=mockDevice();
  const probe=new WinTVProbe();
  probe.device=fake;
  assert.equal(await probe.readChipId(),0x68);
  const info=await probe.claimBulk();
  assert.equal(info.interfaceClaimed,0);
  const result=await probe.readBulkOnce();
  assert.equal(result.readBytes,188);
  assert.equal(result.summary.programs[0].service,100);
  await probe.release();
  assert.equal(fake.claimed,false);
  assert.equal(fake.opened,false);
});
