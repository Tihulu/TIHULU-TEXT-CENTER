/* Provenance-safe Earth imagery catalog. Online photos are not RF detections. */
export const IMAGE_TARGETS=Object.freeze([
 {key:"iss",name:"ISS (ZARYA)",kind:"SSTV",frequencies:[437550000,145800000],
  details:"ARISS SSTV is intermittent; October 2026 events used 437.550 MHz Robot36. Confirm the current dated ARISS event before recording.",
  statusUrl:"https://www.ariss.org/upcoming-sstv-events.html",mode:"Robot36 (event-dependent)",
  reception:"SSTV audio needs FM demodulation and an SSTV decoder. Raw CU8 is not a JPEG."},
 {key:"meteor3",name:"METEOR-M2-3",kind:"LRPT",frequencies:[137900000,137100000],
  details:"Meteor LRPT may use 137.9 or 137.1 MHz; check current transmissions and pass before recording.",
  statusUrl:"https://www.satdump.org/",mode:"Meteor M2-x LRPT 72k/80k",
  reception:"Needs QPSK demodulation, error correction and image assembly (SatDump)."},
 {key:"meteor4",name:"METEOR-M2-4",kind:"LRPT",frequencies:[137900000,137100000],
  details:"Meteor LRPT may use 137.9 or 137.1 MHz; actual radio availability is not guaranteed by TLE.",
  statusUrl:"https://www.satdump.org/",mode:"Meteor M2-x LRPT 72k/80k",
  reception:"Needs QPSK demodulation, error correction and image assembly (SatDump)."}
]);
export function safeSatelliteName(value){
 const result=String(value||"UNKNOWN").normalize("NFKD")
  .replace(/[\u0300-\u036f]/g,"").toUpperCase()
  .replace(/[^A-Z0-9]+/g,"-").replace(/^-+|-+$/g,"").slice(0,44);
 return result||"UNKNOWN";
}
export function isoUtcCompact(value=new Date()){
 const date=value instanceof Date?value:new Date(value);
 if(!Number.isFinite(date.getTime()))throw Error("Invalid UTC timestamp");
 return date.toISOString().replace(/[-:]/g,"").replace(/\.\d{3}Z$/,"Z");
}
export function recordingName({satellite,at=new Date(),frequencyHz,format="cu8",kind="IQ"}={}){
 const freq=Number(frequencyHz);
 if(!Number.isFinite(freq)||freq<0)throw Error("Invalid capture frequency");
 const ext=String(format).toLowerCase();
 if(!["cu8","wav","png","jpg","jpeg","json","txt"].includes(ext))throw Error("Unsupported extension");
 return "TIHULU_"+safeSatelliteName(satellite)+"_"+isoUtcCompact(at)+"_"+
   Math.round(freq)+"Hz_"+safeSatelliteName(kind)+"."+ext;
}
export function parseRecordingName(name){
 const m=String(name||"").match(/^TIHULU_([A-Z0-9-]+)_(\d{8}T\d{6}Z)_(\d{1,11})Hz_([A-Z0-9-]+)\.(cu8|wav|png|jpg|jpeg|json|txt)$/i);
 if(!m)return null;
 const v=m[2],timestamp=new Date(v.slice(0,4)+"-"+v.slice(4,6)+"-"+v.slice(6,8)+"T"+
   v.slice(9,11)+":"+v.slice(11,13)+":"+v.slice(13,15)+"Z");
 if(!Number.isFinite(timestamp.getTime())||isoUtcCompact(timestamp)!==v)return null;
 return {satellite:m[1],timestamp:timestamp.toISOString(),frequencyHz:Number(m[3]),
   kind:m[4],format:m[5].toLowerCase()};
}
export function epicImageUrl(entry,variant="jpg"){
 if(!entry||typeof entry.image!=="string"||!/^[a-z0-9_-]+$/i.test(entry.image))
  throw Error("Invalid NASA EPIC image ID");
 const timestamp=String(entry.date||"");
 if(!/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/.test(timestamp))throw Error("Invalid EPIC observation time");
 const [y,m,d]=timestamp.slice(0,10).split("-");
 const ext=variant==="png"?"png":"jpg";
 return "https://api.nasa.gov/EPIC/archive/natural/"+y+"/"+m+"/"+d+"/"+ext+
   "/"+entry.image+"."+ext+"?api_key=DEMO_KEY";
}
export function epicEntries(payload){
 if(!Array.isArray(payload))throw Error("NASA EPIC returned no valid image catalog");
 return payload.filter(e=>e&&typeof e.image==="string"&&/^[a-z0-9_-]+$/i.test(e.image)&&
   /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/.test(e.date)).slice(0,16).map(e=>({
   source:"NASA DSCOVR EPIC (online archive, NOT this RTL-SDR)",
   satellite:"DSCOVR-EPIC",timestamp:e.date+" UTC",imageId:e.image,
   caption:String(e.caption||"Earth full-disk natural color image").slice(0,400),
   imageUrl:epicImageUrl(e,"jpg"),archiveUrl:epicImageUrl(e,"png")
 }));
}
export function nasaIssEntries(payload){
 const records=payload?.collection?.items;
 if(!Array.isArray(records))throw Error("NASA image library search did not return items");
 return records.filter(it=>it?.data?.[0]?.media_type==="image"&&
  typeof it?.links?.[0]?.href==="string"&&
  /^https:\/\/(?:images\.nasa\.gov|images-assets\.nasa\.gov|images-api\.nasa\.gov)\//.test(it.links[0].href))
 .slice(0,12).map(it=>{
   const d=it.data[0];
   return {source:"NASA Image and Video Library (historical/archive, not live RF)",
    satellite:"ISS-ARCHIVE",timestamp:String(d.date_created||"date not reported"),
    caption:String(d.title||"ISS Earth photograph").slice(0,300),imageUrl:it.links[0].href,
    archiveUrl:typeof d.nasa_id==="string"?
      "https://images.nasa.gov/details-"+encodeURIComponent(d.nasa_id):"https://images.nasa.gov/"};
 });
}
