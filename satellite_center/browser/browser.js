import { platformFamily, webUsbHelp, permissionReport, usbInterfaceClaimProbe } from './usb_diagnostics.mjs?v=20261106-dvb-unbind-v09';
import { createSatelliteMaps } from './satellite_maps.mjs?v=20261106-live-v14';
import { initIqAnalysisUI } from './iq_analysis_ui.mjs?v=20261106-iss-npu-release-v1';
import { initSatelliteImageUI } from './satellite_images_ui.mjs?v=20261107-iss-band-diagnostic-v1';
import { recordingName } from './satellite_imagery.mjs?v=20261106-images-v15';
import { initStationLocationUI } from './location_search.mjs';
import { probeUsbSamples, sampleBytes } from './usb_live_probe.mjs?v=20261106-map-usb-v07';
import { sortPassList } from './pass_sort.mjs';
import {validatedWindow,windowSummary} from './pass_window.mjs';
import { protocolsForPass, protocolCategories, passesFilteredByContent } from './pass_protocol_catalog.mjs';
import {readUserProfiles} from './saved_satellite_protocols.mjs';
import { selectAutomaticPasses, AUTO_TARGETS } from './auto_mission.mjs?v=20261106-iss-npu-release-v1';
import {localDayKey,shiftCalendarDay,renderSatelliteCalendar} from './satellite_calendar.mjs?v=20261106-calendar-zip-v2';
import { localDateInput, parseLocalScheduleTime, createScheduledPass, evaluateScheduledJob, secondsToJob, captureLevelSummary } from './schedule_controller.mjs?v=20261106-direct-fm-wav-v1';
import {planChainedCapture,secondsFromEntry,humanCountdown,scheduledOverlap} from './chained_capture.mjs?v=20261107-chained-v1';
import {candidateFromPass,readPlanningCandidates,savePlanningCandidate,removePlanningCandidate} from './pass_candidates.mjs';
import {captureBudget,formatCaptureBudget,STREAM_IQ_BYTES} from './capture_duration.mjs?v=20261106-stream-v1';
import {createStreamingFmWavEncoder,createPcmWavHeader,wavOutputPlan} from './fm_wav_record.mjs?v=20261106-web-fm-wav-v1';
// TIHULU Satellite Center — no-local-install receive-only browser mode.
// The RTL-SDR device is opened only after a direct user gesture.
// CelesTrak / CDN downloads are for client-side orbital prediction + JS only;
// I/Q samples stay on this device and are never uploaded.
const $ = id => document.getElementById(id);
const status = (id, message) => { $(id).textContent = String(message); };
const log = message => {
  const row = new Date().toLocaleTimeString() + ' · ' + String(message);
  $('log').textContent = row + '\n' + $('log').textContent.slice(0, 7000);
};
const FREQS = Object.freeze({
  iss: 145800000, meteor: 137900000, cubesat: 436000000, iridium: 1620000000
});
const LOCATIONS = Object.freeze({
  Cologne: [50.938,6.960], Izmir:[38.423,27.143], Berlin:[52.520,13.405],
  Istanbul:[41.009,28.978], Ankara:[39.933,32.859], Brussels:[50.850,4.351]
});
const TLE_SOURCES = Object.freeze({
  iss: 'https://celestrak.org/NORAD/elements/gp.php?CATNR=25544&FORMAT=TLE',
  meteor3: 'https://celestrak.org/NORAD/elements/gp.php?CATNR=57166&FORMAT=TLE',
  meteor4: 'https://celestrak.org/NORAD/elements/gp.php?CATNR=59051&FORMAT=TLE',
  cubesat: 'https://celestrak.org/NORAD/elements/gp.php?GROUP=amateur&FORMAT=TLE',
  iridium: 'https://celestrak.org/NORAD/elements/gp.php?GROUP=iridium-NEXT&FORMAT=TLE'
});
let driver = null, device = null, capturePromise = null, stopRequested = false;
let usbTestRunning = false;
let lastCaptured = null, rtlLibraryError = null;
let orbitalLibrary = null, tleEntries = [], passes = [], jobs = [], sessionCounter = 0;
let visiblePassCount=40, lastScheduledFile=null, wakeLock=null, schedulerTickBusy=false;
let lastTleFetchAt = 0;
let locationUI = null;
let satelliteMaps = null;
let iqAnalysisUI = null;
let satelliteImageUI = null;
let imageCandidateTarget=null;
const notifyMaps = () => { if(satelliteMaps) void satelliteMaps.refresh().catch(e=>log('Map refresh: '+e.message)); };
const maxRecordBytes = 128 * 1024 * 1024;
const preparedLongStreams=new Map();
const CHAIN_SEGMENT_GAP_SECONDS=6;
const diskStreamingAvailable=()=>Boolean(window.isSecureContext&&typeof window.showSaveFilePicker==="function");
const nativeLocal=()=>location.protocol==="http:"&&["localhost","127.0.0.1"].includes(location.hostname);
const nativeReceiver=()=>nativeLocal()||window.nativeRFTransport==="rtl_sdr";
async function nativeRequest(route,payload=null,csrf=null){
 const opts={cache:"no-store",credentials:"same-origin"};
 if(payload!==null){opts.method="POST";opts.headers={"Content-Type":"application/json"};opts.body=JSON.stringify({...payload,csrf});}
 const response=await fetch(route,opts);
 const result=await response.json().catch(()=>({error:"Invalid local response"}));
 if(!response.ok)throw Error(String(result.error||response.status));
 return result;
}
async function nativeScheduledPass(pass,{when,durationSeconds,frequency,sampleRate,saveRaw,saveWav=false}){
 if(!nativeLocal())throw Error("Start the Debian app and open http://127.0.0.1:8791/browser/index.html");
 if(![1024000,2048000].includes(sampleRate))throw Error("Native SDR sample rate must be 1.024 or 2.048 MS/s.");
 if(!Number.isInteger(durationSeconds)||durationSeconds<8||durationSeconds>7200)
   throw Error("Native capture chain must be 8–7200 whole seconds and fit the predicted pass.");
 if(!saveRaw&&!saveWav)throw Error("Select at least one recording format.");
 if(pass.family==="meteor"&&!saveRaw)throw Error("Meteor LRPT requires original IQ (.cu8). FM WAV / Robot36 is not a Meteor LRPT format.");
 if(pass.family==="meteor"&&saveWav)throw Error("Meteor LRPT cannot use FM WAV or dual-format recording. Uncheck WAV and record original IQ (.cu8).");
 if(saveWav&&!["iss_voice","iss_sstv","iss_uhf"].includes(
   frequency===437550000?"iss_sstv":frequency===145800000?"iss_voice":frequency===437800000?"iss_uhf":""))
   throw Error("This frequency has no native FM WAV profile. Select original IQ (.cu8).");
 // Native survey is limited to 180 s PER FILE. Longer jobs use the same
 // opt-in backend chain scheduler, each part a separately persisted file.
 const state=await nativeRequest("/api/status");
 if(!state.csrf||!state.profiles)throw Error("Local SDR server not available");
 const profile=Object.entries(state.profiles).find(([,p])=>p.family===pass.family&&Number(p.freq)===frequency)?.[0];
 if(!profile)throw Error("No approved native receiver profile for this satellite and frequency.");
 const lat=Number($('lat').value),lon=Number($('lon').value);
 if(!Number.isFinite(lat)||!Number.isFinite(lon)||Math.abs(lat)>90||Math.abs(lon)>180)
   throw Error("Choose valid observer coordinates first.");
 const hours=Math.max(1,Math.min(72,Math.ceil((pass.aos-Date.now())/3600000)+2));
 const predict=()=>nativeRequest("/api/passes?lat="+encodeURIComponent(lat)+
   "&lon="+encodeURIComponent(lon)+"&hours="+hours+"&elev=10");
 let events=await predict();
 const matched=()=>events.predictions?.find(p=>Number(p.norad)===Number(pass.id)&&
   Math.abs(Date.parse(p.aos)-pass.aos)<=300000&&p.profiles?.includes(profile));
 let target=matched();
 if(!target&&events.warnings?.some(w=>/not downloaded|too old/.test(w))){
   await nativeRequest("/api/refresh",{},state.csrf);
   events=await predict();target=matched();
 }
 if(!target)throw Error("Native TLE pass differs from browser estimate. Refresh catalog and recalculate.");
 const endpoint=durationSeconds>900?"/api/schedule-chain":"/api/schedule";
 const mode=saveRaw&&saveWav?"iq_and_fm_wav":
   saveRaw?"iq":profile==="iss_sstv"?"sstv_audio":"fm_audio";
 return nativeRequest(endpoint,{pass_id:target.id,profile,mode,
   run_at:new Date(when).toISOString(),duration_seconds:durationSeconds,
   sample_rate:sampleRate},state.csrf);
}

function captureWavName(job,frequency,at=new Date()){
 const target=job?.name?job.name+"-CANDIDATE":
   imageCandidateTarget&&imageCandidateTarget.frequencies.includes(frequency)?
     imageCandidateTarget.name+"-CANDIDATE":"RF-UNATTRIBUTED";
 return recordingName({satellite:target,at,frequencyHz:frequency,
   sampleRate:48000,format:"wav",kind:"SSTV-AUDIO"});
}
function inspectCaptureStorage(seconds,rate,raw,wav){
 const iq=captureBudget(seconds,rate,raw,{fileStreaming:diskStreamingAvailable()});
 const audio=wavOutputPlan(seconds,wav,{fileStreaming:diskStreamingAvailable()});
 return {iq,audio,rawDisk:iq.mode==="disk-stream",wavDisk:audio.mode==="disk-stream"};
}
async function selectRecordingFiles(seconds,rate,raw,wav,{job=null,at=new Date(),freq=null}={}){
 const plan=inspectCaptureStorage(seconds,rate,raw,wav);
 if(!plan.rawDisk&&!plan.wavDisk)return null;
 const frequency=freq??Number($('preset').value);
 const rawName=captureFileName(job,frequency,rate,at);
 const wavName=captureWavName(job,frequency,at);
 const prepared={name:rawName,wavName,writable:null,wavWritable:null};
 try{
   if(plan.rawDisk&&plan.wavDisk){
     if(typeof window.showDirectoryPicker!=="function")
       throw Error("Saving long CU8 and WAV together requires a Chromium directory picker. Record WAV-only, lower duration, or use the native app.");
     const directory=await window.showDirectoryPicker({mode:"readwrite"});
     const rawHandle=await directory.getFileHandle(rawName,{create:true});
     const wavHandle=await directory.getFileHandle(wavName,{create:true});
     prepared.writable=await rawHandle.createWritable();
     prepared.wavWritable=await wavHandle.createWritable();
   }else if(plan.rawDisk){
     const handle=await window.showSaveFilePicker({suggestedName:rawName,
       types:[{description:"TIHULU unsigned IQ CU8",accept:{"application/octet-stream":[".cu8"]}}]});
     prepared.writable=await handle.createWritable();
   }else{
     const handle=await window.showSaveFilePicker({suggestedName:wavName,
       types:[{description:"TIHULU demodulated FM WAV",accept:{"audio/wav":[".wav"]}}]});
     prepared.wavWritable=await handle.createWritable();
   }
   return prepared;
 }catch(error){await abortLongCapture(prepared);throw error;}
}
function captureFileName(job,frequency,rate,at=new Date()){
 const target=job?.name?job.name+"-CANDIDATE":
   imageCandidateTarget&&imageCandidateTarget.frequencies.includes(frequency)?
     imageCandidateTarget.name+"-CANDIDATE":"RF-UNATTRIBUTED";
 return recordingName({satellite:target,at,frequencyHz:frequency,
   sampleRate:rate,format:"cu8",kind:job?"SCHEDULED-IQ":"IQ"});
}
async function abortLongCapture(prepared){
 if(!prepared)return;
 for(const key of ["writable","wavWritable"]){
   if(!prepared[key])continue;
   const stream=prepared[key];prepared[key]=null;
   try{await stream.abort();}catch(error){log("Disk stream cleanup: "+error.message);}
 }
}
function releaseScheduledStream(job){
 const prepared=preparedLongStreams.get(job.id);
 if(!prepared)return;
 preparedLongStreams.delete(job.id);
 void abortLongCapture(prepared);
}
function buildBrowserChain(pass,{when,totalSeconds,rate,frequency,raw,wav,excludeIds=[]}){
 const plan=planChainedCapture({startMs:when,totalSeconds,rate,raw,wav,untilMs:pass.los});
 const groupId='chain:'+pass.id+':'+when+':'+frequency+':'+String(++sessionCounter);
 const batch=plan.segments.map(segment=>{
   const job=createScheduledPass(pass,{when:segment.when,durationSeconds:segment.durationSeconds,
     sampleRate:rate,frequency,saveRaw:raw,saveWav:wav,
     diskStreamPrepared:false,wavDiskPrepared:false});
   job.chainId=groupId;job.chainIndex=segment.index;job.chainTotal=plan.segments.length;
   job.chainCaptureTotal=totalSeconds;
   job.estimatedBytes=segment.estimatedRawBytes+segment.estimatedWavBytes;
   job.message='Part '+segment.index+'/'+plan.segments.length+
     ' · '+segment.durationSeconds+' s · '+(job.estimatedBytes/1e6).toFixed(1)+
     ' MB · independent RF file. Possible inter-part gaps; not continuous I/Q.';
   return job;
 });
 for(const candidate of batch){
   if(jobs.some(other=>!excludeIds.includes(other.id)&&
       ['armed','starting','running'].includes(other.state)&&
       (other.id===candidate.id||scheduledOverlap(candidate,other,{guardSeconds:0}))))
     throw Error('Single receiver conflict: another armed or running recording overlaps this capture chain.');
 }
 return {jobs:batch,plan};
}
function addBrowserChain(batch){
 jobs.push(...batch);
 jobs.sort((a,b)=>a.when-b.when);
 renderJobs();
}
function outputSelectionText(raw,wav){
 if(raw&&wav)return 'CU8 + WAV selected · 2 separate files from the same RF recording';
 if(wav)return 'WAV selected · 1 demodulated FM audio file';
 if(raw)return 'CU8 selected · 1 original raw RF/IQ file';
 return 'No file selected · RF level measurements only';
}
function refreshAutoOutputSummary(){
 const raw=$('auto-save-raw').checked,wav=$('auto-save-wav').checked;
 $('auto-format-summary').textContent=outputSelectionText(raw,wav)+
   '. These choices apply to ISS SSTV WebUSB automatic jobs. Other downlink formats keep their own defaults.';
}
function setManualOutputSelection(raw,wav){
 $('record').checked=Boolean(raw);
 $('wav-record').checked=Boolean(wav);
 updateManualCaptureBudget();
}
$('record-both').addEventListener('click',()=>setManualOutputSelection(true,true));
$('record-wav-only').addEventListener('click',()=>setManualOutputSelection(false,true));
$('record-cu8-only').addEventListener('click',()=>setManualOutputSelection(true,false));
for(const id of ['auto-save-raw','auto-save-wav']){
 $(id).addEventListener('change',refreshAutoOutputSummary);
 $(id).addEventListener('input',refreshAutoOutputSummary);
}
refreshAutoOutputSummary();
function updateManualCaptureBudget(){
 const label=$('capture-budget');
 const summary=$('capture-format-summary');
 summary.textContent=outputSelectionText($('record').checked,$('wav-record').checked)+
   '. You may select both, or record uncalibrated RF levels only.';
 try{
   const seconds=secondsFromEntry($('duration').value,$('duration-unit').value);
   const rate=Number($('rate').value),raw=$('record').checked,wav=$('wav-record').checked;
   const segmented=seconds>60||(raw&&seconds*rate*2>maxRecordBytes);
   if(segmented){
     const plan=planChainedCapture({startMs:Date.now()+1000,totalSeconds:seconds,rate,raw,wav});
     label.textContent='Automatic chain: '+plan.segments.length+' separate calendar jobs · '+
       seconds+' s total recording / '+plan.elapsedSeconds+' s elapsed · '+
       (plan.segments.reduce((n,p)=>n+p.estimatedRawBytes+p.estimatedWavBytes,0)/1e6).toFixed(1)+
       ' MB across downloads. Maximum '+plan.segments[0].durationSeconds+
       ' s per file. '+plan.warning+' Multiple automatic downloads may need browser approval.';
   }else{
     const opts=inspectCaptureStorage(seconds,rate,raw,wav);
     label.textContent=(opts.iq.mode==='levels-only'?'No raw CU8. ':
       'CU8: '+(opts.iq.estimatedBytes/1e6).toFixed(0)+' MB ('+opts.iq.mode+'). ')+
       (opts.audio.enabled?'WAV: '+(opts.audio.estimatedBytes/1e6).toFixed(1)+' MB ('+
         opts.audio.mode+', 48 kHz mono PCM). ':'')+
       'Single foreground WebUSB session.';
   }
   label.dataset.feasible='true';
 }catch(error){label.dataset.feasible='false';label.textContent=String(error?.message||error);}
}

