// One-click receive-only selection for the shared browser frontend.
// Forecast geometry is not a downlink activity check. A single RTL-SDR can
// service at most one RF capture at once; never use unnamed CubeSat frequencies.
export const AUTO_TARGETS=Object.freeze({
  "meteor-m2-3":Object.freeze({norad:57166,frequencyHz:137900000,kind:"Earth image candidate"}),
  "meteor-m2-4":Object.freeze({norad:59051,frequencyHz:137900000,kind:"Earth image candidate"}),
  "iss-sstv":Object.freeze({norad:25544,frequencyHz:437550000,kind:"Robot36 event candidate"}),
  "iss-aprs":Object.freeze({norad:25544,frequencyHz:437825000,kind:"AX.25/APRS packet candidate"}),
});
export const AUTO_PRESETS=Object.freeze({
  images:Object.freeze(["meteor-m2-3","meteor-m2-4","iss-sstv"]),
  messages:Object.freeze(["iss-aprs"]),
  all:Object.freeze(["meteor-m2-3","meteor-m2-4","iss-sstv","iss-aprs"])
});
export function selectAutomaticPasses(passes,{mode="images",now=Date.now(),maxJobs=6,
  existingJobs=[]}={}){
  if(!Object.hasOwn(AUTO_PRESETS,mode))throw Error("Unknown automatic reception category");
  if(!Number.isFinite(now)||!Number.isInteger(maxJobs)||maxJobs<1||maxJobs>12)
    throw Error("Invalid automatic scheduling limits");
  if(!Array.isArray(passes)||!Array.isArray(existingJobs))throw Error("Invalid pass/job data");
  const chosen=AUTO_PRESETS[mode],scheduled=[],skipped=[];
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
    const eligible=chosen.filter(key=>AUTO_TARGETS[key].norad===Number(pass.id));
    const matched=eligible.sort((a,b)=>counts[a]-counts[b])[0];
    if(!matched)continue;
    const start=Math.max(pass.aos-10000,now+30000);
    const until=Number(pass.los);
    if(start+45000>until){skipped.push({name:pass.name,reason:"Pass too short or begins too soon"});continue;}
    if(blocked.some(([a,b])=>start<b+20000&&until>a-20000)){
      skipped.push({name:pass.name,reason:"Single receiver conflict with an armed pass"});continue;
    }
    const target=AUTO_TARGETS[matched];
    scheduled.push({pass,missionId:matched,when:start,until,
      frequency:target.frequencyHz,sampleRate:1024000,durationSeconds:60,
      saveRaw:true,description:target.kind});
    blocked.push([start,until]);
    counts[matched]++;
  }
  return {scheduled,skipped,requestedTargets:[...chosen],
    note:"TLE geometry only. Active transmission is unverified. Browser WebUSB capture is limited to 60 seconds and may not contain a complete LRPT image; the tab must remain open and visible."};
}
