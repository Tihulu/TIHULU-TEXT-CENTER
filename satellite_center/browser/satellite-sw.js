/* Satellite Center WebUSB web/PWA shell — RELEASE CACHE, never RF.
 * A worker has NO hardware lease and must never run recording/scheduling.
 * A missing script aborts installation; the old worker stays active.
 * Relative URLs preserve /TIHULU-TEXT-CENTER/satellite_center/browser/ on Pages.
 */
const VERSION="satellite-webusb-shell-20261112-v2";

/* Full static ESM dependency closure of the two page entrypoints plus UI.
 * A successful worker install means the HTML+JS feature shell can load offline;
 * CDN WebUSB driver, satellite.js, fresh TLE, tiles and RF are NOT offline.
 * Bump VERSION on every reviewed deployment changing any of these assets.
 */
const CRITICAL=[
 "./index.html","./reception.html","./browser.css","./reception.css",
 "./browser.js","./reception.mjs","./manifest.webmanifest",
 "./web_shell.mjs","./web_pwa.mjs","./webusb_lifecycle.mjs",
 "./usb_diagnostics.mjs","./usb_live_probe.mjs","./pass_sort.mjs",
 "./satellite_maps.mjs",
 "./pass_window.mjs","./pass_candidates.mjs","./orbit_clock.mjs",
 "./iq_analysis_ui.mjs","./iq_analysis.mjs","./iq_intelligence.mjs",
 "./satellite_images_ui.mjs","./satellite_imagery.mjs",
 "./location_search.mjs","./pass_protocol_catalog.mjs",
 "./saved_satellite_protocols.mjs","./auto_mission.mjs",
 "./satellite_calendar.mjs","./schedule_controller.mjs",
 "./chained_capture.mjs","./capture_duration.mjs","./fm_wav_record.mjs",
 "./reception_catalog.mjs","./file_format_inspector.mjs",
 "./auto_reception_ui.mjs","./user_protocol_ui.mjs",
 "./signal_discovery.mjs","./results_zip.mjs",
 "./compute_selector.mjs","./compute_backends.mjs",
 "./sstv_robot36.mjs","./sstv_capture_diagnostics.mjs",
 "./fm_iq_demod.mjs"
];
/* Optional geography, street-map renderer and app icons: never pretend
 * these were cached successfully if the network request failed. */
const OPTIONAL=[
 "./icon.svg","./icon-192.png","./icon-512.png",
 "./natural-earth-land-110m.geojson","./cities-de-tr.json",
 "./leaflet.js","./leaflet.css"
];
const CACHEABLE=new Set([...CRITICAL,...OPTIONAL]);
const cacheAddress=(path,scope)=>new URL(path,scope).href;

self.addEventListener("install",event=>{
 event.waitUntil((async()=>{
   const cache=await caches.open(VERSION);
   const scope=self.registration.scope;
   // Fail atomically on ANY missing entrypoint/ESM/CSS dependency. The previous
   // healthy service worker remains active; no false "offline-ready" shell.
   await Promise.all(CRITICAL.map(path=>
     cache.add(new Request(cacheAddress(path,scope),{cache:"reload"}))
   ));
   // A missing icon/street layer is an optional offline limitation.
   await Promise.all(OPTIONAL.map(async path=>{
     try{
       await cache.add(new Request(cacheAddress(path,scope),{cache:"reload"}));
     }catch{ /* optional asset: online fallback is permitted */ }
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
 // Only these known, reviewed application assets may be stored. Never cache
 // captured RF/IQ/WAV/images, decoder outputs, arbitrary JSON, or providers.
 if(/\.(?:cu8|wav|iq|bin|zip)$/i.test(url.pathname))return;
 const suffix=url.pathname.slice(scope.pathname.length)||"index.html";
 const relative="./"+suffix;
 if(!CACHEABLE.has(relative))return;
 const address=cacheAddress(relative,scope);

 event.respondWith((async()=>{
   const cache=await caches.open(VERSION);
   try{
     // NETWORK FIRST, bypassing browser HTTP cache on ALL reviewed app assets.
     // The old cache-first/path-only lookup ignored ?v= changes and could run
     // stale JS/CSS after an otherwise good Pages synchronization.
     const response=await fetch(request,{cache:"reload"});
     if(response.ok&&response.type!=="opaque")
       await cache.put(address,response.clone());
     // A real HTTP 404/500 is never hidden by an old cached success response.
     return response;
   }catch{
     // Offline only: normalize URL queries after network failed. A previously
     // cached exact asset (not some unrelated HTML) is the only fallback.
     return await cache.match(address)||Response.error();
   }
 })());
});
