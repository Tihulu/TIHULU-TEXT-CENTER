/* PWA is an offline read-only shell, not a background RF worker. */
export function shouldRegisterPwa(location){
  const protocol=location?.protocol||"";
  return protocol==="https:"||
    (protocol==="http:"&&["localhost","127.0.0.1"].includes(location?.hostname));
}
export async function registerSatellitePwa(nav,location,feedback=()=>{}){
  if(!shouldRegisterPwa(location)||!nav?.serviceWorker?.register){
    feedback("PWA unavailable on this origin; browser planner remains usable.");
    return null;
  }
  try{
    const registration=await nav.serviceWorker.register("./satellite-sw.js",{scope:"./"});
    feedback("Web app shell available; installed offline pages may have cached assets. USB never runs in a service worker.");
    return registration;
  }catch(error){
    feedback("Offline install cache unavailable: "+String(error?.message||error)+". WebUSB and planning can still be used online.");
    return null;
  }
}