$('preset').addEventListener('change',()=>{
 // SSTV defaults to real FM WAV, but users may check CU8 as well.
 const iss=Number($('preset').value)===437550000;
 setManualOutputSelection(!iss,iss);
});
for(const id of ['duration','duration-unit','rate','record','wav-record']){
 $(id).addEventListener('input',updateManualCaptureBudget);
 $(id).addEventListener('change',updateManualCaptureBudget);
}
updateManualCaptureBudget();
const signalHistory = [];
const hardwareSupported = !!(window.isSecureContext && navigator.usb);
const connectButton = $('connect');
$('usb-live-test').disabled=true; // No test until real WebUSB driver is loaded.
const platform = platformFamily(navigator.userAgent || "");
let lastUsbReport = "No USB diagnostics run.";
$('usb-check').addEventListener('click', async () => {
  const report = await permissionReport(navigator.usb, platform);
  lastUsbReport = report;
  $('usb-report').textContent = report;
  log('Read-only USB permission diagnostic completed. No device was opened.');
});
$('usb-claim-test').addEventListener('click',async()=>{
  if(usbTestRunning||capturePromise||device){
    $('usb-claim-result').textContent='Stop the current receiver/test and release USB before trying the interface-only diagnostic.';
    return;
  }
  usbTestRunning=true;
  refreshControls();
  const button=$('usb-claim-test');
  button.disabled=true;
  $('usb-claim-result').textContent='Opening permitted RTL2832U and trying claimInterface(0)… No RF is being sampled.';
  try{
    const res=await usbInterfaceClaimProbe(navigator.usb);
    const output=res.ok?
      'USB INTERFACE TEST PASSED. '+res.summary+'\nThe device was released. To test actual RF bytes, use Test real USB + RF samples.' :
      'USB INTERFACE TEST FAILED at '+res.stage+'.\n'+res.errorName+': '+res.errorMessage+
      (res.cleanupErrors?.length?'\nCleanup warnings: '+res.cleanupErrors.join('; '):'')+
      '\nIf stage is claimInterface(0), another SDR process, kernel DVB driver or OS USB policy is blocking the claim. Browser permission alone cannot override this.';
    $('usb-claim-result').textContent=output;
    lastUsbReport=output+'\n\n'+lastUsbReport;
    log('WebUSB interface-only test: '+(res.ok?'claim succeeded and released':'failed at '+res.stage));
  }catch(e){
    $('usb-claim-result').textContent='USB diagnostic failed: '+String(e?.message||e);
    log('USB claim test unexpected error: '+String(e?.message||e));
  }finally{
    usbTestRunning=false;
    button.disabled=false;
    refreshControls();
  }
});
$('usb-copy').addEventListener('click', async () => {
  try {
    await navigator.clipboard.writeText(lastUsbReport);
    log('USB troubleshooting report copied to clipboard (no device serials or secrets).');
  } catch (error) {
    log('Clipboard not available: ' + error.message);
  }
});
if (!hardwareSupported) {
  connectButton.disabled = true;
  status('device-status', 'Direct USB unavailable in this browser. Use desktop Chrome/Edge/Brave over HTTPS. Firefox and Safari do not implement WebUSB.');
} else {
  connectButton.disabled = true;
  status('device-status', 'Loading version-pinned browser RTL-SDR driver (no local installer)…');
  import('https://esm.sh/@jtarrio/webrtlsdr@3.0.7/rtlsdr.js?bundle').then(mod => {
    if (typeof mod.RTL2832U_Provider !== 'function') throw Error('Unsupported WebUSB driver export');
    driver = mod.RTL2832U_Provider;
    refreshControls();
    status('device-status', 'Ready to ask for USB permission. Plug Nooelec into USB, then select Choose RTL-SDR.');
    // A click on the dedicated Images & Data tab may request a one-step
    // automatic plan. It may ONLY reuse a previously granted USB device,
    // never trigger a permission chooser on page load.
    const requested=new URLSearchParams(location.search).get('auto-mission');
    // Only the user's explicit one-click request in the sibling Images & Data tab
    // can arm this cross-page auto mission. External deep links never schedule RF.
    let permittedAutoIntent=false;
    try {
      const saved=sessionStorage.getItem('tihulu-auto-start-intent');
      sessionStorage.removeItem('tihulu-auto-start-intent');
      const intent=saved?JSON.parse(saved):null;
      permittedAutoIntent=!!(intent && intent.mode===requested &&
        Number.isFinite(intent.createdAt) && Date.now()-intent.createdAt>=0 &&
        Date.now()-intent.createdAt<=5*60000);
    } catch(error){ log('Auto mission intent rejected: '+error.message); }
    if(permittedAutoIntent&&['iss-images','images','messages','voice','all'].includes(requested)){
      void runAutoMission({mode:requested,fromNavigation:true});
    }
  }).catch(err => {
    rtlLibraryError = err;
    refreshControls();
    status('device-status', 'WebUSB library unavailable: ' + err.message + '. Internet access to esm.sh is needed to load the driver; no hardware was opened.');
  });
}
function refreshControls() {
  if(window.nativeWebBridgeReady){
    // Exact Qt desktop UI handles RF through native OS bridge, never WebUSB.
    for(const id of ['start','stop','disconnect','connect','usb-live-test']){
      if($(id))$(id).disabled=false;
    }
    return;
  }
  $('start').disabled = !device || !!capturePromise || usbTestRunning;
  $('stop').disabled = !capturePromise;
  $('disconnect').disabled = (!device && !capturePromise) || usbTestRunning;
  $('connect').disabled = !driver || !!device || !!capturePromise || usbTestRunning;
  $('usb-live-test').disabled = !driver || !!capturePromise || usbTestRunning;
}
async function closeDevice() {
  const previous = device;
  device = null;
  refreshControls();
  if (previous) {
    try { await previous.close(); }
    catch (e) { log('USB close warning: ' + e.message); }
  }
}
async function connectDevice({silent=false}={}) {
  if (!hardwareSupported || !driver) {
    const msg=rtlLibraryError ? rtlLibraryError.message : 'WebUSB receiver driver is not ready';
    status('device-status', msg);
    if(silent)throw Error(msg);
    return false;
  }
  if (device) return true;
  if (capturePromise) {if(silent)throw Error("Another capture is active");return false;}
  let selectedWebUsbDevice = null;
  try {
    // The pinned driver calls requestDevice on this WebUSB adapter.
    // Track *only* the device granted by this click, so a failed post-open
    // claim cannot leave that device open behind the driver's exception.
    // Do not enumerate or close other tabs' or programs' USB sessions.
    const webusb = {
      requestDevice: async options => {
        let chosen;
        if(silent){
          // getDevices() can reopen previously granted devices with no new user
          // gesture. This never requests a new permission in the background.
          const granted=await navigator.usb.getDevices();
          chosen=granted.find(d=>d.vendorId===0x0bda&&d.productId===0x2838);
          if(!chosen)throw Error("No previously permitted 0bda:2838 RTL-SDR. Click Choose RTL-SDR before scheduling.");
        }else{
          chosen=await navigator.usb.requestDevice(options);
        }
        selectedWebUsbDevice=chosen;
        return chosen;
      }
    };
    const provider = new driver({webusb});
    device = await provider.get();
    if (document.hidden) {
      await closeDevice();
      throw Error('Browser tab became hidden during USB permission; reopen this tab and retry.');
    }
    await device.setSampleRate(Number($('rate').value));
    await device.setCenterFrequency(Number($('preset').value));
    await device.setGain(null);
    await device.resetBuffer();
    const paired = await navigator.usb.getDevices();
    const rtl = paired.filter(x => x.vendorId === 0x0bda && x.productId === 0x2838);
    status('device-status', 'USB device opened using WebUSB. RTL2832U permission grants: ' + rtl.length +
      '. No RF data measured yet; antenna and signal unverified.');
    log((silent?"Scheduled auto-reopen":"Manual WebUSB connection")+": RTL2832U opened.");
    refreshControls();
    return true;
  } catch (e) {
    // provider.get() can open USBDevice, then fail to claim the interface.
    // It rejects before assigning our 'device' variable, so close the
    // particular USBDevice we just requested to release the browser handle.
    if (!device && selectedWebUsbDevice?.opened) {
      try {
        await selectedWebUsbDevice.close();
        log('Failed WebUSB claim: released the device opened in this tab.');
      } catch (cleanupError) {
        log('Failed WebUSB claim cleanup warning: ' + cleanupError.message);
      }
    }
    log('WebUSB permission/open error: ' + e.message);
    const report = webUsbHelp(e, platform);
    lastUsbReport = report;
    $('usb-report').textContent = report;
    $('usb-help').open = true;
    status('device-status', 'WebUSB could not open this RTL-SDR. Open the USB diagnostic panel below for platform-specific steps.\n' + String(e.message || e));
    log('USB diagnostics: ' + report.split('\n')[0]);
    await closeDevice();
    if(silent)throw e;
    return false;
  } finally { refreshControls(); }
}
async function testRealUsbReceiver(){
  if(usbTestRunning||capturePromise){
    status('usb-live-test-report','USB test is unavailable while another sample capture/test is running.');
    return;
  }
  if(!driver||!hardwareSupported){
    status('usb-live-test-report','Real USB test unavailable: use desktop Chrome/Brave/Edge with WebUSB and wait for the browser RTL-SDR driver to load.');
    return;
  }
  usbTestRunning=true;
  refreshControls();
  status('usb-live-test-report','Step 1/4: attempting to open the previously permitted RTL2832U. This is a REAL USB claim.');
  try{
    if(!device){
      // Re-use explicit previously granted USB permission without a new
      // chooser or extra program. If none exists, direct user to Choose RTL-SDR.
      await connectDevice({silent:true});
    }
    if(!device)throw Error('No RTL-SDR could be opened. Press Choose RTL-SDR and grant permission first.');
    status('usb-live-test-report','Step 2/4: tuning to the Step 2 frequency and reading real RF I/Q samples...');
    const result=await probeUsbSamples(device,{
      frequency:Number($('preset').value),rate:1024000,durationMs:3000,
      onProgress:message=>status('usb-live-test-report',message)
    });
    if(!Number.isFinite(result.rawBytes)||result.rawBytes<16384)
      throw Error('Too few real USB bytes for a valid sample-read test.');
    status('usb-live-test-report',
      'USB HARDWARE TEST PASSED: actual I/Q bytes received.\n'+
      'Frequency: '+(result.frequencyHz/1e6).toFixed(3)+' MHz · rate: '+
      (result.sampleRate/1e6)+' MS/s\n'+
      'Read: '+result.rawBytes.toLocaleString()+' bytes in '+
      result.blocks+' USB buffers ('+result.elapsedSeconds+' s).\n'+
      'Observed unsigned sample range: '+result.minSample+'–'+result.maxSample+
      ', digital relative level: '+result.relativeDigitalLevelDb+' dBFS-like.\n'+
      (result.sampleSpan<=1?'WARNING: samples are nearly constant; check SDR driver and tuning.\n':'')+
      'This proves USB opening and sample transfers ONLY, not antenna quality, a received satellite or decoded signal. USB released.');
    log('Physical WebUSB test: '+result.rawBytes+' I/Q bytes, tuner opened/tuned and sampled. No station identified.');
  }catch(err){
    const message=String(err?.message||err);
    status('usb-live-test-report','USB HARDWARE TEST FAILED or BLOCKED:\n'+message+
      '\nIf permission already exists but claiming fails, readsb/Gqrx or the Linux DVB kernel driver may own the device. No process was stopped.\n'+
      'Choose RTL-SDR first if this page has not yet been given permission.');
    const report=webUsbHelp(err,platform);
    lastUsbReport=report;
    $('usb-report').textContent=report;
    $('usb-help').open=true;
    log('Physical USB test failed: '+message);
  }finally{
    status('device-status','Hardware test completed; this tab is releasing its RTL-SDR USB handle. Other applications were not stopped.');
    try{await closeDevice();}catch(e){log('USB test cleanup: '+e.message);}
    usbTestRunning=false;
    refreshControls();
  }
}
$('usb-live-test').addEventListener('click',()=>{void testRealUsbReceiver();});
function rmsLevel(bytes) {
  let energy = 0, samples = 0;
  for (let i=0; i+1<bytes.length; i+=32) {
    const re = (bytes[i] - 127.5) / 128;
    const im = (bytes[i+1] - 127.5) / 128;
    energy += re * re + im * im;
    samples++;
  }
  return samples ? Math.round(100 * 10 * Math.log10(Math.max(energy/samples, 1e-12))) / 100 : null;
}
function renderSignal() {
  const canvas = $('level-chart'), ctx = canvas.getContext('2d');
  const w=canvas.width, h=canvas.height;
  ctx.fillStyle='#091523'; ctx.fillRect(0,0,w,h);
  ctx.strokeStyle='#31465f';ctx.lineWidth=1;
  for(let i=0;i<5;i++){let y=12+i*(h-24)/4;ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(w,y);ctx.stroke();}
  ctx.strokeStyle='#79b4fc';ctx.lineWidth=2;ctx.beginPath();
  signalHistory.forEach((v,i)=>{
    // Level is digital power relative to unsigned PCM full-scale, never RF dBm.
    const x=10+i*(w-20)/Math.max(1,signalHistory.length-1);
    const y=h-12-Math.max(0,Math.min(1,(v+65)/70))*(h-24);
    if(i===0)ctx.moveTo(x,y);else ctx.lineTo(x,y);
  });ctx.stroke();
}
function triggerRawDownload(blob,name) {
  const url=URL.createObjectURL(blob);
  const link=document.createElement('a');link.href=url;link.download=name;
  document.body.append(link);link.click();link.remove();
  setTimeout(()=>URL.revokeObjectURL(url),60000);
  log('Requested browser download: '+name+' · '+(blob.size/1048576).toFixed(2)+
    ' MiB of real recorded RF-derived data. Browser settings may block automatic downloads.');
}
function saveCapture(bytes,name,job=null,metadata=null) {
  if (!bytes.length) return null;
  const blob=new Blob(bytes,{type:'application/octet-stream'});
  if(job){
    // Avoid retaining hundreds of large recordings in memory. Only the
    // latest completed scheduled capture can be manually re-downloaded.
    if(lastScheduledFile){
      const previous=jobs.find(j=>j.id===lastScheduledFile.jobId);
      if(previous)previous.downloadAvailable=false;
    }
    lastScheduledFile={blob,name,jobId:job.id};
    job.downloadAvailable=true;
    job.fileName=name;
  }
  triggerRawDownload(blob,name);
  if(iqAnalysisUI&&metadata)iqAnalysisUI.record(blob,name,metadata);
  if(satelliteImageUI&&metadata)satelliteImageUI.recordCapture(blob,name,metadata);
  return blob;
}
async function startCapture(job=null,prepared=null) {
  if(capturePromise || usbTestRunning || !device)throw Error('Choose the RTL-SDR and finish any hardware test before capturing.');
  const freq=job?job.frequency:Number($('preset').value);
  const rate=job?job.sampleRate:Number($('rate').value);
  const limit=job?job.durationSeconds:Number($('duration').value);
  const recording=job?job.saveRaw:$('record').checked;
  const recordingWav=job?Boolean(job.saveWav):$('wav-record').checked;
  const budget=captureBudget(limit,rate,recording,{fileStreaming:Boolean(prepared?.writable)});
  const wavBudget=wavOutputPlan(limit,recordingWav,{fileStreaming:Boolean(prepared?.wavWritable)});
  if(recordingWav&&wavBudget.mode==='disk-stream'&&!prepared?.wavWritable)
    throw Error("Long WAV recording requires an explicitly selected local disk file.");
  if(budget.mode==="disk-stream"&&!prepared?.writable)
    throw Error("No user-selected local CU8 disk stream for this extended capture.");
  stopRequested=false;
  const session=++sessionCounter;
  const captureStartTime=new Date();
  capturePromise=(async()=>{
    let bytesReceived=0,bytesRecorded=0,chunks=[],measured=null,peakCount=0;
    const fmWav=recordingWav?createStreamingFmWavEncoder(rate):null;
    const wavChunks=[];
    let wavWritten=false;
    async function finalizeWav(){
      if(!fmWav||wavWritten||fmWav.pcmBytes<2)return null;
      const name=prepared?.wavName||captureWavName(job,freq,captureStartTime);
      const header=fmWav.makeHeader();
      if(prepared?.wavWritable){
        await prepared.wavWritable.write({type:"write",position:0,data:header});
        await prepared.wavWritable.close();
        prepared.wavWritable=null;
        log("Saved real demodulated FM audio to "+name+" ("+
          (fmWav.pcmBytes/1048576).toFixed(2)+" MiB PCM). Open WAV in the Robot36 decoder.");
      }else{
        const blob=new Blob([header,...wavChunks],{type:"audio/wav"});
        triggerRawDownload(blob,name);
        satelliteImageUI?.recordAudioCapture(blob,name);
      }
      wavWritten=true;
      if(job)job.wavFileName=name;
      return {name,...fmWav.report()};
    }
    const measurements=[],startedAt=Date.now();
    const deadline=startedAt+limit*1000;
    try {
      if(job){
        job.state='running';
        job.message='USB opened. Tuning '+(freq/1e6).toFixed(3)+' MHz, measuring actual I/Q samples...';
        renderJobs();
      }
      await device.setSampleRate(rate);
      await device.setCenterFrequency(freq);
      await device.setGain(null);
      await device.resetBuffer();
      // RIFF/WAV headers are rewritten with the actual captured sample count
      // before closing the streamed local file. Never save fabricated audio.
      if(prepared?.wavWritable)await prepared.wavWritable.write(createPcmWavHeader(0));
      status('sample-state','Receiving real USB I/Q at '+(freq/1e6).toFixed(3)+' MHz · '+
        (rate/1e6)+' MS/s. Sample levels are uncalibrated. No satellite is identified.');
      while(!stopRequested && Date.now()<deadline){
        const raw=await device.readSamples(65536);
        // @jtarrio/webrtlsdr v3 returns SampleBlock {frequency,data,...}.
        // The previous ArrayBuffer-only code discarded every valid RF block.
        const data=sampleBytes(raw);
        if(data.length<2)throw Error('No usable I/Q bytes from RTL-SDR');
        bytesReceived+=data.length;
        measured=rmsLevel(data);
        if(Number.isFinite(measured)){
          measurements.push(measured);
          signalHistory.push(measured);
          if(signalHistory.length>150)signalHistory.shift();
          renderSignal();
        }
        if(fmWav){
          const pcm=fmWav.push(data);
          if(pcm.length){
            if(prepared?.wavWritable)await prepared.wavWritable.write(pcm);
            else wavChunks.push(pcm);
          }
        }
        if(recording){
          if(prepared?.writable){
            if(bytesRecorded+data.length>STREAM_IQ_BYTES)
              throw Error("2 GB stream safety limit exceeded before recording completed");
            await prepared.writable.write(new Uint8Array(data));
            bytesRecorded+=data.length;
          }else if(bytesRecorded+data.length>maxRecordBytes){
            throw Error("128 MiB buffer exceeded. Use streamed disk capture or lower the duration/sample rate.");
          }else{
            chunks.push(new Uint8Array(data));
            bytesRecorded+=data.length;
          }
        }
        status('sample-state','Measured USB bytes: '+(bytesReceived/1048576).toFixed(2)+
          ' MiB · relative sample level '+measured+
          ' dBFS-like · '+(freq/1e6).toFixed(3)+' MHz');
      }
      if(!bytesReceived)throw Error('Zero actual USB sample bytes received; no successful scan.');
      const report=captureLevelSummary(measurements,bytesReceived,Date.now()-startedAt);
      report.selectedOutputs={cu8:Boolean(recording),wav:Boolean(recordingWav)};
      report.wav=await finalizeWav();
      report.frequencyHz=freq;report.sampleRate=rate;report.rawBytes=bytesRecorded;
      report.recordedRaw=Boolean(recording&&bytesRecorded>0);
      report.time=new Date().toISOString();
      lastCaptured={bytesReceived,bytesRecorded,frequency_hz:freq,observedAt:report.time,
        relativeDb:report.averageRelativeDb};
      notifyMaps();
      let rawFileName=null,rawFileSavedToDisk=false;
      if(recording&&(chunks.length>0||prepared?.writable)){
        const name=prepared?.name||captureFileName(job,freq,rate,captureStartTime);
        rawFileName=name;rawFileSavedToDisk=Boolean(prepared?.writable);
        if(prepared?.writable){
          await prepared.writable.close();
          prepared.writable=null;
          if(job){job.fileName=name;job.downloadAvailable=false;}
          log("Saved "+(bytesRecorded/1e6).toFixed(1)+" MB of real CU8 IQ to chosen local disk file "+
            name+". Reopen the file explicitly for decoding/analysis.");
          status('sample-state',"Long RF sample saved to "+name+
            " · "+(bytesRecorded/1e6).toFixed(1)+" MB. Open from disk to analyze with suitable decoders.");
        }else saveCapture(chunks,name,job,{
          centerHz:freq,sampleRate:rate,format:"cu8",
          captureStartedUtc:captureStartTime.toISOString(),
          captureEndedUtc:new Date().toISOString(),
          complexSamples:Math.floor(bytesRecorded/2),
          receiverType:"RTL2832U-family / WebUSB",
          acquisition:"actual USB readSamples",gainMode:"automatic",rfSourceVerified:false
        });
      }
      const savedNames=[];
      if(rawFileName)savedNames.push('CU8: '+rawFileName+
        (rawFileSavedToDisk?' · saved on disk':' · browser download requested'));
      if(report.wav)savedNames.push('WAV: '+report.wav.name+
        (wavBudget.mode==='disk-stream'?' · saved on disk':' · browser download requested'));
      report.outputFiles=savedNames;
      status('sample-state','RF capture completed · '+outputSelectionText(recording,recordingWav)+
        '\n'+(savedNames.length?savedNames.join('\n'):'No output file selected.')+
        '\nA recorded WAV does not prove ISS/Robot36 synchronization. Check downloads or your chosen folder.');
      if(job){
        job.state=stopRequested?'stopped':'finished';
        job.report=report;
        job.message=(stopRequested?'Capture stopped early. ':'Capture completed. ')+
          (recording?(budget.mode==='disk-stream'?'CU8 saved to chosen disk. ':'Raw CU8 download requested. '):
             'Raw CU8 was not selected. ')+
          (recordingWav?(wavBudget.mode==='disk-stream'?'WAV saved to chosen disk. ':'FM WAV download requested. '):'')+
          'Uncalibrated RF power analysis only; no downlink or satellite identity confirmed.';
        status('scheduled-report',
          job.name+' · '+(freq/1e6).toFixed(3)+' MHz\n'+
          'Measured: '+report.bytesReceived.toLocaleString()+' real USB bytes in '+
          report.elapsedSeconds+' seconds. Sample blocks: '+report.blocksMeasured+
          '\nRelative digital level: min '+report.minRelativeDb+
          ', average '+report.averageRelativeDb+', max '+report.maxRelativeDb+
          ' dBFS-like; variation '+report.levelVariationDb+' dB.'+
          '\nThis is NOT a decoded satellite message/image or proof of which spacecraft transmitted.');
      }
      log('Session '+session+' captured '+bytesReceived+' real raw USB bytes; receiver released.');
    }catch(e){
      if(stopRequested&&fmWav?.pcmBytes>0&&!wavWritten){
        try{
          const partial=await finalizeWav();
          if(partial)log("Stopped early: partial real FM WAV preserved ("+partial.durationSeconds+" s).");
        }catch(error){log("Partial FM WAV save failed: "+error.message);}
      }
      if(prepared?.wavWritable){
        const stream=prepared.wavWritable;prepared.wavWritable=null;
        try{await stream.abort();}catch{}
      }
      // A deliberate Stop should preserve already received real RF bytes.
      // Unexpected driver/disk errors abort the uncommitted stream instead.
      if(prepared?.writable){
        if(stopRequested&&bytesRecorded>0){
          try{
            await prepared.writable.close();
            prepared.writable=null;
            log("Stopped early: saved partial real IQ ("+(bytesRecorded/1e6).toFixed(1)+
              " MB) to "+prepared.name+". The recording is incomplete.");
            status('sample-state',"Stopped early, but saved "+
              (bytesRecorded/1e6).toFixed(1)+" MB of partial CU8 data to "+prepared.name+
              ". Analyze only as partial RF evidence.");
            if(job){job.fileName=prepared.name;job.downloadAvailable=false;}
          }catch(saveError){
            log("Partial disk capture could not be finalized: "+saveError.message);
            await abortLongCapture(prepared);
          }
        }else await abortLongCapture(prepared);
      }
      log('Capture error: '+e.message);
      status('sample-state','Capture stopped/failed: '+e.message+'. No satellite decoding is claimed.');
      if(job){job.state=stopRequested?'stopped':'blocked';job.message=String(e.message);job.report=null;
        status('scheduled-report','Scheduled capture '+job.state+': '+e.message);}
    }finally{
      await closeDevice();
    }
  })();
  refreshControls();
  try{await capturePromise;}
  finally{capturePromise=null;refreshControls();renderJobs();}
}
async function stopCapture() {
  stopRequested=true;
  for(const job of jobs){
    if(job.state==='armed'&&String(job.chainId||'').startsWith('manual:')){
      job.state='cancelled';
      job.message='Remaining manual RF chain cancelled by Stop & release.';
    }
  }
  // Closing our own USB handle helps interrupt a stuck readSamples() transfer.
  await closeDevice();
  if(capturePromise){
    try{
      await Promise.race([capturePromise,new Promise(resolve=>setTimeout(resolve,2500))]);
    }catch(e){log('Receiver stop: '+e.message);}
  }
  status('device-status','RTL-SDR release requested. Only this tab-owned USB receiver was closed; unrelated readsb/Gqrx processes untouched.');
  refreshControls();
}
$('connect').addEventListener('click',()=>{void connectDevice();});
$('disconnect').addEventListener('click',()=>{void stopCapture();});
$('stop').addEventListener('click',()=>{void stopCapture();});
$('start').addEventListener('click',()=>{
 void (async()=>{
   let prepared=null;
   try{
     const totalSeconds=secondsFromEntry($('duration').value,$('duration-unit').value);
     const rate=Number($('rate').value),raw=$('record').checked,wav=$('wav-record').checked;
     const frequency=Number($('preset').value);
     if(totalSeconds>60||(raw&&totalSeconds*rate*2>maxRecordBytes)){
       if(!device)throw Error('Connect the RTL-SDR before scheduling manual consecutive captures.');
       const plan=planChainedCapture({startMs:Date.now()+1500,totalSeconds,rate,raw,wav});
       const groupId='manual:'+Date.now()+':'+String(++sessionCounter);
       const chain=plan.segments.map(seg=>({
         id:groupId+':'+seg.index,chainId:groupId,
         chainIndex:seg.index,chainTotal:plan.segments.length,
         chainCaptureTotal:totalSeconds,
         name:'Manual RF · unattributed',family:'manual',passId:'manual',
         when:seg.when,until:seg.end+6000,passAos:seg.when,passLos:seg.end+6000,
         frequency,sampleRate:rate,durationSeconds:seg.durationSeconds,
         saveRaw:raw,saveWav:wav,state:'armed',createdAt:Date.now(),
         estimatedBytes:seg.estimatedRawBytes+seg.estimatedWavBytes,
         message:'Manually requested part '+seg.index+'/'+plan.segments.length+
           '. Not a satellite pass. Browser must remain visible; RF gaps possible.'
       }));
       for(const job of chain){
         if(jobs.some(other=>['armed','starting','running'].includes(other.state)&&
           scheduledOverlap(job,other,{guardSeconds:0})))
           throw Error('A scheduled pass conflicts with this immediate recording chain.');
       }
       addBrowserChain(chain);
       status('sample-state','Armed '+chain.length+' consecutive manually requested WebUSB files · '+
         totalSeconds+' s total and '+plan.totalGapSeconds+
         ' s reserved gaps. See the reception calendar for every file; keep the tab visible. '+
         'Allow multiple browser downloads. No actual RF has been recorded yet.');
       log('Manual browser capture chain armed: '+chain.length+
         ' independent files. No continuous-stream guarantee.');
       void scheduledTick();
     }else{
       prepared=await selectRecordingFiles(totalSeconds,rate,raw,wav,
         {at:new Date(),freq:frequency});
       await startCapture(null,prepared);
     }
   }catch(error){
     if(prepared?.writable||prepared?.wavWritable)await abortLongCapture(prepared);
     status('sample-state','Capture not started: '+String(error?.message||error));
     log('Capture preflight: '+String(error?.message||error));
   }
 })();
});

