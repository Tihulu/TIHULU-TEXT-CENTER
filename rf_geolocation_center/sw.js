/* Same-origin offline app shell only; NEVER cache remote OSM tiles or GNSS private imports. */
const CACHE="tihulu-geolocation-shell-v1";
const SHELL=["./","./index.html","./web/app.mjs","./web/style.css","./web/icon.svg",
 "./core/gnss.mjs","./core/positioning.mjs","./manifest.webmanifest"];
self.addEventListener("install",event=>{
 event.waitUntil(caches.open(CACHE).then(c=>c.addAll(SHELL)));
 self.skipWaiting();
});
self.addEventListener("activate",event=>{
 event.waitUntil(caches.keys().then(async names=>{
  for(const n of names)if(n.startsWith("tihulu-geolocation-")&&n!==CACHE)await caches.delete(n);
  await self.clients.claim();
 }));
});
self.addEventListener("fetch",event=>{
 const req=event.request,url=new URL(req.url);
 if(req.method!=="GET"||url.origin!==self.location.origin)return;
 if(!SHELL.some(s=>new URL(s,self.registration.scope).pathname===url.pathname))return;
 event.respondWith(caches.match(req).then(hit=>hit||fetch(req)));
});
