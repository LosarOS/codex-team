/* Durable task templates: deliberate application, revision checks, no access settings. */
"use strict";
((root) => {
  const fields = ["task", "workspace", "mode", "pack", "specialists", "max_iterations", "max_agent_calls", "max_run_duration"];
  function clean(value) {
    const result = {};
    for (const key of fields) if (value?.[key] !== undefined) result[key] = key === "specialists" ? [...value[key]] : value[key];
    return result;
  }
  function createController({api, read, onState = () => {}, limit = 20}) {
    let state = {items: [], total: 0, query: "", offset: 0, limit, selected: null, busy: false, listLoading: false, detailLoading: false, error: "", notice: ""};
    let listVersion = 0, detailVersion = 0, session = 0, active = false, destroyed = false;
    const emit = patch => { state = {...state, ...patch}; if (active && !destroyed) onState({...state}); };
    const failure = error => {
      const code = error.technical?.code || error.technical?.detail?.code;
      if (error.status === 409 && code === "template_limit") return "limit";
      if (error.status === 401 || error.status === 403) return "access";
      if ((error.status === 400 || error.status === 422) && Array.isArray(error.technical) && error.technical.some(item => item.loc?.some(part => part === "name" || part === "description"))) return "metadata";
      return error.status === 409 ? "conflict" : error.status === 404 ? "missing" : error.status === 400 || error.status === 422 ? "invalid" : error.status ? "error" : "offline";
    };
    async function list({query = state.query, offset = state.offset} = {}) {
      if (destroyed) return false;
      const version = ++listVersion, currentSession = session;
      emit({query, offset, listLoading: true, error: ""});
      try {
        const response = await api(`/api/task-templates?query=${encodeURIComponent(query)}&limit=${limit}&offset=${offset}`);
        if (!active || destroyed || currentSession !== session || version !== listVersion) return false;
        if (!Array.isArray(response?.items) || !Number.isInteger(response.total)) throw new Error("Invalid templates response");
        emit({items: response.items, total: response.total}); return true;
      } catch (error) {
        if (active && currentSession === session && version === listVersion) emit({error: failure(error)});
        return false;
      } finally { if (currentSession === session && version === listVersion) emit({listLoading: false}); }
    }
    async function select(id) {
      if (destroyed || state.busy) return false;
      const version = ++detailVersion, currentSession = session;
      emit({detailLoading: true, error: "", notice: ""});
      try {
        const response = await api(`/api/task-templates/${encodeURIComponent(id)}`);
        if (!active || destroyed || currentSession !== session || version !== detailVersion) return false;
        if (response?.id !== id || !Number.isInteger(response.revision) || !response.data) throw new Error("Invalid template response");
        emit({selected: {...response, data: clean(response.data)}}); return true;
      } catch (error) {
        if (active && currentSession === session && version === detailVersion) emit({error: failure(error)});
        return false;
      } finally { if (currentSession === session && version === detailVersion) emit({detailLoading: false}); }
    }
    async function mutate(method, {name, description, replaceData = false} = {}) {
      if (!active || destroyed || state.busy || state.detailLoading) return false;
      const selected = state.selected, currentSession = session;
      if (method !== "POST" && !selected) return false;
      const data = clean(method === "POST" || replaceData ? read() : selected?.data);
      const body = method === "DELETE" ? {} : {name, description, data};
      if (method === "PUT") body.expected_revision = selected.revision;
      const url = method === "POST" ? "/api/task-templates" : `/api/task-templates/${encodeURIComponent(selected.id)}${method === "DELETE" ? `?expected_revision=${selected.revision}` : ""}`;
      emit({busy: true, error: "", notice: ""});
      try {
        const response = await api(url, method, body);
        if (!active || destroyed || currentSession !== session) return false;
        if (method !== "DELETE" && (!response?.id || !Number.isInteger(response.revision) || !response.data)) throw new Error("Invalid template response");
        emit({selected: method === "DELETE" ? null : {...response, data: clean(response.data)}, notice: method === "DELETE" ? "deleted" : "saved"});
        await list({offset: method === "DELETE" && state.items.length === 1 ? Math.max(0, state.offset - limit) : state.offset});
        return true;
      } catch (error) {
        if (active && currentSession === session) emit({error: failure(error)});
        return false;
      } finally { emit({busy: false}); }
    }
    return {
      open() { if (destroyed) return; active = true; session++; emit({listLoading: false, detailLoading: false, error: "", notice: ""}); return list(); },
      close() { active = false; session++; listVersion++; detailVersion++; state = {...state, listLoading: false, detailLoading: false}; },
      list, select,
      newTemplate() { if (state.busy || state.detailLoading) return false; detailVersion++; emit({selected: null, error: "", notice: ""}); return true; },
      create: values => mutate("POST", values), update: values => mutate("PUT", values), remove: () => mutate("DELETE"),
      get state() { return {...state}; },
      destroy() { destroyed = true; active = false; session++; listVersion++; detailVersion++; },
    };
  }
  function mount({anchor, read, apply, api, confirm, formatValue}) {
    const I = root.CodexI18n || {t: value => value};
    I.register?.({
      "Шаблоны задач": "Task templates", "Закрыть шаблоны": "Close templates", "Сохранённые задачи для повторного использования": "Saved tasks to reuse",
      "Шаблон заполняет задачу, проект, набор агентов и лимиты. Разрешения, ключи и параметры подключения не восстанавливаются. Проверьте доступ перед запуском.": "A template fills in the task, project, agent pack and limits. Permissions, keys and connection settings are not restored. Check access before starting.",
      "Найти шаблон": "Search templates", "Поиск": "Search", "Обновить библиотеку": "Refresh library", "Из текущей задачи": "From current task",
      "Новый шаблон": "New template", "Название шаблона": "Template name", "Описание шаблона": "Template description", "Необязательно": "Optional",
      "Сохранить шаблон": "Save template", "Сохранить название и описание": "Save name and description", "Обновить из текущей задачи": "Update from current task",
      "Применить к форме": "Apply to form", "Удалить шаблон": "Delete template", "Предыдущие шаблоны": "Previous templates", "Следующие шаблоны": "Next templates",
      "Назад": "Previous", "Далее": "Next", "Шаблонов: {total}": "Templates: {total}", "{start}–{end} из {total}": "{start}–{end} of {total}",
      "Шаблонов пока нет. Сохраните текущую задачу для следующего запуска.": "No templates yet. Save the current task for a future run.",
      "По запросу ничего не найдено.": "No templates match your search.", "Загрузка шаблонов…": "Loading templates…", "Загрузка шаблона…": "Loading template…",
      "Сохранение изменений…": "Saving changes…", "Шаблон сохранён.": "Template saved.", "Шаблон удалён.": "Template deleted.",
      "Нет связи. Ввод и сохранённые шаблоны не изменены. Повторите после подключения.": "Offline. Your input and saved templates are unchanged. Retry when connected.",
      "Не удалось выполнить действие. Ввод сохранён; повторите попытку.": "Could not complete the action. Your input is preserved; please retry.",
      "Шаблон изменён в другом окне. Обновите библиотеку перед сохранением; ваш ввод остаётся в полях.": "This template changed in another window. Refresh the library before saving; your input remains in the fields.",
      "Шаблон удалён в другом окне. Ваш ввод остаётся в полях.": "This template was deleted in another window. Your input remains in the fields.",
      "Проверьте название, описание, текст задачи и лимиты.": "Check the name, description, task text and limits.",
      "Название — до 120 символов, описание — до 1000 символов. Проверьте поля и повторите.": "The name can have up to 120 characters and the description up to 1000. Check the fields and retry.",
      "В библиотеке уже 200 шаблонов. Удалите ненужный шаблон перед созданием нового. Введённые название и описание остаются в форме.": "The library already has 200 templates. Delete an unused template before creating another. Your name and description remain in the form.",
      "Нет доступа к библиотеке шаблонов. Проверьте подключение к локальному приложению. Ввод остаётся в форме.": "Access to the template library is unavailable. Check your connection to the local application. Your input remains in the form.",
      "Сначала введите задачу в основной форме.": "First enter a task in the main form.", "Введите название шаблона.": "Enter a template name.",
      "Содержимое шаблона": "Template content", "Будет сохранена текущая задача из основной формы.": "The current task from the main form will be saved.",
      "Задача": "Task", "Проект": "Project", "Режим": "Mode", "Набор агентов": "Agent pack", "Специалисты": "Specialists", "Итерации": "Iterations", "Вызовы агентов": "Agent calls", "Длительность, с": "Duration, seconds",
      "Отменить изменения шаблона?": "Discard template changes?", "Название и описание ещё не сохранены.": "The name and description have not been saved.", "Отменить изменения": "Discard changes",
      "Заменить текущую задачу шаблоном?": "Replace the current task with this template?", "Текст и параметры основной формы будут заменены. Разрешения и подключение останутся текущими. Запуск не начнётся.": "The main form text and parameters will be replaced. Current permissions and connection settings are retained. No run will start.",
      "Применить шаблон": "Apply template", "Обновить содержимое шаблона?": "Update template content?", "Сохранённая задача и параметры шаблона будут заменены текущими значениями из основной формы.": "The saved template task and parameters will be replaced with the current values from the main form.", "Обновить шаблон": "Update template",
      "Удалить этот шаблон?": "Delete this template?", "Шаблон будет удалён из библиотеки на этом компьютере. Текущая задача и запуски сохранятся.": "The template will be deleted from this computer's library. The current task and runs are retained.",
      "Выберите шаблон или сохраните текущую задачу.": "Choose a template or save the current task.",
    });
    const t = (value, params) => I.t(value, params);
    const el = (tag, cls, text) => { const node = document.createElement(tag); if (cls) node.className = cls; if (text) node.textContent = t(text); return node; };
    const button = (text, cls = "secondary") => { const node = el("button", `button ${cls}`, text); node.type = "button"; return node; };
    const trigger = button("Шаблоны задач"); trigger.id = "task-templates-open"; trigger.setAttribute("aria-haspopup", "dialog"); anchor.append(trigger);
    const dialog = el("dialog", "task-templates-dialog"); dialog.id = "task-templates-dialog"; dialog.setAttribute("aria-labelledby", "task-templates-title"); dialog.setAttribute("aria-describedby", "task-templates-safety");
    const header = el("header", "task-templates-header"), heading = el("div");
    const eyebrow = el("p", "eyebrow", "Сохранённые задачи для повторного использования"), title = el("h2", "", "Шаблоны задач"); title.id = "task-templates-title";
    heading.append(eyebrow, title); const close = button("Закрыть шаблоны", "text-button"); close.id = "task-templates-close"; header.append(heading, close);
    const safety = el("p", "task-templates-safety", "Шаблон заполняет задачу, проект, набор агентов и лимиты. Разрешения, ключи и параметры подключения не восстанавливаются. Проверьте доступ перед запуском."); safety.id = "task-templates-safety";
    const status = el("p", "task-templates-status"); status.setAttribute("role", "status"); status.setAttribute("aria-live", "polite");
    const error = el("p", "form-error"); error.id = "task-templates-error"; error.setAttribute("role", "alert"); error.hidden = true;
    const tools = el("div", "task-templates-toolbar");
    const searchForm = el("form", "task-templates-search"), search = el("input"); search.type = "search"; search.maxLength = 200; search.id = "task-templates-query"; search.placeholder = t("Найти шаблон"); search.setAttribute("aria-label", t("Найти шаблон"));
    const searchButton = button("Поиск"); searchButton.type = "submit"; searchForm.append(search, searchButton);
    const refresh = button("Обновить библиотеку", "text-button"), create = button("Из текущей задачи"); create.id = "task-templates-new"; tools.append(searchForm, refresh, create);
    const content = el("div", "task-templates-content"), library = el("section", "task-templates-library"); library.setAttribute("aria-label", t("Шаблоны задач"));
    const list = el("ul", "task-templates-list"), empty = el("p", "task-templates-empty");
    const pagination = el("div", "task-templates-pagination"), previous = button("Назад", "text-button"), next = button("Далее", "text-button"), count = el("span"); previous.setAttribute("aria-label", t("Предыдущие шаблоны")); next.setAttribute("aria-label", t("Следующие шаблоны")); pagination.append(previous, count, next); library.append(list, empty, pagination);
    const editor = el("section", "task-templates-editor"); editor.setAttribute("aria-label", t("Содержимое шаблона"));
    const editorTitle = el("h3", "", "Выберите шаблон или сохраните текущую задачу.");
    const metadata = el("form", "task-templates-metadata");
    const nameLabel = el("label", "", "Название шаблона"), name = el("input"); name.id = "task-template-name"; name.maxLength = 120; name.required = true; nameLabel.htmlFor = name.id;
    const descriptionLabel = el("label", "", "Описание шаблона"), description = el("textarea"); description.id = "task-template-description"; description.maxLength = 1000; description.rows = 3; description.placeholder = t("Необязательно"); descriptionLabel.htmlFor = description.id;
    const previewHint = el("p", "task-templates-hint"), preview = el("pre", "task-templates-preview"); preview.setAttribute("aria-label", t("Содержимое шаблона"));
    const actions = el("div", "task-templates-actions"), save = button("Сохранить шаблон", "primary"), update = button("Обновить из текущей задачи"), use = button("Применить к форме"), remove = button("Удалить шаблон", "text-button"); save.id = "task-template-save"; save.type = "submit"; use.id = "task-template-apply"; update.id = "task-template-update"; remove.id = "task-template-delete";
    actions.append(save, update, use, remove); metadata.append(nameLabel, name, descriptionLabel, description, previewHint, preview, actions); editor.append(editorTitle, metadata); content.append(library, editor); dialog.append(header, safety, tools, status, error, content); document.body.append(dialog);
    const measureHeader = () => dialog.style.setProperty("--task-templates-header-height", `${Math.ceil(header.getBoundingClientRect().height + 12)}px`);
    const headerResize = root.ResizeObserver ? new root.ResizeObserver(measureHeader) : null;
    headerResize?.observe(header);
    let state, controller, shown = false, destroyed = false, pending = false, creating = false, populated = null, savedName = "", savedDescription = "", listIdentity = null, returnFocus = null, localError = "", nextFocus = null;
    const dirty = () => (creating || !!state?.selected) && (name.value !== savedName || description.value !== savedDescription);
    const ask = (title, body, accept) => confirm ? confirm(t(title), t(body), "", t(accept)) : Promise.resolve(root.confirm(`${t(title)}\n\n${t(body)}`));
    const discard = () => !dirty() || ask("Отменить изменения шаблона?", "Название и описание ещё не сохранены.", "Отменить изменения");
    const errors = {limit: "В библиотеке уже 200 шаблонов. Удалите ненужный шаблон перед созданием нового. Введённые название и описание остаются в форме.", access: "Нет доступа к библиотеке шаблонов. Проверьте подключение к локальному приложению. Ввод остаётся в форме.", offline: "Нет связи. Ввод и сохранённые шаблоны не изменены. Повторите после подключения.", error: "Не удалось выполнить действие. Ввод сохранён; повторите попытку.", conflict: "Шаблон изменён в другом окне. Обновите библиотеку перед сохранением; ваш ввод остаётся в полях.", missing: "Шаблон удалён в другом окне. Ваш ввод остаётся в полях.", metadata: "Название — до 120 символов, описание — до 1000 символов. Проверьте поля и повторите.", invalid: "Проверьте название, описание, текст задачи и лимиты."};
    const previewValue = (key, value) => {
      const formatted = formatValue?.(key, value);
      return formatted === undefined ? Array.isArray(value) ? value.join(", ") : String(value) : String(formatted);
    };
    const previewData = data => fields.filter(key => data[key] !== undefined).map(key => `${t({task:"Задача",workspace:"Проект",mode:"Режим",pack:"Набор агентов",specialists:"Специалисты",max_iterations:"Итерации",max_agent_calls:"Вызовы агентов",max_run_duration:"Длительность, с"}[key])}: ${previewValue(key, data[key])}`).join("\n\n");
    function render(value = state) {
      state = value;
      const blocked = pending || value.busy || value.detailLoading;
      dialog.setAttribute("aria-busy", String(value.busy || value.detailLoading || value.listLoading));
      const selected = value.selected;
      if (selected !== populated) {
        populated = selected; creating = false;
        name.value = selected?.name || ""; description.value = selected?.description || "";
        savedName = name.value; savedDescription = description.value;
      }
      metadata.hidden = !creating && !selected;
      editorTitle.textContent = creating ? t("Новый шаблон") : selected?.name || t("Выберите шаблон или сохраните текущую задачу.");
      previewHint.textContent = creating ? t("Будет сохранена текущая задача из основной формы.") : t("Содержимое шаблона");
      preview.textContent = previewData(creating ? clean(read()) : selected?.data || {});
      save.textContent = t(creating ? "Сохранить шаблон" : "Сохранить название и описание");
      for (const node of [update, use, remove]) node.hidden = creating || !selected;
      for (const node of [name, description, save, update, use, remove, create, refresh, search, searchButton, close]) node.disabled = blocked;
      previous.disabled = blocked || value.listLoading || value.offset === 0;
      next.disabled = blocked || value.listLoading || value.offset + value.limit >= value.total;
      if (value.items !== listIdentity) {
        listIdentity = value.items; list.replaceChildren();
        for (const item of value.items) {
          const row = el("li"), itemButton = button("", "task-template-choice"), itemTitle = el("strong"), itemDescription = el("span");
          itemButton.dataset.templateId = item.id; itemTitle.textContent = item.name; itemDescription.textContent = item.description || ""; itemButton.append(itemTitle, itemDescription);
          itemButton.addEventListener("click", () => act(async () => { if (item.id === state.selected?.id || !await discard()) return; await controller.select(item.id); if (state.selected?.id === item.id) nextFocus = name; }));
          row.append(itemButton); list.append(row);
        }
      }
      for (const node of list.querySelectorAll("button")) { node.disabled = blocked; node.setAttribute("aria-pressed", String(node.dataset.templateId === selected?.id)); }
      empty.hidden = value.items.length > 0 || value.listLoading;
      empty.textContent = t(value.query ? "По запросу ничего не найдено." : "Шаблонов пока нет. Сохраните текущую задачу для следующего запуска.");
      count.textContent = value.total ? t("{start}–{end} из {total}", {start:value.offset + 1, end:Math.min(value.offset + value.items.length, value.total), total:value.total}) : t("Шаблонов: {total}", {total:0});
      const message = value.busy ? "Сохранение изменений…" : value.detailLoading ? "Загрузка шаблона…" : value.listLoading ? "Загрузка шаблонов…" : value.notice === "saved" ? "Шаблон сохранён." : value.notice === "deleted" ? "Шаблон удалён." : "";
      status.textContent = message ? t(message) : ""; error.hidden = !value.error && !localError; error.textContent = localError ? t(localError) : value.error ? t(errors[value.error] || errors.error) : "";
    }
    async function act(handler) {
      if (pending || state?.busy || state?.detailLoading || destroyed || !shown) return;
      const previousFocus = document.activeElement;
      pending = true; localError = ""; nextFocus = null; render();
      try { await handler(); } catch (_) { if (shown && !destroyed) { localError = errors.error; render(); } }
      finally {
        pending = false;
        if (!destroyed) {
          render();
          if (shown) {
            const available = node => node?.isConnected && !node.disabled && node.getClientRects().length;
            // Busy controls cannot receive focus. Restore it only after enabling them.
            let target = available(nextFocus) ? nextFocus : null;
            if (!target && (!dialog.contains(document.activeElement) || document.activeElement === dialog)) {
              target = available(previousFocus) ? previousFocus : available(name) ? name : search;
            }
            target?.focus();
          }
        }
        nextFocus = null;
      }
    }
    controller = createController({api, read, onState: render}); state = controller.state; render();
    function hide() { shown = false; creating = false; populated = undefined; controller.close(); dialog.close(); returnFocus?.focus(); }
    async function requestClose() { return act(async () => { if (await discard()) hide(); }); }
    function open() {
      if (destroyed || shown) return;
      shown = true; returnFocus = document.activeElement; dialog.showModal(); measureHeader(); controller.open(); search.focus();
    }
    trigger.addEventListener("click", open); close.addEventListener("click", requestClose);
    dialog.addEventListener("cancel", event => { event.preventDefault(); requestClose(); });
    dialog.addEventListener("close", () => { if (shown) { shown = false; controller.close(); returnFocus?.focus(); } });
    // Native modal focus containment also supports nested confirmation dialogs.
    dialog.addEventListener("keydown", event => {
      if (event.key !== "Tab" || document.querySelector("dialog[open]:last-of-type") !== dialog) return;
      const nodes = [...dialog.querySelectorAll('button:not(:disabled),input:not(:disabled),textarea:not(:disabled),[tabindex="0"]')].filter(node => !node.hidden && node.getClientRects().length);
      if (!nodes.length) { event.preventDefault(); return; }
      if (event.shiftKey && document.activeElement === nodes[0]) { event.preventDefault(); nodes.at(-1).focus(); }
      else if (!event.shiftKey && document.activeElement === nodes.at(-1)) { event.preventDefault(); nodes[0].focus(); }
    });
    searchForm.addEventListener("submit", event => { event.preventDefault(); if (!pending && !state.busy && !state.detailLoading) controller.list({query:search.value.trim(), offset:0}); });
    previous.addEventListener("click", () => controller.list({offset:Math.max(0, state.offset - state.limit)})); next.addEventListener("click", () => controller.list({offset:state.offset + state.limit}));
    refresh.addEventListener("click", () => act(async () => { if (!await discard()) return; const id = state.selected?.id; await controller.list(); if (id) await controller.select(id); }));
    create.addEventListener("click", () => act(async () => {
      if (!await discard()) return;
      controller.newTemplate(); creating = true; name.value = ""; description.value = ""; savedName = ""; savedDescription = ""; render(); nextFocus = name;
    }));
    function values() { return {name:name.value.trim(), description:description.value.trim()}; }
    function validate(needsTask) {
      if (!name.value.trim()) { localError = "Введите название шаблона."; nextFocus = name; return false; }
      if (name.value.length > 120 || description.value.length > 1000) {
        localError = errors.metadata; nextFocus = name.value.length > 120 ? name : description; return false;
      }
      if (needsTask && !read()?.task?.trim()) { localError = "Сначала введите задачу в основной форме."; return false; }
      return true;
    }
    metadata.addEventListener("submit", event => { event.preventDefault(); act(async () => { if (!validate(creating)) return; const wasCreating = creating; if (wasCreating) await controller.create(values()); else await controller.update(values()); }); });
    update.addEventListener("click", () => act(async () => { if (!validate(true)) return; if (await ask("Обновить содержимое шаблона?", "Сохранённая задача и параметры шаблона будут заменены текущими значениями из основной формы.", "Обновить шаблон")) await controller.update({...values(), replaceData:true}); }));
    use.addEventListener("click", () => act(async () => {
      const selected = state.selected; if (!selected) return;
      if (read()?.task?.trim() && !await ask("Заменить текущую задачу шаблоном?", "Текст и параметры основной формы будут заменены. Разрешения и подключение останутся текущими. Запуск не начнётся.", "Применить шаблон")) return;
      if (!await discard() || destroyed || !shown || state.selected !== selected) return;
      apply(clean(selected.data)); hide();
    }));
    remove.addEventListener("click", () => act(async () => { if (await ask("Удалить этот шаблон?", "Шаблон будет удалён из библиотеки на этом компьютере. Текущая задача и запуски сохранятся.", "Удалить шаблон")) { if (await controller.remove()) { creating = false; render(); } } }));
    return {open, close:requestClose, controller, button:trigger, dialog,
      destroy() { destroyed = true; shown = false; controller.destroy(); headerResize?.disconnect(); if (dialog.open) dialog.close(); dialog.remove(); trigger.remove(); returnFocus?.focus(); },
    };
  }
  root.CodexTaskTemplates = {clean, createController, mount};
})(typeof window !== "undefined" ? window : globalThis);
