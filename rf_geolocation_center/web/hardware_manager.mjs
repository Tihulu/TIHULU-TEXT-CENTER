/* Explicit permission-first USB hardware panel.
 * The browser can enumerate ONLY previously permitted devices. Enumeration is NOT
 * a tuner claim, driver access test, signal reception or location measurement.
 * RTL2832U uses the existing app-owned WebUSB receiver; Hauppauge DVB requires
 * the OS DVB kernel frontend, which cannot be operated by static GitHub Pages.
 */
const $=id=>document.getElementById(id);
const VID_RTL=0x0bda,PID_RTL=0x2838,VID_HAUPPAUGE=0x2040;
let lastReceiverStatus="NOT CONNECTED";
let refreshing=false;
const set=(id,value)=>{const e=$(id);if(e)e.textContent=String(value)};
const hex=n=>Number(n).toString(16).padStart(4,"0");
function classify(device){
 if(device.vendorId===VID_RTL&&device.productId===PID_RTL)
  return {type:"rtl",label:"Nooelec / RTL2832U radio SDR",capability:"WebUSB receiver · 24–1766 MHz · dedicated app tuner"};
 if(device.vendorId===VID_HAUPPAUGE)
  return {type:"dvb",label:"Hauppauge USB device (exact model must be verified)",capability:"Linux DVB driver / native scan only · no browser DVB tuning"};
 return {type:"other",label:"Other USB device · permission only",capability:"No implemented receiver driver or location decoder in this app"};
}
function supported(){
 return !!(window.isSecureContext&&navigator.usb?.getDevices&&navigator.usb?.requestDevice);
}
function addRow(device){
 const root=$("hardware-list");if(!root)return;
 const cls=classify(device),row=document.createElement("div");row.className="hardware-device";
 const details=document.createElement("div");details.className="hardware-device-info";
 const title=document.createElement("strong");
 title.textContent=cls.label;
 const line=document.createElement("small");
 line.textContent="USB "+hex(device.vendorId)+":"+hex(device.productId)+
   " · "+String(device.manufacturerName||"Unknown manufacturer").slice(0,80)+
   " · "+String(device.productName||"Unnamed USB product").slice(0,100);
 const description=document.createElement("small");
 description.textContent=cls.capability+" · BROWSER PERMISSION GRANTED (not proof of open interface)";
 details.append(title,line,description);row.append(details);
 if(cls.type==="rtl"){
  const connect=document.createElement("button");connect.type="button";connect.className="primary";
  connect.textContent="Connect this RTL-SDR";
  connect.addEventListener("click",()=>{
   set("hardware-message","Opening this permitted Nooelec SDR. Other SDR software/tabs must release USB first.");
   window.dispatchEvent(new CustomEvent("tihulu:hardware-connect-rtl",{detail:{device}}));
  });
  row.append(connect);
 }else if(cls.type==="dvb"){
  const tv=document.createElement("button");tv.type="button";tv.className="secondary";
  tv.textContent="TV scan instructions";tv.addEventListener("click",()=>window.dispatchEvent(new Event("tihulu:hardware-tv-help")));
  row.append(tv);
 }
 root.append(row);
}
async function refresh({announce=false}={}){
 if(!supported()){
  set("hardware-count","WebUSB unavailable");
  set("hardware-message","WebUSB needs HTTPS and desktop Chrome, Brave or Edge. Firefox/Safari cannot expose this browser device picker. A TV tuner still requires its native DVB driver.");
  const root=$("hardware-list");
  if(root){root.replaceChildren();const p=document.createElement("p");p.textContent="WebUSB device listing unavailable in this browser.";root.append(p)}
  return [];
 }
 if(refreshing)return [];
 refreshing=true;
 try{
  const devices=await navigator.usb.getDevices();
  const root=$("hardware-list");if(root)root.replaceChildren();
  for(const device of devices.slice(0,40))addRow(device);
  if(root&&!devices.length){
   const p=document.createElement("p");p.textContent="No USB device permissions yet. Click + Add USB device to open the browser permission chooser.";root.append(p);
  }
  set("hardware-count",devices.length+" permitted USB device"+(devices.length===1?"":"s"));
  if(announce)set("hardware-message",devices.length+" permitted device(s) detected by the browser. This is NOT proof a USB interface can be claimed. Use Connect this RTL-SDR to start a supported radio receiver.");
  return devices;
 }catch(error){
  set("hardware-message","Cannot list browser-permitted USB devices: "+String(error?.message||error));return [];
 }finally{refreshing=false}
}
async function addDevice(){
 if(!supported()){
  await refresh({announce:true});return;
 }
 try{
  set("hardware-message","Choose a physical USB device in the browser prompt. Permission only; no RF capture or background service starts.");
  // A real user click is required for the browser's native WebUSB picker.
  // Empty filters = generic USB permission request; protected-class devices may
  // remain unavailable and no unauthorized device is enumerated.
  const device=await navigator.usb.requestDevice({filters:[]});
  const c=classify(device);
  set("hardware-message","USB permission added: "+c.label+" ("+hex(device.vendorId)+":"+hex(device.productId)+"). "+
    (c.type==="rtl"?"Use Connect this RTL-SDR to open the actual radio receiver.":
     c.type==="dvb"?"DVB driver access is native Linux-only; WebUSB permission does not enable TV tuning.":
      "This device has no implemented decoder; it is NOT a location source."));
  await refresh();
 }catch(error){
  if(error?.name==="NotFoundError")set("hardware-message","No USB device selected. Nothing was opened or changed.");
  else set("hardware-message","USB device permission failed: "+String(error?.message||error)+
    ". Browser USB policy, protected interfaces or OS ownership may prevent selection.");
 }
}
export function initHardwareManager({setView}){
 if(!$("hardware-add"))return;
 const mount=(source,targetId)=>{
  const el=$(source),dest=$(targetId);if(el&&dest)dest.append(el);
 };
 // Move already-initialized REAL controls, including their existing native
 // user-gesture handlers, from hidden advanced sections into the main UI.
 mount("usb-select","hardware-rtl-slot");
 mount("usb-selftest","hardware-test-slot");
 mount("serial-connect","hardware-gnss-slot");
 mount("serial-disconnect","hardware-gnss-slot");
 $("hardware-add").addEventListener("click",()=>{void addDevice()});
 $("home-tv-identify")?.addEventListener("click",async()=>{
  if(!supported()){
   set("home-tv-state","TV USB WebUSB listing unavailable. Use local DVB adapter discovery: Connect TV tuner and Approve.");
   return;
  }
  set("home-tv-state","Opening generic browser USB permission selector for TV device identification only. Linux DVB driver remains in control.");
  await addDevice();
  const devices=await refresh();
  const tv=devices.filter(device=>classify(device).type==="dvb");
  if(tv.length)set("home-tv-state",tv.length+" permitted Hauppauge USB device(s) listed; physical channel scan still requires the local Linux DVB frontend. Click Connect TV tuner.");
  else set("home-tv-state","No browser-permitted Hauppauge USB device listed. This does not prove the TV tuner is missing: Linux DVB may own its protected USB interface. Connect TV tuner to detect /dev/dvb natively.");
 });
 $("hardware-refresh").addEventListener("click",()=>{void refresh({announce:true})});
 $("hardware-release")?.addEventListener("click",()=>$("live-release")?.click());
 $("radio-connect-rtl")?.addEventListener("click",()=>window.dispatchEvent(new CustomEvent("tihulu:hardware-connect-rtl",{detail:{device:null}})));
 $("radio-manage-usb")?.addEventListener("click",()=>{
  setView("earth");const details=$("simple-hardware");
  if(details){details.open=true;details.scrollIntoView({behavior:"smooth",block:"center"})}
 });
 window.addEventListener("tihulu:hardware-tv-help",()=>{
  setView("radio");const e=$("simple-tv-guide");if(e){e.open=true;e.scrollIntoView({behavior:"smooth",block:"nearest"})}
 });
 window.addEventListener("tihulu:receiver-status",e=>{
  lastReceiverStatus=String(e.detail?.status||"NOT CONNECTED");
  const msg=String(e.detail?.message||"").slice(0,500);
  set("hardware-message","RTL-SDR: "+lastReceiverStatus+" · "+msg);
 });
 if(!supported()){
  $("hardware-add").disabled=true;$("hardware-refresh").disabled=true;
 }
 if(navigator.usb?.addEventListener){
  navigator.usb.addEventListener("connect",()=>{void refresh({announce:true})});
  navigator.usb.addEventListener("disconnect",()=>{void refresh({announce:true})});
 }
 void refresh();
}
