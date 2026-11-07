// One-click receive-only selection for the shared browser frontend.
// Forecast geometry is not a downlink activity check. A single RTL-SDR can
// service at most one RF capture at once; never use unnamed CubeSat frequencies.
// Series 35 event date envelope only: exact UTC activation/deactivation
// times are still TBD. Passing this gate never proves ISS is transmitting.
export const ISS_SSTV_WINDOW=Object.freeze({
 start:Date.parse("2026-11-09T00:00:00Z"),
 end:Date.parse("2026-11-17T00:00:00Z"),
 source:"https://www.ariss.org/upcoming-sstv-events.html",
 frequencyHz:437550000,
});
export function issSstvDateEligible(time){
 const t=Number(time);
 return Number.isFinite(t)&&t>=ISS_SSTV_WINDOW.start&&t<ISS_SSTV_WINDOW.end;
}
export const AUTO_TARGETS=Object.freeze({
  "meteor-m2-3":Object.freeze({norad:57166,frequencyHz:137900000,kind:"Earth image candidate",dataKind:"image",minimumSeconds:120}),
  "meteor-m2-4":Object.freeze({norad:59051,frequencyHz:137900000,kind:"Earth image candidate",dataKind:"image",minimumSeconds:120}),
  "iss-sstv":Object.freeze({norad:25544,frequencyHz:437550000,kind:"Robot36 event candidate",dataKind:"image",minimumSeconds:45}),
  "iss-aprs":Object.freeze({norad:25544,frequencyHz:437825000,kind:"AX.25/APRS packet candidate",dataKind:"text",minimumSeconds:20}),
  "iss-voice":Object.freeze({norad:25544,frequencyHz:437800000,kind:"ISS FM voice candidate",dataKind:"audio",minimumSeconds:20}),
});
export const AUTO_PRESETS=Object.freeze({
  images:Object.freeze(["meteor-m2-3","meteor-m2-4","iss-sstv"]),
  "iss-images":Object.freeze(["iss-sstv"]),
  messages:Object.freeze(["iss-aprs"]),
  voice:Object.freeze(["iss-voice"]),
  all:Object.freeze(["meteor-m2-3","meteor-m2-4","iss-sstv","iss-aprs","iss-voice"])
});
export function selectAutomaticPasses(passes,{mode="images",now=Date.now(),maxJobs=6,
  existingJobs=[],goal="full",durationSeconds=60}={}){
  if(!Object.hasOwn(AUTO_PRESETS,mode))throw Error("Unknown automatic reception category");
  if(!Number.isFinite(now)||!Number.isInteger(maxJobs)||maxJobs<1||maxJobs>12)
    throw Error("Invalid automatic scheduling limits");
  if(!Array.isArray(passes)||!Array.isArray(existingJobs))throw Error("Invalid pass/job data");
  if(!["full","sample"].includes(goal))throw Error("Unknown reception coverage goal");
  if(!Number.isInteger(durationSeconds)||durationSeconds<8||durationSeconds>900)
    throw Error("Total browser recording must be 8–900 seconds and will be segmented into safe clips");
  const chosen=AUTO_PRESETS[mode],scheduled=[],skipped=[],recommendations=[];
  // If both ISS APRS and SSTV are requested, alternate them across separate
  // passes; one receiver cannot sample two simultaneous downlinks.
  const counts=Object.fromEntries(chosen.map(key=>[key,
    existingJobs.filter(j=>j.missionId===key&&["armed","starting","running"].includes(j.state)).length]));
  const blocked=existingJobs.filter(job=>["armed","starting","running"].includes(job.state))
    .map(job=>[Number(job.passAos),Number(job.passLos)])
    .filter(([a,b])=>Number.isFinite(a)&&Number.isFinite(b)&&b>a);
  for(const pass of [...passes].sort((a,b)=>a.aos-b.aos)){
    if(scheduled.length>=maxJobs)break;
    if(!pass||!Number.isFinite(pass.aos)||!Number.isFinite(pass.los)||pass.los<=pass.aos)continue;
    const targets=chosen.filter(key=>AUTO_TARGETS[key].norad===Number(pass.id));
    const eligible=targets.filter(key=>key!=="iss-sstv"||issSstvDateEligible(pass.aos));
    if(targets.includes("iss-sstv")&&!issSstvDateEligible(pass.aos)){
      skipped.push({name:pass.name,reason:"ISS Series 35 SSTV is scheduled only for 9–16 November 2026; exact activation times still TBD"});
    }
    if(!eligible.length)continue;
    // Each individual WebUSB CU8 clip is ≤60 s / 128 MiB.
    // Longer Meteor LRPT acquisition requests create multiple recordings
    // with real SDR-reset gaps, never a seamless full-pass RF claim.
    const viable=eligible.filter(key=>goal==="sample"||AUTO_TARGETS[key].minimumSeconds<=durationSeconds);
    if(!viable.length){
      skipped.push({name:pass.name,reason:"Meteor LRPT image needs longer than browser 60 s; use native SatDump and full-pass disk recording"});
      recommendations.push({name:pass.name,kind:"image",recommended:"Native full-pass capture, not a 60-second browser sample"});
      continue;
    }
    const matched=viable.sort((a,b)=>counts[a]-counts[b])[0];
    const start=Math.max(pass.aos-10000,now+30000);
    const until=Number(pass.los);
    // The browser splits long captures; budget actual receiver restart gaps.
    const resetSeconds=2*Math.max(0,Math.ceil(durationSeconds/60)-1);
    if(start+(durationSeconds+resetSeconds)*1000>until){skipped.push({name:pass.name,reason:"Pass too short or begins too soon"});continue;}
    if(blocked.some(([a,b])=>start<b+20000&&until>a-20000)){
      skipped.push({name:pass.name,reason:"Single receiver conflict with an armed pass"});continue;
    }
    const target=AUTO_TARGETS[matched];
    const windowSeconds=Math.floor((until-start)/1000);
    const coverage=windowSeconds<=durationSeconds+resetSeconds?"full-pass-attempt-with-gaps":"partial-pass";
    const limitation=target.minimumSeconds>60?
      "Meteor may need full continuous LRPT; separate RF clips contain unrecorded receiver-restart gaps":
      target.dataKind==="text"?
      "Browser can capture packet RF but cannot validate APRS text without a native decoder":
      "Recording is only a downlink candidate; complete decoded media is not guaranteed";
    scheduled.push({pass,missionId:matched,when:start,until,
      frequency:target.frequencyHz,sampleRate:1024000,durationSeconds,
      estimatedBytes:durationSeconds*1024000*2,targetSeconds:windowSeconds,
      shortfallSeconds:Math.max(0,windowSeconds-durationSeconds),coverage,
      dataKind:target.dataKind,limitation,
      saveRaw:true,description:target.kind});
    blocked.push([start,until]);
    counts[matched]++;
  }
  return {scheduled,skipped,recommendations,requestedTargets:[...chosen],
    note:"Browser divides up to 900 s of requested RF time into separate ≤60 s CU8 clips with 2 s unrecorded SDR restart gaps. Multiple downloads need browser permission. Continuous Meteor LRPT image reconstruction is NOT guaranteed; native single-file capture is recommended for best results."};
}
