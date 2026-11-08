/* Shared native-TV web controls for GitHub Pages and PIN-paired LAN.
 * WebUSB transport experiments are intentionally NOT treated as RF tuners.
 */
import {scanFields,scanRequest,scanTitle,scanControls} from "./scan-ui-state.js";

(() => {
  const root=document.getElementById("web-control-root");
  if(!root)return;
  // Public GitHub Pages has no privileges to operate the native DVB tuner.
  // Do not render dead scan buttons or a misleading "receiver disconnected".
  if(location.hostname==="tihulu.github.io"){
    root.innerHTML=`
      <section class="panel" id="web-pages-tv-launch">
        <h2>Browser-only DVB-T2 driver · Status</h2>
        <p>The direct WebUSB transport and board-protocol modules are being ported from the Linux driver. Browser recording analysis, MPEG-TS/WASM preview and WebGPU speech AI need no local service. Full automatic frequency scanning is not yet hardware-verified.</p>
        <a class="link-button" href="#browser-driver-center">Open direct USB driver tools</a>
        <small>Chromium WebUSB is required to claim the USB tuner. WebAssembly handles software and recording codecs, not Linux kernel driver ownership.</small>
      </section>`;
    return;
  }
  root.innerHTML=`
    <section class="panel" id="web-channels-panel">
      <h2>Real TV / Radio · Favorites</h2>
      <p id="web-channel-origin">Connect to native TV Center to load genuine scanned services.</p>
      <div class="actions">
        <select id="web-filter" aria-label="Channel filter">
          <option value="all">All scanned</option><option value="included">Included</option>
          <option value="favorite">Favorites</option><option value="new">New after scan</option>
          <option value="tv">Television</option><option value="radio">Radio</option>
        </select>
        <button id="web-refresh" class="secondary" disabled>Refresh channels</button>
      </div>
      <div id="web-channel-list" class="web-channel-list"><p>No native receiver connected.</p></div>
      <p id="web-channel-msg" role="status"></p>
    </section>
    <section class="panel" id="web-scan-panel">
      <h2>Automatic DVB scan <span class="web-mini-subtitle">Native receiver</span></h2>
      <p id="web-scan-backend" class="web-scan-backend">Checking the native DVB frontend…</p>
      <p id="web-scan-context">Select an antenna or cable profile. Real RF scanning needs a native Linux/Pi tuner; WebUSB device diagnostics cannot scan TV channels.</p>
      <div class="web-scan-field" id="web-delivery-field">
        <label for="web-medium">Reception type</label>
        <select id="web-medium">
          <option value="t">Terrestrial antenna · DVB-T/T2</option>
          <option value="c">Cable television · DVB-C</option>
          <option value="s">Satellite dish · DVB-S/S2</option>
        </select>
      </div>
      <div class="web-scan-field" id="web-country-field">
        <label for="web-country">Country / frequency plan</label>
        <select id="web-country"><option value="DE">Germany</option><option value="TR">Türkiye</option></select>
        <small>Used only for antenna and cable frequency scanning.</small>
      </div>
      <div class="web-scan-field" id="web-satellite-field" hidden>
        <label for="web-satellite">Dish position / satellite</label>
        <select id="web-satellite" disabled>
          <option value="S42E0">Türksat · 42°E</option>
          <option value="S13E0">Hot Bird · 13°E</option>
          <option value="S19E2">Astra · 19.2°E</option>
          <option value="S7E0">Eutelsat · 7°E</option>
        </select>
        <small>Satellite transponders depend on the orbital position and LNB, not the country. Requires a real DVB-S/S2 tuner.</small>
      </div>
      <div class="actions">
        <button id="web-scan-start" disabled>Start full scan</button>
        <button id="web-scan-cancel" class="secondary" disabled>Cancel scan</button>
      </div>
      <div class="actions">
        <button id="web-stop" class="secondary" disabled>Stop playing / release tuner</button>
      </div>
      <p id="web-scan-state" role="status">Checking the local TV service and connected DVB tuner…</p>
      <p id="web-signal">No RF readings — receiver disconnected.</p>
      <div class="web-channel-log" id="web-scan-log" aria-label="Real-time scan log"></div>
      <small id="web-scan-limitation">WebUSB permission alone never enables Start full scan. Native DVB hardware is required.</small>
    </section>
    <section class="panel" id="web-model-panel">
      <h2>Native subtitles &amp; installed AI models</h2>
      <p id="web-model-info">Native AI is optional. Install/remove native packs in desktop Settings. Browser AI Studio runs independently.</p>
      <div class="actions">
        <select id="web-caption-mode" aria-label="Native subtitle mode">
          <option value="off">Off</option><option value="teletext">Teletext subtitles</option>
          <option value="page">Interactive Teletext page</option>
          <option value="asr">Native Whisper ASR</option>
          <option value="auto">Teletext → ASR fallback</option>
        </select>
        <button id="web-caption-set" disabled>Set native subtitles</button>
      </div>
    </section>`;

  const $=id=>document.getElementById(id);
  const connector=()=>window.tihuluTVWeb;
  const connected=()=>Boolean(connector()?.connected());
  const show=(id,message)=>{$(id).textContent=message;};
  const make=(tag,value,cls="")=>{
    const el=document.createElement(tag);el.textContent=value||"";
    if(cls)el.className=cls;return el;
  };
  let channels=[], channelBusy=false, pending=false, scanning=false;
  let playing=false, signal="", scanMessage="", frontendAvailable=true, prevConnected=false, profileDirty=false;
  let profileSyncNeeded=true;

  function resetDisconnected(){
    channels=[];scanning=false;playing=false;signal="";scanMessage="";
    frontendAvailable=false;
    show("web-channel-origin","Connect or pair with native TV Center to see actual scanned services.");
    show("web-channel-msg","");
    show("web-model-info","Native model status needs a paired receiver. Browser AI Studio works independently.");
    $("web-channel-list").replaceChildren(make("p","No native receiver connected."));
    $("web-scan-log").replaceChildren();
  }
  function paint(){
    const state=scanControls({connected:connected(),medium:$("web-medium").value,
      scanning,playing,pending,signal,scanMessage,frontendAvailable});
    const satField=$("web-satellite-field"), countryField=$("web-country-field");
    satField.hidden=!state.showSatellite;
    countryField.hidden=!state.showCountry;
    $("web-medium").disabled=!state.deliveryEnabled;
    $("web-country").disabled=!state.countryEnabled;
    $("web-satellite").disabled=!state.satelliteEnabled;
    $("web-scan-start").disabled=!state.scanEnabled;
    $("web-scan-cancel").disabled=!state.cancelEnabled;
    $("web-stop").disabled=!state.stopEnabled;
    $("web-refresh").disabled=!state.refreshEnabled;
    $("web-caption-set").disabled=!state.captionEnabled;
    show("web-scan-backend",state.backendText);
    show("web-scan-context",state.showSatellite
      ? "Satellite DVB-S/S2 scans the chosen orbital position using a Linux/Pi satellite tuner and LNB. A DVB-T2 USB stick cannot receive dish signals."
      : state.deliveryLabel+" uses the selected country's frequency plan on a real native DVB frontend.");
    show("web-scan-state",state.statusText);
    show("web-signal",state.signalText);
    show("web-scan-limitation",state.explanation);
    $("web-scan-panel").setAttribute("data-connected",String(state.connected));
    $("web-scan-panel").setAttribute("data-scanning",String(scanning));
  }
  function connectionChanged(){
    const current=connected();
    if(current!==prevConnected){
      prevConnected=current;
      profileSyncNeeded=true;
      if(!current)resetDisconnected();
      paint();
      if(current)refreshAll();
    }
  }
  async function command(action,params={}){
    if(!connected())throw Error("Connect or pair with native TV Center first. WebUSB diagnostics are not a DVB tuner.");
    return connector().command(action,params);
  }
  function drawChannels(){
    const f=$("web-filter").value;
    const selected=channels.filter(c=>f==="all"||(f==="included"&&c.included)||
      (f==="favorite"&&c.favorite)||(f==="new"&&c.new)||f===c.kind);
    const list=$("web-channel-list");list.replaceChildren();
    if(!selected.length){
      list.append(make("p",channels.length?"No channels match this filter.":"No scanned channels found."));
      return;
    }
    for(const ch of selected){
      const item=make("div","","web-channel-item");
      item.append(make("div",(ch.favorite?"★ ":"")+ch.name+" · "+
        (ch.kind==="radio"?"Radio":"TV")+
        (ch.encrypted?" · encrypted":"")+(ch.new?" · NEW":"")));
      const actions=make("div","","actions");
      for(const [title,operation] of [
        ["▶ Watch","play"],[ch.favorite?"★ Unfavorite":"☆ Favorite","favorite"],
        [ch.included?"− Remove":"+ Include","included"],["↑","up"],["↓","down"]
      ]){
        const button=make("button",title,"secondary");
        button.disabled=!connected()||(operation==="play"&&!ch.included);
        button.onclick=async()=>{
          button.disabled=true;
          try{
            if(operation==="play"){
              if(!ch.included)throw Error("Include this channel before tuning.");
              const answer=await command("play",{key:ch.key});
              show("web-channel-msg","Tune requested: "+(answer.channel||ch.name)+". Waiting for real RF lock.");
              playing=true;paint();
            }else{
              await command("channel_update",{key:ch.key,operation});
              await refreshChannels(true);
              show("web-channel-msg","Saved "+operation+" for "+ch.name);
            }
          }catch(err){show("web-channel-msg",err.message);}
          finally{button.disabled=!connected()||(operation==="play"&&!ch.included);}
        };
        actions.append(button);
      }
      item.append(actions);list.append(item);
    }
  }
  async function refreshChannels(forceProfileSync=false){
    if(!connected()||channelBusy)return;
    channelBusy=true;
    try{
      const data=await connector().get("/api/channels");
      if(!connected())return;
      channels=Array.isArray(data.channels)?data.channels:[];
      show("web-channel-origin",(data.profile||"Native profile")+" · "+
        channels.length+" genuinely scanned services");
      if((forceProfileSync||profileSyncNeeded)&&!profileDirty){
        if(data.medium!=="s" && ["DE","TR"].includes(data.country))
          $("web-country").value=data.country;
        if(["t","c","s"].includes(data.medium))$("web-medium").value=data.medium;
        if(typeof data.satellite==="string")$("web-satellite").value=data.satellite;
        profileSyncNeeded=false;
      }
      drawChannels();paint();
    }catch(err){show("web-channel-msg","Receiver channel lookup: "+err.message);}
    finally{channelBusy=false;}
  }
  async function refreshStatus(){
    if(!connected())return;
    try{
      const data=await connector().get("/api/status");
      if(!connected())return;
      playing=data.source==="live_native_dvb";
      if(data.receiver){
        frontendAvailable=Boolean(data.receiver.frontend_present&&data.receiver.dvr_present);
        show("web-channel-origin",frontendAvailable
          ? "Local TV connected · DVB frontend "+(data.receiver.adapter??0)+" detected"
          : "Local TV connected · DVB hardware missing. Check USB/driver and tuner adapter.");
      }
      paint();
    }catch(err){
      if(connected())show("web-channel-msg","TV status unavailable: "+err.message);
    }
  }
  async function refreshScan(){
    if(!connected())return;
    try{
      const data=await connector().get("/api/scan");
      if(!connected())return;
      scanning=data.running===true;
      signal=typeof data.signal==="string"?data.signal:"";
      scanMessage=typeof data.status==="string"?data.status:"";
      const log=$("web-scan-log");log.replaceChildren();
      for(const event of (Array.isArray(data.events)?data.events:[]).slice(-45)){
        log.append(make("div","["+(event.stage||"·")+"] "+
          (event.channel||event.text||event.kind||"")));
      }
      paint();
    }catch(err){
      if(connected())show("web-scan-state","Native scan monitor unavailable: "+err.message);
    }
  }
  async function refreshModels(){
    if(!connected())return;
    try{
      const data=await connector().get("/api/models");
      if(!connected())return;
      show("web-model-info","Native ASR: "+(data.asr_enabled?"ON":"OFF")+
        " · Translation: "+(data.translation_enabled?"ON":"OFF")+
        " · Engine: "+(data.backend||"not reported")+
        " · Models: "+(data.models||[]).map(m=>m.name+(m.installed?" (installed)":" (not installed)")).join(", ")+
        ". Manage native model files in desktop Settings.");
    }catch(err){show("web-model-info","Native model status unavailable: "+err.message);}
  }
  async function refreshAll(){
    if(!connected())return;
    await Promise.all([refreshChannels(),refreshStatus(),refreshScan(),refreshModels()]);
  }
  for(const name of ["web-medium","web-country","web-satellite"]){
    $(name).addEventListener("change",()=>{profileDirty=true;paint();});
  }
  $("web-filter").addEventListener("change",drawChannels);
  $("web-refresh").onclick=async()=>{
    if(!connected())return;
    profileDirty=false;profileSyncNeeded=true;
    await refreshAll();
  };
  $("web-scan-start").onclick=async()=>{
    const state=scanControls({connected:connected(),medium:$("web-medium").value,
                              scanning,playing,pending});
    if(!state.scanEnabled){paint();return;}
    const params=scanRequest({country:$("web-country").value,
      medium:$("web-medium").value,satellite:$("web-satellite").value});
    const title=scanTitle(params);
    if(!confirm("Start a REAL full scan for "+title+"?\n\n"+
      "The native receiver must be connected and idle. Its frontend will be occupied; existing channel favorites are preserved."))return;
    pending=true;paint();
    try{
      const answer=await command("scan_start",params);
      if(answer?.scan_requested){
        scanning=true;
        profileDirty=false;profileSyncNeeded=true;
        scanMessage="Scan requested: "+title;
        show("web-channel-msg","The native tuner is scanning "+title+".");
      }
      paint();
      await refreshScan();
    }catch(err){scanMessage="Cannot start scan: "+err.message;paint();}
    finally{pending=false;paint();}
  };
  $("web-scan-cancel").onclick=async()=>{
    if(!connected()||!scanning||pending)return;
    pending=true;paint();
    try{
      await command("scan_cancel");
      scanMessage="Cancellation requested; waiting for native scanner to stop.";
    }catch(err){scanMessage="Cancel failed: "+err.message;}
    finally{pending=false;paint();}
  };
  $("web-stop").onclick=async()=>{
    if(!connected()||!playing||pending)return;
    pending=true;paint();
    try{
      await command("stop");
      playing=false;
      show("web-channel-msg","Stop requested; physical DVB tuner released.");
    }catch(err){show("web-channel-msg","Stop failed: "+err.message);}
    finally{pending=false;paint();}
  };
  $("web-caption-set").onclick=async()=>{
    if(!connected()||pending)return;
    pending=true;paint();
    try{
      const answer=await command("set_captions",{mode:$("web-caption-mode").value});
      show("web-model-info","Native caption mode: "+answer.actual_mode);
    }catch(err){show("web-model-info","Cannot change native subtitles: "+err.message);}
    finally{pending=false;paint();}
  };

  // Connection events originate from both the token bridge and PIN-paired LAN.
  document.addEventListener("tihulu-tv-connected",()=>{
    prevConnected=false;connectionChanged();
  });
  document.addEventListener("tihulu-tv-disconnected",()=>{
    prevConnected=true;connectionChanged();
  });
  setInterval(()=>{connectionChanged();if(connected()){refreshStatus();refreshScan();}},3000);
  setInterval(()=>{if(connected()){refreshChannels();refreshModels();}},9000);
  paint();
  connectionChanged();
})();
