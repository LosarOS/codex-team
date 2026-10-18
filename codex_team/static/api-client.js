/* Same-origin transport shared by legacy screens and workspace tools. */
"use strict";
((root) => {
  root.CodexI18n?.register({
  "Проект": "Project",
  "Путь": "Path",
  "Задача": "Task",
  "Описание задачи": "Task description",
  "Идентификатор": "Identifier",
  "Название роли": "Role name",
  "Инструкции": "Instructions",
  "Разрешения": "Permissions",
  "Модель": "Model",
  "Глубина анализа": "Reasoning effort",
  "Описание": "Description",
  "Режимы": "Modes",
  "Разделы задания": "Specification sections",
  "Версия записи": "Record version",
  "Образ Docker": "Docker image",
  "Команды проверки": "Check commands",
  "Подтверждение": "Confirmation",
  "Ключ API": "API key",
  "Способ подключения": "Connection method",
  "Лимит вызовов агентов": "Agent call limit",
  "Лимит токенов": "Token limit",
  "Время ожидания": "Timeout",
  "Подтверждение предпросмотра": "Preview confirmation",
  "Подтверждение запуска": "Run confirmation",
  "Название": "Title",
  "Содержание": "Content",
  "Категория": "Category",
  "Источники": "Sources",
  "Число сохраняемых точек": "Checkpoints to keep",
  "Срок хранения": "Retention period",
  "Включено": "Enabled",
  "Запуск": "Run",
  "Параметры запуска": "Run options",
  "Число повторных циклов": "Iteration limit",
  "Лимит времени запуска": "Run duration limit",
  "Специалисты": "Specialists",
  "Набор агентов": "Agent pack",
  "Состав команды": "Team members",
  "Режим по умолчанию": "Default mode",
  "Обязательные проверки": "Required checks",
  "Идентификатор операции": "Operation identifier",
  "Выполнение команд": "Command execution",
  "Доступ к сети": "Network access",
  "Заполните обязательное поле.": "Complete this required field.",
  "Укажите допустимое число.": "Enter a valid number.",
  "Выберите «Да» или «Нет».": "Select Yes or No.",
  "Этот параметр не поддерживается. Обновите страницу и повторите действие.": "This option is not supported. Refresh the page and try again.",
  "Введите текст.": "Enter text.",
  "Проверьте формат значения.": "Check the value format.",
  "Выберите значение из доступного списка.": "Select a value from the list.",
  "Не удалось прочитать данные. Обновите страницу и повторите действие.": "Could not read the data. Refresh the page and try again.",
  "Проверьте значение поля.": "Check the field value.",
  "Не удалось завершить действие. Проверьте параметры и повторите попытку.": "Could not complete the action. Check the options and try again.",
  "Данные запроса": "Request data",
  "Параметр": "Parameter",
  "В проекте есть несохранённые Git-изменения. Для изолированной рабочей копии нужен чистый репозиторий. Проверьте состояние в разделе «Проекты».": "The project has uncommitted Git changes. An isolated worktree requires a clean repository. Check its status in Projects.",
  "Сначала завершите, остановите или приостановите текущий запуск.": "Complete, stop or pause the current run first.",
  "Проверьте состав набора: нужные роли должны быть включены для выбранного режима.": "Check the agent pack: all roles required by the selected mode must be enabled.",
  "Проверьте настройки подключения, сохранённый ключ API и подтверждение отдельной оплаты.": "Check the connection settings, saved API key and separate billing confirmation.",
  "Запрос уже завершён или больше не ожидает решения. Обновите Центр действий.": "This request is completed or no longer awaiting a decision. Refresh the Action Center.",
  "Для этого действия требуется официальный вход Codex.": "Sign in through the official Codex login to continue.",
  "Не удалось выполнить действие. Проверьте введённые данные.": "Could not complete the action. Check the entered data.",
  "Для этого действия нужен вход. Проверьте подключение в настройках.": "Sign in to continue. Check the connection in Settings.",
  "Доступ к действию запрещён. Проверьте разрешения и откройте приложение заново.": "Access denied. Check the permissions and reopen the application.",
  "Запись или действие больше недоступны. Обновите данные.": "This record or action is no longer available. Refresh the data.",
  "Данные изменились. Обновите их перед повторным действием.": "The data has changed. Refresh it before trying again.",
  "Проверьте заполнение полей.": "Check the form fields.",
  "Слишком много запросов. Подождите и повторите действие.": "Too many requests. Wait and try again.",
  "Сервис временно недоступен. Проверьте подключение и повторите попытку.": "The service is temporarily unavailable. Check the connection and try again.",
  "Не удалось выполнить действие из-за ошибки сервера. Повторите попытку; если ошибка сохраняется, сохраните диагностику.": "A server error prevented this action. Try again; if the problem persists, save the diagnostics.",
  "Не удалось выполнить действие. Обновите данные и повторите попытку.": "Could not complete the action. Refresh the data and try again.",
  "Разрешены только запросы к локальному приложению.": "Only requests to the local application are allowed.",
  "Не удалось подготовить данные запроса.": "Could not prepare the request data.",
  "Сервер вернул некорректный ответ. Обновите данные и повторите запрос.": "The server returned an invalid response. Refresh the data and try again.",
  "Сервер вернул ответ в неподдерживаемом формате.": "The server returned an unsupported response format.",
  "Сервер не ответил вовремя. Проверьте локальное приложение и повторите попытку.": "The server did not respond in time. Check the local application and try again.",
  "Запрос отменён.": "Request cancelled.",
  "Нет связи с локальным сервером. Убедитесь, что приложение запущено.": "Cannot reach the local server. Make sure the application is running.",
  "Введите не менее {value} символов.": "Enter at least {value} characters.",
  "Сократите текст до {value} символов.": "Shorten the text to {value} characters.",
  "Укажите число не меньше {value}.": "Enter a number greater than or equal to {value}.",
  "Укажите число не больше {value}.": "Enter a number less than or equal to {value}.",
  "Укажите число больше {value}.": "Enter a number greater than {value}.",
  "Укажите число меньше {value}.": "Enter a number less than {value}.",
  "Добавьте не менее {value} элементов.": "Add at least {value} items.",
  "Оставьте не более {value} элементов.": "Keep no more than {value} items.",
  "допустимого числа": "the allowed number of",
  "элемент {value}": "item {value}"
});
  const t=(source,params)=>root.CodexI18n?.t(source,params)||source.replace(/\{(\w+)\}/g,(_,key)=>params?.[key]??"{"+key+"}");
  class ApiError extends Error {
    constructor(message, {status=0,technical=null,kind="server"}={}) {
      super(message); this.name="ApiError"; this.status=status;
      this.technical=technical; this.kind=kind;
    }
  }
  const fieldNames={workspace:t("Проект"),path:t("Путь"),task:t("Задача"),idea:t("Описание задачи"),name:t("Идентификатор"),role:t("Название роли"),instructions:t("Инструкции"),permission:t("Разрешения"),model:t("Модель"),reasoning_effort:t("Глубина анализа"),description:t("Описание"),enabled_modes:t("Режимы"),sections:t("Разделы задания"),expected_version:t("Версия записи"),image:t("Образ Docker"),commands:t("Команды проверки"),confirmed:t("Подтверждение"),key:t("Ключ API"),provider:t("Способ подключения"),max_agent_calls:t("Лимит вызовов агентов"),max_total_tokens:t("Лимит токенов"),timeout_seconds:t("Время ожидания"),preview_token:t("Подтверждение предпросмотра"),confirmation_token:t("Подтверждение запуска"),title:t("Название"),content:t("Содержание"),category:t("Категория"),sources:t("Источники"),keep_latest:t("Число сохраняемых точек"),max_age_days:t("Срок хранения"),enabled:t("Включено"),project_id:t("Проект"),run_id:t("Запуск"),run_options:t("Параметры запуска"),max_iterations:t("Число повторных циклов"),max_run_duration:t("Лимит времени запуска"),specialists:t("Специалисты"),pack:t("Набор агентов"),agents:t("Состав команды"),default_mode:t("Режим по умолчанию"),required_categories:t("Обязательные проверки"),request_id:t("Идентификатор операции"),label:t("Название"),can_execute:t("Выполнение команд"),can_network:t("Доступ к сети")};
  function validationMessage(error) {
    const context=error.ctx||{},type=error.type||"";
    if(type==="missing")return t("Заполните обязательное поле.");
    if(type==="string_too_short")return t("Введите не менее {value} символов.",{value:context.min_length??1});
    if(type==="string_too_long")return t("Сократите текст до {value} символов.",{value:context.max_length??t("допустимого числа")});
    if(type==="greater_than_equal")return t("Укажите число не меньше {value}.",{value:context.ge});
    if(type==="less_than_equal")return t("Укажите число не больше {value}.",{value:context.le});
    if(type==="greater_than")return t("Укажите число больше {value}.",{value:context.gt});
    if(type==="less_than")return t("Укажите число меньше {value}.",{value:context.lt});
    if(type==="too_short")return t("Добавьте не менее {value} элементов.",{value:context.min_length??1});
    if(type==="too_long")return t("Оставьте не более {value} элементов.",{value:context.max_length??t("допустимого числа")});
    if(type.startsWith("int_")||type.startsWith("float_")||type==="finite_number")return t("Укажите допустимое число.");
    if(type.startsWith("bool_"))return t("Выберите «Да» или «Нет».");
    if(type==="extra_forbidden")return t("Этот параметр не поддерживается. Обновите страницу и повторите действие.");
    if(type==="string_type")return t("Введите текст.");
    if(type==="string_pattern_mismatch")return t("Проверьте формат значения.");
    if(type==="literal_error"||type==="enum")return t("Выберите значение из доступного списка.");
    if(type==="json_invalid")return t("Не удалось прочитать данные. Обновите страницу и повторите действие.");
    const message=typeof error.msg==="string"?error.msg.replace(/^Value error,\s*/,""):"";
    return /[А-Яа-яЁё]/.test(message)&&root.CodexI18n?.language!=="en"?message:t("Проверьте значение поля.");
  }
  function formatError(body,fallback=t("Не удалось завершить действие. Проверьте параметры и повторите попытку.")) {
    const detail=body?.validation_errors||body?.detail;
    if(Array.isArray(detail))return detail.slice(0,12).map(error=>{
      const path=(error.loc||[]).filter(key=>!["body","query","path"].includes(key));
      const label=path.map(key=>typeof key==="number"?t("элемент {value}",{value:key+1}):fieldNames[key]||t("Параметр")).join(" · ")||t("Данные запроса");
      return `${label}: ${validationMessage(error)}`;
    }).join("\n");
    const raw=typeof detail==="string"?detail:detail?.message||body?.message||body?.error?.message||body?.error;
    if(typeof raw==="string"){
      if(/dirty|uncommitted|clean (?:tree|repository)|unclean/i.test(raw))return t("В проекте есть несохранённые Git-изменения. Для изолированной рабочей копии нужен чистый репозиторий. Проверьте состояние в разделе «Проекты».");
      if(/another run is active/i.test(raw))return t("Сначала завершите, остановите или приостановите текущий запуск.");
      if(/agent.*(?:absent|disabled)|core roles|required.*roles/i.test(raw))return t("Проверьте состав набора: нужные роли должны быть включены для выбранного режима.");
      if(/API key|credential|separate billing|billing.*acknowledge/i.test(raw))return t("Проверьте настройки подключения, сохранённый ключ API и подтверждение отдельной оплаты.");
      if(/no longer waiting|no longer pending/i.test(raw))return t("Запрос уже завершён или больше не ожидает решения. Обновите Центр действий.");
      if(/[А-Яа-яЁё]/.test(raw)&&!/(?:Traceback|\{\s*")/.test(raw))return root.CodexI18n?.language==="en" ? (t(raw)!==raw?t(raw):fallback) : raw;
    }
    return detail?.category==="AUTH_REQUIRED"?t("Для этого действия требуется официальный вход Codex."):fallback;
  }
  function httpMessage(status) {
    return {400:t("Не удалось выполнить действие. Проверьте введённые данные."),401:t("Для этого действия нужен вход. Проверьте подключение в настройках."),403:t("Доступ к действию запрещён. Проверьте разрешения и откройте приложение заново."),404:t("Запись или действие больше недоступны. Обновите данные."),409:t("Данные изменились. Обновите их перед повторным действием."),422:t("Проверьте заполнение полей."),429:t("Слишком много запросов. Подождите и повторите действие."),503:t("Сервис временно недоступен. Проверьте подключение и повторите попытку.")}[status]||(status>=500?t("Не удалось выполнить действие из-за ошибки сервера. Повторите попытку; если ошибка сохраняется, сохраните диагностику."):t("Не удалось выполнить действие. Обновите данные и повторите попытку."));
  }
  async function request(path,method="GET",body,options={}) {
    if(typeof path!=="string"||!path.startsWith("/")||path.startsWith("//")||/[\\\x00-\x20]/.test(path))throw new ApiError(t("Разрешены только запросы к локальному приложению."),{kind:"validation"});
    const controller=new AbortController();let timedOut=false;
    const duration=options.timeoutMs??(/^\/api\/suite\/specifications\/[^/]+\/ai$/.test(path)?135000:/\/qa\/setup$/.test(path)?40000:method==="GET"?12000:35000);
    const timer=setTimeout(()=>{timedOut=true;controller.abort();},duration);
    const cancel=()=>controller.abort();
    if(options.signal?.aborted)cancel();else options.signal?.addEventListener("abort",cancel,{once:true});
    try {
      const init={method,signal:controller.signal,credentials:"same-origin",cache:"no-store",headers:{Accept:"application/json"}};
      if(body!==undefined){init.headers["Content-Type"]="application/json";try{init.body=JSON.stringify(body);}catch(error){throw new ApiError(t("Не удалось подготовить данные запроса."),{kind:"validation"});}}
      const response=await fetch(path,init),json=(response.headers.get("content-type")||"").includes("json");
      let data;
      try{data=json?await response.json():{detail:(await response.text()).slice(0,4000)};}
      catch(error){if(error.name==="AbortError")throw error;throw new ApiError(t("Сервер вернул некорректный ответ. Обновите данные и повторите запрос."),{status:response.status,kind:"protocol"});}
      if(response.ok&&!json)throw new ApiError(t("Сервер вернул ответ в неподдерживаемом формате."),{status:response.status,kind:"protocol"});
      if(!response.ok){const fallback=httpMessage(response.status);const detail=data?.validation_errors||data?.detail||data?.error||null;const technical=Array.isArray(detail)?detail.map(({loc,type,msg})=>({loc,type,msg})):detail;throw new ApiError((options.formatError||formatError)(data,fallback)||fallback,{status:response.status,technical});}
      return data;
    }catch(error){
      if(error.name==="AbortError")throw new ApiError(timedOut?t("Сервер не ответил вовремя. Проверьте локальное приложение и повторите попытку."):t("Запрос отменён."),{kind:timedOut?"timeout":"cancelled"});
      if(error instanceof TypeError)throw new ApiError(t("Нет связи с локальным сервером. Убедитесь, что приложение запущено."),{kind:"offline"});
      throw error;
    }finally{clearTimeout(timer);options.signal?.removeEventListener("abort",cancel);}
  }
  root.CodexApi={request,ApiError,formatError};
})(typeof window!=="undefined"?window:globalThis);
