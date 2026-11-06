/* Published receive-only downlink capabilities, not observed traffic.
 * Identity by NORAD number, never by substring name, RF peak or orbit alone.
 * Mission configuration is historical or status-dependent. Verify before RF.
 */
export const PUBLIC_DOWNLINKS=Object.freeze([
 Object.freeze({id:"iss-sstv-robot36",norad:25544,kind:"image",label:"SSTV image",
  protocol:"SSTV Robot36",frequencyHz:437550000,activity:"event-only",
  decoder:"browser-experimental",station:"ISS",source:"https://www.ariss.org/upcoming-sstv-events.html",
  note:"Only during announced Robot36 events; frequency, mode and schedule can change."}),
 Object.freeze({id:"iss-sstv-pd120",norad:25544,kind:"image",label:"SSTV image",
  protocol:"SSTV PD120 (historical event mode)",frequencyHz:145800000,activity:"historical-event",
  decoder:"external-only",station:"ISS",source:"https://www.ariss.org/upcoming-sstv-events.html",
  note:"Past ISS SSTV transmissions used PD120; current in-browser Robot36 decoder cannot decode PD120."}),
 Object.freeze({id:"iss-aprs-uhf",norad:25544,kind:"text",label:"Packet text",
  protocol:"APRS / AX.25 AFSK1200",frequencyHz:437825000,activity:"station-mode-dependent",
  decoder:"native-multimon-unverified-crc",station:"ISS",source:"https://www.ariss.org/current-status-of-iss-stations.html",
  note:"Requires a receiver and packet decoder; display actual decoded frames with CRC provenance separately."}),
 Object.freeze({id:"iss-voice-repeater",norad:25544,kind:"audio",label:"FM voice",
  protocol:"Amateur FM repeater",frequencyHz:437800000,activity:"station-mode-dependent",
  decoder:"native-or-browser-audio-candidate",station:"ISS",source:"https://www.ariss.org/current-status-of-iss-stations.html",
  note:"Repeater is not a continuous voice broadcast; listen only when active."}),
 Object.freeze({id:"iss-hamtv",norad:25544,kind:"video",label:"HamTV video",
  protocol:"S-band digital video",frequencyHz:2395000000,activity:"hardware-upgrade",
  decoder:"unsupported-hardware",station:"ISS",source:"https://www.ariss.org/current-status-of-iss-stations.html",
  note:"2395 MHz needs an S-band-capable receiver, not NESDR v5 or WinTV-soloHD."}),
 Object.freeze({id:"meteor-m2-3-lrpt",norad:57166,kind:"image",label:"Earth imagery",
  protocol:"Meteor LRPT 72k/80k (verify)",frequencyHz:137900000,activity:"verify-downlink",
  decoder:"native-satdump",station:"Meteor-M2-3",
  source:"https://github.com/SatDump/SatDump.Docs/blob/master/pipelines.rst",
  note:"Recorded CU8 requires working LRPT pipeline, suitable 137 MHz antenna and valid downlink."}),
 Object.freeze({id:"meteor-m2-4-lrpt",norad:59051,kind:"image",label:"Earth imagery",
  protocol:"Meteor LRPT 80k (verify)",frequencyHz:137900000,activity:"verify-downlink",
  decoder:"native-satdump",station:"Meteor-M2-4",
  source:"https://db.satnogs.org/",note:"Possible 137.900/137.9125 MHz transmitter; confirm active frequency and decoder."})
]);
export const CONTENT_KINDS=Object.freeze(["image","audio","text","video"]);
export function noradFromPass(pass){
 const number=pass?.norad??pass?.id;
 if(typeof number==="number" && Number.isInteger(number))return number;
 const digits=String(number??"").split(":")[0];
 return /^\d{4,7}$/.test(digits)?Number(digits):null;
}
export function protocolsForPass(pass){
 const id=noradFromPass(pass);
 return id===null?[]:PUBLIC_DOWNLINKS.filter(d=>d.norad===id);
}
export function protocolCategories(pass){
 return [...new Set(protocolsForPass(pass).map(d=>d.kind))].sort((a,b)=>CONTENT_KINDS.indexOf(a)-CONTENT_KINDS.indexOf(b));
}
export function passesFilteredByContent(passes,kind="all"){
 if(kind==="all")return passes;
 if(kind==="known")return passes.filter(p=>protocolCategories(p).length);
 if(!CONTENT_KINDS.includes(kind))throw Error("Unknown downlink content filter");
 return passes.filter(p=>protocolCategories(p).includes(kind));
}
export function protocolIsDecodableNow(protocol){
 return ["browser-experimental","native-satdump","native-or-browser-audio-candidate","native-multimon-unverified-crc"].includes(protocol.decoder);
}
export function listCapabilityDetails(pass){
 return protocolsForPass(pass).map(d=>({
   id:d.id,kind:d.kind,label:d.label,protocol:d.protocol,frequencyMHz:d.frequencyHz/1e6,
   activity:d.activity,decoder:d.decoder,source:d.source,note:d.note,
   message:"Known published protocol, NOT an active RF detection"
 }));
}
