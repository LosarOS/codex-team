/* Fill the existing task editor from a saved run. Never starts execution. */
((root) => {
  'use strict';
  const fields = ['task','workspace','mode','pack','specialists','max_iterations','max_agent_calls','max_run_duration'];
  const modes = ['quick','standard','deep','audit','plan','implement'];
  const knownWarnings = ['invalid_settings','missing_workspace','security_reset'];
  const string = (value, maximum) => typeof value === 'string' && [...value].length <= maximum;
  function cleanData(value) {
    if (!value || typeof value !== 'object' || Array.isArray(value) || Object.keys(value).some(key => !fields.includes(key)) || fields.some(key => !Object.hasOwn(value,key))) return null;
    if (!string(value.task,30000) || !value.task.trim() || !string(value.workspace,4096) || !modes.includes(value.mode) || !string(value.pack,100) || !Array.isArray(value.specialists) || value.specialists.length > 50 || value.specialists.some(role => !string(role,100))) return null;
    for (const [key,min,max] of [['max_iterations',1,10],['max_agent_calls',1,100],['max_run_duration',30,86400]]) if (!Number.isInteger(value[key]) || value[key] < min || value[key] > max) return null;
    return Object.fromEntries(fields.map(key => [key,key === 'specialists' ? [...value[key]] : value[key]]));
  }
  function fingerprint(value) {return JSON.stringify(value, (_, item) => item && typeof item === 'object' && !Array.isArray(item) ? Object.fromEntries(Object.keys(item).sort().map(key => [key,item[key]])) : item);}
  const selectedId = value => typeof value === 'string' ? value : typeof value?.id === 'string' ? value.id : '';
  const labels = {
    'Повторить задачу':'Reuse task', 'Подготовка задачи…':'Preparing task…', 'Подготовить повторную задачу?':'Prepare this task again?',
    'Сохранённая задача и её параметры заменят текущую форму создания задачи, включая уже введённый текст. Выполнение не начнётся.':'The saved task and its settings will replace the current task form, including any text already entered. Execution will not start.',
    'Разрешения не копируются: стандартный доступ, изолированная рабочая копия, без автоматического коммита. Токеновый бюджет не переносится. Проверьте проект и параметры перед запуском.':'Permissions are not copied: standard access, an isolated workspace and no automatic commit. The token budget is not copied. Review the project and settings before starting.',
    'Некорректные сохранённые параметры заменены безопасными значениями.':'Invalid saved settings have been replaced with safe defaults.',
    'Рабочая папка не сохранена. Выберите проект в форме задачи.':'The workspace was not stored. Choose a project in the task form.',
    'Заполнить форму':'Fill task form', 'Задача перенесена в форму. Проверьте параметры и запустите её самостоятельно.':'The task is in the form. Review its settings and start it when ready.',
    'Не удалось заполнить форму. Проверьте её содержимое перед повторной попыткой.':'Could not fill the form. Review its contents before trying again.',
    'Нет связи с сервером. Форма задачи не изменена.':'Cannot reach the server. The task form is unchanged.',
    'Нет разрешения на чтение сохранённого запуска.':'You do not have permission to read the saved run.',
    'Запуск недоступен или не содержит задачи для повторения.':'The run is unavailable or has no task to reuse.',
    'Не удалось подготовить задачу. Форма не изменена; повторите попытку.':'Could not prepare the task. The form is unchanged; try again.',
    'Форма или выбранный запуск изменились. Повторите действие, чтобы не потерять новый ввод.':'The form or selected run changed. Try again to preserve your latest input.',
    'Форма задачи пока недоступна для изменений. Дождитесь загрузки черновика или решите конфликт сохранения.':'The task form is not ready for changes. Wait for the draft to load or resolve its save conflict.',
  };
  function createController({api,read,apply,getSelectedRun,confirm,notify = () => {},canApply = () => true,onState = () => {},t = value => value}) {
    let busy = false, destroyed = false, epoch = 0;
    const say = (label,error=true) => {if (!destroyed) notify(t(label),error);};
    const available = () => {try {return canApply() === true;} catch (_) {return false;}};
    async function replay(explicitId) {
      if (destroyed || busy) return false;
      if (!available()) {say('Форма задачи пока недоступна для изменений. Дождитесь загрузки черновика или решите конфликт сохранения.'); return false;}
      const version = ++epoch; let originalId, id, originalForm, applying = false;
      try {originalId = selectedId(getSelectedRun()); id = explicitId || originalId; originalForm = fingerprint(read());} catch (_) {say('Не удалось подготовить задачу. Форма не изменена; повторите попытку.'); return false;}
      if (!string(id,512) || !id) {say('Запуск недоступен или не содержит задачи для повторения.'); return false;}
      const current = () => !destroyed && version === epoch;
      const unchanged = () => {try {return current() && available() && selectedId(getSelectedRun()) === originalId && fingerprint(read()) === originalForm;} catch (_) {return false;}};
      busy = true; onState({busy});
      try {
        const response = await api(`/api/runs/${encodeURIComponent(id)}/replay`);
        if (!current()) return false;
        const data = cleanData(response?.data);
        if (response?.run_id !== id || !data || !Array.isArray(response.warnings) || response.warnings.length > 10 || response.warnings.some(code => !knownWarnings.includes(code))) throw new Error('Invalid replay snapshot');
        if (!unchanged()) {say('Форма или выбранный запуск изменились. Повторите действие, чтобы не потерять новый ввод.'); return false;}
        const description = [t('Сохранённая задача и её параметры заменят текущую форму создания задачи, включая уже введённый текст. Выполнение не начнётся.'),t('Разрешения не копируются: стандартный доступ, изолированная рабочая копия, без автоматического коммита. Токеновый бюджет не переносится. Проверьте проект и параметры перед запуском.')];
        if (response.warnings.includes('invalid_settings')) description.push(t('Некорректные сохранённые параметры заменены безопасными значениями.'));
        if (response.warnings.includes('missing_workspace')) description.push(t('Рабочая папка не сохранена. Выберите проект в форме задачи.'));
        if (!await confirm(t('Подготовить повторную задачу?'),description.join('\n\n'),id,t('Заполнить форму'))) return false;
        if (!current()) return false;
        if (!unchanged()) {say('Форма или выбранный запуск изменились. Повторите действие, чтобы не потерять новый ввод.'); return false;}
        applying = true; await apply(data);
        if (current()) say('Задача перенесена в форму. Проверьте параметры и запустите её самостоятельно.',false);
        return true;
      } catch (error) {
        if (current()) say(applying ? 'Не удалось заполнить форму. Проверьте её содержимое перед повторной попыткой.' : error?.status === 401 || error?.status === 403 ? 'Нет разрешения на чтение сохранённого запуска.' : error?.status === 404 ? 'Запуск недоступен или не содержит задачи для повторения.' : error?.status === 0 || error?.kind === 'network' || error instanceof TypeError ? 'Нет связи с сервером. Форма задачи не изменена.' : 'Не удалось подготовить задачу. Форма не изменена; повторите попытку.');
        return false;
      } finally {busy = false; if (current()) onState({busy});}
    }
    return {replay,get busy() {return busy;},destroy() {destroyed=true;epoch++;}};
  }
  function mount({anchor,api,read,apply,getSelectedRun,confirm,notify,canApply}) {
    if (!anchor || !root.document) return null;
    const I = root.CodexI18n || {t:value=>value,register() {}}; I.register(labels);
    const button = root.document.createElement('button'); button.type='button'; button.id='run-replay-open'; button.className='button secondary'; button.textContent=I.t('Повторить задачу'); anchor.append(button);
    const controller = createController({api,read,apply,getSelectedRun,confirm:confirm || ((title,body) => Promise.resolve(root.confirm(title+'\n\n'+body))),notify,canApply,t:source=>I.t(source),onState:({busy})=>{button.disabled=busy;button.textContent=I.t(busy?'Подготовка задачи…':'Повторить задачу');button.setAttribute('aria-busy',String(busy));}});
    button.addEventListener('click',()=>controller.replay());
    return {button,replay:controller.replay,destroy() {controller.destroy();button.remove();}};
  }
  const exported = {mount,createController,cleanData,fingerprint}; root.CodexRunReplay=exported;
  if (typeof module !== 'undefined' && module.exports) module.exports=exported;
})(typeof window !== 'undefined' ? window : globalThis);
