/* Static, hardware-free regression for GitHub Pages and native bundled browser.
 * Does not weaken the separate 31-asset published-gh-pages parity workflow.
 */
import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync,existsSync} from "node:fs";
import {dirname,join,resolve} from "node:path";
import {fileURLToPath} from "node:url";
const root=dirname(fileURLToPath(import.meta.url));
const read=name=>readFileSync(join(root,name),"utf8");

test("four top-level sections link only to real bundled pages or anchors",()=>{
 const index=read("index.html"),images=read("reception.html");
 for(const html of [index,images]){
   for(const id of ["receiver","images","earth","analysis"])
     assert.match(html,new RegExp('data-shell-section="'+id+'"'));
   assert.match(html,/id="ui-language"/);
   assert.match(html,/web_shell\.mjs/);
   assert.match(html,/web_pwa\.mjs/);
 }
 for(const id of ["auto-workflow","satellite-tracking-maps","iq-analysis","satellite-images"])
   assert.ok(index.includes('id="'+id+'"'),"Missing deep-link anchor "+id);
 assert.ok(images.includes('id="auto-mission-center"'));
 assert.ok(existsSync(join(root,"reception.html")));
 assert.ok(existsSync(join(root,"index.html")));
});
test("three steps, WAV/CU8 independent controls and progress stay in both web views",()=>{
 const index=read("index.html"),images=read("reception.html");
 for(const key of ["step1","step2","step3"])
   assert.ok(index.includes('data-shell-text="'+key+'"')&&images.includes('data-shell-text="'+key+'"'));
 for(const id of ["auto-save-wav","auto-save-raw","wav-record","record","web-capture-progress"])
   assert.ok(index.includes('id="'+id+'"'),"Missing WebUSB choice "+id);
 for(const id of ["reception-auto-raw","reception-auto-wav"])
   assert.ok(images.includes('id="'+id+'"'));
});
test("all same-origin ESM static imports in the entrypoints resolve to real files",()=>{
 for(const entry of ["browser.js","reception.mjs","web_shell.mjs","web_pwa.mjs"]){
   const code=read(entry);
   const relative=[...code.matchAll(/(?:from\s*|import\s*\()\s*['"]([.][^'"]+)['"]/g)]
     .map(match=>match[1].split("?")[0]);
   for(const sub of relative){
     const target=resolve(root,sub);
     assert.ok(target.startsWith(root),"Import escapes browser root: "+sub);
     assert.ok(existsSync(target),entry+" has missing import "+sub);
   }
 }
});
test("offline shell assets exist; service worker never caches RF payloads or invokes WebUSB",()=>{
 const sw=read("satellite-sw.js");
 for(const entry of ["index.html","reception.html","browser.css","reception.css",
  "browser.js","reception.mjs","web_shell.mjs","web_pwa.mjs","webusb_lifecycle.mjs",
  "manifest.webmanifest","icon.svg","icon-192.png"]){
   assert.ok(existsSync(join(root,entry)), "Missing app-shell asset "+entry);
 }
 assert.match(sw,/request\.method!=="GET"/);
 assert.match(sw,/url\.origin!==scope\.origin/);
 assert.match(sw,/cu8\|wav\|iq\|bin\|zip/);
 assert.doesNotMatch(sw,/requestDevice\s*\(/);
 assert.doesNotMatch(sw,/readSamples\s*\(/);
 const manifest=JSON.parse(read("manifest.webmanifest"));
 assert.equal(manifest.display,"standalone");
 assert.equal(manifest.scope,"./");
 assert.ok(manifest.icons.every(icon=>existsSync(join(root,icon.src))));
});
test("responsive desktop/tablet/mobile CSS includes nav, maps and reduced motion",()=>{
 const css=read("browser.css");
 for(const term of [".shell-main-nav",".shell-module-grid",".web-capture-progress",
   "max-width:1100px","max-width:760px","max-width:480px","prefers-reduced-motion"])
   assert.ok(css.includes(term),term);
 for(const section of ["satellite-tracking-maps","iq-analysis"])
   assert.ok(css.includes(section),"Missing scroll-target style "+section);
});
