/* Real DVB driver bridge client. Requires explicit loopback server launch and
 * a session token copied by the user; never persists the token or auto-scans.
 * Network loopback access can require Chromium's user-granted permission.
 */
const $=id=>document.getElementById(id);
const ENDPOINT="http://127.0.0.1:8794";
let token="",connected=false,refreshHandle=null,scanning=false,lastJob=null;
const say=value=>{const el=$("tv-bridge-status");if(el)el.textContent=value};
const toggle=()=>{
 if($("tv-start-scan"))$("tv-start-scan").disabled=!connected||scanning;
 if($("tv-stop-scan"))$("tv-stop-scan").disabled=!connected||!scanning;
};
async function rpc(route,method="GET",body=null){
 if(!token)throw Error("Paste the local bridge token from your own terminal first.");
 const ctrl=new AbortController(),timeout=setTimeout(()=>ctrl.abort(),6000);
 try{
  const response=await fetch(ENDPOINT+route,{method,mode:"cors",cache:"no-store",
   headers:{"X-Tihulu-Bridge-Token":token,...(body?{"Content-Type":"application/json"}:{})},
   body:body?JSON.stringify(body):undefined,signal:ctrl.signal,credentials:"omit"});
  const data=await response.json();
  if(!response.ok)throw Error(data?.error||"Bridge HTTP "+response.status);
  return data;
 }catch(error){
  if(error?.name==="AbortError")throw Error("Local bridge did not respond within 6 s. Check the server and local network permission.");
  throw error;
 }finally{clearTimeout(timeout)}
}
function adapterOptions(devices){
 const selector=$("tv-adapter");if(!selector)return;
 selector.replaceChildren();
 for(const device of devices){
  const item=document.createElement("option");
  item.value=String(device.adapter);
  item.textContent="Adapter "+device.adapter+" · "+device.device;
  selector.append(item);
 }
 if(!devices.length){const item=document.createElement("option");item.value="";item.textContent="No usable /dev/dvb frontend";selector.append(item)}
}
function profileOptions(profiles){
 const selector=$("tv-profile");if(!selector)return;
 selector.replaceChildren();
 for(const profile of profiles.slice(0,90)){
  const item=document.createElement("option");item.value=profile.id;
  item.textContent=profile.name;selector.append(item);
 }
}
async function connect(){
 const supplied=$("tv-bridge-token")?.value?.trim()||"";
 if(supplied.length<20||supplied.length>200){say("Enter the actual session token printed by your local DVB bridge process. Tokens are not saved.");return}
 token=supplied;
 try{
  const caps=await rpc("/api/dvb/capabilities");
  adapterOptions(Array.isArray(caps.adapters)?caps.adapters:[]);
  profileOptions(Array.isArray(caps.profiles)?caps.profiles:[]);
  connected=!!caps.available;
  say("LOCAL HARDWARE CHECK: "+(caps.adapters?.length||0)+" Linux DVB frontend(s), dvbv5-scan "+(caps.scanTool?"installed":"NOT installed")+". "+
    (connected?"Ready for a user-requested physical DVB-T2 scan.":"Not ready: connect TV tuner and install dvb-tools / verify kernel firmware.")+
    " NO antenna positions or GPS location have been inferred.");
  window.dispatchEvent(new CustomEvent("tihulu:tv-bridge-hardware",{detail:{available:connected,adapters:caps.adapters||[]}}));
  toggle();
  if(connected)await status();
 }catch(error){
  connected=false;toggle();
  say("Unable to connect LOCAL DVB bridge: "+String(error.message||error)+
     ". Start: python3 -m rf_geolocation_center.native serve --enable-pages-bridge; "+
     "then copy the token printed there. Chrome may prompt for loopback network permission.");
 }
}
async function status(){
 const data=await rpc("/api/dvb/status");
 if(data.state==="RUNNING"||data.state==="STOPPING"){
  scanning=true;toggle();
  say("NATIVE TV SCANNING · Linux adapter "+data.adapter+" · profile "+data.profile+
    " · reading actual DVB service information. No fake progress or channels.");
  return;
 }
 scanning=false;toggle();
 if(data.state==="COMPLETE"&&Array.isArray(data.channels)&&data.channels.length){
  const signature=String(data.startedAt)+"|"+data.channels.length;
  if(signature!==lastJob){
   lastJob=signature;
   window.dispatchEvent(new CustomEvent("tihulu:native-dvb-channels",
      {detail:{channels:data.channels,source:"REAL LINUX DVBv5 SCAN / LOCAL BRIDGE",
               scannedAt:data.endedAt?new Date(data.endedAt*1000).toISOString():new Date().toISOString()}}));
  }
  say("TV SCAN COMPLETE · "+data.channels.length+" actual service entries. "+
    "Transport/network IDs and frequencies come from the connected DVB tuner. "+
    "Possible transmitter locations appear only where the public site catalog has matching frequency data.");
 }else if(data.state==="CANCELLED"){
  say("Native TV scan cancelled. No channels were fabricated.");
 }else if(data.state==="FAILED"||data.state==="NO_SERVICES"){
  say(data.state+" · "+data.details+". Check antenna, installed scan profile, tuner firmware or driver.");
 }else{
  say("Bridge connected. No DVB scan currently running. Choose adapter/profile and press Scan TV channels.");
 }
}
async function scan(){
 if(!connected||scanning)return;
 const adapter=Number($("tv-adapter")?.value),profile=$("tv-profile")?.value||"eu-uhf-t2";
 if(!$("tv-adapter")?.value||!Number.isInteger(adapter)||adapter<0){say("Select a detected Linux DVB adapter");return}
 scanning=true;toggle();
 try{
  const data=await rpc("/api/dvb/scan","POST",{adapter,profile});
  say("NATIVE DVB-T2 SCAN STARTED · adapter "+adapter+" · "+profile+
      ". This uses real /dev/dvb hardware through a token-protected localhost process.");
  if(data.state!=="RUNNING")await status();
  if(refreshHandle)clearInterval(refreshHandle);
  refreshHandle=setInterval(async()=>{
   try{await status();if(!scanning){clearInterval(refreshHandle);refreshHandle=null}}
   catch(error){clearInterval(refreshHandle);refreshHandle=null;scanning=false;toggle();
     say("Lost DVB bridge response: "+String(error.message||error)+". Check the local scanner; do not assume scan completed.") }
  },2600);
 }catch(error){scanning=false;toggle();say("TV scan was not started: "+String(error.message||error))}
}
async function stop(){
 if(!connected)return;
 try{
  await rpc("/api/dvb/stop","POST",{});
  say("Stop requested; waiting for native DVB scanner to release the TV tuner.");
 }catch(error){say("Could not stop local TV scanner: "+String(error.message||error)+
  ". If necessary stop your own local bridge process in its terminal.")}
}
export function initDVBBridge(){
 if(!$("tv-bridge-connect"))return;
 $("tv-bridge-connect").addEventListener("click",()=>{void connect()});
 $("tv-start-scan").addEventListener("click",()=>{void scan()});
 $("tv-stop-scan").addEventListener("click",()=>{void stop()});
 $("tv-show-map").addEventListener("click",()=>window.dispatchEvent(new Event("tihulu:show-tv-on-map")));
 // Token intentionally remains in page memory only. No localStorage, cookies,
 // cross-tab messages, background scanning or automatic credential submission.
 window.addEventListener("pagehide",()=>{if(refreshHandle)clearInterval(refreshHandle)});
 toggle();
}
