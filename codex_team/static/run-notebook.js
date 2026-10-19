/* Local run notes and user-requested Markdown reports. Never executes an agent. */
((root) => {
  'use strict';
  const MAX_NOTE = 10000;
  function validNotebook(value, id) {
    return value && value.run_id === id && Number.isInteger(value.revision) && value.revision >= 0 &&
      typeof value.favorite === 'boolean' && typeof value.note === 'string' && [...value.note].length <= MAX_NOTE &&
      (value.updated_at === null || typeof value.updated_at === 'string');
  }
  function errorCode(error) {
    if (error?.status === 409) return 'conflict';
    if ([401, 403].includes(error?.status)) return 'permission';
    if (error?.status === 404) return 'missing';
    if (error?.status === 0 || error?.kind === 'network' || error instanceof TypeError) return 'offline';
    return 'error';
  }
  function safeFilename(value) {
    if (typeof value !== 'string' || value.length > 180 || !/^[a-zA-Z0-9][a-zA-Z0-9._-]*\.md$/.test(value) || value.includes('..')) return 'codex-team-run-report.md';
    return value;
  }
  function createController({api, onState = () => {}, onSaved = () => {}}) {
    let state = {id: '', data: null, loading: false, saving: false, exporting: false, error: '', notice: ''};
    let session = 0, active = false, destroyed = false, mutation = false, reading = 0;
    const current = version => active && !destroyed && session === version;
    const emit = patch => {state = {...state, ...patch}; if (active && !destroyed) onState({...state});};
    async function load(id = state.id) {
      if (!active || destroyed || mutation || state.exporting || typeof id !== 'string' || !id) return false;
      const version = session, request = ++reading;
      emit({id, data: id === state.id ? state.data : null, loading: true, error: '', notice: ''});
      try {
        const response = await api(`/api/runs/${encodeURIComponent(id)}/notebook`);
        if (!current(version) || request !== reading) return false;
        if (!validNotebook(response, id)) throw new Error('Invalid notebook');
        emit({data: {...response}, loading: false}); return true;
      } catch (error) {if (current(version) && request === reading) emit({error: errorCode(error), loading: false}); return false;}
    }
    async function save({note, favorite}) {
      if (!active || destroyed || mutation || state.loading || state.exporting || !state.data) return false;
      if (typeof note !== 'string' || [...note].length > MAX_NOTE || typeof favorite !== 'boolean') {emit({error: 'validation'}); return false;}
      const version = session, id = state.id, revision = state.data.revision;
      mutation = true; emit({saving: true, error: '', notice: ''});
      try {
        const response = await api(`/api/runs/${encodeURIComponent(id)}/notebook`, 'PUT', {expected_revision: revision, favorite, note});
        if (!validNotebook(response, id) || response.revision <= revision || response.note !== note || response.favorite !== favorite) throw new Error('Invalid notebook save');
        try {if (!destroyed) Promise.resolve(onSaved({...response})).catch(() => {});} catch (_) { /* History refresh cannot invalidate a successful save. */ }
        if (!current(version)) return true;
        emit({data: {...response}, notice: 'saved'}); return true;
      } catch (error) {if (current(version)) emit({error: errorCode(error)}); return false;}
      finally {mutation = false; if (current(version)) emit({saving: false});}
    }
    async function report(language) {
      if (!active || destroyed || mutation || state.loading || state.exporting || !state.data) return null;
      const version = session, id = state.id;
      emit({exporting: true, error: '', notice: ''});
      try {
        const response = await api(`/api/runs/${encodeURIComponent(id)}/report?language=${language === 'en' ? 'en' : 'ru'}`);
        if (!current(version)) return null;
        if (response?.run_id !== id || typeof response.markdown !== 'string' || response.markdown.length > 2000000 || !response.markdown.trim()) throw new Error('Invalid report');
        emit({notice: 'exported'}); return {markdown: response.markdown, filename: safeFilename(response.filename)};
      } catch (error) {if (current(version)) emit({error: errorCode(error)}); return null;}
      finally {if (current(version)) emit({exporting: false});}
    }
    return {async open(id) {if (destroyed || mutation || typeof id !== 'string' || !id) return false; active = true; session++; state = {id, data: null, loading: false, saving: false, exporting: false, error: '', notice: ''}; return load(id);},
      load, save, report, close() {active = false; session++; reading++;},
      get state() {return {...state};}, get pendingSave() {return mutation;},
      destroy() {destroyed = true; active = false; session++; reading++;}};
  }
  const labels = {
    'Не удалось скачать отчёт. Попробуйте ещё раз или откройте приложение в браузере.':'Could not download the report. Try again or open the application in a browser.',
    'Заметки и отчёт':'Notes and report', 'Заметки запуска':'Run notebook', 'Закрыть заметки':'Close notebook',
    'Избранный запуск':'Favorite run', 'Личная заметка':'Personal note', 'Решения, наблюдения и следующий шаг…':'Decisions, observations and next step…',
    'Заметка хранится локально и не передаётся агентам.':'This note is stored locally and is not sent to agents.',
    'Сохранить заметку':'Save note', 'Обновить заметку':'Refresh note', 'Скачать отчёт .md':'Download .md report',
    'Отчёт содержит задачу, пути проекта и сохранённую заметку. Просмотрите файл перед отправкой другим людям.':'The report includes the task, project paths and saved note. Review the file before sharing it.',
    'Загрузка заметки…':'Loading notebook…', 'Сохранение…':'Saving…', 'Подготовка отчёта…':'Preparing report…',
    'Заметка сохранена.':'Note saved.', 'Отчёт подготовлен для скачивания.':'The report is ready to download.',
    'Изменения не сохранены.':'Unsaved changes.', 'Сохранённых заметок пока нет.':'No saved notes yet.',
    'Заметка загружена.':'Notebook loaded.', 'Сначала сохраните изменения, затем скачайте отчёт.':'Save your changes before downloading the report.',
    'Заметка изменена в другом окне. Ваш ввод сохранён. Обновите заметку, чтобы загрузить актуальную версию.':'The notebook changed in another window. Your input is preserved. Refresh the note to load the latest version.',
    'Нет разрешения на чтение или изменение заметки.':'You do not have permission to read or edit this notebook.',
    'Запуск недоступен или сервер не поддерживает заметки.':'The run is unavailable, or the server does not support notebooks.',
    'Нет связи с сервером. Ввод сохранён; повторите после подключения.':'Cannot reach the server. Your input is preserved; retry when connected.',
    'Не удалось выполнить действие. Ввод сохранён; повторите попытку.':'Could not complete the action. Your input is preserved; try again.',
    'Заметка может содержать не более 10 000 символов.':'A note can contain at most 10,000 characters.',
    'Отменить изменения?':'Discard changes?', 'Несохранённая заметка будет потеряна.':'The unsaved note will be lost.', 'Отменить изменения':'Discard changes',
    'Сохранение ещё выполняется. Повторное открытие будет доступно после его завершения.':'Saving is still in progress. You can reopen the notebook when it finishes.',
    '{count} / 10 000 символов':'{count} / 10,000 characters', 'Запуск: {id}':'Run: {id}',
  };
  function mount({anchor, api, getSelectedRun = () => null, onSaved = () => {}, confirm}) {
    const doc = root.document;
    if (!doc || !anchor) return null;
    const I = root.CodexI18n || {t: value => value, register() {}}; I.register(labels);
    const t = (source, params) => I.t(source, params);
    const el = (tag, cls, text) => {const node = doc.createElement(tag); if (cls) node.className = cls; if (text !== undefined) node.textContent = text; return node;};
    const btn = (text, cls = 'button secondary') => {const node = el('button', cls, t(text)); node.type = 'button'; return node;};
    const trigger = btn('Заметки и отчёт'); trigger.id = 'run-notebook-open'; trigger.setAttribute('aria-haspopup', 'dialog'); anchor.append(trigger);
    const dialog = el('dialog', 'run-notebook'); dialog.id = 'run-notebook'; dialog.setAttribute('aria-labelledby', 'run-notebook-title');
    const header = el('header', 'run-notebook-header'), heading = el('div');
    const title = el('h2', '', t('Заметки запуска')); title.id = 'run-notebook-title'; const runId = el('code', 'run-notebook-id');
    heading.append(title, runId); const closeButton = btn('Закрыть заметки', 'run-notebook-close'); header.append(heading, closeButton);
    const body = el('div', 'run-notebook-body'), favoriteLabel = el('label', 'run-notebook-favorite'), favorite = el('input'); favorite.type = 'checkbox'; favorite.id = 'run-notebook-favorite';
    favoriteLabel.append(favorite, el('span', '', t('Избранный запуск')));
    const noteLabel = el('label', 'run-notebook-label', t('Личная заметка')); noteLabel.htmlFor = 'run-notebook-note';
    const note = el('textarea', 'run-notebook-note'); note.id = 'run-notebook-note'; note.rows = 11; note.placeholder = t('Решения, наблюдения и следующий шаг…');
    const hint = el('p', 'run-notebook-muted', t('Заметка хранится локально и не передаётся агентам.')); hint.id = 'run-notebook-local';
    const counter = el('span', 'run-notebook-counter'); counter.id = 'run-notebook-counter'; note.setAttribute('aria-describedby', 'run-notebook-local run-notebook-counter');
    const actions = el('div', 'run-notebook-actions'), save = btn('Сохранить заметку', 'button primary'), refresh = btn('Обновить заметку'), exportButton = btn('Скачать отчёт .md');
    save.id = 'run-notebook-save'; refresh.id = 'run-notebook-refresh'; exportButton.id = 'run-notebook-export'; actions.append(save, refresh, exportButton);
    const status = el('p', 'run-notebook-status'); status.setAttribute('role', 'status'); status.setAttribute('aria-live', 'polite');
    const privacy = el('p', 'run-notebook-privacy', t('Отчёт содержит задачу, пути проекта и сохранённую заметку. Просмотрите файл перед отправкой другим людям.'));
    body.append(favoriteLabel, noteLabel, note, counter, hint, actions, status, privacy); dialog.append(header, body); doc.body.append(dialog);
    let previousFocus = null, rendered = null, destroyed = false, promptBusy = false, epoch = 0;
    const dirty = () => !!controller.state.data && (note.value !== controller.state.data.note || favorite.checked !== controller.state.data.favorite);
    function render(state) {
      if (!dialog.open || destroyed) return;
      runId.textContent = t('Запуск: {id}', {id: state.id});
      if (state.data && rendered !== state.data) {note.value = state.data.note; favorite.checked = state.data.favorite; rendered = state.data;}
      const busy = state.loading || state.saving || state.exporting;
      dialog.setAttribute('aria-busy', String(busy)); note.disabled = !state.data || busy; favorite.disabled = !state.data || busy;
      save.disabled = !state.data || busy || !dirty() || [...note.value].length > MAX_NOTE;
      refresh.disabled = busy; exportButton.disabled = !state.data || busy || dirty();
      counter.textContent = t('{count} / 10 000 символов', {count: [...note.value].length}); counter.classList.toggle('is-error', [...note.value].length > MAX_NOTE);
      const errors = {conflict:'Заметка изменена в другом окне. Ваш ввод сохранён. Обновите заметку, чтобы загрузить актуальную версию.',permission:'Нет разрешения на чтение или изменение заметки.',missing:'Запуск недоступен или сервер не поддерживает заметки.',offline:'Нет связи с сервером. Ввод сохранён; повторите после подключения.',validation:'Заметка может содержать не более 10 000 символов.',error:'Не удалось выполнить действие. Ввод сохранён; повторите попытку.'};
      status.textContent = t(state.loading ? 'Загрузка заметки…' : state.saving ? 'Сохранение…' : state.exporting ? 'Подготовка отчёта…' : errors[state.error] || (dirty() ? 'Изменения не сохранены.' : state.notice === 'saved' ? 'Заметка сохранена.' : state.notice === 'exported' ? 'Отчёт подготовлен для скачивания.' : state.data ? state.data.note ? 'Заметка загружена.' : 'Сохранённых заметок пока нет.' : ''));
      status.classList.toggle('is-error', !!state.error);
    }
    const controller = createController({api, onState: render, onSaved});
    const askDiscard = () => confirm ? confirm(t('Отменить изменения?'), t('Несохранённая заметка будет потеряна.'), '', t('Отменить изменения')) : Promise.resolve(root.confirm(t('Несохранённая заметка будет потеряна.')));
    async function canDiscard() {if (promptBusy) return false; if (!dirty()) return true; promptBusy = true; try {return !!(await askDiscard());} finally {promptBusy = false;}}
    async function close() {
      if (!dialog.open || promptBusy) return;
      const version = epoch;
      // A submitted save already owns its payload; closing must not interrupt that write.
      if (!controller.state.saving && !await canDiscard()) return;
      if (version !== epoch || !dialog.open || destroyed) return;
      epoch++; controller.close(); dialog.close(); rendered = null;
      if (previousFocus?.isConnected && !previousFocus.closest?.('[hidden]')) previousFocus.focus();
    }
    async function open(id) {
      if (destroyed || promptBusy || controller.pendingSave) return false;
      let selected; try {selected = id || getSelectedRun();} catch (_) {return false;}
      const next = typeof selected === 'string' ? selected : selected?.id;
      if (typeof next !== 'string' || !next) return false;
      if (dialog.open && controller.state.id === next) {note.focus(); return true;}
      if (dialog.open) {if (!await canDiscard()) return false; controller.close();}
      else {if (doc.querySelector('dialog[open]')) return false; previousFocus = doc.activeElement; dialog.showModal();}
      const version = ++epoch; rendered = null; note.value = ''; favorite.checked = false;
      const loaded = await controller.open(next);
      if (version === epoch && dialog.open && !destroyed) (loaded ? note : refresh).focus();
      return loaded;
    }
    trigger.addEventListener('click', () => open()); closeButton.addEventListener('click', close);
    note.addEventListener('input', () => render(controller.state)); favorite.addEventListener('change', () => render(controller.state));
    save.addEventListener('click', async () => {const version = epoch; const result = await controller.save({note: note.value, favorite: favorite.checked}); if (version === epoch && dialog.open && !destroyed) (result ? note : save).focus();});
    refresh.addEventListener('click', async () => {const version = epoch; if (!await canDiscard() || version !== epoch || destroyed || !dialog.open) return; const result = await controller.load(); if (version === epoch && dialog.open) (result ? note : refresh).focus();});
    exportButton.addEventListener('click', async () => {
      if (dirty()) {status.textContent = t('Сначала сохраните изменения, затем скачайте отчёт.'); return;}
      const version = epoch, report = await controller.report(I.language);
      if (!report || version !== epoch || destroyed || !dialog.open) return;
      let url, link;
      try {
        url = root.URL.createObjectURL(new root.Blob([report.markdown], {type: 'text/markdown;charset=utf-8'}));
        link = el('a'); link.href = url; link.download = report.filename; link.hidden = true; doc.body.append(link); link.click();
      } catch (_) {status.textContent = t('Не удалось скачать отчёт. Попробуйте ещё раз или откройте приложение в браузере.'); status.classList.add('is-error');}
      finally {link?.remove(); if (url) root.setTimeout(() => root.URL.revokeObjectURL(url), 1000);}
      exportButton.focus();
    });
    dialog.addEventListener('cancel', event => {event.preventDefault(); close();});
    dialog.addEventListener('keydown', event => {
      if (event.key === 'Escape') {event.preventDefault(); close(); return;}
      if (event.key !== 'Tab') return;
      const nodes = [...dialog.querySelectorAll('button:not(:disabled),input:not(:disabled),textarea:not(:disabled)')].filter(node => node.getClientRects().length);
      const index = nodes.indexOf(doc.activeElement), next = index + (event.shiftKey ? -1 : 1);
      if (next < 0 || next >= nodes.length) {event.preventDefault(); nodes[(next + nodes.length) % nodes.length]?.focus();}
    });
    const resize = typeof root.ResizeObserver === 'function' ? new root.ResizeObserver(() => {dialog.style.scrollPaddingTop = `${header.getBoundingClientRect().height + 12}px`;}) : null; resize?.observe(header);
    return {button: trigger, open, close, controller, destroy() {destroyed = true; epoch++; controller.destroy(); resize?.disconnect(); if (dialog.open) dialog.close(); dialog.remove(); trigger.remove();}};
  }
  const exported = {mount, createController, validNotebook, safeFilename, errorCode, MAX_NOTE}; root.CodexRunNotebook = exported;
  if (typeof module !== 'undefined' && module.exports) module.exports = exported;
})(typeof window !== 'undefined' ? window : globalThis);
