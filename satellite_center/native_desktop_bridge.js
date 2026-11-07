/* TIHULU native installed desktop: SAME HTML/CSS/JS as the website.
 * Intercepts only radio ownership/recording/scheduling controls BEFORE the
 * browser WebUSB listeners, and uses an allowlisted in-process Qt WebChannel.
 * The browser's pass/map/file-analysis/imagery controls remain its originals.
 * Never reveal WebUSB UI or invent received RF, satellite audio or images.
 */
(() => {
  'use strict';
  if (window.nativeWebBridgeReady) return;
  const $ = id => document.getElementById(id);
  const say = (id,value) => { const el=$(id); if(el) el.textContent=String(value); };
  const log = value => {
    const node=$('log');
    if(node) node.textContent=new Date().toLocaleTimeString()+
      ' · NATIVE: '+String(value)+'\n'+node.textContent.slice(0,8000);
  };
  let bridge=null,seq=0;
  const callbacks=new Map();
  const hardwareState={enabled:false,verified:false,actualIQ:false};
  const lookup = (command,args={}) => new Promise((resolve,reject)=>{
    if(!bridge) return reject(Error('Qt native bridge is not available'));
    const id='q'+String(++seq);
    callbacks.set(id,{resolve,reject});
    bridge.request(id,command,JSON.stringify(args));
  });
  const invoke = async (command,args={},statusElement='device-status')=>{
    say(statusElement,'Native '+command+' requested; waiting for the OS receiver…');
    try {
      const result=await lookup(command,args);
      log(command+' PASS · '+JSON.stringify(result).slice(0,900));
      return result;
    } catch(error) {
      const message=String(error?.message || error);
      say(statusElement,command+' failed: '+message);
      log(command+' FAILED: '+message);
      throw error;
    }
  };
  const setHardwareLabels=()=>{
    const eyebrow=document.querySelector('header .eyebrow');
    if(eyebrow)eyebrow.textContent='TIHULU SATELLITE CENTER · DIRECT NATIVE OS SDR';
    const pill=document.querySelector('header h1 .pill');
    if(pill)pill.textContent='Native desktop · 0.3.0 preview10';
    const intro=document.querySelector('header h1 + p');
    if(intro)intro.textContent=
      'Same Satellite Center web interface in a locally installed Qt window. '+
      'Hardware is controlled by Linux RTL-SDR tools through Qt WebChannel, '+
      'not WebUSB or an external browser. Offline maps and local analysis '+
      'are available without an SDR.';
    const strip=document.querySelector('.web-runtime-strip');
    if(strip){
      const strong=strip.querySelector('strong');
      if(strong)strong.textContent='Native Qt desktop · web-identical UI';
      const hints=strip.querySelectorAll('span');
      if(hints[0])hints[0].textContent=
        'Same orbit maps and data panels as the website. TLE positions are NOT RF signals.';
      if(hints[1])hints[1].textContent=
        'Real USB connection and RF acquisition use OS-native SDR binaries (no WebUSB).';
    }
    const install=document.querySelector('#desktop-install');
    if(install)install.hidden=true; // PWA install is browser-only, desktop is installed.
    for(const id of ['connect','usb-live-test','disconnect','start','stop']){
      if($(id))$(id).disabled=false;
    }
    if($('connect'))$('connect').textContent='Connect & verify physical RTL-SDR';
    if($('usb-live-test'))$('usb-live-test').textContent='Test real USB + IQ (native)';
    if($('disconnect')){
      $('disconnect').textContent='Stop & disconnect RF';
      $('disconnect').disabled=false;
    }
    if($('usb-check'))$('usb-check').textContent='Refresh Linux USB/process status';
    if($('usb-claim-test'))$('usb-claim-test').textContent='Test native USB open / release';
    if($('start'))$('start').textContent='Start direct native RF capture';
    if($('stop'))$('stop').textContent='Stop native capture';
    if($('auto-plan'))$('auto-plan').textContent='1 · Schedule native RF passes';
    if($('auto-stop'))$('auto-stop').textContent='Cancel native auto jobs';
    if($('schedule-check'))$('schedule-check').textContent='Check native scheduler status';
    // Website source remains unchanged; only desktop-specific hardware copy.
    const lead=$('device-status');
    if(lead)lead.textContent='Native RTL-SDR backend · hardware not yet verified';
    const mode=$('auto-workflow');
    if(mode){
      const hints=mode.querySelectorAll('p.hint');
      for(const hint of hints){
        if(hint.textContent?.includes('WebUSB')){
          hint.dataset.nativeWebsiteText='true';
          hint.hidden=true; // avoid browser-only advice that is false for native
        }
      }
    }
    const status=$('usb-live-test-report');
    if(status)status.textContent='The desktop tests real IQ using rtl_sdr, not browser WebUSB.';
    const state=document.createElement('p');
    state.className='status';
    state.id='native-receiver-status';
    state.textContent='Same web UI · OS-native SDR · no WebUSB · no radio capture on startup';
    $('device-status')?.after(state);
    // Never insert fake coordinates, imagery or signal levels.
  };
  const duration=(id,unitId)=>{
    const count=Number($(id)?.value);
    const unit=$(unitId)?.value;
    const value=Math.round(count*(unit==='minutes'?60:1));
    if(!Number.isInteger(value)||value<8||value>900){
      throw Error('Native RF capture must be 8–900 seconds, subject to 2 GB disk cap');
    }
    return value;
  };
  const selectedFrequency=()=>Number($('preset')?.value||137900000);
  const coordinateArgs=()=>({
    lat:Number($('lat')?.value),
    lon:Number($('lon')?.value),
    hours:Number($('hours')?.value||24),
    elevation:Number($('elev')?.value||15),
  });
  const execute = async (id) => {
    switch(id){
      case 'connect': {
        const result=await invoke('connect',{},'device-status');
        hardwareState.enabled=true;hardwareState.verified=true;
        say('device-status','PASS · physical USB and actual CU8 samples tested, then released. Native RF armed.');
        say('usb-live-test-report','Physical receiver tested; no app-owned USB handle remains open while idle.');
        $('disconnect').disabled=false;
        return result;
      }
      case 'usb-live-test': {
        const result=await invoke('sample',{frequency:selectedFrequency()},'usb-live-test-report');
        hardwareState.actualIQ=true;
        say('usb-live-test-report',
          'PASS · '+result.complex_samples+' physical complex IQ samples at '+
          (result.frequency_hz/1e6).toFixed(3)+
          ' MHz. Process released. This does not prove satellite reception.');
        return;
      }
      case 'usb-check': {
        const result=await invoke('status',{},'usb-report');
        const hw=result.hardware||{};
        say('usb-report',JSON.stringify({
          devices:hw.usb_devices,enabled:hw.receiver_enabled,
          app_released:hw.app_released,external_busy:result.busy,
          last_real_sample:hw.last_real_sample,pending_schedules:hw.pending_schedules
        },null,2));
        say('device-status',hw.receiver_enabled?
          'Native RF enabled · OS device is '+(hw.app_released?'released while idle':'busy or in use'):
          'RF disabled · '+(hw.app_released?'released':'release not yet verified'));
        return;
      }
      case 'usb-claim-test': {
        const result=await invoke('usb_open',{},'usb-claim-result');
        say('usb-claim-result',JSON.stringify(result,null,2));
        return;
      }
      case 'usb-copy': {
        const text=$('usb-report')?.textContent||'No native USB diagnostics yet';
        await navigator.clipboard?.writeText(text);
        return;
      }
      case 'disconnect': {
        const result=await invoke('disconnect',{},'device-status');
        hardwareState.enabled=false;hardwareState.verified=false;
        say('device-status',result.app_released?
          'RF DISABLED · application SDR process and lock RELEASED. USB remains physically plugged in.':
          'RF DISABLED · release still pending; check process status.');
        say('native-receiver-status','RF disabled · '+result.pending_jobs_paused+
          ' pending scheduled jobs paused');
        return;
      }
      case 'stop': {
        const result=await invoke('stop',{},'device-status');
        say('device-status','Stop requested for native owned SDR capture. '+
          'Refresh USB status to confirm release.');
        return result;
      }
      case 'start': {
        const raw=Boolean($('record')?.checked),wav=Boolean($('wav-record')?.checked);
        const params={frequency:selectedFrequency(),
          seconds:duration('duration','duration-unit'),
          rate:Number($('rate')?.value||1024000),raw,wav};
        const result=await invoke('capture',params,'device-status');
        say('device-status','Actual native file saved: '+String(result.file||'unknown')+
          (result.wav?' · plus WAV: '+result.wav:'')+
          '. Source and decoded content not verified.');
        say('native-receiver-status','Native capture completed · '+params.seconds+
          ' s · local disk, no browser memory limit or WebUSB');
        return;
      }
      case 'auto-plan': {
        const raw=Boolean($('auto-save-raw')?.checked),
          wav=Boolean($('auto-save-wav')?.checked);
        if(!raw&&!wav) throw Error('Select WAV, CU8 or both for ISS recording');
        const formats=raw&&wav?'both':raw?'cu8':'wav';
        const params={group:$('auto-mode')?.value||'images',
          goal:$('auto-coverage')?.value||'full',
          format:formats,...coordinateArgs()};
        const seconds=duration('auto-browser-seconds','auto-browser-unit');
        if(seconds>=8)params.seconds=seconds;
        const result=await invoke('auto',params,'auto-plan-status');
        say('auto-plan-status',JSON.stringify(result,null,2).slice(0,1200));
        say('native-receiver-status','Native auto scheduling completed; '+String(
          result.scheduled_count||0)+' actual OS-RF jobs stored locally');
        return;
      }
      case 'auto-stop': {
        const result=await invoke('auto_cancel',{},'auto-plan-status');
        say('auto-plan-status','Native auto jobs canceled: '+JSON.stringify(result));
        return;
      }
      case 'schedule-check': {
        const result=await invoke('status',{},'schedule-readiness');
        const hw=result.hardware||{};
        say('schedule-readiness',
          'Native station scheduling. RF enabled: '+Boolean(hw.receiver_enabled)+
          ' · app receiver released: '+Boolean(hw.app_released)+
          ' · pending jobs: '+Number(hw.pending_schedules||0)+
          '. Jobs run only while Satellite Center is open. '+
          'No browser tab, WebUSB or wake lock required; prevent OS sleep.');
        return;
      }
      case 'schedule-wake': {
        say('schedule-readiness',
            'Native process does not need a visible browser tab. '+
            'Keep the PC awake using your OS power settings for scheduled RF acquisition.');
        return;
      }
    }
  };
  // Pass card forms are native SDR schedules, never browser-local/WebUSB jobs.
  document.addEventListener('submit',event=>{
    const form=event.target.closest?.('form.pass-schedule-form');
    if(!form)return;
    event.preventDefault();event.stopImmediatePropagation();
    const card=form.closest('.pass');
    const selections=[...form.querySelectorAll('select')];
    const fields=form.querySelectorAll('input');
    const time=form.querySelector('input[type="datetime-local"]');
    const numeric=form.querySelector('input[type="number"]');
    const checks=[...form.querySelectorAll('input[type="checkbox"]')];
    const warn=form.querySelector('.pass-schedule-error');
    const norad=Number(card?.dataset?.norad);
    const aos_millis=Number(card?.dataset?.aos);
    const at=new Date(time?.value||'').getTime();
    const seconds=Math.round(Number(numeric?.value||0)*
                      (selections[1]?.value==='minutes'?60:1));
    if(!norad||!aos_millis||!Number.isFinite(at)){
      if(warn)warn.textContent='Native pass metadata missing; refresh TLE and recalculate.';
      return;
    }
    const args={...coordinateArgs(),norad,aos_millis,when_millis:at,
      frequency:Number(selections[0]?.value),
      rate:Number(selections[2]?.value||1024000),
      seconds,raw:Boolean(checks[0]?.checked),wav:Boolean(checks[1]?.checked)};
    if(warn)warn.textContent='Verifying native orbital geometry and receiver availability…';
    lookup('schedule',args).then(result=>{
      if(warn)warn.textContent='Native TLE-backed RF capture scheduled: '+
         result.satellite+' · '+result.run_at+' · '+result.capture_seconds+
         ' s. No WebUSB and no fabricated satellite content.';
    }).catch(error=>{
      if(warn)warn.textContent='Native schedule rejected: '+String(error.message);
    });
  },true);

  const controls=new Set([
    'connect','usb-live-test','usb-check','usb-claim-test','usb-copy',
    'disconnect','start','stop','auto-plan','auto-stop',
    'schedule-check','schedule-wake',
  ]);
  document.addEventListener('click',event=>{
    const node=event.target.closest?.('button');
    if(!node||!controls.has(node.id))return;
    event.preventDefault();
    event.stopImmediatePropagation(); // never reach browser.js WebUSB callbacks
    Promise.resolve().then(()=>execute(node.id)).catch(error=>{
      const message=String(error?.message||error);
      say(node.id.startsWith('auto-')?'auto-plan-status':'device-status',
          'Native operation failed: '+message);
      log('Native action '+node.id+' failed: '+message);
    });
  },true);

  const q=document.createElement('script');
  q.src='qrc:///qtwebchannel/qwebchannel.js';
  q.onload=()=>{
    if(!window.qt?.webChannelTransport||!window.QWebChannel){
      log('Native QWebChannel transport missing; RF controls disabled');
      return;
    }
    new QWebChannel(qt.webChannelTransport,channel=>{
      bridge=channel.objects.nativeReceiver;
      bridge.reply.connect((id,payload)=>{
        const waiter=callbacks.get(id);
        if(!waiter)return;
        callbacks.delete(id);
        try{
          const response=JSON.parse(payload);
          if(response.ok)waiter.resolve(response.result);
          else waiter.reject(Error(response.error||'Native command rejected'));
        }catch(error){waiter.reject(error);}
      });
      setHardwareLabels();
      window.nativeWebBridgeReady=true;
      window.nativeRFTransport='rtl_sdr';
      log('Exact bundled web UI ready · native Qt SDR WebChannel · WebUSB DISABLED');
      lookup('status').then(result=>{
        const hw=result.hardware||{};
        say('device-status',hw.receiver_enabled?
          'Physical receiver idle · use Connect to verify actual I/Q samples':
          'RF disabled. Use Connect to test physical USB and enable recordings.');
        say('native-receiver-status','Native OS SDR · no browser USB · '+
          (hw.app_released?'receiver released':'receiver status pending'));
      }).catch(error=>log('Passive USB status: '+error.message));
    });
  };
  q.onerror=()=>log('Qt WebChannel script missing; native RF unavailable');
  document.head.appendChild(q);
})();
