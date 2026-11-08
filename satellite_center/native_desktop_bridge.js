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
  let radioPending=null;
  const radioControls=['connect','usb-live-test','usb-claim-test','start','auto-plan'];
  const updateRadioControls=()=>{
    for(const id of radioControls){
      const el=$(id);if(!el)continue;
      if(radioPending)el.disabled=true;
      else if(id==='start')el.disabled=!hardwareState.enabled;
      else el.disabled=false;
    }
  };
  const showNativeStatus=(response)=>{
    const hw=response?.hardware||{};
    const present=(hw.usb_devices||[]).some(d=>d.receiver_type==='rtl_sdr') ||
      Number(hw.usb_rtl_count)>0;
    hardwareState.enabled=hw.receiver_enabled===true;
    hardwareState.verified=hardwareState.enabled;
    const receiver=(hw.usb_devices||[]).find(d=>d.receiver_type==='rtl_sdr');
    const active=response?.session?.active===true;
    const phase=active?'RECORDING · native SDR process running':
      hardwareState.enabled?'READY · real IQ tested; receiver armed':
      present?'DETECTED · press Connect to verify actual IQ':'NO COMPATIBLE SDR DETECTED';
    say('native-receiver-status',phase);
    say('native-rx-phase',phase);
    say('native-rx-device',receiver?.name||'No RTL-SDR hardware detected');
    say('native-rx-driver',receiver
      ? 'Physical USB '+receiver.vendor_id+':'+receiver.product_id+
        ' · OS native rtl_sdr · no WebUSB'
      : 'No usable USB RTL-SDR interface found; DVB TV cards are separate');
    say('native-rx-usb',receiver?'Detected via Linux USB':'Not detected');
    say('native-rx-iq',hw.last_real_sample?.sample_bytes
      ? hw.last_real_sample.sample_bytes.toLocaleString()+' physical CU8 bytes verified'
      : 'Not verified in this session');
    say('native-rx-capture',active?'Recording in progress':
      hardwareState.enabled?'Armed; click Start direct native RF capture':
      'Disabled until USB + IQ verification succeeds');
    say('native-rx-release',hw.app_released
      ? 'Released while idle · available for other SDR apps'
      : active?'Owned by Satellite Center recording':
               'Busy, connecting or release not yet confirmed');
    say('native-rx-pll',hw.last_real_sample?.pll_warning===true
      ? 'PLL warning observed · tuner lock not proven'
      : 'PLL lock not independently verified');
    if($('native-hardware-card')){
      const card=$('native-hardware-card');
      card.dataset.state=active?'recording':hardwareState.enabled?'ready':
        present?'detected':'missing';
    }
    updateRadioControls();
    if($('disconnect'))$('disconnect').disabled=!hardwareState.enabled;
    return response;
  };
  const refreshNativeStatus=async()=>showNativeStatus(await lookup('status'));
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
      if(command==='connect'||command==='sample')
        say('native-rx-phase','CONNECT FAILED · '+message);
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
    // Web-style worldwide city suggestions should work while typing in the
    // *installed* desktop by default. No location data is requested at startup:
    // actual Open-Meteo requests occur only after user types >=3 characters,
    // with the same web debounce/fair-use/cancel logic. The checkbox remains
    // visible and user-controlled; turning it off restores offline-only typing.
    const onlineSuggest=$('city-online-toggle');
    if(onlineSuggest){
      onlineSuggest.checked=true;
      onlineSuggest.dispatchEvent(new Event('change',{bubbles:true}));
      const label=onlineSuggest.closest('label');
      if(label)label.title='Native desktop: worldwide suggestions are enabled while typing. Uncheck to keep searches offline.';
    }
    // Do not claim the native local-disk capture uses WebUSB 60-second
    // segmenting. Keep the exact controls/layout but correct device copy.
    const formatSummary=$('auto-format-summary');
    if(formatSummary){
      formatSummary.textContent=formatSummary.textContent
        .replace(/WebUSB automatic jobs/g,'native RTL-SDR automatic jobs')
        .replace(/WebUSB/g,'native SDR');
    }
    const misleading=document.querySelectorAll(
      'a[href^="http://127.0.0.1:8791/"]');
    for(const link of misleading){
      // Optional localhost helper belongs to the browser edition only.
      link.title='Optional legacy browser companion; not needed for native desktop';
      const parent=link.closest('p.hint');
      if(parent && /Firefox|WebUSB|browser/i.test(parent.textContent||'')){
        parent.hidden=true;
      }
    }
    const install=document.querySelector('#desktop-install');
    if(install)install.hidden=true; // PWA install is browser-only, desktop is installed.
    for(const id of ['connect','usb-live-test','disconnect','start','stop']){
      if($(id))$(id).disabled=false;
    }
    if($('connect'))$('connect').textContent='Connect & enable RF (USB + real IQ)';
    if($('usb-live-test'))$('usb-live-test').textContent='IQ test only (does not enable RF)';
    if($('disconnect')){
      $('disconnect').textContent='Stop & disconnect RF';
      $('disconnect').disabled=false;
    }
    if($('usb-check'))$('usb-check').textContent='Refresh Linux USB/process status';
    if($('usb-claim-test'))$('usb-claim-test').textContent='USB access check only (does not enable RF)';
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
    // Browser-only troubleshooting copy is inaccurate in the native build.
    // The device lifecycle is verified with rtl_test/rtl_sdr, not a chooser.
    const usbHints=document.querySelectorAll('details');
    for(const details of usbHints){
      const body=details.textContent||'';
      if(body.includes('USB not connecting?') && body.includes('browser will show')){
        details.querySelectorAll('p').forEach(p=>{
          if(/browser will show|WebUSB|Chrome|chooser/i.test(p.textContent||'')){
            p.textContent='Native Linux receiver diagnostics use rtl_test and rtl_sdr. If the device is busy, inspect readsb, other SDR applications and DVB kernel drivers. Disconnect only releases processes owned by this app.';
          }
        });
      }
    }
    const status=$('usb-live-test-report');
    if(status)status.textContent='The desktop tests real IQ using rtl_sdr, not browser WebUSB.';
    const state=document.createElement('p');
    state.className='status';
    state.id='native-receiver-status';
    state.textContent='Same web UI · OS-native SDR · no WebUSB · no radio capture on startup';
    $('device-status')?.after(state);
    const card=document.createElement('div');
    card.id='native-hardware-card';
    card.className='native-hardware-card';
    card.setAttribute('role','group');
    card.setAttribute('aria-label','Direct receiver hardware dashboard');
    card.innerHTML=`
      <div class="native-hardware-heading">
        <strong>Receiver status</strong>
        <small>Flight Radar-style native lifecycle · direct RTL-SDR</small>
      </div>
      <p id="native-rx-phase" class="native-hardware-phase">Checking USB inventory…</p>
      <strong id="native-rx-device">Receiver information pending</strong>
      <p id="native-rx-driver" class="native-hardware-sub">OS device enumeration</p>
      <div class="native-hardware-grid">
        <div><small>USB hardware</small><span id="native-rx-usb">Checking</span></div>
        <div><small>Actual I/Q sample</small><span id="native-rx-iq">Not yet tested</span></div>
        <div><small>RF recording</small><span id="native-rx-capture">Not armed</span></div>
        <div><small>Resource ownership</small><span id="native-rx-release">Checking</span></div>
        <div><small>Tuner lock</small><span id="native-rx-pll">Not independently verified</span></div>
      </div>
      <p class="native-hardware-sub">Connect verifies real bytes and arms recording; USB access check alone never enables RF. No Internet data is labelled as radio reception.</p>`;
    const style=document.createElement('style');
    style.textContent=`
      .native-hardware-card{margin:12px 0 16px;padding:16px;border:1px solid #506c83;
        border-radius:14px;background:linear-gradient(135deg,rgba(19,48,64,.55),rgba(20,30,45,.18))}
      .native-hardware-heading{display:flex;flex-wrap:wrap;gap:8px;
        justify-content:space-between;align-items:center}
      .native-hardware-heading small,.native-hardware-sub{font-size:.82em;opacity:.78}
      .native-hardware-phase{font-weight:700;font-size:1.03em;margin:12px 0;
        padding:8px 12px;border-radius:8px;background:rgba(128,145,165,.12)}
      .native-hardware-card[data-state=ready] .native-hardware-phase{color:#52c7a8}
      .native-hardware-card[data-state=recording] .native-hardware-phase{color:#fbbf67}
      .native-hardware-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(175px,1fr));
        gap:8px;margin:12px 0}
      .native-hardware-grid>div{padding:9px;border:1px solid rgba(145,165,184,.22);
        border-radius:9px;min-width:0}
      .native-hardware-grid small{display:block;opacity:.75;font-size:.75em;margin-bottom:5px}
      .native-hardware-grid span{display:block;overflow-wrap:anywhere;font-size:.9em}`;
    document.head.appendChild(style);
    state.after(card);
    const help=document.createElement('p');
    help.className='hint';
    help.textContent='To record from your Nooelec NESDR, use the FIRST blue button: Connect & enable RF (USB + real IQ). USB access check and IQ test are diagnostics ONLY and do not enable recording. The SDR is intentionally released while idle.';
    card.after(help);
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
        if($('connect'))$('connect').disabled=true;
        try{
          say('device-status','Connecting: checking physical USB (rtl_test) then acquiring a real 1 MiB IQ sample (rtl_sdr). A successful USB-open test alone does not enable RF.');
          const result=await invoke('connect',{},'device-status');
          if(result.receiver_enabled!==true ||
             result.sample_test?.state!=='real_iq_samples_received')
            throw Error('Backend did not confirm both real IQ capture and enabled RF');
          say('device-status','RF ENABLED · '+result.sample_test.sample_bytes+
            ' physical IQ bytes verified. PLL and actual satellite reception remain unverified.');
          say('usb-live-test-report','Real IQ verified; RTL-SDR is released while idle.');
          return result;
        }finally{
          if($('connect'))$('connect').disabled=false;
          await refreshNativeStatus();
        }
      }
      case 'usb-live-test': {
        const result=await invoke('sample',{frequency:selectedFrequency()},'usb-live-test-report');
        hardwareState.actualIQ=true;
        say('usb-live-test-report',
          'IQ DIAGNOSTIC PASS · '+result.complex_samples+' physical complex IQ samples at '+
          (result.frequency_hz/1e6).toFixed(3)+
          ' MHz. Process released. This test DOES NOT enable RF recording; use Connect & enable RF.');
        await refreshNativeStatus();
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
        const status=await refreshNativeStatus();
        const armed=status.hardware?.receiver_enabled===true;
        say('usb-claim-result',
          'USB ACCESS DIAGNOSTIC PASS · '+String(result.state)+
          '\nOnly USB open/release was tested; no IQ sample was acquired by this action.'+
          '\nRF recording: '+(armed?'already enabled from a separate Connect action':
            'DISABLED. Press the FIRST blue Connect & enable RF (USB + real IQ) button to activate.')+
          '\n\nRaw USB evidence:\n'+JSON.stringify(result,null,2));
        say('device-status',armed
          ? 'USB open check passed · RF already enabled from prior Connect.'
          : 'USB open check passed · RF is still DISABLED. Click Connect & enable RF above.');
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
        await refreshNativeStatus();
        say('device-status','RF disabled · '+result.pending_jobs_paused+
          ' pending jobs paused. Receiver released: '+Boolean(result.app_released));
        return;
      }
      case 'stop': {
        const result=await invoke('stop',{},'device-status');
        say('device-status','Stop requested for native owned SDR capture. '+
          'Refresh USB status to confirm release.');
        return result;
      }
      case 'start': {
        const check=await refreshNativeStatus();
        if(check.hardware?.receiver_enabled!==true)
          throw Error('RF disabled. Click Connect & verify physical RTL-SDR before starting a recording.');
        const raw=Boolean($('record')?.checked),wav=Boolean($('wav-record')?.checked);
        const params={frequency:selectedFrequency(),
          seconds:duration('duration','duration-unit'),
          rate:Number($('rate')?.value||1024000),raw,wav};
        if(!raw&&!wav)throw Error('Select CU8, WAV or both');
        try{
          const result=await invoke('capture',params,'device-status');
          if(!result.file||!Number(result.bytes))
            throw Error('Native recorder did not confirm a nonempty saved file');
          say('device-status','SAVED REAL RF · '+result.file+' · '+
            Number(result.bytes).toLocaleString()+' bytes. Satellite source not verified.');
          return result;
        }finally{
          await refreshNativeStatus();
        }
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
  // They reuse browser HTML, but every scheduling hint/budget must describe
  // the native OS receiver rather than WebUSB's <=60 second segmented capture.
  const enhanceNativePassForm=form=>{
    if(!form)return;
    const card=form.closest('.pass');
    const norad=Number(card?.dataset?.norad);
    const selects=[...form.querySelectorAll('select')];
    const checks=[...form.querySelectorAll('input[type="checkbox"]')];
    const secondsInput=form.querySelector('input[type="number"]');
    const freq=selects[0],unit=selects[1],rate=selects[2];
    const raw=checks[0],wav=checks[1];
    if(!freq||!raw||!wav)return;
    const hint=form.querySelector('p.hint.schedule-wide');
    const budget=form.querySelector('.schedule-capture-budget');
    const legacyLink=form.querySelector('a[href^="http://127.0.0.1:8791/"]');
    if(legacyLink)legacyLink.hidden=true;
    const update=()=>{
      const hz=Number(freq.value);
      const meteor=(norad===57166||norad===59051);
      const supportsWav= !meteor && [145800000,437550000,437800000].includes(hz);
      wav.disabled=!supportsWav;
      if(!supportsWav){wav.checked=false;raw.checked=true;}
      wav.title=supportsWav
        ?'ISS FM WAV audio is available for this selected downlink'
        :'This native profile does not support FM WAV. Meteor LRPT requires original IQ (.cu8).';
      if(hint)hint.textContent=
        'Native OS RTL-SDR: continuous local-disk IQ recording up to 900 seconds / 2 GB, '+
        'if this duration fits the predicted pass. No WebUSB, browser downloads, '+
        'or 60-second file segmentation. Keep the PC awake and Satellite Center running.';
      if(budget){
        const n=Number(secondsInput?.value||0);
        const secs=Math.round(n*(unit?.value==='minutes'?60:1));
        const sr=Number(rate?.value||1024000);
        const bytes=secs*((raw.checked?2*sr:0)+(wav.checked?96000:0));
        const tooLarge=bytes>2000000000;
        budget.textContent=secs<=900
          ?'Native capture: 1 continuous file · '+secs+' s · '+
            (bytes/1e6).toFixed(1)+' MB estimated'+
            (tooLarge?' · exceeds the 2 GB safety cap':'')+
            '. Must finish before predicted LOS.'
          :'Native long request: '+secs+' s. Exceeds 900 s single-file limit; '+
            'separate OS capture segments and restart gaps required. '+
            'All segments must fit the predicted pass.';
      }
    };
    if(form.dataset.nativeScheduleEnhanced!=='true'){
      form.dataset.nativeScheduleEnhanced='true';
      for(const el of [freq,unit,rate,raw,wav,secondsInput]){
        el?.addEventListener('change',update);
        if(el===secondsInput)el?.addEventListener('input',update);
      }
    }
    update();
  };
  const enhanceAllNativePassForms=()=>{
    document.querySelectorAll('form.pass-schedule-form').forEach(enhanceNativePassForm);
  };
  enhanceAllNativePassForms();
  const passList=$('passes');
  if(passList){
    new MutationObserver(entries=>{
      if(entries.some(entry=>entry.addedNodes.length))
        enhanceAllNativePassForms();
    }).observe(passList,{childList:true,subtree:true});
  }
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
    // Guard against stale/browser-only media selections, including imported
    // form state from before the desktop native bridge was initialized.
    enhanceNativePassForm(form);
    const args={...coordinateArgs(),norad,aos_millis,when_millis:at,
      frequency:Number(selections[0]?.value),
      rate:Number(selections[2]?.value||1024000),
      seconds,raw:Boolean(checks[0]?.checked),wav:Boolean(checks[1]?.checked)};
    if(!args.raw&&!args.wav){
      if(warn)warn.textContent='Choose original IQ (.cu8), or ISS FM WAV when supported.';
      return;
    }
    if((norad===57166||norad===59051)&&(!args.raw||args.wav)){
      if(warn)warn.textContent='Meteor LRPT requires original IQ (.cu8) only. Disable WAV / Robot36.';
      return;
    }
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
    const ownsRadio=radioControls.includes(node.id);
    if(ownsRadio&&radioPending){
      say('device-status','Receiver busy with '+radioPending+
        '. Do not start another USB test until this operation finishes.');
      return;
    }
    if(ownsRadio){radioPending=node.id;updateRadioControls();}
    Promise.resolve().then(()=>execute(node.id)).catch(error=>{
      const message=String(error?.message||error);
      say(node.id.startsWith('auto-')?'auto-plan-status':'device-status',
          'Native operation failed: '+message);
      log('Native action '+node.id+' failed: '+message);
    }).finally(()=>{
      if(ownsRadio){radioPending=null;updateRadioControls();}
      if(bridge)refreshNativeStatus().catch(error=>
        log('Status refresh after '+node.id+': '+error.message));
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
      // The installed custom-scheme page cannot rely on cross-origin browser
      // fetch for world geocoding. Route opt-in queries through OS HTTPS.
      // Reuse the exact same location widget, validation and provider data.
      window.nativeLocationLookup=(name,country='all')=>
        lookup('geocode',{name,country});
      // Desktop orbital data never uses blocked cross-origin fetch in the
      // embedded custom-scheme page. Python fetches whitelisted HTTPS TLEs,
      // Skyfield computes real TLE geometry; website keeps its own JS path.
      window.nativeOrbitCatalog=()=>lookup('tle_catalog');
      window.nativeCustomTle=norad=>lookup('tle_custom',{norad});
      window.nativeOrbitPasses=(lat,lon,hours,elevation)=>
        lookup('passes',{lat,lon,hours,elevation});
      window.nativeOrbitSnapshot=(lat,lon,at_ms,tracks=false)=>
        lookup('orbit_snapshot',{lat,lon,at_ms,tracks});
      window.nativeWorldOutline=()=>lookup('world_outline');
      window.nativeImportTle=text=>lookup('tle_import',{text});
      setHardwareLabels();
      window.nativeWebBridgeReady=true;
      window.nativeRFTransport='rtl_sdr';
      log('Exact bundled web UI ready · native Qt SDR WebChannel · WebUSB DISABLED');
      refreshNativeStatus().then(result=>{
        say('device-status',result.hardware?.receiver_enabled?
          'Native RF enabled · press Start native RF capture to record':
          'RF disabled · press Connect & verify physical RTL-SDR to arm real recording');
      }).catch(error=>log('Passive USB status: '+error.message));
    });
  };
  q.onerror=()=>log('Qt WebChannel script missing; native RF unavailable');
  document.head.appendChild(q);
})();
