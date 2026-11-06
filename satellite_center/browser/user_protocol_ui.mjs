/* Manual extension of the public RF reference library.
 * Never silently schedule, transmit, download or enable unknown decoders.
 */
import {PROFILE_KEY,parseUserProtocol,readUserProfiles,saveUserProfiles,
  validateUserProfiles} from "./saved_satellite_protocols.mjs";

export function initSavedProtocolUI(){
 const $=id=>document.getElementById(id);
 const form=$("user-protocol-form"),target=$("user-protocol-list"),status=$("user-protocol-status");
 if(!form||!target)return;
 const say=text=>{status.textContent=String(text);};
 function announce(){window.dispatchEvent(new Event("tihulu-profiles-changed"));}
 function download(blob,name){
   const url=URL.createObjectURL(blob),a=document.createElement("a");
   a.href=url;a.download=name;document.body.append(a);a.click();a.remove();
   setTimeout(()=>URL.revokeObjectURL(url),60000);
 }
 function render(){
   target.replaceChildren();
   const profiles=readUserProfiles();
   if(!profiles.length){
     const p=document.createElement("p");p.className="hint";
     p.textContent="No manually saved satellites. Curated ISS/Meteor profiles remain available without imports.";
     target.append(p);
     return;
   }
   for(const profile of profiles){
     const row=document.createElement("article");row.className="mission-detail";
     const heading=document.createElement("strong");
     heading.textContent="NORAD "+profile.norad+" · "+profile.kind.toUpperCase()+
       " · "+(profile.frequencyHz/1e6).toFixed(6)+" MHz";
     const p=document.createElement("p");
     p.textContent=profile.protocol+" · user-supplied; not independently verified; no automated decoder.";
     const source=document.createElement("a");
     source.href=profile.source;source.target="_blank";source.rel="noopener noreferrer";
     source.textContent="Saved reference";
     const edit=document.createElement("button");edit.type="button";edit.className="secondary";edit.textContent="Edit profile";
     edit.addEventListener("click",()=>{
       $("user-protocol-norad").value=String(profile.norad);
       $("user-protocol-frequency").value=String(profile.frequencyHz/1e6);
       $("user-protocol-kind").value=profile.kind;
       $("user-protocol-mode").value=profile.protocol;
       $("user-protocol-source").value=profile.source;
       form.scrollIntoView({behavior:"smooth",block:"nearest"});
       say("Editing an existing local reference. Saving will update matching satellite/frequency/type.");
     });
     const remove=document.createElement("button");remove.type="button";remove.className="secondary";remove.textContent="Remove";
     remove.addEventListener("click",()=>{
       try{
         saveUserProfiles(readUserProfiles().filter(p=>p.id!==profile.id));
         render();announce();say("Removed one manual profile; official reference data unaffected.");
       }catch(e){say("Could not remove: "+e.message);}
     });
     row.append(heading,p,source,document.createTextNode(" "),edit,document.createTextNode(" "),remove);
     target.append(row);
   }
 }
 form.addEventListener("submit",e=>{
   e.preventDefault();
   try{
     const profile=parseUserProtocol({
       norad:$("user-protocol-norad").value,
       frequencyHz:Math.round(Number($("user-protocol-frequency").value)*1e6),
       kind:$("user-protocol-kind").value,
       protocol:$("user-protocol-mode").value,
       source:$("user-protocol-source").value
     });
     const merged=readUserProfiles().filter(p=>p.id!==profile.id).concat(profile);
     saveUserProfiles(merged);render();announce();
     say("Saved locally. This is a MANUAL, UNVERIFIED RF reference, not an active satellite observation or installed decoder.");
   }catch(err){say("Profile not saved: "+err.message);}
 });
 $("user-protocol-export").addEventListener("click",()=>{
   const data=readUserProfiles();
   download(new Blob([JSON.stringify({schema:"tihulu-public-satellite-profiles-v1",
     source:"user-supplied-unverified",profiles:data},null,2)],{type:"application/json"}),
     "TIHULU_satellite_custom_downlinks.json");
   say("Exported "+data.length+" user-defined receiver profiles. No I/Q recordings exported.");
 });
 $("user-protocol-import").addEventListener("change",async()=>{
   const file=$("user-protocol-import").files?.[0];
   if(!file)return;
   try{
     if(file.size>40_000)throw Error("Import exceeds 40 kB limit");
     const raw=JSON.parse(await file.text());
     const rows=Array.isArray(raw)?raw:raw?.profiles;
     const incoming=validateUserProfiles(rows);
     const merged=validateUserProfiles([...readUserProfiles(),...incoming]);
     saveUserProfiles(merged);render();announce();
     say("Imported "+incoming.length+" user-supplied profile(s); none is automatically treated as a verified transmitter or decoder.");
   }catch(e){say("Import rejected: "+e.message);}
   finally{$("user-protocol-import").value="";}
 });
 window.addEventListener("storage",e=>{if(e.key===PROFILE_KEY)render();});
 render();
}
