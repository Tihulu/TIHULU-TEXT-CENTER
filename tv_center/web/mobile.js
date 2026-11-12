"use strict";
(() => {
  const el = id => document.getElementById(id);
  let connected = false, busy = false, ticker = null, hls = null;
  const send = async (url, obj) => {
    const response = await fetch(url, {method:"POST", credentials:"same-origin",
      headers:{"Content-Type":"application/json"}, body:JSON.stringify(obj), cache:"no-store"});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || ("HTTP "+response.status));
    return data;
  };
  function disconnect() {
    const wasConnected = connected;
    connected = false;
    clearInterval(ticker); ticker = null;
    if (hls) { hls.destroy(); hls = null; }
    el("tv").pause(); el("tv").removeAttribute("src"); el("tv").load();
    el("pair").disabled = false; el("leave").disabled = true;
    el("start-video").disabled = true; el("open-page").disabled = true;
    el("state").textContent = "NOT PAIRED";
    el("channel").textContent = "Receiver not connected";
    el("source").textContent = "Pair with your native DVB host to see real signals.";
    el("original").textContent = "No active broadcaster captions.";
    el("translated").textContent = "";
    el("caption-source").textContent = "No decoded caption";
    if (wasConnected) document.dispatchEvent(new Event("tihulu-tv-disconnected"));
    // Session cookie remains until host expiry or restart; browser cannot
    // delete it because it is HttpOnly. A host reset revokes sessions.
  }
  async function refresh() {
    if (!connected || busy) return;
    busy = true;
    try {
      const response = await fetch("/api/status", {credentials:"same-origin", cache:"no-store"});
      if (!response.ok) throw new Error("Host session expired or unavailable");
      const data = await response.json();
      el("channel").textContent = data.channel || "No TV channel tuned on host";
      el("source").textContent = data.source === "live_native_dvb" ?
        "Real DVB stream from the connected host. No demo content." :
        "No live DVB signal: tune a channel on the host.";
      el("original").textContent = data.caption?.original || "Waiting for broadcaster captions";
      el("translated").textContent = data.caption?.translated || "";
      el("caption-source").textContent = data.caption?.source || "None";
      el("page").value = data.teletext_page || 150;
      el("state").textContent = data.source === "live_native_dvb" ? "TV TUNED" : "PAIRED";
      el("start-video").disabled = !data.mobile_video;
      el("video-status").textContent = data.mobile_video ?
        "HLS enabled; press Watch live TV to start playing." :
        "Mobile video encoding is OFF. Enable it on the host to share TV.";
    } catch (err) {
      el("pair-note").textContent = err.message;
      disconnect();
    } finally {
      busy = false;
    }
  }
  el("pair").onclick = async () => {
    try {
      await send("/api/pair", {pin:el("pin").value.trim()});
      el("pin").value = ""; connected = true;
      el("pair").disabled = true; el("leave").disabled = false;
      el("open-page").disabled = false;
      await refresh();
      if (connected) {ticker = setInterval(refresh, 1800);
        document.dispatchEvent(new Event("tihulu-tv-connected"));}
    } catch (err) { el("pair-note").textContent = err.message; }
  };
  el("leave").onclick = disconnect;
  el("start-video").onclick = () => {
    const url = "/hls/index.m3u8";
    const video = el("tv");
    if (hls) { hls.destroy(); hls = null; }
    if (video.canPlayType("application/vnd.apple.mpegurl")) {
      video.src = url;
    } else if (window.Hls?.isSupported()) {
      hls = new window.Hls({lowLatencyMode:false, maxBufferLength:12});
      hls.loadSource(url);
      hls.attachMedia(video);
      hls.on(window.Hls.Events.ERROR, (_, err) => {
        if (err.fatal) el("video-status").textContent = "HLS error: "+err.type+"; check host video encoder.";
      });
    } else {
      el("video-status").textContent = "Browser cannot play HLS. Try Safari/Chrome or load hls.js.";
      return;
    }
    video.play().catch(() => { el("video-status").textContent = "Tap Play inside the video player."; });
  };
  el("open-page").onclick = async () => {
    const page = Number(el("page").value);
    if (!Number.isInteger(page) || page < 100 || page > 899) return;
    try {
      await send("/api/teletext", {page});
      el("teletext-result").textContent = "Page "+page+" requested — waits for real broadcast packets.";
    } catch (err) { el("teletext-result").textContent = err.message; }
  };
  document.querySelectorAll("[data-page]").forEach(btn => {
    btn.onclick = () => {el("page").value = btn.dataset.page; if (connected) el("open-page").click();};
  });
  window.tihuluTVWeb = {
    connected:()=>connected,
    get:async path=>{
      const response=await fetch(path,{credentials:"same-origin",cache:"no-store"});
      const data=await response.json();
      if(!response.ok)throw Error(data.error||"HTTP "+response.status);
      return data;
    },
    command:async(action,params)=>{
      const data=await send("/api/command",{action,params});
      return data.result;
    }
  };
  // Previous cookie may be valid; only the host can accept it.
  connected = true;
  refresh().then(() => {
    if (connected) {el("pair").disabled = true; el("leave").disabled = false; el("open-page").disabled = false;
       ticker = setInterval(refresh, 1800);
       document.dispatchEvent(new Event("tihulu-tv-connected"));}
  });
})();
