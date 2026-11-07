/* Informative, provenance-safe Robot36 receive diagnostics.
 * Filenames supply candidate metadata; they do NOT verify RF source,
 * spacecraft identity, true hardware tuning or decoded image content.
 */
import {parseRecordingName} from "./satellite_imagery.mjs";

export const SERIES35_SSTV_FREQUENCY_HZ=437550000;
export const SERIES35_START_UTC=Date.parse("2026-11-09T00:00:00Z");
export const SERIES35_END_UTC=Date.parse("2026-11-17T00:00:00Z");

export function robot36CaptureHint(name){
  const meta=parseRecordingName(String(name||""));
  if(!meta)return "The WAV may be a valid audio file without containing SSTV. Verify the original SDR tuning, the broadcast date, a visible RF carrier and repeated Robot36 1200 Hz synchronization pulses.";
  const hz=meta.frequencyHz,time=Date.parse(meta.timestamp);
  const inWindow=time>=SERIES35_START_UTC&&time<SERIES35_END_UTC;
  const mhz=(hz/1e6).toFixed(3);
  const wrongBand=Math.abs(hz-SERIES35_SSTV_FREQUENCY_HZ)>20000;
  const parts=["Filename metadata: "+mhz+" MHz, "+meta.timestamp+"."];
  if(wrongBand){
    parts.push("This is NOT the 437.550 MHz ARISS Series 35 SSTV downlink. "+
      (Math.abs(hz-145800000)<20000?
        "145.800 MHz is the ISS VHF voice/contact channel, not this SSTV campaign. ":"")+
      "Select 'ISS SSTV · 437.550 MHz' when recording during the announced 9–16 Nov 2026 event (allow for Doppler).");
    if(meta.format==="cu8"&&meta.sampleRate&&
       Math.abs(hz-SERIES35_SSTV_FREQUENCY_HZ)>meta.sampleRate/2)
      parts.push("The original CU8 bandwidth cannot be retuned hundreds of MHz after recording.");
  }
  if(!inWindow)
    parts.push("This file was recorded outside the announced 9–16 November 2026 Series 35 event. A geometric ISS pass or a valid WAV alone is not proof that SSTV was transmitted.");
  if(!wrongBand&&inWindow)
    parts.push("Frequency and event date match the announced Series 35 profile, but no genuine repeated 1200 Hz sync was detected. Check antenna, actual RF signal, ±10 kHz Doppler and FM demodulation quality.");
  return parts.join(" ");
}
