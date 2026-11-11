/* Open, receive-only imagery/audio/data mission catalog.
 * Published in the same form by Pages/PWA and native companion.
 * Catalog targets are not proof of an active downlink.
 */
export const MISSIONS = Object.freeze([
  {
    id:"iss-sstv", name:"ISS · SSTV pictures", group:"Image", satellite:"ISS",
    frequencyHz:437550000, mode:"Robot36 over FM (event only)",
    input:"CU8 I/Q or demodulated FM WAV", decoder:"Browser: experimental Robot36; native: compatible SSTV tools",
    description:"Commemorative or educational SSTV pictures; usually NOT live Earth photographs. Transmissions are intermittent, frequency/mode can change by event; verify with ARISS. Doppler may require retuning.",
    official:"https://www.ariss.org/upcoming-sstv-events.html",
    availability:"event-only", receiver:"rtlsdr", route:"index.html#satellite-images",
    imageTarget:"iss"
  },
  {
    id:"meteor-m2-3", name:"Meteor-M2-3 · Earth weather scan", group:"Image", satellite:"Meteor-M2-3",
    frequencyHz:137900000, mode:"LRPT (frequency and symbol rate must be checked)",
    input:"CU8 I/Q", decoder:"Optional native SatDump; no in-browser LRPT decoder yet",
    description:"Actual Earth cloud/weather data when the spacecraft downlink is active and the receiver captures a decodable pass. 137.100 MHz is another documented candidate, not a promise of an active channel. A V-dipole or QFH is preferable.",
    official:"https://github.com/SatDump/SatDump.Docs/blob/master/pipelines.rst",
    availability:"verify-current-downlink", receiver:"rtlsdr-native-decode", route:"index.html#satellite-images",
    imageTarget:"meteor3"
  },
  {
    id:"meteor-m2-4", name:"Meteor-M2-4 · Earth weather scan", group:"Image", satellite:"Meteor-M2-4",
    frequencyHz:137900000, mode:"LRPT (verify current channel/pipeline)",
    input:"CU8 I/Q", decoder:"Optional native SatDump; no in-browser LRPT decoder yet",
    description:"Actual Earth imagery is possible from LRPT during a real downlink. Test decoder 72k/80k only as supported by the installed SatDump build; an orbit pass alone proves nothing.",
    official:"https://github.com/SatDump/SatDump.Docs/blob/master/pipelines.rst",
    availability:"verify-current-downlink", receiver:"rtlsdr-native-decode", route:"index.html#satellite-images",
    imageTarget:"meteor4"
  },
  {
    id:"iss-aprs", name:"ISS · packet messages", group:"Text / data", satellite:"ISS",
    frequencyHz:437825000, mode:"AX.25 / APRS (check ARISS current station status)",
    input:"Real RF capture / decoded packets", decoder:"Native multimon-ng when installed; browser RF packet decode not implemented",
    description:"Public amateur packet traffic is text/telemetry, not an Earth-camera video stream. Station mode changes; do not infer successful packets from signal strength.",
    official:"https://www.ariss.org/current-status-of-iss-stations.html",
    availability:"station-mode-dependent", receiver:"rtlsdr-native-decode", route:"index.html#satellite-images",
    imageTarget:"iss"
  },
  {
    id:"iss-voice", name:"ISS · voice / repeater audio", group:"Audio", satellite:"ISS",
    frequencyHz:437800000, mode:"FM voice/repeater (station-mode dependent)",
    input:"FM demodulated WAV / CU8 I/Q", decoder:"Browser local audio candidate; native radio FM demodulator",
    description:"Possible public amateur voice/repeater downlink, not guaranteed astronaut speech. Verify the actual current station configuration and downlink with ARISS.",
    official:"https://www.ariss.org/current-status-of-iss-stations.html",
    availability:"station-mode-dependent", receiver:"rtlsdr", route:"index.html#iq-analysis",
    imageTarget:"iss"
  },
  {
    id:"iss-hamtv", name:"ISS · HamTV digital video (advanced)", group:"Video", satellite:"ISS",
    frequencyHz:2395000000, mode:"S-band 2.395 GHz DVB-S digital TV (check ARISS status)",
    input:"Specialized S-band antenna/receiver and true captured DVB-S transport stream", decoder:"External compatible S-band DVB-S/SatDump tools; NOT available from current two USB receivers",
    description:"HamTV usually sends a blank test signal unless a camera/educational event is active. No continuous live Earth-camera feed is promised. NESDR SMArt v5 tops out at 1750 MHz; Hauppauge WinTV-soloHD is DVB-T/T2/C, not a 2.395 GHz satellite DVB-S receiver.",
    official:"https://www.ariss.org/hamtv-on-the-iss.html",
    availability:"hardware-upgrade", receiver:"new-sband-hardware", route:"index.html#satellite-tracking-maps",
    imageTarget:null
  },
  {
    id:"satnogs", name:"Other amateur satellites · open catalog", group:"Text / data", satellite:"User-selected verified satellite",
    frequencyHz:null, mode:"Depends on published transmitter/protocol",
    input:"Recorded samples or protocol-specific decoded data", decoder:"Only if a matching validated decoder is available",
    description:"Explore a verified open-frequency catalog first. A CubeSat orbit does not indicate the downlink, modulation, permissions, or whether an image/file is transmitted.",
    official:"https://db.satnogs.org/",
    availability:"catalog-only", receiver:"protocol-dependent", route:"index.html#satellite-tracking-maps",
    imageTarget:null
  },
  {
    id:"nasa-online", name:"NASA · Earth images & ISS archive", group:"Online imagery", satellite:"DSCOVR/ISS online archive",
    frequencyHz:null, mode:"Official online media; not an antenna downlink",
    input:"Internet imagery", decoder:"None; provider image archive",
    description:"NASA DSCOVR EPIC full-disk Earth photos and ISS historical Earth photography. Sources and acquisition times must be visible; never label these as images received over RTL-SDR.",
    official:"https://epic.gsfc.nasa.gov/about/api",
    availability:"online-on-demand", receiver:"internet", route:"index.html#satellite-images",
    imageTarget:null
  },
  {
    id:"legacy-noaa", name:"NOAA-15 / 18 / 19 · archived APT files", group:"Archive", satellite:"Retired NOAA POES",
    frequencyHz:null, mode:"Historical APT recordings only; satellites decommissioned in 2025",
    input:"Previously recorded audio/images", decoder:"Compatible offline APT decoder (optional external)",
    description:"NOAA-15, -18 and -19 are decommissioned. Do NOT schedule them as active weather image downlinks.",
    official:"https://www.nesdis.noaa.gov/news/suspension-of-poes-data-to-users-after-june-16-2025-and-decommissioning",
    availability:"retired", receiver:"offline-only", route:"index.html#iq-analysis",
    imageTarget:null
  }
]);