navigator.usb?.addEventListener('disconnect',e=>{
  stopRequested=true;
  if(device)log('USB disconnection detected; receiving session is stopping.');
});
for (const [city,coords] of Object.entries(LOCATIONS)) void coords;
$('city').addEventListener('change',()=>{
  const pair=LOCATIONS[$('city').value];
  if(pair){
    const beforeLat=Number($('lat').value),beforeLon=Number($('lon').value);
    $('lat').value=pair[0];$('lon').value=pair[1];
    $('location-status').textContent='Preset: '+$('city').value+' · '+pair[0].toFixed(3)+'°, '+pair[1].toFixed(3)+'°. Recalculate passes for this location.';
    if(beforeLat!==pair[0]||beforeLon!==pair[1])$('lat').dispatchEvent(new Event('change',{bubbles:true}));
    invalidatePasses();
  }
});
function invalidatePasses(){
 if(passes.length){passes=[];renderPasses();}
 // A pass at another ground station is not the same schedule. Never run
 // stale geometry after GPS, offline city or custom coordinates change.
 let cancelled=0;
 for(const job of jobs){
   if(job.state==='armed'){
     releaseScheduledStream(job);
     job.state='cancelled';
     job.message='Ground station changed. Recalculate passes for the new location and schedule again.';
     cancelled++;
   }
 }
 if(cancelled){
   log('Cancelled '+cancelled+' future pass capture(s): station location changed.');
   status('schedule-readiness','Station changed: '+cancelled+
     ' old timed scan(s) cancelled. Recalculate and confirm new local pass times.');
   renderJobs();
 }
 notifyMaps();
}
function parseTle(text,source='uploaded') {
  const lines=String(text).replace(/\r/g,'').split('\n').map(l=>l.trim()).filter(Boolean);
  const matches=[];
  for(let i=0;i+1<lines.length;i++){
    if(!/^1 \d{5}/.test(lines[i]) || !/^2 \d{5}/.test(lines[i+1]))continue;
    if(lines[i].slice(2,7)!==lines[i+1].slice(2,7) || lines[i].length<60 || lines[i+1].length<60)continue;
    const id=Number(lines[i].slice(2,7));
    const name=i>0 && !/^[12] \d{5}/.test(lines[i-1]) ? lines[i-1].replace(/^0 /,''):'NORAD '+id;
    const family=source==='iss'||id===25544?'iss':source.startsWith('meteor')||/METEOR/i.test(name)?'meteor':
      source==='iridium'||/IRIDIUM/i.test(name)?'iridium':'cubesat';
    matches.push({id,name:name.slice(0,70),l1:lines[i],l2:lines[i+1],family});
  }
  return matches;
}
function boundedCatalog(records) {
  const caps={iss:1,meteor:3,cubesat:80,iridium:24},counts={},ids=new Set();
  const result=[];
  for(const obj of records){
    if(ids.has(obj.id))continue;
    const family=obj.family;
    if(!Object.prototype.hasOwnProperty.call(caps,family)|| (counts[family]||0)>=caps[family])continue;
    counts[family]=(counts[family]||0)+1;
    ids.add(obj.id);result.push(obj);
  }
  return result;
}
$('tle-file').addEventListener('change',async e=>{
  const file=e.target.files?.[0];
  if(!file)return;
  if(file.size>350000){status('orbit-state','TLE file exceeds 350 kB cap');return;}
  try{
    const text=await file.text();
    const rows=parseTle(text,'uploaded');
    if(!rows.length)throw Error('No valid two-line elements (TLE) found');
    let nativeNote='';
    if(typeof window.nativeImportTle==='function'){
      const saved=await window.nativeImportTle(text);
      nativeNote=' Native Skyfield cache updated ('+saved.count+' records); available for offline Earth/Sky and pass calculations.';
    }
    tleEntries=boundedCatalog([...rows,...tleEntries]);
    passes=[];visiblePassCount=40;renderPasses();
    notifyMaps();
    status('orbit-state','Imported '+rows.length+' valid TLE records locally; '+tleEntries.length+
      ' candidates selected.'+nativeNote+' These are orbital data, not received RF.');
  }catch(err){status('orbit-state','TLE import failed: '+err.message);}
});
$('saved-tle-fetch').addEventListener('click',async()=>{
  const button=$('saved-tle-fetch'),label=$('saved-tle-status');
  const records=readUserProfiles();
  const norads=[...new Set(records.map(p=>p.norad))];
  if(!norads.length){label.textContent='No saved custom NORAD transmitters. Add profiles from Images & Data first.';return;}
  const supported=norads.filter(id=>id>=1000&&id<=99999).slice(0,8);
  const skipped=norads.length-supported.length;
  if(!supported.length){
    label.textContent='The built-in TLE parser currently accepts five-digit NORAD IDs. For larger IDs, use an external tracker until OMM import is supported.';return;
  }
  button.disabled=true;
  let loaded=[],errors=[];
  try{
    label.textContent='Downloading orbital elements for '+supported.length+' user-selected public catalog numbers. No SDR opened…';
    // Bounded 3-way fanout with 8 s requests: avoid hammering public CelesTrak.
    for(let index=0;index<supported.length;index+=3){
      await Promise.all(supported.slice(index,index+3).map(async id=>{
        const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),8000);
        try{
          if(typeof window.nativeCustomTle==='function'){
            const answer=await window.nativeCustomTle(id);
            const rows=(answer.entries||[]).filter(p=>p.id===id);
            if(!rows.length)throw Error('No valid matching native TLE');
            loaded.push(...rows);
          }else{
            const uri='https://celestrak.org/NORAD/elements/gp.php?CATNR='+id+'&FORMAT=TLE';
            const result=await fetch(uri,{mode:'cors',cache:'no-store',signal:controller.signal});
            if(!result.ok)throw Error('HTTP '+result.status);
            const txt=await result.text();
            if(txt.length>70000)throw Error('TLE response oversized');
            const rows=parseTle(txt,'custom').filter(p=>p.id===id);
            if(!rows.length)throw Error('No valid matching TLE');
            loaded.push(...rows);
          }
        }catch(e){errors.push('NORAD '+id+': '+e.message);}
        finally{clearTimeout(timeout);}
      }));
    }
    if(loaded.length){
      // Saved, opt-in profiles should be visible ahead of generic CubeSat survey
      // rows but never overwrite the official ISS/Meteor identity.
      tleEntries=boundedCatalog([...loaded,...tleEntries]);
      passes=[];renderPasses();notifyMaps();
    }
    label.textContent='Loaded '+loaded.length+' verified-format TLE(s) for saved satellite IDs; '+
      skipped+' skipped (max 8 five-digit IDs). '+(errors.length?'Errors: '+errors.slice(0,3).join(' · '):'')+
      ' Click Calculate passes. The radio protocol is still USER-SUPPLIED and not independently verified.';
  }finally{button.disabled=false;}
});

