"""Native, evidence-based CU8 signal discovery and narrow-FM WAV extraction.

A spectral peak is NOT enough to identify a spacecraft, packet, or image.
This creates actual PCM WAV samples from real IQ; never changes file labels.
"""
from __future__ import annotations
from datetime import datetime,timezone
import json,math,os,uuid,wave
from pathlib import Path
from statistics import median
from .native_analysis import _file,MAX_IQ_BYTES

FREQUENCY_HINTS=(
 (137900000,"Meteor LRPT Earth-image candidate; requires SatDump sync/FEC"),
 (137100000,"Meteor alternate LRPT candidate; verify actual downlink"),
 (437550000,"ISS SSTV image candidate; active ARISS event required"),
 (145800000,"ISS voice/SSTV FM audio candidate; activity unverified"),
 (145825000,"ISS APRS/AX.25 text candidate; CRC decoding required"),
 (437825000,"ISS UHF APRS/AX.25 candidate; CRC decoding required"),
 (437800000,"ISS repeater FM audio candidate; activity unverified"),
)

def discover_channels(report,threshold_db=7.0,limit=16):
    """Return spectral regions above noise baseline, not RF classifications."""
    powers=report.get("relative_spectrum_db") or []
    freq=report.get("frequencies_hz") or []
    if len(powers)!=len(freq) or len(freq)<4:
        raise ValueError("Analyze CU8 spectrum first")
    base=median(float(v) for v in powers if math.isfinite(float(v)))
    candidates=[];region=[]
    for i,v in enumerate(powers):
        if math.isfinite(float(v)) and v>=base+threshold_db:region.append(i)
        elif region:
            candidates.append(region);region=[]
    if region:candidates.append(region)
    result=[]
    for cells in candidates:
        highest=max(cells,key=lambda i:powers[i])
        width=(max(freq[i] for i in cells)-min(freq[i] for i in cells))
        hz=float(freq[highest])
        hints=[message for known,message in FREQUENCY_HINTS if abs(known-hz)<=max(20000,width)]
        result.append({
            "frequency_hz":round(hz,2),
            "width_hz_approx":round(width,2),
            "relative_peak_db":round(float(powers[highest]),2),
            "above_median_db":round(float(powers[highest]-base),2),
            "bin_count":len(cells),
            "possible_protocols_not_verified":hints,
            "status":"UNCLASSIFIED_RF_ENERGY_ONLY"
        })
    result.sort(key=lambda x:-x["above_median_db"])
    return {
        "format":"tihulu-native-spectrum-candidates-v1",
        "source":report.get("source"),
        "source_bytes":report.get("source_bytes"),
        "full_time_coverage":bool(report.get("complete_time_coverage")),
        "measured_noise_floor_relative_db":round(base,2),
        "threshold_above_median_db":threshold_db,
        "candidates":result[:limit],
        "disclaimer":"Relative spectrum peaks and catalog frequency hints do not prove satellite identity, audio, image, or valid packets."
    }

def fm_to_wav(cu8_path,output_dir,sample_rate=1024000,center_hz=0,
              offset_hz=0,gain=1.0):
    """Stream narrow FM I/Q to an actual 32 kHz mono 16-bit RIFF/WAV.

    Native CPU/Numpy only. The incoming CU8 MUST be an actual complex IQ
    recording with the correct user-specified sample-rate/frequency metadata.
    Output is an unverified analog demodulation, not decoded SSTV/voice.
    """
    source=_file(cu8_path)
    if source.suffix.lower()!=".cu8":
        raise ValueError("Select a real unsigned interleaved .cu8 recording")
    if type(sample_rate) is not int or sample_rate not in (1024000,2048000):
        raise ValueError("Supported input rate: 1.024 or 2.048 MS/s")
    if not all(isinstance(v,(int,float)) and math.isfinite(v) for v in
               (center_hz,offset_hz,gain)):
        raise ValueError("Invalid demodulator frequency or gain")
    if abs(offset_hz)>sample_rate/2-20000 or not .05<=gain<=10:
        raise ValueError("FM channel outside IQ bandwidth or invalid gain")
    if source.stat().st_size<4096 or source.stat().st_size>MAX_IQ_BYTES:
        raise ValueError("CU8 missing or larger than safe 2GB input limit")
    try:import numpy as np
    except ImportError as exc:raise RuntimeError("Requires python3-numpy") from exc
    decimation=sample_rate//32000
    root=Path(output_dir).expanduser()
    root.mkdir(parents=True,exist_ok=True)
    suffix=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")+"_"+uuid.uuid4().hex[:6]
    name=source.stem[:75]+"_fm_"+suffix
    dest=root/(name+".wav")
    temporary=root/(name+".wav.part")
    reportpath=root/(name+".json")
    frames=0;offset_samples=0;previous=None
    try:
        with source.open("rb") as stream,wave.open(str(temporary),"wb") as wav:
            wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(32000)
            while True:
                data=stream.read(decimation*4096*2)
                if not data:break
                bytes_in=len(data)//(decimation*2)*(decimation*2)
                if not bytes_in:break
                pairs=np.frombuffer(data[:bytes_in],dtype=np.uint8).astype(np.float32)
                iq=(pairs[0::2]-127.5 + 1j*(pairs[1::2]-127.5))/128.
                if offset_hz:
                    phase=(np.arange(iq.size,dtype=np.float64)+offset_samples)
                    iq=iq*np.exp(-2j*np.pi*offset_hz*(phase%sample_rate)/sample_rate)
                offset_samples+=iq.size
                avg=iq.reshape(-1,decimation).mean(axis=1)
                prev=avg[0] if previous is None else previous
                diffs=np.angle(avg*np.conj(np.concatenate(([prev],avg[:-1]))))
                previous=avg[-1]
                # Suppress residual receiver carrier offset in each short block.
                audio=diffs-np.mean(diffs)
                pcm=np.clip(audio*(24000*gain),-32767,32767).astype("<i2")
                wav.writeframes(pcm.tobytes())
                frames+=len(pcm)
        if frames<100:raise ValueError("Insufficient real audio samples")
        os.replace(temporary,dest)
        report={
            "format":"tihulu-uncalibrated-narrow-fm-audio-v1",
            "source":str(source),"output_wav":str(dest),
            "center_frequency_hz":int(center_hz),"channel_offset_hz":float(offset_hz),
            "input_sample_rate":sample_rate,"pcm_sample_rate":32000,
            "pcm_channels":1,"pcm_bits_per_sample":16,
            "pcm_frames":frames,"duration_seconds":round(frames/32000,3),
            "confidence":"UNVERIFIED_FM_DEMODULATION",
            "warnings":["A valid WAV is not proof of speech, SSTV or a satellite.",
                        "Narrow FM/audio only; this is NOT Meteor LRPT image decoding.",
                        "Offset, sample rate and gain must match actual RF capture."]
        }
        reportpath.write_text(json.dumps(report,indent=2),encoding="utf-8")
        return report
    finally:
        temporary.unlink(missing_ok=True)
