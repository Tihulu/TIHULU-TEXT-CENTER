/* Satellite Center pass/satellite list sorting: deterministic, geometry-only.
 * Sorting must never modify raw pass times, capture jobs, or RF measurements.
 */
export const PASS_SORTS = Object.freeze([
  "soonest","latest","elevation-high","elevation-low",
  "duration-long","duration-short","name"
]);
export const SATELLITE_SORTS = Object.freeze([
  "elevation-high","elevation-low","next-soonest","next-latest",
  "range-near","range-far","name"
]);
function compareNum(a,b){return a-b;}
function time(p){return Number.isFinite(Number(p.aos))?Number(p.aos):Infinity;}
function maxEl(p){return Number.isFinite(Number(p.maximum))?Number(p.maximum):-Infinity;}
function duration(p){
  const start=time(p),end=Number(p.los);
  return Number.isFinite(start)&&Number.isFinite(end)&&end>=start?end-start:0;
}
function compareName(a,b){return String(a.name||"").localeCompare(String(b.name||""),"en",{numeric:true,sensitivity:"base"});}
function passTie(a,b){return compareNum(time(a),time(b))||compareName(a,b)||compareNum(Number(a.id)||0,Number(b.id)||0);}
export function sortPassList(records,sort="soonest",family="all"){
  if(!Array.isArray(records))return [];
  return records.filter(p=>p&&Number.isFinite(time(p))&&(family==="all"||p.family===family))
    .sort((a,b)=>{
      let cmp=0;
      switch(sort){
        case "latest":cmp=compareNum(time(b),time(a));break;
        case "elevation-high":cmp=compareNum(maxEl(b),maxEl(a));break;
        case "elevation-low":cmp=compareNum(maxEl(a),maxEl(b));break;
        case "duration-long":cmp=compareNum(duration(b),duration(a));break;
        case "duration-short":cmp=compareNum(duration(a),duration(b));break;
        case "name":cmp=compareName(a,b);break;
        default:cmp=compareNum(time(a),time(b));
      }
      return cmp||passTie(a,b);
    });
}
function upcomingFor(s,records,now){
  const id=String(s.id);
  let earliest=Infinity;
  for(const p of records){
    if(String(p.id)!==id)continue;
    const aos=time(p),los=Number(p.los);
    if(Number.isFinite(aos)&&Number.isFinite(los)&&los>now&&aos<earliest)
      earliest=aos;
  }
  return earliest;
}
function finiteOr(x,value){
  return Number.isFinite(Number(x))?Number(x):value;
}
export function sortSatelliteList(records,sort="elevation-high",passes=[],now=Date.now()){
  if(!Array.isArray(records))return [];
  const passRows=Array.isArray(passes)?passes:[];
  const next=new Map(records.map(s=>[String(s.id),upcomingFor(s,passRows,now)]));
  return [...records].sort((a,b)=>{
    let cmp=0;
    switch(sort){
      case "elevation-low":cmp=compareNum(finiteOr(a.el,0),finiteOr(b.el,0));break;
      case "next-soonest":{
        const x=next.get(String(a.id))??Infinity,y=next.get(String(b.id))??Infinity;
        cmp=compareNum(x,y);break;
      }
      case "next-latest":{
        const x=next.get(String(a.id))??Infinity,y=next.get(String(b.id))??Infinity;
        // unknown next pass always last, even for latest-date sort
        cmp=(Number.isFinite(y)?1:0)-(Number.isFinite(x)?1:0);
        if(!cmp&&Number.isFinite(x)&&Number.isFinite(y))cmp=compareNum(y,x);
        break;
      }
      case "range-near":cmp=compareNum(finiteOr(a.rangeKm,Infinity),finiteOr(b.rangeKm,Infinity));break;
      case "range-far":cmp=compareNum(finiteOr(b.rangeKm,-Infinity),finiteOr(a.rangeKm,-Infinity));break;
      case "name":cmp=compareName(a,b);break;
      default:cmp=compareNum(finiteOr(b.el,0),finiteOr(a.el,0));
    }
    return cmp||compareName(a,b)||compareNum(Number(a.id)||0,Number(b.id)||0);
  });
}
export function nextPassForSatellite(item,passes=[],now=Date.now()){
  const time=upcomingFor(item,Array.isArray(passes)?passes:[],now);
  return Number.isFinite(time)?time:null;
}