async function refreshOrbitalCatalog(){
  if(tleEntries.length && lastTleFetchAt && Date.now()-lastTleFetchAt < 2*3600000) {
    status('orbit-state','Keeping '+tleEntries.length+' TLE candidates from this tab\'s recent download. CelesTrak GP data is not refreshed more often than every two hours.');
    return;
  }
  if(typeof window.nativeOrbitCatalog==='function'){
    status('orbit-state','Downloading CelesTrak orbit data with native HTTPS, then reading local TLE cache…');
    try{
      const answer=await window.nativeOrbitCatalog();
      const records=(answer.entries||[]).filter(item=>
        Number.isInteger(item.id)&&typeof item.l1==='string'&&
        typeof item.l2==='string'&&typeof item.name==='string'&&
        ['iss','meteor','cubesat','iridium'].includes(item.family));
      if(records.length){
        tleEntries=boundedCatalog(records);
        lastTleFetchAt=Date.now();
        passes=[];
        visiblePassCount=40;
        renderPasses();
        notifyMaps();
      }
      const diagnostics=(answer.warnings||[]).slice(0,4).join(' · ');
      status('orbit-state',records.length
        ? 'Native CelesTrak + disk cache: '+tleEntries.length+
          ' real TLE candidates ready. '+(diagnostics||'Orbit data received.')+
          ' Recalculate passes. Positions are orbital predictions, not received RF.'
        : 'Native CelesTrak returned no usable TLEs. '+(diagnostics||'Inspect HTTPS, local cache or import a .tle file.'));
    }catch(error){
      status('orbit-state','Native orbit refresh failed: '+String(error?.message||error)+
        '. Check computer HTTPS access or import a local TLE file.');
    }
    return;
  }
  status('orbit-state','Requesting whitelisted CelesTrak TLEs…');
  const results=[];
  const errors=[];
  for(const [name,url] of Object.entries(TLE_SOURCES)){
    const cancel=new AbortController();
    const timer=setTimeout(()=>cancel.abort(),10000);
    try{
      const response=await fetch(url,{mode:'cors',cache:'no-store',signal:cancel.signal});
      if(!response.ok)throw Error('HTTP '+response.status);
      const content=await response.text();
      if(content.length>350000)throw Error('Source TLE too large');
      const list=parseTle(content,name);
      if(!list.length)throw Error('No parseable TLEs');
      results.push(...list);
    }catch(err){errors.push(name+': '+err.message);}
    finally{clearTimeout(timer);}
  }
  if(results.length){tleEntries=boundedCatalog(results);lastTleFetchAt=Date.now();notifyMaps();}
  status('orbit-state',results.length ? 'Cached '+tleEntries.length+' client-side TLE candidates. '+(errors.join(' · ')||'All sources read') :
     'Browser could not read CelesTrak (possibly CORS/network). Import a .tle/.txt file manually. '+errors.join(' · '));
}
$('orbit-fetch').addEventListener('click',()=>{void refreshOrbitalCatalog();});
const rad = deg=>deg*Math.PI/180, deg=rad=>rad*180/Math.PI;
async function getOrbitalLibrary(){
  if(!orbitalLibrary)orbitalLibrary=await import('https://esm.sh/satellite.js@6.0.1?bundle');
  return orbitalLibrary;
}
function satElevation(satlib,rec,observer,date) {
  const state=satlib.propagate(rec,date);
  if(!state.position || !Number.isFinite(state.position.x))return null;
  const ecf=satlib.eciToEcf(state.position,satlib.gstime(date));
  const look=satlib.ecfToLookAngles(observer,ecf);
  if(!Number.isFinite(look.elevation))return null;
  const angle=deg(look.elevation);
  return angle>=-90&&angle<=90?angle:null;
}
function currentWindow(){
 if(!$('map-window-enabled')?.checked)return null;
 return validatedWindow({
  az:$('map-window-az').value,half:$('map-window-halfwidth').value,
  min:$('map-window-minel').value,max:$('map-window-maxel').value
 });
}
function assessBrowserWindow(satlib,rec,observer,pass,profile){
 if(!profile)return null;
 const records=[];
 for(let ms=pass.aos;ms<=pass.los;ms+=10000){
  const when=new Date(ms),state=satlib.propagate(rec,when);
  if(!state?.position||!Number.isFinite(state.position.x))continue;
  const look=satlib.ecfToLookAngles(observer,satlib.eciToEcf(
   state.position,satlib.gstime(when)));
  if(Number.isFinite(look.azimuth)&&Number.isFinite(look.elevation))
   records.push({ms,az:(deg(look.azimuth)+360)%360,el:deg(look.elevation)});
 }
 return windowSummary(records,profile);
}
function fmtTime(time){return new Date(time).toLocaleString(undefined,{dateStyle:'short',timeStyle:'short'});}
function scheduleFrequencyChoices(family,pass=null){
  const known={
    iss:[[145800000,"ISS VHF 145.800 MHz (voice/SSTV vicinity)"],
         [145825000,"ISS APRS 145.825 MHz (historical/alternate; check ARISS)"],
         [437825000,"ISS UHF APRS 437.825 MHz (verify current status)"],
         [437550000,"ISS SSTV Robot36 437.550 MHz (event-only)"],
         [437800000,"ISS UHF voice repeater 437.800 MHz"]],
    meteor:[[137900000,"Meteor LRPT 137.900 MHz"],[137100000,"Meteor LRPT 137.100 MHz alternate"]],
    cubesat:[[436000000,"CubeSat generic 436 MHz survey (NOT satellite-assigned downlink)"]],
    iridium:[[1620000000,"Iridium 1620 MHz L-band spectrum energy ONLY"]]
  };
  const options=[...(known[family]||[])];
  if(pass){
    for(const candidate of protocolsForPass(pass)){
      if(candidate.frequencyHz<24000000||candidate.frequencyHz>1750000000)continue;
      if(options.some(o=>o[0]===candidate.frequencyHz))continue;
      options.push([candidate.frequencyHz,
        (candidate.provenance==="user-supplied"?"USER-DEFINED · ":"Published · ")+
        candidate.protocol+" · "+(candidate.frequencyHz/1e6).toFixed(4)+" MHz"]);
    }
  }
  return options;
}
function appendPass(pass){
  const item=document.createElement('div');item.className='pass';
  // Harmless source metadata for native desktop scheduling; the displayed
  // pass still comes from genuine TLE geometry, not received RF evidence.
  item.dataset.norad=String(pass.id);
  item.dataset.aos=String(pass.aos);
  const strong=document.createElement('strong');strong.textContent=pass.name+' · '+pass.family.toUpperCase();
  const description=document.createElement('small');
  description.textContent=fmtTime(pass.aos)+' → '+fmtTime(pass.los)+
    ' · max elevation '+pass.maximum.toFixed(1)+'° · '+
    Math.max(1,Math.round((pass.los-pass.aos)/60000))+' min geometric pass (not an RF detection)';
  item.append(strong,description);
  if(pass.windowVisibility){
   const w=pass.windowVisibility;
   const chip=document.createElement('small');
   chip.className='pass-window-result '+String(w.status);
   chip.textContent=w.status==='outside'
    ?'Estimated window: no overlap'
    :'Estimated window: '+Math.round(w.seconds||0)+' s geometric exposure · '+
      (w.status==='good_geometry'?'longer potential reception window':
       w.status==='short_window'?'short reception opportunity':'very brief / difficult');
   chip.title='Only a modeled azimuth/elevation sector; cannot prove reception through a window.';
   item.append(chip);
  }
  const known=protocolsForPass(pass), kinds=protocolCategories(pass);
  if(kinds.length){
    const badges=document.createElement('div');badges.className='pass-capability-list';
    const names={image:'🖼 IMAGE',audio:'🔊 AUDIO',text:'✉ TEXT / DATA',video:'🎥 VIDEO'};
    for(const kind of kinds){
      const badge=document.createElement('span');badge.className='pass-capability pass-kind-'+kind;
      badge.textContent=names[kind];
      badge.title=known.some(p=>p.kind===kind&&p.provenance==='user-supplied')?'Contains a USER-SUPPLIED/UNVERIFIED profile; reception and decoder are not established.':'Published protocol candidate, NOT an active RF detection.';
      badges.append(badge);
    }
    item.append(badges);
    const more=document.createElement('details');more.className='pass-known-protocols';
    const toggle=document.createElement('summary');toggle.textContent='Published / user receiver profiles ('+known.length+')';
    more.append(toggle);
    for(const p of known){
      const row=document.createElement('p');
      row.textContent=p.protocol+' · '+(p.frequencyHz/1e6).toFixed(4)+' MHz · '+p.activity+
        ' · '+p.decoder+' — '+p.note;
      const link=document.createElement('a');link.href=p.source;
      link.target='_blank';link.rel='noopener noreferrer';link.textContent=p.provenance==='user-supplied'?'User-provided reference · not verified':'Published transmitter reference';
      row.append(document.createTextNode(' · '),link);more.append(row);
    }
    item.append(more);
  }else{
    const unknown=document.createElement('small');unknown.className='pass-no-known-protocol';
    unknown.textContent='No verified public image/audio/text decoder profile in local catalog';
    item.append(unknown);
  }
  const details=document.createElement('details');
  const summary=document.createElement('summary');summary.textContent='Schedule / configure timed RF analysis';
  details.append(summary);
  const form=document.createElement('form');form.className='pass-schedule-form';
  const fields=[
    ['Run date + minute (local time)','when','datetime-local',localDateInput(Math.max(Date.now()+60000,pass.aos))],
  ];
  const timeLabel=document.createElement('label');
  timeLabel.textContent='Run at local date / hour / minute ('+(Intl.DateTimeFormat().resolvedOptions().timeZone||'device timezone')+')';
  const input=document.createElement('input');
  input.type='datetime-local';input.step='60';
  input.required=true;input.value=fields[0][3];
  timeLabel.append(input);
  const frequencyLabel=document.createElement('label');frequencyLabel.textContent='Receiver frequency';
  const frequency=document.createElement('select');
  for(const [hz,name] of scheduleFrequencyChoices(pass.family,pass)){
    const o=document.createElement('option');o.value=String(hz);o.textContent=name;frequency.append(o);
  }
  frequencyLabel.append(frequency);
  const durationLabel=document.createElement('label');
  durationLabel.textContent='Actual RF sample length · manual seconds';
  const duration=document.createElement('input');
  duration.type='number';duration.min='1';duration.max='7200';duration.step='1';
  duration.inputMode='numeric';duration.value='60';duration.required=true;
  durationLabel.append(duration);
  const unitLabel=document.createElement('label');unitLabel.textContent='Length unit';
  const lengthUnit=document.createElement('select');
  lengthUnit.innerHTML='<option value="seconds">Seconds</option><option value="minutes">Minutes</option>';
  unitLabel.append(lengthUnit);
  const rateLabel=document.createElement('label');rateLabel.textContent='Sample rate';
  const rate=document.createElement('select');
  for(const hz of [1024000,2048000]){
    const o=document.createElement('option');o.value=String(hz);o.textContent=(hz/1e6)+' MS/s';
    rate.append(o);
  }
  rateLabel.append(rate);
  const saveLabel=document.createElement('label');saveLabel.className='schedule-wide check';
  const raw=document.createElement('input');raw.type='checkbox';raw.checked=true;
  saveLabel.append(raw,' Record original unsigned I/Q (.cu8).');
  const wavLabel=document.createElement('label');wavLabel.className='schedule-wide check';
  const wav=document.createElement('input');wav.type='checkbox';
  wav.checked=Number(frequency.value)===437550000;
  if(wav.checked)raw.checked=false;
  wavLabel.append(wav,' Record real FM-demodulated audio (.wav, mono PCM 48 kHz), suitable for Robot36 analysis.');
  const updateNativeFormat=()=>{
    if(!nativeReceiver())return;
    const hz=Number(frequency.value);
    const supportsAudio=pass.family==="iss"&&[145800000,437550000,437800000].includes(hz);
    wav.disabled=!supportsAudio;
    if(!supportsAudio){wav.checked=false;raw.checked=true;}
    wavLabel.title=supportsAudio
      ?"Optional ISS FM audio for this native receiving profile."
      :"Unavailable for this RF profile. Meteor LRPT must be saved as raw IQ.";
    localLink.hidden=true;
    explanation.textContent="Native RTL-SDR: continuous direct-to-disk capture up to 900 s / "+
      "2 GB if the requested window fits the predicted pass. No WebUSB and no 60-second "+
      "browser segmentation. Keep the application open and prevent OS sleep.";
  };
  frequency.addEventListener('change',()=>{
    const iss=Number(frequency.value)===437550000;
    wav.checked=iss;raw.checked=!iss;updateNativeFormat();refreshBudget();
  });
  const localLink=document.createElement('a');
  localLink.className="iq-jump-link schedule-wide";
  localLink.href="http://127.0.0.1:8791/browser/index.html";
  localLink.rel="noopener noreferrer";localLink.target="_blank";
  localLink.textContent="Debian / Firefox alternative: use the local RTL-SDR app (no WebUSB or browser file limit)";
  const explanation=document.createElement('p');explanation.className='hint schedule-wide';
  explanation.textContent='Choose seconds or minutes. WebUSB recordings over 60 seconds (or the 128 MiB RAM cap) are automatically split into independent <=60 s files with 6-second reserved gaps. The calendar displays every part. This is not continuous I/Q: USB reopen/download can add gaps. A visible awake Chromium tab and prior RTL-SDR permission are still required.';
  const alert=document.createElement('p');alert.className='pass-schedule-error schedule-wide';alert.setAttribute('role','status');
  const confirm=document.createElement('button');confirm.type='submit';confirm.textContent='Confirm scheduled RF scan';
  const planOnly=document.createElement('button');planOnly.type='button';
  planOnly.className='secondary';planOnly.textContent='Add planning candidate · no antenna';
  planOnly.title='TLE-only calendar plan, never touches USB or starts any recording';
  planOnly.onclick=()=>planCandidate(pass);
  const budgetLabel=document.createElement('p');
  budgetLabel.className='schedule-capture-budget schedule-wide';
  budgetLabel.setAttribute('role','status');
  const refreshBudget=()=>{
    try{
      const total=secondsFromEntry(duration.value,lengthUnit.value);
      if(nativeReceiver()){
        const bytes=2*Number(rate.value)*total*(raw.checked?1:0)+96000*total*(wav.checked?1:0);
        budgetLabel.textContent=total<=900
          ?"Native direct-to-disk: one continuous "+total+" s capture · "+
            (bytes/1e6).toFixed(1)+" MB estimated · no WebUSB 60 s segmentation. "+
            (bytes>2e9?"EXCEEDS 2 GB cap. ":"")+
            "Capture must fit the native TLE-defined pass and LOS margin."
          :"Native long capture: "+total+" s exceeds the single 900 s limit. "+
            "Native segments with receiver restart gaps must fit before LOS; no WebUSB.";
        return;
      }
      const plan=planChainedCapture({startMs:Date.now()+60000,totalSeconds:total,
        rate:Number(rate.value),raw:raw.checked,wav:w.checked});
      budgetLabel.textContent=plan.segments.length+' separate calendar recording(s) · '+
        total+' s captured over '+plan.elapsedSeconds+' s · '+
        (plan.segments.reduce((n,x)=>n+x.estimatedRawBytes+x.estimatedWavBytes,0)/1e6).toFixed(1)+
        ' MB total · up to '+plan.segments[0].durationSeconds+
        ' s/part. No large RAM buffer or file picker. Downloads require browser permission. '+plan.warning;
    }catch(error){budgetLabel.textContent=String(error?.message||error);}
  };
  for(const element of [duration,rate,raw,wav,lengthUnit])element.addEventListener('change',refreshBudget);
  duration.addEventListener('input',refreshBudget);rate.addEventListener('input',refreshBudget);
  updateNativeFormat();
  refreshBudget();
  form.append(timeLabel,frequencyLabel,durationLabel,unitLabel,rateLabel,saveLabel,wavLabel,budgetLabel,localLink,explanation,alert,planOnly,confirm);
  form.addEventListener('submit',async event=>{
    event.preventDefault();
    let prepared=null;
    confirm.disabled=true;
    try{
      const selectedTime=parseLocalScheduleTime(input.value);
      const seconds=secondsFromEntry(duration.value,lengthUnit.value),chosenRate=Number(rate.value);
      if(nativeLocal()){
        const job=await nativeScheduledPass(pass,{
          when:selectedTime,durationSeconds:seconds,frequency:Number(frequency.value),
          sampleRate:chosenRate,saveRaw:raw.checked,saveWav:wav.checked
        });
        alert.textContent=job.scheduled_count?
          "Native companion: "+job.scheduled_count+" separate calendar files queued · "+
          seconds+" s of radio recording / "+job.elapsed_seconds+
          " s with "+job.total_gap_seconds+" s reserved gaps. "+
          "The native scheduler remains active while the app runs; data is not gap-free.":
          "Native companion: "+job.satellite+" · "+new Date(job.run_at).toLocaleString()+
          " · "+job.capture_seconds+" s scheduled. Keep native receiver running.";
        log("Native "+(job.scheduled_count||1)+" scheduled RF file(s) armed; RTL-SDR idle until start.");
        return;
      }
      const totalSeconds=secondsFromEntry(duration.value,lengthUnit.value);
      const chain=buildBrowserChain(pass,{when:selectedTime,totalSeconds,
        rate:chosenRate,frequency:Number(frequency.value),raw:raw.checked,wav:wav.checked});
      addBrowserChain(chain.jobs);
      alert.textContent='Scheduled '+chain.jobs.length+' sequential RF files · '+
        totalSeconds+' s recording / '+chain.plan.elapsedSeconds+
        ' s including '+chain.plan.totalGapSeconds+
        ' s reserved gaps. First '+fmtTime(chain.jobs[0].when)+
        ', last '+fmtTime(chain.jobs[chain.jobs.length-1].when+chain.jobs[chain.jobs.length-1].durationSeconds*1000)+
        '. See the calendar; keep this tab visible. Browser downloads may require permission.';
      log('Operator armed '+chain.jobs.length+' independent CU8/WAV jobs for '+pass.name+
        '; no radio has been claimed. '+chain.plan.warning);
      renderJobs();
      if(device&&!capturePromise){
        await closeDevice(); // do not monopolize USB while waiting
        status('device-status','USB released after scheduling. Tab must remain open and foreground.');
      }
      document.getElementById('schedule-center')?.scrollIntoView({behavior:'smooth',block:'nearest'});
    }catch(error){
      if(prepared?.writable||prepared?.wavWritable)await abortLongCapture(prepared);
      alert.textContent='Could not schedule: '+String(error?.message||error)+
        (nativeLocal()?'':'. In Firefox open the Debian native app on http://127.0.0.1:8791/browser/index.html to record without WebUSB/File System Access.');
    }finally{confirm.disabled=false;}
  });
  details.append(form);item.append(details);
  return item;
}
// TLE-only calendar plans never claim a receiver or arm a capture job.
let planningCandidates=readPlanningCandidates();
function planCandidate(pass){
 try{
  const entry=candidateFromPass(pass,{observer:{lat:Number($('lat').value),lon:Number($('lon').value)}});
  planningCandidates=savePlanningCandidate(entry);
  if($('browser-calendar-date'))
   $('browser-calendar-date').value=localDayKey(new Date(entry.aos));
  renderPredictedPassCalendar();
  const connected=Boolean(device||window.nativeHardwareState?.verified);
  status('candidate-hardware-warning',connected
   ?'Planning candidate saved only: no recording is armed. Use the real RF scheduler separately.'
   :'⚠ Antenna not connected/verified. Planning candidate saved only; NOTHING will record until a real receiver is connected and an RF job armed.');
  log('Saved planning-only TLE candidate '+entry.name+
   ' at '+new Date(entry.aos).toLocaleString()+' · no USB or RF scheduling.');
  return entry;
 }catch(error){
  status('candidate-hardware-warning','Cannot save planning candidate: '+String(error?.message||error));
  return null;
 }
}
function renderPlanningCandidates(){
 const list=$('candidate-calendar-list');if(!list)return;
 list.replaceChildren();
 const day=$('browser-calendar-date')?.value||localDayKey(new Date());
 const rows=planningCandidates.filter(x=>localDayKey(new Date(x.aos))===day);
 $('candidate-count').textContent=planningCandidates.length+' planned · not recording';
 if(!rows.length){
  const hint=document.createElement('p');hint.className='hint';
  hint.textContent='No planning candidates for this day. Add a predicted satellite pass even with no antenna.';
  list.append(hint);return;
 }
 for(const p of rows){
  const card=document.createElement('div');card.className='candidate-pass-card';
  const title=document.createElement('strong');title.textContent=p.name+' · NORAD '+p.norad;
  const meta=document.createElement('small');
  meta.textContent=new Date(p.aos).toLocaleTimeString()+' – '+
   new Date(p.los).toLocaleTimeString()+' · orbital estimate · NOT armed/recording'+
   (p.observer?' · station '+p.observer.lat.toFixed(3)+', '+p.observer.lon.toFixed(3):'');
  const remove=document.createElement('button');remove.type='button';remove.className='secondary';
  remove.textContent='Remove plan';
  remove.onclick=()=>{planningCandidates=removePlanningCandidate(p.id);renderPlanningCandidates();};
  card.append(title,meta,remove);list.append(card);
 }
}
let passRenderDeferred=false;
$('passes').addEventListener('focusout',()=>{
  queueMicrotask(()=>{
    if(passRenderDeferred&&!$('passes').contains(document.activeElement))renderPasses();
  });
});
function renderPasses(){
  const target=$('passes'),sort=$('pass-sort').value,family=$('pass-family').value,contentKind=$('pass-content').value;
  // Defer protocol/catalog redraw until native select popup has closed.
  if(target.contains(document.activeElement)&&
     document.activeElement.matches?.('select,input,textarea')){
    passRenderDeferred=true;return;
  }
  passRenderDeferred=false;
  target.replaceChildren();
  const baseItems=passesFilteredByContent(sortPassList(passes,sort,family),contentKind);
  const sectorFilter=$('pass-window-filter')?.value||'all';
  const enabled=Boolean($('map-window-enabled')?.checked);
  const items=sectorFilter==='all'||!enabled?baseItems:baseItems.filter(p=>
    sectorFilter==='usable'?p.windowVisibility?.seconds>=60:
    p.windowVisibility?.status!=='outside'&&p.windowVisibility!=null);
  const eligible=baseItems.filter(p=>(p.windowVisibility?.seconds||0)>=60).length;
  const count=$('window-filter-count');
  if(count)count.textContent=enabled?
    eligible+' / '+baseItems.length+' shown candidates have ≥60 s estimated window exposure. '+
      (sectorFilter==='all'?'All passes shown.':'Window-only filter active.')+
      ' Buildings and radio activity remain unknown.':
    'Window profile OFF — all orbital passes shown; enable the sector above to evaluate geometry.';
  const shown=items.slice(0,visiblePassCount);
  $('pass-list-count').textContent='Showing '+shown.length+' of '+items.length+
    ' matches ('+passes.length+' total computed passes).';
  const more=$('pass-show-more');
  more.hidden=shown.length>=items.length;more.textContent='Show more passes ('+(items.length-shown.length)+' remaining)';
  if(!items.length){
    target.append(Object.assign(document.createElement('p'),{
      className:'hint',textContent:passes.length?'No passes match the selected satellite filter.':'Calculate potential passes first.'
    }));
    renderPredictedPassCalendar();
    window.dispatchEvent(new Event('tihulu-passes-updated'));
    return;
  }
  const fragment=document.createDocumentFragment();
  for(const pass of shown)fragment.append(appendPass(pass));
  target.append(fragment);
  renderPredictedPassCalendar();
  window.dispatchEvent(new Event('tihulu-passes-updated'));
}
function renderPredictedPassCalendar(){
 renderPlanningCandidates();
 const node=$('predicted-pass-calendar-grid');
 if(!node)return;
 node.replaceChildren();
 const day=$('browser-calendar-date')?.value||localDayKey(new Date());
 const filter=$('pass-window-filter')?.value||'all';
 const enabled=Boolean($('map-window-enabled')?.checked);
 const items=passes.filter(p=>p.los>p.aos&&
  (localDayKey(new Date(p.aos))===day||
   localDayKey(new Date(p.los-1))===day)).filter(p=>
    !enabled||filter==='all'||(filter==='usable'
     ?(p.windowVisibility?.seconds||0)>=60
     :p.windowVisibility!=null&&p.windowVisibility.status!=='outside'
    )).sort((a,b)=>a.aos-b.aos);
 if(!items.length){
  const p=document.createElement('p');p.className='hint';
  p.textContent=passes.length
   ?'No predicted passes fall on this selected day. Change the calendar date.'
   :'No orbital predictions yet. Click Calculate passes first; the receiver is not needed.';
  node.append(p);return;
 }
 for(const pass of items.slice(0,50)){
  const card=document.createElement('div');card.className='predicted-pass-card';
  const name=document.createElement('strong');name.textContent=pass.name;
  const meta=document.createElement('small');
  meta.textContent=new Date(pass.aos).toLocaleString(undefined,{hour:"2-digit",minute:"2-digit"})+
   ' – '+new Date(pass.los).toLocaleString(undefined,{hour:"2-digit",minute:"2-digit"})+
   ' local · maximum '+pass.maximum.toFixed(1)+'° · '+pass.family.toUpperCase()+
   (pass.windowVisibility?
     ' · window '+(pass.windowVisibility.seconds||0)+' s ('+
     String(pass.windowVisibility.status||'unrated').replaceAll('_',' ')+')':'');
  const preview=document.createElement('button');preview.type='button';
  preview.textContent='Preview sky / ground track';
  preview.addEventListener('click',()=>{
   if(!satelliteMaps?.showPassPreview){
    preview.textContent='Map module unavailable';return;
   }
   preview.disabled=true;
   satelliteMaps.showPassPreview(pass).then(()=>{
    $('satellite-tracking-maps').scrollIntoView({behavior:'smooth',block:'start'});
   }).catch(err=>{
    $('map-pass-summary').textContent='Preview failed: '+String(err?.message||err);
   }).finally(()=>{preview.disabled=false;});
  });
  const add=document.createElement('button');add.type='button';
  add.className='secondary';add.textContent='Add to planning calendar';
  add.title='Save a TLE-only opportunity with no SDR or RF scheduler';
  add.onclick=()=>planCandidate(pass);
  card.append(name,meta,preview,add);node.append(card);
 }
 if(items.length>50){
  const note=document.createElement('p');note.className='hint';
  note.textContent='Showing the first 50 of '+items.length+' geometric passes on this day.';
  node.append(note);
 }
}
window.addEventListener('storage',event=>{
 if(event.key==='tihulu-satellite-user-downlinks-v1'){visiblePassCount=40;renderPasses();}
});
window.addEventListener('tihulu-profiles-changed',()=>{
 visiblePassCount=40;renderPasses();
});
for(const id of ['pass-sort','pass-family','pass-content']){
  $(id).addEventListener('change',()=>{visiblePassCount=40;renderPasses();});
}
$('pass-show-more').addEventListener('click',()=>{visiblePassCount+=40;renderPasses();});
async function calculateOrbitalPasses(){
  // Calculate passes is an explicit user action: native desktop can refresh
  // its orbit cache on demand without requiring a separate prerequisite click.
  if(!tleEntries.length)await refreshOrbitalCatalog();
  if(!tleEntries.length){
    status('orbit-state','No valid TLE catalog: check native HTTPS/cache or import a local TLE file.');
    return;
  }
  const lat=Number($('lat').value),lon=Number($('lon').value),hours=Number($('hours').value),minimum=Number($('elev').value);
  let windowProfile;
  try{windowProfile=currentWindow();}
  catch(error){status('orbit-state','Invalid window sector: '+error.message);return;}
  if(!$('lat').value.trim()||!$('lon').value.trim()||!Number.isFinite(lat)||!Number.isFinite(lon)||lat<-90||lat>90||lon<-180||lon>180){status('orbit-state','Enter valid latitude (−90…90) and longitude (−180…180) before calculating passes.');return;}
  if(typeof window.nativeOrbitPasses==='function'){
    status('orbit-state','Calculating genuine orbital passes with native Skyfield (no USB or browser CDN)…');
    try{
      const answer=await window.nativeOrbitPasses(lat,lon,hours,minimum,windowProfile);
      const found=(answer.predictions||[]).map(row=>({
        id:Number(row.norad),name:String(row.name||'NORAD '+row.norad),
        family:String(row.family||'cubesat'),
        aos:Date.parse(row.aos),los:Date.parse(row.los),
        maximum:Number(row.max_elevation_deg),
        windowVisibility:row.window_visibility||null,
        tleSource:row.tle_source||'native Skyfield TLE'
      })).filter(row=>Number.isInteger(row.id)&&Number.isFinite(row.aos)&&
        Number.isFinite(row.los)&&Number.isFinite(row.maximum)&&row.los>row.aos);
      found.sort((a,b)=>a.aos-b.aos);
      passes=found;
      visiblePassCount=40;
      renderPasses();
      notifyMaps();
      const warns=(answer.warnings||[]).slice(0,2).join(' · ');
      status('orbit-state','Native Skyfield calculated '+found.length+
        ' geometric passes for '+lat.toFixed(3)+', '+lon.toFixed(3)+
        '. '+warns+' No satellite radio signals claimed.');
    }catch(error){
      status('orbit-state','Native orbit calculation failed: '+String(error?.message||error)+
        '. Verify locally cached TLE data and Python Skyfield installation.');
    }
    return;
  }
  status('orbit-state','Computing geometry locally in this browser (no RF reception implied)…');
  try{
    const satlib=await getOrbitalLibrary();
    const observer={longitude:rad(lon),latitude:rad(lat),height:0};
    const start=Date.now(),end=start+hours*3600000,step=30000;
    const found=[];
    for(const item of tleEntries.slice(0,100)){
      const rec=satlib.twoline2satrec(item.l1,item.l2);
      let current=null;
      for(let t=start;t<=end;t+=step){
        const el=satElevation(satlib,rec,observer,new Date(t));
        const above=el!==null&&el>=minimum;
        if(above){
          if(!current)current={id:item.id,name:item.name,family:item.family,aos:t,maximum:el};
          current.maximum=Math.max(current.maximum,el);
        }else if(current){
          current.los=t;
          if(current.maximum>=minimum&&current.maximum<=90){
           if(windowProfile)current.windowVisibility=assessBrowserWindow(
             satlib,rec,observer,current,windowProfile);
           found.push(current);
          }
          current=null;
        }
      }
    }
    found.sort((a,b)=>a.aos-b.aos);
    passes=found; // retain all calculated passes so "latest date" is truthful
    visiblePassCount=40;
    renderPasses();
    notifyMaps();
    status('orbit-state','Calculated '+found.length+' geometric passes from '+tleEntries.length+' TLE candidates at '+lat.toFixed(3)+', '+lon.toFixed(3)+
      (windowProfile?'. Window-sector geometric exposure assessed for each pass.':'. No window filter active.')+
      '. Approximate 30-second resolution; no satellite signals identified.');
  }catch(err){status('orbit-state','Orbit computation failed: '+err.message+'. Check browser connectivity to the JS library CDN.');}
}
$('orbit-calc').addEventListener('click',()=>{void calculateOrbitalPasses();});
$('pass-window-filter').addEventListener('change',renderPasses);
for(const id of ['map-window-enabled','map-window-az','map-window-halfwidth',
                 'map-window-minel','map-window-maxel']){
 $(id).addEventListener('change',()=>{
  status('orbit-state','Window settings changed: click Calculate passes to rescore every satellite.');
  if(!$('map-window-enabled').checked)$('pass-window-filter').value='all';
  renderPasses();
 });
}
function readableJobState(job,now=Date.now()){
 if(job.state!=='armed')return job.state;
 const action=evaluateScheduledJob(job,now,{visible:!document.hidden,receiverBusy:!!capturePromise||usbTestRunning});
 if(action==='waiting-foreground')return 'due / waiting for visible tab';
 if(action==='waiting-receiver')return 'due / waiting for free receiver';
 if(action==='start')return 'due now';
 if(action==='missed')return 'expired';
 return 'armed / '+humanCountdown(secondsToJob(job,now))+' remaining';
}
let browserCalendarSignature="";
let nativeScheduledJobs=[];
const nativeMode=()=>typeof window.nativeScheduleStatus==="function";
const browserCalendarDay=$('browser-calendar-date');
browserCalendarDay.value=localDayKey(new Date());
function showCalendarEdit(job,card){
 if(job.state!=='armed')return;
 const existing=card.querySelector('.calendar-edit');
 if(existing){existing.remove();return;}
 const form=document.createElement('form');form.className='calendar-edit';
 const addField=(name,control)=>{
   const label=document.createElement('label');label.textContent=name;label.append(control);form.append(label);
 };
 const time=document.createElement('input');time.type='datetime-local';
 time.required=true;time.value=localDateInput(job.when);
 addField('Start · device local time',time);
 const freq=document.createElement('select');
 const choices=scheduleFrequencyChoices(job.family,{id:job.passId});
 if(!choices.some(v=>v[0]===job.frequency))choices.unshift([job.frequency,'Current: '+(job.frequency/1e6).toFixed(3)+' MHz']);
 for(const [hz,name] of choices){
   if(hz<24000000||hz>1750000000)continue;
   const o=document.createElement('option');o.value=String(hz);o.textContent=name;freq.append(o);
 }
 freq.value=String(job.frequency);addField('Known downlink frequency',freq);
 const seconds=document.createElement('input');seconds.type='number';
 seconds.min='1';seconds.max='7200';seconds.step='1';seconds.inputMode='numeric';
 seconds.value=String(job.chainId?job.chainCaptureTotal:job.durationSeconds);
 addField('Total RF capture length',seconds);
 const unit=document.createElement('select');
 unit.innerHTML='<option value="seconds">Seconds</option><option value="minutes">Minutes</option>';
 addField('Length unit',unit);
 const rate=document.createElement('select');
 for(const value of [1024000,2048000]){
   const o=document.createElement('option');o.value=String(value);o.textContent=(value/1e6).toFixed(3)+' MS/s';rate.append(o);
 }
 rate.value=String(job.sampleRate);addField('Sample rate',rate);
 const rawToggle=document.createElement('input');rawToggle.type='checkbox';rawToggle.checked=Boolean(job.saveRaw);
 addField('Record raw CU8',rawToggle);
 const wavToggle=document.createElement('input');wavToggle.type='checkbox';wavToggle.checked=Boolean(job.saveWav);
 addField('Record real FM WAV (48 kHz PCM)',wavToggle);
 const note=document.createElement('p');note.className='hint';
 note.textContent='Editing one part of a chained recording replaces all future armed parts of that chain. WebUSB clips automatically split into <=60 s files and allow 6-second gaps. These are separate files, NOT uninterrupted RF.';
 form.append(note);
 const save=document.createElement('button');save.type='submit';save.textContent='Save job changes';form.append(save);
 const error=document.createElement('p');error.className='status';error.setAttribute('role','status');form.append(error);
 form.addEventListener('submit',async event=>{
   event.preventDefault();save.disabled=true;
   let newPrepared=null;
   try{
     const totalSeconds=secondsFromEntry(seconds.value,unit.value),
           sampleRate=Number(rate.value);
     const pass={id:job.passId,name:job.name,family:job.family,
       aos:job.passAos,los:job.passLos};
     const oldGroup=jobs.filter(x=>x.id===job.id||
       (job.chainId&&x.chainId===job.chainId&&x.state==='armed'));
     if(oldGroup.some(x=>x.state!=='armed'))
       throw Error('A chained part has already started; cancel remaining parts and create a new schedule.');
     const chain=buildBrowserChain(pass,{
       when:parseLocalScheduleTime(time.value),totalSeconds,rate:sampleRate,
       frequency:Number(freq.value),raw:rawToggle.checked,wav:wavToggle.checked,
       excludeIds:oldGroup.map(x=>x.id)});
     for(const old of oldGroup){releaseScheduledStream(old);old.state='cancelled';
       old.message='Replaced by edited recording chain.';}
     const mission=Object.entries(AUTO_TARGETS).find(([_,x])=>
       x.frequencyHz===Number(freq.value)&&x.norad===Number(job.passId));
     for(const next of chain.jobs)next.missionId=mission?.[0]||undefined;
     addBrowserChain(chain.jobs);
     form.remove();
     browserCalendarSignature='';renderJobs();
     status('schedule-readiness','Replaced '+oldGroup.length+
       ' pending job(s) with '+chain.jobs.length+' parts · '+totalSeconds+
       ' s of RF and '+chain.plan.totalGapSeconds+
       ' s reserved inter-part gaps. Browser must remain visible.');
   }catch(error){
     if(newPrepared?.writable||newPrepared?.wavWritable)await abortLongCapture(newPrepared);
     error.textContent='Changes not saved: '+String(error?.message||error);
   }finally{save.disabled=false;}
 });
 card.append(form);
}
function paintBrowserCalendar(force=false){
 const day=browserCalendarDay.value;
 const source=nativeMode()?nativeScheduledJobs:jobs;
 const signature=day+'|'+source.map(j=>[
   j.id,j.run_at??j.when,j.state,j.capture_seconds??j.durationSeconds,j.result
 ].join(':')).join('|');
 const editingCard=$('browser-calendar-grid').querySelector('.calendar-edit')?.closest('.sat-calendar-job');
 const editedJob=jobs.find(j=>j.id===editingCard?.dataset.jobId);
 if(!force&&!nativeMode()&&editingCard&&editedJob?.state==='armed')return;
 if(!force&&signature===browserCalendarSignature)return;
 browserCalendarSignature=signature;
 renderSatelliteCalendar($('browser-calendar-grid'),source,day,{
   onEdit:nativeMode()?null:showCalendarEdit,
   onCancel:job=>{
    if(nativeMode()){
     if(!window.nativeCancelScheduledJob)return;
     window.nativeCancelScheduledJob(String(job.id)).then(()=>{
      void syncNativeScheduler();
     }).catch(err=>{
      $('schedule-readiness').textContent='Native cancellation failed: '+String(err?.message||err);
     });return;
    }
     if(job.state==='armed'){
       for(const related of jobs.filter(j=>j.id===job.id||(job.chainId&&j.chainId===job.chainId))){
         if(related.state!=='armed')continue;
         releaseScheduledStream(related);
         related.state='cancelled';related.message='Cancelled by operator with recording chain. No RF capture started.';
       }
       browserCalendarSignature='';renderJobs();
     }
   }
 });
}
browserCalendarDay.addEventListener('change',()=>{
 paintBrowserCalendar(true);renderPredictedPassCalendar();
});
$('browser-calendar-prev').addEventListener('click',()=>{
 browserCalendarDay.value=shiftCalendarDay(browserCalendarDay.value,-1);
 paintBrowserCalendar(true);renderPredictedPassCalendar();
});
$('browser-calendar-next').addEventListener('click',()=>{
 browserCalendarDay.value=shiftCalendarDay(browserCalendarDay.value,1);
 paintBrowserCalendar(true);renderPredictedPassCalendar();
});

