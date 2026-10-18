/* Stored run snapshots only. No task execution, configuration writes or polling. */
((root) => {
  'use strict';
  const text = value => typeof value === 'string' ? value : '';
  const numeric = value => typeof value === 'number' && Number.isFinite(value) && value >= 0;
  function runChoices(runs = [], query = '') {
    const words = text(query).normalize('NFKC').toLocaleLowerCase().trim().split(/\s+/).filter(Boolean);
    const seen = new Set();
    return (Array.isArray(runs) ? runs : []).filter(run => {
      if (!run || !text(run.id) || seen.has(run.id)) return false;
      seen.add(run.id);
      const haystack = [run.id, run.task, run.workspace, run.original_workspace, run.state].map(text).join(' ').normalize('NFKC').toLocaleLowerCase();
      return words.every(word => haystack.includes(word));
    });
  }
  function errorCode(error) {
    if (error?.status === 401 || error?.status === 403) return 'permission';
    if (error?.status === 404) return 'missing';
    if (error?.kind === 'network' || error?.status === 0 || error instanceof TypeError) return 'offline';
    return 'error';
  }
  function createController({api, onState = () => {}}) {
    let state = {left: '', right: '', busy: false, data: null, error: ''};
    let generation = 0, destroyed = false;
    const emit = patch => {state = {...state, ...patch}; if (!destroyed) onState({...state});};
    async function refresh() {
      const version = ++generation, left = state.left, right = state.right;
      if (destroyed) return;
      if (!left || !right || left === right) {emit({busy: false, data: null, error: ''}); return;}
      emit({busy: true, data: null, error: ''});
      try {
        const data = await api('/api/run-comparison?' + new URLSearchParams({left, right}));
        if (destroyed || version !== generation) return;
        if (data?.left?.id !== left || data?.right?.id !== right || typeof data.comparable_project !== 'boolean') throw new Error('Invalid comparison snapshot');
        emit({busy: false, data, error: ''});
      } catch (error) {
        if (!destroyed && version === generation) emit({busy: false, data: null, error: errorCode(error)});
      }
    }
    function choose(side, id, fetch = true) {
      if (destroyed || !['left', 'right'].includes(side) || state[side] === text(id)) return Promise.resolve();
      generation++; emit({[side]: text(id), busy: false, data: null, error: ''});
      return fetch ? refresh() : Promise.resolve();
    }
    return {choose, refresh, swap() {if (destroyed) return; generation++; emit({left: state.right, right: state.left, busy: false, data: null, error: ''}); return refresh();},
      cancel() {generation++; if (!destroyed) emit({busy: false});},
      get state() {return {...state};}, destroy() {destroyed = true; generation++;}};
  }
  const labels = {
    'Сравнить запуски': 'Compare runs', 'Сравнение запусков': 'Run comparison', 'Закрыть сравнение': 'Close comparison',
    'Базовый запуск': 'Baseline run', 'Второй запуск': 'Second run', 'Поиск базового запуска': 'Search baseline runs', 'Поиск второго запуска': 'Search second runs',
    'Задача, ID или путь…': 'Task, ID or path…', 'Выберите запуск': 'Choose a run', 'Поменять местами': 'Swap runs', 'Обновить сравнение': 'Refresh comparison',
    'Только загруженные запуски. Другие записи доступны через страницы и фильтры истории.': 'Only loaded runs. Find other records using history pages and filters.',
    'Выберите два разных запуска для сравнения сохранённых данных.': 'Choose two different runs to compare stored data.',
    'Выберите разные запуски.': 'Choose different runs.', 'Загрузка сравнения…': 'Loading comparison…',
    'Сравнение загружено. Данные обновляются только по вашему запросу.': 'Comparison loaded. Data updates only when you request it.',
    'Сравнение недоступно: нет разрешения на чтение.': 'Comparison unavailable: read permission is required.',
    'Один из запусков больше недоступен или сервер не поддерживает сравнение.': 'A run is no longer available, or the server does not support comparison.',
    'Нет связи с сервером. Повторите обновление после подключения.': 'Cannot reach the server. Retry refreshing when connected.',
    'Не удалось загрузить сравнение. Повторите обновление.': 'Could not load the comparison. Retry refreshing.',
    'Не удалось открыть запуск. Повторите попытку.': 'Could not open the run. Try again.',
    'Разные проекты: результаты зависят от контекста задач и настроек.': 'Different projects: results depend on task context and configuration.',
    'Проект одного из запусков неизвестен. Сопоставимость не установлена.': 'A run’s project is unknown. Comparability has not been established.',
    'Есть незавершённые запуски. Сохранённые данные могут быть частичными.': 'Some runs are unfinished. Stored data may be partial.',
    'Использование учтено не полностью. Отсутствующие значения не означают ноль.': 'Usage tracking is incomplete. Missing values do not mean zero.',
    'Один проект не гарантирует одинаковые задачи, настройки или условия выполнения.': 'The same project does not guarantee matching tasks, configuration or execution conditions.',
    'Сохранённые настройки': 'Stored configuration', 'Результаты и использование': 'Results and usage', 'Последние результаты ролей': 'Latest role results',
    'Режим': 'Mode', 'Набор агентов': 'Agent pack', 'Уровень доступа': 'Access level', 'Рабочая папка': 'Workspace', 'Исходный проект': 'Original project', 'Состояние': 'State',
    'Вызовы агентов': 'Agent calls', 'Длительность': 'Duration', 'Измеренные токены': 'Measured tokens', 'Полнота учёта': 'Usage completeness', 'Изменённые файлы': 'Changed files',
    'Лимит итераций': 'Iteration limit', 'Лимит вызовов': 'Call limit', 'Лимит времени': 'Duration limit', 'Лимит токенов': 'Token limit',
    'Полный': 'Complete', 'Частичный': 'Partial', 'Нет данных': 'No data', 'Открыть запуск': 'Open run', 'Вердикт': 'Verdict', 'Сводка': 'Summary', 'Ошибка': 'Error', 'Попытки': 'Attempts',
    'Параллельные агенты': 'Parallel agents', 'Изолированная копия': 'Isolated workspace', 'Автоматический коммит': 'Automatic commit', 'Специалисты': 'Specialists', 'Да': 'Yes', 'Нет': 'No',
    'Результаты ролей не сохранены.': 'Role results have not been stored.', '{value} с': '{value} s', 'Показано {count} записей': '{count} records shown',
    'Выполняется': 'Running', 'Завершён': 'Completed', 'Ожидает': 'Queued', 'Пауза': 'Paused', 'Остановлен': 'Stopped', 'Прерван': 'Interrupted',
    'Ожидает решения': 'Needs action', 'Ожидание этапа': 'Waiting for stage', 'Приостановка': 'Pausing', 'Остановка': 'Stopping',
    'Нужен вход': 'Sign-in required', 'Лимит Codex': 'Codex limit', 'Заблокировано': 'Blocked', 'Выполнено частично': 'Partially completed',
    'Только чтение': 'Read only', 'Стандартный': 'Standard', 'Полный доступ': 'Full access',
    'Быстрый': 'Quick', 'Глубокий': 'Deep', 'Аудит': 'Audit', 'Планирование': 'Planning', 'Готовый план': 'Implementation',
    'История ролей сокращена. Показаны последние сохранённые результаты.': 'Role history is truncated. The latest stored results are shown.',
  };
  function mount({anchor, api, getRuns = () => [], getSelectedRun = () => null, openRun = () => {}}) {
    const doc = root.document;
    if (!doc || !anchor) return null;
    const I = root.CodexI18n || {t: source => source, register() {}};
    I.register(labels);
    const t = (source, params) => I.t(source, params);
    const el = (tag, cls, value) => {const node = doc.createElement(tag); if (cls) node.className = cls; if (value !== undefined) node.textContent = value; return node;};
    const button = (label, cls = 'button secondary') => {const node = el('button', cls, t(label)); node.type = 'button'; return node;};
    const trigger = button('Сравнить запуски'); trigger.id = 'run-comparison-open'; trigger.setAttribute('aria-haspopup', 'dialog');
    const dialog = el('dialog', 'run-comparison'); dialog.id = 'run-comparison'; dialog.setAttribute('aria-labelledby', 'run-comparison-title'); dialog.setAttribute('aria-describedby', 'run-comparison-scope');
    const header = el('header', 'run-comparison-header');
    const title = el('h2', '', t('Сравнение запусков')); title.id = 'run-comparison-title';
    const closeButton = button('Закрыть сравнение', 'run-comparison-close');
    header.append(title, closeButton);
    const scope = el('p', 'run-comparison-scope', t('Только загруженные запуски. Другие записи доступны через страницы и фильтры истории.')); scope.id = 'run-comparison-scope';
    const selectors = el('div', 'run-comparison-selectors');
    const controls = {};
    for (const [side, label, searchLabel] of [['left', 'Базовый запуск', 'Поиск базового запуска'], ['right', 'Второй запуск', 'Поиск второго запуска']]) {
      const group = el('div', 'run-comparison-selector');
      const caption = el('label', '', t(label)); caption.htmlFor = 'run-comparison-' + side;
      const search = el('input', 'run-comparison-search'); search.type = 'search'; search.placeholder = t('Задача, ID или путь…'); search.setAttribute('aria-label', t(searchLabel)); search.autocomplete = 'off';
      const select = el('select', 'run-comparison-select'); select.id = 'run-comparison-' + side;
      const count = el('small', 'run-comparison-count'); count.id = select.id + '-count'; select.setAttribute('aria-describedby', count.id);
      group.append(caption, search, select, count); selectors.append(group); controls[side] = {search, select, count};
      search.addEventListener('input', () => renderChoices());
      select.addEventListener('change', () => controller.choose(side, select.value));
    }
    const actions = el('div', 'run-comparison-actions');
    const swap = button('Поменять местами'), refreshButton = button('Обновить сравнение'); actions.append(swap, refreshButton);
    const status = el('p', 'run-comparison-status'); status.setAttribute('role', 'status'); status.setAttribute('aria-live', 'polite'); status.setAttribute('aria-atomic', 'true');
    const content = el('div', 'run-comparison-content');
    dialog.append(header, scope, selectors, actions, status, content); doc.body.append(dialog); anchor.append(trigger);
    let previousFocus = null, cached = new Map(), last = null, destroyed = false;
    const number = value => numeric(value) ? new Intl.NumberFormat(I.locale || 'ru-RU', {maximumFractionDigits: 1}).format(value) : t('Нет данных');
    const duration = value => numeric(value) ? t('{value} с', {value: number(value)}) : t('Нет данных');
    const value = input => text(input) || (numeric(input) ? number(input) : t('Нет данных'));
    const states = {RUNNING:'Выполняется',COMPLETED:'Завершён',DONE:'Завершён',FAILED:'Ошибка',ERROR:'Ошибка',QUEUED:'Ожидает',PAUSED:'Пауза',STOPPED:'Остановлен',CANCELLED:'Остановлен',INTERRUPTED:'Прерван',WAITING_USER:'Ожидает решения',USER_DECISION_REQUIRED:'Ожидает решения',WAITING:'Ожидание этапа',PAUSING:'Приостановка',STOPPING:'Остановка',AUTH_REQUIRED:'Нужен вход',USAGE_LIMIT:'Лимит Codex',BLOCKED:'Заблокировано',PARTIAL:'Выполнено частично'};
    const stateText = state => t(states[state] || value(state));
    function renderChoices() {
      let loaded = []; try {loaded = runChoices(getRuns());} catch (_) { /* previously selected runs remain available */ }
      for (const run of loaded) cached.set(run.id, run);
      const selected = controller.state;
      for (const side of ['left', 'right']) {
        const {search, select, count} = controls[side];
        const matches = runChoices(loaded, search.value);
        const chosen = cached.get(selected[side]);
        const rows = chosen && !matches.some(run => run.id === chosen.id) ? [chosen, ...matches] : matches;
        const blank = el('option', '', t('Выберите запуск')); blank.value = '';
        select.replaceChildren(blank, ...rows.map(run => {const option = el('option', '', [run.id, text(run.task)].filter(Boolean).join(' · ')); option.value = run.id; return option;}));
        if (selected[side] && !rows.some(run => run.id === selected[side])) {const option = el('option', '', selected[side]); option.value = selected[side]; select.append(option);}
        select.value = selected[side]; count.textContent = t('Показано {count} записей', {count: matches.length});
      }
      // Retain only loaded records and the two explicit selections, never all visited history pages.
      const keep = new Set([...loaded.map(run => run.id), selected.left, selected.right]);
      for (const id of cached.keys()) if (!keep.has(id)) cached.delete(id);
    }
    const warnings = {different_projects:'Разные проекты: результаты зависят от контекста задач и настроек.',project_unknown:'Проект одного из запусков неизвестен. Сопоставимость не установлена.',active_runs_partial:'Есть незавершённые запуски. Сохранённые данные могут быть частичными.',incomplete_usage:'Использование учтено не полностью. Отсутствующие значения не означают ноль.',stage_history_truncated:'История ролей сокращена. Показаны последние сохранённые результаты.'};
    function definition(list, label, result) {list.append(el('dt', '', t(label)), el('dd', '', result));}
    function runCard(run, caption) {
      const card = el('article', 'run-comparison-card'); card.setAttribute('aria-label', t(caption));
      const top = el('div', 'run-comparison-card-top'); top.append(el('span', 'run-comparison-eyebrow', t(caption)), el('span', 'run-comparison-state', stateText(run.state))); card.append(top);
      card.append(el('code', 'run-comparison-id', text(run.id)), el('h3', 'run-comparison-task', value(run.task)));
      const open = button('Открыть запуск', 'button text-button'); open.addEventListener('click', async () => {
        close(false);
        try {await openRun(run.id); doc.getElementById('main')?.focus();} catch (_) {openDialog(false); status.textContent = t('Не удалось открыть запуск. Повторите попытку.');}
      }); card.append(open);
      card.append(el('h4', '', t('Результаты и использование')));
      const metrics = el('dl', 'run-comparison-metrics');
      for (const [label, result] of [['Вызовы агентов', number(run.calls)], ['Длительность', duration(run.duration_seconds)], ['Измеренные токены', number(run.measured_tokens)], ['Изменённые файлы', number(run.changed_files_count)], ['Полнота учёта', t(run.usage_complete === true ? 'Полный' : run.usage_complete === false ? 'Частичный' : 'Нет данных')]]) definition(metrics, label, result);
      card.append(metrics, el('h4', '', t('Сохранённые настройки')));
      const config = el('dl', 'run-comparison-config');
      const access = {'read-only':'Только чтение',standard:'Стандартный','full-access':'Полный доступ'};
      const modes = {quick:'Быстрый',standard:'Стандартный',deep:'Глубокий',audit:'Аудит',plan:'Планирование',implement:'Готовый план'};
      for (const [label, result] of [['Режим', t(modes[run.mode] || value(run.mode))], ['Набор агентов', value(run.pack)], ['Уровень доступа', t(access[run.access_level] || value(run.access_level))], ['Рабочая папка', value(run.workspace)], ['Исходный проект', value(run.original_workspace)], ['Лимит итераций', number(run.max_iterations)], ['Лимит вызовов', number(run.max_agent_calls)], ['Лимит времени', duration(run.max_run_duration)], ['Лимит токенов', number(run.max_total_tokens)]]) definition(config, label, result);
      const boolean = input => t(input === true ? 'Да' : input === false ? 'Нет' : 'Нет данных');
      for (const [key, label, format] of [['max_parallel_agents', 'Параллельные агенты', number], ['isolated', 'Изолированная копия', boolean], ['auto_commit', 'Автоматический коммит', boolean], ['specialists', 'Специалисты', input => Array.isArray(input) ? (input.map(text).filter(Boolean).join(', ') || '—') : t('Нет данных')]]) {
        if (run[key] !== undefined) definition(config, label, format(run[key]));
      }
      card.append(config, el('h4', '', t('Последние результаты ролей')));
      const stages = Array.isArray(run.stages) ? run.stages : [];
      if (!stages.length) card.append(el('p', 'run-comparison-muted', t('Результаты ролей не сохранены.')));
      for (const stage of stages) {
        if (!stage || typeof stage !== 'object') continue;
        const section = el('section', 'run-comparison-role'); section.append(el('h5', '', value(stage.role)));
        const details = el('dl', 'run-comparison-config');
        definition(details, 'Вердикт', value(stage.verdict)); definition(details, 'Попытки', number(stage.attempts));
        definition(details, 'Сводка', value(stage.summary)); definition(details, 'Ошибка', value(stage.error)); section.append(details); card.append(section);
      }
      if (text(run.error)) {const error = el('p', 'run-comparison-run-error'); error.append(el('strong', '', t('Ошибка') + ': '), doc.createTextNode(run.error)); card.append(error);}
      return card;
    }
    function render(state) {
      renderChoices();
      dialog.setAttribute('aria-busy', String(state.busy));
      const valid = !!state.left && !!state.right && state.left !== state.right;
      swap.disabled = !valid; refreshButton.disabled = !valid || state.busy;
      const errors = {permission:'Сравнение недоступно: нет разрешения на чтение.',missing:'Один из запусков больше недоступен или сервер не поддерживает сравнение.',offline:'Нет связи с сервером. Повторите обновление после подключения.',error:'Не удалось загрузить сравнение. Повторите обновление.'};
      status.textContent = t(state.busy ? 'Загрузка сравнения…' : errors[state.error] || (state.data ? 'Сравнение загружено. Данные обновляются только по вашему запросу.' : state.left && state.left === state.right ? 'Выберите разные запуски.' : 'Выберите два разных запуска для сравнения сохранённых данных.'));
      status.classList.toggle('is-error', !!state.error);
      if (last === state.data) return;
      last = state.data; content.replaceChildren();
      if (!state.data) return;
      const data = state.data, notes = el('div', 'run-comparison-notes');
      const codes = new Set(Array.isArray(data.warnings) ? data.warnings : []);
      if (!data.comparable_project && !codes.has('different_projects')) codes.add('project_unknown');
      if (data.left.usage_complete !== true || data.right.usage_complete !== true) codes.add('incomplete_usage');
      for (const code of codes) if (warnings[code]) notes.append(el('p', 'run-comparison-warning', t(warnings[code])));
      notes.append(el('p', 'run-comparison-muted', t('Один проект не гарантирует одинаковые задачи, настройки или условия выполнения.')));
      const cards = el('div', 'run-comparison-cards'); cards.append(runCard(data.left, 'Базовый запуск'), runCard(data.right, 'Второй запуск')); content.append(notes, cards);
    }
    const controller = createController({api, onState: render});
    function openDialog(fetch = true) {
      if (destroyed) return;
      if (dialog.open) {controls.left.search.focus(); return;}
      if (doc.querySelector('dialog[open]')) return;
      previousFocus = doc.activeElement;
      if (!controller.state.left) {
        let baseline; try {baseline = getSelectedRun();} catch (_) { /* optional selection bridge */ }
        let first; try {first = runChoices(getRuns())[0];} catch (_) { /* empty choices */ }
        if (baseline && typeof baseline === 'object' && text(baseline.id)) cached.set(baseline.id, baseline);
        controller.choose('left', text(baseline?.id) || text(baseline) || first?.id || '', false);
      }
      render(controller.state); dialog.showModal(); controls.right.search.focus();
      if (fetch && controller.state.left && controller.state.right) controller.refresh();
    }
    const open = () => openDialog();
    function close(restore = true) {
      if (!dialog.open) return;
      controller.cancel(); dialog.close();
      if (restore && previousFocus?.isConnected && !previousFocus.closest?.('[hidden]')) previousFocus.focus();
    }
    trigger.addEventListener('click', open); closeButton.addEventListener('click', () => close());
    swap.addEventListener('click', () => controller.swap()); refreshButton.addEventListener('click', () => controller.refresh());
    dialog.addEventListener('cancel', event => {event.preventDefault(); close();});
    dialog.addEventListener('keydown', event => {
      if (event.key === 'Escape') {event.preventDefault(); close(); return;}
      if (event.key !== 'Tab') return;
      const focusable = [...dialog.querySelectorAll('button:not(:disabled),input,select,[tabindex="0"]')].filter(node => node.getClientRects().length);
      const index = focusable.indexOf(doc.activeElement), next = index + (event.shiftKey ? -1 : 1);
      if (next < 0 || next >= focusable.length) {event.preventDefault(); focusable[(next + focusable.length) % focusable.length]?.focus();}
    });
    render(controller.state);
    return {open, close, controller, refresh: renderChoices, destroy() {destroyed = true; close(); controller.destroy(); dialog.remove(); trigger.remove();}};
  }
  const exported = {mount, createController, runChoices, numeric, errorCode};
  root.CodexRunComparison = exported;
  if (typeof module !== 'undefined' && module.exports) module.exports = exported;
})(typeof window !== 'undefined' ? window : globalThis);
