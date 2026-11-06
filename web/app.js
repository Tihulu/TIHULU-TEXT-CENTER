/* TIHULU TEXT CENTER — no external libraries, no background timers fetching data. */
"use strict";

const state = { csrf:"", page:100, subpage:0, source:"", entries:[], pages:[], receivers:null, rdsActive:false, rdsPollTimer:null };
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
async function showIndex(){
  section("START HERE","Explore the center","8 primary sections");
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
  const buttons=el("div","card-actions");buttons.append(start,stop);
  append(form,frequency.wrap,duration,consent,buttons);
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
        frequency_mhz:Number(frequency.input.value),duration_seconds:Number(seconds.value)
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
async function showRadioData(){
  section("RECEIVER / INPUT","Radio & TV text archive","Receive-only imports");
  try { $("content").append(receiverCard(await refreshReceiverStatus())); }
  catch(error){empty("Receiver detection unavailable","The local USB inventory could not be read: "+error.message)}
  try {await addRdsControl()}
  catch(error){empty("FM capture control unavailable","Unable to load RDS status: "+error.message)}
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
  section("TEXT NETWORKS","Explore the small web","External sites require internet");
  const entries=await api("/api/directory");
  entries.forEach((d)=>{
    const n=card(d.name,d.note,d.category.toUpperCase());
    const link=el("a","","OPEN EXTERNAL SITE ↗");link.href=d.url;link.target="_blank";link.rel="noopener noreferrer";
    const actions=el("div","card-actions");actions.append(link);n.append(actions);$("content").append(n);
  });
}
async function showCapabilities(){
  section("PROTOCOL COVERAGE","Full text & data service catalog","Verified / import / planned");
  const catalog=await api("/api/capabilities");
  const groups=[...new Set(catalog.map(x=>x.group))];
  const intro=el("article","notice-card");
  append(intro,el("h3","","Capabilities are not active reception"),
        el("p","","Installed decoders, a USB ID and a local archive do not prove a live broadcast. "+
          "All planned modules remain visible; no feature silently disappears, and official alerts require trusted verification."));
  $("content").append(intro);
  groups.forEach(group=>{
    const title=el("h3","protocol-group",group);$("content").append(title);
    catalog.filter(x=>x.group===group).forEach(feature=>{
      const display=feature.state.replaceAll("_"," ").toUpperCase();
      const item=card(feature.title,feature.purpose,display);
      item.append(el("p","full-body","Requires: "+feature.requirements));
      const status=feature.dependency_status||null;
      if(status) item.append(el("p","full-body",Object.entries(status).map(([k,v])=>
        k.replaceAll("_"," ")+": "+(v?"yes":"no")).join(" · ")));
      $("content").append(item);
    });
  });
  $("section-count").textContent=catalog.length+" features tracked";
}
function showAbout(){
  section("SYSTEM","How this terminal works","Build 0.1");
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
  const now=new Date();
  $("clock").textContent=now.toLocaleTimeString([],{hour:"2-digit",minute:"2-digit"});
  try{await refreshCounts();await refreshSourceChoices();await openPage(100,"",0)}
  catch(err){notice("Local content failed to load: "+err.message);$("teletext-body").textContent="Local API unavailable. Check the server and reload."}
  try{await refreshReceiverStatus()}
  catch(err){notice("USB status could not be checked: "+err.message)}
}
start();