function renderNativeJobCards(){
 const container=$('jobs');
 container.replaceChildren();
 if(!nativeScheduledJobs.length){
  const empty=document.createElement('p');empty.className='hint';
  empty.textContent='No native RF recordings scheduled. Predicted passes appear in the orbital calendar below, not as recorded data.';
  container.append(empty);
 }else for(const job of [...nativeScheduledJobs].reverse().slice(0,40)){
  const card=document.createElement('div');card.className='scheduled-job';
  const title=document.createElement('h4');
  title.textContent=String(job.satellite||'Unknown satellite')+' · '+String(job.state||'unknown').toUpperCase();
  const meta=document.createElement('p');
  const hz=job.profile==='meteor'||job.profile==='meteor_backup'
   ?job.profile==='meteor'?137.900:137.100:null;
  meta.textContent='Native OS job · start '+new Date(job.run_at||job.aos).toLocaleString()+
   ' · '+Number(job.capture_seconds||0)+' s'+
   (hz?' · '+hz.toFixed(3)+' MHz':'')+
   ' · '+String(job.mode||'unknown')+
   ' · '+(job.estimated_bytes?(job.estimated_bytes/1e6).toFixed(1)+' MB estimated':'');
  card.append(title,meta);
  if(job.result){
   const detail=document.createElement('p');detail.className='hint';
   detail.textContent=typeof job.result==='string'?job.result:
    job.result.file?'Saved '+job.result.file+' · '+job.result.bytes+' actual bytes':
    JSON.stringify(job.result).slice(0,350);
   card.append(detail);
  }
  if(job.state==='pending'&&window.nativeCancelScheduledJob){
   const cancel=document.createElement('button');cancel.className='secondary';cancel.type='button';
   cancel.textContent='Cancel native job';
   cancel.addEventListener('click',()=>{
    cancel.disabled=true;
    window.nativeCancelScheduledJob(String(job.id))
     .then(()=>syncNativeScheduler()).catch(err=>{
      $('schedule-readiness').textContent='Cancellation failed: '+err.message;
      cancel.disabled=false;
     });
   });card.append(cancel);
  }
  container.append(card);
 }
 paintBrowserCalendar(true);
}
let nativeSyncRunning=false;
async function syncNativeScheduler(){
 if(!nativeMode()||nativeSyncRunning)return;
 nativeSyncRunning=true;
 try{
  const data=await window.nativeScheduleStatus();
  nativeScheduledJobs=Array.isArray(data?.jobs)?data.jobs:[];
  renderNativeJobCards();
  const heading=$('browser-calendar-title');
  if(heading)heading.textContent='Native reception calendar · actual scheduled RF jobs';
  const help=$('browser-schedule-calendar')?.querySelector('p.hint');
  if(help)help.textContent='Persistent native RTL-SDR recordings, loaded from the local OS scheduler. These are not WebUSB jobs. Predictions are listed separately below; no radio samples are implied by a predicted pass.';
 }catch(err){
  $('schedule-readiness').textContent='Native calendar status unavailable: '+String(err?.message||err);
 }finally{nativeSyncRunning=false;}
}
window.addEventListener('tihulu-native-bridge-ready',()=>{void syncNativeScheduler();});
window.addEventListener('tihulu-native-schedule-changed',()=>{void syncNativeScheduler();});
setInterval(()=>{
 if(!document.hidden&&nativeMode())void syncNativeScheduler();
},15000);
let lastRenderedJobCardsSignature='';
function jobCardsSignature(){
 return JSON.stringify(jobs.map(j=>[j.id,j.state,j.when,j.until,j.frequency,
   j.durationSeconds,j.sampleRate,j.saveRaw,j.saveWav,j.chainIndex,j.chainId,j.message,j.downloadAvailable,
   j.report,lastScheduledFile?.jobId===j.id]));
}
function renderJobs(){
 if(nativeMode()){renderNativeJobCards();return;}
 const container=$('jobs');
 const signature=jobCardsSignature();
 if(signature===lastRenderedJobCardsSignature){
   // Preserve native dropdown menus and focus while refreshing countdowns.
   for(const panel of container.querySelectorAll('.scheduled-job[data-job-id]')){
     const job=jobs.find(j=>j.id===panel.dataset.jobId);
     const line=panel.querySelector('.job-state');
     if(job&&line)line.textContent=readableJobState(job);
   }
   paintBrowserCalendar();return;
 }
 lastRenderedJobCardsSignature=signature;
 container.replaceChildren();
 if(!jobs.length){
   const empty=document.createElement('p');empty.className='hint';
   empty.textContent='No scheduled captures. Calculate passes and select Schedule / configure to create one.';
   container.append(empty);
   paintBrowserCalendar();
   return;
 }
 const now=Date.now();
 for(const job of [...jobs].sort((a,b)=>a.when-b.when)){
   const panel=document.createElement('div');panel.className='scheduled-job';
   panel.dataset.state=job.state;panel.dataset.jobId=job.id;
   const title=document.createElement('h4');title.textContent=job.name+' · '+(job.frequency/1e6).toFixed(3)+' MHz';
   const statusLine=document.createElement('p');statusLine.className='job-state';
   statusLine.textContent=readableJobState(job,now);
   const timings=document.createElement('p');
   timings.textContent='Scheduled start (local): '+fmtTime(job.when)+
     ' · pass ends '+fmtTime(job.until)+
     ' · '+job.durationSeconds+' s'+(job.chainId?' · PART '+job.chainIndex+'/'+job.chainTotal:'')+' · '+(job.sampleRate/1e6)+' MS/s'+
     ' · '+(job.saveRaw?'Raw IQ + power analysis':'Power analysis only');
   const message=document.createElement('p');
   message.textContent=job.message||'Waiting for browser scheduler.';
   const controls=document.createElement('div');controls.className='line';
   if(job.state==='armed'){
     const cancel=document.createElement('button');cancel.type='button';
     cancel.className='secondary';cancel.textContent='Cancel scheduled scan';
     cancel.addEventListener('click',()=>{
       for(const related of jobs.filter(j=>j.id===job.id||(job.chainId&&j.chainId===job.chainId))){
         if(related.state!=='armed')continue;
         releaseScheduledStream(related);
         related.state='cancelled';related.message='Cancelled by operator with recording chain.';
       }
       renderJobs();
     });controls.append(cancel);
   }
   if(job.state==='blocked'&&Date.now()+1500<job.until){
     const retry=document.createElement('button');retry.type='button';
     retry.textContent='Retry while pass is active';
     retry.addEventListener('click',()=>{
       job.when=Date.now()+1000;job.state='armed';
       job.message='Retry armed. Keep browser visible and ensure RTL-SDR permission.';
       renderJobs();
     });
     controls.append(retry);
   }
   if(job.downloadAvailable&&lastScheduledFile?.jobId===job.id){
     const download=document.createElement('button');download.type='button';
     download.className='secondary';download.textContent='Download raw IQ again';
     download.addEventListener('click',()=>triggerRawDownload(lastScheduledFile.blob,lastScheduledFile.name));
     controls.append(download);
   }
   if(job.report){
     const report=document.createElement('p');
     report.textContent='Measured '+(job.report.bytesReceived/1048576).toFixed(2)+
       ' MiB · '+job.report.blocksMeasured+' power blocks · average digital level '+
       job.report.averageRelativeDb+' dBFS-like · '+job.report.elapsedSeconds+
       ' s. No satellite message decoded or identified.';
     panel.append(title,statusLine,timings,report,message,controls);
   }else panel.append(title,statusLine,timings,message,controls);
   container.append(panel);
 }
 paintBrowserCalendar();
}
async function checkScheduledReadiness(){
 const lines=[];
 lines.push('Tab: '+(document.hidden?'HIDDEN — cannot reliably receive':"visible"));
 lines.push('WebUSB: '+(hardwareSupported?'available':'not supported in this browser'));
 lines.push('RTL-SDR JavaScript driver: '+(driver?'loaded':'unavailable / loading'));
 lines.push('Device open now: '+(device?'yes':'no (release while waiting is recommended)'));
 if(hardwareSupported){
   try{
     const grants=await navigator.usb.getDevices();
     const rtl=grants.filter(d=>d.vendorId===0x0bda&&d.productId===0x2838);
     lines.push('Previously granted Nooelec/RTL2832U: '+rtl.length+
       (rtl.length?' (can attempt silent reopen at scheduled minute)':' (click Choose RTL-SDR first)'));
   }catch(e){lines.push('USB permissions could not be inspected: '+e.message);}
 }
 lines.push('Screen wake lock: '+(wakeLock?'active':'off / not guaranteed'));
 lines.push('Armed passes: '+jobs.filter(j=>j.state==='armed').length);
 lines.push('Your browser must stay OPEN, visible and not suspended. This test does NOT claim or test the USB tuner.');
 status('schedule-readiness',lines.join('\n'));
}
$('schedule-check').addEventListener('click',()=>{void checkScheduledReadiness();});
$('schedule-wake').addEventListener('click',async()=>{
 if(wakeLock){try{await wakeLock.release();}catch(_){ }wakeLock=null;
   $('schedule-wake').textContent='Request screen wake lock';
   status('schedule-readiness','Screen wake lock released. The scheduler may stop if your computer sleeps.');
   return;
 }
 if(!navigator.wakeLock){
   status('schedule-readiness','Screen Wake Lock API is unavailable. Keep screen awake using your computer power settings.');
   return;
 }
 try{
   wakeLock=await navigator.wakeLock.request('screen');
   wakeLock.addEventListener('release',()=>{
     wakeLock=null;
     $('schedule-wake').textContent='Request screen wake lock';
   });
   $('schedule-wake').textContent='Release screen wake lock';
   status('schedule-readiness','Screen wake lock requested successfully. Browser and operating system can still suspend background tabs; keep the tab visible.');
 }catch(e){status('schedule-readiness','Wake lock not permitted: '+e.message+'. Keep this browser tab awake manually.');}
});
async function scheduledTick(){
 if(schedulerTickBusy||!jobs.length)return;
 schedulerTickBusy=true;
 try{
   const now=Date.now();
   for(const job of jobs){
     if(job.state!=='armed')continue;
     const action=evaluateScheduledJob(job,now,{
       visible:!document.hidden,receiverBusy:!!capturePromise||usbTestRunning
     });
     if(action==='missed'){
        releaseScheduledStream(job);
       job.state='missed';job.message='Pass ended or insufficient time remained for a complete recording. No radio data collected.';
       log('Missed '+job.name+': pass window expired.');
       continue;
     }
     if(action==='waiting-foreground'){
       job.message='Scheduled minute reached, but tab is hidden/suspended. Return before the pass ends to try an RF sample.';
       continue;
     }
     if(action==='waiting-receiver'){
       job.message='Scheduled minute reached; waiting for current RTL-SDR capture to release.';
       continue;
     }
     if(action!=='start')continue;
     job.state='starting';
     job.message='At scheduled minute. Attempting to reopen previously permitted USB receiver (no new permission prompt).';
     log('Scheduled capture starting: '+job.name+' at '+new Date().toLocaleTimeString());
     renderJobs();
     try{
       if(!device)await connectDevice({silent:true});
       if(!device)throw Error('WebUSB did not open the selected RTL-SDR.');
       if(document.hidden)throw Error('Browser became hidden; scheduled RF operation cancelled.');
       const remaining=Math.floor((job.until-Date.now())/1000);
       if(remaining<job.durationSeconds){
         releaseScheduledStream(job);
         job.state='missed';job.message='Insufficient predicted LOS time for full requested recording.';
         await closeDevice();continue;
       }
       const prepared=preparedLongStreams.get(job.id)||null;
       if(job.diskStreamPrepared&&!prepared?.writable)
         throw Error('Preauthorized CU8 file writer unavailable; re-plan explicitly.');
       if(job.wavDiskPrepared&&!prepared?.wavWritable)
         throw Error('Preauthorized WAV file writer unavailable; re-plan explicitly.');
       preparedLongStreams.delete(job.id);
       await startCapture(job,prepared);
     }catch(e){
       job.state='blocked';job.message='Could not start real USB reception: '+e.message+
         '. Check readsb/Gqrx conflicts, OS drivers, RTL-SDR permission and page visibility.';
       status('scheduled-report',job.name+' — BLOCKED. '+e.message+
         '. No RF data was captured. You can retry while the pass is active.');
       log('Scheduled scan blocked: '+e.message);
       await closeDevice();
     }
     break; // process only one RF capture at a time
   }
 }finally{
   schedulerTickBusy=false;
   renderJobs();
 }
}
setInterval(()=>{
 // Interval checks the actual wall clock; browser timer throttling cannot be
 // defeated, therefore missed/late jobs remain explicitly labelled.
 void scheduledTick();
 if(!schedulerTickBusy&&jobs.length)renderJobs();
},1000);
// Closing a page destroys the WebUSB session; no service worker keeps hardware open.
// Promise resolution is not guaranteed during pagehide, but browser ownership ends.
window.addEventListener('pagehide',()=>{
  stopRequested=true;
  if(wakeLock){void wakeLock.release().catch(()=>{});wakeLock=null;}
  if(device)void device.close().catch(()=>{});
  for(const [id,prepared] of preparedLongStreams){
    preparedLongStreams.delete(id);
    void abortLongCapture(prepared);
  }
});
document.addEventListener('visibilitychange',()=>{
  if(document.hidden && (capturePromise || device)){
    stopRequested=true;
    log('Tab hidden: releasing browser-owned RTL-SDR. Scheduled passes require the tab to stay in foreground.');
    void stopCapture();
  }
});

