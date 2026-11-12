/* EXIT-01: per-tab scoped shutdown. Never kill external SDR/host services.
 * Stop RF: own RF only. Hard Stop: all owned workers/devices, leave GUI alive.
 * Quit: additionally dispose UI handlers/buffers. Browser close is best-effort.
 */
export function createExitLifecycle(onState = () => {}) {
  let state="RUNNING",rfStopped=false,hardPromise=null,quitPromise=null;
  const handlers=new Map(),invoked=new Map();
  function register(name,kind,cleanup){
    if(state!=="RUNNING"||handlers.has(name)||!["rf","device","ui","ui-controls"].includes(kind)
        ||typeof cleanup!=="function")throw Error("Invalid or late lifecycle registration");
    handlers.set(name,{kind,cleanup});
  }
  function once(name){
    if(invoked.has(name))return invoked.get(name);
    const {cleanup}=handlers.get(name);
    const result=Promise.resolve().then(cleanup).then(
      ()=>({name,released:true}),
      error=>({name,released:false,error:String(error?.message||error).slice(0,240)})
    );
    invoked.set(name,result);
    return result;
  }
  function stopRf(){
    if(state!=="RUNNING"||rfStopped)return Promise.resolve({state,rfStopped,results:[]});
    rfStopped=true;onState("RF_STOPPING");
    return Promise.all([...handlers].filter(([,r])=>r.kind==="rf")
      .map(([name])=>once(name))).then(results=>{
       if(state==="RUNNING")onState("RF_STOPPED");
       return {state,rfStopped,results};
      });
  }
  function hardStop(){
    if(quitPromise)return quitPromise;
    if(hardPromise)return hardPromise;
    state="STOPPING";rfStopped=true;onState(state);
    hardPromise=Promise.all([...handlers].filter(([,r])=>r.kind!=="ui-controls")
       .map(([name])=>once(name))).then(results=>{
         if(!quitPromise){state="HARD_STOPPED";onState(state)}
         return {state:"HARD_STOPPED",results,incomplete:results.filter(r=>!r.released)};
       });
    return hardPromise;
  }
  function quit(){
    if(quitPromise)return quitPromise;
    state="STOPPING";rfStopped=true;onState(state);
    quitPromise=Promise.all([...handlers.keys()].map(name=>once(name))).then(results=>{
      state="QUIT";onState(state);
      return {state,results,incomplete:results.filter(r=>!r.released)};
    });
    return quitPromise;
  }
  return {
    register,stopRf,hardStop,quit,
    get state(){return state},
    get rfStopped(){return rfStopped},
    canStart:(kind="ui")=>state==="RUNNING"&&!(kind==="rf"&&rfStopped),
    isQuit:()=>state==="STOPPING"||state==="QUIT"||state==="HARD_STOPPED"
  };
}
