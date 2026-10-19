'use strict';
const assert = require('assert/strict'), fs = require('fs'), path = require('path');
const sourceRoot = process.argv.find(arg => !arg.startsWith('-') && arg.endsWith('/static')) || path.join(__dirname, '../codex_team/static');
const {createController, validNotebook, safeFilename, errorCode} = require(path.resolve(sourceRoot, 'run-notebook.js'));
const deferred = () => {let resolve, reject; const promise = new Promise((a,b) => {resolve=a; reject=b;}); return {resolve,reject,promise};};
const notebook = (id, revision = 0, note = '', favorite = false) => ({run_id:id,revision,note,favorite,updated_at:null});
async function pureTests() {
  assert(validNotebook(notebook('a'), 'a')); assert(!validNotebook({...notebook('a'), favorite:'true'},'a'));
  for(const invalid of [null, {}, {...notebook('a'), revision:-1}, {...notebook('a'),note:'x'.repeat(10001)}, {...notebook('a'),updated_at:5}]) assert(!validNotebook(invalid,'a'));
  assert(validNotebook(notebook('a',0,'😀'.repeat(10000)),'a'));
  assert.equal(safeFilename('../private.md'),'codex-team-run-report.md'); assert.equal(safeFilename('C:\\secret.md'),'codex-team-run-report.md'); assert.equal(safeFilename('run-a.md'),'run-a.md');
  assert.equal(errorCode({status:409}),'conflict'); assert.equal(errorCode({status:403}),'permission'); assert.equal(errorCode({status:0}),'offline');
  const calls = [], states = [], saved = [];
  const c = createController({api:(...args)=>{const d=deferred(); calls.push({...d,args}); return d.promise;}, onState:s=>states.push(s),onSaved:s=>saved.push(s)});
  const a = c.open('a/path'), b = c.open('b'); calls[1].resolve(notebook('b')); await b; calls[0].resolve(notebook('a/path')); await a; assert.equal(c.state.id,'b'); assert.equal(c.state.data.run_id,'b');
  assert.equal(calls[0].args[0],'/api/runs/a%2Fpath/notebook');
  const write = c.save({note:'literal <img onerror=x>',favorite:true}); assert.equal(c.pendingSave,true); assert.equal(await c.save({note:'double',favorite:false}),false); assert.equal(calls.length,3);
  assert.deepEqual(calls[2].args.slice(1),['PUT',{expected_revision:0,note:'literal <img onerror=x>',favorite:true}]);
  calls[2].reject({status:409}); await write; assert.equal(c.state.error,'conflict'); assert.equal(c.state.data.revision,0);
  const refresh = c.load(); calls[3].resolve(notebook('b',1,'other')); await refresh;
  const secondWrite = c.save({note:'mine',favorite:true}); c.close(); const emitted=states.length; assert.equal(await c.open('c'),false,'pending write serializes reopen');
  calls[4].resolve(notebook('b',2,'mine',true)); assert.equal(await secondWrite,true); assert.equal(states.length,emitted,'closed UI receives no late save or finally render'); assert.equal(saved.length,1,'history gets persisted update even after close');
  const reopened = c.open('b'); calls[5].resolve(notebook('b',2,'mine',true)); await reopened;
  assert.equal(await c.save({note:'x'.repeat(10001),favorite:false}),false); assert.equal(c.state.error,'validation'); assert.equal(calls.length,6);
  const invalidWrite = c.save({note:'valid',favorite:false}); calls[6].resolve(notebook('wrong',3)); await invalidWrite; assert.equal(c.state.error,'error'); assert.equal(c.state.data.note,'mine');
  const report = c.report('en'); assert.equal(calls[7].args[0],'/api/runs/b/report?language=en'); assert.equal(calls[7].args.length,1); assert.equal(await c.report('ru'),null);
  calls[7].resolve({run_id:'b',filename:'../../oops.md',markdown:'# Facts'}); assert.deepEqual(await report,{filename:'codex-team-run-report.md',markdown:'# Facts'});
  const malformed = c.report('ru'); calls[8].resolve({run_id:'b',markdown:5}); assert.equal(await malformed,null); assert.equal(c.state.error,'error');
  const late = c.report('ru'); c.close(); calls[9].resolve({run_id:'b',filename:'b.md',markdown:'late'}); assert.equal(await late,null,'closed export cannot trigger a late download');
  const offline = c.open('x'); calls[10].reject({status:0}); await offline; assert.equal(c.state.error,'offline'); assert.equal(c.state.loading,false);
  const pending = c.load(); const before=states.length; c.destroy(); calls[11].resolve(notebook('x')); await pending; assert.equal(states.length,before); assert.equal(await c.open('z'),false);
  console.log('PASS notebook controller: schema/Unicode boundaries, safe filenames, encoded requests, CAS conflicts, serialized writes, closed/destroyed guards, malformed data, offline and report safety.');
}
async function browserTests() {
  const {chromium} = require('playwright'); const browser = await chromium.launch({executablePath:process.env.CHROMIUM_PATH || '/usr/bin/chromium',headless:true,args:['--no-sandbox']});
  try {
    const page = await browser.newPage({viewport:{width:1100,height:900}});
    async function setup(language='ru') {
      await page.setContent('<!doctype html><html><body><div id="toolbar"></div><dialog id="other"><button>Other</button></dialog></body></html>');
      for(const file of ['style.css','run-notebook.css']) await page.addStyleTag({content:fs.readFileSync(path.resolve(sourceRoot,file),'utf8')});
      await page.addScriptTag({content:fs.readFileSync(path.resolve(sourceRoot,'i18n.js'),'utf8')}); await page.evaluate(lang=>window.CodexI18n.setLanguage(lang),language);
      await page.addScriptTag({content:fs.readFileSync(path.resolve(sourceRoot,'run-notebook.js'),'utf8')});
      await page.evaluate(() => {
        window.stored = {run_id:'r1',revision:0,note:'',favorite:false,updated_at:null}; window.calls=[]; window.saved=[]; window.downloads=[]; window.allowDiscard=false;
        const original = HTMLAnchorElement.prototype.click; HTMLAnchorElement.prototype.click=function(){if(this.download){window.downloads.push({filename:this.download,href:this.href}); return;} return original.call(this);};
        window.module = window.CodexRunNotebook.mount({anchor:document.querySelector('#toolbar'),getSelectedRun:()=>({id:'r1'}), confirm:async()=>window.allowDiscard,onSaved:value=>window.saved.push(value),api:async(...args)=> {
          window.calls.push(args); if(window.hold) await new Promise(resolve=>window.release=resolve); if(window.failure) throw window.failure;
          if(args[0].includes('/report?')) return {run_id:'r1',filename:'r1.md',markdown:'# Task\n\n'+window.stored.note};
          if(args[1]==='PUT') window.stored={...window.stored,...args[2],revision:window.stored.revision+1}; return {...window.stored};
        }});
      });
    }
    await setup(); await page.locator('#run-notebook-open').click();
    const note=page.locator('#run-notebook-note'); await note.waitFor(); await page.waitForFunction(()=>!document.querySelector('#run-notebook-note').disabled);
    assert.equal(await note.evaluate(node=>node===document.activeElement),true); assert.equal(await page.locator('#run-notebook-save').isDisabled(),true);
    await note.fill('<img src=x onerror=alert(1)>\nРешение'); await page.locator('#run-notebook-favorite').check(); assert.equal(await page.locator('#run-notebook-export').isDisabled(),true);
    await page.keyboard.press('Escape'); assert.equal(await page.locator('#run-notebook').evaluate(node=>node.open),true,'dirty close requires confirmation');
    await page.locator('#run-notebook-save').click(); await page.getByText('Заметка сохранена.',{exact:true}).waitFor(); assert.equal(await note.inputValue(),'<img src=x onerror=alert(1)>\nРешение'); assert.equal(await page.locator('#run-notebook img').count(),0);
    assert.equal(await note.evaluate(node=>node===document.activeElement),true,'save restores editable focus'); assert.equal(await page.evaluate(()=>window.saved.length),1);
    await page.locator('#run-notebook-export').click(); await page.waitForFunction(()=>window.downloads.length===1); assert.equal(await page.evaluate(()=>window.downloads[0].filename),'r1.md');
    await note.fill('local unsaved'); await page.evaluate(()=>window.failure={status:409}); await page.locator('#run-notebook-save').click(); await page.getByText(/Заметка изменена в другом окне/).waitFor(); assert.equal(await note.inputValue(),'local unsaved');
    const count=await page.evaluate(()=>window.calls.length); await page.locator('#run-notebook-refresh').click(); assert.equal(await page.evaluate(()=>window.calls.length),count,'refresh refuses silently discarding dirty input');
    await page.evaluate(()=>{window.allowDiscard=true;window.failure={status:0};}); await page.locator('#run-notebook-refresh').click(); await page.getByText(/Нет связи с сервером/).waitFor(); assert.equal(await note.inputValue(),'local unsaved','failed refresh retains text');
    await page.evaluate(()=>{window.allowDiscard=false;}); await page.keyboard.press('Escape'); assert.equal(await page.locator('#run-notebook').evaluate(node=>node.open),true,'failed refresh still protects dirty text');
    await page.evaluate(()=>{window.failure=null;window.hold=true;}); await page.locator('#run-notebook-save').click(); assert.equal(await note.isDisabled(),true); await page.keyboard.press('Escape'); await page.waitForFunction(()=>!document.querySelector('#run-notebook').open);
    const before=await page.locator('.run-notebook-status').textContent(); await page.evaluate(()=>{window.hold=false;window.release();}); await page.waitForTimeout(30); assert.equal(await page.locator('.run-notebook-status').textContent(),before,'closed dialog has no late write'); assert.equal(await page.locator('#run-notebook-open').evaluate(node=>node===document.activeElement),true);
    await page.locator('#run-notebook-open').click(); await page.waitForFunction(()=>!document.querySelector('#run-notebook-note').disabled); assert.equal(await note.inputValue(),'local unsaved');
    await page.setViewportSize({width:390,height:740}); await note.fill('x'.repeat(10001)); assert.equal(await page.locator('#run-notebook-save').isDisabled(),true); await note.fill('x'.repeat(10000)); assert.equal(await page.locator('#run-notebook-save').isDisabled(),false);
    assert.equal(await page.locator('#run-notebook').evaluate(node=>node.scrollWidth<=node.clientWidth),true);
    await page.locator('#run-notebook').evaluate(node=>node.scrollTop=node.scrollHeight); const geometry=await page.locator('#run-notebook').evaluate(node=>{const d=node.getBoundingClientRect(),h=node.querySelector('header').getBoundingClientRect(),c=node.querySelector('.run-notebook-close').getBoundingClientRect();return {top:d.top,header:h.top,close:c.bottom,bottom:d.bottom,padding:parseFloat(getComputedStyle(node).scrollPaddingTop),height:h.height};}); assert(geometry.header>=geometry.top && geometry.header<geometry.top+3 && geometry.close<=geometry.bottom && geometry.padding>=geometry.height);
    await page.locator('.run-notebook-close').focus(); await page.keyboard.press('Shift+Tab'); assert.equal(await page.locator('#run-notebook-refresh').evaluate(node=>node===document.activeElement),true,'focus wraps to last enabled control with dirty export disabled');
    await page.evaluate(()=>window.module.destroy()); assert.equal(await page.locator('#run-notebook').count(),0);
    await setup('en'); await page.locator('#run-notebook-open').click(); await page.waitForFunction(()=>!document.querySelector('#run-notebook-note').disabled); assert.equal(await page.locator('#run-notebook').evaluate(node=>/[А-Яа-яЁё]/u.test(node.innerText)),false,'English translates all authored labels'); await page.keyboard.press('Escape'); await page.evaluate(()=>document.querySelector('#other').showModal()); await page.evaluate(()=>window.module.open()); assert.equal(await page.locator('#run-notebook').evaluate(node=>node.open),false,'no competing modal');
    console.log('PASS browser notebook: CRUD/favorite, literal text, focus, dirty close/refresh, CAS/offline preservation, closed saves, explicit download, boundaries, mobile/sticky/focus trap, English and modal exclusion.');
  } finally {await browser.close();}
}
(async()=>{await pureTests(); if(process.argv.includes('--browser')) await browserTests();})().catch(error=>{console.error(error);process.exitCode=1;});
