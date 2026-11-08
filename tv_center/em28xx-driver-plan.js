/* WinTV-soloHD EM28178 / Si2168-D60 / Si2157 browser driver core.
 * Research-stage protocol adapter. No control-OUT is connected to the UI.
 * Source-derived commands: Linux drivers/media/usb/em28xx/{em28xx-core,
 * em28xx-i2c,em28xx-cards,em28xx-dvb}.c, media/dvb-frontends/si2168.c,
 * media/tuners/si2157.c (GPL-2.0+). Independent JS implementation.
 * GPL source attribution preserved; keep this module GPL-compatible.
 */
export const EM28178 = Object.freeze({
  vendor:0x2040,product:0x8268,demod7bit:0x64,tuner7bit:0x60,
  reg:{chip:0x0a,clock:0x06,i2cStatus:0x05,gpio:0x80,ts:0x5f},
  board:"EM28178_BOARD_PCTV_292E"
});
const bytes=x=>Uint8Array.from(x);
export const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const ensureU8=(n,label)=>{if(!Number.isInteger(n)||n<0||n>255)
  throw RangeError(label+" must be 0..255");return n;};
const ensure7Bit=n=>{if(!Number.isInteger(n)||n<8||n>0x77)
  throw RangeError("Invalid 7-bit I2C address");return n;};

/** Linux's board-specific GPIO reset sequence, not a generic recipe.
 * Not executed by default; writing GPIO without USB exclusive ownership can
 * interfere with a running Linux tuner.
 */
export function boardInitPlan(){
  return [
    {reg:0x80,value:0xff,delayMs:0},
    {reg:0x0d,value:0xff,delayMs:950},
    {reg:0x80,value:0xbd,delayMs:100},
    {reg:0x80,value:0xfd,delayMs:410},
    {reg:0x80,value:0x7d,delayMs:300},
    {reg:0x80,value:0x7c,delayMs:60},
    {reg:0x0d,value:0x42,delayMs:50},
    {reg:0x5f,value:0x85,delayMs:0}
  ];
}
/** USB transfers used by Linux EM28xx, not libusb-specific C declarations. */
export function regReadSetup(register,length=1,request=0){
  ensureU8(register,"Register");if(!Number.isInteger(length)||length<1||length>64)throw RangeError("Read size must be 1..64");
  return {setup:{requestType:"vendor",recipient:"device",request,
    value:0,index:register},length};
}
export function regWriteSetup(register,contents,request=0){
  ensureU8(register,"Register");
  const data=bytes(contents);
  if(!data.length||data.length>64)throw RangeError("Write size must be 1..64");
  return {setup:{requestType:"vendor",recipient:"device",request,
    value:0,index:register},data};
}
export function i2cWriteSetup(addr7,contents,stop=true){
  ensure7Bit(addr7);
  // EM28178: vendor request 2=write with STOP, 3=write with repeated START
  // The USB wIndex contains the 8-bit I2C address (addr7 << 1).
  return regWriteSetup(addr7<<1,contents,stop?2:3);
}
export function i2cReadSetup(addr7,length){
  ensure7Bit(addr7);
  return regReadSetup(addr7<<1,length,2);
}
export function validateI2cStatus(status){
  if(status===0)return true;
  if(status===0x10)throw Error("I2C NACK (0x10)");
  if(status===0x02||status===0x04)throw Error("I2C clock stretch / timeout");
  throw Error("Unexpected I2C bridge status "+status);
}
/** Board I2C bus 1 selection: Linux updates 0x06 bit 2 while preserving
 * the rest of the register, and defaults to WAIT+400kHz on this model.
 */
