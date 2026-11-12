import test from "node:test";
import assert from "node:assert/strict";
import {EM28178,boardInitPlan,regReadSetup,regWriteSetup,
  i2cReadSetup,i2cWriteSetup,secondaryBusClock,parseSi2168Firmware,
  describeFirmware,validateI2cStatus,si2157TunePlan,si2168TunePlan,
  Em28xxTransport} from "../em28xx-driver-plan.js";

test("Hauppauge 2040:8268 maps to specific EM28178 board and tuner addresses",()=>{
  assert.equal(EM28178.vendor,0x2040);
  assert.equal(EM28178.product,0x8268);
  assert.equal(EM28178.demod7bit,0x64);
  assert.equal(EM28178.tuner7bit,0x60);
  assert.equal(EM28178.reg.ts,0x5f);
});
test("board initialization is exactly the card-specific sequenced plan, never automatic",()=>{
  const seq=boardInitPlan();
  assert.deepEqual(seq.map(x=>[x.reg,x.value,x.delayMs]),[
    [0x80,0xff,0],[0x0d,0xff,950],[0x80,0xbd,100],
    [0x80,0xfd,410],[0x80,0x7d,300],[0x80,0x7c,60],
    [0x0d,0x42,50],[0x5f,0x85,0]
  ]);
  assert.equal(seq.reduce((a,x)=>a+x.delayMs,0),1870);
});
test("EM28178 USB vendor packets use verified bridge requests",()=>{
  assert.deepEqual(regReadSetup(0x0a),{
    setup:{requestType:"vendor",recipient:"device",request:0,value:0,index:0x0a},length:1
  });
  assert.deepEqual(i2cReadSetup(0x64,13),{
    setup:{requestType:"vendor",recipient:"device",request:2,value:0,index:0xc8},length:13
  });
  assert.equal(i2cWriteSetup(0x64,[0x02],true).setup.request,2);
  assert.equal(i2cWriteSetup(0x60,[0x41,0],false).setup.request,3);
  assert.equal(i2cWriteSetup(0x60,[0x41,0]).setup.index,0xc0);
  assert.equal(regWriteSetup(0x80,[0xff]).data.byteLength,1);
  assert.throws(()=>i2cWriteSetup(0x60,[]),RangeError);
  assert.throws(()=>i2cReadSetup(0x80,1),RangeError);
});
test("secondary I2C clock leaves existing bits intact and enables bus B",()=>{
  assert.equal(secondaryBusClock(0x41),0x45);
  assert.equal(secondaryBusClock(0x00),0x44);
  assert.equal(validateI2cStatus(0),true);
  assert.throws(()=>validateI2cStatus(0x10),/NACK/);
});
test("old 8-byte Si2168 firmware records are exact and no modification occurs",()=>{
  const fw=Uint8Array.from(Array.from({length:24},(_,i)=>i));
  const p=parseSi2168Firmware(fw);
  assert.equal(p.format,"record8");
  assert.equal(p.recordCount,3);
  assert.deepEqual([...p.records[1]],[8,9,10,11,12,13,14,15]);
  assert.equal(describeFirmware(fw).sendToDevice,false);
});
test("new 17-byte Si2168 firmware record format and invalid headers",()=>{
  const fw=new Uint8Array(34);
  fw.set([6,1,2,3,4,5,6],0);
  fw.set([2,7,8],17);
  const p=parseSi2168Firmware(fw);
  assert.equal(p.format,"record17");
  assert.deepEqual([...p.records[0]],[1,2,3,4,5,6]);
  assert.deepEqual([...p.records[1]],[7,8]);
  assert.throws(()=>parseSi2168Firmware(new Uint8Array(19)));
  assert.throws(()=>parseSi2168Firmware(new Uint8Array(1024*1024+1)));
  fw[17]=17;
  assert.throws(()=>parseSi2168Firmware(fw),/Invalid Si2168/);
});
test("Si2157 tune plan sets exact RF value little-endian, delivery and IF",()=>{
  const p=si2157TunePlan({frequencyHz:538000000,bandwidthHz:8000000,delivery:"t2"});
  assert.equal(p.length,4);
  assert.deepEqual([...p[0].args],[0x14,0,3,7,0x28,0]);
  assert.deepEqual([...p[1].args],[0x14,0,2,7,1,0]);
  assert.deepEqual([...p[3].args],[0x41,0,0,0,0x80,0x3a,0x11,0x20]);
  assert.throws(()=>si2157TunePlan({frequencyHz:1}),RangeError);
});
test("Si2168 DVB-T2 uses 0x70 delivery setting and PLP is explicit",()=>{
  const p=si2168TunePlan({bandwidthHz:8000000,delivery:"t2"});
  assert.equal(p[1].response,3);
  assert.deepEqual([...p[2].args],[0x52,0xff,0]);
  assert.equal(p.at(-1).args[4],0x78);
  assert.deepEqual([...si2168TunePlan({delivery:"t",bandwidthHz:7000000})[1].args],
    [0x89,0x21,6,0x11,0xff,0x98]);
  assert.throws(()=>si2168TunePlan({delivery:"s",bandwidthHz:8000000}));
});
test("USB register writes are rejected unless explicit exclusive ownership",async()=>{
  const events=[];
  const mock={
    vendorId:0x2040,productId:0x8268,
    async controlTransferIn(setup,len){events.push(["in",setup,len]);
      return {status:"ok",data:new DataView(Uint8Array.of(0x68).buffer)};},
    async controlTransferOut(setup,data){events.push(["out",setup,data]);
      return {status:"ok",bytesWritten:data.length};}
  };
  const transport=new Em28xxTransport(mock);
  const id=await transport.registerRead(0x0a);
  assert.equal(id[0],0x68);
  await assert.rejects(transport.registerWrite(0x80,[0xff]),/exclusive ownership/);
  assert.equal(events.filter(x=>x[0]==="out").length,0);
  const granted=new Em28xxTransport(mock,{exclusive:true});
  await granted.registerWrite(0x80,[0xff]);
  assert.equal(events.filter(x=>x[0]==="out").length,1);
  assert.throws(()=>new Em28xxTransport({vendorId:1,productId:2}),/Not a supported/);
});
