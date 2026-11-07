/* Experimental, deliberately non-mutating WinTV-soloHD WebUSB transport probe.
 * Linux em28xx source maps 2040:8268 to EM28178_BOARD_PCTV_292E (bulk).
 * This is NOT a DVB-T2 tuner/demodulator implementation. No vendor OUT,
 * firmware upload, kernel-driver detach, configuration change or USB reset.
 */
import {TransportAnalyzer} from "./ts-analyzer.js";

export const WINTV = Object.freeze({vendorId:0x2040,productId:0x8268,
  board:"Hauppauge WinTV-soloHD (retail bulk), Empia EM28178"});
export function supportedUSB(device){
  return !!device && device.vendorId===WINTV.vendorId && device.productId===WINTV.productId;
}
export function endpointsOf(device){
  if(!supportedUSB(device))throw Error("Unsupported TV USB device ID");
  const configurations = device.configurations || (device.configuration?[device.configuration]:[]);
  return configurations.flatMap(cfg=>(cfg.interfaces||[]).flatMap(iface=>
    (iface.alternates||[]).flatMap(alt=> (alt.endpoints||[]).map(ep=>({
      configuration:cfg.configurationValue,
      interface:iface.interfaceNumber,
      alternate:alt.alternateSetting,
      type:ep.type,
      direction:ep.direction,
      number:ep.endpointNumber,
      packetSize:ep.packetSize
    }))));
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
    this.lastError="";
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
      linuxFrontendMayBeBusy:true};
  }
  async openForRead(){
    if(!this.device)throw Error("Select the WinTV-soloHD first");
    if(!this.device.opened)await this.device.open();
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
      throw Error("USB interface is unavailable (possibly owned by Linux em28xx). "+
                  "No driver was detached. Use native DVB or free the tuner safely. "+
                  this.lastError);
    }
  }
  async readBulkOnce(){
    if(this.claimed===null||this.endpoint===null)
      throw Error("Explicitly claim the bulk-IN interface first");
    // At most 16384 bytes. This probes an already-active stream only.
    // It does not initialize the EM28xx TS bridge, Si2168, Si2157 or PLL.
    const result=await this.device.transferIn(this.endpoint,16384);
    if(result.status!=="ok"||!result.data)
      throw Error("USB bulk-IN did not return an OK transport result");
    const data=new Uint8Array(result.data.buffer,result.data.byteOffset,
                              result.data.byteLength);
    this.analyzer.feed(new Uint8Array(data));
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
