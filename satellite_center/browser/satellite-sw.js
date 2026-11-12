/* TIHULU Satellite WebUSB Edition cache. Never open hardware or background jobs.
 * Relative scope preserves GitHub Pages project paths and native subdirectories.
 * No remote provider URLs, private IQ/WAV, SDR APIs, or /api/ are cached.
 */
const VERSION="satellite-webusb-shell-20261112-v1";
const CORE=[
  "./index.html","./reception.html","./browser.css","./reception.css",
  "./browser.js","./reception.mjs","./web_shell.mjs","./web_pwa.mjs",
  "./webusb_lifecycle.mjs","./manifest.webmanifest","./icon.svg","./icon-192.png"
];
self.addEventListener("install",event=>{
  event.waitUntil((async()=>{
    const cache=await caches.open(VERSION);
    // Cache individually: an optional icon/asset failure must not take the
    // entire offline shell offline. Review missing assets in asset QA.
    await Promise.all(CORE.map(async path=>{
      try{await cache.add(new Request(new URL(path,self.registration.scope),{cache:"reload"}));}
      catch(error){ /* Optional asset: network fallback when next online. */ }
    }));
    await self.skipWaiting();
  })());
});
self.addEventListener("activate",event=>{
  event.waitUntil((async()=>{
    for(const name of await caches.keys())
      if(name.startsWith("satellite-webusb-shell-")&&name!==VERSION)
        await caches.delete(name);
    await self.clients.claim();
  })());
});
self.addEventListener("fetch",event=>{
  const request=event.request;
  if(request.method!=="GET")return;
  const url=new URL(request.url);
  const scope=new URL(self.registration.scope);
  if(url.origin!==scope.origin||!url.pathname.startsWith(scope.pathname))return;
  if(url.pathname.includes("/api/"))return;
  // Never cache RF payloads or provider responses, even by accident.
  if(/\.(?:cu8|wav|iq|bin|zip)$/i.test(url.pathname))return;
  const address=new URL(url.pathname,scope.origin).href;
  event.respondWith((async()=>{
    const cache=await caches.open(VERSION);
    if(request.mode==="navigate"){
      try{
        const response=await fetch(request);
        if(response.ok)await cache.put(address,response.clone());
        return response;
      }catch{
        return await cache.match(address)||await cache.match(new URL("./index.html",scope).href)||
          Response.error();
      }
    }
    const saved=await cache.match(address);
    if(saved)return saved;
    try{
      const response=await fetch(request);
      if(response.ok&&response.type==="basic")await cache.put(address,response.clone());
      return response;
    }catch{
      return Response.error();
    }
  })());
});
