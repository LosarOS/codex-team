/* Same-origin transport shared by legacy screens and workspace tools. */
"use strict";
((root) => {
  class ApiError extends Error {
    constructor(message, {status=0,technical=null,kind="server"}={}) {
      super(message); this.name="ApiError"; this.status=status;
      this.technical=technical; this.kind=kind;
    }
  }
  async function request(path,method="GET",body,options={}) {
    if(typeof path!=="string"||!path.startsWith("/")||path.startsWith("//")||/[\\\x00-\x20]/.test(path))throw new ApiError("Разрешены только запросы к локальному приложению.",{kind:"validation"});
    const controller=new AbortController();let timedOut=false;
    const duration=options.timeoutMs??(/^\/api\/suite\/specifications\/[^/]+\/ai$/.test(path)?135000:/\/qa\/setup$/.test(path)?40000:method==="GET"?12000:35000);
    const timer=setTimeout(()=>{timedOut=true;controller.abort();},duration);
    const cancel=()=>controller.abort();
    if(options.signal?.aborted)cancel();else options.signal?.addEventListener("abort",cancel,{once:true});
    try {
      const init={method,signal:controller.signal,credentials:"same-origin",cache:"no-store",headers:{Accept:"application/json"}};
      if(body!==undefined){init.headers["Content-Type"]="application/json";try{init.body=JSON.stringify(body);}catch(error){throw new ApiError("Не удалось подготовить данные запроса.",{kind:"validation"});}}
      const response=await fetch(path,init),json=(response.headers.get("content-type")||"").includes("json");
      let data;
      try{data=json?await response.json():{detail:(await response.text()).slice(0,4000)};}
      catch(error){if(error.name==="AbortError")throw error;throw new ApiError("Сервер вернул некорректный ответ. Обновите данные и повторите запрос.",{status:response.status,kind:"protocol"});}
      if(response.ok&&!json)throw new ApiError("Сервер вернул ответ в неподдерживаемом формате.",{status:response.status,kind:"protocol"});
      if(!response.ok){const fallback=`Ошибка сервера (${response.status})`;throw new ApiError(options.formatError?.(data,fallback)||fallback,{status:response.status,technical:data?.detail||data?.error||null});}
      return data;
    }catch(error){
      if(error.name==="AbortError")throw new ApiError(timedOut?"Сервер не ответил вовремя. Проверьте локальное приложение и повторите попытку.":"Запрос отменён.",{kind:timedOut?"timeout":"cancelled"});
      if(error instanceof TypeError)throw new ApiError("Нет связи с локальным сервером. Убедитесь, что приложение запущено.",{kind:"offline"});
      throw error;
    }finally{clearTimeout(timer);options.signal?.removeEventListener("abort",cancel);}
  }
  root.CodexApi={request,ApiError};
})(typeof window!=="undefined"?window:globalThis);