let deferredInstallPrompt=null;
const installButton=$('install-app');
window.addEventListener('beforeinstallprompt',event=>{
  event.preventDefault();
  deferredInstallPrompt=event;
  installButton.hidden=false;
});
installButton.addEventListener('click',async()=>{
  if(!deferredInstallPrompt)return;
  const prompt=deferredInstallPrompt;
  deferredInstallPrompt=null;
  installButton.hidden=true;
  try{await prompt.prompt();}catch(err){log('PWA install prompt: '+err.message);}
});
window.addEventListener('appinstalled',()=>{
  installButton.hidden=true;
  log('Satellite Center added to your browser applications. Pin it to the OS dock from Applications.');
});

async function runAutoMission({mode=$('auto-mode').value,goal=$('auto-coverage').value,fromNavigation=false}={}) {
  const button=$('auto-plan'),statusBox=$('auto-plan-status');
  if(button.disabled)return;
  button.disabled=true;
  $('auto-mode').value=mode;
  try {
    if(!hardwareSupported||!driver)throw Error('Direct WebUSB requires a supported Chromium browser and ready RTL2832U driver. Use the native companion for Firefox/Safari or unattended capture.');
    if(usbTestRunning||capturePromise)throw Error('Receiver is already sampling; stop your owned capture before arming new passes.');
    statusBox.textContent='Checking explicit WebUSB access, current TLE catalog and ground-station pass predictions…';
    // First-click chooser is an actual direct user gesture. Navigation from
    // another page may only silently reopen an already granted device.
    if(!device) {
      const opened=await connectDevice({silent:fromNavigation});
      if(!opened)throw Error('RTL-SDR not granted/opened. Click Choose RTL-SDR and retry Auto Schedule.');
    }
    if(!device)throw Error('RTL-SDR permission not available in this browser.');
    await closeDevice(); // waiting for future passes must NOT monopolize the dongle
    if(!tleEntries.length)await refreshOrbitalCatalog();
    if(!tleEntries.length)throw Error('Could not load TLEs. Import a TLE text file, then retry.');
    if(!passes.length)await calculateOrbitalPasses();
    const totalSeconds=secondsFromEntry($('auto-browser-seconds').value,$('auto-browser-unit').value);
    if(totalSeconds<8)throw Error('Automatic RF recording must be at least 8 seconds.');
    const durationSeconds=Math.min(60,totalSeconds);
    const autoRaw=$('auto-save-raw').checked,autoWav=$('auto-save-wav').checked;
    if(['iss-images','images','all'].includes(mode)&&!autoRaw&&!autoWav)
      throw Error('Choose at least CU8 or WAV for automatic ISS SSTV image capture. Both are allowed.');
    const proposal=selectAutomaticPasses(passes,{
      mode,goal:totalSeconds>60?'sample':goal,durationSeconds,now:Date.now(),maxJobs:6,existingJobs:jobs
    });
    let armed=0,recordingGroups=0;
    for(const item of proposal.scheduled) {
      const selectedRaw=item.missionId==='iss-sstv'?autoRaw:item.saveRaw;
      const selectedWav=item.missionId==='iss-sstv'?autoWav:false;
      try{
        const chain=buildBrowserChain(item.pass,{when:item.when,totalSeconds,
          rate:item.sampleRate,frequency:item.frequency,raw:selectedRaw,wav:selectedWav});
        for(const job of chain.jobs){
          job.missionId=item.missionId;
          job.coverage=item.coverage;
          job.dataKind=item.dataKind;
          job.shortfallSeconds=item.shortfallSeconds;
        }
        jobs.push(...chain.jobs);
        armed+=chain.jobs.length;recordingGroups++;
      }catch(error){
        proposal.skipped.push({name:item.pass.name,reason:'Chained recording unavailable: '+error.message});
      }
    }
    jobs.sort((a,b)=>a.when-b.when);
    renderJobs();
    statusBox.textContent=armed?
      'Armed '+recordingGroups+' satellite pass(es) as '+armed+' independent calendar capture segment(s), '+totalSeconds+' s per pass, 6 s reserved between parts. Segments are not lossless or gap-free. ISS selected outputs: '+
      outputSelectionText(autoRaw,autoWav)+'. USB is released while waiting. Browser clips max out at 60 s / 128 MiB; Meteor full imagery requires a native disk capture. '+proposal.skipped.length+' skipped; '+proposal.skipped.map(x=>x.reason).slice(0,2).join(' · ')+' Downloads may require multiple-file approval. Keep this tab VISIBLE and AWAKE.':
      'No feasible passes or not enough LOS time for this capture chain. '+proposal.skipped.map(x=>x.reason).slice(0,3).join(' · ')+' You can choose Quick RF sample or use the optional local receiver for full-pass imaging.';
    log('Automatic mission plan: '+armed+' RF recording jobs armed, '+proposal.skipped.length+' skipped; no device is currently in use.');
    if(armed)document.getElementById('schedule-center')?.scrollIntoView({behavior:'smooth',block:'nearest'});
  }catch(error){
    statusBox.textContent='Auto schedule not armed: '+String(error?.message||error)+
      '. No background service was started and existing recordings are unchanged.';
    log('Auto mission scheduling: '+String(error?.message||error));
  }finally{button.disabled=false;}
}
$('auto-plan').addEventListener('click',()=>{void runAutoMission();});
$('auto-stop').addEventListener('click',async()=>{
  let cancelled=0;
  for(const job of jobs){
    if(job.missionId&&job.state==='armed'){
      releaseScheduledStream(job);
     job.state='cancelled';job.message='Operator cancelled automatic reception before the pass.';
      cancelled++;
    }
  }
  const ownedAutoCapture=jobs.some(j=>j.missionId&&['starting','running'].includes(j.state));
  if(ownedAutoCapture)await stopCapture();
  renderJobs();
  $('auto-plan-status').textContent='Cancelled '+cancelled+
    ' auto-armed pass(es). '+(ownedAutoCapture?'Stopped app-owned active auto capture. ':'')+
    'No unrelated readsb/welle.io/Gqrx process or manual recording was stopped.';
});
$('auto-analyze').addEventListener('click',()=>{
  const file=$('iq-file').files?.[0];
  if(!file&&!lastScheduledFile){
    $('auto-plan-status').textContent='No recording available in this tab. Wait for a real capture or choose a saved .cu8 in Signal Intelligence below.';
    $('iq-analysis').scrollIntoView({behavior:'smooth'});return;
  }
  $('auto-plan-status').textContent='Analyzing real CU8 now. Results only appear after validated decoding or measurable RF evidence.';
  $('iq-analysis').scrollIntoView({behavior:'smooth'});
  $('iq-auto-discover').click();
});
$('auto-results').addEventListener('click',()=>{
  $('iq-discovery-results').scrollIntoView({behavior:'smooth',block:'start'});
  $('auto-plan-status').textContent=!$('iq-discovery-zip').disabled?
    'Inspect the actual measured spectrum, Robot36 image candidates and audio previews below. Save everything as ZIP or download individual files. No satellite origin is presumed.':
    'No completed analysis results yet. Analyze a real CU8 recording first.';
});
// Carry the operator's coverage preference from Images & Data without URL
// coordinates or background USB permission prompts.
try {
  const goal=sessionStorage.getItem('tihulu-auto-coverage-goal');
  sessionStorage.removeItem('tihulu-auto-coverage-goal');
  if(['full','sample'].includes(goal))$('auto-coverage').value=goal;
  const transferredSeconds=sessionStorage.getItem('tihulu-auto-browser-seconds');
  sessionStorage.removeItem('tihulu-auto-browser-seconds');
  if(transferredSeconds!==null&&Number.isInteger(Number(transferredSeconds))&&
     Number(transferredSeconds)>=8&&Number(transferredSeconds)<=7200)
    $('auto-browser-seconds').value=transferredSeconds;
  const transferredUnit=sessionStorage.getItem('tihulu-auto-browser-unit');
  sessionStorage.removeItem('tihulu-auto-browser-unit');
  if(['minutes','seconds'].includes(transferredUnit))$('auto-browser-unit').value=transferredUnit;
} catch(_error) { /* Storage unavailable: keep safe full-data default. */ }
// Same-tab transfer from the Images & Data recording-formats picker.
try {
 const raw=sessionStorage.getItem('tihulu-auto-formats');
 if(raw){
   sessionStorage.removeItem('tihulu-auto-formats');
   const choice=JSON.parse(raw);
   if(typeof choice.raw==='boolean'&&typeof choice.wav==='boolean'&&
      Number.isFinite(choice.createdAt)&&Date.now()-choice.createdAt<5*60000){
     $('auto-save-raw').checked=choice.raw;
     $('auto-save-wav').checked=choice.wav;
     refreshAutoOutputSummary();
     $('auto-plan-status').textContent=
       'Recording formats transferred from Satellite Images & Data: '+
       outputSelectionText(choice.raw,choice.wav)+'. Review before arming.';
   }
 }
}catch(e){log('Recording format transfer not available: '+String(e?.message||e));}
const requestedAutoMission=new URLSearchParams(location.search).get('auto-mission');
if(['iss-images','images','messages','voice','all'].includes(requestedAutoMission)){
  $('auto-mode').value=requestedAutoMission;
  $('auto-plan-status').textContent='Reception type preselected. Click Auto Schedule & Capture to grant hardware permission and arm passes.';
}

