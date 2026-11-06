/* Offline-first static shell; network-first to prevent outdated maps and USB controls.
 * Never cache OSM tiles, public orbital catalogs or private imported observations.
 */
const CACHE="tihulu-geolocation-shell-v3";
const SHELL=["./","./index.html","./web/app.mjs","./web/auto_explorer.mjs","./web/usb_sdr.mjs",
 "./web/style.css","./web/icon.svg","./core/gnss.mjs","./core/positioning.mjs","./manifest.webmanifest"];
self.addEventListener("install",event=>{
 event.waitUntil(caches.open(CACHE).then(c=>c.addAll(SHELL)));
 self.skipWaiting();
});
self.addEventListener("activate",event=>{
 event.waitUntil(caches.keys().then(async names=>{
  for(const name of names)if(name.startsWith("tihulu-geolocation-shell-")&&name!==CACHE)await caches.delete(name);
  await self.clients.claim();
 }));
});
self.addEventListener("fetch",event=>{
 const request=event.request,url=new URL(request.url);
 if(request.method!=="GET"||url.origin!==self.location.origin)return;
 if(!SHELL.some(path=>new URL(path,self.registration.scope).pathname===url.pathname))return;
 event.respondWith(fetch(request).then(response=>{
   if(response.ok){
     const copy=response.clone();
     caches.open(CACHE).then(cache=>cache.put(request,copy)).catch(()=>{});
   }
   return response;
 }).catch(()=>caches.match(request)));
});