export function secondaryBusClock(original){
  ensureU8(original,"Old I2C clock register");
  return (original|0x04|0x40) & 0xff;
}
export function parseSi2168Firmware(fileBytes){
  if(!(fileBytes instanceof Uint8Array))throw TypeError("Firmware must be Uint8Array");
  if(fileBytes.length===0||fileBytes.length>1024*1024)
    throw RangeError("Firmware must be 1..1048576 bytes");
  const old=fileBytes.length%8===0;
  const newer=fileBytes.length%17===0 && fileBytes[0]>5;
  const format=newer?"record17":old?"record8":null;
  if(!format)throw Error("Not a known Si2168 firmware record format");
  const records=[];
  if(format==="record17"){
    for(let p=0;p<fileBytes.length;p+=17){
      const len=fileBytes[p];
      if(len<1||len>16)throw Error("Invalid Si2168 firmware command at record "+(p/17));
      records.push(fileBytes.slice(p+1,p+1+len));
    }
  }else{
    for(let p=0;p<fileBytes.length;p+=8)
      records.push(fileBytes.slice(p,p+8));
  }
  return {format,recordCount:records.length,records};
}
export function describeFirmware(fileBytes){
  const parsed=parseSi2168Firmware(fileBytes);
  return {format:parsed.format,recordCount:parsed.recordCount,
    bytes:fileBytes.length,sendToDevice:false,
    advisory:"Firmware parsed locally. Chip revision and distribution rights must be checked before writing to hardware."};
}
export function si2157TunePlan({frequencyHz,bandwidthHz=8000000,delivery="t2",ifHz=5000000}){
  if(!Number.isInteger(frequencyHz)||frequencyHz<48000000||frequencyHz>1000000000)
    throw RangeError("Terrestrial tuner frequency must be 48..1000 MHz");
  if(![5000000,6000000,7000000,8000000].includes(bandwidthHz))
    throw RangeError("Unverified tuner bandwidth");
  if(!["t","t2","c"].includes(delivery))throw RangeError("Unknown delivery");
  const bw=bandwidthHz/1000000;
  const sys=delivery==="c"?0x30:0x20;
  return [
    {name:"DTV mode",args:bytes([0x14,0,3,7,sys|bw,0]),response:4},
    {name:"Digital IF port",args:bytes([0x14,0,2,7,1,0]),response:4},
    {name:"IF frequency",args:bytes([0x14,0,6,7,(ifHz/1000)&255,((ifHz/1000)>>8)&255]),response:4},
    {name:"RF frequency",args:bytes([0x41,0,0,0,
      frequencyHz&255,(frequencyHz>>>8)&255,(frequencyHz>>>16)&255,
      (frequencyHz>>>24)&255]),response:1}
  ];
}
export function si2168TunePlan({bandwidthHz=8000000,delivery="t2",plp=0xff}){
  if(!["t","t2","c"].includes(delivery))throw RangeError("Unknown delivery");
  if(![6000000,7000000,8000000].includes(bandwidthHz))
    throw RangeError("Bandwidth must be 6,7,8 MHz");
  const bw=bandwidthHz/1000000;
  const ds=delivery==="t"?0x20:delivery==="t2"?0x70:0x30;
  if(!Number.isInteger(plp)||plp<0||plp>255)throw RangeError("PLP must be 0..255");
  const plan=[
    {name:"Demod probe",args:bytes([0x88,2,2,2,2]),response:5},
    {name:"Delivery setting",args:bytes(delivery==="t"?[0x89,0x21,6,0x11,0xff,0x98]:
      delivery==="c"?[0x89,0x21,6,0x11,0x89,0xf0]:
      [0x89,0x21,6,0x11,0x89,0x20]),response:3}
  ];
  if(delivery==="t2")plan.push({
    name:"PLP",args:bytes([0x52,plp,plp===0xff?0:1]),response:1
  });
  plan.push(
    {name:"Signal setup",args:bytes([0x51,3]),response:12},
    {name:"Frontend setup",args:bytes([0x12,8,4]),response:3},
    {name:"Frontend parameter 1",args:bytes([0x14,0,0x0c,0x10,0x12,0]),response:4},
    {name:"Frontend parameter 2",args:bytes([0x14,0,6,0x10,0x24,0]),response:4},
    {name:"Frontend parameter 3",args:bytes([0x14,0,7,0x10,0,0x24]),response:4},
    {name:"Delivery bandwidth & spectral inversion",args:bytes([0x14,0,0x0a,0x10,ds|bw,1]),response:4}
  );
  return plan;
}
/** No actual WebUSB device writes without an explicit caller-supplied
 * ownership grant. Access is further limited to claimed exact VID/PID.
 * Kept private to driver research; not invoked from Pages UI yet.
 */
export class Em28xxTransport {
  constructor(device,{exclusive=false}={}){
    if(device.vendorId!==EM28178.vendor||device.productId!==EM28178.product)
      throw Error("Not a supported Hauppauge 2040:8268 device");
    this.device=device;
    this.exclusive=exclusive;
  }
  async registerRead(reg,len=1,request=0){
    const op=regReadSetup(reg,len,request);
    const result=await this.device.controlTransferIn(op.setup,op.length);
    if(result.status!=="ok"||!result.data||result.data.byteLength!==len)
      throw Error("EM28xx register read failed");
    return new Uint8Array(result.data.buffer,result.data.byteOffset,result.data.byteLength).slice();
  }
  async registerWrite(reg,data,request=0){
    if(!this.exclusive)throw Error("Refusing USB register write without verified exclusive ownership");
    const op=regWriteSetup(reg,data,request);
    const result=await this.device.controlTransferOut(op.setup,op.data);
    if(result.status!=="ok"||result.bytesWritten!==op.data.length)
      throw Error("EM28xx register write failed");
  }
  async i2cRead(address,count){
    const op=i2cReadSetup(address,count);
    const result=await this.registerRead(op.setup.index,count,op.setup.request);
    const status=(await this.registerRead(0x05))[0];
    validateI2cStatus(status);
    return result;
  }
  async i2cWrite(address,data,stop=true){
    const op=i2cWriteSetup(address,data,stop);
    await this.registerWrite(op.setup.index,op.data,op.setup.request);
    for(let i=0;i<20;i++){
      const status=(await this.registerRead(0x05))[0];
      if(status===0)return;
      if(status===0x10||status===0x02||status===0x04)
        validateI2cStatus(status);
      await delay(5);
    }
    throw Error("I2C operation timed out");
  }
  async boardSecondaryBusSelect(){
    if(!this.exclusive)throw Error("Exclusive USB ownership required");
    const old=(await this.registerRead(0x06))[0];
    await this.registerWrite(0x06,[secondaryBusClock(old)]);
  }
}
