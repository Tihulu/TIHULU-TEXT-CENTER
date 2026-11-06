/* TIHULU TEXT CENTER — no external libraries, no background timers fetching data. */
"use strict";

const state = { csrf:"", page:100, subpage:0, source:"", entries:[], pages:[] };
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
async function api(path, method, payload){
  const options = {method:method || "GET", headers:{"Accept":"application/json"}};
  if(method === "POST") {
    options.headers["Content-Type"]="application/json";
    options.headers["X-Tihulu-CSRF"]=state.csrf;
    options.body=JSON.stringify(payload);
  }
  const response=await fetch(path,options);
  const data=await response.json();
  if(!response.ok) throw new Error(data.error || "Request failed ("+response.status+")");
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
}
async function refreshCounts(){
  const d=await api("/api/bootstrap");
  state.csrf=d.csrf;
  [["articles","stat-articles"],["pages","stat-pages"],["events","stat-events"],["bulletins","stat-posts"]].forEach(([key,id])=>{$(id).textContent=d.counts[key]});
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
    return showAbout();
  } catch(err) {
    section("NOT FOUND","No page available");
    empty("Page unavailable",err.message+" — No content will be invented.");
    notice(err.message);
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
async function showRadioData(){
  section("RECEIVER / INPUT","Radio & TV text archive","Receive-only imports");
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
  document.querySelectorAll("[data-page]").forEach((n)=>n.addEventListener("click",()=>openPage(Number(n.dataset.page),"",0)));
  $("page-form").addEventListener("submit",(ev)=>{ev.preventDefault();openPage(Number($("page-number").value),$("source-select").value,Number($("subpage-number").value))});
  $("bookmark-page").addEventListener("click",()=>saveBookmark("Page "+state.page+(state.source?" · "+state.source:""),"page",state.page+":"+state.subpage+":"+state.source).catch((err)=>notice(err.message)));
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
  catch(err){notice("Local service unavailable: "+err.message);$("teletext-body").textContent="Unable to reach the local application server."}
}
start();
