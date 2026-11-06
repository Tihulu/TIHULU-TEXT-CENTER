/* TIHULU TEXT CENTER — no external libraries, no background timers fetching data. */
"use strict";

const state = {
  managedDabOwned:false, managedDabPollTimer:null,
  clientId:(window.crypto?.randomUUID?.()||
    ("client-"+Date.now()+"-"+Math.random().toString(36).slice(2))),
  tvActive:false, tvPollTimer:null, tvSession:null, liveActive:false, livePollTimer:null, liveSession:null, audioActive:false, audioPollTimer:null, csrf:"", page:100, subpage:0, source:"", entries:[], pages:[], receivers:null, rdsActive:false, rdsPollTimer:null, scanActive:false, scanPollTimer:null, selectedSurveyBand:"fm" };
const $ = (id) => document.getElementById(id);

function el(tag, cls, text) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}
function append(parent, ...children) { children.forEach((n) => parent.appendChild(n)); return parent; }
function notice(msg) { const n=$("notification"); n.textContent=msg; n.hidden=false; }
function clearNotice(){ $("notification").hidden=true; }
function connectionState(connected){
  const badge=document.querySelector(".indicator");
  if (badge){
    badge.textContent=connected ? "● LOCAL" : "● DISCONNECTED";
    badge.setAttribute("aria-label", connected ? "Local API reachable on last request" : "Local API disconnected");
  }
  const rail=document.querySelector(".rail-heading .lime");
  if (rail) rail.textContent=connected ? "● LAST REQUEST OK" : "● OFFLINE";
}
async function api(path, method, payload){
  const options = {method:method || "GET", headers:{"Accept":"application/json"}};
  if(method === "POST") {
    options.headers["Content-Type"]="application/json";
    options.headers["X-Tihulu-CSRF"]=state.csrf;
    options.body=JSON.stringify(payload);
  }
  let response;
  try { response=await fetch(path,options); }
  catch (cause) {
    connectionState(false);
    throw new Error("Cannot reach the local Text Center server. Start it with 'python3 -m textcenter serve', then reload this tab.");
  }
  connectionState(true);
  let data;
  try { data=await response.json(); }
  catch (_) { throw new Error("The local server returned an unreadable response (HTTP "+response.status+"). Try reloading the page."); }
  if(!response.ok) {
    const message=data.error || "Request failed (HTTP "+response.status+")";
    if(response.status===403 && method==="POST") throw new Error(message+" Reload the browser tab after restarting the server.");
    throw new Error(message);
  }
  return data;
}
function timeLabel(value) {
  if (!value) return "No timestamp";
  const date=new Date(value);
  return Number.isNaN(date.getTime()) ? String(value).slice(0,55) : date.toLocaleString();
}
function section(kicker,title,count){
  $("section-kicker").textContent=kicker; $("section-title").textContent=title;
  $("section-count").textContent=count || "";
  $("content").replaceChildren();
}
function card(title, description, meta) {
  const n=el("article","item-card");
  if(meta) n.append(el("div","item-meta",meta));
  append(n,el("h3","",title),el("p","",description));
  return n;
}
function button(text, cb, cls) {
  const b=el("button",cls || "small-btn",text); b.type="button";b.addEventListener("click",cb);return b;
}
function empty(title,body) {
  const n=el("article","notice-card");
  append(n,el("h3","",title),el("p","",body));$("content").append(n);
}
function headingMeta(data) {
  $("view-title").textContent="PAGE "+String(data.page).padStart(3,"0")+" — "+data.title;
  $("view-source").textContent=data.kind==="broadcast" ? data.medium.toUpperCase()+" / IMPORTED RF" : "LOCAL / OFFLINE";
  $("view-stamp").textContent=data.received_at ? timeLabel(data.received_at) : "";
  $("teletext-page").textContent="P"+String(data.page).padStart(3,"0")+" / "+String(data.subpage||0).padStart(2,"0");
  $("teletext-kicker").textContent=data.kind==="broadcast" ? data.station+" • "+data.language+" • "+data.frequency_hz+" Hz" : "LOCAL INFORMATION SYSTEM";
  $("teletext-title").textContent=data.title;
  $("teletext-body").textContent=data.body;
  const integrity=document.querySelector(".teletext-bottom span:first-child");
  if (integrity) integrity.textContent=data.kind==="broadcast"
      ? "● DECODER IMPORT / AUTHORITY UNVERIFIED"
      : "● LOCAL INDEX / NOT RF RECEPTION";
}
async function refreshCounts(){
  const d=await api("/api/bootstrap");
  state.csrf=d.csrf;
  [["articles","stat-articles"],["pages","stat-pages"],["events","stat-events"],["bulletins","stat-posts"]].forEach(([key,id])=>{$(id).textContent=d.counts[key]});
}
function receiverSummary(data){
  if(!data) return "Receiver status not checked";
  if(data.rtl_usb_count>0) {
    const first=data.rtl_usb_devices[0];
    return (first && first.product || "RTL2832U-compatible SDR")+" · USB detected";
  }
  if(data.status==="sysfs_unavailable") return "USB inventory unavailable on this OS";
  return "No RTL2832U USB receiver detected";
}
function statusLine(id,text,ready){
  const line=$(id);
  if(!line) return;
  const dot=el("span","status-dot "+(ready?"green":"muted"));
  line.replaceChildren(dot, document.createTextNode(" "+text));
}
function renderReceiverStatus(data){
  statusLine("rtl-status",receiverSummary(data),data.rtl_usb_count>0);
  statusLine("dvb-status",data.dvb_frontends.length
    ? "DVB frontend detected ("+data.dvb_frontends.length+")"
    : "No DVB frontend detected",data.dvb_frontends.length>0);
  statusLine("decoder-status",data.rds_capture_active
    ? "FM RDS capture running · "+data.rds_groups_decoded+" groups decoded"
    : data.receiver_conflicts?.length
      ? "SDR may be busy: "+[...new Set(data.receiver_conflicts.map(c=>c.process))].join(", ")
      : data.rds_pipeline_available ? "RDS tools installed · decoder inactive"
      : "RF text decoder inactive",Boolean(data.rds_capture_active));
  if($("receiver-check-note")){
    $("receiver-check-note").textContent="Checked "+timeLabel(data.checked_at)+" · Passive inspection, no tuning";
  }
}
async function refreshReceiverStatus(){
  try{
    const data=await api("/api/receivers");
    state.receivers=data;
    renderReceiverStatus(data);
    return data;
  }catch(err){
    state.receivers=null;
    statusLine("rtl-status","USB status unavailable · check local server",false);
    statusLine("dvb-status","DVB status unavailable",false);
    statusLine("decoder-status","Decoder status unknown",false);
    throw err;
  }
}
function receiverCard(data){
  const n=el("article","item-card");
  n.append(el("div","item-meta","PASSIVE HARDWARE INVENTORY / NOT LIVE RADIO"));
  n.append(el("h3","","Receiver & decoder readiness"));
  n.append(el("p","",receiverSummary(data)));
  n.append(el("p","full-body","RTL2832U USB candidates: "+data.rtl_usb_count+
    " · DVB frontend paths: "+data.dvb_frontends.length+
    " · Decoding active: NO · RF signal verified: NO"));
  if(data.rtl_usb_devices.length){
    data.rtl_usb_devices.forEach(d=>n.append(el("p","full-body",d.product+" / USB "+d.usb_id+" / "+d.usb_path)));
  }
  n.append(el("p","full-body","Executables: "+Object.entries(data.decoders).map(([k,v])=>k+" "+(v?"installed":"missing")).join(" · ")));
  if(data.receiver_conflicts?.length){
    const names=[...new Set(data.receiver_conflicts.map(c=>c.process))].join(", ");
    n.append(el("p","full-body","SDR CONFLICT: "+names+
      ". An existing flight tracker or radio application may own the same receiver. "+
      "Tihulu will not stop or retune it automatically."));
  }
  const actions=el("div","card-actions");
  actions.append(button("START FM RADIO",()=>openPage(410,"",0),"action primary"));
  actions.append(button("STOP ALL TEXT CENTER RF",async()=>{
    const response=await api("/api/receiver/stop-all","POST",{});
    state.managedDabOwned=false;
    if(state.managedDabPollTimer){
      clearTimeout(state.managedDabPollTimer);state.managedDabPollTimer=null;
    }
    state.liveActive=false;state.tvActive=false;
    state.audioActive=false;state.scanActive=false;state.rdsActive=false;
    syncLiveMediaDock();
    notice("Text Center's own radio, TV, FM/RDS, scans and managed DAB "+
      "have been requested to stop. External readsb and welle-cli were NOT touched. "+
      Object.entries(response.receivers).filter(([,v])=>v==="stop_failed")
        .map(([k])=>k).join(", "));
    await refreshReceiverStatus();
  },"action ghost"));
  actions.append(button("REFRESH DEVICE STATUS",async()=>{
    try{
      await refreshReceiverStatus();
      await showRadioData();
      notice("Passive USB inventory refreshed. No radio tuning or decoder started.");
    }catch(e){notice(e.message)}
  }));
  n.append(actions);
  n.append(el("p","full-body","USB detection is not active reception. To display actual FM/DAB text, a compatible decoder must supply real source-attributed data. No tuner was opened."));
  return n;
}
function setActivePage(number){
  document.querySelectorAll("[data-page]").forEach((n)=>n.classList.toggle("active",n.classList.contains("nav-item") && Number(n.dataset.page)===number));
}
async function refreshSourceChoices(){
  state.pages=await api("/api/pages");
  const select=$("source-select"), selected=select.value;
  select.replaceChildren(el("option","","Local index"));
  select.firstElementChild.value="";
  const sources=[...new Map(state.pages.map((p)=>[p.source_id,p.station+" / "+p.source_id])).entries()];
  sources.forEach(([id,label])=>{const o=el("option","",label);o.value=id;select.append(o)});
  select.value=sources.some(([id])=>id===selected)?selected:"";
}
async function openPage(number,source,subpage){
  if(state.page===400 && Number(number)!==400 && state.audioActive){
    state.audioActive=false;
    if(state.audioPollTimer){clearTimeout(state.audioPollTimer);state.audioPollTimer=null;}
    api("/api/audio/stop","POST",{}).catch(()=>{});
  }
  if(state.page===400 && Number(number)!==400 && state.scanActive){
    state.scanActive=false;
    if(state.scanPollTimer){clearTimeout(state.scanPollTimer);state.scanPollTimer=null;}
    api("/api/scans/stop","POST",{}).catch(error=>notice("Survey stop request failed: "+error.message));
  }
  if(state.page===400 && Number(number)!==400 && state.rdsActive){
    state.rdsActive=false;
    if(state.rdsPollTimer){clearTimeout(state.rdsPollTimer);state.rdsPollTimer=null;}
    api("/api/rds/stop","POST",{}).catch((error)=>notice("Could not stop capture: "+error.message));
  }
  clearNotice();
  if(!Number.isInteger(Number(number)) || Number(number)<100 || Number(number)>899) return notice("Select a page from 100 to 899.");
  state.page=Number(number);state.source=source||"";state.subpage=Number(subpage)||0;
  $("page-number").value=state.page;$("subpage-number").value=state.subpage;$("source-select").value=state.source;
  const query=new URLSearchParams({number:String(state.page),subpage:String(state.subpage)});
  if(state.source)query.set("source_id",state.source);
  try {
    const data=await api("/api/page?"+query.toString());
    headingMeta(data); setActivePage(state.page);
    if(data.kind==="broadcast") return showBroadcast(data);
    if(state.page===100) return showIndex();
    if(state.page===200) return showArticles();
    if(state.page===300) return showWeather();
    if(state.page===400) return showRadioData();
    if(state.page===410) return showLiveRadioPage();
    if(state.page===420) return showLiveTVPage();
    if(state.page===450) return showTranslatorPage();
    if(state.page===500) return showEmergency();
    if(state.page===600) return showBulletins();
    if(state.page===700) return showLibrary();
    if(state.page===800) return showDirectory();
    if(state.page===860) return showCapabilities();
    return showAbout();
  } catch(err) {
    const message=String(err && err.message || err);
    const disconnected=message.startsWith("Cannot reach the local Text Center server");
    const missing=message.includes("No imported page") || message.includes("Page not present in local index");
    section(disconnected ? "CONNECTION LOST" : missing ? "NOT FOUND" : "LOAD ERROR",
            disconnected ? "Local service disconnected" : missing ? "No page imported" : "Unable to load page content");
    empty(disconnected ? "Cannot contact the running server" : missing ? "No received data for this page" : "Request unsuccessful",
          message + (disconnected ? " Previously displayed data may be out of date." : ""));
    $("content").append(button("RETRY PAGE",()=>openPage(state.page,state.source,state.subpage)));
    notice(message);
  }
}
function showBroadcast(data){
  section("RECEIVER IMPORT","Decoded page",data.source_id+" / subpage "+data.subpage);
  const n=card(data.title,data.body,data.station+" • "+data.language+" • "+timeLabel(data.received_at));
  n.append(el("div","inline-tag","DECODER-IMPORTED · AUTHORITY NOT VERIFIED"));
  n.append(el("p","full-body","Provenance: "+data.provenance));
  n.append(el("p","full-body","Frequency: "+data.frequency_hz+" Hz"));
  const actions=el("div","card-actions");
  actions.append(button("← Previous",()=>openPage(Math.max(100,data.page-1),data.source_id,0)));
  actions.append(button("Next →",()=>openPage(Math.min(899,data.page+1),data.source_id,0)));
  n.append(actions);$("content").append(n);
}
function discoveryLine(label,detail,tone){
  const line=el("div","discover-line");
  const key=el("span","discover-key",label);
  const value=el("strong","discover-value "+(tone||""),detail);
  line.append(key,value);
  return line;
}
function renderHomeDiscovery(report){
  const container=$("home-discovery-results");
  if(!container||state.page!==100)return;
  container.replaceChildren();
  const inv=report.receiver||{}, dec=inv.decoders||{},counts=report.archive_counts||{};
  const sdr=Number(inv.rtl_usb_count||0),dvb=(inv.dvb_frontends||[]).length;
  const busy=(inv.receiver_conflicts||[]);
  const conflicts=[...new Set(busy.map(x=>x.process))];
  container.append(
    discoveryLine("RTL-SDR",sdr ? (inv.rtl_usb_devices?.[0]?.product||"RTL2832U device")+" detected" : "Not detected",sdr?"discover-good":""),
    discoveryLine("DVB frontend",dvb ? String(dvb)+" device path(s) detected" : "No frontend detected",dvb?"discover-good":""),
    discoveryLine("Receiver sharing",busy.length?"Possibly busy: "+conflicts.join(", "):"No known conflict · ownership unverified",busy.length?"discover-warn":""),
    discoveryLine("FM scan",dec.rtl_power?"rtl_power installed · explicit approval required":"rtl_power missing",dec.rtl_power?"discover-good":"discover-warn"),
    discoveryLine("RadioText decoder",dec.rtl_fm&&dec.redsea?"rtl_fm + redsea installed":"Missing: "+[!dec.rtl_fm?"rtl_fm":null,!dec.redsea?"redsea":null].filter(Boolean).join(", "),dec.rtl_fm&&dec.redsea?"discover-good":"discover-warn"),
    discoveryLine("DAB text",dec["welle-cli"]?"DAB tool detected · integration pending":"DAB text decoder not connected",""),
    discoveryLine("Text archive",String((counts.articles||0))+" articles · "+String((counts.events||0)+(counts.pages||0))+" RF records · "+String(counts.bulletins||0)+" notes","")
  );
  container.append(el("p","discover-disclaimer",
    "Passive detection only — no tuning, station scan, internet requests or live broadcast verification. "+
    "A visible USB device is not a free tuner."));
  const missing=["redsea","rtl_power"].filter(k=>!dec[k]);
  if(missing.length){
    container.append(el("p","discover-guidance",
      "Optional tools missing: "+missing.join(", ")+
      ". Open Radio Data (400) for detailed readiness. Nothing will be installed automatically."));
  }
}
async function addHomeDiscovery(){
  const panel=el("article","home-discovery");
  panel.append(el("div","item-meta","LIVE LOCAL CAPABILITY CHECK · NOT RF RECEPTION"));
  const header=el("div","home-discovery-head");
  header.append(el("h3","","Your connected information sources"));
  const controls=el("div","card-actions");
  const refresh=button("CHECK AGAIN",async()=>{
    refresh.disabled=true;
    try{
      const result=await api("/api/discovery/passive");
      renderHomeDiscovery(result);
      await refreshReceiverStatus();
      notice("Local hardware, services and cache checked. No RF tuning performed.");
    }catch(err){notice("Discovery failed: "+err.message)}
    finally{refresh.disabled=false}
  });
  controls.append(refresh);
  header.append(controls);
  panel.append(header);
  const details=el("div","home-discovery-results");details.id="home-discovery-results";
  details.append(el("p","","Inspecting local devices and installed decoders…"));
  panel.append(details);
  const actionRow=el("div","home-shortcuts");
  actionRow.append(button("OPEN RADIO & FM SCAN",()=>openPage(400,"",0),"action primary"));
  actionRow.append(button("ADD NEWS / BLOG FEEDS",()=>openPage(200,"",0)));
  actionRow.append(button("ALL 31 PROTOCOLS",()=>openPage(860,"",0)));
  panel.append(actionRow);
  $("content").append(panel);
  try{
    const result=await api("/api/discovery/passive");
    renderHomeDiscovery(result);
  }catch(error){
    if(state.page===100)details.replaceChildren(el("p","",
      "Local discovery unavailable: "+error.message));
  }
}
async function showIndex(){
  section("START HERE","Your connected sources","Passive discovery at startup");
  await addHomeDiscovery();
  if(state.page!==100)return;
  const index=await api("/api/index");
  index.filter((x)=>x.page!==100).forEach((entry)=>{
    const n=el("button","tile");
    append(n,el("span","tile-page","P"+entry.page),el("h3","",entry.title),el("p","",entry.description));
    const footer=el("div","tile-footer");append(footer,el("span","","OPEN CHANNEL"),el("span","","↗"));n.append(footer);
    n.addEventListener("click",()=>openPage(entry.page,"",0));
    $("content").append(n);
  });
}
async function showArticles(query){
  section("INTERNET / CACHED","News & independent feeds","Manual sync only");
  const form=el("article","form-card");
  form.append(el("h3","","Add a trusted RSS / Atom source"));
  const add=el("form","form-grid");
  const name=field("Feed name","text","Name this source",120);
  const url=field("HTTPS feed URL","url","https://example.org/feed.xml",1200);
  append(add,name.wrap,url.wrap);
  const save=el("button","action primary","ADD FEED");save.type="submit";add.append(save);
  add.addEventListener("submit",async(ev)=>{
    ev.preventDefault();
    try {await api("/api/feeds/add","POST",{title:name.input.value,url:url.input.value});notice("Feed registered. Choose Refresh to retrieve articles.");await openPage(200,"",0)}
    catch(err){notice(err.message)}
  });
  form.append(add);$("content").append(form);
  const feeds=await api("/api/feeds");
  if(!feeds.length) empty("No feeds registered","Add a real HTTPS RSS/Atom address above. The app never polls feeds on its own.");
  feeds.forEach((f)=>{
    const n=card(f.title,f.url,"FEED · "+(f.last_fetched?"Updated "+timeLabel(f.last_fetched):"Not fetched"));
    const actions=el("div","card-actions");
    actions.append(button("↻ REFRESH NOW",async()=>{
      try {const r=await api("/api/feeds/refresh","POST",{id:f.id});notice("Imported "+r.imported+" items. No background sync enabled.");await refreshCounts();await showArticles()}
      catch(err){notice(err.message)}
    }));
    n.append(actions);$("content").append(n);
  });
  const search=el("article","form-card");
  const f=el("form","form-grid");
  const input=field("Search saved articles","search","Find a keyword",100);
  input.wrap.classList.add("full");f.append(input.wrap);
  const s=el("button","small-btn","SEARCH ARCHIVE");s.type="submit";f.append(s);
  f.addEventListener("submit",(ev)=>{ev.preventDefault();showArticles(input.input.value)});
  search.append(f);$("content").append(search);
  const articles=await api("/api/articles"+(query?"?q="+encodeURIComponent(query):""));
  articles.forEach((a)=>{
    const n=card(a.title,a.body.slice(0,350),a.source_name+" · "+(a.published_at||"No publication date")+" · CACHED");
    const actions=el("div","card-actions");
    if(a.body.length>350) actions.append(button("READ FULL TEXT",()=>{n.querySelector("p").textContent=a.body}));
    if(a.url){const link=el("a","","OPEN ORIGINAL ↗");link.href=a.url;link.target="_blank";link.rel="noopener noreferrer";actions.append(link)}
    actions.append(button("☆ SAVE",async()=>{try{await saveBookmark(a.title,"article",a.id)}catch(err){notice(err.message)}}));
    n.append(actions);$("content").append(n);
  });
  if(!articles.length) empty("No cached articles","Refresh an added feed manually to create a searchable offline archive.");
  $("section-count").textContent=articles.length+" cached items shown";
}
function field(label,type,placeholder,maxLength) {
  const wrap=el("div","field"), lbl=el("label","",label);
  const input=el("input");input.type=type;input.placeholder=placeholder;input.maxLength=maxLength;input.required=true;
  append(wrap,lbl,input); return {wrap,input};
}
async function showWeather() {
  section("RADIO / WEATHER","Received weather text","No invented forecasts");
  const events=await api("/api/events");const found=events.filter((e)=>["navtex","hf_weather"].includes(e.medium));
  found.forEach((e)=>append($("content"),card(e.title,e.body,e.medium.toUpperCase()+" · "+e.station+" · "+timeLabel(e.received_at))));
  if(!found.length) empty("No weather broadcast imported","NAVTEX and HF weatherfax require a compatible antenna, receiver and decoder. Local conditions are not inferred from unverified presets.");
}
function setRdsText(data){
  const box=$("rds-live"),status=$("rds-progress");
  if(status){
    statusLine("decoder-status",data.active
      ? "FM RDS capture running · "+data.received_groups+" groups decoded"
      : "RF text decoder inactive",Boolean(data.active));
    let line="Status: "+data.status.toUpperCase();
    if(data.frequency_hz)line+=" · "+(data.frequency_hz/1e6).toFixed(3)+" MHz";
    line+=" · "+data.received_groups+" decoded groups · "+data.saved_items+" saved text items";
    if(data.rds2_images)line+=" · "+data.saved_images+" RDS2 images received";
    if(data.error)line+=" · "+data.error;
    status.textContent=line;
  }
  if(box){
    box.replaceChildren();
    if(!data.recent.length){
      box.append(el("p","",data.active
        ?"Listening for actual RDS groups. No signal or station is assumed."
        :"No recent decoded text in this session."));
    }else{
      data.recent.slice().reverse().forEach(event=>{
        const row=el("div","rds-row");
        append(row,el("div","item-meta",event.station+" · "+timeLabel(event.received_at)),
                   el("strong","",event.title),el("p","",event.text));
        box.append(row);
      });
    }
  }
  const start=$("rds-start"),stop=$("rds-stop"),confirm=$("rds-confirm");
  if(start)start.disabled=Boolean(data.active) || !data.capability?.ready || !confirm?.checked;
  if(stop)stop.disabled=!data.active;
}
async function pollRds(){
  if(state.page!==400)return;
  try{
    const status=await api("/api/rds/status");
    state.rdsActive=status.active;
    setRdsText(status);
    if(status.active && state.page===400){
      state.rdsPollTimer=setTimeout(pollRds,1500);
    }else if(state.page===400 && (status.status==="completed" || status.status==="cancelled" || status.status==="error")){
      // Reload source-attributed stored text after an actual capture ends.
      if(!$("rds-finished-"+status.session)){
        const marker=el("span"); marker.id="rds-finished-"+status.session;
        const box=$("rds-live");if(box)box.append(marker);
        await showRadioData();
      }
    }
  }catch(error){
    state.rdsActive=false;
    notice("FM capture status unavailable: "+error.message);
  }
}
async function addRdsControl(){
  const status=await api("/api/rds/status");
  const outer=el("article","item-card");outer.id="rds-control";
  outer.append(el("div","item-meta","REAL FM RADIOTEXT / EXPLICIT CAPTURE ONLY"));
  outer.append(el("h3","","Tune & decode FM RDS"));
  const help=el("p","",
    "Uses the single RTL-SDR receiver via rtl_fm → redsea. No scanning, no transmission. "+
    "A protected recording or other SDR app may already own the device; stop them yourself first.");
  outer.append(help);
  const reason=el("p","full-body",status.capability?.reason||"Receiver readiness unknown");
  outer.append(reason);
  if(status.capability?.conflicts?.length){
    const names=[...new Set(status.capability.conflicts.map(c=>c.process))].join(", ");
    outer.append(el("p","full-body","BLOCKED: "+names+" is running. "+
      "Do not interrupt an active ADS-B/Radio recording. Use another USB SDR or stop it manually."));
  }
  const form=el("form","rds-form");
  const frequency=field("FM frequency (MHz)","number","98.600",10);
  frequency.input.id="rds-frequency";frequency.input.min="87.5";frequency.input.max="108.0";
  frequency.input.step="0.001";frequency.input.value="98.6";
  const duration=el("div","field");const durationLabel=el("label","","Capture duration");
  const seconds=el("select");seconds.id="rds-duration";
  [15,30,45,60,90].forEach(n=>{const option=el("option","",n+" seconds");option.value=String(n);if(n===30)option.selected=true;seconds.append(option)});
  append(duration,durationLabel,seconds);
  const consent=el("label","rds-consent"),check=el("input");check.type="checkbox";check.id="rds-confirm";
  consent.append(check,document.createTextNode(" I confirm that my RTL-SDR is not used by Gqrx, welle.io, readsb, or another recording."));
  const start=el("button","action primary","START RDS CAPTURE");start.id="rds-start";start.type="submit";
  const stop=el("button","action ghost","STOP CAPTURE");stop.id="rds-stop";stop.type="button";
  const imagesOption=el("label","scan-consent");
  const imageCheck=el("input");imageCheck.type="checkbox";imageCheck.id="rds-images";
  imagesOption.append(imageCheck,document.createTextNode(
    " Receive optional RDS2/RFT station logos via redsea --streams (requires redsea >=1.2; "+
    "3–4× decoder CPU load; only broadcasters transmitting RDS2 logos will supply images)."));
  const buttons=el("div","card-actions");buttons.append(start,stop);
  append(form,frequency.wrap,duration,consent,imagesOption,buttons);
  outer.append(form);
  const progress=el("p","full-body","No capture yet");progress.id="rds-progress";
  const live=el("div","rds-live");live.id="rds-live";
  append(outer,progress,live);
  check.addEventListener("change",()=>{start.disabled=!check.checked || state.rdsActive || !status.capability?.ready});
  form.addEventListener("submit",async(ev)=>{
    ev.preventDefault();
    if(!check.checked)return notice("Confirm that the SDR is free before starting.");
    start.disabled=true;
    try{
      const started=await api("/api/rds/start","POST",{
        frequency_mhz:Number(frequency.input.value),duration_seconds:Number(seconds.value),
        rds2_images:imageCheck.checked
      });
      state.rdsActive=true;notice("Receiver launched on your explicit request. Unverified until actual RDS JSON arrives.");
      setRdsText({...started,capability:status.capability});
      if(state.rdsPollTimer)clearTimeout(state.rdsPollTimer);
      state.rdsPollTimer=setTimeout(pollRds,500);
    }catch(error){notice(error.message);start.disabled=false;}
  });
  stop.addEventListener("click",async()=>{
    try{
      const stopped=await api("/api/rds/stop","POST",{});
      notice("Stop requested; waiting for decoder cleanup.");
      if(state.rdsPollTimer)clearTimeout(state.rdsPollTimer);
      state.rdsPollTimer=setTimeout(pollRds,300);
      setRdsText({...stopped,capability:status.capability});
    }catch(error){notice(error.message)}
  });
  $("content").append(outer);
  setRdsText(status);
  state.rdsActive=status.active;
  if(status.active){
    if(state.rdsPollTimer)clearTimeout(state.rdsPollTimer);
    state.rdsPollTimer=setTimeout(pollRds,1500);
  }
}
function showPassiveDiscovery(result){
  const list=$("discovery-details");
  if(!list)return;
  list.replaceChildren();
  const inv=result.receiver;
  const counts=result.archive_counts;
  list.append(el("p","full-body","USB RTL-SDR: "+inv.rtl_usb_count+
    " · DVB frontends: "+inv.dvb_frontends.length+
    " · Cached articles: "+counts.articles+
    " · Imported broadcast records: "+(counts.events+counts.pages)+
    " · Feature types tracked: "+result.features_total));
  const installed=Object.entries(inv.decoders).filter(([k,v])=>v).map(([k])=>k);
  const missing=Object.entries(inv.decoders).filter(([k,v])=>!v).map(([k])=>k);
  list.append(el("p","full-body","Installed tools: "+(installed.join(", ")||"none")));
  list.append(el("p","full-body","Missing optional tools: "+(missing.join(", ")||"none")));
  if(inv.receiver_conflicts?.length){
    list.append(el("p","full-body","ACTIVE RECEIVER CONFLICTS: "+
      [...new Set(inv.receiver_conflicts.map(x=>x.process))].join(", ")+
      ". No tuner will be opened or retuned while a conflict exists."));
  }else{
    list.append(el("p","full-body","No known receiver process conflict detected. "+
      "This does not guarantee exclusive hardware access."));
  }
  list.append(el("p","full-body","Passive discovery does not contact the internet or claim RF reception. "+
    "Additional protocols are listed under Protocols (860)."));
}
async function addAutoDiscovery(){
  const outer=el("article","item-card");outer.id="auto-discovery";
  outer.append(el("div","item-meta","STEP 1 / SAFE AUTOMATIC DISCOVERY / NO TUNING"));
  outer.append(el("h3","","Auto Discover connected sources"));
  outer.append(el("p","",
    "Detect available USB/DVB hardware, installed decoder tools, other receiver processes, "+
    "stored RF text, feed cache and supported protocol modules. This step never changes radio frequency."));
  const controls=el("div","card-actions");
  const discover=button("AUTO DISCOVER",async()=>{
    discover.disabled=true;
    try{
      const result=await api("/api/discovery/passive");
      showPassiveDiscovery(result);
      await refreshReceiverStatus();
      notice("Local sources inventoried. Live RF scans require separate permission.");
    }catch(error){notice(error.message)}
    finally{discover.disabled=false}
  });
  controls.append(discover);
  outer.append(controls);
  const details=el("div","scan-summary");details.id="discovery-details";
  outer.append(details);$("content").append(outer);
  try{showPassiveDiscovery(await api("/api/discovery/passive"))}
  catch(error){details.textContent="Passive discovery unavailable: "+error.message}
}
function displaySurvey(status){
  const label=$("fm-survey-progress"),results=$("fm-survey-results");
  if(label){
    label.textContent="Band: "+String(status.band||"fm").toUpperCase()+
      " · "+status.status.toUpperCase()+
      " · "+status.candidates.length+" unidentified energy peaks"+
      (status.error?" · "+status.error:"");
  }
  const start=$("fm-survey-start"),stop=$("fm-survey-stop");
  const selected=$("fm-survey-band");
  const selectedReady=selected&&selected.options[selected.selectedIndex]?.dataset.ready==="true";
  if(start)start.disabled=Boolean(status.active)||!selectedReady||!$("fm-survey-confirm")?.checked;
  if(stop)stop.disabled=!status.active;
  if(selected)selected.disabled=Boolean(status.active);
  if(!results)return;
  results.replaceChildren();
  if(!status.candidates.length){
    results.append(el("p","full-body",status.active
      ?"Measuring RF energy. No channel or programme is decoded by this survey."
      :status.note||"No signal candidates saved."));
    return;
  }
  results.append(el("p","full-body",
    "These are unidentified spectrum peaks, NOT decoded radio/TV stations, services, messages or official alerts."));
  status.candidates.forEach(candidate=>{
    const row=el("div","scan-row");
    row.append(el("strong","",candidate.frequency_mhz.toFixed(3)+" MHz"));
    row.append(el("span","",candidate.above_median_db.toFixed(1)+" dB above local median"));
    if(status.band==="fm"){
      row.append(button("TRY RDS",()=>{
        const input=$("rds-frequency");
        if(input){input.value=String(candidate.frequency_mhz);input.focus()}
        notice("Unidentified FM spectral peak; RDS decoding must verify the station.");
      }));
    }
    results.append(row);
  });
}
async function pollFMSurvey(){
  if(state.page!==400)return;
  try{
    const report=await api("/api/scans/status");
    state.scanActive=report.active;
    displaySurvey(report);
    if(report.active && state.page===400){
      state.scanPollTimer=setTimeout(pollFMSurvey,750);
    }else{
      await refreshReceiverStatus();
    }
  }catch(error){
    state.scanActive=false;
    notice("RF survey status unavailable: "+error.message);
  }
}
async function addFMSurveyControl(){
  const discovery=await api("/api/scans");
  const report=await api("/api/scans/status");
  const available=discovery.features.filter(f=>f.scan_type==="rf_spectrum");
  const bands=new Map();
  available.forEach(f=>{
    if(!bands.has(f.band))bands.set(f.band,{label:f.band_label,features:[],ready:f.can_survey_now,reason:f.reason});
    bands.get(f.band).features.push(f.title);
  });
  const outer=el("article","item-card");outer.id="fm-survey-control";
  outer.append(el("div","item-meta","STEP 2 / MANUAL RF SPECTRUM SURVEY / NO AUTOMATIC RETUNING"));
  outer.append(el("h3","","Scan each receivable RF band"));
  outer.append(el("p","",
    "Select FM, DAB, APRS or a low-frequency/HF service band. A one-shot rtl_power sweep "+
    "detects possible RF energy only. Actual programme text needs a compatible decoder. "+
    "No device is used until you explicitly approve the survey."));
  const selectGroup=el("div","field"),selectLabel=el("label","","RF band / technology");
  const selected=el("select");selected.id="fm-survey-band";
  bands.forEach((value,key)=>{
    const option=el("option","",value.label+" — "+value.features.join(", "));
    option.value=key;option.dataset.ready=String(value.ready);
    selected.append(option);
  });
  selected.value=bands.has(state.selectedSurveyBand)?state.selectedSurveyBand:"fm";
  if(report.active&&bands.has(report.band))selected.value=report.band;
  selectGroup.append(selectLabel,selected);outer.append(selectGroup);
  const reason=el("p","full-body","");outer.append(reason);
  const updateReason=()=>{
    const entry=bands.get(selected.value);
    state.selectedSurveyBand=selected.value;
    reason.textContent=entry?.reason||"No compatible survey profile found";
    const start=$("fm-survey-start");
    if(start) start.disabled=state.scanActive||!entry?.ready||!$("fm-survey-confirm")?.checked;
  };
  selected.addEventListener("change",updateReason);
  const consent=el("label","scan-consent");
  const cb=el("input");cb.type="checkbox";cb.id="fm-survey-confirm";
  consent.append(cb,document.createTextNode(
    " I understand that this explicitly opens and retunes the Nooelec SDR for a short spectrum scan. "+
    "Flight Radar/readsb, Gqrx, welle.io and protected recordings must not be using this device. "+
    "LF/HF reception also requires suitable Q-branch configuration and antenna."));
  outer.append(consent);
  const controls=el("div","card-actions");
  const start=button("SCAN SELECTED RF BAND",async()=>{
    start.disabled=true;
    try{
      const response=await api("/api/scans/start","POST",{band:selected.value});
      state.scanActive=response.active;
      notice("Measuring "+selected.value.toUpperCase()+" band; no services identified yet.");
      await refreshReceiverStatus();
      if(state.scanPollTimer)clearTimeout(state.scanPollTimer);
      state.scanPollTimer=setTimeout(pollFMSurvey,350);
    }catch(error){
      notice("Scan refused: "+error.message);
      updateReason();
    }
  },"action primary");
  start.id="fm-survey-start";start.disabled=true;
  const stop=button("STOP RF SCAN",async()=>{
    try{
      await api("/api/scans/stop","POST",{});
      if(state.scanPollTimer)clearTimeout(state.scanPollTimer);
      state.scanPollTimer=setTimeout(pollFMSurvey,300);
    }catch(error){notice(error.message)}
  },"action ghost");
  stop.id="fm-survey-stop";
  controls.append(start,stop);outer.append(controls);
  cb.addEventListener("change",updateReason);
  const label=el("p","full-body","No scan attempted");label.id="fm-survey-progress";outer.append(label);
  const data=el("div","scan-candidates");data.id="fm-survey-results";outer.append(data);
  $("content").append(outer);
  state.scanActive=report.active;
  updateReason();
  displaySurvey(report);
  if(report.active){
    if(state.scanPollTimer)clearTimeout(state.scanPollTimer);
    state.scanPollTimer=setTimeout(pollFMSurvey,750);
  }
}
function showAudioStatus(report){
  const status=$("fm-audio-status");
  if(status){
    let label="Capture: "+report.status.toUpperCase();
    if(report.recorded_seconds)label+=" · "+report.recorded_seconds+" sec recorded";
    if(report.error)label+=" · "+report.error;
    status.textContent=label;
  }
  const player=$("fm-audio-player");
  if(player&&report.clip_ready&&!report.active&&player.dataset.session!==report.session){
    player.dataset.session=report.session;
    player.src="/api/audio/clip.wav?session="+encodeURIComponent(report.session);
    player.hidden=false;
    player.load();
  }
  const start=$("fm-audio-start"),stop=$("fm-audio-stop");
  if(start)start.disabled=Boolean(report.active)||!$("fm-audio-confirm")?.checked||!report.capability?.ready;
  if(stop)stop.disabled=!report.active;
}
async function pollAudioPreview(){
  if(state.page!==400)return;
  try{
    const report=await api("/api/audio/status");
    state.audioActive=report.active;
    showAudioStatus(report);
    if(report.active&&state.page===400){
      state.audioPollTimer=setTimeout(pollAudioPreview,750);
    }else{
      await refreshReceiverStatus();
    }
  }catch(error){
    state.audioActive=false;
    notice("FM audio preview status failed: "+error.message);
  }
}
function renderLiveDockCaptions(items,kind){
  const container=$(kind==="tv"?"live-dock-tv-captions":"live-dock-radio-captions");
  if(!container)return;
  container.replaceChildren();
  if(kind==="radio")container.hidden=!state.liveActive;
  if(!items.length)return;
  const last=items[items.length-1];
  const original=el("p","dock-subtitle-original",
    "["+last.original_language.toUpperCase()+"] "+last.original_text);
  container.append(original);
  if(last.translated_text){
    container.append(el("p","dock-subtitle-translated",
      "["+last.translated_language.toUpperCase()+"] "+last.translated_text));
  }
}
function syncLiveMediaDock(){
  const dock=$("live-media-dock");if(!dock)return;
  dock.hidden=!(state.liveActive||state.tvActive);
  const a=$("persistent-radio-player"),v=$("persistent-tv-player");
  if(a)a.hidden=!state.liveActive;
  const tvFrame=$("persistent-tv-frame");
  if(tvFrame)tvFrame.hidden=!state.tvActive;
  const label=$("live-dock-title");
  if(label)label.textContent=(state.tvActive?"LIVE TV  ":"")+
    (state.liveActive?"LIVE FM RADIO  ":"")+
    "· user-started receive-only stream";
  const r=$("live-dock-stop-radio"),t=$("live-dock-stop-tv");
  if(r)r.hidden=!state.liveActive;
  if(t)t.hidden=!state.tvActive;
}
function bindMediaDock(){
  const radio=$("live-dock-stop-radio"),tv=$("live-dock-stop-tv");
  if(radio)radio.addEventListener("click",async()=>{
    try{
      const player=$("persistent-radio-player");
      player.pause();player.removeAttribute("src");player.dataset.session="";player.load();
      await api("/api/live/radio/stop","POST",{});
      state.liveActive=false;syncLiveMediaDock();
    }catch(e){notice(e.message)}
  });
  if(tv)tv.addEventListener("click",async()=>{
    try{
      const player=$("persistent-tv-player");
      player.pause();player.removeAttribute("src");player.dataset.session="";player.load();
      await api("/api/live/tv/stop","POST",{});
      state.tvActive=false;syncLiveMediaDock();
    }catch(e){notice(e.message)}
  });
}
function liveRadioCaptionPanel(captions,session,targetId="live-radio-captions"){
  const container=$(targetId);
  if(!container)return;
  container.replaceChildren();
  if(!captions.length){
    container.append(el("p","full-body",
      "No real speech segments decoded yet. A configured local speech model is required; "+
      "background noise and music may not produce any caption."));
    return;
  }
  for(const item of captions.slice(-12)){
    const card=el("article","live-caption-row");
    card.append(el("span","item-meta",
      "["+item.started_seconds.toFixed(0)+"–"+item.ended_seconds.toFixed(0)+"s] "+
      item.original_language.toUpperCase()+" · "+item.compute_backend+
      " · "+item.captured_at));
    card.append(el("p","caption-original",item.original_text));
    if(item.translated_text)card.append(el("p","caption-translated",
      item.translated_language.toUpperCase()+": "+item.translated_text));
    const actions=el("div","card-actions");
    if(!item.translated_text){
      actions.append(button("TRANSLATE THIS CAPTION",async()=>{
        const target=$(targetId==="live-tv-captions"?"live-tv-later-language":"live-later-language")?.value||"tr";
        try{
          const result=await api("/api/transcripts/translate","POST",{
            id:item.id,target_language:target,backend:"auto"});
          item.translated_text=result.translated_text;
          item.translated_language=result.translated_language;
          liveRadioCaptionPanel(captions,session,targetId);
          notice("Caption translated offline; original preserved.");
        }catch(err){notice("Translation unavailable: "+err.message)}
      }));
    }
    card.append(actions);
    container.append(card);
  }
}
async function pollLiveRadio(){
  if(![400,410].includes(state.page)&&!state.liveActive)return;
  try{
    const current=await api("/api/live/radio/status");
    state.liveActive=current.active;
    state.liveSession=current.session||state.liveSession;
    syncLiveMediaDock();
    const label=$("live-radio-status");
    if(label){
      label.textContent=current.status.toUpperCase()+
        " · "+(current.frequency_hz?current.frequency_hz/1e6+" MHz":"no tuned station")+
        " · recording: "+(current.recording?"ON":"OFF")+
        (current.speech?.enabled?
          " · ASR "+current.speech.selected_backend+" · "+
          current.speech.segments_completed+" segments":" · subtitles off")+
        (current.speech?.error?" · "+current.speech.error:"")+
        (current.error?" · "+current.error:"");
    }
    const start=$("live-radio-start"),stop=$("live-radio-stop");
    const permission=$("live-radio-consent");
    if(start)start.disabled=current.active||!permission?.checked||!current.capability?.ready;
    if(stop)stop.disabled=!current.active;
    if(state.liveSession){
      const data=await api("/api/transcripts?session="+encodeURIComponent(state.liveSession));
      liveRadioCaptionPanel(data,state.liveSession);
      renderLiveDockCaptions(data,"radio");
      const links=$("live-export-links");
      if(links){
        links.replaceChildren();
        for(const fmt of ["srt","vtt"]){
          for(const translated of [false,true]){
            const link=el("a","action ghost",
              "SAVE "+(translated?"TRANSLATED":"ORIGINAL")+" "+fmt.toUpperCase());
            link.href="/api/transcripts/export?session="+
              encodeURIComponent(state.liveSession)+"&format="+fmt+
              "&translated="+(translated?"1":"0");
            link.download="tihulu-"+state.liveSession.slice(0,8)+
              (translated?"-translated":"-original")+"."+fmt;
            links.append(link);
          }
        }
      }
    }
    if(current.active){
      state.livePollTimer=setTimeout(pollLiveRadio,1800);
    }else{
      await refreshReceiverStatus();
    }
  }catch(e){notice("Live receiver status unavailable: "+e.message);}
}
async function pollLiveTV(){
  if(![400,420].includes(state.page)&&!state.tvActive)return;
  try{
    const current=await api("/api/live/tv/status");
    state.tvActive=current.active;
    state.tvSession=current.session||state.tvSession;
    syncLiveMediaDock();
    const label=$("live-tv-status");
    if(label)label.textContent=current.status.toUpperCase()+
      " · "+(current.channel_name||"No TV channel selected")+
      " · recording "+(current.recording?"ON":"OFF")+
      (current.speech?.enabled?" · ASR "+current.speech.selected_backend+
        " · "+current.speech.segments_completed+" segments":" · subtitles off")+
      (current.speech?.error?" · "+current.speech.error:"")+
      (current.error?" · "+current.error:"");
    const start=$("live-tv-start"),stop=$("live-tv-stop");
    const approved=$("live-tv-consent");
    const configured=$("live-tv-channel");
    if(start)start.disabled=current.active||!approved?.checked||
      !configured?.value||!current.capability?.ready;
    if(stop)stop.disabled=!current.active;
    if(state.tvSession){
      const data=await api("/api/transcripts?session="+encodeURIComponent(state.tvSession));
      liveRadioCaptionPanel(data,state.tvSession,"live-tv-captions");
      renderLiveDockCaptions(data,"tv");
      const links=$("live-tv-export");
      if(links){
        links.replaceChildren();
        for(const fmt of ["srt","vtt"])for(const translated of [false,true]){
          const link=el("a","action ghost","SAVE "+(translated?"TRANSLATED":"ORIGINAL")+" "+fmt.toUpperCase());
          link.href="/api/transcripts/export?session="+encodeURIComponent(state.tvSession)+
            "&format="+fmt+"&translated="+(translated?"1":"0");
          link.download="tihulu-tv-"+state.tvSession.slice(0,8)+
            (translated?"-translated":"-original")+"."+fmt;
          links.append(link);
        }
      }
    }
    if(current.active){
      state.tvPollTimer=setTimeout(pollLiveTV,1800);
    }
  }catch(e){notice("TV playback status unavailable: "+e.message)}
}
async function addLiveTV(){
  const listing=await api("/api/live/tv/channels");
  const snapshot=await api("/api/live/tv/status");
  const compute=await api("/api/compute");
  const panel=el("article","item-card");panel.id="live-tv-center";
  panel.append(el("div","item-meta","LIVE TV / AUTHORIZED UPSTREAM SOURCE / REAL VIDEO ONLY"));
  panel.append(el("h3","","Live TV, Recording & Bilingual Subtitles"));
  panel.append(el("p","",
    "Continuous video from a pre-authorized local MPEG transport stream supplied "+
    "by Radio/TV Center; ffmpeg converts to browser-compatible fragmented MP4. "+
    "Does not scan, tune or commandeer a DVB device. No TV stream is configured "+
    "until a channel source is supplied and independently granted a tuner lease."));
  const form=el("form","rds-form");
  const channel=el("select");channel.id="live-tv-channel";
  if(!listing.channels.length){
    const empty=el("option","","No verified local TV channel source configured");
    empty.value="";channel.append(empty);
  }else{
    listing.channels.forEach(c=>{
      const option=el("option","",c.name+" · operator-configured / not RF-verified");
      option.value=c.id;channel.append(option);
    });
  }
  const ch=el("div","field");ch.append(el("label","","TV channel / upstream source"),channel);form.append(ch);
  const settings=el("div","live-grid");
  const lang=el("select"),target=el("select"),backend=el("select");
  const tvTranslationBackend=el("select");
  for(const name of ["auto","cpu","gpu","npu"]){
    const option=el("option","",name.toUpperCase()+" (subtitle translator)");
    option.value=name;tvTranslationBackend.append(option);
  }
  for(const [value,name] of [["en","English"],["de","Deutsch"],["tr","Türkçe"]]){
    const l=el("option","",name);l.value=value;lang.append(l);
    const t=el("option","",name);t.value=value;target.append(t);
  }
  lang.value="de";target.value="tr";
  for(const key of ["auto","cpu","gpu","npu"]){
    const option=el("option","",key.toUpperCase()+" · "+
      compute.selection[key].detected_device+
      (compute.selection[key].ready?" · ready":" · unavailable"));
    option.value=key;backend.append(option);
  }
  for(const [label,control] of [["Original TV audio language",lang],
                                  ["Translate captions to",target],
                                  ["Speech compute backend",backend],
                                  ["Translation backend",tvTranslationBackend]]){
    const wrap=el("div","field");
    wrap.append(el("label","",label),control);settings.append(wrap);
  }
  form.append(settings);
  const subtitles=el("input");subtitles.type="checkbox";
  const translate=el("input");translate.type="checkbox";
  const record=el("input");record.type="checkbox";
  for(const [input,text] of [[subtitles,"Transcribe real TV audio into original-language captions"],
                              [translate,"Also translate live subtitles (EN/DE/TR)"],
                              [record,"Record the TV stream locally"]]){
    const label=el("label","scan-consent");
    label.append(input,document.createTextNode(" "+text));form.append(label);
  }
  const consent=el("input");consent.type="checkbox";consent.id="live-tv-consent";
  const label=el("label","scan-consent");
  label.append(consent,document.createTextNode(
    " I confirm the upstream TV source is dedicated to this session "+
    "and does not interrupt protected recordings or Flight Radar."));
  form.append(label);
  const start=el("button","action primary","START LIVE TV");
  start.id="live-tv-start";start.type="submit";
  const stop=el("button","action ghost","STOP TV");
  stop.id="live-tv-stop";stop.type="button";
  form.append(start,stop);panel.append(form);
  const status=el("p","full-body",listing.capability.reason);
  status.id="live-tv-status";panel.append(status);
  const video=$("persistent-tv-player");
  panel.append(el("p","full-body",
    "Your live TV playback stays in the media dock while you browse other pages."));
  panel.append(el("h4","","Real original / translated TV captions"));
  const captionList=el("div","live-caption-list");captionList.id="live-tv-captions";panel.append(captionList);
  const later=el("div","field");later.append(el("label","","Translate saved captions later to"));
  const laterLang=el("select");laterLang.id="live-tv-later-language";
  for(const [code,name] of [["en","English"],["de","Deutsch"],["tr","Türkçe"]]){
    const option=el("option","",name);option.value=code;laterLang.append(option);
  }
  laterLang.value="tr";later.append(laterLang);panel.append(later);
  const links=el("div","card-actions");links.id="live-tv-export";panel.append(links);
  panel.append(el("p","full-body",
    "TV and radio share the same transcript/translation archive. Actual "+
    "live TV subtitles depend on installed Whisper-compatible models, a "+
    "working upstream MPEG-TS audio track and available compute. "+
    "No dummy captions or artificial broadcasts are generated."));
  if(!listing.channels.length){
    panel.append(el("p","discover-warn",
      "Hauppauge DVB-T2 input is not yet connected. Configure an owned local "+
      "MPEG-TS channel feed via TIHULU_TV_CHANNELS_FILE after DVB service "+
      "and receiver-leasing setup; see docs/LIVE_MEDIA_TRANSLATION.md."));
  }
  $("content").append(panel);
  form.addEventListener("submit",async e=>{
    e.preventDefault();if(!consent.checked||!channel.value)return;
    start.disabled=true;
    try{
      const newSession=await api("/api/live/tv/start","POST",{
        channel_id:channel.value,record:record.checked,
        subtitles:subtitles.checked,original_language:lang.value,
        translated_language:subtitles.checked&&translate.checked?target.value:null,
        backend:backend.value,translation_backend:tvTranslationBackend.value,
        upstream_authorized:true});
      state.tvActive=true;state.tvSession=newSession.session;
      video.src="/api/live/tv/stream?session="+encodeURIComponent(state.tvSession)+
        "&token="+encodeURIComponent(state.csrf);
      video.dataset.session=state.tvSession;syncLiveMediaDock();
      try{await video.play()}
      catch(_){notice("TV source started. Press Play on the TV player if autoplay is blocked.")}
      if(state.tvPollTimer)clearTimeout(state.tvPollTimer);
      state.tvPollTimer=setTimeout(pollLiveTV,250);
    }catch(err){notice("TV unavailable: "+err.message);start.disabled=false}
  });
  stop.addEventListener("click",async()=>{
    try{
      video.pause();video.removeAttribute("src");video.dataset.session="";video.load();syncLiveMediaDock();
      await api("/api/live/tv/stop","POST",{});
      state.tvActive=false;
      if(state.tvPollTimer)clearTimeout(state.tvPollTimer);
      state.tvPollTimer=setTimeout(pollLiveTV,250);
    }catch(err){notice(err.message)}
  });
  consent.addEventListener("change",()=>{
    start.disabled=!consent.checked||!channel.value||state.tvActive||!listing.capability.ready;
  });
  state.tvActive=snapshot.active;
  if(snapshot.session)state.tvSession=snapshot.session;
  if(snapshot.active&&snapshot.session&&video.dataset.session!==snapshot.session){
    video.src="/api/live/tv/stream?session="+encodeURIComponent(snapshot.session)+
      "&token="+encodeURIComponent(state.csrf);
    video.dataset.session=snapshot.session;
  }
  syncLiveMediaDock();
  start.disabled=!listing.capability.ready||!listing.channels.length;
  stop.disabled=!snapshot.active;
  if(state.tvPollTimer)clearTimeout(state.tvPollTimer);
  state.tvPollTimer=setTimeout(pollLiveTV,500);
  const records=await api("/api/live/tv/recordings");
  if(records.length){
    const archive=el("div","scan-summary");
    archive.append(el("h4","","Local TV recordings"));
    records.forEach(item=>{
      const link=el("a","","DOWNLOAD "+item.name+" · "+(item.bytes/1048576).toFixed(1)+" MiB");
      link.href="/api/live/tv/recording/"+encodeURIComponent(item.name);
      link.download=item.name;archive.append(link);
    });
    panel.append(archive);
  }
}
async function addLiveRadio(){
  const snapshot=await api("/api/live/radio/status");
  const compute=await api("/api/compute");
  const panel=el("article","item-card");panel.id="live-radio-center";
  panel.append(el("div","item-meta","LIVE RF / INDEFINITE RADIO PLAYBACK / OPTIONAL RECORDING"));
  panel.append(el("h3","","Live FM Radio & Subtitles"));
  panel.append(el("p","",
    "Listen continuously over local RTL-SDR → rtl_fm → ffmpeg audio/mpeg. "+
    "Stop playback at any time. Optional local recording captures the same "+
    "stream until Stop; no Internet radio is substituted."));
  const form=el("form","rds-form");
  const frequency=field("Station frequency (MHz)","number","98.6",10);
  frequency.input.value="98.6";frequency.input.min="87.5";
  frequency.input.max="108";frequency.input.step="0.001";
  const options=el("div","live-grid");
  const source=el("select"),target=el("select"),backend=el("select");
  const translationBackend=el("select");
  for(const name of ["auto","cpu","gpu","npu"]){
    const option=el("option","",name.toUpperCase()+" (subtitle translator)");
    option.value=name;translationBackend.append(option);
  }
  for(const [value,label] of [["en","English"],["de","Deutsch"],["tr","Türkçe"]]){
    const op=el("option","",label);op.value=value;source.append(op);
    const ot=el("option","",label);ot.value=value;target.append(ot);
  }
  source.value="de";target.value="tr";
  for(const name of ["auto","cpu","gpu","npu"]){
    const status=compute.selection[name];
    const op=el("option","",name.toUpperCase()+" — "+status.detected_device+
      (status.ready?" · ready":" · not ready"));
    op.value=name;backend.append(op);
  }
  for(const [label,select] of [["Original speech language",source],
                              ["Translation target",target],
                              ["Compute (auto or manual)",backend],
                              ["Translation backend",translationBackend]]){
    const wrap=el("div","field");
    wrap.append(el("label","",label),select);options.append(wrap);
  }
  form.append(frequency.wrap,options);
  const flags=el("div","live-choices");
  const captions=el("input");captions.type="checkbox";captions.id="live-enable-captions";
  const autoTranslate=el("input");autoTranslate.type="checkbox";autoTranslate.id="live-auto-translate";
  const record=el("input");record.type="checkbox";record.id="live-record";
  for(const [input,label] of [[captions,"Enable live original-language transcription"],
                              [autoTranslate,"Also translate speech live to the target language"],
                              [record,"Record actual radio audio to local storage"]]){
    const row=el("label","scan-consent");
    row.append(input,document.createTextNode(" "+label));flags.append(row);
  }
  form.append(flags);
  const agree=el("input");agree.type="checkbox";agree.id="live-radio-consent";
  const permission=el("label","scan-consent");
  permission.append(agree,document.createTextNode(
    " I approve continuous receiver tuning. Flight Radar, Gqrx, welle.io or "+
    "other protected recordings must not use this same RTL-SDR."));
  form.append(permission);
  const start=el("button","action primary","START LIVE RADIO");
  start.type="submit";start.id="live-radio-start";
  const stop=el("button","action ghost","STOP RADIO");
  stop.type="button";stop.id="live-radio-stop";
  const actions=el("div","card-actions");
  actions.append(start,stop);form.append(actions);
  panel.append(form);
  const status=el("p","full-body","Not started");status.id="live-radio-status";
  panel.append(status);
  const audio=$("persistent-radio-player");
  panel.append(el("p","full-body",
    "Your live FM playback stays in the media dock while you browse other pages."));
  const computeInfo=el("div","scan-summary");
  computeInfo.append(el("h4","","Detected local compute and offline models"));
  compute.devices.forEach(d=>computeInfo.append(el("p","full-body",
    d.id.toUpperCase()+": "+d.name+" · "+
    (d.detected?"hardware detected":"not detected")+" · "+
    (compute.selection[d.id].ready?"speech runtime ready":"speech runtime unavailable"))));
  computeInfo.append(el("p","full-body",
    "Speech: "+(compute.speech.ready_cpu?"CPU model ready":"CPU model missing")+
    " · GPU compatible model: "+(compute.speech.ready_gpu?"ready":"not confirmed")+
    " · NPU compatible model: "+(compute.speech.ready_npu?"ready":"not configured")+
    " · Argos package: "+(compute.translation.python_package_installed?"installed":"missing")+
    " · offline language pairs: "+compute.translation.available_pairs.map(p=>p.source+"→"+p.target).join(", ")));
  panel.append(computeInfo);
  panel.append(el("h4","","Live / saved transcript (original & translated)"));
  const captionList=el("div","live-caption-list");captionList.id="live-radio-captions";
  panel.append(captionList);
  const later=el("div","field");
  later.append(el("label","","Translate stored captions later to"));
  const laterLanguage=el("select");laterLanguage.id="live-later-language";
  for(const [value,label] of [["en","English"],["de","Deutsch"],["tr","Türkçe"]]){
    const opt=el("option","",label);opt.value=value;laterLanguage.append(opt);
  }
  laterLanguage.value="tr";later.append(laterLanguage);panel.append(later);
  const exportLinks=el("div","card-actions");exportLinks.id="live-export-links";
  panel.append(exportLinks);
  panel.append(el("p","full-body",
    "Speech/translation runs only with installed compatible local models. "+
    "When a model or language pair is missing, no artificial caption/translation is shown. "+
    "Original transcripts remain available for later translation."));
  $("content").append(panel);
  agree.addEventListener("change",()=>{start.disabled=!agree.checked||state.liveActive||!snapshot.capability?.ready});
  form.addEventListener("submit",async e=>{
    e.preventDefault();if(!agree.checked)return;
    start.disabled=true;
    try{
      const created=await api("/api/live/radio/start","POST",{
        frequency_mhz:Number(frequency.input.value),record:record.checked,
        subtitles:captions.checked,
        original_language:source.value,
        translated_language:captions.checked&&autoTranslate.checked?target.value:null,
        backend:backend.value,translation_backend:translationBackend.value});
      state.liveActive=created.active;state.liveSession=created.session;
      const url="/api/live/radio/stream?session="+
        encodeURIComponent(created.session)+"&token="+encodeURIComponent(state.csrf);
      audio.src=url;audio.dataset.session=created.session;syncLiveMediaDock();
      try{await audio.play()}catch(_){
        notice("Stream started. Press Play on the radio player if browser autoplay was blocked.");
      }
      if(state.livePollTimer)clearTimeout(state.livePollTimer);
      state.livePollTimer=setTimeout(pollLiveRadio,300);
    }catch(err){notice("Cannot start live radio: "+err.message);start.disabled=false;}
  });
  stop.addEventListener("click",async()=>{
    try{
      audio.pause();audio.removeAttribute("src");audio.dataset.session="";audio.load();syncLiveMediaDock();
      await api("/api/live/radio/stop","POST",{});
      state.liveActive=false;
      if(state.livePollTimer)clearTimeout(state.livePollTimer);
      state.livePollTimer=setTimeout(pollLiveRadio,250);
      notice("Live receiver stopped. Saved audio/captions remain in archive.");
    }catch(e){notice(e.message)}
  });
  state.liveActive=snapshot.active;
  if(snapshot.session)state.liveSession=snapshot.session;
  if(snapshot.active&&snapshot.session&&audio.dataset.session!==snapshot.session){
    audio.src="/api/live/radio/stream?session="+encodeURIComponent(snapshot.session)+
      "&token="+encodeURIComponent(state.csrf);
    audio.dataset.session=snapshot.session;
  }
  syncLiveMediaDock();
  if(state.livePollTimer)clearTimeout(state.livePollTimer);
  state.livePollTimer=setTimeout(pollLiveRadio,500);
  const recordings=await api("/api/live/radio/recordings");
  if(recordings.length){
    const archive=el("div","scan-summary");
    archive.append(el("h4","","Local radio recordings"));
    recordings.forEach(r=>{
      const link=el("a","","SAVE "+r.name+" ("+(r.bytes/1024/1024).toFixed(1)+" MiB)");
      link.href="/api/live/radio/recording/"+encodeURIComponent(r.name);
      link.download=r.name;archive.append(link);
    });
    panel.append(archive);
  }
}
async function addAudioPreview(){
  const snapshot=await api("/api/audio/status");
  const outer=el("article","item-card");outer.id="fm-audio-panel";
  outer.append(el("div","item-meta","RECEIVE-ONLY FM AUDIO / EXPLICIT USER REQUEST"));
  outer.append(el("h3","","Listen to a short FM radio preview"));
  outer.append(el("p","",
    "Captures 10–20 seconds of actual mono FM audio as WAV using rtl_fm. "+
    "This is a listening preview, NOT an indefinite live stream; it does not "+
    "require an Internet connection, redsea, or an audio output device on the server. "+
    "The clip is held in memory only."));
  const duration=el("div","field");
  const frequency=field("FM frequency (MHz)","number","98.600",10);
  frequency.input.id="fm-audio-frequency";
  frequency.input.value="98.6";frequency.input.min="87.5";
  frequency.input.max="108.0";frequency.input.step="0.001";
  const opts=el("select");opts.id="fm-audio-length";
  [10,12,15,20].forEach(n=>{
    const option=el("option","",n+" seconds");option.value=n;
    if(n===12)option.selected=true;opts.append(option);
  });
  duration.append(el("label","","Preview duration"),opts);
  const form=el("form","rds-form");
  const cbLabel=el("label","scan-consent");
  const confirm=el("input");confirm.type="checkbox";confirm.id="fm-audio-confirm";
  cbLabel.append(confirm,document.createTextNode(
    " I authorize this short RTL-SDR FM tuning session; no Flight Radar, "+
    "SDR app or protected recording may be using the same tuner."));
  const start=el("button","action primary","RECORD & LISTEN");
  start.type="submit";start.id="fm-audio-start";
  const stop=button("STOP RECORDING",async()=>{
    try{
      await api("/api/audio/stop","POST",{});
      if(state.audioPollTimer)clearTimeout(state.audioPollTimer);
      state.audioPollTimer=setTimeout(pollAudioPreview,200);
    }catch(e){notice(e.message)}
  },"action ghost");
  stop.id="fm-audio-stop";
  const actions=el("div","card-actions");actions.append(start,stop);
  append(form,frequency.wrap,duration,cbLabel,actions);outer.append(form);
  const progress=el("p","full-body","No audio preview recorded");
  progress.id="fm-audio-status";outer.append(progress);
  const player=el("audio","local-audio-player");
  player.id="fm-audio-player";player.controls=true;player.preload="none";
  player.hidden=true;
  player.setAttribute("aria-label","Locally received FM audio preview");
  outer.append(player);
  outer.append(el("p","full-body",snapshot.capability?.reason||"Audio readiness unknown"));
  form.addEventListener("submit",async e=>{
    e.preventDefault();
    if(!confirm.checked)return notice("Confirm that your SDR is free before listening.");
    start.disabled=true;
    try{
      player.pause();player.hidden=true;player.removeAttribute("src");
      const created=await api("/api/audio/start","POST",{
        frequency_mhz:Number(frequency.input.value),
        duration_seconds:Number(opts.value)});
      state.audioActive=created.active;
      notice("Recording an actual, short FM preview; audio playback becomes available when complete.");
      if(state.audioPollTimer)clearTimeout(state.audioPollTimer);
      state.audioPollTimer=setTimeout(pollAudioPreview,400);
    }catch(error){notice("Audio preview unavailable: "+error.message);start.disabled=false;}
  });
  confirm.addEventListener("change",()=>{start.disabled=!confirm.checked||state.audioActive||!snapshot.capability?.ready});
  $("content").append(outer);
  state.audioActive=snapshot.active;
  showAudioStatus(snapshot);
  if(snapshot.active){
    if(state.audioPollTimer)clearTimeout(state.audioPollTimer);
    state.audioPollTimer=setTimeout(pollAudioPreview,750);
  }
}
function showDabServices(result){
  const box=$("dab-service-results");
  if(!box)return;
  box.replaceChildren();
  if(!result.connected){
    box.append(el("p","",result.message||
      "No existing welle-cli local web receiver has been checked."));
    return;
  }
  box.append(el("p","",
    "Ensemble: "+(result.ensemble||"unlabelled")+" · channel "+result.channel+
    " · "+(result.frequency_hz?(result.frequency_hz/1e6).toFixed(3)+" MHz":"frequency unverified")+
    " · "+result.services.length+" decoded service entries"));
  box.append(el("p","full-body",
    "DLS labels archived: "+result.imported_dls+
    " · MOT slides archived: "+result.saved_mot_images+
    (result.archive_notice?" · "+result.archive_notice:"")));
  result.services.forEach(s=>{
    const item=el("div","rds-row");
    item.append(el("div","item-meta",
      s.sid+" · "+(s.program_type||"unknown programme type")));
    item.append(el("strong","",s.name));
    item.append(el("p","",
      s.dls ? "DLS: "+s.dls+" · received "+(s.dls_received_at||"time unknown")
            : "No decoded DLS from this station"));
    item.append(el("p","full-body",
      s.mot_received_at?"MOT slide timestamp: "+s.mot_received_at:
      "No decoded slideshow timestamp"));
    box.append(item);
  });
}
function stopManagedDabPolling(){
  if(state.managedDabPollTimer){
    clearTimeout(state.managedDabPollTimer);
    state.managedDabPollTimer=null;
  }
}
async function pollManagedDab(){
  if(!state.managedDabOwned){stopManagedDabPolling();return;}
  try{
    const status=await api("/api/dab/manage/status?owner="+
      encodeURIComponent(state.clientId));
    const info=$("managed-dab-status");
    if(info)info.textContent=status.active
      ?"APP-OWNED DAB "+status.channel+" · receiver PID "+status.pid+
        " · auto-release after browser disconnect"
      :"APP-OWNED DAB STOPPED · local SDR released";
    if(!status.active){state.managedDabOwned=false;stopManagedDabPolling();return;}
  }catch(e){
    notice("Managed DAB receiver check: "+e.message);
  }
  stopManagedDabPolling();
  if(state.managedDabOwned)state.managedDabPollTimer=setTimeout(pollManagedDab,4500);
}
async function addWelleDabBridge(){
  const last=await api("/api/dab/last");
  const panel=el("article","item-card");
  panel.id="dab-welle-bridge";
  panel.append(el("div","item-meta","DAB+ BROADCAST DATA / EXISTING RECEIVER / READ-ONLY"));
  panel.append(el("h3","","DAB+ DLS, MOT slideshow & radio services"));
  panel.append(el("p","",
    "Read current DAB ensemble, station names, DLS and genuine MOT slides "+
    "from the local welle-cli decoder at 127.0.0.1:7979. Decoder data import "+
    "remains read-only and never retunes. The separate Start/Stop section "+
    "below can launch or stop ONLY a welle-cli child explicitly started by "+
    "this Text Center tab. External readsb, Flight Radar and independently "+
    "started welle-cli processes are never stopped automatically."));
  const opt=el("label","scan-consent");
  const img=el("input");img.type="checkbox";img.checked=true;img.id="dab-images";
  opt.append(img,document.createTextNode(" Save decoded MOT slideshow images offline "+
    "from this receiver (bounded PNG/JPEG, only if the broadcast actually provides them)."));
  panel.append(opt);
  const managed=el("section","scan-summary");
  managed.append(el("h4","","Manage local DAB receiver (explicit opt-in)"));
  managed.append(el("p","full-body",
    "START DAB opens welle-cli as a child of this Text Center only after checking "+
    "the SDR is free. STOP DAB releases only this app-owned child. "+
    "Independently started welle-cli and readsb are never terminated."));
  const channel=el("select");
  channel.id="managed-dab-channel";
  for(const code of ["5C","8B","9D","11D"]){
    const o=el("option","",code);o.value=code;
    if(code==="11D")o.selected=true;
    channel.append(o);
  }
  managed.append(channel);
  const manageActions=el("div","card-actions");
  const dabStart=button("START DAB RECEIVER",async()=>{
    dabStart.disabled=true;
    try{
      const consent=confirm("Start the locally installed welle-cli and tune the "+
        "Nooelec SDR to DAB "+channel.value+
        "? All other SDR owners must first be stopped in their own applications.");
      if(!consent)return;
      const result=await api("/api/dab/manage/start","POST",{
        channel:channel.value,owner:state.clientId,consent:true
      });
      state.managedDabOwned=true;
      notice("Started app-owned DAB "+result.channel+
        ". The browser connection will be monitored and the child freed on exit.");
      await pollManagedDab();
    }catch(error){notice("Could not start DAB: "+error.message)}
    finally{dabStart.disabled=false}
  },"action primary");
  const dabStop=button("STOP DAB RECEIVER",async()=>{
    dabStop.disabled=true;
    try{
      const result=await api("/api/dab/manage/stop","POST",{
        owner:state.clientId,owner_only:true
      });
      state.managedDabOwned=false;stopManagedDabPolling();
      const info=$("managed-dab-status");
      if(info)info.textContent=result.stopped
        ?"Owned DAB decoder stopped; tuner released."
        :"No DAB receiver was started by this browser tab.";
      notice("Only this tab's app-managed DAB receiver was stopped.");
    }catch(error){notice(error.message)}
    finally{dabStop.disabled=false}
  },"action ghost");
  manageActions.append(dabStart,dabStop);
  managed.append(manageActions);
  const managedStatus=el("p","full-body",
    "External receivers remain externally managed.");
  managedStatus.id="managed-dab-status";
  managed.append(managedStatus);
  panel.append(managed);
  const row=el("div","card-actions");
  const refresh=button("READ RUNNING DAB RECEIVER",async()=>{
    refresh.disabled=true;
    try{
      const result=await api("/api/dab/refresh","POST",{
        include_images:img.checked
      });
      showDabServices(result);
      await refreshCounts();
      notice("Read actual welle-cli metadata; no tuner retuned. Refresh page 400 to view archived images.");
    }catch(e){notice("DAB receiver unavailable: "+e.message)}
    finally{refresh.disabled=false}
  },"action primary");
  const external=el("a","action ghost","OPEN WELLE-CLI PLAYER");
  external.href="http://127.0.0.1:7979/";
  external.target="_blank";external.rel="noopener noreferrer";
  external.title="Opens existing local welle-cli web interface; requires running welle-cli";
  row.append(refresh,external);
  panel.append(row);
  const results=el("div","scan-summary");results.id="dab-service-results";
  panel.append(results);
  $("content").append(panel);
  showDabServices(last);
  panel.append(el("p","full-body",
    "Journaline interactive menus, TPEG and other advanced services still require "+
    "their own decoders and licensing. A DAB image is NOT automatically an Internet cover image."));
}
async function addRadioImageGallery(){
  const images=await api("/api/media");
  const outer=el("article","item-card");
  outer.append(el("div","item-meta","REAL BROADCAST IMAGE ARCHIVE · OFFLINE"));
  outer.append(el("h3","","Station logos & DAB slideshow images"));
  outer.append(el("p","",
    "RDS2/RFT station logos and actual DAB MOT decoder images appear "+
    "here only after being decoded/attributed and stored locally. "+
    "No Internet artwork is substituted for broadcast images."));
  if(!images.length){
    outer.append(el("p","full-body",
      "No broadcast images received or imported. RDS2 needs redsea 1.2+ "+
      "and a broadcaster sending logo data. DAB MOT needs a DAB metadata decoder."));
  }else{
    const gallery=el("div","radio-media-grid");
    images.forEach(entry=>{
      const card=el("div","radio-media-card");
      const picture=el("img","radio-image");
      picture.src="/api/media/file/"+encodeURIComponent(entry.id);
      picture.loading="lazy";
      picture.alt="Broadcast image imported from "+entry.station;
      card.append(picture,el("strong","",entry.station),
        el("p","",entry.medium.toUpperCase()+" · "+(entry.frequency_hz/1e6).toFixed(3)+" MHz"),
        el("p","",timeLabel(entry.received_at)+" · "+entry.provenance));
      gallery.append(card);
    });
    outer.append(gallery);
  }
  $("content").append(outer);
}
async function addDvbDevicePanel(){
  const dvb=await api("/api/dvb/status");
  const panel=el("article","item-card");
  panel.append(el("div","item-meta","DVB-T / DVB-T2 / DVB-C · PASSIVE DEVICE CHECK"));
  panel.append(el("h3","","Hauppauge WinTV-soloHD 01589 readiness"));
  panel.append(el("p","",
    "Separate USB television receiver — not the Nooelec SDR. "+
    "Detect USB devices, frontend paths, candidate firmware and installed DVB tools. "+
    "No TV channel scan or recording is interrupted by this check."));
  panel.append(el("p","full-body",
    "Hauppauge USB candidates: "+dvb.hauppauge_usb.length+
    " · Explicit soloHD product string: "+(dvb.model_confirmed?"seen":"not confirmed")+
    " · DVB frontends: "+dvb.dvb_frontends.length));
  dvb.hauppauge_usb.forEach(x=>panel.append(el("p","full-body",
    "USB "+x.usb_id+" · "+x.product+" · "+x.usb_path)));
  dvb.dvb_frontends.forEach(x=>panel.append(el("p","full-body",
    "Frontend "+x.frontend+" · "+x.kernel_name+" · ownership/lock not verified")));
  panel.append(el("p","full-body",
    "Firmware candidates: "+Object.entries(dvb.firmware_candidates).map(([k,v])=>
      k+" "+(v?"present":"missing")).join(" · ")));
  panel.append(el("p","full-body",
    "DVB utilities: "+Object.entries(dvb.tools).map(([k,v])=>
      k+" "+(v?"installed":"missing")).join(" · ")));
  panel.append(el("p","full-body",
    "DVB service and Teletext PID decoding NOT connected yet. "+
    "When the tuner arrives, verify its physical USB identity and driver/firmware "+
    "before a region-scoped service scan behind protected tuner ownership."));
  const actions=el("div","card-actions");
  actions.append(button("RECHECK DVB HARDWARE",async()=>{
    try{await showRadioData();notice("Refreshed passive DVB status; no tuning performed.")}
    catch(e){notice(e.message)}
  }));
  panel.append(actions);
  $("content").append(panel);
}

