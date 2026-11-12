/* Experimental, deliberately non-mutating WinTV-soloHD WebUSB transport probe.
 * Linux em28xx source maps 2040:8268 to EM28178_BOARD_PCTV_292E (bulk).
 * This is NOT a DVB-T2 tuner/demodulator implementation. No vendor OUT,
 * firmware upload, kernel-driver detach, configuration change or USB reset.
 */
import {TransportAnalyzer} from "./ts-analyzer.js";
import {classifyUsbFailure} from "./webusb-access-guide.js";

export const WINTV = Object.freeze({vendorId:0x2040,productId:0x8268,
  board:"Hauppauge WinTV-soloHD (retail bulk), Empia EM28178"});
export function supportedUSB(device){
  return !!device && device.vendorId===WINTV.vendorId && device.productId===WINTV.productId;
}
export function endpointsOf(device){
  if(!supportedUSB(device))throw Error("Unsupported TV USB device ID");
  const configurations = device.configurations || (device.configuration?[device.configuration]:[]);
  const results=[];
  for(const cfg of configurations){
    for(const iface of (cfg.interfaces||[])){
      for(const alt of (iface.alternates||[])){
        for(const ep of (alt.endpoints||[])){
          results.push({
            configuration:cfg.configurationValue,
            interface:iface.interfaceNumber,
            alternate:alt.alternateSetting,
            type:ep.type,
            direction:ep.direction,
            number:ep.endpointNumber,
            packetSize:ep.packetSize
          });
        }
      }
    }
  }
  return results;
}
export function bulkCandidates(device){
  return endpointsOf(device).filter(e=>e.type==="bulk"&&e.direction==="in");
}
const hex=n=>"0x"+Number(n).toString(16).padStart(2,"0");
export class WinTVProbe {
  constructor(){
    this.device=null;this.claimed=null;this.endpoint=null;
    this.analyzer=new TransportAnalyzer();
    this.chipId=null;
    this.lastError="";this.lastErrorStage=null;
  }
  requirePermission(){
    if(!navigator.usb || !globalThis.isSecureContext)
      throw Error("WebUSB requires a compatible Chromium browser and secure context");
  }
  async select(){
    this.requirePermission();
    await this.release();
    const device=await navigator.usb.requestDevice({
      filters:[{vendorId:WINTV.vendorId,productId:WINTV.productId}]
    });
    if(!supportedUSB(device))throw Error("Selected device ID does not match WinTV-soloHD 2040:8268");
    this.device=device;this.analyzer=new TransportAnalyzer();
    this.lastError="";this.lastErrorStage=null;
    return this.describe();
  }
  async permitted(){
    this.requirePermission();
    const devices=(await navigator.usb.getDevices()).filter(supportedUSB);
    if(!this.device&&devices.length===1)this.device=devices[0];
    return devices.length;
  }
  describe(){
    if(!this.device)return {connected:false,model:WINTV.board};
    return {connected:true,model:WINTV.board,usbVersion:this.device.usbVersionMajor+"."+this.device.usbVersionMinor,
      deviceVersion:this.device.deviceVersionMajor+"."+this.device.deviceVersionMinor,
      opened:!!this.device.opened,
      configurations:(this.device.configurations||[]).length,
      endpoints:endpointsOf(this.device),chipId:this.chipId===null?null:hex(this.chipId),
      interfaceClaimed:this.claimed,
      fullDvbDriverImplemented:false,
      linuxFrontendMayBeBusy:true,
      lastError:this.lastError||null,lastErrorStage:this.lastErrorStage};
  }
  async openForRead(){
    if(!this.device)throw Error("Select the WinTV-soloHD first");
    if(!this.device.opened){
      try{
        await this.device.open();
        this.lastError="";this.lastErrorStage=null;
      }catch(error){
        // Selecting a USB device in the browser does not provide Linux
        // /dev/bus/usb rights. Keep the original error for troubleshooting.
        const advice=classifyUsbFailure(error,"open");
        this.lastError=advice.raw;this.lastErrorStage="open";
        const failure=new Error(advice.title+": "+advice.explanation);
        failure.name="WebUSBOpenError";
        failure.usbStage="open";failure.usbReason=advice.code;
        failure.usbOriginal=advice.raw;
        throw failure;
      }
    }
    if(!this.device.configuration)
      throw Error("No active USB configuration. Do not change configurations while Linux DVB is connected.");
    return this.describe();
  }
  async readChipId(){
    // Linux em28xx: em28xx_read_reg(EM28XX_R0A_CHIPID), USB vendor IN
    // (request 0x00, index 0x0a, value 0). Never writes device registers.
    await this.openForRead();
    const result=await this.device.controlTransferIn({
      requestType:"vendor",recipient:"device",request:0,
      value:0,index:0x0a
    },1);
    if(result.status!=="ok"||!result.data||result.data.byteLength!==1)
      throw Error("No valid EM28xx chip-ID register response");
    this.chipId=result.data.getUint8(0);
    return this.chipId;
  }
  async claimBulk(){
    await this.openForRead();
    if(this.claimed!==null)return this.describe();
    const active=this.device.configuration.configurationValue;
    const candidates=bulkCandidates(this.device).filter(x=>
      x.configuration===active && x.alternate===0);
    if(candidates.length!==1){
      throw Error(candidates.length===0?
        "No unambiguous bulk-IN endpoint at active alternate setting 0.":
        "Multiple bulk-IN endpoints; refuse to guess tuner endpoint.");
    }
    const endpoint=candidates[0];
    try{
      // It should fail when Linux em28xx already owns the interface.
      // Never attempt kernel-driver detach, sudo, or USB reset.
      await this.device.claimInterface(endpoint.interface);
      this.claimed=endpoint.interface;
      this.endpoint=endpoint.number;
      return this.describe();
    }catch(error){
      this.lastError=String(error.message||error);
      this.lastErrorStage="claim";
      const advice=classifyUsbFailure(error,"claim");
      const failure=new Error(advice.title+": "+advice.explanation+
        " No driver was detached. Original: "+this.lastError);
      failure.name="WebUSBClaimError";
      failure.usbStage="claim";failure.usbReason=advice.code;
      failure.usbOriginal=this.lastError;
      throw failure;
    }
  }
  async readBulkBytes(length=16384){
    if(this.claimed===null||this.endpoint===null)
      throw Error("Explicitly claim the bulk-IN interface first");
    if(!Number.isInteger(length)||length<1||length>16384)
      throw RangeError("USB bulk reads must be 1..16384 bytes");
    // This does not enable the TS bridge or initialize the Si2168/Si2157.
    const result=await this.device.transferIn(this.endpoint,length);
    if(result.status!=="ok"||!result.data)
      throw Error("USB bulk-IN did not return an OK transport result");
    if(result.data.byteLength>length)
      throw Error("USB transfer exceeded the requested size");
    return new Uint8Array(result.data.buffer,result.data.byteOffset,
                          result.data.byteLength).slice();
  }
  async readBulkOnce(){
    const data=await this.readBulkBytes();
    this.analyzer.feed(data);
    return {readBytes:data.length,summary:this.analyzer.summary()};
  }
  async release(){
    const device=this.device;
    if(!device)return;
    const claimed=this.claimed;
    this.claimed=null;this.endpoint=null;this.device=null;
    try{
      if(claimed!==null&&device.opened)await device.releaseInterface(claimed);
    }finally{
      if(device.opened)await device.close();
    }
  }
  onDisconnect(device){
    if(this.device===device){
      this.device=null;this.claimed=null;this.endpoint=null;
      return true;
    }
    return false;
  }
}
