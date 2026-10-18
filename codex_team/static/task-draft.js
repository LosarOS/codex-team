/* Durable compose drafts. Explicit restoration, optimistic writes, no credentials or permissions. */
"use strict";
((root) => {
  const fields = ["task", "workspace", "mode", "pack", "specialists", "max_iterations", "max_agent_calls", "max_run_duration"];
  function clean(value) {
    const result = {};
    for (const key of fields) if (value?.[key] !== undefined) result[key] = key === "specialists" ? [...value[key]] : value[key];
    return result;
  }
  function createController({api, read, apply, onState = () => {}, delay = 600, schedule = setTimeout, unschedule = clearTimeout}) {
    let revision = null, remote = null, version = 0, dirty = false, timer = null, operation = null;
    let status = "loading", error = "", destroyed = false, conflict = false, hasSaved = false, savedData = null;
    const current = () => clean(read());
    const emit = (next = status, reason = "") => {
      status = next; error = reason;
      if (!destroyed) onState({status, error, remote, dirty, busy: !!operation, revision, version});
    };
    const cancelTimer = () => { if (timer !== null) unschedule(timer); timer = null; };
    function queueSave() {
      cancelTimer();
      if (!destroyed && dirty && revision !== null && !remote && !conflict) timer = schedule(() => { timer = null; flush(); }, delay);
    }
    async function load() {
      if (operation) return operation;
      const work = (async () => {
        emit("loading");
        try {
          const response = await api("/api/task-draft");
          if (destroyed) return;
          if (!Number.isInteger(response?.revision) || response.revision < 0) throw new Error("Invalid draft revision");
          revision = response.revision; remote = response.draft || null; hasSaved = !!remote; savedData = null;
          conflict = !!remote && dirty;
          emit(remote ? (conflict ? "conflict" : "available") : dirty ? "unsaved" : "empty");
        } catch (failure) { emit("offline", failure.message); }
      })();
      operation = work; emit();
      try { await work; } finally { operation = null; emit(); queueSave(); }
    }
    function changed() {
      if (destroyed) return;
      version++; dirty = true;
      emit(remote || conflict ? (conflict ? "conflict" : "available") : "unsaved");
      queueSave();
    }
    async function flush() {
      cancelTimer();
      if (operation) return operation;
      if (destroyed || !dirty || revision === null || remote || conflict) return;
      const sentVersion = version, data = current(), expected = revision;
      if (!data.task?.trim() && !hasSaved) { dirty = false; emit("empty"); return; }
      if (savedData !== null && savedData === JSON.stringify(data)) { dirty = false; emit(hasSaved ? "saved" : "empty"); return; }
      if (data.task?.trim() && [["max_iterations", 1, 10], ["max_agent_calls", 1, 100], ["max_run_duration", 30, 86400]].some(([key, min, max]) => data[key] !== undefined && (!Number.isInteger(data[key]) || data[key] < min || data[key] > max))) { emit("invalid"); return; }
      const work = (async () => {
        emit("saving");
        try {
          const response = data.task?.trim()
            ? await api("/api/task-draft", "PUT", {expected_revision: expected, data})
            : await api(`/api/task-draft?expected_revision=${expected}`, "DELETE", {});
          if (destroyed) return;
          if (!Number.isInteger(response?.revision) || response.revision < expected) throw new Error("Invalid draft revision");
          revision = response.revision; hasSaved = !!data.task?.trim(); savedData = JSON.stringify(data);
          dirty = version !== sentVersion;
          emit(dirty ? "unsaved" : data.task?.trim() ? "saved" : "empty");
        } catch (failure) {
          if (failure.status === 409) { conflict = true; emit("conflict"); }
          else emit(failure.status && failure.status !== 0 ? "error" : "offline", failure.message);
        }
      })();
      operation = work; emit();
      try { await work; } finally {
        operation = null; emit();
        // Failed writes wait for a deliberate retry / reconnect, never a busy retry loop.
        if (dirty && status === "unsaved") queueSave();
      }
    }
    async function restore() {
      if (operation || !remote || destroyed) return false;
      cancelTimer();
      apply(clean(remote.data)); savedData = JSON.stringify(current()); remote = null; conflict = false; dirty = false; version++;
      emit("restored"); return true;
    }
    async function keepCurrent() {
      if (operation || destroyed) return;
      // Refresh the latest version first: explicitly replacing a draft must still use CAS.
      if (conflict && !remote) { await load(); if (!remote && status === "offline") return; }
      remote = null; conflict = false; dirty = true; emit("unsaved"); await flush();
    }
    async function clear({ifVersion = version, consuming = false} = {}) {
      cancelTimer();
      if (operation) await operation;
      if (destroyed || version !== ifVersion || (consuming && (remote || conflict))) return false;
      if (revision === null) { emit("offline"); return false; }
      const expected = revision;
      const work = (async () => {
        emit("saving");
        try {
          const response = await api(`/api/task-draft?expected_revision=${expected}`, "DELETE", {});
          if (destroyed) return false;
          if (!Number.isInteger(response?.revision) || response.revision < expected) throw new Error("Invalid draft revision");
          revision = response.revision; remote = null; conflict = false; hasSaved = false; savedData = null;
          dirty = version !== ifVersion;
          emit(dirty ? "unsaved" : "empty"); return true;
        } catch (failure) {
          if (failure.status === 409) { conflict = true; emit("conflict"); }
          else emit(failure.status && failure.status !== 0 ? "error" : "offline", failure.message);
          return false;
        }
      })();
      operation = work; emit();
      try { return await work; } finally { operation = null; emit(); if (dirty && status === "unsaved") queueSave(); }
    }
    async function retry() {
      if (operation || destroyed) return;
      if (revision === null || conflict) await load(); else await flush();
    }
    return {load, changed, flush, restore, keepCurrent, clear, retry,
      checkpoint: () => ({version}),
      consume: (checkpoint) => clear({ifVersion: checkpoint.version, consuming: true}),
      get dirty() { return dirty; },
      get version() { return version; },
      destroy() { destroyed = true; cancelTimer(); },
    };
  }
  function mount({form, read, apply, api, confirm}) {
    const I = root.CodexI18n || {t: value => value};
    I.register?.({
      "Черновик задачи": "Task draft",
      "Черновик не сохранён: проверьте числовые лимиты.": "Draft not saved: check the numeric limits.",
      "Не удалось сохранить черновик. Проверьте поля и повторите.": "Could not save the draft. Check the fields and retry.", "Проверяем сохранённый черновик…": "Checking for a saved draft…",
      "Черновик сохраняется…": "Saving draft…", "Изменения ещё не сохранены": "Changes are not saved yet",
      "Черновик сохранён на этом компьютере": "Draft saved on this computer",
      "Есть сохранённый черновик. Восстановите его или сохраните текущую задачу вместо него.": "A saved draft is available. Restore it or replace it with the current task.",
      "Черновик изменён в другом окне. Ваш ввод сохранён в форме. Выберите, какую версию оставить.": "The draft changed in another window. Your input remains in the form. Choose which version to keep.",
      "Нет связи: ввод остаётся в форме. Повторите сохранение после подключения.": "Offline: your input remains in the form. Retry saving when connected.",
      "Черновик восстановлен. Проверьте проект и уровень доступа перед запуском.": "Draft restored. Check the project and access level before starting.",
      "Сохранённого черновика нет": "No saved draft", "Восстановить черновик": "Restore draft",
      "Сохранить текущую задачу": "Save current task", "Удалить сохранённый черновик": "Delete saved draft",
      "Повторить сохранение": "Retry saving", "Заменить текущий ввод черновиком?": "Replace your current input with the draft?",
      "Текущий текст в форме будет заменён. Разрешения и подключение не восстанавливаются из черновика.": "The current form text will be replaced. Permissions and connection settings are not restored from a draft.",
      "Восстановить": "Restore", "Заменить сохранённый черновик?": "Replace the saved draft?",
      "Вместо сохранённого черновика будет записана текущая задача из формы.": "The current task in the form will replace the saved draft.",
      "Заменить": "Replace", "Удалить черновик с этого компьютера?": "Delete the draft from this computer?",
      "Текущий ввод в форме и запуски останутся без изменений.": "Your current form input and runs will remain unchanged.",
      "Удалить черновик": "Delete draft", "Обновить черновик": "Refresh draft",
    });
    const el = (tag, cls, text) => { const value = document.createElement(tag); value.className = cls; if (text) value.textContent = I.t(text); return value; };
    const panel = el("section", "task-draft-panel"); panel.setAttribute("aria-label", I.t("Черновик задачи"));
    const status = el("p", "task-draft-status"); status.id = "task-draft-status"; status.setAttribute("role", "status"); status.setAttribute("aria-live", "polite");
    const actions = el("div", "task-draft-actions button-row"); panel.append(status, actions); form.prepend(panel);
    let latest = {}, controller;
    const buttons = {};
    const action = (name, text, handler) => {
      const button = el("button", "button text-button", text); button.type = "button"; button.id = `task-draft-${name}`;
      button.addEventListener("click", handler); actions.append(button); buttons[name] = button; return button;
    };
    const ask = (title, description, actionLabel) => confirm ? confirm(I.t(title), I.t(description), "", I.t(actionLabel)) : Promise.resolve(false);
    action("restore", "Восстановить черновик", async () => {
      if (latest.dirty && !await ask("Заменить текущий ввод черновиком?", "Текущий текст в форме будет заменён. Разрешения и подключение не восстанавливаются из черновика.", "Восстановить")) return;
      await controller.restore();
    });
    action("keep", "Сохранить текущую задачу", async () => {
      if (await ask("Заменить сохранённый черновик?", "Вместо сохранённого черновика будет записана текущая задача из формы.", "Заменить")) await controller.keepCurrent();
    });
    action("clear", "Удалить сохранённый черновик", async () => {
      if (await ask("Удалить черновик с этого компьютера?", "Текущий ввод в форме и запуски останутся без изменений.", "Удалить черновик")) await controller.clear();
    });
    action("retry", "Повторить сохранение", () => controller.retry());
    action("refresh", "Обновить черновик", () => controller.load());
    const labels = {invalid:"Черновик не сохранён: проверьте числовые лимиты.",error:"Не удалось сохранить черновик. Проверьте поля и повторите.",loading:"Проверяем сохранённый черновик…",saving:"Черновик сохраняется…",unsaved:"Изменения ещё не сохранены",saved:"Черновик сохранён на этом компьютере",available:"Есть сохранённый черновик. Восстановите его или сохраните текущую задачу вместо него.",conflict:"Черновик изменён в другом окне. Ваш ввод сохранён в форме. Выберите, какую версию оставить.",offline:"Нет связи: ввод остаётся в форме. Повторите сохранение после подключения.",restored:"Черновик восстановлен. Проверьте проект и уровень доступа перед запуском.",empty:"Сохранённого черновика нет"};
    controller = createController({api, read, apply, onState(value) {
      latest = value; panel.dataset.state = value.status; const text = I.t(labels[value.status]); if (status.textContent !== text) status.textContent = text;
      buttons.restore.hidden = !value.remote; buttons.keep.hidden = !value.remote && !["conflict"].includes(value.status);
      buttons.clear.hidden = value.revision === null || ["empty", "loading"].includes(value.status);
      buttons.retry.hidden = !["offline", "error", "invalid"].includes(value.status); buttons.refresh.hidden = value.status !== "conflict" || !!value.remote;
      for (const button of Object.values(buttons)) button.disabled = value.busy;
    }});
    const update = event => {
      if (["task", "workspace", "run-mode", "run-pack", "max-iterations", "max-calls", "max-duration"].includes(event.target.id) || event.target.closest?.("#specialist-options")) controller.changed();
    };
    form.addEventListener("input", update); form.addEventListener("change", update);
    root.addEventListener("online", () => controller.retry());
    status.textContent = I.t(labels.loading);
    document.addEventListener("visibilitychange", () => { if (document.hidden) controller.flush(); });
    return controller;
  }
  root.CodexTaskDraft = {createController, mount};
})(typeof window !== "undefined" ? window : globalThis);
