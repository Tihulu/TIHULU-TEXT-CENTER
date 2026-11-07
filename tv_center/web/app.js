"use strict";
/* Tokenless TV Web Companion.
 * GitHub Pages: public non-sensitive local-health check + one-click navigation.
 * localhost: same-origin direct DVB commands, real subtitles and optional HLS.
 * No bearer tokens, no cookies, no WebUSB tuner illusion.
 */
(() => {
  const $=id=>document.getElementById(id);
  const LOOPBACK="http://127.0.0.1:8768";
  const local=location.protocol==="http:" &&
    ["127.0.0.1","localhost"].includes(location.hostname) &&
    location.port==="8768";
  let connected=false,timer=null,busy=false,hls=null;
  let videoActive=false;

  const state=text=>{$("state").textContent=text};
  const note=text=>{$("connection-note").textContent=text};

  function reset(message="Native receiver disconnected.") {
    const previous=connected;
    connected=false;busy=false;
    if(timer){clearInterval(timer);timer=null;}
    $("open-page").disabled=true;
    $("channel").textContent="No local receiver connected";
    $("source").textContent="Real DVB requires a running native Linux/Pi receiver.";
    $("original").textContent="No broadcaster caption decoded";
    $("translated").textContent="";
    $("caption-source").textContent="None";
    $("video-start").disabled=true;
    $("video-stop").disabled=true;
    state(local?"LOCAL TV OFFLINE":"WEBUSB / BROWSER AI");
    note(message);
    if(previous)document.dispatchEvent(new Event("tihulu-tv-disconnected"));
  }

  async function api(path,method="GET",payload=null){
    if(!local)throw Error("Open Local TV first; Pages cannot directly control a physical tuner.");
    const response=await fetch(path,{
      method,cache:"no-store",credentials:"same-origin",
      headers:{"Content-Type":"application/json"},
      ...(payload?{body:JSON.stringify(payload)}:{})
    });
    let data;
    try{data=await response.json();}
    catch{throw Error("Local TV sent an invalid response (HTTP "+response.status+")");}
    if(!response.ok)throw Error(data.error||"Local TV HTTP "+response.status);
    return data;
  }
  async function health(){
    if(local)return api("/api/health");
    // Only /api/health allows limited cross-origin read. Real tuner commands
    // are permitted exclusively when the page itself is served on localhost.
    const response=await fetch(LOOPBACK+"/api/health",{
      method:"GET",cache:"no-store",mode:"cors",credentials:"omit"
    });
    if(!response.ok)throw Error("Local TV HTTP "+response.status);
    const data=await response.json();
    if(data.app!=="tihulu-tv-center"||data.mode!=="tokenless_loopback")
      throw Error("Unexpected application on the local TV port");
    return data;
  }
  async function refresh(){
    if(!connected||busy)return;
    busy=true;
    try{
      const data=await api("/api/status");
      $("channel").textContent=data.channel||"No tuned TV channel";
      $("source").textContent=data.source==="live_native_dvb"
        ?"Live native Linux DVB receiver connected. Genuine broadcast source."
        :"Local TV is connected but no channel is tuned.";
      $("original").textContent=data.caption?.original||"No actual caption decoded yet";
      $("translated").textContent=data.caption?.translated||"";
      $("caption-source").textContent=data.caption?.source||"none";
      $("page").value=data.teletext_page||150;
      const live=data.source==="live_native_dvb";
      $("video-start").disabled=!live;
      $("video-stop").disabled=!data.mobile_video;
      $("video-status").textContent=live
        ?data.mobile_video
          ?"Live HLS encoder is on. Use Watch video to play the real local broadcast."
          :"Channel tuned. Enable live web video when needed (CPU intensive)."
        :"Tune a real channel from the channel list to enable video.";
      state(live?"LIVE DVB · LOCAL":"LOCAL TV CONNECTED");
      note("Connected automatically on localhost. No token or pairing required on this computer.");
    }catch(err){
      reset("Native receiver stopped: "+err.message);
    }finally{busy=false;}
  }

  async function initialize(){
    if(!local){
      state("WEBUSB / BROWSER AI");
      note("GitHub Pages needs no token. To scan/watch DVB, open the token-free local web app on this computer.");
      try{
        await health();
        state("LOCAL TV FOUND");
        note("Local TV Center detected. Open it with the link above; no token or login.");
      }catch(err){
        note("Local receiver not detected or browser blocked localhost discovery. Start tihulu-tv-center, then click Open Local TV. No token is needed.");
      }
      return;
    }
    try{
      await health();
      const data=await api("/api/status");
      connected=true;
      $("open-page").disabled=false;
      document.dispatchEvent(new Event("tihulu-tv-connected"));
      state("LOCAL TV CONNECTED");
      await refresh();
      timer=setInterval(refresh,1700);
    }catch(err){
      reset("Could not connect to local TV: "+err.message);
    }
  }

  $("connect").onclick=async()=>{
    $("connect").disabled=true;
    if(local){
      await initialize();
    }else{
      try{await health();state("LOCAL TV FOUND");
        note("Local TV is available — click Open Local TV. No token required.");}
      catch(err){note("Local TV unavailable or browser discovery blocked; click Open Local TV to test directly.");}
    }
    $("connect").disabled=false;
  };

  $("open-page").onclick=async()=>{
    if(!connected)return;
    const page=Number($("page").value);
    if(!Number.isInteger(page)||page<100||page>899){
      $("teletext-result").textContent="Use a page from 100 to 899.";return;
    }
    try{
      await api("/api/teletext","POST",{page});
      $("teletext-result").textContent="Page "+page+
        " requested from actual transport packets; availability depends on broadcaster.";
    }catch(err){$("teletext-result").textContent=err.message;}
  };
  for(const button of document.querySelectorAll("[data-page]")){
    button.onclick=()=>{
      $("page").value=button.dataset.page;
      if(connected)$("open-page").click();
    };
  }

  function unloadVideo(){
    if(hls){hls.destroy();hls=null;}
    $("tv").pause();$("tv").removeAttribute("src");$("tv").load();
    videoActive=false;
  }
  $("video-start").onclick=async()=>{
    if(!connected)return;
    $("video-start").disabled=true;
    try{
      await api("/api/command","POST",{action:"video_start",params:{}});
      const video=$("tv"),url="/hls/index.m3u8";
      unloadVideo();
      if(video.canPlayType("application/vnd.apple.mpegurl")){
        video.src=url;
      }else if(window.Hls?.isSupported()){
        hls=new window.Hls({lowLatencyMode:false,maxBufferLength:10});
        hls.loadSource(url);
        hls.attachMedia(video);
        hls.on(window.Hls.Events.ERROR,(_,err)=>{
          if(err.fatal)$("video-status").textContent=
            "HLS decode error: "+err.type+". Inspect TV Center encoder and reception.";
        });
      }else{
        throw Error("Browser lacks HLS playback. Try Chromium/Firefox with hls.js, or Safari.");
      }
      videoActive=true;
      video.play().catch(()=>{$("video-status").textContent="Click Play on the video player.";});
      $("video-stop").disabled=false;
      $("video-status").textContent="Real native DVB stream via local H.264/AAC HLS (may lag).";
    }catch(err){$("video-status").textContent="Live video unavailable: "+err.message;}
    finally{$("video-start").disabled=false;}
  };
  $("video-stop").onclick=async()=>{
    unloadVideo();
    try{if(connected)await api("/api/command","POST",{action:"video_stop",params:{}});}
    catch(err){$("video-status").textContent="Stop encoder: "+err.message;}
    $("video-stop").disabled=true;
  };

  $("check-compute").onclick=async()=>{
    const wasm=typeof WebAssembly!=="undefined";
    let gpu="unavailable";
    if(navigator.gpu){
      try{gpu=(await navigator.gpu.requestAdapter())?"adapter detected":"adapter unavailable";}
      catch{gpu="adapter check failed";}
    }
    $("compute-status").textContent=
      "WebAssembly: "+(wasm?"available":"unavailable")+
      " · WebGPU: "+gpu+
      " · Browser speech models load only after you request them in Browser AI Studio.";
  };

  window.tihuluTVWeb={
    connected:()=>connected,
    get:path=>api(path),
    command:async(action,params)=>{
      const data=await api("/api/command","POST",{action,params});
      return data.result;
    }
  };
  window.addEventListener("pagehide",()=>{if(timer)clearInterval(timer);unloadVideo();});
  void initialize();
})();