async function addOfflineRecordingControl(){
  const [radio,tv,hardware,job]=await Promise.all([
    api("/api/live/radio/recordings"),api("/api/live/tv/recordings"),
    api("/api/compute"),api("/api/recordings/transcription/status")
  ]);
  const recordings=radio.map(x=>({medium:"fm",name:x.name})).concat(tv.map(x=>({medium:"dvb_tv",name:x.name})));
  const panel=card("Transcribe an earlier FM or TV recording",
    "Offline EN / DE / TR speech-to-text. Optional translation, original text and SRT/VTT exports. Does not tune any receiver.",
    "SAVED MEDIA / MANUAL POST-PROCESSING");
  const form=el("form","rds-form");
  const selector=el("select");
  for(let i=0;i<recordings.length;i++){
    const r=recordings[i],o=el("option","",(r.medium==="fm"?"FM":"TV")+" · "+r.name);
    o.value=i;selector.append(o);
  }
  if(!recordings.length)selector.append(el("option","","No recorded streams yet"));
  const language=el("select"),target=el("select"),backend=el("select");
  for(const k of ["en","de","tr"]){
    const a=el("option","",k.toUpperCase()),b=el("option","",k.toUpperCase());
    a.value=k;b.value=k;language.append(a);target.append(b);
  }
  language.value="de";target.value="tr";
  for(const k of ["auto","cpu","gpu","npu"]){
    const v=hardware.selection[k];
    const o=el("option","",k.toUpperCase()+" · "+v.detected_device+
      (v.ready?" · ready":" · unavailable"));
    o.value=k;backend.append(o);
  }
  for(const pair of [["Recording",selector],["Original language",language],
    ["Translation language",target],["ASR compute device",backend]]){
    const p=el("div","field");
    p.append(el("label","",pair[0]),pair[1]);form.append(p);
  }
  const translation=el("input");translation.type="checkbox";
  const label=el("label","scan-consent");
  label.append(translation,document.createTextNode(" Also translate with installed offline language model"));
  form.append(label);
  const go=el("button","action primary","TRANSCRIBE SAVED RECORDING");go.type="submit";
  const stop=button("CANCEL",()=>api("/api/recordings/transcription/stop","POST",{})
    .catch(e=>notice(e.message)),"action ghost");
  form.append(go,stop);panel.append(form);
  const stateLabel=el("p","full-body","");panel.append(stateLabel);
  const output=el("div","live-caption-list");panel.append(output);
  const exports=el("div","card-actions");panel.append(exports);
  $("content").append(panel);
  async function refresh(){
    if(state.page!==400)return;
    const status=await api("/api/recordings/transcription/status");
    stateLabel.textContent=status.status.toUpperCase()+" · "+status.segments+
      " segments · "+status.seconds_processed+" s · "+(status.device||"no ASR")+
      (status.error?" · "+status.error:"");
    go.disabled=status.active||!recordings.length;
    stop.disabled=!status.active;
    if(status.session){
      const items=await api("/api/transcripts?session="+encodeURIComponent(status.session));
      output.replaceChildren();
      for(const item of items.slice(-10)){
        const row=el("div","live-caption-row");
        row.append(el("p","full-body",item.original_language.toUpperCase()+
          " [ "+item.started_seconds.toFixed(1)+"–"+item.ended_seconds.toFixed(1)+
          " s ]: "+item.original_text));
        row.append(el("p","full-body",item.translated_text
          ? item.translated_language.toUpperCase()+": "+item.translated_text
          : "No translated text stored"));
        if(!item.translated_text){
          row.append(button("TRANSLATE THIS SEGMENT LATER",async()=>{
            try{
              await api("/api/transcripts/translate","POST",{
                id:item.id,target_language:target.value,backend:"auto"});
              notice("Original and translated caption saved separately.");
              await refresh();
            }catch(error){notice("Translation unavailable: "+error.message)}
          }));
        }
        output.append(row);
      }
      exports.replaceChildren();
      for(const format of ["srt","vtt"]){
        for(const translated of [false,true]){
          const link=el("a","action ghost","EXPORT "+
            (translated?"TRANSLATED ":"ORIGINAL ")+format.toUpperCase());
          link.href="/api/transcripts/export?session="+encodeURIComponent(status.session)+
            "&format="+format+"&translated="+(translated?"1":"0");
          link.target="_blank";link.rel="noopener";
          exports.append(link);
        }
      }
    }
    if(status.active)setTimeout(refresh,1200);
  }
  form.addEventListener("submit",async event=>{
    event.preventDefault();
    const source=recordings[Number(selector.value)];
    if(!source)return;
    try{
      await api("/api/recordings/transcription/start","POST",{
        medium:source.medium,filename:source.name,original_language:language.value,
        translated_language:translation.checked?target.value:null,backend:backend.value
      });
      await refresh();
    }catch(error){notice(error.message)}
  });
  await refresh();
}
async function showLiveRadioPage(){
  section("LIVE RADIO","Continuous FM radio, recording & captions",
    "Only when one available RTL-SDR is explicitly allocated");
  try{await addLiveRadio()}catch(e){empty("Live radio unavailable",e.message)}
  try{await addRdsControl()}catch(e){empty("RDS metadata unavailable",e.message)}
  try{await addRadioImageGallery()}catch(e){empty("Station artwork unavailable",e.message)}
}
async function showLiveTVPage(){
  section("LIVE TV","Live television, recording & bilingual subtitles",
    "Requires a separately leased authorized MPEG-TS source");
  try{await addLiveTV()}catch(e){empty("TV source unavailable",e.message)}
  try{await addDvbDevicePanel()}catch(e){empty("DVB diagnostics unavailable",e.message)}
}
async function showTranslatorPage(){
  section("OFFLINE TRANSLATOR","English · Deutsch · Türkçe",
    "Original language preserved · Local models only");
  const translation=await api("/api/translation/status");
  const compute=await api("/api/compute");
  const box=el("article","item-card");
  box.append(el("div","item-meta","OFFLINE / NO AUTOMATIC MODEL DOWNLOAD"));
  box.append(el("h3","","Translate between English, German and Turkish"));
  const pairs=translation.pairs.map(p=>p.source.toUpperCase()+" → "+p.target.toUpperCase());
  box.append(el("p","",pairs.length?
    "Installed language pairs: "+pairs.join(", "):
    "No installed Argos language-pair models detected. Install pairs explicitly to enable translation."));
  const form=el("form","rds-form");
  const controls=el("div","live-grid");
  const source=el("select"),target=el("select"),backend=el("select");
  const options=[["en","English"],["de","Deutsch"],["tr","Türkçe"]];
  options.forEach(([code,title])=>{
    const a=el("option","",title);a.value=code;source.append(a);
    const b=el("option","",title);b.value=code;target.append(b);
  });
  source.value="de";target.value="tr";
  for(const [key,label,ready] of [
      ["auto","AUTO — verified GPU or CPU",true],
      ["cpu","CPU — offline Argos",translation.cpu_available],
      ["gpu","GPU — CUDA / CTranslate2",translation.gpu_available],
      ["npu","NPU — translator model not supported",translation.npu_available]]){
    const option=el("option","",label+(ready?"":" · UNAVAILABLE"));
    option.value=key;option.disabled=!ready;backend.append(option);
  }
  for(const [label,control] of [
      ["Original language",source],["Target language",target],
      ["Compute backend",backend]]){
    const group=el("div","field");group.append(el("label","",label),control);
    controls.append(group);
  }
  form.append(controls);
  const original=el("textarea","translation-editor");
  original.rows=6;original.maxLength=12000;
  original.placeholder="Write or paste text in English, German or Turkish.";
  form.append(original);
  const go=el("button","action primary","TRANSLATE OFFLINE");
  go.type="submit";form.append(go);
  const output=el("pre","translation-output");
  output.textContent="Only a genuine installed translation model can produce translated text.";
  box.append(form,el("h4","","Translation"),output);
  const copy=button("COPY TRANSLATION",async()=>{
    try{
      if(!navigator.clipboard)throw Error("Clipboard not available");
      await navigator.clipboard.writeText(output.textContent);
      notice("Translation copied.");
    }catch(_){notice("Select and copy the translated text manually.")}
  });
  box.append(copy);
  form.addEventListener("submit",async e=>{
    e.preventDefault();go.disabled=true;
    try{
      const response=await api("/api/translation/text","POST",{
        source:source.value,target:target.value,
        backend:backend.value,text:original.value});
      output.textContent=response.translated;
      notice("Translated locally; original text remains untouched.");
    }catch(e){
      output.textContent="Translation unavailable: "+e.message;
      notice(e.message);
    }finally{go.disabled=false}
  });
  $("content").append(box);
  const hardware=el("article","notice-card");
  hardware.append(el("h3","","Detected compute devices"));
  compute.devices.forEach(d=>hardware.append(el("p","",
    d.id.toUpperCase()+" — "+d.name+" · "+
    (d.detected?"detected":"not detected")+" · "+
    (d.runtime_ready?"runtime verified":"runtime not verified"))));
  hardware.append(el("p","",
    "Speech recognition and text translation use separate engines. "+
    "Hailo or Intel NPU detection may allow speech recognition with a compatible "+
    "installed model, but NPU translation remains disabled until verified. "+
    "Nothing is downloaded automatically."));
  $("content").append(hardware);
}
async function showRadioData(){
  section("RF / BROADCAST SOURCES","Antenna scanning & actual decoder imports","User-approved tuning only");
  try { $("content").append(receiverCard(await refreshReceiverStatus())); }
  catch(error){empty("Receiver detection unavailable","The local USB inventory could not be read: "+error.message)}
  try {await addAutoDiscovery()}
  catch(error){empty("Auto discovery unavailable","Could not inspect local sources: "+error.message)}
  try {await addFMSurveyControl()}
  catch(error){empty("FM spectrum survey unavailable","Could not inspect rtl_power: "+error.message)}
  try {await addRdsControl()}
  catch(error){empty("FM capture control unavailable","Unable to load RDS status: "+error.message)}
  try {await addLiveRadio()}
  catch(error){empty("Live FM & subtitles unavailable",error.message)}
  try {await addLiveTV()}
  catch(error){empty("Live TV & subtitles unavailable",error.message)}
  try {await addOfflineRecordingControl()}
  catch(error){empty("Saved recording ASR unavailable",error.message)}
  try {await addAudioPreview()}
  catch(error){empty("FM audio preview unavailable",error.message)}
  try {await addWelleDabBridge()}
  catch(error){empty("DAB receiver bridge unavailable",error.message)}
  try {await addRadioImageGallery()}
  catch(error){empty("Radio image archive unavailable",error.message)}
  try {await addDvbDevicePanel()}
  catch(error){empty("DVB device diagnostics unavailable",error.message)}
  const info=el("article","notice-card");
  append(info,el("h3","","RF survey is not a full broadcast decoder"),
    el("p","","Band scans for DAB/DRM/RTTY/NAVTEX/APRS/WeatherFAX find RF energy, "+
      "but no messages or stations until their specific decoders are connected. "+
      "A DVB frontend also needs a real transport-stream and Teletext PID adapter. "+
      "Internet directories are separate; they cannot be received from the antenna."));
  const more=el("div","card-actions");
  more.append(button("VIEW ALL PROTOCOLS & SCAN OPTIONS",()=>openPage(860,"",0)));
  info.append(more);$("content").append(info);
  const events=await api("/api/events");
  events.forEach((e)=>{
    const n=card(e.title,e.body,e.medium.toUpperCase()+" · "+e.station+" · "+timeLabel(e.received_at));
    n.append(el("p","full-body","Decoder evidence: "+e.provenance+" · "+e.frequency_hz+" Hz"));
    $("content").append(n);
  });
  const pages=await api("/api/pages");
  pages.forEach((p)=>{
    const n=card("P"+p.page+" / "+p.subpage+" — "+p.title,"Source: "+p.source_id+" · "+p.station+" · "+timeLabel(p.received_at),p.medium.toUpperCase());
    n.append(el("div","card-actions"));
    n.lastElementChild.append(button("OPEN RECEIVED PAGE",()=>openPage(p.page,p.source_id,p.subpage)));
    $("content").append(n);
  });
  if(!(events.length+pages.length)) empty("Nothing received yet","Use an authorized external decoder and import its actual JSON output. No fake Journaline, RDS or Teletext pages are supplied.");
  $("section-count").textContent=(events.length+pages.length)+" imported records";
}
function showEmergency(){
  section("TRUST & SAFETY","Emergency text integrity","Not an official alert feed");
  const n=el("article","notice-card");
  append(n,el("h3","","Broadcast information is not an authenticated warning"),el("p","","A received radio message, Teletext headline or community bulletin does not prove an official emergency. This standalone version does not receive BBK/NINA, AFAD, CAP or other verified alert feeds. For urgent risk, consult official channels and local authorities."));
  $("content").append(n);
  const a=el("article","item-card");
  append(a,el("h3","","Official reference sites"),el("p","","These links require internet access and are informational, not live alerts in this app."));
  const links=el("div","card-actions");
  [["Germany: warnung.bund.de","https://warnung.bund.de/"],["Türkiye: AFAD","https://www.afad.gov.tr/"]].forEach(([t,u])=>{const n=el("a","",t+" ↗");n.href=u;n.rel="noopener noreferrer";n.target="_blank";links.append(n)});
  a.append(links);$("content").append(a);
}
async function showBulletins(){
  section("LOCAL / OFFLINE","Your local bulletin board","Stored on this device");
  const form=el("article","form-card");form.append(el("h3","","Create a new local post"));
  const f=el("form","form-grid"),author=field("Author label","text","Local user",60),title=field("Subject","text","Message title",140);
  append(f,author.wrap,title.wrap);
  const msgwrap=el("div","field full"),label=el("label","","Message"),message=el("textarea");message.maxLength=4000;message.placeholder="Write a note for the offline archive…";message.required=true;append(msgwrap,label,message);f.append(msgwrap);
  const submit=el("button","action primary","POST LOCALLY");submit.type="submit";f.append(submit);
  f.addEventListener("submit",async(ev)=>{ev.preventDefault();try{
    await api("/api/bulletins","POST",{author:author.input.value,title:title.input.value,body:message.value});
    notice("Post saved locally, not transmitted over radio or internet.");await refreshCounts();await showBulletins();
  }catch(err){notice(err.message)}});
  form.append(f);$("content").append(form);
  const posts=await api("/api/bulletins");
  posts.forEach((p)=>$("content").append(card(p.title,p.body,p.author+" · "+timeLabel(p.created_at)+" · LOCAL")));
  if(!posts.length) empty("No posts yet","This is a local owner notebook. It is not an authenticated public forum or a packet-radio BBS.");
}
async function saveBookmark(label,targetType,target) {
  await api("/api/bookmarks","POST",{label,target_type:targetType,target});
  notice("Saved to local bookmarks.");
  await refreshCounts();
}
async function showLibrary(){
  section("PERSISTENT STORAGE","Saved & archived","Offline-ready");
  const bookmarks=await api("/api/bookmarks");
  bookmarks.forEach((b)=>{
    const n=card(b.label,"Saved "+timeLabel(b.created_at),b.target_type.toUpperCase());
    if(b.target_type==="page"){
      n.append(el("div","card-actions"));
      n.lastElementChild.append(button("OPEN",()=>{
        const parts=b.target.split(":");openPage(Number(parts[0]),parts[2]||"",Number(parts[1])||0);
      }));
    }
    $("content").append(n);
  });
  if(!bookmarks.length) empty("No bookmarks","Use ☆ SAVE while browsing. The underlying cached articles and imported pages remain in SQLite.");
  const pages=await api("/api/pages");
  if(pages.length){const n=el("article","notice-card");append(n,el("h3","","Imported broadcast archive"),el("p","",pages.length+" numbered page records are stored locally. Open page 400 to browse received pages."));$("content").append(n)}
}
async function showDirectory(){
  section("INTERNET-ONLY SOURCES","The small web","Not received from an antenna");
  const explainer=el("article","notice-card");
  append(explainer,
    el("h3","","These are Internet links, not broadcast channels"),
    el("p","","ARD Text on the web, TRT Telegün's website, Gemini, Gopher and online BBS "+
      "need a network connection. Antennas cannot download these sites. "+
      "When Internet is unavailable, previously downloaded RSS/Atom/JSON Feed items "+
      "and locally stored RF pages remain readable; web links without cache do not."));
  const actions=el("div","card-actions");
  actions.append(button("ANTENNA CHANNEL SCANNING",()=>openPage(400,"",0),"action primary"));
  actions.append(button("READ OFFLINE ARCHIVE",()=>openPage(700,"",0)));
  actions.append(button("CACHED NEWS / FEEDS",()=>openPage(200,"",0)));
  explainer.append(actions);
  $("content").append(explainer);
  const entries=await api("/api/directory");
  entries.forEach(d=>{
    const n=card(d.name,d.note,d.category.toUpperCase()+" · INTERNET REQUIRED");
    const link=el("a","","OPEN INTERNET SITE ↗");
    link.href=d.url;link.target="_blank";link.rel="noopener noreferrer";
    const wrapper=el("div","card-actions");wrapper.append(link);n.append(wrapper);
    $("content").append(n);
  });
}
async function openScanBand(band){
  state.selectedSurveyBand=band;
  await openPage(400,"",0);
  const elScan=$("fm-survey-control");
  if(elScan)elScan.scrollIntoView({behavior:"smooth",block:"start"});
}
async function showCapabilities(){
  section("PROTOCOLS & SCANS","31 service types and scan readiness",
          "RF bands · broadcast decoders · Internet · local content");
  const response=await api("/api/scans");
  const features=response.features;
  const intro=el("article","notice-card");
  append(intro,
    el("h3","","Every requested service is tracked — but not all can be scanned by an antenna"),
    el("p","","RF spectrum scans only identify possible energy peaks. "+
      "DAB Journaline, MOT, EPG, DVB Teletext, NAVTEX, DRM and APRS text need "+
      "their own verified decoders. Internet-only sources need a network or a prior cache. "+
      "Current receiver ownership and missing software can block a scan."));
  const shortcuts=el("div","card-actions");
  shortcuts.append(button("GO TO RF SCANNER",()=>openPage(400,"",0),"action primary"));
  shortcuts.append(button("VIEW INTERNET LINKS",()=>openPage(800,"",0)));
  intro.append(shortcuts);
  $("content").append(intro);
  const groups=[...new Set(features.map(x=>x.group))];
  groups.forEach(group=>{
    const title=el("h3","protocol-group",group);$("content").append(title);
    features.filter(x=>x.group===group).forEach(f=>{
      const source=f.medium.replaceAll("_"," ").toUpperCase();
      const stateText=f.implementation.replaceAll("_"," ").toUpperCase();
      const item=card(f.title,f.requirements,source+" · "+stateText);
      const description=el("p","full-body",f.reason);
      item.append(description);
      const actionRow=el("div","card-actions");
      if(f.scan_type==="rf_spectrum"){
        actionRow.append(button(
          f.can_survey_now?"SCAN RF ENERGY BAND":"CHECK / SELECT RF BAND",
          ()=>openScanBand(f.band)));
        item.append(el("p","full-body","Band: "+f.band_label+
          " · Spectrum survey: "+(f.can_survey_now?"available if device is still free":"blocked by current dependencies")+
          " · Protocol decoder: not connected by this survey"));
      }else if(f.scan_type==="dvb_service_adapter_pending"){
        actionRow.append(button("VIEW DVB HARDWARE",()=>openPage(400,"",0)));
        item.append(el("p","full-body",
          "No DVB service scan is started until the TV/Radio Center resource lease, "+
          "channel database and actual Teletext PID decoder are integrated."));
      }else if(f.medium==="internet_only"){
        actionRow.append(button(f.can_decode_now?"OPEN CACHED FEEDS":"VIEW INTERNET SOURCES",
          ()=>openPage(f.can_decode_now?200:800,"",0)));
      }else if(f.medium==="local_archive"){
        actionRow.append(button("OPEN LOCAL ARCHIVE",
          ()=>openPage(f.id==="local_board"?600:700,"",0)));
      }else{
        actionRow.append(button("CHECK DEPENDENCIES",async()=>{
          try{
            const fresh=await api("/api/scans");
            const latest=fresh.features.find(x=>x.id===f.id);
            if(latest)description.textContent=latest.reason;
            notice("Dependencies rechecked; unsupported functions remain disabled.");
          }catch(error){notice(error.message)}
        }));
      }
      item.append(actionRow);
      $("content").append(item);
    });
  });
  $("section-count").textContent=features.length+" protocols mapped to appropriate scanning or caching";
}
function showAbout(){
  section("SYSTEM","How this terminal works","Build 0.3");
  const notes=[
    ["Offline first","All imported pages, notes and saved RSS text persist in a local SQLite database."],
    ["No silent network traffic","Feeds only refresh when you choose Refresh. No auto-scanning, tuner access, telemetry or AI."],
    ["Honest provenance","Actual radio/DVB content requires an external decoder and explicit JSON import, with source and receiver timestamp."],
    ["Network boundaries","Loopback service only. For phone access, configure an authenticated, TLS-enabled Survival Kit gateway."],
    ["Radio messages","The local board cannot transmit over APRS, packet radio, Meshtastic or any other RF network."]
  ];
  notes.forEach(([t,d])=>$("content").append(card(t,d,"DESIGN RULE")));
}
function bindNavigation(){
  const recheck=$("receiver-recheck");
  if(recheck) recheck.addEventListener("click",async()=>{
    recheck.disabled=true;
    try {
      await refreshReceiverStatus();
      notice("USB status refreshed. No receiver opened or retuned.");
    } catch (err) {
      notice("USB status check failed: "+err.message);
    } finally {
      recheck.disabled=false;
    }
  });
  document.querySelectorAll("[data-page]").forEach((n)=>n.addEventListener("click",()=>openPage(Number(n.dataset.page),"",0)));
  $("page-form").addEventListener("submit",(ev)=>{ev.preventDefault();openPage(Number($("page-number").value),$("source-select").value,Number($("subpage-number").value))});
  $("bookmark-page").addEventListener("click",()=>saveBookmark("Page "+state.page+(state.source?" · "+state.source:""),"page",state.page+":"+state.subpage+":"+state.source).catch((err)=>notice(err.message)));
  window.addEventListener("pagehide",()=>{
    stopManagedDabPolling();
    if(state.managedDabOwned){
      fetch("/api/dab/manage/stop",{
        method:"POST",keepalive:true,
        headers:{"Content-Type":"application/json","X-Tihulu-CSRF":state.csrf},
        body:JSON.stringify({owner:state.clientId,owner_only:true})
      }).catch(()=>{});
    }
    if(state.tvActive){
      fetch("/api/live/tv/stop",{
        method:"POST",headers:{"Content-Type":"application/json","X-Tihulu-CSRF":state.csrf},
        body:"{}",keepalive:true
      }).catch(()=>{});
    }
    if(state.liveActive){
      fetch("/api/live/radio/stop",{
        method:"POST",headers:{"Content-Type":"application/json","X-Tihulu-CSRF":state.csrf},
        body:"{}",keepalive:true
      }).catch(()=>{});
    }
    if(state.audioActive){
      fetch("/api/audio/stop",{
        method:"POST",headers:{"Content-Type":"application/json","X-Tihulu-CSRF":state.csrf},
        body:"{}",keepalive:true
      }).catch(()=>{});
    }
    if(state.scanActive){
      fetch("/api/scans/stop",{
        method:"POST",headers:{"Content-Type":"application/json","X-Tihulu-CSRF":state.csrf},
        body:"{}",keepalive:true
      }).catch(()=>{});
    }
    if(state.rdsActive){
      fetch("/api/rds/stop",{
        method:"POST",headers:{"Content-Type":"application/json","X-Tihulu-CSRF":state.csrf},
        body:"{}",keepalive:true
      }).catch(()=>{});
    }
  });
  document.addEventListener("keydown",(ev)=>{
    if(ev.key.toLowerCase()==="g" && !["INPUT","TEXTAREA","SELECT"].includes(document.activeElement.tagName)){
      ev.preventDefault();$("page-number").focus();$("page-number").select();
    }
  });
}
async function start(){
  bindNavigation();
  bindMediaDock();
  const now=new Date();
  $("clock").textContent=now.toLocaleTimeString([],{hour:"2-digit",minute:"2-digit"});
  try{await refreshCounts();await refreshSourceChoices();await openPage(100,"",0)}
  catch(err){notice("Local content failed to load: "+err.message);$("teletext-body").textContent="Local API unavailable. Check the server and reload."}
  try{await refreshReceiverStatus()}
  catch(err){notice("USB status could not be checked: "+err.message)}
}
start();
