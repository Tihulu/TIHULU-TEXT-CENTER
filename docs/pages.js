"use strict";
const views=["home","radio","tv","translate","radar","notes","setup"];
const title={
  home:["Information, without the noise.","Offline-first radio, television, text and aircraft information"],
  radio:["Live radio & metadata","Real RF only, using your local receiver"],
  tv:["Live digital television","A genuine authorized local DVB stream is required"],
  translate:["Translation & captions","Original audio, source language and installed offline models"],
  radar:["Flight Radar & tar1090","Real antenna, Internet and hybrid observations kept distinct"],
  notes:["Offline notebook","This browser profile only — never claimed as received broadcast data"],
  setup:["Install a local companion","Keep USB decoder and recordings on your own computer"]
};
const branch="integration/unified-text-center-pages-desktop-radar-2026-11-06";
function show(view){
  if(!views.includes(view))view="home";
  document.querySelectorAll(".view").forEach(x=>x.hidden=x.id!=="view-"+view);
  document.querySelectorAll("[data-view]").forEach(x=>x.classList.toggle("active",x.dataset.view===view));
  document.getElementById("view-title").textContent=title[view][0];
  document.getElementById("view-subtitle").textContent=title[view][1];
  location.hash=view;
  if(view==="notes")renderNotes();
}
document.querySelectorAll("[data-view]").forEach(x=>x.addEventListener("click",()=>show(x.dataset.view)));
window.addEventListener("hashchange",()=>{
  const view=location.hash.replace("#","");
  if(views.includes(view)&&!document.getElementById("view-"+view).hidden) return;
  show(view);
});
function readNotes(){
  try{
    const arr=JSON.parse(localStorage.getItem("tihulu-pages-notes-v1")||"[]");
    return Array.isArray(arr)?arr.slice(0,50).filter(n=>n&&typeof n.title==="string"&&typeof n.body==="string"):[];
  }catch(_){return []}
}
function writeNotes(notes){
  try{localStorage.setItem("tihulu-pages-notes-v1",JSON.stringify(notes.slice(0,50)));return true}
  catch(_){return false}
}
function renderNotes(){
  const container=document.getElementById("note-list");
  container.replaceChildren();
  const all=readNotes();
  if(!all.length){
    const empty=document.createElement("p");
    empty.textContent="No browser-only notes saved yet.";
    container.append(empty);return;
  }
  all.forEach((n,i)=>{
    const div=document.createElement("article");div.className="note";
    const strong=document.createElement("strong");strong.textContent=n.title;
    const meta=document.createElement("span");meta.textContent="LOCAL NOTE / "+n.saved;
    const body=document.createElement("p");body.textContent=n.body;
    const remove=document.createElement("button");remove.textContent="DELETE NOTE";remove.type="button";
    remove.addEventListener("click",()=>{
      const updated=readNotes();updated.splice(i,1);
      if(writeNotes(updated))renderNotes();
    });
    div.append(strong,meta,body,remove);container.append(div);
  });
}
document.getElementById("save-note").addEventListener("click",()=>{
  const t=document.getElementById("note-title"),b=document.getElementById("note-body");
  if(!t.value.trim()||!b.value.trim())return window.alert("Add a title and note first.");
  const notes=readNotes();
  notes.unshift({title:t.value.trim().slice(0,80),body:b.value.trim().slice(0,6000),
    saved:new Date().toLocaleString()});
  if(!writeNotes(notes))return window.alert("Browser storage unavailable; nothing was saved.");
  t.value="";b.value="";renderNotes();
});
document.getElementById("clear-note").addEventListener("click",()=>{
  document.getElementById("note-title").value="";
  document.getElementById("note-body").value="";
});
const raw="https://raw.githubusercontent.com/Tihulu/TIHULU-TEXT-CENTER/"+branch;
document.getElementById("unix-command").textContent=
  "curl -fsSL '"+raw+"/scripts/bootstrap-unix.sh' | bash -s -- '"+branch+"'";
document.getElementById("windows-command").textContent=
  "$env:TIHULU_TEXT_BRANCH='"+branch+"'; irm '"+raw+"/scripts/install-windows.ps1' | iex";
document.querySelectorAll("[data-copy]").forEach(button=>button.addEventListener("click",async()=>{
  const text=document.getElementById(button.dataset.copy).textContent;
  try{await navigator.clipboard.writeText(text);button.textContent="COPIED";}
  catch(_){button.textContent="SELECT AND COPY COMMAND MANUALLY";}
}));
const network=document.getElementById("network-status");
function updateNetwork(){
  network.textContent=navigator.onLine?
    "Browser reports network available · receiver not checked":
    "Browser reports offline · local notes remain readable";
}
window.addEventListener("online",updateNetwork);
window.addEventListener("offline",updateNetwork);
updateNetwork();
document.getElementById("clock").textContent=new Date().toLocaleString();
show(location.hash.replace("#","")||"home");
if("serviceWorker" in navigator && location.protocol==="https:"){
  navigator.serviceWorker.register("./sw.js").catch(()=>{});
}
