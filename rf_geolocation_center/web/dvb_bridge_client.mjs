/* Real DVB driver bridge client. Requires explicit loopback server launch and
 * a session token copied by the user; never persists the token or auto-scans.
 * Network loopback access can require Chromium's user-granted permission.
 */
const $=id=>document.getElementById(id);
const ENDPOINT="http://127.0.0.1:8794";
let token="",connected=false,refreshHandle=null,scanning=false,lastJob=null,pairPopup=null,pairNonce="",pairAction="tv";
let closed=false,ownerId="",ownedScan=false,scanRequest=null,stopRequest=null,messageListener=null;
const pendingRequests=new Set();
const say=value=>{const el=$("tv-bridge-status"),home=$("home-tv-state");if(el)el.textContent=value;if(home)home.textContent=String(value).slice(0,260)};
const toggle=()=>{
 if($("tv-start-scan"))$("tv-start-scan").disabled=!connected||scanning;
 if($("tv-stop-scan"))$("tv-stop-scan").disabled=!connected||!scanning;
 if($("home-tv-scan"))$("home-tv-scan").disabled=!connected||scanning;
};
async function rpc(route,method="GET",body=null,shutdown=false){
 if(closed&&!shutdown)throw Error("Bridge client stopped");
 if(!token)throw Error("Local approval required. Click Connect TV tuner, then approve the localhost pairing window.");
 const ctrl=new AbortController(),timeout=setTimeout(()=>ctrl.abort(),6000);
 pendingRequests.add(ctrl);
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
 }finally{clearTimeout(timeout);pendingRequests.delete(ctrl)}
}
function adapterOptions(devices){
 const selector=$("tv-adapter");if(!selector)return;
 selector.replaceChildren();
 for(const device of devices){
  const item=document.createElement("option");
  item.value=String(device.adapter);
  item.textContent="Adapter "+device.adapter+" · "+(device.manufacturer||"Linux DVB")+": "+(device.product||device.device)+
    (device.usbId?" · USB "+device.usbId:"");
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
function choosePairingMode(){
 return location.origin==="https://tihulu.github.io"?"pages":"local";
}
function pair(action="tv"){
 if(closed)return;
 if(!window.crypto?.getRandomValues){say("Secure browser crypto unavailable. Open the trusted localhost app directly.");return}
 const rand=new Uint8Array(24);crypto.getRandomValues(rand);
 pairNonce=Array.from(rand,b=>b.toString(16).padStart(2,"0")).join("");
 pairAction=action;
 const url=ENDPOINT+"/pair?origin="+choosePairingMode()+"&nonce="+encodeURIComponent(pairNonce)+
   (choosePairingMode()==="local"?"&from="+encodeURIComponent(location.hostname==="localhost"?"localhost":"127.0.0.1"):"");
 // Must open synchronously in direct click handler to avoid popup blockers.
 pairPopup=window.open(url,"tihulu_tv_pair","width=620,height=490");
 if(!pairPopup){
  say("Pop-up blocked. Allow the official TIHULU page to open localhost:8794, then retry Connect TV.");
  return;
 }
 say("Approve this browser tab in the LOCAL TIHULU pairing window. No code or token to paste. "+
     "The companion must already be running on 127.0.0.1:8794; official Pages needs --enable-pages-bridge.");
}
async function connect(){
 if(!token){pair("tv");return}
 await connectedStatus();
}
async function connectedStatus(){
 if(closed)return;
 try{
  const caps=await rpc("/api/dvb/capabilities");
  if(closed)return;
  adapterOptions(Array.isArray(caps.adapters)?caps.adapters:[]);
  profileOptions(Array.isArray(caps.profiles)?caps.profiles:[]);
  connected=!!caps.available;
  const matchedHauppauge=Array.isArray(caps.adapters)?caps.adapters.filter(a=>a.likelyHauppauge).length:0;
  say("LOCAL HARDWARE CHECK: "+(caps.adapters?.length||0)+" Linux DVB frontend(s), "+matchedHauppauge+" Hauppauge-like adapter(s) via sysfs, dvbv5-scan "+(caps.scanTool?"installed":"NOT installed")+". "+
    (connected?"Ready for a user-requested physical DVB-T2 scan.":"Not ready: connect TV tuner and install dvb-tools / verify kernel firmware.")+
    " NO antenna positions or GPS location have been inferred.");
  window.dispatchEvent(new CustomEvent("tihulu:tv-bridge-hardware",{detail:{available:connected,adapters:caps.adapters||[]}}));
  toggle();
  if(connected)await status();
 }catch(error){
  connected=false;toggle();
  say("Unable to connect local DVB tuner: "+String(error.message||error)+
     ". Start python3 -m rf_geolocation_center.native serve --enable-pages-bridge; then Connect TV and Approve in localhost window. Browsers may require a local network permission.");
 }
}
async function status(){
 if(closed)return;
 const data=await rpc("/api/dvb/status");
 if(closed)return;
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
 if(closed||!connected||scanning)return;
 const adapter=Number($("tv-adapter")?.value),profile=$("tv-profile")?.value||"eu-uhf-t2";
 if(!$("tv-adapter")?.value||!Number.isInteger(adapter)||adapter<0){say("Select a detected Linux DVB adapter");return}
 if(!window.crypto?.getRandomValues){say("Secure owner identity unavailable; refusing native scan");return}
 const bytes=new Uint8Array(24);window.crypto.getRandomValues(bytes);
 ownerId=Array.from(bytes,b=>b.toString(16).padStart(2,"0")).join("");
 ownedScan=true;scanning=true;toggle();
 try{
  scanRequest=rpc("/api/dvb/scan","POST",{adapter,profile,owner:ownerId});
  const data=await scanRequest;
  if(closed)return;
  say("NATIVE DVB-T2 SCAN STARTED · adapter "+adapter+" · "+profile+
      ". This uses real /dev/dvb hardware through a token-protected localhost process.");
  if(data.state!=="RUNNING")await status();
  if(refreshHandle)clearInterval(refreshHandle);
  refreshHandle=setInterval(async()=>{
   if(closed)return;
   try{await status();if(!scanning){clearInterval(refreshHandle);refreshHandle=null}}
   catch(error){clearInterval(refreshHandle);refreshHandle=null;scanning=false;toggle();
     say("Lost DVB bridge response: "+String(error.message||error)+". Check the local scanner; do not assume scan completed.") }
  },2600);
 }catch(error){
   if(!closed){scanning=false;ownedScan=false;toggle();say("TV scan was not started: "+String(error.message||error))}
 }finally{scanRequest=null}
}
async function readRadioMetadata(){
 if(closed)return;
 const output=$("radio-rds-results"),info=$("radio-rds-status");
 if(!token){pair("radio");if(info)info.textContent="Approve the LOCAL receiver bridge pairing window. RDS/DAB uses the existing receiver without claiming USB.";return}
 try{
  const response=await rpc("/api/radio/decoded");
  if(closed)return;
  if(output)output.replaceChildren();
  const records=Array.isArray(response.events)?response.events.slice(0,60):[];
  if(info)info.textContent=(response.available?"LOCAL TEXT CENTER CONNECTED · ":"LOCAL TEXT CENTER UNAVAILABLE · ")+
    records.length+" stored, broadcaster-supplied FM RDS / DAB metadata record(s). "+
    String(response.message||"")+" No receiver position implied.";
  for(const item of records.slice(0,40)){
   const row=document.createElement("div");row.className="simple-channel";
   const label=document.createElement("strong");
   label.textContent=String(item.station||item.title||"Broadcast metadata").slice(0,140)+
     (Number.isFinite(item.frequencyMHz)?" · "+item.frequencyMHz.toFixed(3)+" MHz":"");
   const detail=document.createElement("small");
   detail.textContent=String(item.title||"")+" · "+String(item.body||"").slice(0,220)+
     " · "+String(item.observedAt||"TIME UNKNOWN")+
     " · BROADCASTER-SUPPLIED / UNAUTHENTICATED / NOT POSITION";
   row.append(label,detail);if(output)output.append(row);
  }
  window.dispatchEvent(new CustomEvent("tihulu:radio-metadata",{detail:{events:records,source:"LOCAL TEXT CENTER / EXISTING FM RDS & DAB RECEIVER"}}));
 }catch(error){
  if(info)info.textContent="Radio metadata bridge unavailable: "+String(error.message||error)+
    ". No WebUSB claim was attempted. Run local Text Center capture separately after releasing the RTL-SDR from this tab.";
 }
}
async function stop(){
 if(!token||!ownedScan||!ownerId)return;
 if(stopRequest)return stopRequest;
 const id=ownerId;
 stopRequest=(async()=>{
  try{
   await rpc("/api/dvb/stop","POST",{owner:id},true);
   if(!closed)say("Stop requested for this tab's owned native DVB scan. Other clients remain active.");
  }catch(error){
   if(!closed)say("Own scan stop was not acknowledged: "+String(error.message||error)+
     ". Stop the native service you started if necessary; no other clients were touched.");
   throw error;
  }finally{
   scanning=false;ownedScan=false;
   if(refreshHandle){clearInterval(refreshHandle);refreshHandle=null;}
   if(!closed)toggle();
  }
 })().finally(()=>{stopRequest=null});
 return stopRequest;
}
async function quit(){
 if(closed)return stopRequest||Promise.resolve();
 closed=true;
 if(refreshHandle){clearInterval(refreshHandle);refreshHandle=null;}
 // In-flight scan request may have reached the local server; wait its bounded HTTP
 // request before sending the owner-scoped stop to avoid Stop-before-Start races.
 if(scanRequest)try{await scanRequest}catch{}
 let failure=null;
 if(ownedScan&&ownerId)try{await stop()}catch(error){failure=error}
 for(const ctrl of pendingRequests)ctrl.abort();
 pendingRequests.clear();
 if(messageListener)window.removeEventListener("message",messageListener);
 messageListener=null;
 if(pairPopup&&!pairPopup.closed)pairPopup.close();
 pairPopup=null;pairNonce="";token="";connected=false;scanning=false;lastJob=null;
 if(failure)throw failure;
}
export function initDVBBridge(){
 if(!$("tv-bridge-connect"))return {quit:async()=>{}};
 messageListener=event=>{
  if(closed)return;
  // A pairing result is accepted ONLY from our exact spawned loopback popup
  // with a cryptographically unpredictable one-use challenge.
  if(event.origin!==ENDPOINT||!pairPopup||event.source!==pairPopup||
     event.data?.type!=="tihulu:dvb-bridge-paired"||event.data?.nonce!==pairNonce||
     typeof event.data?.token!=="string"||event.data.token.length<20||event.data.token.length>200)return;
  token=event.data.token;pairNonce="";pairPopup=null;
  if(pairAction==="radio")void readRadioMetadata();
  else void connectedStatus();
 };
 window.addEventListener("message",messageListener);
 $("tv-bridge-connect").addEventListener("click",()=>{void connect()});
 $("home-tv-connect")?.addEventListener("click",()=>{void connect()});
 $("home-tv-scan")?.addEventListener("click",()=>{void scan()});
 $("hard-stop")?.addEventListener("click",()=>{if(scanning)void stop()});
 $("tv-start-scan").addEventListener("click",()=>{void scan()});
 $("tv-stop-scan").addEventListener("click",()=>{void stop()});
 $("tv-show-map").addEventListener("click",()=>window.dispatchEvent(new Event("tihulu:show-tv-on-map")));
 $("radio-read-rds")?.addEventListener("click",()=>{void readRadioMetadata()});
 // Pairing secret is transient and delivered via explicit localhost approval;
 // no localStorage, cookies, periodic scans or automatic credential submission.
 window.addEventListener("pagehide",()=>{void quit().catch(()=>{})});
 toggle();
 return {quit,stop};
}
