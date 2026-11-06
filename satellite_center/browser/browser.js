import { platformFamily, webUsbHelp, permissionReport } from './usb_diagnostics.mjs';
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
let lastCaptured = null, rtlLibraryError = null;
let orbitalLibrary = null, tleEntries = [], passes = [], jobs = [], sessionCounter = 0;
let lastTleFetchAt = 0;
const maxRecordBytes = 128 * 1024 * 1024;
const signalHistory = [];
const hardwareSupported = !!(window.isSecureContext && navigator.usb);
const connectButton = $('connect');
const platform = platformFamily(navigator.userAgent || "");
let lastUsbReport = "No USB diagnostics run.";
$('usb-check').addEventListener('click', async () => {
  const report = await permissionReport(navigator.usb, platform);
  lastUsbReport = report;
  $('usb-report').textContent = report;
  log('Read-only USB permission diagnostic completed. No device was opened.');
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
    connectButton.disabled = false;
    status('device-status', 'Ready to ask for USB permission. Plug Nooelec into USB, then select Choose RTL-SDR.');
  }).catch(err => {
    rtlLibraryError = err;
    status('device-status', 'WebUSB library unavailable: ' + err.message + '. Internet access to esm.sh is needed to load the driver; no hardware was opened.');
  });
}
function refreshControls() {
  $('start').disabled = !device || !!capturePromise;
  $('stop').disabled = !capturePromise;
  $('disconnect').disabled = !device && !capturePromise;
  $('connect').disabled = !driver || !!device || !!capturePromise;
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
async function connectDevice() {
  if (!hardwareSupported || !driver) {
    status('device-status', rtlLibraryError ? rtlLibraryError.message : 'WebUSB not ready');
    return;
  }
  if (device || capturePromise) return;
  try {
    // provider.get() itself invokes the browser's WebUSB chooser.
    // Keep this directly associated with the click; no arbitrary USB filters.
    const provider = new driver();
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
    log('RTL2832U WebUSB tuner opened. Device held only while this page is open.');
  } catch (e) {
    log('WebUSB permission/open error: ' + e.message);
    const report = webUsbHelp(e, platform);
    lastUsbReport = report;
    $('usb-report').textContent = report;
    $('usb-help').open = true;
    status('device-status', 'WebUSB could not open this RTL-SDR. Open the USB diagnostic panel below for platform-specific steps.\n' + String(e.message || e));
    log('USB diagnostics: ' + report.split('\n')[0]);
    await closeDevice();
  } finally { refreshControls(); }
}
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
function saveCapture(bytes,name) {
  if (!bytes.length) return;
  const blob = new Blob(bytes,{type:'application/octet-stream'});
  const url = URL.createObjectURL(blob);
  const link=document.createElement('a'); link.href=url;link.download=name;
  document.body.append(link);link.click();link.remove();
  setTimeout(()=>URL.revokeObjectURL(url),60000);
  log('Saved ' + name + ' · ' + (blob.size/1048576).toFixed(1) + ' MiB, real raw IQ only.');
}
async function startCapture(job=null) {
  if (capturePromise || !device) throw Error('Choose the USB device first, or finish the previous capture.');
  stopRequested=false;
  const freq=job ? job.frequency : Number($('preset').value);
  const rate=Number($('rate').value), limit=Number($('duration').value);
  const recording=$('record').checked;
  const session=++sessionCounter;
  capturePromise=(async()=>{
    let bytesReceived=0, bytesRecorded=0, chunks=[], measured=null;
    const deadline=Date.now()+limit*1000;
    try {
      await device.setSampleRate(rate);
      await device.setCenterFrequency(freq);
      await device.setGain(null);
      await device.resetBuffer();
      status('sample-state','Receiving raw I/Q at '+(freq/1e6).toFixed(3)+' MHz · '+(rate/1e6)+' MS/s. This is not a satellite identification.');
      while(!stopRequested && Date.now()<deadline) {
        const raw=await device.readSamples(65536);
        // Library returns raw CU8 bytes (ArrayBuffer or typed array).
        const data=raw instanceof ArrayBuffer ? new Uint8Array(raw) :
          ArrayBuffer.isView(raw) ? new Uint8Array(raw.buffer,raw.byteOffset,raw.byteLength) : null;
        if(!data || data.length<2) throw Error('No usable I/Q bytes returned by SDR driver');
        bytesReceived+=data.length; measured=rmsLevel(data);
        signalHistory.push(measured);
        if(signalHistory.length>150) signalHistory.shift();
        renderSignal();
        if(recording) {
          if(bytesRecorded+data.length>maxRecordBytes) {
            log('Recording size cap 128 MiB reached; ending receiver session');
            stopRequested=true;
          } else {chunks.push(new Uint8Array(data));bytesRecorded+=data.length;}
        }
        status('sample-state','Real USB samples: '+(bytesReceived/1048576).toFixed(2)+
          ' MiB · relative digital level '+measured+' dBFS-like · '+(freq/1e6).toFixed(3)+' MHz');
      }
      if(recording && chunks.length>0) {
        const tag=new Date().toISOString().replaceAll(':','-').replace(/\..*/, '');
        saveCapture(chunks,'TIHULU-'+Math.round(freq)+'-'+rate+'-'+tag+'.cu8');
      }
      lastCaptured={bytesReceived,bytesRecorded,frequency_hz:freq,observedAt:new Date().toISOString()};
      if(job) job.state='finished';
      log('Capture ended. USB bytes: '+bytesReceived+'. Device released on exit.');
    } catch(e) {
      log('Capture stopped with driver error: '+e.message);
      status('sample-state','Capture failed: '+e.message+'. Any partial recording was not labelled as a successful decode.');
      if(job) job.state='blocked';
    } finally {
      await closeDevice();
    }
  })();
  refreshControls();
  try { await capturePromise; }
  finally { capturePromise=null;refreshControls();renderJobs(); }
}
async function stopCapture() {
  stopRequested=true;
  if(capturePromise) {
    try{await capturePromise;}catch(e){log('Receiver stop: '+e.message);}
  }
  await closeDevice();
  status('device-status','RTL-SDR released. Choose USB again for a new scan. No third-party SDR process was touched.');
  refreshControls();
}
$('connect').addEventListener('click',()=>{void connectDevice();});
$('disconnect').addEventListener('click',()=>{void stopCapture();});
$('stop').addEventListener('click',()=>{void stopCapture();});
$('start').addEventListener('click',()=>{void startCapture().catch(e=>log(e.message));});
navigator.usb?.addEventListener('disconnect',e=>{
  stopRequested=true;
  if(device)log('USB disconnection detected; receiving session is stopping.');
});
for (const [city,coords] of Object.entries(LOCATIONS)) void coords;
$('city').addEventListener('change',()=>{
  const pair=LOCATIONS[$('city').value];
  if(pair){$('lat').value=pair[0];$('lon').value=pair[1];}
});
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
  const caps={iss:1,meteor:3,cubesat:8,iridium:14},counts={},ids=new Set();
  const result=[];
  for(const obj of records){
    if(ids.has(obj.id))continue;
    const family=obj.family;
    if(!Object.hasOwn(caps,family)|| (counts[family]||0)>=caps[family])continue;
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
    const rows=parseTle(await file.text(),'uploaded');
    if(!rows.length)throw Error('No valid two-line elements (TLE) found');
    tleEntries=boundedCatalog([...tleEntries,...rows]);
    status('orbit-state','Imported '+rows.length+' valid TLE records locally; '+tleEntries.length+' candidates selected. These are ephemerides, not live radio signals.');
  }catch(err){status('orbit-state','TLE import failed: '+err.message);}
});
$('orbit-fetch').addEventListener('click',async()=>{
  if(tleEntries.length && lastTleFetchAt && Date.now()-lastTleFetchAt < 2*3600000) {
    status('orbit-state','Keeping '+tleEntries.length+' TLE candidates from this tab\'s recent download. CelesTrak GP data is not refreshed more often than every two hours.');
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
  if(results.length){tleEntries=boundedCatalog(results);lastTleFetchAt=Date.now();}
  status('orbit-state',results.length ? 'Cached '+tleEntries.length+' client-side TLE candidates. '+(errors.join(' · ')||'All sources read') :
     'Browser could not read CelesTrak (possibly CORS/network). Import a .tle/.txt file manually. '+errors.join(' · '));
});
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
function fmtTime(time){return new Date(time).toLocaleString(undefined,{dateStyle:'short',timeStyle:'short'});}
function appendPass(pass){
  const item=document.createElement('div');item.className='pass';
  const strong=document.createElement('strong');strong.textContent=pass.name+' · '+pass.family.toUpperCase();
  const description=document.createElement('small');
  description.textContent=fmtTime(pass.aos)+' → '+fmtTime(pass.los)+' · max elevation '+pass.maximum.toFixed(1)+'° (geometric estimate)';
  const btn=document.createElement('button');btn.textContent='Schedule browser-open capture';
  btn.addEventListener('click',()=>{
    if(!device){status('orbit-state','Choose and keep the WebUSB receiver connected before arming a scheduled capture.');return;}
    const freq=FREQS[pass.family];
    if(!freq){status('orbit-state','No verified receive frequency for this family');return;}
    const id=pass.id+':'+pass.aos;
    if(jobs.some(j=>j.id===id))return;
    jobs.push({id,frequency:freq,when:pass.aos,until:pass.los,state:'armed',name:pass.name});
    log('Scheduled '+pass.name+'; keep this tab foreground and connected. This cannot run if browser closes.');
    renderJobs();
  });
  item.append(strong,description,btn);
  return item;
}
function renderPasses(){
  $('passes').replaceChildren();
  if(!passes.length){status('passes','No passes above the selected elevation found in this window.');return;}
  const fragment=document.createDocumentFragment();
  for(const pass of passes.slice(0,80))fragment.append(appendPass(pass));
  $('passes').append(fragment);
}
$('orbit-calc').addEventListener('click',async()=>{
  if(!tleEntries.length){status('orbit-state','Load orbit TLEs from CelesTrak or an uploaded file first.');return;}
  const lat=Number($('lat').value),lon=Number($('lon').value),hours=Number($('hours').value),minimum=Number($('elev').value);
  if(!Number.isFinite(lat)||!Number.isFinite(lon)||lat<-90||lat>90||lon<-180||lon>180){status('orbit-state','Invalid latitude/longitude');return;}
  status('orbit-state','Computing geometry locally in this browser (no RF reception implied)…');
  try{
    const satlib=await getOrbitalLibrary();
    const observer={longitude:rad(lon),latitude:rad(lat),height:0};
    const start=Date.now(),end=start+hours*3600000,step=30000;
    const found=[];
    for(const item of tleEntries.slice(0,30)){
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
          if(current.maximum>=minimum&&current.maximum<=90)found.push(current);
          current=null;
        }
      }
    }
    found.sort((a,b)=>a.aos-b.aos);
    passes=found.slice(0,100);
    renderPasses();
    status('orbit-state','Calculated '+found.length+' geometric passes from '+tleEntries.length+' TLE candidates at '+lat.toFixed(3)+', '+lon.toFixed(3)+'. Approximate 30-second resolution; no satellite signals identified.');
  }catch(err){status('orbit-state','Orbit computation failed: '+err.message+'. Check browser connectivity to the JS library CDN.');}
});
function renderJobs(){
  $('jobs').replaceChildren();
  if(!jobs.length){status('jobs','No scheduled browser captures.');return;}
  for(const job of jobs){
    const row=document.createElement('div');row.className='pass';
    const line=document.createElement('span');
    line.textContent=job.name+' · '+fmtTime(job.when)+' · '+job.state+' · '+(job.frequency/1e6).toFixed(3)+' MHz';
    row.append(line);
    if(job.state==='armed'){
      const cancel=document.createElement('button');cancel.className='secondary';cancel.textContent='Cancel';
      cancel.addEventListener('click',()=>{job.state='cancelled';renderJobs();});
      row.append(' ',cancel);
    }
    $('jobs').append(row);
  }
}
setInterval(()=>{
  if(!jobs.length)return;
  const now=Date.now();
  for(const job of jobs){
    if(job.state!=='armed')continue;
    if(now>job.until){job.state='missed';renderJobs();continue;}
    if(now>=job.when){
      if(document.hidden || !device || capturePromise){
        job.state='blocked';log('Scheduled pass blocked: page hidden, no USB device, or another capture active.');
      } else {
        job.state='running';
        void startCapture(job).catch(err=>{job.state='blocked';log('Scheduled capture: '+err.message);renderJobs();});
      }
      renderJobs();
    }
  }
},1000);
// Closing a page destroys the WebUSB session; no service worker keeps hardware open.
// Promise resolution is not guaranteed during pagehide, but browser ownership ends.
window.addEventListener('pagehide',()=>{stopRequested=true; if(device)void device.close().catch(()=>{});});
document.addEventListener('visibilitychange',()=>{
  if(document.hidden && (capturePromise || device)){
    stopRequested=true;
    log('Tab hidden: releasing browser-owned RTL-SDR. Scheduled passes require the tab to stay in foreground.');
    void stopCapture();
  }
});
renderSignal();
log('Browser-only mode loaded. No local service or USB access attempted.');
