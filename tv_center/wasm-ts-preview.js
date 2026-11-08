/* Completely browser-local MPEG-TS → preview MP4 with ffmpeg.wasm.
 * Deliberately opt-in because the WASM decoder is large and transcoding DVB-T2
 * HEVC can be very slow. No upload or native backend.
 */
const $=id=>document.getElementById(id);
const status=$("wasm-ts-status");
const video=$("wasm-ts-video");
let ffmpeg=null,outputURL=null,loading=false;
const load=async()=>{
  if(ffmpeg)return ffmpeg;
  status.textContent="Downloading browser FFmpeg/WebAssembly core (large file)…";
  const {FFmpeg}=await import("https://cdn.jsdelivr.net/npm/@ffmpeg/ffmpeg@0.12.10/dist/esm/index.js");
  const {toBlobURL}=await import("https://cdn.jsdelivr.net/npm/@ffmpeg/util@0.12.1/dist/esm/index.js");
  const base="https://cdn.jsdelivr.net/npm/@ffmpeg/core@0.12.10/dist/umd";
  const instance=new FFmpeg();
  instance.on("log",({message})=>{
    if(/time=|Error|Invalid|Stream/i.test(message))
      status.textContent="Local FFmpeg: "+message.slice(0,220);
  });
  await instance.load({
    coreURL:await toBlobURL(base+"/ffmpeg-core.js","text/javascript"),
    wasmURL:await toBlobURL(base+"/ffmpeg-core.wasm","application/wasm")
  });
  ffmpeg=instance;
  return instance;
};
$("wasm-ts-start").onclick=async()=>{
  if(loading)return;
  const file=$("wasm-ts-file").files?.[0];
  if(!file){status.textContent="Choose a real .ts recording from your tuner first.";return;}
  // A bounded memory budget is essential with in-browser HEVC software decode.
  if(file.size>64*1024*1024){
    status.textContent="Recording exceeds 64 MiB. Export a short ~5–15 second .ts sample.";return;
  }
  loading=true;$("wasm-ts-start").disabled=true;
  try{
    const engine=await load();
    const input=new Uint8Array(await file.arrayBuffer());
    status.textContent="Demuxing real transport stream and decoding first 5 seconds entirely in WASM…";
    await engine.writeFile("input.ts",input);
    // The standard GPL ffmpeg.wasm core includes libx264 in supported builds.
    // If codec is unavailable this must report a real error, not fake video.
    const code=await engine.exec([
      "-hide_banner","-y","-analyzeduration","2000000",
      "-probesize","2000000","-i","input.ts",
      "-t","5","-map","0:v:0?","-map","0:a:0?",
      "-vf","scale=w='min(640,iw)':h=-2",
      "-c:v","libx264","-preset","ultrafast","-crf","33",
      "-pix_fmt","yuv420p",
      "-c:a","aac","-b:a","96k",
      "-movflags","+faststart","preview.mp4"
    ],120000);
    if(code!==0)throw Error("FFmpeg returned code "+code+" (video codec may be unsupported)");
    const bytes=await engine.readFile("preview.mp4");
    if(bytes.length<500)throw Error("No decodable video/audio in recording");
    if(outputURL)URL.revokeObjectURL(outputURL);
    outputURL=URL.createObjectURL(new Blob([bytes],{type:"video/mp4"}));
    video.src=outputURL;video.hidden=false;
    await video.play().catch(()=>{});
    status.textContent="Decoded real recorded DVB transport stream in-browser: first 5 seconds. No upload or native receiver.";
    await engine.deleteFile("preview.mp4").catch(()=>{});
    await engine.deleteFile("input.ts").catch(()=>{});
  }catch(error){
    status.textContent="In-browser TS preview could not decode: "+(error?.message||error)+
      ". Check the recording, codec support, memory, CDN and browser console.";
  }finally{
    loading=false;$("wasm-ts-start").disabled=false;
  }
};
$("wasm-ts-unload").onclick=()=>{
  if(ffmpeg){ffmpeg.terminate();ffmpeg=null;}
  if(outputURL){URL.revokeObjectURL(outputURL);outputURL=null;}
  video.pause();video.removeAttribute("src");video.load();video.hidden=true;
  status.textContent="Browser decoder unloaded; no local server used.";
};
window.addEventListener("pagehide",()=>{
  if(outputURL)URL.revokeObjectURL(outputURL);
  ffmpeg?.terminate();
});
