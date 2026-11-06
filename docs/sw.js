"use strict";
const CACHE="tihulu-text-center-pages-2026-11";
const ASSETS=["./","./index.html","./pages.css","./pages.js","./pages-icon.svg","./manifest.webmanifest"];
self.addEventListener("install",event=>{
  event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(ASSETS)));
  self.skipWaiting();
});
self.addEventListener("activate",event=>{
  event.waitUntil(caches.keys().then(keys=>Promise.all(
    keys.filter(k=>k.startsWith("tihulu-text-center-pages-")&&k!==CACHE).map(k=>caches.delete(k)))));
  self.clients.claim();
});
self.addEventListener("fetch",event=>{
  const request=event.request;
  if(request.method!=="GET"||new URL(request.url).origin!==self.location.origin)return;
  const u=new URL(request.url);
  if(!u.pathname.startsWith(new URL(self.registration.scope).pathname))return;
  event.respondWith(caches.match(request).then(cached=>cached||
    fetch(request).then(response=>{
      if(response.ok && (request.destination==="document" ||
          request.destination==="script" ||request.destination==="style" ||
          request.destination==="image")){
        const copy=response.clone();
        caches.open(CACHE).then(cache=>cache.put(request,copy)).catch(()=>{});
      }
      return response;
    }).catch(()=>new Response("Offline cache unavailable",{status:503}))));
});
