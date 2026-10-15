"use strict";

(() => {
  const $ = (id) => document.getElementById(id);
  const qa = (selector) => Array.from(document.querySelectorAll(selector));
  const state = {
    status: null, agents: [], packs: [], runs: [], selectedRun: null,
    selectedRole: null, events: [], eventCursor: 0, detailTab: "overview",
    page: "workbench", refreshing: false, polling: false, selecting: false, editingAgent: null, lastStatus: 0,
    lastRegistry: 0, online: false, selectionVersion: 0, loginPending: false,
    runSignature: "", runsSignature: "", agentsSignature: "", usageSignature: "", accountUsage: null, lastAccountUsage: 0, accountUsageLoading: false, modelsLoaded: false, modelsLoading: false,
    projects: [], projectsError: null, actions: [], actionsError: null, actionsLoading: false, actionsSignature: "", providers: null, providerTouched: false,
    appearance: {theme:"system",accent_color:null}, historyRows: [], historyPage: 0, historyTotal: 0, historyVersion: 0, historyTimer: null, runTotal: 0, allUsage: null,
    editingPack: null, editingProject: null, diffLimit: 1000, diffLines: [], diffRun: null, diffTotal: 0, diffHasMore: false, diffLoading: false,
    lastEventsFetch: 0, eventsHasMore: false, eventsLoaded: false, eventsState: null, lastRunList: 0, lastRunDetail: 0, availableModels: [], diffError: null,
    controlPending: false, creatingRun: false, runRevision: 0, pendingActions: new Set(),
    stageEvents: [], selectedAttempt: null, eventFilter: "all", eventsRequest: null,
    desktopReady: false, health: null, healthError: null, healthCheckedAt: null,
  };
  const roles = {
    coordinator: ["Координатор", "План и организация работы"],
    analyst: ["Аналитик", "Архитектура и критерии приёмки"],
    developer: ["Разработчик", "Изменения кода и тестов"],
    qa: ["Тестировщик", "Независимая проверка и регрессии"],
    reviewer: ["Проверка кода", "Финальная проверка решения"],
    architect: ["Архитектор", "Проектирование решения"],
    "final-audit": ["Финальный аудит", "Проверка всех результатов"],
    security:["Безопасность","Проверка угроз и защиты данных"],
    performance:["Производительность","Проверка скорости работы и использования ресурсов"],
    "game-logic":["Игровая логика","Проверка правил игры и сохранений"],
    narrative:["Сценарий игры","Проверка сюжета и согласованности состояний"],
    "business-analyst":["Бизнес-аналитик","Анализ требований и рабочих процессов"],
    "system-analyst":["Системный аналитик","Анализ системных требований и взаимодействий"],
    integration:["Интеграции","Проверка взаимодействия с внешними системами"],
    frontend:["Интерфейс","Проверка интерфейса и доступности"],
    backend:["Серверная часть","Проверка обработки данных и серверной логики"],
    documentation:["Документация","Проверка руководств и технических описаний"],
    specialists: ["Специалисты", "Предметная экспертиза"],
  };
  const modes = {
    quick: {title: "Быстрый", description: "Короткий цикл: план, реализация и независимая QA-проверка.", pipeline: ["coordinator", "developer", "qa"]},
    standard: {title: "Стандартный", description: "Полный цикл разработки с независимой проверкой кода и тестов.", pipeline: ["coordinator", "analyst", "developer", "qa", "reviewer"]},
    deep: {title: "Глубокий", description: "Расширенный анализ со специалистами и итоговым аудитом.", pipeline: ["coordinator", "analyst", "specialists", "developer", "qa", "reviewer", "final-audit"]},
    audit: {title: "Аудит", description: "Изучение проекта и независимый отчёт. Production-код не изменяется.", pipeline: ["coordinator", "analyst", "reviewer", "qa", "final-audit"]},
    plan: {title: "Планирование", description: "Анализ и план реализации. Production-код не изменяется.", pipeline: ["coordinator", "analyst", "architect"]},
    implement: {title: "Готовый план", description: "Реализация заданного плана с QA и ревью результата.", pipeline: ["coordinator", "developer", "qa", "reviewer"]},
  };
  const stateLabels = {
    WAITING: "Ожидание этапа", QUEUED: "В очереди", RUNNING: "В работе", PAUSING: "Приостановка",
    PAUSED: "Пауза", STOPPING: "Остановка", STOPPED: "Остановлен",
    INTERRUPTED: "Прерван", DONE: "Завершён", COMPLETED: "Завершён",
    FAILED: "Ошибка", USER_DECISION_REQUIRED: "Нужно решение", AUTH_REQUIRED: "Нужен вход", USAGE_LIMIT: "Лимит Codex",
    BLOCKED:"Заблокировано", PARTIAL:"Выполнено частично", "NOT RUN":"Не запускалось", PENDING:"Ожидает решения",
    PLAN: "План", ANALYSIS: "Анализ", IMPLEMENTED: "Реализовано", PASS: "Проверено",
    FAIL: "Проверка не пройдена", APPROVED: "Одобрено", CHANGES_REQUIRED: "Нужны исправления",
  };
  const eventLabels = {
    run_created: "Запуск создан", created: "Запуск создан", state_changed: "Состояние изменено",
    state: "Состояние", stage_started: "Этап начат", agent_started: "Агент запущен",
    agent_completed: "Агент завершил работу", agent_result: "Результат агента",
    turn_started: "Шаг агента начат", turn_completed: "Шаг агента завершён", turn_complete: "Шаг агента завершён",
    turn_failed: "Ошибка шага агента", command: "Команда", command_execution: "Выполнение команды",
    tool: "Действие инструмента", item: "Действие Codex", usage: "Использование",
    completed: "Запуск завершён", failed: "Ошибка выполнения", paused: "Приостановлен",
    resumed: "Продолжен", stopped: "Остановлен", recovered: "Восстановление после перезапуска",
    instruction: "Указание пользователя", steering: "Указание команде", queued_instruction: "Указание в очереди",
    retry: "Повторная проверка", pipeline: "План выполнения", workspace: "Рабочая копия",
    "item/started": "Действие начато", "item/completed": "Действие завершено", "turn/started": "Шаг агента начат", "turn/completed": "Шаг агента завершён",
    "thread/tokenUsage/updated": "Расход токенов обновлён", thread_ready: "Независимая сессия готова", run_state: "Состояние запуска",
    repair_requested: "Возврат на исправление", user_instruction: "Указание пользователя", pause_requested: "Пауза запрошена", stop_requested: "Остановка запрошена", approval_required: "Требуется разрешение",
  };
  const activeStates = new Set(["RUNNING", "QUEUED", "PAUSING", "STOPPING"]);
  const resumeStates = new Set(["PAUSED", "INTERRUPTED", "USER_DECISION_REQUIRED", "AUTH_REQUIRED", "FAILED", "STOPPED", "USAGE_LIMIT"]);
  const terminalStates = new Set(["DONE", "COMPLETED", "STOPPED"]);
  const standardRoles = new Set(["coordinator", "analyst", "developer", "qa", "reviewer", "architect", "final-audit"]);
  const formatNumber = new Intl.NumberFormat("ru-RU");
  const dateFormat = new Intl.DateTimeFormat("ru-RU", {dateStyle: "short", timeStyle: "short"});
  const timeFormat = new Intl.DateTimeFormat("ru-RU", {hour: "2-digit", minute: "2-digit", second: "2-digit"});

  function node(tag, className, value) {
    const el = document.createElement(tag);
    if (className) el.className = className;
    if (value !== undefined && value !== null) el.textContent = String(value);
    return el;
  }
  function text(value) {
    if (value === null || value === undefined) return "";
    return typeof value === "string" ? value : JSON.stringify(value, null, 2);
  }
  function list(value) {
    if (Array.isArray(value)) return value;
    return value && typeof value === "object" ? Object.values(value) : [];
  }
  function prettyDate(value, onlyTime = false) {
    if (!value) return "—";
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? String(value) : (onlyTime ? timeFormat : dateFormat).format(date);
  }
  function roleName(role) {
    const configured = state.agents.find((agent) => agent.name === role)?.role;
    return (configured && configured !== role ? configured : roles[role]?.[0]) || configured || role || "—";
  }
  function normalizedState(value) { return String(value || "").toUpperCase(); }
  function badge(value) {
    const status = normalizedState(value);
    let cls = "";
    if (["DONE", "COMPLETED", "PASS", "APPROVED", "IMPLEMENTED"].includes(status)) cls = "state-good";
    else if (["RUNNING", "QUEUED", "PLAN", "ANALYSIS"].includes(status)) cls = "state-active";
    else if (["FAILED", "FAIL", "CHANGES_REQUIRED"].includes(status)) cls = "state-error";
    else if (["PAUSED", "PAUSING", "INTERRUPTED", "USER_DECISION_REQUIRED", "AUTH_REQUIRED", "USAGE_LIMIT"].includes(status)) cls = "state-warning";
    return node("span", `state-badge ${cls}`, stateLabels[status] || value || "—");
  }
  function empty(container, title, description) {
    const el = node("div", "empty-state");
    el.append(node("span", "empty-icon", "◈"), node("h3", "", title));
    if (description) el.append(node("p", "", description));
    container.replaceChildren(el);
  }
  function toast(message, error = false) {
    const el = node("div", `toast${error ? " error" : ""}`, message);
    $("toast-region").append(el);
    setTimeout(() => el.remove(), error ? 9000 : 5000);
  }
  function showFormError(id,message) {
    const el=$(id);el.replaceChildren();el.hidden=!message;if(!message)return;
    const error=message instanceof Error?message:null;el.append(node("span","",error?error.message:message));
    if(error?.technical){const d=node("details","raw-details");d.append(node("summary","","Технические подробности"),node("pre","code-block",text(error.technical)));el.append(d);}
  }
  function errorMessage(body,fallback) {
    return window.CodexApi.formatError(body,fallback);
  }

  function api(path, method = "GET", body, options={}) {
    return window.CodexApi.request(path,method,body,{...options,formatError:errorMessage});
  }

  function setPage(page) {
    const [route,feature]=String(page||"workbench").split("/");
    page=route;
    if(page==="suite")state.suiteFeature=["architect","intelligence","git","qa","budget"].includes(feature)?feature:state.suiteFeature||"architect";
    if(page==="dashboard")page="workbench";
    if (!$("page-" + page)) page = "workbench";
    const changed=state.page!==page;state.page = page;if(changed)window.scrollTo?.({top:0,behavior:"auto"});
    qa(".page").forEach((el) => { el.hidden = el.id !== "page-" + page; });
    qa(".nav-item").forEach((el) => {const active=el.dataset.page===page&&(!el.dataset.suiteFeatureLink||el.dataset.suiteFeatureLink===state.suiteFeature);el.classList.toggle("active",active);if(active)el.setAttribute("aria-current","page");else el.removeAttribute("aria-current");});
    $("page-label").textContent={workbench:"Обзор",projects:"Проекты",runs:"Запуски",history:"История",agents:"Агенты",packs:"Наборы",actions:"Центр действий",usage:"Использование",settings:"Настройки",suite:"Рабочее пространство V2"}[page];
    const hash="#"+page+(page==="suite"?"/"+state.suiteFeature:"");
    if(window.location.hash!==hash)history.replaceState(null,"",hash);
    if(page==="usage"){renderGlobalUsage();loadAccountUsage();}
    if(page==="agents"||page==="settings")loadModels();
    if(page==="history")loadHistory();
    if(page==="history")loadProjects();
    if(page==="projects")loadProjects();
    if(page==="packs")renderPacks();
    if(page==="actions")loadActions();
    if(page==="settings")loadProviders();
    if(page==="suite"){const event=new Event("codex-suite-open");event.detail={feature:state.suiteFeature};window.dispatchEvent?.(event);}
    if(page==="runs"){renderRunList();if(state.selectedRun)setDetailTab(state.detailTab);}
  }
  function setDetailTab(tab) {
    state.detailTab=tab;
    qa("[data-detail-tab]").forEach(button=>{const active=button.dataset.detailTab===tab;button.classList.toggle("active",active);button.setAttribute("aria-selected",String(active));button.tabIndex=active?0:-1;$("detail-"+button.dataset.detailTab).hidden=!active;});
    if(!state.selectedRun)return;
    if(tab==="overview"){renderRoles();if(!state.eventsLoaded)fetchEvents(state.selectedRun.id,state.selectionVersion).catch(e=>showEventError(e));}
    if(tab==="diff")loadDiff();
    if(tab==="tests")renderTests();
    if(tab==="artifacts")renderArtifacts();
    if(tab==="usage")renderRunUsage();
    if(tab==="activity"){renderEvents();if(!state.eventsLoaded)fetchEvents(state.selectedRun.id,state.selectionVersion).catch(e=>toast(e.message,true));}
  }
  function renderPreview() {
    const mode = modes[$("run-mode").value] || modes.standard;
    $("mode-description").textContent = mode.description;
    $("pipeline-preview-list").replaceChildren(...composerPipeline().map((role, index) => {
      const li = node("li");
      const description = node("div");
      description.append(node("h3", "", roleName(role)), node("p", "", roles[role]?.[1]||state.agents.find(a=>a.name===role)?.description||"Дополнительная роль только для чтения"));
      li.append(node("span", "pipeline-number", String(index + 1).padStart(2, "0")), description);
      return li;
    }));
    $("specialists-group").hidden = !["deep", "audit"].includes($("run-mode").value) || !state.agents.some((agent) => !standardRoles.has(agent.name) && agent.enabled !== false && agent.permission === "read-only");
  }
  function desktopBridge() {
    // pywebview exposes fixed native operations; project/worktree opens accept registered IDs.
    return state.desktopReady ? window.pywebview?.api : null;
  }
  function renderDesktopIntegration() {
    const bridge = desktopBridge();
    const canChooseProject = typeof bridge?.choose_project === "function";
    const canOpenLogs = typeof bridge?.open_logs === "function";
    $("browse-project-button").hidden = !canChooseProject; $("project-browse-button").hidden = !canChooseProject; $("tray-setting-row").hidden=!bridge; $("export-diagnostics-button").hidden = typeof bridge?.export_diagnostics!=="function";
    $("open-logs-button").hidden = !canOpenLogs;
    $("desktop-settings-panel").hidden = !canOpenLogs && !state.health;
    $("desktop-mode-badge").textContent = state.desktopReady ? "ПРИЛОЖЕНИЕ" : "ЛОКАЛЬНЫЙ СЕРВЕР";
    const checks = $("health-checks");
    checks.hidden = !state.health;
    if (state.health) {
      const health = state.health; if(health.version) $("about-version").textContent=`Версия ${health.version}`;
      const entries = [];
      const healthStatus = health.status || (health.ok === true ? "ok" : null);
      if (healthStatus) entries.push(["Состояние сервера", ["ok", "healthy", "ready"].includes(String(healthStatus).toLowerCase()) ? "Готов" : "Требуется проверка"]);
      if (health.app || health.service || health.name) entries.push(["Приложение", health.app || health.service || health.name]);
      if (health.version) entries.push(["Версия", health.version]);
      if (health.checks && typeof health.checks === "object") entries.push(...Object.entries(health.checks));
      const labels = {database: "База данных", storage: "Хранилище", git: "Git", codex: "Codex", backend: "Серверная часть", data_directory: "Каталог данных"};
      checks.replaceChildren(...entries.map(([key, value]) => {
        const row = node("div", "capability-row");
        const display = typeof value === "boolean" ? value ? "Готов" : "Недоступно" : value?.status ? ({ok:"Готов",ready:"Готов",available:"Доступно",unavailable:"Недоступно",error:"Ошибка",missing:"Не найдено",failed:"Ошибка"}[String(value.status).toLowerCase()]||"Требуется проверка")+(value.detail?` · ${errorMessage({detail:value.detail},"Подробности доступны в диагностике.")}`:"") : text(value);
        row.append(node("span", "", labels[key] || key), node("span", "muted", display));
        return row;
      }));
    }
    const note = $("desktop-health-note");
    note.hidden = !state.healthError && !state.healthCheckedAt;
    note.textContent = state.healthError || (state.healthCheckedAt ? `Последняя проверка сервера: ${prettyDate(state.healthCheckedAt, true)}` : "");
  }
  function onDesktopReady() {
    state.desktopReady = Boolean(window.pywebview?.api);
    renderDesktopIntegration(); renderProjects(); if(state.selectedRun)renderActivePipeline(); loadRecovery();
  }
  async function chooseProject() {
    const bridge = desktopBridge();
    if (typeof bridge?.choose_project !== "function") return;
    const button = $("browse-project-button"); button.disabled = true;
    try {
      const selected = await bridge.choose_project();
      if (selected?.error) throw new Error(text(selected.error));
      const path = typeof selected === "string" ? selected : selected?.path;
      // Cancellation leaves the typed path and current task intact.
      if (typeof path !== "string" || !path.trim()) return;
      $("workspace").value = path;
      $("workspace").dispatchEvent(new Event("input", {bubbles: true}));
      $("workspace").focus();
      try { await addProject(path); } catch(error) { if(error.status!==404)toast(`Папка выбрана. Не удалось добавить в список: ${error.message}`,true); }
      try { localStorage.setItem("codex-team-workspace", path); } catch (_) { /* storage may be disabled */ }
    } catch (error) { toast(`Не удалось выбрать проект: ${error.message || text(error)}`, true); }
    finally { button.disabled = false; }
  }
  async function openLogs() {
    const bridge = desktopBridge();
    if (typeof bridge?.open_logs !== "function") return;
    const button = $("open-logs-button"); button.disabled = true;
    try {
      const result = await bridge.open_logs();
      if (result?.error || result === false || result?.ok === false) throw new Error(text(result?.error) || "Каталог логов недоступен.");
    } catch (error) { toast(`Не удалось открыть логи: ${error.message || text(error)}`, true); }
    finally { button.disabled = false; }
  }
  function updateHealth(result) {
    if (result.status === "fulfilled" && result.value && typeof result.value === "object") {
      state.health = result.value; state.healthError = null; state.healthCheckedAt = new Date().toISOString();
    } else if (result.status === "rejected" && result.reason.status !== 404 && state.health) {
      state.healthError = `Проверка сервера недоступна: ${result.reason.message}`;
    }
    renderDesktopIntegration();
  }
  function authConnected() {
    const auth = state.status?.auth;
    return ["CONNECTED", "AUTHENTICATED", "LOGGED_IN"].includes(normalizedState(auth?.status)) || auth?.authenticated === true;
  }
  function setOnline(online, error) {
    state.online = online;
    const service = $("service-banner");
    service.hidden = online;
    if (!online) service.textContent = error || "Локальный сервер недоступен. Проверьте, что приложение запущено.";
    renderConnection();
    if(state.selectedRun)renderRun();
  }
  function renderConnection() {
    const connected = runReady();
    const apiActive=(state.providers?.active||state.status?.settings?.execution_backend)==="openai_api";
    const dotClass=!state.online?"red":connected?apiActive&&state.providers?.openai_api?.status!=="CONNECTED"?"yellow":"green":"yellow";
    $("connection-status").replaceChildren(node("span", `status-dot ${dotClass}`), document.createTextNode(!state.online ? "Сервер недоступен" : connected ? apiActive ? "OpenAI API настроен" : "Codex подключён" : apiActive ? "Нужен ключ API" : "Нужен вход"));
    $("sidebar-auth-dot").className = `status-dot ${dotClass}`;
    $("sidebar-auth-label").textContent=!state.online?"Нет связи с сервером":apiActive?connected?"Ключ API настроен":"Требуется ключ API":connected?"Аккаунт подключён":"Авторизация требуется"; $("sidebar-provider-label").textContent=apiActive?"OpenAI API":"ChatGPT / Codex"; $("compose-provider-label").replaceChildren(node("span",`status-dot ${apiActive?"yellow":"green"}`),document.createTextNode(apiActive?"Отдельная оплата OpenAI API":"Через ваш аккаунт Codex")); $("api-required-banner").hidden=!state.online||!apiActive||connected;
    $("auth-banner").hidden = !state.online || connected || apiActive;
    $("start-button").disabled = state.creatingRun || !state.online || !connected || state.runs.some((run) => activeStates.has(normalizedState(run.state)));
    $("start-button").title=state.runs.some(run=>activeStates.has(normalizedState(run.state)))?"Сначала завершите, остановите или приостановите текущий запуск.":!connected?apiActive?"Сохраните ключ API или выберите Codex в настройках.":"Войдите через официальный Codex.":"";
    qa(".login-button").forEach((button) => { button.disabled = !state.online || state.loginPending; }); renderProviderChoice();
  }
  function renderStatus() {
    renderConnection();
    const auth = state.status?.auth || {};
    const account = auth.account || {};
    const details = $("settings-auth-details");
    details.replaceChildren();
    details.append(node("p", "", `Состояние: ${authConnected() ? "аккаунт подключён" : ({AUTH_REQUIRED:"нужен вход",UNAVAILABLE:"подключение недоступно",ERROR:"ошибка подключения",NOT_LOGGED_IN:"нужен вход"}[auth.status] || "нет подключения")}`));
    if (typeof account === "string") details.append(node("p", "", account));
    else for (const [key, label] of [["email", "Аккаунт"], ["planType", "План"], ["plan_type", "План"], ["type", "Тип"]]) {
      if (account[key]) details.append(node("p", "", `${label}: ${account[key]}`));
    }
    if (auth.error) details.append(node("p", "", errorMessage({detail:auth.error},"Не удалось проверить вход. Повторите проверку или войдите в Codex заново.")));
    const capabilities = state.status?.capabilities || {};
    const capabilityLabels = {
      threads: "Независимые сессии", thread_start: "Создание сессии", thread_resume: "Продолжение сессии", resume: "Продолжение сессии",
      thread_fork: "Ответвление сессии", fork: "Ответвление сессии", streaming: "Поток событий", stream: "Поток событий",
      usage: "Расход токенов", token_usage: "Расход токенов", steering: "Указания во время работы агента", steer: "Указания во время работы агента",
      interrupt: "Прерывание работы агента", sandbox: "Изолированная среда Codex", models: "Модели", chatgpt_auth: "Авторизация ChatGPT",
      sdk: "Официальный SDK", version: "Версия", device_code_login: "Вход по коду", auto_review: "Автоматическая проверка",
      parallel: "Параллельные агенты", rate_limits: "Лимиты аккаунта", python_sdk: "Python SDK", approvals:"Разрешения", openai_api:"Подключение через API", parallel_writers:"Одновременная запись агентов", multi_solution:"Несколько вариантов решения",
    };
    const capabilityContainer = $("capabilities-list");
    const entries = Object.entries(capabilities);
    if (!entries.length) empty(capabilityContainer, "Нет данных о возможностях SDK", "Данные появятся после подключения к локальному серверу.");
    else capabilityContainer.replaceChildren(...entries.map(([key, value]) => {
      const row = node("div", "capability-row");
      let display = value;
      if (typeof value === "boolean") display = value ? "Поддерживается" : "Не поддерживается";
      if (value?.status) display = ({CONNECTED:"Подключено",AVAILABLE:"Доступно",UNAVAILABLE:"Недоступно",ERROR:"Ошибка"}[value.status]||"Нет данных");
      if(typeof value==="string"&&key==="approvals")display="Поддерживаемые запросы — через Центр действий; остальные отклоняются";
      if(typeof value==="string"&&key==="openai_api")display="Необязательное подключение с отдельной оплатой; без автоматического переключения";
      row.append(node("span", "", capabilityLabels[key] || key), node("span", "muted", text(display)));
      return row;
    }));
    const modelsList = state.status?.models || capabilities.models;
    if (Array.isArray(modelsList)) $("supported-models").replaceChildren(...modelsList.map((model) => {
      const option = node("option"); option.value = typeof model === "string" ? model : model.id || model.model || model.name || ""; return option;
    }).filter((option) => option.value));
    if (authConnected() && $("login-info").dataset.pending === "true") {
      $("login-info").replaceChildren(node("strong", "", "Аккаунт ChatGPT подключён. Можно запускать команду."));
      delete $("login-info").dataset.pending;
    }
    if (state.page === "usage") loadAccountUsage();
    if (state.page === "agents" || state.page === "settings") loadModels();
  }
  function applyDefaults(settings) {
    if (!settings || typeof settings !== "object") return;
    if(settings.theme)applyAppearance(settings.theme,settings.accent_color||null);
    $("settings-minimize-to-tray").checked=settings.minimize_to_tray===true;
    if(settings.onboarding_dismissed){$("onboarding").hidden=true;storageSet("codex-team-onboarding","dismissed");}
    Object.keys(permissionLabels).forEach(key=>{if(settings.permission_policy?.[key])$("permission-"+key).value=settings.permission_policy[key];});
    for(const [key,id]of [["task_complete","notify-task-complete"],["needs_attention","notify-needs-attention"],["stage_complete","notify-stage-complete"]])if(typeof settings.notifications?.[key]==="boolean")$(id).checked=settings.notifications[key];
    $("settings-model").value = settings.model || "";
    updateEffortOptions($("settings-model").value,"settings-reasoning");$("settings-reasoning").value = settings.reasoning_effort || "";
    const fields = [
      ["max_iterations", "settings-iterations", "max-iterations", 1],
      ["max_agent_calls", "settings-calls", "max-calls", 1],
      ["max_parallel_agents", "settings-parallel", "max-parallel", 1],
      ["max_run_duration", "settings-duration", "max-duration", 60],
    ];
    fields.forEach(([key, settingsId, runId, divisor]) => {
      if (typeof settings[key] === "number") { $(settingsId).value = settings[key] / divisor; $(runId).value = settings[key] / divisor; }
    });
  }
  function renderRegistry() {
    renderRoleModelDefaults();const registrySignature=JSON.stringify([state.agents,state.packs,$("agents-search").value]);if(registrySignature===state.registrySignature)return;state.registrySignature=registrySignature;
    const packs = state.packs.length ? state.packs : [{name: "software-development"}];
    const selectedPack = $("run-pack").value;
    $("run-pack").replaceChildren(...packs.map((pack) => {
      const option = node("option", "", pack.title || pack.label || ({"software-development": "Разработка ПО", "web-development": "Веб-разработка", "game-development": "Разработка игр", "elma365": "ELMA365", audit: "Аудит"}[pack.name]) || pack.name);
      option.value = pack.name; return option;
    }));
    if (packs.some((pack) => pack.name === selectedPack)) $("run-pack").value = selectedPack;
    const chosenSpecialists = new Set(qa("#specialist-options input:checked").map((input) => input.value));
    const specialists = state.agents.filter((agent) => !standardRoles.has(agent.name) && agent.enabled !== false && agent.permission === "read-only");
    $("specialists-group").hidden = !specialists.length || !["deep", "audit"].includes($("run-mode").value);
    $("specialist-options").replaceChildren(...specialists.map((agent) => {
      const label = node("label", "specialist-option"); const input = node("input");
      input.type = "checkbox"; input.value = agent.name; input.checked = chosenSpecialists.has(agent.name);input.addEventListener("change",renderPreview);
      label.append(input, document.createTextNode(roleName(agent.name))); return label;
    }));
    renderPreview();renderPacks(); renderRoleModelDefaults();
    const signature = JSON.stringify(state.agents);
    if (signature === state.agentsSignature) return;
    state.agentsSignature = signature;
    if (!state.agents.length) { empty($("agents-list"), "Команда пока не загружена", "Подключите локальный сервер или добавьте собственного агента."); return; }
    $("agents-list").replaceChildren(...state.agents.filter(agent=>{const q=$("agents-search").value.trim().toLowerCase();return !q||`${agent.name} ${roleName(agent.name)} ${agent.description||roles[agent.name]?.[1]||""}`.toLowerCase().includes(q);}).map((agent, index) => {
      const card = node("article", "panel agent-card");
      const heading = node("div", "agent-card-heading");
      const title = node("div");
      title.append(node("span", "agent-symbol", String(index + 1).padStart(2, "0")), node("h3", "", roleName(agent.name)), node("div", "role-id mono", agent.name));
      heading.append(title, node("span", `state-badge ${agent.enabled !== false ? "state-good" : ""}`, agent.enabled !== false ? "Включён" : "Выключен"));
      card.append(heading, node("p", "agent-instructions-preview", agent.description || roles[agent.name]?.[1] || agent.instructions || "Инструкции не заданы"));
      const footer = node("div", "agent-card-footer");
      const permission = node("span", "agent-permission", agent.permission === "workspace-write" ? "Чтение и запись в рабочей папке" : "Только чтение");
      const edit = node("button", "button text-button", "Изменить →"); edit.type = "button";
      edit.addEventListener("click", () => openAgentEditor(agent));
      footer.append(permission, edit); card.append(footer);
      const actions=node("div","registry-actions");
      actions.append(actionButton("Дублировать",()=>openAgentEditor({...agent,name:"",role:`${roleName(agent.name)} · копия`,builtin:false})),actionButton(agent.enabled===false?"Включить":"Выключить",async()=>{try{await api(`/api/agents/${encodeURIComponent(agent.name)}`,"PUT",{...agentPayload(agent),enabled:agent.enabled===false});await reloadRegistry();}catch(e){toast(e.message,true);}}),actionButton("Экспорт",()=>exportJSON(`${agent.name}.agent.json`,agentPayload(agent))));
      if(!agent.builtin)actions.append(actionButton("Удалить",()=>deleteRegistry("agents",agent),"danger"));
      else card.append(node("p","field-note","Встроенная роль · удаление защищено"));
      card.append(actions); return card;
    }));
  }

  function renderRuns(force = false) {
    const signature = JSON.stringify(state.runs.map((run) => [run.id, run.state, run.current_role, run.calls, run.iteration, run.task, run.updated_at, run.usage]));
    if (!force && signature === state.runsSignature) return;
    state.runsSignature = signature;
    const activeCount = state.runs.filter((run) => activeStates.has(normalizedState(run.state))).length;
    $("active-count").textContent = activeCount;
    $("active-count").hidden = !activeCount;
    if (!state.runs.length) empty($("run-cards"), "Здесь появится работа команды", "Выберите проект и запустите первую задачу.");
    else $("run-cards").replaceChildren(...state.runs.slice(0, 4).map((run) => {
      const button = node("button", `run-card${run.id === state.selectedRun?.id ? " selected" : ""}`);
      button.type = "button";
      button.setAttribute("aria-label", `Открыть запуск: ${run.task}`);
      button.append(node("span", "run-card-icon", activeStates.has(normalizedState(run.state)) ? "→" : "•"));
      const main = node("div"); main.append(node("span", "run-card-title", run.task));
      const meta = node("div", "run-card-meta");
      meta.append(node("span", "mono", run.workspace), node("span", "", modes[run.mode]?.title || run.mode || "Стандартный"));
      main.append(meta);
      const tail = node("div", "run-card-tail"); tail.append(badge(run.state), node("span", "muted", prettyDate(run.created_at)));
      button.append(main, tail); button.addEventListener("click", () => selectRun(run.id)); return button;
    }));
    renderConnection(); renderRunList(); renderDashboard();
    if(state.page==="usage")renderGlobalUsage();
  }
  function renderHistory() {
    const table=makeTable(["Задача / проект","Состояние","Агент","Вызовы","Создан"],state.historyRows.map(run=>{const title=node("div"),open=node("button","",run.task);open.type="button";open.addEventListener("click",()=>selectRun(run.id));title.append(open,node("small","mono",run.workspace));if(run.archived)title.append(node("small","muted","Архивный запуск"));if(run.worktree_deleted)title.append(node("small","muted","Рабочая копия удалена"));return [title,badge(run.state),roleName(run.current_role),run.calls??"—",prettyDate(run.created_at)];}),state.historyTotal?"По этим фильтрам запуски не найдены.":"Запусков пока нет. Создайте первую задачу на странице «Обзор».");
    $("history-list").replaceChildren(table);$("history-prev").disabled=state.historyPage===0;$("history-next").disabled=(state.historyPage+1)*20>=state.historyTotal;$("history-page-info").textContent=`Страница ${state.historyPage+1} · ${formatNumber.format(state.historyTotal)} запусков`;
  }
  function makeTable(headers, rows, noData = "Нет данных") {
    const table = node("table"); const head = node("thead"); const headRow = node("tr");
    headers.forEach((header) => { const th = node("th", "", header); th.scope = "col"; headRow.append(th); }); head.append(headRow);
    const body = node("tbody");
    if (!rows.length) { const row = node("tr"); const cell = node("td", "table-empty", noData); cell.colSpan = headers.length; row.append(cell); body.append(row); }
    rows.forEach((values) => {
      const row = node("tr"); values.forEach((value) => { const cell = node("td"); cell.append(value instanceof Node ? value : document.createTextNode(String(value ?? "—"))); row.append(cell); }); body.append(row);
    });
    table.append(head, body); return table;
  }
  async function selectRun(id,scroll=true) {
    const version=++state.selectionVersion;state.selecting=true;$("steer-instruction").value="";state.events=[];state.lastEventsFetch=0;state.eventCursor=0;state.eventsLoaded=false;state.eventsHasMore=false;state.eventsState=null;state.selectedRole=null;state.selectedAttempt=null;state.selectedAttemptInfo=null;state.stageEvents=[];state.eventsRequest=null;$("events-error").hidden=true;$("more-events-button").disabled=false;$("more-events-button").hidden=true;state.runSignature="";state.actionsSignature="";state.diffLimit=1000;state.diffLines=[];state.diffRun=null;state.diffHasMore=false;state.diffLoading=false;state.diffError=null;state.diffStat=null;
    try{const run=await api(`/api/runs/${encodeURIComponent(id)}`);if(version!==state.selectionVersion)return;state.selectedRun=run;setPage("runs");renderRun();renderRuns(true);renderActions();if(scroll)$("run-detail").scrollIntoView({behavior:window.matchMedia("(prefers-reduced-motion: reduce)").matches?"auto":"smooth",block:"start"});}
    catch(error){if(version===state.selectionVersion)toast(error.message,true);}finally{if(version===state.selectionVersion)state.selecting=false;}
  }
  function availableRoles(run) {
    const pipeline = list(run.pipeline).map((role) => typeof role === "string" ? role : role.role || role.name).filter(Boolean);
    const resultRoles = Object.keys(run.results || {});
    return [...new Set([...pipeline, ...resultRoles, ...Object.keys(run.threads || {}), ...(run.current_role ? [run.current_role] : [])])];
  }
  function renderRun() {
    const run = state.selectedRun;
    if (!run) { $("run-detail").hidden = true; return; }
    $("run-detail").hidden = false;
    $("detail-id").textContent = `ЗАПУСК ${run.id} · ${prettyDate(run.created_at)}`;
    $("detail-task").textContent = run.task;
    const stateBadge = badge(run.state);
    $("detail-state").className = stateBadge.className;
    $("detail-state").textContent = stateBadge.textContent;
    $("detail-workspace").textContent = run.workspace;
    $("detail-role").textContent = roleName(run.current_role);
    $("detail-iteration").textContent = run.iteration ?? "—";
    $("detail-calls").textContent = run.calls ?? "—";
    const workspace = run.worktree?.path || run.worktree?.workspace || run.worktree;
    $("detail-isolation").textContent = workspace ? "Изолированная рабочая копия Git" : run.isolated === false ? "Исходная рабочая папка" : "Ожидание подготовки";
    $("detail-isolation").title = workspace ? text(workspace) : "";
    renderRunProblem(run); renderActivePipeline();
    const currentState = normalizedState(run.state);
    $("run-decision").hidden=currentState!=="USER_DECISION_REQUIRED"||state.actions.some(a=>a.run_id===run.id);
    $("pause-button").hidden = !["RUNNING", "QUEUED", "PAUSING"].includes(currentState);
    $("pause-button").disabled = currentState === "PAUSING";
    $("resume-button").hidden = !resumeStates.has(currentState);
    $("resume-button").disabled = !runReady() || !state.online;
    $("stop-button").hidden = !activeStates.has(currentState);
    $("stop-button").disabled = currentState === "STOPPING";
    const latestControl=state.events.filter(e=>["pause_requested","stop_requested","run_state","resumed","recovered"].includes(e.type)).at(-1);
    if(activeStates.has(currentState)&&latestControl?.type==="pause_requested")$("pause-button").disabled=true;
    if(activeStates.has(currentState)&&latestControl?.type==="stop_requested")$("stop-button").disabled=true;
    $("steer-form").hidden = terminalStates.has(currentState);
    if(state.controlPending || !state.online)qa(".run-controls button, #steer-button, #queue-button").forEach(b=>b.disabled=true);
    else {$("steer-button").disabled=false;$("queue-button").disabled=false;}
    const signature = JSON.stringify([run.results, run.threads, run.pipeline, run.current_role, run.usage, run.state, run.calls]);
    if (signature !== state.runSignature) {
      state.runSignature = signature;
      if(state.detailTab==="overview")renderRoles(); if(state.detailTab==="tests")renderTests(); if(state.detailTab==="artifacts")renderArtifacts(); if(state.detailTab==="usage")renderRunUsage();
    }
    if(state.detailTab==="activity")renderEvents();
  }
  function renderRoles() {
    const run = state.selectedRun;
    const roleList = availableRoles(run);
    if (!roleList.includes(state.selectedRole)) state.selectedRole = run.current_role || roleList[0];
    if (!roleList.length) { $("role-list").replaceChildren(); empty($("role-inspector"), "Команда готовится к работе", "После планирования здесь появятся этапы и результаты агентов."); return; }
    const attempts=MissionControl.attempts(run,state.stageEvents,state.eventsLoaded&&!state.eventsHasMore);
    const focusedRole=Array.from($("role-list").children).find(b=>b===document.activeElement)?.dataset.role;
    $("role-list").replaceChildren(...roleList.map((role) => {
      const button = node("button", `role-button${state.selectedRole === role ? " active" : ""}`); button.type = "button";
      button.dataset.role=role;
      const attempt=[...attempts].reverse().find(a=>a.role===role&&(a.number||a.call||a.result))||attempts.find(a=>a.role===role);
      const result=attempt?.result;
      const isActive=activeStates.has(normalizedState(attempt?.state));
      const needsAction=["USER_DECISION_REQUIRED","AUTH_REQUIRED","USAGE_LIMIT","PAUSED","INTERRUPTED"].includes(normalizedState(attempt?.state));
      const success = result && ["PASS", "APPROVED", "IMPLEMENTED", "PLAN", "ANALYSIS"].includes(normalizedState(result.verdict));
      button.append(node("span", `status-dot ${isActive || needsAction ? "yellow" : result ? success ? "green" : "red" : ""}`), node("span", "", roleName(role)), node("span", "", isActive ? "↗" : needsAction ? "!" : result ? success ? "✓" : "×" : "·"));
      button.setAttribute("aria-pressed", String(state.selectedRole === role));
      button.addEventListener("click", () => { state.selectedRole = role; state.selectedAttempt=null;state.selectedAttemptInfo=null; renderRoles(); }); return button;
    }));
    if(focusedRole)Array.from($("role-list").children).find(b=>b.dataset.role===focusedRole)?.focus();
    renderInspector(state.selectedRole);
  }
  function appendResultSection(container, title, value, asList = false) {
    if (value === null || value === undefined || value === "" || (Array.isArray(value) && !value.length)) return;
    const section = node("section", "result-section"); section.append(node("h3", "", title));
    if (asList && Array.isArray(value)) {
      const ul = node("ul", "result-list"); value.forEach((item) => ul.append(node("li", "", text(item)))); section.append(ul);
    } else section.append(node("div", "result-text", text(value)));
    container.append(section);
  }
  function renderInspector(role) {
    const container = $("role-inspector");
    const run = state.selectedRun;
    const attempts = MissionControl.attempts(run,state.stageEvents,state.eventsLoaded&&!state.eventsHasMore);
    const attempt = attempts.find(a=>a.key===state.selectedAttempt) || [...attempts].reverse().find(a=>a.role===role&&(a.number||a.call||a.result)) || attempts.find(a=>a.role===role);
    const result = attempt ? attempt.result : run.results?.[role];
    const inspectionKey=`${run.id}:${attempt?.key||role}`;
    const keepExpanded=container.dataset.inspection===inspectionKey&&Array.from(container.querySelectorAll("details")).some(d=>d.open);
    container.dataset.inspection=inspectionKey;container.replaceChildren();
    const heading = node("div", "role-inspector-header"); heading.append(node("h3", "", roleName(role)));
    if (attempt) heading.append(badge(attempt.state));
    else if (result?.verdict) heading.append(badge(result.verdict));
    else if (run.current_role === role && activeStates.has(normalizedState(run.state))) heading.append(badge("RUNNING"));
    container.append(heading);
    if(attempt) {
      const timing = node("dl","mission-metadata");
      for(const [label,value] of [["Попытка",attempt.historyOnly?"Нет данных (сохранённый результат)":attempt.number|| (attempt.call?`Вызов ${attempt.call}`:"Ещё не начата")],["Итерация",attempt.iteration??"Нет данных"],["Начало",attempt.started?prettyDate(attempt.started):"Нет данных"],["Завершение",attempt.ended?prettyDate(attempt.ended):"Нет данных"]])timing.append(node("dt","",label),node("dd","",value));
      if(attempt.started&&attempt.ended)timing.append(node("dt","","Продолжительность"),node("dd","",`${Math.max(0,Math.round((new Date(attempt.ended)-new Date(attempt.started))/1000))} с`));
      container.append(timing);
      if(attempt.error)appendResultSection(container,"Ошибка / блокировка",attempt.error);
    }
    appendResultSection(container,"Задача запуска",run.task);
    const roleUsage=aggregateUsage(list(run.usage).filter(u=>(u.agent||u.role)===role));
    appendResultSection(container,"Токены роли за весь запуск",roleUsage.total===null?"Нет данных":formatNumber.format(roleUsage.total));
    const recent=state.events.filter(e=>e.role===role).slice(-5);
    if(recent.length)appendResultSection(container,"Последние события роли",recent.map(e=>`${prettyDate(e.created_at,true)} · ${eventLabels[e.type]||e.type}: ${eventSummary(e.payload)}`),true);
    const thread = run.threads?.[role];
    if (thread) container.append(node("div", "thread-id mono", `Сессия: ${typeof thread === "string" ? thread : thread.id || thread.thread_id || text(thread)}`));
    if (!result) {
      container.append(node("p", "muted", run.current_role === role ? "Результат появится после завершения этапа. Действия агента доступны во вкладке «События»." : "Роль ещё не завершила свой этап."));
      return;
    }
    if (typeof result === "string") { appendResultSection(container, "Результат", result); return; }
    appendResultSection(container, "Результат", result.summary || result.result || result.output);
    appendResultSection(container, "Проверки", result.tests, true);
    appendResultSection(container, "План", result.plan, true);
    appendResultSection(container, "Критерии приёмки", result.acceptance_criteria, true);
    appendResultSection(container, "Важные файлы", result.relevant_files || result.changed_files, true);
    appendResultSection(container, "Команды сборки", result.build_commands, true);
    appendResultSection(container, "Предположения", result.assumptions, true);
    if (result.findings?.length) {
      const section = node("section", "result-section"); section.append(node("h3", "", "Замечания и доказательства"));
      result.findings.forEach((finding) => {
        const card = node("div", "test-card");
        const title = node("div", "test-card-heading"); title.append(node("strong", "", finding.problem || finding.title || "Замечание"), node("span", `state-badge ${["critical", "high"].includes(finding.severity) ? "state-error" : "state-warning"}`, ({critical:"Критическая",high:"Высокая",medium:"Средняя",low:"Низкая",info:"Информация"}[finding.severity] || finding.severity || "")));
        card.append(title);
        if (finding.file) card.append(node("div", "mono muted", finding.file));
        appendResultSection(card, "Доказательство", finding.evidence);
        appendResultSection(card, "Ожидаемое поведение", finding.expected_behavior);
        appendResultSection(card, "Исправление", finding.suggested_fix);
        section.append(card);
      }); container.append(section);
    }
    if (Object.keys(result.project_map || {}).length) appendResultSection(container, "Карта проекта", result.project_map);
    const details = node("details", "raw-details");details.open=keepExpanded; details.append(node("summary", "", "Полный структурированный результат"), node("pre", "code-block", text(result))); container.append(details);
  }
  function renderDiff() {
    const run=state.selectedRun;if(!run)return;
    if(state.diffError){$("diff-content").textContent=`Не удалось загрузить изменения: ${state.diffError}`;$("more-diff-button").hidden=true;return;}
    $("diff-stat").textContent=text(state.diffStat||run.diff_stat||"Изменённые файлы пока не зарегистрированы.");
    if(!state.diffLines.length){$("diff-content").textContent=state.diffLoading?"Загрузка изменений…":"Изменений в Git пока нет. Они появятся после редактирования файлов.";$("more-diff-button").hidden=!state.diffHasMore;return;}
    const fragment=document.createDocumentFragment();state.diffLines.slice(0,state.diffLimit).forEach(line=>{const cls=line.startsWith("+++")||line.startsWith("---")||line.startsWith("@@")||line.startsWith("diff ")?"header":line.startsWith("+")?"addition":line.startsWith("-")?"deletion":"";fragment.append(node("span",`diff-line ${cls}`,line||" "));});$("diff-content").replaceChildren(fragment);$("more-diff-button").hidden=!state.diffHasMore&&state.diffLimit>=state.diffLines.length;$("more-diff-button").disabled=state.diffLoading;
  }
  async function loadDiff(more=false) {
    const run=state.selectedRun;if(!run||state.diffLoading)return;
    if(state.diffRun===run.id&&!more){renderDiff();return;}
    const version=state.selectionVersion;state.diffLoading=true;state.diffError=null;renderDiff();
    try{const response=await api(`/api/runs/${encodeURIComponent(run.id)}/diff?offset=${more?state.diffLines.length:0}&limit=1000`);if(version!==state.selectionVersion)return;const chunk=(response.diff||"").split("\n");if(chunk.at(-1)==="")chunk.pop();state.diffLines=more?[...state.diffLines,...chunk]:chunk;state.diffStat=response.diff_stat;state.diffHasMore=Boolean(response.has_more);state.diffTotal=response.total_lines??state.diffLines.length;state.diffRun=run.id;}
    catch(error){if(error.status===404&&version===state.selectionVersion){state.diffLines=(typeof run.diff==="string"?run.diff:"").split("\n");if(!run.diff)state.diffLines=[];state.diffHasMore=false;state.diffRun=run.id;}else if(version===state.selectionVersion)state.diffError=error.message;}
    finally{if(version===state.selectionVersion){state.diffLoading=false;renderDiff();}}
  }
  function renderTests() {
    const entries = Object.entries(state.selectedRun?.results || {}).flatMap(([role, result]) => list(result?.tests).map((test) => ({role, test})));
    const container = $("tests-content");
    if (!entries.length) { empty(container, "Результатов тестов пока нет", "Здесь появятся команды, exit code и вывод, переданные агентами."); return; }
    container.replaceChildren(...entries.map(({role, test}) => {
      const card = node("section", "test-card");
      const title = node("div", "test-card-heading");
      title.append(node("strong", "mono", test.command || "Тест"), badge(test.exit_code === 0 ? "PASS" : test.exit_code === null || test.exit_code === undefined ? "Не завершён" : "FAIL"));
      card.append(title, node("p", "muted", `${roleName(role)} · exit code: ${test.exit_code ?? "не указан"}`));
      card.append(node("pre", "code-block", text(test.output || "Вывод не предоставлен"))); return card;
    }));
  }
  function renderArtifacts() {
    const run = state.selectedRun;
    const container = $("artifacts-content");
    container.replaceChildren();
    const context = node("div", "result-section");
    appendResultSection(context, "Рабочая копия", run.worktree?.path || run.worktree?.workspace || run.worktree || run.workspace);
    if (run.artifact_path || run.artifacts_path) appendResultSection(context, "Каталог артефактов", run.artifact_path || run.artifacts_path);
    container.append(context);
    const artifactList = node("div", "artifact-list");
    list(run.artifacts).forEach((artifact) => {
      const el = node("div", "artifact-item", typeof artifact === "string" ? artifact : artifact.path || artifact.name || text(artifact));
      if (artifact?.description) el.append(node("small", "", artifact.description)); artifactList.append(el);
    });
    Object.entries(run.results || {}).forEach(([role, result]) => {
      const details = node("details", "raw-details"); details.append(node("summary", "", `${roleName(role)} · структурированный результат`), node("pre", "code-block", text(result))); artifactList.append(details);
    });
    if (!artifactList.childElementCount) artifactList.append(node("p", "muted", "Артефакты появятся после завершения первого этапа."));
    container.append(artifactList);
  }

  function usageRecord(record) {
    return record?.usage?.tokenUsage?.last || record?.usage?.last || record?.tokenUsage?.last || record?.last || record?.usage || record?.token_usage || record?.tokens || record || {};
  }
  function usageValue(record, keys) {
    const data = usageRecord(record);
    for (const key of keys) if (typeof data[key] === "number" && Number.isFinite(data[key])) return data[key];
    return null;
  }
  function aggregateUsage(records) {
    const totals = {input: null, output: null, cached: null, total: null};
    records.forEach((record) => {
      const values = {
        input: usageValue(record, ["input_tokens", "inputTokens", "input"]),
        output: usageValue(record, ["output_tokens", "outputTokens", "output"]),
        cached: usageValue(record, ["cached_input_tokens", "cachedInputTokens", "cached_tokens", "cached"]),
        total: usageValue(record, ["total_tokens", "totalTokens", "total"]),
      };
      if (values.total === null && values.input !== null && values.output !== null) values.total = values.input + values.output;
      Object.entries(values).forEach(([key, value]) => { if (value !== null) totals[key] = (totals[key] ?? 0) + value; });
    });
    return totals;
  }
  function usageCards(totals) {
    const container = node("div", "usage-cards");
    [["total", "Всего токенов", "Вход + выход"], ["input", "Входные токены", "Переданный контекст"], ["output", "Выходные токены", "Ответы агентов"], ["cached", "Кэшированные входные", "Входят в число входных"]].forEach(([key, label, description]) => {
      const card = node("div", "usage-card");
      card.append(node("span", "", label), node("strong", "", totals[key] === null ? "—" : formatNumber.format(totals[key])), node("small", "", totals[key] === null ? "SDK не передал данные" : description));
      container.append(card);
    }); return container;
  }
  function renderRunUsage() {
    const records = list(state.selectedRun?.usage);
    const container = $("run-usage-content");
    container.replaceChildren(usageCards(aggregateUsage(records)), node("p", "muted", "Данные из официальных ответов Codex. Токены не пересчитываются в деньги или доступную квоту."));
    if (records.length) {
      const table = makeTable(["Роль", "Вход", "Выход", "Кэш", "Всего"], records.map((record) => {
        const totals = aggregateUsage([record]);
        return [roleName(record.role || record.agent), ...["input", "output", "cached", "total"].map((key) => totals[key] === null ? "—" : formatNumber.format(totals[key]))];
      })); const wrap = node("div", "table-container result-section"); wrap.append(table); container.append(wrap);
    }
  }
  function renderGlobalUsage() {
    const records = state.runs.flatMap((run) => list(run.usage));
    const signature = JSON.stringify([state.runs.map((run) => [run.id, run.state, run.task, run.calls, run.usage])]);
    if (signature === state.usageSignature) return;
    state.usageSignature = signature;
    $("total-usage-content").replaceChildren(usageCards(loadedUsageTotals()),node("p","muted",state.allUsage?"Сумма по всем сохранённым запускам.":"Сумма по загруженным запускам. Данные отдельных задач доступны в истории."));
    $("usage-runs-list").replaceChildren(makeTable(["Задача", "Состояние", "Вызовы", "Токены"], state.runs.map((run) => {
      const button = node("button", "", run.task); button.type = "button"; button.addEventListener("click", () => selectRun(run.id));
      const total = summaryTotals(run).total;
      return [button, badge(run.state), run.calls ?? "—", total === null ? "—" : formatNumber.format(total)];
    }), "Запуски пока отсутствуют."));
  }

  async function loadModels() {
    if (state.modelsLoaded || state.modelsLoading || !authConnected() || !state.online) return;
    state.modelsLoading = true;
    try {
      const response = await api("/api/models");
      const data = Array.isArray(response) ? response : response.data || response.models || [];
      $("supported-models").replaceChildren(...data.map((model) => {
        const option = node("option"); option.value = typeof model === "string" ? model : model.model || model.id || "";
        if (model.displayName || model.display_name) option.label = model.displayName || model.display_name;
        return option;
      }).filter((option) => option.value));
      state.availableModels=data.map(m=>typeof m==="string"?{id:m}:m);state.modelsLoaded = true; updateEffortOptions($("agent-model").value,"agent-reasoning"); updateEffortOptions($("settings-model").value,"settings-reasoning"); renderRoleModelDefaults();
    } catch (_) { /* Free-form model configuration remains available when model/list is unavailable. */ }
    finally { state.modelsLoading = false; }
  }
  async function loadAccountUsage(force = false) {
    if (state.accountUsageLoading || !state.online || !authConnected() || (!force && Date.now() - state.lastAccountUsage < 60000)) return;
    state.accountUsageLoading = true;
    const container = $("account-usage-note");
    if (!state.accountUsage) container.textContent = "Получаем лимиты аккаунта из официального Codex…";
    try {
      state.accountUsage = await api("/api/usage"); state.lastAccountUsage = Date.now(); renderAccountUsage();
    } catch (error) {
      state.lastAccountUsage = Date.now();
      container.textContent = `Лимиты аккаунта сейчас недоступны: ${error.message}`;
    } finally { state.accountUsageLoading = false; }
  }
  function renderAccountUsage() {
    const container = $("account-usage-note");
    const data = state.accountUsage || {};
    const parent = container.parentElement;
    qa("#page-usage .quota-content, #page-usage .quota-refresh").forEach((el) => el.remove());
    const refreshButton = node("button", "button secondary quota-refresh", "Обновить лимиты ↻");
    refreshButton.type = "button"; refreshButton.addEventListener("click", () => loadAccountUsage(true));
    parent.append(refreshButton);
    if (data.unavailable) { container.textContent = `Официальные данные сейчас недоступны: ${text(data.unavailable)}`; return; }
    const limits = data.rateLimitsByLimitId || data.rate_limits_by_limit_id;
    const entries = limits && Object.keys(limits).length ? Object.entries(limits) : data.rateLimits || data.rate_limits ? [["Codex", data.rateLimits || data.rate_limits]] : [];
    const content = node("div", "quota-content");
    entries.forEach(([id, limit]) => {
      const group = node("section", "quota-group");
      group.append(node("h3", "", limit.limitName || limit.limit_name || id));
      ["primary", "secondary"].forEach((kind) => {
        const window = limit[kind];
        const used = window?.usedPercent ?? window?.used_percent;
        if (typeof used !== "number" || !Number.isFinite(used)) return;
        const remaining = Math.max(0, Math.min(100, 100 - used));
        const minutes = window.windowDurationMins ?? window.window_duration_mins;
        const duration = typeof minutes === "number" ? minutes >= 1440 ? `${formatNumber.format(minutes / 1440)} дн.` : minutes >= 60 ? `${formatNumber.format(minutes / 60)} ч.` : `${formatNumber.format(minutes)} мин.` : "";
        const row = node("div", "quota-window"); const heading = node("div", "quota-heading");
        heading.append(node("span", "", `${kind === "primary" ? "Основное окно" : "Дополнительное окно"}${duration ? ` · ${duration}` : ""}`), node("strong", "", `${formatNumber.format(remaining)}% осталось`));
        const progress = node("progress", "quota-progress"); progress.max = 100; progress.value = Math.max(0, Math.min(100, used));
        progress.setAttribute("aria-label", `Использовано ${used}%`);
        const reset = window.resetsAt ?? window.resets_at;
        const resetValue = typeof reset === "number" ? new Date(reset * 1000) : null;
        const resetDate = resetValue && !Number.isNaN(resetValue.getTime()) ? resetValue.toISOString() : typeof reset === "string" ? reset : null;
        row.append(heading, progress, node("p", "muted", `Использовано: ${formatNumber.format(used)}%${resetDate ? ` · сброс ${prettyDate(resetDate)}` : ""}`));
        group.append(row);
      });
      if (group.childElementCount > 1) content.append(group);
    });
    container.textContent = content.childElementCount ? "Данные официального сервиса Codex. Лимиты общие для аккаунта, включая другие сессии Codex." : "SDK не передал доступные окна лимитов аккаунта.";
    if (content.childElementCount) parent.insertBefore(content, refreshButton);
  }

  function eventSummary(payload) {
    if (typeof payload === "string") return payload.slice(0, 1200);
    if (!payload) return "";
    const item = payload.item || payload;
    if(Array.isArray(item.changes)&&item.changes.some(c=>c.path))return `Файлы: ${item.changes.map(c=>c.path).filter(Boolean).join(", ").slice(0,1200)}`;
    return text(item.command || item.summary || item.message || item.instruction || stateLabels[normalizedState(item.state||item.verdict)] || item.state || item.verdict || item.error || eventLabels[item.type] || item.type || "").slice(0, 1200);
  }
  function showEventError(error) {
    $("events-error").hidden=false;$("events-error").textContent=error.message;
    $("events-status").textContent="Сохранённая лента доступна. Повторите загрузку.";
    $("more-events-button").hidden=false;
  }
  function renderEvents() {
    $("events-count").textContent = state.events.length;
    const container=$("event-list"), filter=state.eventFilter;
    const visible=state.events.filter(e=>filter==="all"||MissionControl.category(e)===filter);
    const context=`${state.selectedRun?.id}:${filter}`;
    const same=container.dataset.context===context;
    const wasAtBottom=container.scrollHeight-container.scrollTop-container.clientHeight<70;
    const previousScroll=container.scrollTop;
    if(!same){container.replaceChildren();container.dataset.context=context;}
    const existing=new Map(Array.from(container.children).filter(el=>el.dataset.eventId).map(el=>[el.dataset.eventId,el]));
    const wanted=new Set(visible.map(e=>String(e.id)));
    for(const [id,el] of existing)if(!wanted.has(id))el.remove();
    if(visible.length){
      if(!existing.size)container.replaceChildren();
      for(const event of visible){
        if(existing.has(String(event.id)))continue;
        const row=node("article","event-item");row.dataset.eventId=String(event.id);
        row.append(node("time","event-time",prettyDate(event.created_at,true)));
        const content=node("div"),title=node("div","event-title");
        if(event.role)title.append(node("span","event-role",roleName(event.role)));
        title.append(document.createTextNode(eventLabels[event.type]||event.type));content.append(title);
        const summary=eventSummary(event.payload);if(summary)content.append(node("p","event-summary",summary));
        if(event.payload&&Object.keys(event.payload).length){const details=node("details","event-details");details.append(node("summary","","Данные события"),node("pre","code-block",text(event.payload)));content.append(details);}
        row.append(content);container.append(row);
      }
    } else empty(container,"Нет событий",state.eventsLoaded?"Для выбранного фильтра пока нет событий.":"Загружаем сохранённые события запуска…");
    if($("follow-events").checked&&(wasAtBottom||!same))container.scrollTop=container.scrollHeight;
    else container.scrollTop=previousScroll;
    $("events-status").textContent=`Показано ${visible.length} · загружено ${state.events.length}${state.eventsHasMore?" · есть следующие страницы":""}`;
  }
  async function fetchEvents(id,version) {
    if(state.eventsRequest)return state.eventsRequest;
    const button=$("more-events-button");button.disabled=true;
    const request=(async()=>{
      try {
        const response=await api(`/api/runs/${encodeURIComponent(id)}/events?after=${state.eventCursor}&limit=100&meaningful=true`);
        if(version!==state.selectionVersion||state.selectedRun?.id!==id)return;
        const data=Array.isArray(response)?response:response.items||response.events||[];
        state.lastEventsFetch=Date.now();state.eventsLoaded=true;state.eventsHasMore=Boolean(response.has_more);state.eventsState=normalizedState(state.selectedRun.state);
        const ids=new Set(state.events.map(e=>e.id));const added=data.filter(e=>!ids.has(e.id));state.events.push(...added);
        state.stageEvents.push(...added.filter(e=>["agent_started","agent_completed"].includes(e.type)));
        state.eventCursor=response.next_cursor??Math.max(state.eventCursor,...data.map(e=>Number(e.id)||0));
        if(state.events.length>600)state.events.splice(0,state.events.length-600);
        $("events-error").hidden=true;button.hidden=!state.eventsHasMore;renderEvents();renderActivePipeline();
        if(state.detailTab==="overview"&&added.length)renderRoles();
      }catch(error){if(version===state.selectionVersion)showEventError(error);}
      finally{if(version===state.selectionVersion){state.eventsRequest=null;button.disabled=false;}}
    })();
    state.eventsRequest=request;return request;
  }
  async function refresh() {
    if(state.refreshing)return;state.refreshing=true;$("refresh-button").disabled=true;
    try{const responses=await Promise.allSettled([api("/api/status"),api("/api/runs?summary=true&limit=20&offset=0"),api("/api/agents"),api("/api/packs"),api("/health"),api("/api/providers")]);updateHealth(responses[4]);
      if(responses[0].status==="fulfilled"){const first=!state.status;state.status=responses[0].value;state.lastStatus=Date.now();setOnline(true);renderStatus();if(first)applyDefaults(state.status.settings);}else setOnline(false,responses[0].reason.message);
      if(responses[1].status==="fulfilled"){acceptRuns(responses[1].value);state.lastRunList=Date.now();}
      if(responses[2].status==="fulfilled")state.agents=Array.isArray(responses[2].value)?responses[2].value:responses[2].value.agents||[];
      if(responses[3].status==="fulfilled")state.packs=Array.isArray(responses[3].value)?responses[3].value:responses[3].value.packs||[];
      if(responses[2].status==="fulfilled"||responses[3].status==="fulfilled"){renderRegistry();state.lastRegistry=Date.now();}
      if(responses[5].status==="fulfilled"){state.providers=responses[5].value;renderProviders();renderConnection();}
      if(state.online){await loadActions();if(["projects","history"].includes(state.page))await loadProjects();if(state.page==="history")await loadHistory();}
      if(state.selectedRun&&!state.controlPending&&!state.pendingActions.size){const id=state.selectedRun.id,version=state.selectionVersion,revision=state.runRevision,run=await api(`/api/runs/${encodeURIComponent(id)}`);if(version===state.selectionVersion&&revision===state.runRevision){state.selectedRun=run;renderRun();if(["overview","activity"].includes(state.detailTab))await fetchEvents(id,version);if(state.detailTab==="diff"){state.diffRun=null;await loadDiff();}}}
    }catch(error){toast(error.message,true);}finally{state.refreshing=false;$("refresh-button").disabled=false;}
  }
  async function poll() {
    if(state.polling||state.refreshing||state.selecting||state.controlPending||state.pendingActions.size||document.hidden)return;state.polling=true;
    try{if(Date.now()-state.lastStatus>15000||!state.online){state.status=await api("/api/status");state.lastStatus=Date.now();setOnline(true);renderStatus();}
      const active=state.runs.some(r=>activeStates.has(normalizedState(r.state)));
      if(Date.now()-state.lastRunList>(active?1800:10000)){acceptRuns(await api("/api/runs?summary=true&limit=20&offset=0"));state.lastRunList=Date.now();}
      await loadActions();
      const run=state.selectedRun,id=run?.id,version=state.selectionVersion,revision=state.runRevision,summary=state.runs.find(r=>r.id===id);
      if(id&&state.page==="runs"&&Date.now()-state.lastRunDetail>1800&&((summary&&(summary.state!==run.state||summary.calls!==run.calls||summary.current_role!==run.current_role||summary.iteration!==run.iteration))||(activeStates.has(normalizedState(run.state))&&Date.now()-state.lastRunDetail>30000))){const updated=await api(`/api/runs/${encodeURIComponent(id)}`);if(version===state.selectionVersion&&revision===state.runRevision){state.selectedRun=updated;state.lastRunDetail=Date.now();renderRun();}}
      if(id&&state.page==="runs"&&["overview","activity"].includes(state.detailTab)&&(activeStates.has(normalizedState(state.selectedRun.state))||Date.now()-state.lastEventsFetch>10000||state.eventsHasMore||!state.eventsLoaded||state.eventsState!==normalizedState(state.selectedRun.state)))await fetchEvents(id,version);
      if(Date.now()-state.lastRegistry>30000){const rs=await Promise.allSettled([api("/api/agents"),api("/api/packs")]);if(rs[0].status==="fulfilled")state.agents=Array.isArray(rs[0].value)?rs[0].value:rs[0].value.agents||[];if(rs[1].status==="fulfilled")state.packs=Array.isArray(rs[1].value)?rs[1].value:rs[1].value.packs||[];state.lastRegistry=Date.now();renderRegistry();}
    }catch(error){setOnline(false,error.message);}finally{state.polling=false;}
  }
  async function control(action, instruction) {
    const id = state.selectedRun?.id;
    if (!id || state.controlPending) return;
    state.controlPending=true;state.runRevision++;
    const selection=state.selectionVersion;
    const submittedInstruction=$("steer-instruction").value;
    const buttons = qa(".run-controls button, #steer-button, #queue-button"); buttons.forEach((button) => { button.disabled = true; });
    try {
      await api(`/api/runs/${encodeURIComponent(id)}/control`, "POST", {action, ...(instruction ? {instruction} : {})});
      state.runRevision++;
      toast({pause: "Пауза запрошена после завершения текущего этапа.", stop: "Запрошена остановка запуска.", resume: "Запуск продолжен.", steer: "Указание передано команде.", queue: "Указание сохранено для следующего этапа."}[action]);
      if (instruction && selection===state.selectionVersion && $("steer-instruction").value===submittedInstruction) $("steer-instruction").value = "";
      const version = selection;
      const run = await api(`/api/runs/${encodeURIComponent(id)}`);
      if (version === state.selectionVersion && state.selectedRun?.id === id) { state.selectedRun = run; renderRun(); }
    } catch (error) { toast(error.message, true); }
    finally { state.controlPending=false; buttons.forEach((button) => { button.disabled = false; }); if (state.selectedRun) renderRun(); }
  }
  async function login(method) {
    if (state.loginPending) return;
    state.loginPending = true; renderConnection();
    const container = $("login-info"); container.hidden = false;
    container.replaceChildren(node("strong", "", "Запускается официальный вход Codex…"));
    try {
      const result = await api("/api/login", "POST", {method});
      container.replaceChildren(node("strong", "", "Завершите вход в официальном окне ChatGPT / Codex"));
      container.dataset.pending = "true";
      const url = result.authUrl || result.auth_url || result.verificationUrl || result.verificationUri || result.verification_uri || result.verification_url || result.url;
      const code = result.userCode || result.user_code || result.code;
      if (code) container.append(node("div", "login-code", code));
      if (url) {
        let parsed;
        try { parsed = new URL(url); } catch (_) { parsed = null; }
        // Login URLs must be HTTPS URLs on the official OpenAI authentication domains.
        if (parsed && parsed.protocol === "https:" && (parsed.hostname === "openai.com" || parsed.hostname.endsWith(".openai.com") || parsed.hostname === "chatgpt.com" || parsed.hostname.endsWith(".chatgpt.com"))) {
          const link = node("a", "login-link", "Открыть страницу входа ↗"); link.href = parsed.href; link.target = "_blank"; link.rel = "noopener noreferrer"; container.append(link);
        } else container.append(node("p", "", "Сервер вернул неподдерживаемый адрес входа. Используйте официальный codex login в терминале."));
      }
      if (result.message || result.instructions) container.append(node("p", "", result.message || result.instructions));
      if (result.expiresAt || result.expires_at) container.append(node("p", "muted", `Код действителен до ${prettyDate(result.expiresAt || result.expires_at)}`));
      container.append(node("p", "muted", "Подключение проверяется автоматически. Сессия хранится официальным Codex."));
      state.lastStatus = 0; await poll();
    } catch (error) { container.replaceChildren(node("strong", "", error.message)); toast(error.message, true); }
    finally { state.loginPending = false; renderConnection(); }
  }
  function openAgentEditor(agent) {
    state.editingAgent = agent?.name || null;
    $("agent-editor").hidden = false;
    $("agent-editor-title").textContent = agent ? `Агент: ${agent.name?roleName(agent.name):agent.role}` : "Новый агент";
    $("agent-name").value = agent?.name || ""; $("agent-name").readOnly = Boolean(agent);
    $("agent-role").value = agent?.role===agent?.name&&agent?.name?roleName(agent.name):agent?.role || ""; $("agent-description").value=agent?.description||""; renderModeChecks($("agent-mode-options"),agent?.enabled_modes||Object.keys(modes)); $("agent-instructions").value = agent?.instructions || "";
    $("agent-permission").value = agent?.permission || "read-only";
    $("agent-permission").disabled = Boolean(agent && ["coordinator", "analyst", "qa", "reviewer", "architect", "final-audit"].includes(agent.name));
    $("agent-model").value = agent?.model || ""; updateEffortOptions($("agent-model").value,"agent-reasoning");$("agent-reasoning").value = agent?.reasoning_effort || "";
    $("agent-can-execute").checked=agent?.can_execute!==false; $("agent-can-network").checked=agent?.can_network===true; $("agent-enabled").checked = agent?.enabled !== false; showFormError("agent-form-error", "");
    $("agent-editor").scrollIntoView({behavior: "smooth", block: "start"});
    (agent ? $("agent-instructions") : $("agent-name")).focus({preventScroll: true});
  }

  // Release Candidate features use the official backend contracts; no provider fallback.
  const themeNames = new Set(["system", "light", "dark", "purple-neon", "dark-fantasy"]);
  const permissionLabels = {file_access:"Доступ к файлам",command_execution:"Выполнение команд",package_installation:"Установка пакетов",network_access:"Доступ к сети",git_operations:"Git-операции",external_tools:"Внешние инструменты",project_writes:"Изменения проекта"};
  const decisionLabels = {allow_once:"Разрешить один раз",allow_run:"Разрешить в этой сессии",deny:"Запретить",cancel:"Отменить запрос",answer:"Отправить ответ",resume:"Продолжить задачу",stop:"Остановить задачу",explain:"Попросить объяснить"};
  function actionButton(label, fn, variant = "secondary") { const b=node("button",`button ${variant}`,label);b.type="button";b.addEventListener("click",fn);return b; }
  function storageGet(key) { try{return localStorage.getItem(key);}catch(_){return null;} }
  function storageSet(key,value) { try{localStorage.setItem(key,value);}catch(_){/* private mode */} }
  function accentInk(hex) { const rgb=hex.slice(1).match(/../g).map(v=>parseInt(v,16)/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4);const luminance=.2126*rgb[0]+.7152*rgb[1]+.0722*rgb[2];return (luminance+.05)/.05>1.05/(luminance+.05)?"#111318":"#ffffff"; }
  function readableAccent(hex,background) { const parse=v=>v.slice(1).match(/../g).map(n=>parseInt(n,16));const lum=rgb=>rgb.map(n=>n/255).map(n=>n<=.04045?n/12.92:((n+.055)/1.055)**2.4).reduce((n,v,i)=>n+v*[.2126,.7152,.0722][i],0);if(!/^#[0-9a-f]{6}$/i.test(background))return hex;const rgb=parse(hex),base=lum(parse(background)),target=base>.35?0:255;for(let weight=0;weight<=1;weight+=.05){const mixed=rgb.map(n=>Math.round(n*(1-weight)+target*weight)),value=lum(mixed),ratio=(Math.max(value,base)+.05)/(Math.min(value,base)+.05);if(ratio>=4.5)return '#'+mixed.map(n=>n.toString(16).padStart(2,'0')).join('');}return target?'#ffffff':'#111318'; }
  function applyAppearance(theme,accent,cache=true) {
    if(!themeNames.has(theme))theme="system";
    accent=/^#[0-9a-f]{6}$/i.test(accent||"")?accent:null;
    state.appearance={theme,accent_color:accent};
    const resolved=theme==="system"?(window.matchMedia("(prefers-color-scheme: light)").matches?"light":"dark"):theme;
    document.documentElement.dataset.theme=resolved;
    document.documentElement.dataset.themePreference=theme;
    document.documentElement.style.removeProperty("--accent");document.documentElement.style.removeProperty("--accent-ink");document.documentElement.style.removeProperty("--accent-text");
    if(accent){document.documentElement.style.setProperty("--accent",accent);document.documentElement.style.setProperty("--accent-ink",accentInk(accent));document.documentElement.style.setProperty("--accent-text",readableAccent(accent,getComputedStyle(document.documentElement).getPropertyValue("--panel").trim()));}
    $("settings-theme").value=theme;$("settings-accent").value=accent||(resolved==="light"?"#335d23":resolved==="purple-neon"?"#d1b2ff":resolved==="dark-fantasy"?"#dec598":"#b8e97d");
    qa("[data-accent]").forEach(b=>{const active=(b.dataset.accent||null)===accent;b.classList.toggle("active",active);b.setAttribute("aria-pressed",String(active));});
    if(cache)storageSet("codex-team-appearance",JSON.stringify(state.appearance));
  }
  function initializeAppearance() { let saved;try{saved=JSON.parse(storageGet("codex-team-appearance")||"null");}catch(_){saved=null;}applyAppearance(saved?.theme||"system",saved?.accent_color||null,false);window.matchMedia("(prefers-color-scheme: light)").addEventListener?.("change",()=>{if(state.appearance.theme==="system")applyAppearance("system",state.appearance.accent_color,false);}); }
  function initializePolicies() {
    $("permission-settings").replaceChildren(...Object.entries(permissionLabels).map(([key,label])=>{const wrap=node("div"),l=node("label","",label),s=node("select");s.id="permission-"+key;l.htmlFor=s.id;for(const [value,title]of [["ask","Запрашивать"],["deny","Запрещать"]]){const o=node("option","",title);o.value=value;s.append(o);}wrap.append(l,s);return wrap;}));
    renderModeChecks($("agent-mode-options"),Object.keys(modes),true);
    $("runs-detail-slot").append($("run-detail"));
    $("onboarding").hidden=storageGet("codex-team-onboarding")==="dismissed";
  }
  function renderModeChecks(container,selected,showAll=false) { container.replaceChildren(...Object.entries(modes).map(([id,mode])=>{const l=node("label","specialist-option"),i=node("input");i.type="checkbox";i.value=id;i.checked=showAll||selected.includes(id);l.append(i,document.createTextNode(mode.title));return l;})); }
  function runReady() { return (state.providers?.active||state.status?.settings?.execution_backend)==="openai_api"?state.providers?.openai_api?.configured===true:authConnected(); }
  function modelEffortOptions(modelId) {const model=state.availableModels?.find(m=>(m.model||m.id)===modelId)||(!modelId?state.availableModels?.find(m=>m.isDefault||m.is_default):null);return list(model?.supportedReasoningEfforts||model?.supported_reasoning_efforts).map(e=>typeof e==="string"?e:e.reasoningEffort||e.reasoning_effort||e.effort).filter(Boolean);}
  function effortLabelText(value) {return {none:"Без дополнительного анализа",minimal:"Минимальная",low:"Низкая",medium:"Средняя",high:"Высокая",xhigh:"Очень высокая",max:"Максимальная",ultra:"Предельная"}[value]||value;}
  function scopeLabel(value) {return {turn:"Текущий шаг агента",session:"Текущая сессия",run:"Этот запуск",project:"Этот проект",once:"Однократно",command:"Эта команда",workspace:"Рабочая папка",network:"Доступ к сети"}[value]||value;}
  function updateEffortOptions(modelId,selectId) {const select=typeof selectId==="string"?$(selectId):selectId,selected=select.value,official=modelEffortOptions(modelId);const values=official.length?official:["none","minimal","low","medium","high","xhigh","max","ultra"];const def=node("option","","По умолчанию Codex");def.value="";select.replaceChildren(def,...values.map(value=>{const o=node("option","",effortLabelText(value));o.value=value;return o;}));select.value=values.includes(selected)?selected:"";}
  function renderRoleModelDefaults() {
    if(state.roleDefaultsDirty)return;
    const signature=JSON.stringify([state.agents.map(a=>[a.name,a.role,a.model,a.reasoning_effort]),state.status?.settings?.role_model_defaults,state.modelsLoaded]);if(signature===state.roleDefaultsSignature)return;state.roleDefaultsSignature=signature;
    const defaults=state.status?.settings?.role_model_defaults||{};state.roleDefaultInputs=new Map();
    if(!state.agents.length){empty($("role-defaults-list"),"Роли ещё не загружены","Обновите данные, чтобы настроить модели команды.");return;}
    $("role-defaults-list").replaceChildren(...state.agents.map(agent=>{const row=node("fieldset","role-default-row");row.append(node("legend","",roleName(agent.name)));const grid=node("div","form-row"),model=node("input"),effort=node("select");model.id=`role-model-${agent.name}`;model.value=defaults[agent.name]?.model||"";model.placeholder="Общая модель по умолчанию";model.setAttribute("list","supported-models");model.autocomplete="off";model.spellcheck=false;model.setAttribute("aria-label",`Модель по умолчанию: ${roleName(agent.name)}`);effort.id=`role-effort-${agent.name}`;effort.value=defaults[agent.name]?.reasoning_effort||"";effort.setAttribute("aria-label",`Глубина анализа по умолчанию: ${roleName(agent.name)}`);updateEffortOptions(model.value,effort);effort.value=defaults[agent.name]?.reasoning_effort||"";const modelLabel=node("label","","Модель"),effortLabel=node("label","","Глубина анализа");modelLabel.append(model);effortLabel.append(effort);grid.append(modelLabel,effortLabel);row.append(grid);if(agent.model||agent.reasoning_effort)row.append(node("p","field-note",`У агента задано: ${agent.model?`модель ${agent.model}`:""}${agent.model&&agent.reasoning_effort?"; ":""}${agent.reasoning_effort?`глубина анализа: ${effortLabelText(agent.reasoning_effort)}`:""}. Эти индивидуальные значения имеют приоритет над соответствующим общим значением роли.`));model.addEventListener("input",()=>{state.roleDefaultsDirty=true;});model.addEventListener("change",()=>updateEffortOptions(model.value.trim(),effort));effort.addEventListener("change",()=>{state.roleDefaultsDirty=true;});state.roleDefaultInputs.set(agent.name,{model,effort});return row;}));
  }
  function validateModel(modelId,effort) {if(!state.modelsLoaded)return null;if(modelId&&!state.availableModels.some(m=>(m.model||m.id)===modelId))return "Выберите модель из официального списка или оставьте поле пустым.";const values=modelEffortOptions(modelId);if(effort&&values.length&&!values.includes(effort))return "Выбранная модель не поддерживает эту глубину анализа.";return null;}
  function summaryTotals(run) { if(run?.usage_total&&typeof run.usage_total==="object")return {input:run.usage_total.input??null,output:run.usage_total.output??null,cached:run.usage_total.cached??null,total:run.usage_total.total??null};if(typeof run?.usage_total==="number")return {input:null,output:null,cached:null,total:run.usage_total};return aggregateUsage(list(run?.usage)); }
  function loadedUsageTotals() { if(state.allUsage)return state.allUsage;const totals={input:null,output:null,cached:null,total:null};state.runs.forEach(run=>{Object.entries(summaryTotals(run)).forEach(([key,v])=>{if(typeof v==="number")totals[key]=(totals[key]??0)+v;});});return totals; }
  async function setOnboarding(dismissed) { $("onboarding").hidden=dismissed;storageSet("codex-team-onboarding",dismissed?"dismissed":"");if(state.online){try{const saved=await api("/api/settings","POST",{onboarding_dismissed:dismissed});if(state.status)state.status.settings=saved;}catch(error){toast("Начало работы сохранено локально. Серверные настройки временно недоступны.",true);}} }
  function renderDashboard() {
    const path=$("workspace").value.trim();$("dashboard-project").textContent=path?path.split(/[\\/]/).filter(Boolean).pop():"Не выбран";$("dashboard-project").title=path;
    const active=state.runs.find(r=>activeStates.has(normalizedState(r.state)));$("dashboard-active").textContent=active?`${roleName(active.current_role)} · ${stateLabels[normalizedState(active.state)]||active.state}`:"Нет активной задачи";
    $("dashboard-actions").textContent=state.actions.length;const total=loadedUsageTotals().total;$("dashboard-usage").textContent=total===null?"—":formatNumber.format(total);
    $("onboarding-codex").textContent=state.health?.checks?.codex===false?"Codex: требуется настройка":"Проверить Codex";$("onboarding-auth").textContent=authConnected()?"ChatGPT подключён ✓":"Подключить ChatGPT";
  }
  function acceptRuns(response) { state.runs=Array.isArray(response)?response:response.items||response.runs||[];state.runTotal=response.total??state.runs.length;state.allUsage=response.usage_total||null;renderRuns();renderDashboard(); }
  async function loadHistory(reset=false) {
    if(reset)state.historyPage=0;
    const version=++state.historyVersion,offset=state.historyPage*20;
    $("history-list").setAttribute("aria-busy","true");
    try { const p=new URLSearchParams({summary:"true",limit:"20",offset:String(offset),archived:String($("history-archived").checked),q:$("history-search").value.trim(),state:$("history-filter").value,project:$("history-project").value,mode:$("history-mode").value,date:$("history-date").value});const response=await api("/api/runs?"+p);if(version!==state.historyVersion)return;
      if(Array.isArray(response)){const query=$("history-search").value.trim().toLowerCase(),filter=$("history-filter").value;const rows=response.filter(r=>(!query||`${r.task} ${r.workspace} ${r.id}`.toLowerCase().includes(query))&&(!filter||normalizedState(r.state)===filter));state.historyTotal=rows.length;state.historyRows=rows.slice(offset,offset+20);}else{state.historyRows=response.items||response.runs||[];state.historyTotal=response.total??state.historyRows.length;}renderHistory();
    }catch(error){if(version===state.historyVersion)empty($("history-list"),"История временно недоступна",error.message);}finally{if(version===state.historyVersion)$("history-list").removeAttribute("aria-busy");}
  }
  function renderRunList() {
    const c=$("runs-list"),query=($("runs-search")?.value||"").trim().toLocaleLowerCase(),filter=$("runs-state-filter")?.value||"all";
    const attention=new Set(["FAILED","PAUSED","INTERRUPTED","USER_DECISION_REQUIRED","AUTH_REQUIRED","USAGE_LIMIT"]);
    const runs=state.runs.filter(run=>{
      const status=normalizedState(run.state);
      return (!query||[run.task,run.workspace,run.id].some(value=>String(value||"").toLocaleLowerCase().includes(query)))&&
        (filter==="all"||filter==="active"&&activeStates.has(status)||filter==="attention"&&attention.has(status)||filter==="finished"&&terminalStates.has(status));
    });
    if(!runs.length){empty(c,state.runs.length?"Нет подходящих запусков":"Пока нет запусков",state.runs.length?"Измените поиск или фильтр. В списке показаны загруженные запуски; полная история доступна в разделе «История».":"Создайте первую задачу на странице «Обзор».");return;}
    c.replaceChildren(...runs.map(run=>{const b=node("button","run-card");b.type="button";const d=node("div");d.append(node("strong","run-card-title",run.task),node("div","run-card-meta mono",run.worktree?.path||run.workspace));b.append(d,badge(run.state));b.addEventListener("click",()=>selectRun(run.id));return b;}));
  }
  function renderActivePipeline() {
    const run=state.selectedRun;if(!run)return;
    const attempts=MissionControl.attempts(run,state.stageEvents,state.eventsLoaded&&!state.eventsHasMore);
    if(state.selectedAttempt&&!attempts.some(a=>a.key===state.selectedAttempt)){
      const match=attempts.find(a=>a.role===state.selectedAttemptInfo?.role&&(state.selectedAttemptInfo?.resultNumber?a.resultNumber===state.selectedAttemptInfo.resultNumber:a.number===state.selectedAttemptInfo?.number));
      state.selectedAttempt=match?.key||null;
    }
    const signature=JSON.stringify([run.id,attempts,state.selectedAttempt]);
    const pipeline=$("active-pipeline");
    if(pipeline.dataset.signature!==signature){
      const focusedKey=Array.from(pipeline.children).find(li=>li.querySelector?.("button")===document.activeElement)?.dataset.key;
      pipeline.dataset.signature=signature;
      pipeline.replaceChildren(...attempts.map(attempt=>{
        const li=node("li","pipeline-step");li.dataset.key=attempt.key;
        const button=node("button","mission-stage");button.type="button";
        button.setAttribute("aria-pressed",String(state.selectedAttempt===attempt.key));
        const status=normalizedState(attempt.state);
        const indicatorClass=["PASS","APPROVED","IMPLEMENTED","PLAN","ANALYSIS","DONE","COMPLETED"].includes(status)?"good":["FAIL","FAILED","CHANGES_REQUIRED"].includes(status)?"failed":activeStates.has(status)?"working":["USER_DECISION_REQUIRED","AUTH_REQUIRED","USAGE_LIMIT","PAUSED","INTERRUPTED","STOPPED"].includes(status)?"attention":"waiting";
        const indicator=node("span",`mission-indicator ${indicatorClass}`,{good:"✓",failed:"×",working:"",attention:"!",waiting:"◷"}[indicatorClass]);indicator.setAttribute("aria-hidden","true");
        button.append(indicator,node("strong","",roleName(attempt.role)),badge(attempt.state));
        button.append(node("span","muted",attempt.historyOnly?`Сохранённый результат ${attempt.resultNumber}`:attempt.number?`Попытка ${attempt.number}${attempt.iteration?` · итерация ${attempt.iteration}`:""}`:attempt.call?`Вызов ${attempt.call} · время не загружено`:"Этап запланирован"));
        if(attempt.started)button.append(node("time","muted",`${prettyDate(attempt.started,true)}${attempt.ended?` → ${prettyDate(attempt.ended,true)}`:""}`));
        button.addEventListener("click",()=>{state.selectedRole=attempt.role;state.selectedAttempt=attempt.key;state.selectedAttemptInfo={role:attempt.role,number:attempt.number,resultNumber:attempt.resultNumber};setDetailTab("overview");renderActivePipeline();$("role-inspector").focus();});
        li.append(button);return li;
      }));
      if(focusedKey)Array.from(pipeline.children).find(li=>li.dataset.key===focusedKey)?.querySelector("button")?.focus();
    }
    $("mission-current-role").textContent=run.current_role?roleName(run.current_role):"Агент ещё не начал работу";
    const lastActivity=state.events.filter(e=>e.role===run.current_role).at(-1);
    $("mission-current-activity").textContent=state.eventsHasMore?"История загружена частично. Продолжение доступно во вкладке «Логи».":lastActivity?`${prettyDate(lastActivity.created_at,true)} · ${eventLabels[lastActivity.type]||lastActivity.type}${eventSummary(lastActivity.payload)?` · ${eventSummary(lastActivity.payload)}`:""}`:"Нет данных о последнем действии";
    $("mission-steer-button").hidden=terminalStates.has(normalizedState(run.state));
    $("mission-steer-button").disabled=state.controlPending||!state.online;
    const completed=attempts.filter(a=>a.result).length,required=state.actions.filter(a=>a.run_id===run.id).length;
    $("mission-summary").textContent=`Результатов попыток: ${completed} · требуется решений: ${required}${state.eventsHasMore?" · загружается история этапов":""}`;
    const requests=state.events.filter(e=>["pause_requested","stop_requested","run_state","resumed","recovered"].includes(e.type));
    const latest=requests.at(-1);
    if(activeStates.has(normalizedState(run.state))){
      if(latest?.type==="pause_requested")$("pause-button").disabled=true;
      if(latest?.type==="stop_requested")$("stop-button").disabled=true;
    }
    $("pause-button").textContent=latest?.type==="pause_requested"&&activeStates.has(normalizedState(run.state))?"Пауза запрошена":"Пауза";
    $("stop-button").textContent=latest?.type==="stop_requested"&&activeStates.has(normalizedState(run.state))?"Остановка запрошена":"Стоп";
    const elapsed=run.elapsed_seconds;$("detail-elapsed").textContent=typeof elapsed!=="number"?"Время: Нет данных":`Время: ${Math.floor(elapsed/60)} мин ${Math.floor(elapsed%60)} с`;$("detail-branch").textContent=`Ветка: ${run.worktree?.branch||run.branch||"не передана"}`; $("detail-worktree-path").textContent=text(run.worktree?.path||run.worktree?.workspace||run.worktree||run.workspace); const tokens=summaryTotals(run).total;$("detail-token-total").textContent=tokens===null?"—":formatNumber.format(tokens); const tests=Object.values(run.results||{}).flatMap(r=>list(r?.tests)),failed=tests.filter(t=>typeof t.exit_code==="number"&&t.exit_code!==0).length;$("detail-test-total").textContent=tests.length?`${tests.length} · ошибок: ${failed}`:"Пока нет результатов";$("detail-file-total").textContent=Array.isArray(run.changed_files)?run.changed_files.length:run.changed_files_count??"Нет данных";$("detail-task-text").textContent=run.task;$("detail-full-task").hidden=(run.task||"").length<150;$("open-worktree-button").hidden=typeof desktopBridge()?.open_worktree!=="function"||!run.worktree||Boolean(run.worktree_deleted);renderRunArtifacts(); }
  function renderRunProblem(run) {
    const c=$("run-error"),kind=normalizedState(run.error_info?.category||run.state);c.replaceChildren();c.hidden=!run.error&&!run.error_info;
    c.classList.toggle("error",!["USER_DECISION_REQUIRED","USER_ACTION_REQUIRED","AUTH_REQUIRED","PERMISSION_REQUIRED","CONFIGURATION_REQUIRED","USAGE_LIMIT","INTERRUPTED"].includes(kind));
    if(c.hidden)return;
    const titles={USER_DECISION_REQUIRED:"Команде нужно ваше решение",USER_ACTION_REQUIRED:"Требуется действие",AUTH_REQUIRED:"Подключите аккаунт ChatGPT",PERMISSION_REQUIRED:"Требуется разрешение",CONFIGURATION_REQUIRED:"Проекту нужна настройка",USAGE_LIMIT:"Доступный лимит Codex исчерпан",INTERRUPTED:"Запуск прерван",RECOVERABLE_ERROR:"Запуск не смог продолжиться",FAILED:"Запуск не смог продолжиться",FATAL_ERROR:"Выполнение остановлено"};
    c.append(node("strong","",titles[kind]||"Выполнение остановлено"),node("p","",kind==="USAGE_LIMIT"?"Проверьте время сброса лимита и продолжите запуск позже. Способ подключения выбирается отдельно в настройках.":kind==="INTERRUPTED"?"Сохранённые результаты доступны. Можно продолжить запуск с прерванного этапа.":kind==="AUTH_REQUIRED"?"Откройте настройки и войдите через официальный Codex.":"Проверьте запросы в центре действий и результат текущей роли. Добавьте указание, если команде нужен контекст."));
    const row=node("div","button-row");row.append(actionButton("Центр действий →",()=>setPage("actions")),actionButton("Копировать диагностику",copyDiagnostics));if(kind==="AUTH_REQUIRED")row.append(actionButton("Открыть настройки",()=>setPage("settings")));c.append(row);
    const details=node("details","raw-details");details.append(node("summary","","Технические подробности"),node("pre","code-block",text(run.error_info?.message||run.error)));c.append(details);
  }
  async function confirmOperation(title,description,scope="",accept="Подтвердить") { const dialog=$("confirm-dialog");if(typeof dialog.showModal!=="function")return window.confirm(`${title}\n\n${description}\n\n${scope}`);$("confirm-title").textContent=title;$("confirm-description").textContent=description;$("confirm-scope").textContent=scope;$("confirm-scope").hidden=!scope;$("confirm-accept").textContent=accept;dialog.returnValue="cancel";return new Promise(resolve=>{dialog.addEventListener("close",()=>resolve(dialog.returnValue==="confirm"),{once:true});dialog.showModal();$("confirm-cancel").focus();}); }
  async function loadActions() { if(state.actionsLoading)return;state.actionsLoading=true;try{const response=await api("/api/actions?status=pending");state.actions=Array.isArray(response)?response:response.items||response.actions||[];state.actionsError=null;renderActions();}catch(error){state.actionsError=error.status===404?"Центр действий недоступен в этой версии сервера.":error.message;renderActions();}finally{state.actionsLoading=false;} }
  function syncActionCards(container,actions,where) {
    const existing=new Map(Array.from(container.children).filter(el=>el.dataset.actionId).map(el=>[el.dataset.actionId,el]));
    const ids=new Set(actions.map(a=>a.id));
    for(const [id,card] of existing)if(!ids.has(id))card.remove();
    if(!existing.size)container.replaceChildren();
    for(const action of actions){
      const signature=JSON.stringify(action),old=existing.get(action.id);
      if(old?.dataset.signature===signature)continue;
      const card=renderActionCard(action,where);card.dataset.actionId=action.id;card.dataset.signature=signature;
      if(old)old.remove();container.append(card);
    }
  }
  function renderActions() {
    $("actions-count").textContent=state.actions.length;$("actions-count").hidden=!state.actions.length;renderDashboard();if(state.selectedRun)renderActivePipeline();
    const signature=JSON.stringify([state.actions,state.actionsError,state.selectedRun?.id]);if(signature===state.actionsSignature)return;state.actionsSignature=signature;
    const c=$("actions-list");if(state.actionsError)empty(c,"Запросы временно недоступны",state.actionsError);else if(!state.actions.length)empty(c,"Сейчас ваше действие не требуется","Когда команде понадобится разрешение или решение, запрос появится здесь.");else syncActionCards(c,state.actions,"center");
    const relevant=state.actions.filter(a=>a.run_id===state.selectedRun?.id);$("run-actions").hidden=!relevant.length;syncActionCards($("run-actions"),relevant,"run");
  }
  function renderActionCard(action,where) {
    const card=node("article","action-card"),heading=node("div","action-header");heading.append(node("h3","",action.kind==="permission"?`${roleName(action.role)}: требуется разрешение`:`${roleName(action.role)}: нужно решение`),node("span","state-badge state-warning","ТРЕБУЕТСЯ ДЕЙСТВИЕ"));card.append(heading,node("p","action-reason",action.reason||action.title));
    if(action.command)card.append(node("pre","code-block",text(action.command)));
    const meta=node("div","action-meta");for(const [label,value]of [["Рабочая папка",action.cwd],["Область действия",scopeLabel(action.scope)],["Риск",{low:"Низкий",medium:"Средний",high:"Высокий"}[action.risk]||action.risk]])if(value)meta.append(node("div","",`${label}: ${text(value)}`));card.append(meta);
    if(action.limitation)card.append(node("p","limitation",action.limitation));
    const allowed=new Set(action.allowed_decisions||[]),form=node("form"),questions=list(action.questions),hasSecret=questions.some(q=>q.isSecret),inputs=[];
    questions.forEach((question,index)=>{const field=node("fieldset","action-question"),legend=node("legend","",question.question||question.header||"Вопрос");field.append(legend);if(question.isSecret){field.append(node("p","muted","Секреты вводятся только в настройках подключения или в официальном окне входа."));form.append(field);return;}
      const name=`${where}-${action.id}-q${index}`,options=list(question.options);const group={question,radios:[],other:null};options.forEach(option=>{const label=node("label","answer-option"),radio=node("input");radio.type="radio";radio.name=name;radio.value=option.label;radio.required=true;const content=node("span","",option.label);if(option.description)content.append(node("small","",option.description));label.append(radio,content);field.append(label);group.radios.push(radio);});
      if(question.isOther||!options.length){const input=node("textarea");input.rows=2;input.maxLength=10000;input.setAttribute("aria-label",`${question.header||"Вопрос"}: свой ответ`);if(options.length){const l=node("label","answer-option"),radio=node("input");radio.type="radio";radio.name=name;radio.value="__other__";radio.required=true;l.append(radio,document.createTextNode("Свой ответ"));field.append(l);group.radios.push(radio);}else input.required=true;field.append(input);group.other=input;}inputs.push(group);form.append(field);});
    const actions=node("div","button-row");
    let productInstruction=null,budgetEnabled=null,budgetInputs=null;
    if(action.kind==="product"&&allowed.has("resume")){
      const run=state.selectedRun?.id===action.run_id?state.selectedRun:state.runs.find(r=>r.id===action.run_id),current=run||action.details?.run||{};
      const note=node("p","muted",`Уже использовано — итерации: ${current.iteration??"—"}; вызовы: ${current.calls??"—"}; время: ${current.elapsed_seconds===undefined?"—":Math.floor(current.elapsed_seconds)} с.`);form.append(note);
      const label=node("label","check-label");budgetEnabled=node("input");budgetEnabled.type="checkbox";label.append(budgetEnabled,node("span","","Изменить общие лимиты перед продолжением"));form.append(label);
      const field=node("fieldset","action-budget");field.hidden=true;field.append(node("legend","","Общие лимиты этого запуска"),node("p","field-note","Это новые общие пределы, включая уже использованные ресурсы. Значения не добавляются к прежнему бюджету. Увеличение может привести к дополнительным вызовам выбранного сервиса выполнения."));budgetInputs={};
      const grid=node("div","form-row");for(const [key,title,min,max,fallback]of [["max_iterations","Итерации",1,10,3],["max_agent_calls","Вызовы агентов",1,100,15],["max_run_duration","Время, секунды",30,86400,1800]]){const wrap=node("label","",title),input=node("input");input.type="number";input.min=String(min);input.max=String(max);input.step="1";input.value=String(current[key]??state.status?.settings?.[key]??fallback);input.required=true;input.disabled=true;input.setAttribute("aria-label",`Общий лимит: ${title.toLowerCase()}`);wrap.append(input);grid.append(wrap);budgetInputs[key]=input;}field.append(grid);form.append(field);
      budgetEnabled.addEventListener("change",()=>{field.hidden=!budgetEnabled.checked;Object.values(budgetInputs).forEach(i=>i.disabled=!budgetEnabled.checked);});
      productInstruction=node("textarea");productInstruction.rows=2;productInstruction.maxLength=10000;productInstruction.placeholder="Необязательное указание для продолжения или объяснения";productInstruction.setAttribute("aria-label","Указание для продолжения");form.append(productInstruction);
    }
    if(allowed.has("answer")&&!hasSecret&&questions.length){const submit=node("button","button primary","Отправить ответ");submit.type="submit";actions.append(submit);form.addEventListener("submit",event=>{event.preventDefault();if(!form.reportValidity())return;const answers={};for(const group of inputs){const value=group.radios.find(r=>r.checked)?.value;const answer=value&&value!=="__other__"?value:group.other?.value.trim();if(!answer){group.other?.focus();toast("Ответьте на каждый вопрос.",true);return;}answers[group.question.id]=[answer];}resolveAction(action,"answer",answers,null,card);});}
    if(allowed.has("answer")&&!questions.length){list(action.choices).forEach(choice=>actions.append(actionButton(choice.label,()=>resolveAction(action,"answer",{},choice.id||choice.label,card),"primary")));const instruction=node("textarea");instruction.rows=2;instruction.maxLength=10000;instruction.placeholder="Ваше решение или дополнительное указание";instruction.setAttribute("aria-label","Указание для решения");form.append(instruction);actions.append(actionButton("Отправить решение",()=>{if(instruction.value.trim())resolveAction(action,"answer",{},instruction.value.trim(),card);else{instruction.focus();toast("Напишите решение.",true);}},"primary"));}
    for(const decision of ["allow_once","allow_run","deny","cancel","explain","resume","stop"]){if(!allowed.has(decision))continue;actions.append(actionButton(decisionLabels[decision],()=>{let budget=null;if(decision==="resume"&&budgetEnabled?.checked){if(!form.reportValidity())return;budget=Object.fromEntries(Object.entries(budgetInputs).map(([key,input])=>[key,Number(input.value)]));}return resolveAction(action,decision,{},productInstruction?.value.trim()||null,card,budget);},["allow_once","resume"].includes(decision)?"primary":["deny","stop"].includes(decision)?"danger":"secondary"));}
    if(hasSecret)actions.append(actionButton("Открыть настройки",()=>setPage("settings")));
    actions.append(actionButton("Открыть запуск",()=>selectRun(action.run_id),"text-button"));form.append(actions);card.append(form);
    const details=node("details","raw-details");details.append(node("summary","","Подробности запроса"),node("pre","code-block",text(action.details||{})));card.append(details);return card;
  }
  async function resolveAction(action,decision,answers={},instruction=null,card,budget=null) {
    if(state.pendingActions.has(action.id))return;state.pendingActions.add(action.id);state.runRevision++;
    const selection=state.selectionVersion;
    let confirmed=false;if(["allow_once","allow_run"].includes(decision)&&action.requires_confirmation){confirmed=await confirmOperation("Подтвердите запрошенное разрешение","Проверьте команду, рабочую папку и область действия разрешения. Разрешение относится только к этому запросу официальной сессии Codex.",[action.command,action.cwd,action.scope,action.limitation].filter(Boolean).map(text).join("\n"),decisionLabels[decision]);if(!confirmed){state.pendingActions.delete(action.id);return;}}
    const buttons=Array.from(card?.querySelectorAll("button")||[]);buttons.forEach(b=>b.disabled=true);
    try{await api(`/api/actions/${encodeURIComponent(action.id)}/resolve`,"POST",{decision,answers,...(instruction?{instruction}:{}),...(decision==="resume"&&budget?{budget}:{}),confirmed});state.runRevision++;toast("Решение передано. Состояние команды обновляется.");state.actionsSignature="";await loadActions();if(state.selectedRun?.id===action.run_id){const run=await api(`/api/runs/${encodeURIComponent(action.run_id)}`);if(selection===state.selectionVersion&&state.selectedRun?.id===action.run_id){state.selectedRun=run;renderRun();}}}
    catch(error){toast(error.message,true);}finally{state.pendingActions.delete(action.id);buttons.forEach(b=>b.disabled=false);}
  }
  function renderRunArtifacts() {
    const run=state.selectedRun,finished=run&&["DONE","COMPLETED","STOPPED","FAILED","INTERRUPTED"].includes(normalizedState(run.state));
    const labels=[run?.archived?"Архивный запуск":null,run?.worktree_deleted?"Рабочая копия удалена; путь сохранён в истории":null].filter(Boolean);$("detail-record-state").hidden=!labels.length;$("detail-record-state").textContent=labels.join(" · ");
    if(run?.worktree_deleted)$("detail-isolation").textContent="Удалена";
    $("archive-run-button").hidden=!finished||Boolean(run?.archived);$("delete-worktree-button").hidden=!finished||!run?.worktree||Boolean(run?.worktree_deleted);
    $("run-artifact-controls").hidden=$("archive-run-button").hidden&&$("delete-worktree-button").hidden;
  }
  async function manageRunArtifact(kind) {
    const run=state.selectedRun;if(!run)return;
    const removing=kind==="worktree",scope=removing?text(run.worktree?.path||run.worktree?.workspace||run.worktree):run.id;
    if(!await confirmOperation(removing?"Удалить чистую рабочую копию?":"Архивировать запуск?",removing?"Сервер проверит, что запуск не активен и в рабочей копии нет изменений. Будет удалена только изолированная рабочая копия. История и результаты сохранятся. Продолжить работу в удалённой копии нельзя.":"Запуск будет отмечен как архивный. Результаты, события и файлы рабочей копии сохранятся.",scope,removing?"Удалить рабочую копию":"Архивировать"))return;
    const button=$(removing?"delete-worktree-button":"archive-run-button");button.disabled=true;
    try{await api(`/api/runs/${encodeURIComponent(run.id)}/${kind}`,removing?"DELETE":"POST",removing?{confirmed:true}:{});toast(removing?"Рабочая копия удалена. История сохранена.":"Запуск архивирован. Результаты сохранены.");await refresh();}
    catch(error){toast(error.message,true);}finally{button.disabled=false;}
  }
  async function loadProjects() { try{const response=await api("/api/projects");state.projects=Array.isArray(response)?response:response.items||response.projects||[];state.projectsError=null;const selected=$("history-project").value,all=node("option","","Все проекты");all.value="";$("history-project").replaceChildren(all,...state.projects.map(p=>{const o=node("option","",p.name||p.path);o.value=p.path;return o;}));$("history-project").value=selected;renderProjects();renderProjectPreflight();}catch(error){state.projectsError=error.status===404?"Управление проектами недоступно в этой версии сервера.":error.message;renderProjects();} }
  function renderProjects() {
    const c=$("projects-list");if(state.projectsError){empty(c,"Проекты временно недоступны",state.projectsError);return;}if(!state.projects.length){empty(c,"Добавьте свой первый проект","Выберите локальный Git-репозиторий. Его файлы останутся на месте.");return;}
    c.replaceChildren(...state.projects.map(project=>{
      const card=node("article","panel project-card");card.append(node("h3","",project.name||project.path?.split(/[\\/]/).pop()),node("p","project-path mono muted",project.path));
      const meta=node("div","project-meta");meta.append(node("span","state-badge",`Ветка: ${project.branch||"—"}`),node("span",`state-badge ${project.error||project.dirty?"state-warning":"state-good"}`,project.error?"Нужна проверка":project.dirty?"Есть изменения":"Чистый Git"));
      if(project.memory_status)meta.append(node("span","state-badge",`Память: ${{available:"Есть",empty:"Пока нет"}[project.memory_status]||text(project.memory_status)}`));card.append(meta);
      const runtime=project.runtime_status;if(runtime)card.append(node("p","project-runtime",typeof runtime==="object"?(runtime.ready?"Среда выполнения доступна":`Проекту нужна среда: ${(runtime.missing||[]).join(", ")||"см. подробности"}`):text(runtime)));
      if(project.error)card.append(node("p","project-runtime","Не удалось проверить папку. Убедитесь, что проект доступен, затем обновите данные."));else if(project.ready===false&&!project.dirty)card.append(node("p","project-runtime","Для изолированного запуска нужен первый Git commit в проекте."));
      if(runtime?.missing?.length)card.append(node("p","field-note","Приложение обнаруживает доступные среды автоматически. После настройки среды обновите проект. Если доступный runtime не найден, экспортируйте диагностику из настроек."));
      const row=node("div","project-actions");row.append(actionButton("Выбрать проект",()=>useProject(project),"primary"),actionButton("Настроить команды",()=>openProjectEditor(project)));
      if(project.dirty)row.append(actionButton("Посмотреть изменения",()=>openProjectDiff(project)));
      if(project.last_run)row.append(actionButton("Последний запуск",()=>selectRun(typeof project.last_run==="string"?project.last_run:project.last_run.id)));
      if(typeof desktopBridge()?.open_project==="function")row.append(actionButton("Открыть папку ↗",()=>nativeOperation("open_project",project.id)));
      row.append(actionButton("Убрать из списка",async()=>{if(await confirmOperation("Убрать проект из списка?","Файлы проекта, Git-история и сохранённые запуски останутся на компьютере.",project.path,"Убрать из списка")){try{await api(`/api/projects/${encodeURIComponent(project.id)}`,"DELETE",{});await loadProjects();}catch(e){toast(e.message,true);}}},"text-button"));card.append(row);
      if(project.changed_files?.length||runtime||project.error){const d=node("details","raw-details");d.append(node("summary","","Состояние проекта"));if(project.changed_files?.length)d.append(node("pre","code-block",text(project.changed_files)));if(runtime)d.append(node("pre","code-block",text(runtime)));if(project.error)d.append(node("pre","code-block",text(project.error)));card.append(d);}return card;
    }));
  }
  async function openProjectDiff(project) {
    setPage("projects");const version=state.projectDiffVersion=(state.projectDiffVersion||0)+1;$("project-diff-panel").hidden=false;$("project-diff-title").textContent=`Изменения: ${project.name||project.path}`;$("project-diff-body").replaceChildren(node("p","loading-state","Читаем изменения исходного проекта…"));$("project-diff-panel").scrollIntoView({block:"start"});
    try{const response=await api(`/api/projects/${encodeURIComponent(project.id)}/diff`);if(version!==state.projectDiffVersion)return;const lines=(response.diff||"").split("\n"),chunk=node("pre","code-block diff-block",lines.slice(0,1000).join("\n"));$("project-diff-body").replaceChildren(node("p","muted","Просмотр не изменяет файлы. Для изолированного запуска сохраните или отмените изменения в своём Git-инструменте."),node("pre","code-block",response.diff_stat||""),chunk);if(!response.diff)chunk.textContent="Текстовых изменений нет.";if(lines.length>1000){let limit=1000;const more=actionButton("Показать ещё 1000 строк",()=>{limit+=1000;chunk.textContent=lines.slice(0,limit).join("\n");more.hidden=limit>=lines.length;});$("project-diff-body").append(more);}}
    catch(error){if(version===state.projectDiffVersion)empty($("project-diff-body"),"Не удалось прочитать изменения",error.message);}
  }
  function useProject(project) { $("workspace").value=project.path;storageSet("codex-team-workspace",project.path);renderProjectPreflight();renderDashboard();setPage("workbench");$("task").focus(); }
  function renderProjectPreflight() { const project=state.projects.find(p=>p.path?.toLowerCase()===$("workspace").value.trim().toLowerCase()),c=$("project-preflight");c.replaceChildren();c.hidden=!project?.dirty&&!project?.runtime_status?.missing?.length;if(c.hidden)return;if(project.dirty){c.append(node("strong","","В проекте есть несохранённые Git-изменения"),node("p","","Изолированная рабочая копия требует чистого репозитория. Сохраните или отмените изменения в своём Git-инструменте, затем обновите проект."));const d=node("details","raw-details");d.append(node("summary","","Изменённые файлы"),node("pre","code-block",text(project.changed_files||[])));c.append(d);}if(project.runtime_status?.missing?.length)c.append(node("p","",`Проекту нужна среда: ${project.runtime_status.missing.join(", ")}. Откройте состояние проекта и рекомендации настройки.`));const row=node("div","button-row");row.append(actionButton("Состояние проекта",()=>setPage("projects")),actionButton("Обновить",loadProjects));if(project.dirty)row.append(actionButton("Посмотреть изменения",()=>openProjectDiff(project)));c.append(row); }
  async function addProject(path) { const project=await api("/api/projects","POST",{path});await loadProjects();return project; }
  function openProjectEditor(project) {state.editingProject=project.id;$("project-editor-title").textContent=`Команды: ${project.name||project.path}`;for(const [kind,id]of [["test","project-test-command"],["build","project-build-command"],["run","project-run-command"]])$(id).value=JSON.stringify(project.commands?.[kind]||project.config?.commands?.[kind]||[]);$("project-editor").hidden=false;$("project-test-command").focus();}
  async function nativeOperation(method,id) { const bridge=desktopBridge();if(typeof bridge?.[method]!=="function")return;try{const result=await bridge[method](...(id===undefined?[]:[id]));if(result?.error||result?.ok===false)throw new Error(result.error||"Действие недоступно.");if(result?.path&&method==="export_diagnostics")toast(`Диагностика сохранена: ${result.path}`);}catch(error){toast(error.message,true);} }
  function exportJSON(filename,data) { const blob=new Blob([JSON.stringify(data,null,2)],{type:"application/json"}),url=URL.createObjectURL(blob),a=node("a");a.href=url;a.download=filename;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000); }
  function agentPayload(agent) { const {name,role,instructions,permission,model,reasoning_effort,enabled,description,enabled_modes,can_execute,can_network}=agent;return {name,role,instructions,permission,model:model||null,reasoning_effort:reasoning_effort||null,enabled:enabled!==false,description:description||"",enabled_modes:enabled_modes||Object.keys(modes),can_execute:can_execute!==false,can_network:can_network===true}; }
  function packPayload(pack) { return {name:pack.name,title:pack.title||pack.name,description:pack.description||"",default_mode:pack.default_mode||"standard",agents:pack.agents||[],specialists:pack.specialists||[]}; }
  function syncPackModeChoices() {
    const mode=$("pack-mode").value,required=new Set(modes[mode].pipeline.filter(name=>name!=="specialists"));
    qa("#pack-agent-options input").forEach(input=>{const incompatible=input.value==="developer"&&!required.has("developer");if(required.has(input.value))input.checked=true;if(incompatible)input.checked=false;input.disabled=required.has(input.value)||incompatible;input.title=required.has(input.value)?"Обязательная роль выбранного режима":incompatible?"Этот режим допускает только роли для чтения":"";});
  }
  function validatePack(request) {
    const required=modes[request.default_mode].pipeline.filter(name=>name!=="specialists"),missing=required.filter(name=>!request.agents.includes(name));if(missing.length)return `Выбранному режиму нужны роли: ${missing.map(roleName).join(", ")}.`;
    for(const name of [...request.agents,...request.specialists]){const agent=state.agents.find(a=>a.name===name);if(!agent||agent.enabled===false)return `Включите роль «${roleName(name)}» на странице «Агенты» перед сохранением набора.`;if(agent.enabled_modes&&!agent.enabled_modes.includes(request.default_mode))return `Разрешите режим «${modes[request.default_mode].title}» у роли «${roleName(name)}» на странице «Агенты».`;}
    return null;
  }
  function composerPipeline() {
    const mode=$("run-mode").value,base=modes[mode].pipeline.filter(name=>name!=="specialists"),pack=state.packs.find(p=>p.name===$("run-pack").value);
    for(const name of pack?.agents||[])if(!base.includes(name))base.splice(base.includes("developer")?base.indexOf("developer"):2,0,name);
    if(["deep","audit"].includes(mode)){const extras=[...new Set([...(pack?.specialists||[]),...qa("#specialist-options input:checked").map(i=>i.value)])];base.splice(2,0,...extras);}return base;
  }
  function validateComposerPack() {
    const mode=$("run-mode").value,pack=state.packs.find(p=>p.name===$("run-pack").value);if(!pack)return "Выберите существующий набор агентов.";
    const base=modes[mode].pipeline.filter(name=>name!=="specialists"),agents=pack.agents?.length?pack.agents:base;
    if(!base.includes("developer")&&agents.includes("developer"))return "Этот режим допускает только чтение. Выберите набор без роли разработчика или другой режим.";
    return validatePack({default_mode:mode,agents,specialists:["deep","audit"].includes(mode)?[...(pack.specialists||[]),...qa("#specialist-options input:checked").map(i=>i.value)]:[]});
  }
  async function deleteRegistry(kind,item) { if(!await confirmOperation(`Удалить ${kind==="agents"?"агента":"набор"}?`,"Сохранённые результаты прошлых запусков останутся в истории.",item.name,"Удалить"))return;try{await api(`/api/${kind}/${encodeURIComponent(item.name)}`,"DELETE",{});state.agentsSignature="";await reloadRegistry();toast("Удалено.");}catch(error){toast(error.message,true);} }
  async function reloadRegistry() { const responses=await Promise.all([api("/api/agents"),api("/api/packs")]);state.agents=Array.isArray(responses[0])?responses[0]:responses[0].agents||[];state.packs=Array.isArray(responses[1])?responses[1]:responses[1].packs||[];state.agentsSignature="";renderRegistry(); }
  function renderPacks() { const c=$("packs-list");if(!state.packs.length){empty(c,"Наборы пока не загружены","Используйте встроенный набор или создайте собственный.");return;}c.replaceChildren(...state.packs.filter(pack=>{const q=$("packs-search").value.trim().toLowerCase();return !q||`${pack.name} ${pack.title||""} ${pack.description||""}`.toLowerCase().includes(q);}).map(pack=>{const card=node("article","panel pack-card");card.append(node("h3","",pack.title||pack.name),node("p","role-id mono muted",pack.name),node("p","agent-instructions-preview",pack.description||"Описание не задано"));card.append(node("p","muted",`Режим: ${modes[pack.default_mode||"standard"]?.title||pack.default_mode} · Специалисты: ${(pack.specialists||[]).length}`));const row=node("div","registry-actions");row.append(actionButton("Изменить",()=>openPackEditor(pack)),actionButton("Дублировать",()=>openPackEditor({...pack,name:"",title:`${pack.title||pack.name} · копия`,builtin:false},true)),actionButton("Экспорт",()=>exportJSON(`${pack.name}.pack.json`,packPayload(pack))));if(!pack.builtin)row.append(actionButton("Удалить",()=>deleteRegistry("packs",pack),"danger"));card.append(row);return card;})); }
  function openPackEditor(pack,duplicate=false) {state.editingPack=pack?.name&&!duplicate?pack.name:null;$("pack-editor-title").textContent=state.editingPack?`Набор: ${pack.title||pack.name}`:"Новый набор";$("pack-name").value=pack?.name||"";$("pack-name").readOnly=Boolean(state.editingPack);$("pack-title").value=pack?.title||"";$("pack-description").value=pack?.description||"";$("pack-mode").value=pack?.default_mode||"standard";const choices=(container,filter,selected)=>{container.replaceChildren(...state.agents.filter(filter).map(agent=>{const l=node("label","specialist-option"),i=node("input");i.type="checkbox";i.value=agent.name;i.checked=selected.includes(agent.name);l.append(i,document.createTextNode(roleName(agent.name)));return l;}));};choices($("pack-agent-options"),a=>a.name==="developer"||a.permission==="read-only",pack?.agents?.length?pack.agents:(modes[pack?.default_mode||"standard"].pipeline.filter(id=>id!=="specialists")));choices($("pack-specialist-options"),a=>!standardRoles.has(a.name)&&a.permission==="read-only",pack?.specialists||[]);syncPackModeChoices();$("pack-editor").hidden=false;showFormError("pack-form-error","");$("pack-name").focus();}
  async function importRegistry(kind,file) { if(!file)return;try{if(file.size>1024*1024)throw new Error("JSON-файл должен быть не больше 1 МБ.");const data=JSON.parse(await file.text());if(!data||Array.isArray(data)||typeof data!=="object")throw new Error("Ожидается один JSON-объект.");if(kind==="agents")openAgentEditor({...agentPayload(data),name:""});else openPackEditor({...packPayload(data),name:""},true);toast("Файл загружен в редактор. Проверьте поля и задайте уникальный идентификатор перед сохранением.");}catch(error){toast(`Не удалось импортировать: ${error.message}`,true);} }
  async function loadProviders() {try{state.providers=await api("/api/providers");renderProviders();renderConnection();}catch(error){$("api-key-status").textContent=error.status===404?"Подключение через API недоступно в этой версии сервера.":"Сведения о подключении временно недоступны.";} }
  function renderProviders() {const p=state.providers;if(!p)return;$("provider-active-label").textContent=p.active==="openai_api"?"OPENAI API · ОТДЕЛЬНАЯ ОПЛАТА":"CODEX / CHATGPT";const labels={CONNECTED:"Подключён",CONFIGURED:"Ключ сохранён","NOT CONFIGURED":"Не настроен",ERROR:"Ошибка подключения",AUTH_REQUIRED:"Нужен вход",UNAVAILABLE:"Недоступен"};$("codex-provider-status").textContent=labels[p.codex?.status]||p.codex?.status||"Недоступен";$("api-provider-status").textContent=labels[p.openai_api?.status]||p.openai_api?.status||"Не настроен";$("api-key-status").textContent=p.openai_api?.configured?`Ключ сохранён: ${p.openai_api.key_hint||"••••••••"}${p.openai_api.tested_at?` · Проверка: ${prettyDate(p.openai_api.tested_at)}`:" · Подключение ещё не проверено"}`:"Ключ не настроен";$("test-api-key").disabled=!p.openai_api?.configured;$("remove-api-key").disabled=!p.openai_api?.configured;if(!state.providerTouched)qa('input[name="provider"]').forEach(r=>r.checked=r.value===p.active);renderProviderChoice();if(p.openai_api?.error)showFormError("api-key-error",errorMessage({detail:p.openai_api.error},"Не удалось проверить подключение к API. Проверьте ключ и доступ к сети."));}
  function renderProviderChoice() {const apiSelected=qa('input[name="provider"]').some(r=>r.checked&&r.value==="openai_api");$("provider-billing-note").hidden=!apiSelected;$("save-provider-button").disabled=!state.online||(apiSelected&&!$("provider-billing-confirmed").checked);}
  async function copyDiagnostics() { const data={app:"Codex Team",version:state.health?.version||"unknown",server:state.health?.status||"unavailable",auth:state.status?.auth?.status||"unavailable",provider:state.providers?.active||state.status?.settings?.execution_backend||"codex_chatgpt",run:state.selectedRun?{id:state.selectedRun.id,state:state.selectedRun.state,role:state.selectedRun.current_role}:null};try{await navigator.clipboard.writeText(JSON.stringify(data,null,2));toast("Диагностика скопирована. Секреты и текст задачи не включены.");}catch(_){toast("Буфер обмена недоступен. Используйте экспорт диагностики или папку журналов.",true);} }
  async function loadRecovery() {if(typeof desktopBridge()?.recovery_status!=="function")return;try{const r=await desktopBridge().recovery_status();$("recovery-banner").hidden=!r?.abnormal;if(r?.message)$("recovery-message").textContent=r.message;}catch(_){/* optional native status */} }
  async function savePartialSettings(values,errorId) {try{const saved=await api("/api/settings","POST",values);if(state.status)state.status.settings=saved;showFormError(errorId,"");toast("Настройки сохранены.");return saved;}catch(error){showFormError(errorId,error.message);return null;} }
  function bindFeatures() {
    document.querySelector(".skip-link")?.addEventListener("click",event=>{event.preventDefault();$("main").focus();});
    $("agents-search").addEventListener("input",()=>{state.agentsSignature="";renderRegistry();});$("packs-search").addEventListener("input",renderPacks);
    $("role-defaults-form").addEventListener("submit",async event=>{event.preventDefault();const defaults={...(state.status?.settings?.role_model_defaults||{})};for(const [name,{model,effort}]of state.roleDefaultInputs||[]){const modelId=model.value.trim(),reasoning=effort.value||null,error=validateModel(modelId,reasoning);if(error){showFormError("role-defaults-error",`${roleName(name)}: ${error}`);model.focus();return;}if(modelId||reasoning)defaults[name]={model:modelId||null,reasoning_effort:reasoning};else delete defaults[name];}$("save-role-defaults-button").disabled=true;try{const saved=await savePartialSettings({role_model_defaults:defaults},"role-defaults-error");if(saved){state.roleDefaultsDirty=false;renderRoleModelDefaults();}}finally{$("save-role-defaults-button").disabled=false;}});
    $("agent-model").addEventListener("change",()=>updateEffortOptions($("agent-model").value.trim(),"agent-reasoning"));$("settings-model").addEventListener("change",()=>updateEffortOptions($("settings-model").value.trim(),"settings-reasoning"));
    $("workspace").addEventListener("input",()=>{renderDashboard();renderProjectPreflight();});
    qa("[data-preset]").forEach(b=>b.addEventListener("click",()=>{const preset={fast:{mode:"quick",iterations:1,calls:6,duration:15},balanced:{mode:"standard",iterations:3,calls:15,duration:30},thorough:{mode:"deep",iterations:5,calls:30,duration:60}}[b.dataset.preset];$("run-mode").value=preset.mode;$("max-iterations").value=preset.iterations;$("max-calls").value=preset.calls;$("max-duration").value=preset.duration;qa("[data-preset]").forEach(item=>{const active=item===b;item.classList.toggle("active",active);item.setAttribute("aria-pressed",String(active));});renderPreview();}));
    $("run-pack").addEventListener("change",()=>{const pack=state.packs.find(p=>p.name===$("run-pack").value);if(pack?.default_mode){$("run-mode").value=pack.default_mode;renderPreview();}});
    $("open-diff-button").addEventListener("click",()=>{setDetailTab("diff");$("detail-diff").scrollIntoView({block:"nearest"});});$("more-diff-button").addEventListener("click",()=>{state.diffLimit+=1000;if(state.diffHasMore&&state.diffLimit>state.diffLines.length)loadDiff(true);else renderDiff();});$("more-events-button").addEventListener("click",()=>{if(state.selectedRun)return fetchEvents(state.selectedRun.id,state.selectionVersion);});
    $("mission-steer-button").addEventListener("click",()=>{$("steer-form").scrollIntoView({block:"nearest"});$("steer-instruction").focus();});
    $("mission-logs-button").addEventListener("click",()=>{setDetailTab("activity");$("detail-activity").scrollIntoView({block:"nearest"});$("tab-activity").focus();});
    $("event-filter").addEventListener("change",()=>{state.eventFilter=$("event-filter").value;renderEvents();});
    $("open-worktree-button").addEventListener("click",()=>nativeOperation("open_worktree",state.selectedRun?.id));$("refresh-actions-button").addEventListener("click",loadActions);
    $("archive-run-button").addEventListener("click",()=>manageRunArtifact("archive"));$("delete-worktree-button").addEventListener("click",()=>manageRunArtifact("worktree"));
    $("history-prev").addEventListener("click",()=>{state.historyPage=Math.max(0,state.historyPage-1);loadHistory();});$("history-next").addEventListener("click",()=>{state.historyPage++;loadHistory();});
    for(const id of ["history-project","history-mode","history-date","history-archived"])$(id).addEventListener("change",()=>loadHistory(true));
    $("dismiss-onboarding").addEventListener("click",()=>setOnboarding(true));$("show-onboarding-button").addEventListener("click",()=>{setOnboarding(false);setPage("workbench");});
    $("dismiss-recovery").addEventListener("click",async()=>{await nativeOperation("dismiss_recovery");$("recovery-banner").hidden=true;});
    $("project-browse-button").addEventListener("click",async()=>{await chooseProject();$("project-path").value=$("workspace").value;});$("project-form").addEventListener("submit",async event=>{event.preventDefault();if(!$("project-form").reportValidity())return;$("project-add-button").disabled=true;showFormError("project-form-error","");try{await addProject($("project-path").value.trim());$("project-path").value="";toast("Проект добавлен.");}catch(error){showFormError("project-form-error",error);}finally{$("project-add-button").disabled=false;}});$("close-project-editor").addEventListener("click",()=>$("project-editor").hidden=true);$("close-project-diff").addEventListener("click",()=>{$("project-diff-panel").hidden=true;state.projectDiffVersion=(state.projectDiffVersion||0)+1;});
    $("project-commands-form").addEventListener("submit",async event=>{event.preventDefault();try{const commands={};for(const [kind,id]of [["test","project-test-command"],["build","project-build-command"],["run","project-run-command"]]){const value=JSON.parse($(id).value.trim()||"[]");if(!Array.isArray(value)||value.some(v=>typeof v!=="string"))throw new Error("Каждая команда должна быть JSON-массивом строк.");commands[kind]=value;}await api(`/api/projects/${encodeURIComponent(state.editingProject)}`,"PUT",{commands});$("project-editor").hidden=true;await loadProjects();toast("Команды сохранены. Выполнение не запускалось.");}catch(error){showFormError("project-commands-error",error);}});
    $("add-pack-button").addEventListener("click",()=>openPackEditor());$("close-pack-editor").addEventListener("click",()=>$("pack-editor").hidden=true);
    $("pack-mode").addEventListener("change",syncPackModeChoices);
    $("pack-form").addEventListener("submit",async event=>{event.preventDefault();if(!$("pack-form").reportValidity())return;const request={name:$("pack-name").value.trim(),title:$("pack-title").value.trim(),description:$("pack-description").value.trim(),default_mode:$("pack-mode").value,agents:qa("#pack-agent-options input:checked").map(i=>i.value),specialists:qa("#pack-specialist-options input:checked").map(i=>i.value)};const validation=validatePack(request);if(validation){showFormError("pack-form-error",validation);return;}$("save-pack-button").disabled=true;showFormError("pack-form-error","");try{await api(state.editingPack?`/api/packs/${encodeURIComponent(state.editingPack)}`:"/api/packs",state.editingPack?"PUT":"POST",request);await reloadRegistry();$("pack-editor").hidden=true;toast("Набор сохранён.");}catch(error){showFormError("pack-form-error",error);}finally{$("save-pack-button").disabled=false;}});
    for(const kind of ["agent","pack"]){$("import-"+kind+"-button").addEventListener("click",()=>$("import-"+kind+"-file").click());$("import-"+kind+"-file").addEventListener("change",event=>{importRegistry(kind+"s",event.target.files?.[0]);event.target.value="";});}
    $("settings-theme").addEventListener("change",()=>applyAppearance($("settings-theme").value,state.appearance.accent_color));$("settings-accent").addEventListener("input",()=>applyAppearance(state.appearance.theme,$("settings-accent").value));qa("[data-accent]").forEach(b=>b.addEventListener("click",()=>applyAppearance(state.appearance.theme,b.dataset.accent||null)));$("appearance-form").addEventListener("submit",async event=>{event.preventDefault();applyAppearance(state.appearance.theme,state.appearance.accent_color);await savePartialSettings(state.appearance,"appearance-form-error");});
    $("policy-form").addEventListener("submit",async event=>{event.preventDefault();const permission_policy={};Object.keys(permissionLabels).forEach(key=>permission_policy[key]=$("permission-"+key).value);await savePartialSettings({...(desktopBridge()?{minimize_to_tray:$("settings-minimize-to-tray").checked}:{}),permission_policy,notifications:{task_complete:$("notify-task-complete").checked,needs_attention:$("notify-needs-attention").checked,stage_complete:$("notify-stage-complete").checked}},"policy-form-error");});
    qa('input[name="provider"]').forEach(r=>r.addEventListener("change",()=>{state.providerTouched=true;renderProviderChoice();}));$("provider-billing-confirmed").addEventListener("change",renderProviderChoice);
    $("provider-form").addEventListener("submit",async event=>{event.preventDefault();const provider=qa('input[name="provider"]').find(r=>r.checked)?.value;if(provider==="openai_api"&&!$("provider-billing-confirmed").checked){showFormError("provider-form-error","Подтвердите отдельную оплату API.");return;}$("save-provider-button").disabled=true;try{await api("/api/providers/select","POST",{provider,acknowledge_billing:provider==="openai_api"&&$("provider-billing-confirmed").checked});state.providerTouched=false;await loadProviders();state.lastStatus=0;await poll();toast("Подключение сохранено. Оно будет использоваться для новых запусков.");showFormError("provider-form-error","");}catch(error){showFormError("provider-form-error",error);}finally{renderProviderChoice();}});
    $("api-key-form").addEventListener("submit",async event=>{event.preventDefault();const key=$("api-key-input").value.trim();if(!key){showFormError("api-key-error","Введите ключ API, который нужно сохранить.");return;}$("save-api-key").disabled=true;try{await api("/api/providers/openai/key","POST",{key});$("api-key-input").value="";showFormError("api-key-error","");await loadProviders();toast("Ключ сохранён в защищённом хранилище Windows.");}catch(error){showFormError("api-key-error",error);}finally{$("save-api-key").disabled=false;}});
    $("test-api-key").addEventListener("click",async()=>{$("test-api-key").disabled=true;try{await api("/api/providers/openai/test","POST",{});showFormError("api-key-error","");await loadProviders();toast("Подключение проверено без генерации модели.");}catch(error){showFormError("api-key-error",error);}finally{$("test-api-key").disabled=!state.providers?.openai_api?.configured;}});
    $("remove-api-key").addEventListener("click",async()=>{if(!await confirmOperation("Удалить сохранённый ключ API?","Запуски через API будут недоступны, пока вы не сохраните новый ключ. Способ подключения автоматически не изменится.","","Удалить ключ"))return;try{await api("/api/providers/openai/key","DELETE",{});$("api-key-input").value="";await loadProviders();toast("Ключ удалён.");}catch(error){showFormError("api-key-error",error);}});
    $("copy-diagnostics-button").addEventListener("click",copyDiagnostics);$("export-diagnostics-button").addEventListener("click",()=>nativeOperation("export_diagnostics"));
  }

  qa("[data-page]").forEach((button) => button.addEventListener("click", () => setPage(button.dataset.page+(button.dataset.suiteFeatureLink?"/"+button.dataset.suiteFeatureLink:""))));
  qa("[data-open-page]").forEach((button) => button.addEventListener("click", () => setPage(button.dataset.openPage)));
  qa("[data-detail-tab]").forEach((button) => {
    button.addEventListener("click", () => setDetailTab(button.dataset.detailTab));
    button.addEventListener("keydown", (event) => {
      const tabs = qa("[data-detail-tab]"); const index = tabs.indexOf(button);
      let target;
      if (event.key === "ArrowRight") target = tabs[(index + 1) % tabs.length];
      if (event.key === "ArrowLeft") target = tabs[(index + tabs.length - 1) % tabs.length];
      if (event.key === "Home") target = tabs[0];
      if (event.key === "End") target = tabs[tabs.length - 1];
      if (target) { event.preventDefault(); setDetailTab(target.dataset.detailTab); target.focus(); }
    });
  });
  $("run-mode").addEventListener("change", renderPreview);
  $("refresh-button").addEventListener("click", refresh);
  $("browse-project-button").addEventListener("click", chooseProject);
  $("open-logs-button").addEventListener("click", openLogs);
  window.addEventListener("pywebviewready", onDesktopReady);
  $("history-search").addEventListener("input",()=>{clearTimeout(state.historyTimer);state.historyTimer=setTimeout(()=>loadHistory(true),250);});
  $("history-filter").addEventListener("change",()=>loadHistory(true));
  $("pause-button").addEventListener("click", () => control("pause"));
  $("resume-button").addEventListener("click",()=>{const action=state.actions.find(a=>a.run_id===state.selectedRun?.id&&a.kind==="product"&&a.allowed_decisions?.includes("resume"));if(action){$("run-actions").scrollIntoView({block:"nearest"});$("run-actions").querySelector("button")?.focus();}else control("resume");});
  $("stop-button").addEventListener("click", () => control("stop"));
  $("steer-form").addEventListener("submit", (event) => { event.preventDefault(); const instruction = $("steer-instruction").value.trim(); if (instruction) control("steer", instruction); });
  $("queue-button").addEventListener("click", () => { if ($("steer-form").reportValidity()) { const instruction = $("steer-instruction").value.trim(); if (instruction) control("queue", instruction); } });
  qa(".login-button").forEach((button) => button.addEventListener("click", () => login(button.dataset.method)));
  $("add-agent-button").addEventListener("click", () => openAgentEditor());
  ["close-agent-editor", "cancel-agent-button"].forEach((id) => $(id).addEventListener("click", () => { $("agent-editor").hidden = true; }));
  $("run-form").addEventListener("submit", async (event) => {
    event.preventDefault(); if (state.creatingRun || !$("run-form").reportValidity()) return;
    const workspace = $("workspace").value.trim(); const task = $("task").value.trim();
    if (!workspace || !task) { showFormError("run-form-error", "Укажите путь к проекту и непустую задачу."); return; }
    const request = {
      workspace, task, mode: $("run-mode").value, pack: $("run-pack").value,
      max_iterations: Number($("max-iterations").value), max_agent_calls: Number($("max-calls").value),
      max_parallel_agents: Number($("max-parallel").value), max_run_duration: Math.round(Number($("max-duration").value) * 60),
      auto_commit: $("auto-commit").checked, isolated: $("isolated").checked,
      specialists: ["deep", "audit"].includes($("run-mode").value) ? qa("#specialist-options input:checked").map((input) => input.value) : [],
    };
    const packError=validateComposerPack();if(packError){showFormError("run-form-error",packError);return;}
    state.creatingRun=true;const button = $("start-button"); button.disabled = true; button.textContent = "Подготовка запуска…"; showFormError("run-form-error", "");
    try {
      const run = await api("/api/runs", "POST", request);
      try { localStorage.setItem("codex-team-workspace", workspace); } catch (_) { /* storage may be disabled */ }
      state.runs = [run, ...state.runs.filter((item) => item.id !== run.id)]; renderRuns(true);
      toast("Задача передана координатору."); await selectRun(run.id);
    } catch (error) { showFormError("run-form-error", error); }
    finally { state.creatingRun=false;button.textContent = "Запустить команду ↗"; renderConnection(); }
  });
  $("agent-form").addEventListener("submit", async (event) => {
    event.preventDefault(); if (!$("agent-form").reportValidity()) return;
    const request = {
      description: $("agent-description").value.trim(), enabled_modes: qa("#agent-mode-options input:checked").map(i=>i.value), can_execute: $("agent-can-execute").checked, can_network: $("agent-can-network").checked,
      name: $("agent-name").value.trim(), role: $("agent-role").value.trim(), instructions: $("agent-instructions").value.trim(),
      permission: $("agent-permission").value, model: $("agent-model").value.trim() || null,
      reasoning_effort: $("agent-reasoning").value || null, enabled: $("agent-enabled").checked,
    };
    if(request.can_network){if(!await confirmOperation("Разрешить роли запросы доступа к сети?","Это не отключает официальные разрешения Codex. Запросы сети всё равно проверяются политикой и подтверждаются через центр действий.",request.role,"Разрешить запросы сети"))return;request.confirmed_permissions=true;}
    if (!request.role || !request.instructions) { showFormError("agent-form-error", "Введите название роли и инструкции."); return; }
    const modelError=validateModel(request.model,request.reasoning_effort);if(modelError){showFormError("agent-form-error",modelError);return;}
    $("save-agent-button").disabled = true; showFormError("agent-form-error", "");
    try {
      await api(state.editingAgent ? `/api/agents/${encodeURIComponent(state.editingAgent)}` : "/api/agents", state.editingAgent ? "PUT" : "POST", request);
      const agents = await api("/api/agents"); state.agents = Array.isArray(agents) ? agents : agents.agents || []; renderRegistry();
      $("agent-editor").hidden = true; toast("Агент сохранён. Новые инструкции применяются к следующим запускам.");
    } catch (error) { showFormError("agent-form-error", error); }
    finally { $("save-agent-button").disabled = false; }
  });
  $("settings-form").addEventListener("submit", async (event) => {
    event.preventDefault(); if (!$("settings-form").reportValidity()) return;
    const settings = {
      model: $("settings-model").value.trim() || null, reasoning_effort: $("settings-reasoning").value || null,
      max_iterations: Number($("settings-iterations").value), max_agent_calls: Number($("settings-calls").value),
      max_parallel_agents: Number($("settings-parallel").value), max_run_duration: Math.round(Number($("settings-duration").value) * 60),
    };
    const modelError=validateModel(settings.model,settings.reasoning_effort);if(modelError){showFormError("settings-form-error",modelError);return;}
    $("save-settings-button").disabled = true; showFormError("settings-form-error", "");
    try { const saved = await api("/api/settings", "POST", settings); if (state.status) state.status.settings = saved; applyDefaults(saved); toast("Настройки сохранены для новых запусков."); }
    catch (error) { showFormError("settings-form-error", error); }
    finally { $("save-settings-button").disabled = false; }
  });
  window.addEventListener("codex-suite-feature-change",event=>{
    state.suiteFeature=event.detail?.feature||"architect";
    qa(".nav-item[data-page='suite']").forEach(el=>{const active=el.dataset.suiteFeatureLink===state.suiteFeature;el.classList.toggle("active",active);if(active)el.setAttribute("aria-current","page");else el.removeAttribute("aria-current");});
  });
  $("runs-search")?.addEventListener("input",renderRunList);
  $("runs-state-filter")?.addEventListener("change",renderRunList);
  window.addEventListener("hashchange", () => setPage(location.hash.slice(1)));
  document.addEventListener("visibilitychange", () => { if (!document.hidden) poll(); });
  try { $("workspace").value = localStorage.getItem("codex-team-workspace") || ""; } catch (_) { /* storage may be disabled */ }
  window.CodexTeamSuite={api,setPage,selectRun,toast,confirmOperation,state,node,runReady};
  // Handle injection before or after this deferred script without assuming a bridge in debug browsers.
  initializePolicies(); initializeAppearance(); bindFeatures(); renderPreview(); renderGlobalUsage(); renderStatus(); setPage(location.hash.slice(1) || "workbench");
  onDesktopReady(); refresh();
  setInterval(poll, 2000);
})();