export function missionById(id) {
  return MISSIONS.find(m => m.id === id) || null;
}

export function localFileKind(name) {
  const ext=String(name||"").toLowerCase().split(".").pop();
  if(["png","jpg","jpeg","webp","gif"].includes(ext))return "image";
  if(["wav","mp3","ogg","flac","m4a"].includes(ext))return "audio";
  if(["mp4","webm","mov"].includes(ext))return "video";
  if(["txt","json","csv","tle","log","aprs"].includes(ext))return "text";
  if(["cu8","iq","u8","cfile"].includes(ext))return "iq";
  return "unknown";
}

export function fileEvidence({name,size,lastModified},missionId,centerHz=null,sampleRate=null) {
  const mission=missionById(missionId);
  if(!mission)throw new Error("Choose a valid catalog target");
  if(!Number.isFinite(size)||size<0)throw new Error("Invalid file size");
  const hz=centerHz===null?null:Number(centerHz);
  const rate=sampleRate===null?null:Number(sampleRate);
  if(hz!==null&&(!Number.isFinite(hz)||hz<0))throw new Error("Invalid recording frequency");
  if(rate!==null&&(!Number.isFinite(rate)||rate<=0))throw new Error("Invalid sample rate");
  return {
    schema:"tihulu-satellite-local-evidence-v1",
    source:"user-imported_unverified",
    catalogTarget:mission.id,
    catalogTargetIsVerifiedTransmitter:false,
    name:String(name||"").slice(0,240),
    format:localFileKind(name),
    sizeBytes:size,
    fileModifiedUtc:Number.isFinite(lastModified)?new Date(lastModified).toISOString():null,
    selectedFrequencyHz:hz,
    sampleRateSps:rate,
    durationSeconds:localFileKind(name)==="iq"&&rate?size/(2*rate):null,
    meaning:"Local file metadata only; no signal identity, successful packet CRC, audio content or image provenance has been verified"
  };
}
