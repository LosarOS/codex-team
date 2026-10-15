/* Same-origin transport shared by legacy screens and workspace tools. */
"use strict";
((root) => {
  class ApiError extends Error {
    constructor(message, {status=0,technical=null,kind="server"}={}) {
      super(message); this.name="ApiError"; this.status=status;
      this.technical=technical; this.kind=kind;
    }
  }
  const fieldNames={workspace:"Проект",path:"Путь",task:"Задача",idea:"Описание задачи",name:"Идентификатор",role:"Название роли",instructions:"Инструкции",permission:"Разрешения",model:"Модель",reasoning_effort:"Глубина анализа",description:"Описание",enabled_modes:"Режимы",sections:"Разделы задания",expected_version:"Версия записи",image:"Образ Docker",commands:"Команды проверки",confirmed:"Подтверждение",key:"Ключ API",provider:"Способ подключения",max_agent_calls:"Лимит вызовов агентов",max_total_tokens:"Лимит токенов",timeout_seconds:"Время ожидания",preview_token:"Подтверждение предпросмотра",confirmation_token:"Подтверждение запуска",title:"Название",content:"Содержание",category:"Категория",sources:"Источники",keep_latest:"Число сохраняемых точек",max_age_days:"Срок хранения",enabled:"Включено"};
  function validationMessage(error) {
    const context=error.ctx||{},type=error.type||"";
    if(type==="missing")return "Заполните обязательное поле.";
    if(type==="string_too_short")return `Введите не менее ${context.min_length??1} символов.`;
    if(type==="string_too_long")return `Сократите текст до ${context.max_length??"допустимого числа"} символов.`;
    if(type==="greater_than_equal")return `Укажите число не меньше ${context.ge}.`;
    if(type==="less_than_equal")return `Укажите число не больше ${context.le}.`;
    if(type==="greater_than")return `Укажите число больше ${context.gt}.`;
    if(type==="less_than")return `Укажите число меньше ${context.lt}.`;
    if(type==="too_short")return `Добавьте не менее ${context.min_length??1} элементов.`;
    if(type==="too_long")return `Оставьте не более ${context.max_length??"допустимого числа"} элементов.`;
    if(type.startsWith("int_")||type.startsWith("float_")||type==="finite_number")return "Укажите допустимое число.";
    if(type.startsWith("bool_"))return "Выберите «Да» или «Нет».";
    if(type==="extra_forbidden")return "Этот параметр не поддерживается. Обновите страницу и повторите действие.";
    if(type==="string_type")return "Введите текст.";
    if(type==="string_pattern_mismatch")return "Проверьте формат значения.";
    if(type==="literal_error"||type==="enum")return "Выберите значение из доступного списка.";
    if(type==="json_invalid")return "Не удалось прочитать данные. Обновите страницу и повторите действие.";
    const message=typeof error.msg==="string"?error.msg.replace(/^Value error,\s*/,""):"";
    return /[А-Яа-яЁё]/.test(message)?message:"Проверьте значение поля.";
  }
  function formatError(body,fallback="Не удалось завершить действие. Проверьте параметры и повторите попытку.") {
    const detail=body?.detail;
    if(Array.isArray(detail))return detail.slice(0,12).map(error=>{
      const path=(error.loc||[]).filter(key=>!["body","query","path"].includes(key));
      const label=path.map(key=>typeof key==="number"?`элемент ${key+1}`:fieldNames[key]||"Параметр").join(" · ")||"Данные запроса";
      return `${label}: ${validationMessage(error)}`;
    }).join("\n");
    const raw=typeof detail==="string"?detail:detail?.message||body?.message||body?.error?.message||body?.error;
    if(typeof raw==="string"){
      if(/dirty|uncommitted|clean (?:tree|repository)|unclean/i.test(raw))return "В проекте есть несохранённые Git-изменения. Для изолированной рабочей копии нужен чистый репозиторий. Проверьте состояние в разделе «Проекты».";
      if(/another run is active/i.test(raw))return "Сначала завершите, остановите или приостановите текущий запуск.";
      if(/agent.*(?:absent|disabled)|core roles|required.*roles/i.test(raw))return "Проверьте состав набора: нужные роли должны быть включены для выбранного режима.";
      if(/API key|credential|separate billing|billing.*acknowledge/i.test(raw))return "Проверьте настройки подключения, сохранённый ключ API и подтверждение отдельной оплаты.";
      if(/no longer waiting|no longer pending/i.test(raw))return "Запрос уже завершён или больше не ожидает решения. Обновите Центр действий.";
      if(/[А-Яа-яЁё]/.test(raw)&&!/(?:Traceback|\{\s*")/.test(raw))return raw;
    }
    return detail?.category==="AUTH_REQUIRED"?"Для этого действия требуется официальный вход Codex.":fallback;
  }
  function httpMessage(status) {
    return {400:"Не удалось выполнить действие. Проверьте введённые данные.",401:"Для этого действия нужен вход. Проверьте подключение в настройках.",403:"Доступ к действию запрещён. Проверьте разрешения и откройте приложение заново.",404:"Запись или действие больше недоступны. Обновите данные.",409:"Данные изменились. Обновите их перед повторным действием.",422:"Проверьте заполнение полей.",429:"Слишком много запросов. Подождите и повторите действие.",503:"Сервис временно недоступен. Проверьте подключение и повторите попытку."}[status]||(status>=500?"Не удалось выполнить действие из-за ошибки сервера. Повторите попытку; если ошибка сохраняется, сохраните диагностику.":"Не удалось выполнить действие. Обновите данные и повторите попытку.");
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
      if(!response.ok){const fallback=httpMessage(response.status);const detail=data?.detail||data?.error||null;const technical=Array.isArray(detail)?detail.map(({loc,type,msg})=>({loc,type,msg})):detail;throw new ApiError((options.formatError||formatError)(data,fallback)||fallback,{status:response.status,technical});}
      return data;
    }catch(error){
      if(error.name==="AbortError")throw new ApiError(timedOut?"Сервер не ответил вовремя. Проверьте локальное приложение и повторите попытку.":"Запрос отменён.",{kind:timedOut?"timeout":"cancelled"});
      if(error instanceof TypeError)throw new ApiError("Нет связи с локальным сервером. Убедитесь, что приложение запущено.",{kind:"offline"});
      throw error;
    }finally{clearTimeout(timer);options.signal?.removeEventListener("abort",cancel);}
  }
  root.CodexApi={request,ApiError,formatError};
})(typeof window!=="undefined"?window:globalThis);
