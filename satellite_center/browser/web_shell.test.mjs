import test from "node:test";
import assert from "node:assert/strict";
import {SECTIONS,UI_TEXT,supportedLocale,activeSection,sectionHref,applyShell} from "./web_shell.mjs";

test("the four sections have stable unique relative links",()=>{
 assert.equal(SECTIONS.length,4);
 assert.equal(new Set(SECTIONS.map(x=>x.id)).size,4);
 assert.deepEqual(SECTIONS.map(x=>x.id),["receiver","images","earth","analysis"]);
 assert.equal(sectionHref("images"),"./reception.html");
 assert.equal(sectionHref("earth"),"./index.html#satellite-tracking-maps");
 assert.equal(sectionHref("analysis"),"./index.html#iq-analysis");
});
test("deep links and sibling pages retain the right active section",()=>{
 assert.equal(activeSection("/project/satellite_center/browser/index.html","#iq-analysis"),"analysis");
 assert.equal(activeSection("/project/satellite_center/browser/","#satellite-tracking-maps"),"earth");
 assert.equal(activeSection("/project/satellite_center/browser/reception.html","#auto-mission-center"),"images");
 assert.equal(activeSection("/project/satellite_center/browser/index.html",""),"receiver");
});
test("English is default; Turkish and German have core nav, workflow and receiver strings",()=>{
 assert.equal(supportedLocale(null),"en");
 assert.equal(supportedLocale("es"),"en");
 for(const language of ["en","tr","de"]){
  assert.equal(supportedLocale(language),language);
  for(const section of SECTIONS)
   assert.ok(UI_TEXT[language][section.label],language+"/"+section.label);
  for(const key of ["step1","step2","step3","connect","disconnect","stop","capture"])
   assert.ok(UI_TEXT[language][key],language+"/"+key);
 }
});
test("language preference and active nav update without a DOM runtime dependency",()=>{
 const elements=new Map();
 const links=SECTIONS.map(section=>({
   attrs:new Map([["data-shell-section",section.id],["data-shell-text",section.label]]),
   textContent:"",classList:{add(){},remove(){}},
   getAttribute(name){return this.attrs.get(name)},
   setAttribute(name,value){this.attrs.set(name,value)},
   removeAttribute(name){this.attrs.delete(name)}
 }));
 const picker={value:"en",handlers:{},addEventListener(type,fn){this.handlers[type]=fn}};
 const heading={textContent:"",getAttribute(){return "stepTitle"}};
 const doc={
  documentElement:{lang:"en"},
  getElementById(id){return id==="ui-language"?picker:null},
  querySelectorAll(selector){
   return selector==="[data-shell-text]"?[...links,heading]:selector==="a[data-shell-section]"?links:[];
  }
 };
 let stored="de",onHash;
 const storage={getItem(){return stored},setItem(key,value){stored=value}};
 const win={localStorage:storage,location:{pathname:"/reception.html",hash:""},
  addEventListener(kind,fn){if(kind==="hashchange")onHash=fn;}};
 const shell=applyShell(doc,win);
 assert.equal(shell.initial,"de");
 assert.equal(heading.textContent,UI_TEXT.de.stepTitle);
 assert.equal(doc.documentElement.lang,"de");
 assert.equal(links[1].attrs.get("aria-current"),"page");
 picker.value="tr";picker.handlers.change();
 assert.equal(stored,"tr");
 assert.equal(doc.documentElement.lang,"tr");
 win.location.pathname="/index.html";win.location.hash="#iq-analysis";onHash();
 assert.equal(links[3].attrs.get("aria-current"),"page");
 assert.equal(links[1].attrs.has("aria-current"),false);
});