iqAnalysisUI=initIqAnalysisUI({log});
satelliteImageUI=initSatelliteImageUI({
 log,
 onTargetChange:target=>{imageCandidateTarget=target;},
 onTune:(hz,target)=>{
   const preset=$("preset");
   const option=Array.from(preset.options).find(o=>Number(o.value)===hz);
   if(!option)throw Error("Receiver has no preset for "+(hz/1e6).toFixed(3)+" MHz.");
   preset.value=option.value;
   imageCandidateTarget=target;
   preset.dispatchEvent(new Event("change",{bubbles:true}));
 }
});
// Deep-link from the shared Satellite Images & Data mission catalog.
const receptionTarget = new URLSearchParams(window.location.search).get("image-target");
if (["iss","meteor3","meteor4"].includes(receptionTarget)) {
  const selection = $("image-target");
  selection.value = receptionTarget;
  selection.dispatchEvent(new Event("change", {bubbles:true}));
}
satelliteMaps = createSatelliteMaps({
 getTles:()=>tleEntries,
 getSatLib:getOrbitalLibrary,
 getPasses:()=>passes,
 getLastCapture:()=>lastCaptured,
 onTune:(frequency)=>{
   const preset=$('preset');
   const option=Array.from(preset.options).find(o=>Number(o.value)===frequency);
   if(option){
     preset.value=option.value;
     preset.dispatchEvent(new Event('change',{bubbles:true}));
   }
 },
 log
});
locationUI=initStationLocationUI({
 onStationChanged:invalidatePasses,
 log
});
// Honor the explicitly selected observer from the separate Images & Data
// page. Do not place precise coordinates in a URL or send them to a catalog.
try {
  const savedStation=sessionStorage.getItem('tihulu-auto-station');
  if(savedStation){
    sessionStorage.removeItem('tihulu-auto-station');
    const saved=JSON.parse(savedStation);
    if(Date.now()-saved.createdAt<5*60000 &&
       Number.isFinite(saved.lat)&&Math.abs(saved.lat)<=90 &&
       Number.isFinite(saved.lon)&&Math.abs(saved.lon)<=180 &&
       [12,24,48].includes(saved.hours)) {
      $('city').value='Custom';
      $('lat').value=String(saved.lat);$('lon').value=String(saved.lon);
      $('hours').value=String(saved.hours);
      if([5,15,20,30].includes(saved.elevation)){
        // The main pass planner currently supports 5°, 15°, 30°; add 20° dynamically.
        const elev=$('elev');
        if(!Array.from(elev.options).some(o=>o.value===String(saved.elevation))){
          const o=document.createElement('option');o.value=String(saved.elevation);
          o.textContent=saved.elevation+'°';elev.append(o);
        }
        elev.value=String(saved.elevation);
      }
      $('lat').dispatchEvent(new Event('change',{bubbles:true}));
      $('auto-plan-status').textContent='Observer location transferred locally (not in URL). Auto Mission uses the selected station.';
    }
  }
} catch(e) {
  $('auto-plan-status').textContent='Station transfer unavailable: '+e.message+
    '. Confirm latitude/longitude before using Auto Schedule.';
}

renderSignal();
log('Browser-only mode loaded with Earth/sky TLE tracking. No local service or USB access attempted.');
