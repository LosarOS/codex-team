/* Serialized, visibility-aware polling. Never retries a mutation. */
"use strict";
((root) => {
  function create({run, visible=()=>true, interval=2000, maximum=30000,
                   schedule=setTimeout, cancel=clearTimeout, onChange=()=>{}}) {
    let timer=null, stopped=true, running=false, failures=0, wakePending=false, generation=0;
    const delay=()=>Math.min(maximum,interval*Math.pow(2,Math.min(failures,8)));
    function clear(){if(timer!==null){cancel(timer);timer=null;}}
    function queue(ms){clear();if(!stopped&&visible())timer=schedule(tick,ms);}
    async function tick(){
      timer=null;if(stopped||!visible())return;
      if(running){wakePending=true;return;}
      running=true;const epoch=generation;
      try{const result=await run();if(epoch===generation)failures=result===false?failures+1:0;}
      catch(_){if(epoch===generation)failures++;}
      finally{
        running=false;
        if(epoch===generation){onChange({failures,delay:delay()});const immediate=wakePending;wakePending=false;queue(immediate?0:delay());}
        else if(wakePending&&!stopped){wakePending=false;queue(0);}
      }
    }
    return {
      start(){if(!stopped)return;stopped=false;generation++;queue(interval);},
      stop(){stopped=true;generation++;wakePending=false;clear();},
      wake(){if(stopped)return;failures=0;if(running)wakePending=true;else queue(0);},
      visibilityChanged(){if(!visible())clear();else this.wake();},
      snapshot:()=>({running,failures,delay:delay(),scheduled:timer!==null})
    };
  }
  root.CodexRefreshLoop={create};
})(typeof window!=="undefined"?window:globalThis);
