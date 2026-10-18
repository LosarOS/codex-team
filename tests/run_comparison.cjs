/* Snapshot requests must remain read-only and stale responses must not replace a new pair. */
'use strict';
const assert = require('assert/strict'), fs = require('fs'), path = require('path');
const sourceRoot = process.argv.find(arg => !arg.startsWith('-') && arg.endsWith('/static')) || path.join(__dirname, '../codex_team/static');
const {createController, runChoices, numeric, errorCode} = require(path.resolve(sourceRoot, 'run-comparison.js'));
const deferred = () => {let resolve, reject; const promise = new Promise((a, b) => {resolve = a; reject = b;}); return {resolve, reject, promise};};
const run = (id, extras = {}) => ({id, task: 'Task ' + id, state: 'COMPLETED', workspace: '/repo', mode: 'standard', pack: 'default', access_level: 'read-only', calls: 0, measured_tokens: null, usage_complete: false, duration_seconds: null, changed_files_count: null, stages: [], ...extras});
const snapshot = (left, right) => ({left: run(left), right: run(right), comparable_project: true, warnings: ['incomplete_usage']});
async function pureTests() {
  assert.deepEqual(runChoices([null, {}, {id: 5}, run('1'), run('1'), run('2', {task: 'Проверка входа', workspace: 'D:\\Иван\\auth'})], 'ВХОДА иван').map(row => row.id), ['2']);
  assert.equal(runChoices([run('1'), run('1')]).length, 1);
  for (const invalid of [null, undefined, '0', NaN, Infinity, -1]) assert.equal(numeric(invalid), false);
  assert.equal(numeric(0), true);
  assert.equal(errorCode({status: 403}), 'permission'); assert.equal(errorCode({status: 404}), 'missing'); assert.equal(errorCode({status: 0}), 'offline');
  const requests = [], states = [];
  const controller = createController({api: (...args) => {const pending = deferred(); requests.push({args, ...pending}); return pending.promise;}, onState: state => states.push(state)});
  await controller.choose('left', 'a&x=unsafe'); assert.equal(requests.length, 0);
  const first = controller.choose('right', 'b'); assert.equal(requests.length, 1); assert.equal(controller.state.busy, true);
  const firstUrl = new URL(requests[0].args[0], 'http://localhost'); assert.equal(firstUrl.pathname, '/api/run-comparison'); assert.equal(firstUrl.searchParams.get('left'), 'a&x=unsafe'); assert.equal(requests[0].args.length, 1, 'comparison only uses default GET; no body or mutation');
  const second = controller.choose('right', 'c'); requests[1].resolve(snapshot('a&x=unsafe', 'c')); await second;
  requests[0].resolve(snapshot('a&x=unsafe', 'b')); await first; assert.equal(controller.state.data.right.id, 'c', 'late old pair cannot replace current pair');
  const failedOld = controller.refresh(), fresh = controller.choose('right', 'd'); requests[3].resolve(snapshot('a&x=unsafe', 'd')); await fresh;
  requests[2].reject({status: 403}); await failedOld; assert.equal(controller.state.error, '', 'late failure cannot hide current successful pair');
  const swapped = controller.swap(); assert.equal(controller.state.left, 'd'); requests[4].resolve(snapshot('d', 'a&x=unsafe')); await swapped;
  await controller.choose('right', 'd'); assert.equal(requests.length, 5, 'same run on both sides never fetches'); assert.equal(controller.state.data, null);
  await controller.choose('right', ''); assert.equal(requests.length, 5);
  const denied = controller.choose('right', 'e'); requests[5].reject({status: 403}); await denied; assert.equal(controller.state.error, 'permission'); assert.equal(controller.state.busy, false);
  const offline = controller.refresh(); requests[6].reject({status: 0}); await offline; assert.equal(controller.state.error, 'offline');
  const malformed = controller.refresh(); requests[7].resolve(snapshot('wrong', 'e')); await malformed; assert.equal(controller.state.error, 'error'); assert.equal(controller.state.data, null);
  const cancelled = controller.refresh(); controller.cancel(); requests[8].resolve(snapshot('d', 'e')); await cancelled; assert.equal(controller.state.data, null, 'closed dialog ignores in-flight responses');
  const destroyed = controller.refresh(); const emitted = states.length; controller.destroy(); requests[9].resolve(snapshot('d', 'e')); await destroyed; assert.equal(states.length, emitted, 'unmounted UI receives no late updates');
  await controller.choose('right', 'z'); await controller.refresh(); assert.equal(requests.length, 10, 'destroyed controller never requests again');
  console.log('PASS: loaded-run search, null/zero facts, encoded GET-only requests, pair swaps, explicit refresh, permissions/offline, malformed data, stale success/failure and destroyed state.');
}
async function browserTests() {
  const {chromium} = require('playwright');
  const browser = await chromium.launch({executablePath: process.env.CHROMIUM_PATH || '/usr/bin/chromium', headless: true, args: ['--no-sandbox']});
  try {
    const page = await browser.newPage({viewport: {width: 1100, height: 900}});
    const injection = '<img src=x onerror=alert(1)> & literal';
    async function setup(page, language = 'ru', formatRoles = false) {
      await page.setContent('<!doctype html><html><head></head><body><div id="toolbar"></div><main id="main" tabindex="-1"></main><dialog id="other"><button>Other modal</button></dialog></body></html>');
      await page.addStyleTag({content: fs.readFileSync(path.resolve(sourceRoot, 'style.css'), 'utf8')});
      await page.addStyleTag({content: fs.readFileSync(path.resolve(sourceRoot, 'run-comparison.css'), 'utf8')});
      await page.addScriptTag({content: fs.readFileSync(path.resolve(sourceRoot, 'i18n.js'), 'utf8')});
      await page.evaluate(language => window.CodexI18n.setLanguage(language), language);
      await page.addScriptTag({content: fs.readFileSync(path.resolve(sourceRoot, 'run-comparison.js'), 'utf8')});
      await page.evaluate(({runs, result, formatRoles}) => {
        window.loadedRuns = runs; window.result = result; window.requests = []; window.opened = []; window.failure = null;
        window.mounted = window.CodexRunComparison.mount({anchor: document.querySelector('#toolbar'), getRuns: () => window.loadedRuns, getSelectedRun: () => 'b', formatRole: formatRoles ? role => role === 'qa' ? 'QA review' : role : undefined,
          openRun: id => {window.opened.push(id); document.querySelector('#main').focus();}, api: async (...args) => {window.requests.push(args); if (window.hold) await new Promise(resolve => window.release = resolve); if (window.failure) throw window.failure; const query = new URL(args[0], 'http://localhost').searchParams; return {...window.result, left: {...window.result.left, id: query.get('left')}, right: {...window.result.right, id: query.get('right')}};}});
      }, {formatRoles, runs: [run('a', {task: 'Fix entry'}), run('b', {task: injection})], result: {...snapshot('b', 'a'), left: run('b', {task: injection, calls: 0, stages: [{role: 'qa', verdict: 'FAIL', summary: injection, error: null, attempts: 2}]}), right: run('a', {state: 'RUNNING', calls: null, measured_tokens: 42}), comparable_project: false, warnings: ['different_projects', 'active_runs_partial', 'incomplete_usage', 'stage_history_truncated']}});
    }
    await setup(page);
    const trigger = page.getByRole('button', {name: 'Сравнить запуски', exact: true}); await trigger.click();
    assert.equal(await page.locator('#run-comparison-left').inputValue(), 'b', 'actual selected run is baseline');
    assert.equal(await page.locator('#run-comparison-right').inputValue(), ''); assert.equal(await page.evaluate(() => window.requests.length), 0);
    assert.equal(await page.getByRole('searchbox', {name: 'Поиск второго запуска'}).evaluate(node => node === document.activeElement), true);
    await page.locator('#run-comparison-right').selectOption('a'); await page.locator('.run-comparison-card').first().waitFor();
    assert.equal(await page.locator('.run-comparison-card').count(), 2); assert.equal(await page.locator('.run-comparison img').count(), 0);
    const leftFacts = await page.locator('.run-comparison-metrics').first().innerText(); assert.match(leftFacts, /Вызовы агентов\s+0/); assert.match(leftFacts, /Измеренные токены\s+Нет данных/); assert.match(leftFacts, /Изменённые файлы\s+Нет данных/); assert.match(leftFacts, /Полнота учёта\s+Частичный/);
    assert.equal(await page.locator('.run-comparison-role h5').innerText(), 'qa', 'default role formatter preserves the stored ID');
    assert.match(await page.locator('.run-comparison-role').innerText(), /Попытки\s+2/); assert.match(await page.locator('.run-comparison-notes').innerText(), /Разные проекты/); assert.match(await page.locator('.run-comparison-notes').innerText(), /незавершённые/);
    const count = await page.evaluate(() => window.requests.length);
    await page.evaluate(() => {window.loadedRuns = [{id: 'c', task: 'New page'}]; window.mounted.refresh();});
    assert.equal(await page.locator('#run-comparison-left').inputValue(), 'b'); assert.equal(await page.locator('#run-comparison-right').inputValue(), 'a'); assert.equal(await page.evaluate(() => window.requests.length), count, 'history refresh retains explicit pair without a request');
    await page.getByRole('searchbox', {name: 'Поиск второго запуска'}).fill('new PAGE'); assert.equal(await page.locator('#run-comparison-right option').count(), 3, 'filter shows match and retains selected run');
    await page.getByRole('button', {name: 'Поменять местами', exact: true}).click(); assert.equal(await page.locator('#run-comparison-left').inputValue(), 'a');
    await page.evaluate(() => {window.hold = true;}); await page.getByRole('button', {name: 'Обновить сравнение', exact: true}).click();
    assert.equal(await page.locator('#run-comparison').getAttribute('aria-busy'), 'true'); assert.equal(await page.getByRole('button', {name: 'Обновить сравнение', exact: true}).isDisabled(), true);
    await page.evaluate(() => {window.hold = false; window.release();}); await page.waitForFunction(() => document.querySelector('#run-comparison').getAttribute('aria-busy') === 'false');
    await page.evaluate(() => {window.failure = {status: 403};}); await page.getByRole('button', {name: 'Обновить сравнение', exact: true}).click(); await page.getByText('Сравнение недоступно: нет разрешения на чтение.', {exact: true}).waitFor(); assert.equal(await page.locator('.run-comparison-card').count(), 0);
    await page.evaluate(() => {window.failure = {status: 0};}); await page.getByRole('button', {name: 'Обновить сравнение', exact: true}).click(); await page.getByText('Нет связи с сервером. Повторите обновление после подключения.', {exact: true}).waitFor();
    await page.evaluate(() => {window.failure = null;}); await page.getByRole('button', {name: 'Обновить сравнение', exact: true}).click(); await page.locator('.run-comparison-card').first().waitFor();
    await page.getByRole('button', {name: 'Открыть запуск', exact: true}).first().click(); assert.deepEqual(await page.evaluate(() => window.opened), ['a']); assert.equal(await page.locator('#main').evaluate(node => node === document.activeElement), true);
    await trigger.click(); await page.keyboard.press('Escape'); assert.equal(await trigger.evaluate(node => node === document.activeElement), true);
    await page.evaluate(() => document.querySelector('#other').showModal()); await page.evaluate(() => window.mounted.open()); assert.equal(await page.locator('#run-comparison').evaluate(node => node.open), false); await page.evaluate(() => document.querySelector('#other').close());
    await page.setViewportSize({width: 390, height: 740}); await trigger.click(); const bounds = await page.locator('#run-comparison').boundingBox(); assert(bounds.x >= 0 && bounds.x + bounds.width <= 390); assert(bounds.y >= 0 && bounds.y + bounds.height <= 740); assert.equal(await page.locator('#run-comparison').evaluate(node => node.scrollWidth <= node.clientWidth), true, 'mobile dialog does not overflow horizontally');
    await page.locator('.run-comparison-card').first().waitFor();
    await page.locator('#run-comparison').evaluate(node => {node.scrollTop = node.scrollHeight;});
    const scrolled = await page.locator('#run-comparison').evaluate(node => {
      const rect = node.getBoundingClientRect(), header = node.querySelector('.run-comparison-header'), headerRect = header.getBoundingClientRect(), close = node.querySelector('.run-comparison-close').getBoundingClientRect();
      return {top: rect.top, bottom: rect.bottom, headerTop: headerRect.top, closeTop: close.top, closeBottom: close.bottom, scrollTop: node.scrollTop, headerHeight: headerRect.height, padding: parseFloat(getComputedStyle(node).scrollPaddingTop), opaque: getComputedStyle(header).backgroundColor === getComputedStyle(node).backgroundColor};
    });
    assert(scrolled.scrollTop > 0, 'comparison has enough content to exercise scrolling');
    assert(scrolled.headerTop >= scrolled.top && scrolled.headerTop < scrolled.top + 3 && scrolled.closeTop >= scrolled.top && scrolled.closeBottom <= scrolled.bottom, 'sticky header and close button remain visible at the bottom');
    assert(scrolled.opaque && scrolled.padding >= scrolled.headerHeight, 'opaque sticky header has enough scroll padding for focused content');
    await page.getByRole('button', {name: 'Открыть запуск', exact: true}).last().focus();
    assert.equal(await page.getByRole('button', {name: 'Открыть запуск', exact: true}).last().evaluate(node => {
      const rect = node.getBoundingClientRect(), dialog = node.closest('dialog'), header = dialog.querySelector('.run-comparison-header').getBoundingClientRect();
      return document.activeElement === node && rect.top >= header.bottom && rect.bottom <= dialog.getBoundingClientRect().bottom;
    }), true, 'focusing the lower open-run action reveals it below the sticky header');
    await page.getByRole('button', {name: 'Закрыть сравнение', exact: true}).focus(); await page.keyboard.press('Shift+Tab'); assert.equal(await page.getByRole('button', {name: 'Открыть запуск', exact: true}).last().evaluate(node => node === document.activeElement), true, 'Shift+Tab wraps inside dialog');
    const english = await browser.newPage(); await setup(english, 'en', true); await english.getByRole('button', {name: 'Compare runs', exact: true}).click(); await english.locator('#run-comparison-right').selectOption('a'); await english.locator('.run-comparison-card').first().waitFor();
    assert.equal(await english.locator('.run-comparison-role h5').innerText(), 'QA review', 'host formatter supplies the same role label as Mission Control');
    assert.match(await english.locator('.run-comparison-card').first().innerText(), /Measured tokens\s+No data/); assert.match(await english.locator('.run-comparison-notes').innerText(), /Different projects/); assert.match(await english.locator('.run-comparison-card').first().innerText(), /<img src=x onerror=alert\(1\)> & literal/);
    assert.equal(await english.locator('.run-comparison-content').evaluate(node => /[А-Яа-яЁё]/u.test(node.innerText)), false, 'authored comparison UI is translated in English');
    await english.evaluate(() => window.mounted.destroy()); assert.equal(await english.locator('#run-comparison').count(), 0); assert.equal(await english.locator('#run-comparison-open').count(), 0);
    console.log('PASS browser: selected baseline, no empty-pair requests, null/zero metrics, real attempts, literal content, localized warnings, pagination-stable choices, explicit refresh, busy state, permission/offline errors, swap/open-run, Escape/focus trap, modal exclusion, mobile fit, sticky close and focus reveal, English and destroy.');
  } finally {await browser.close();}
}
(async () => {await pureTests(); if (process.argv.includes('--browser')) await browserTests();})().catch(error => {console.error(error); process.exitCode = 1;});
