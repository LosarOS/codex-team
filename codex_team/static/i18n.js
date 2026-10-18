/* Local-only, opt-in UI localization. User tasks, paths, logs and API payloads are never scanned. */
((root) => {
  'use strict';
  const catalog = Object.assign(Object.create(null), root.CodexI18nCatalog || {});
  let language = 'ru';
  let dirty = false;
  try { const saved = root.localStorage?.getItem('codex-team-language'); if (saved === 'en' || saved === 'ru') language = saved; } catch (_) { /* restricted storage */ }
  function t(source, params) {
    if (typeof source !== 'string') return source;
    let value = language === 'en' && Object.prototype.hasOwnProperty.call(catalog, source) ? catalog[source] : source;
    if (params) value = value.replace(/\{([\w]+)\}/g, (match, key) => Object.prototype.hasOwnProperty.call(params, key) ? String(params[key]) : match);
    return value;
  }
  function tr(parts, ...values) {
    const key = parts.reduce((result, part, index) => result + part + (index < values.length ? `{${index}}` : ''), '');
    return t(key, Object.fromEntries(values.map((value, index) => [String(index), value])));
  }
  function setLanguage(value) {
    if (!['ru','en'].includes(value)) throw new Error('Unsupported UI language');
    language = value;
    try { root.localStorage?.setItem('codex-team-language', value); } catch (_) { /* restricted storage */ }
    if (root.document) root.document.documentElement.lang = value;
  }
  const api = {hasUnsavedChanges:()=>dirty,t, translate:t, tr, setLanguage, register(values) { Object.assign(catalog, values); }, get language() { return language; }, get locale() { return language === 'en' ? 'en-US' : 'ru-RU'; }};
  root.CodexI18n = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  const doc = root.document;
  if (!doc) return;
  doc.documentElement.lang = language;
  // This script runs before app.js/suite.js. Only authored initial HTML is localized.
  // No observer is installed, so repository output and user-entered text stay byte-for-byte intact.
  const walker = doc.createTreeWalker(doc.documentElement, 4);
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    if (['SCRIPT','STYLE','TEXTAREA','PRE','CODE'].includes(node.parentElement?.tagName)) continue;
    const source = node.nodeValue.trim();
    if (Object.prototype.hasOwnProperty.call(catalog, source)) node.nodeValue = node.nodeValue.replace(source, t(source));
  }
  for (const node of doc.querySelectorAll('[placeholder],[title],[aria-label]')) {
    for (const attr of ['placeholder','title','aria-label']) if (node.hasAttribute(attr)) node.setAttribute(attr, t(node.getAttribute(attr)));
  }
  const selector = doc.getElementById('settings-language');
  if (selector) {
    selector.value = language;
    // Changing language rebuilds constant label maps. Explicit confirmation protects unsaved forms.
    doc.addEventListener('input', event => { if (event.target !== selector && event.target.matches('input,textarea,select')) dirty = true; });
    selector.addEventListener('change', async () => {
      const next = selector.value;
      if (dirty && !root.confirm(t('Изменение языка перезагрузит интерфейс. Несохранённые изменения форм будут потеряны. Продолжить?'))) { selector.value = language; return; }
      selector.disabled = true;
      try {
        await root.CodexApi.request('/api/settings', 'POST', {language:next});
        setLanguage(next);
        root.sessionStorage?.setItem('codex-language-switching', '1');
        root.location.reload();
      } catch (error) {
        selector.value = language;
        const notice = doc.getElementById('appearance-form-error');
        if (notice) { notice.hidden = false; notice.textContent = error.message || t('Не удалось сохранить язык интерфейса.'); }
      } finally { selector.disabled = false; }
    });
  }
})(typeof window !== 'undefined' ? window : globalThis);
