/* Offline-first PWA shell. Never cache OSM tiles, USB samples, personal location or imported measurements.
 * The pinned satellite.js library is cached solely for local orbital predictions; RF is not involved.
 */
const CACHE="tihulu-geolocation-shell-v6";
const ORBITAL_LIB="https://esm.sh/satellite.js@6.0.1?bundle";
const SHELL=["./","./index.html","./web/app.mjs","./web/auto_explorer.mjs","./web/usb_sdr.mjs",
 "./web/style.css","./web/icon.svg","./core/gnss.mjs","./core/positioning.mjs",
 "./core/evidence.mjs","./core/location_layers.mjs","./manifest.webmanifest"];
self.addEventListener("install",event=>{
 event.waitUntil(caches.open(CACHE).then(async cache=>{
   await cache.addAll(SHELL);
   // Best-effort optional library cache; failure must not break offline PWA install.
   await cache.add(ORBITAL_LIB).catch(()=>{});
 }));
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
 if(request.method!=="GET")return;
 const local=url.origin===self.location.origin&&SHELL.some(path=>new URL(path,self.registration.scope).pathname===url.pathname);
 const library=url.origin==="https://esm.sh"&&url.pathname.startsWith("/satellite.js@6.0.1");
 if(!local&&!library)return;
 event.respondWith(fetch(request).then(response=>{
   if(response.ok){
     const copy=response.clone();
     caches.open(CACHE).then(cache=>cache.put(request,copy)).catch(()=>{});
   }
   return response;
 }).catch(()=>caches.match(request)));
});