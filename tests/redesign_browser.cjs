/* Explicit HTTP contract fixtures; no Codex calls, repository commands or Windows E2E. */
const {chromium}=require('playwright');
const fs=require('fs'),path=require('path'),http=require('http'),assert=require('assert');
const staticRoot=process.env.UI_DIR||path.join(__dirname,'../codex_team/static');
const output=process.env.QA_OUTPUT||'/workspace/redesign-evidence';fs.mkdirSync(output,{recursive:true});
const settings={theme:'dark',execution_backend:'codex_chatgpt',onboarding_dismissed:true};
const writes=[],unknown=[],errors=[],checks=[],languageIssues=[];
const run={id:'fixture-run',task:'ТЕСТОВЫЕ ДАННЫЕ: исправление авторизации, длинный русский текст '.repeat(5),workspace:'C:\\Пользователи\\Разработчик\\ПроектОченьДлинныйПуть\\'.repeat(3),state:'RUNNING',current_role:'developer',calls:2,iteration:1,stage:1,mode:'standard',created_at:'2026-10-15T10:00:00Z',elapsed_seconds:120,pipeline:['coordinator','developer','qa'],worktree:null,results:{coordinator:{verdict:'PLAN',summary:'План готов'}},result_history:[{role:'coordinator',iteration:1,result:{verdict:'PLAN',summary:'План готов'}}],usage:[],usage_total:{input:20,output:10,total:30}};
const defaultPacks=fs.readdirSync(path.join(__dirname,'../packs')).filter(f=>f.endsWith('.json')).map(f=>({...JSON.parse(fs.readFileSync(path.join(__dirname,'../packs',f),'utf8')),builtin:true,agents:['coordinator','developer','qa']}));
const defaultAgents=fs.readdirSync(path.join(__dirname,'../agents')).filter(f=>f.endsWith('.md')).map(f=>({name:f.slice(0,-3),role:f.slice(0,-3),instructions:'Fixture technical instructions',enabled:true,builtin:true,permission:f==='developer.md'?'workspace-write':'read-only'}));
const project={id:'fixture-project',name:'ТЕСТОВЫЕ ДАННЫЕ — проект',path:'C:\\Projects\\fixture'};
const wrap=(id,data)=>({id,project_id:project.id,version:1,created_at:'2026-10-15T12:00:00Z',data});
const intel=wrap('arch1',{head:'a'.repeat(40),files:['src/auth.py','pyproject.toml'],technologies:[{name:'Python',source:'pyproject.toml'}],modules:[{path:'src',files:1}],dependencies:[],summary:'Локальный анализ fixture',limitations:'Тестовые данные'});
const cp=wrap('cp1',{label:'ТЕСТОВАЯ контрольная точка',sha:'a'.repeat(40),stage:'developer',run_id:'fixture-run'});
const qa=wrap('qa1',{status:'PASS',head:'a'.repeat(40),checks:[{id:'test',category:'test',status:'PASS',exit_code:0,log:'1 passed'}]});
let knowledge=[];let spec;
if(process.env.QA_SHOWCASE==='1'){
 project.name='ТЕСТОВЫЕ ДАННЫЕ — Python / TypeScript workspace';
 const moduleFiles={src:'src/auth.py',tests:'tests/test_auth.py',docs:'docs/architecture.md',scripts:'scripts/check.py',config:'config/settings.toml',packages:'packages/client.ts'};
 intel.data.files=[...Object.values(moduleFiles),'pyproject.toml','package.json'];
 intel.data.technologies=[{name:'Python',source:'pyproject.toml'},{name:'TypeScript',source:'package.json'}];
 intel.data.modules=Object.entries(moduleFiles).map(([module,source])=>({path:module,name:module,files:1,source,category:'verified_fact',confidence:'high',summary:'ТЕСТОВЫЕ ДАННЫЕ: модуль из fixture-структуры Git.'}));
 intel.data.summary='ТЕСТОВЫЕ ДАННЫЕ: локальная карта небольшого проекта; связи зависимостей не предполагаются.';
 knowledge=[wrap('fixture-fact',{category:'verified_fact',title:'ТЕСТ: стек проекта',content:'Python API и TypeScript-клиент определены по fixture-манифестам.',sources:['pyproject.toml','package.json']}),wrap('fixture-derived',{category:'derived_finding',title:'ТЕСТ: модульные границы',content:'Каталоги src и packages разделены в fixture-структуре.',sources:['src/auth.py','packages/client.ts']}),wrap('fixture-decision',{category:'decision',title:'ТЕСТ: отдельная проверка',content:'Результат проверяется тестами проекта; это пользовательская тестовая запись.',sources:['tests/test_auth.py']})];
}

function fixture(url,method,body){const p=url.pathname;
 if(method!=='GET')writes.push({path:p,method,body});
 if(p==='/api/settings'){Object.assign(settings,body);return settings;}
 if(p==='/api/status')return {auth:{status:'CONNECTED',account:{type:'chatgpt'}},settings,capabilities:{steering:true}};
 if(p==='/health')return {status:'ok',version:'fixture-only',checks:{backend:true}};
 if(p==='/api/providers')return {active:'codex_chatgpt',codex:{status:'CONNECTED'},openai_api:{configured:false}};
 if(p==='/api/projects')return [project];
 if(p==='/api/runs')return {items:[run],total:1};if(p==='/api/runs/fixture-run')return run;if(p.endsWith('/events'))return {items:[{id:1,type:'agent_started',role:'developer',created_at:'2026-10-15T10:00:00Z',payload:{iteration:1,call:2}},{id:2,type:'item/completed',role:'developer',created_at:'2026-10-15T10:00:01Z',payload:{item:{type:'commandExecution',command:'git status',status:'completed',exitCode:0}}}],next_cursor:2,has_more:false};if(p.endsWith('/diff'))return {diff:'+ Тестовое изменение\n',diff_stat:'1 file changed',has_more:false,total_lines:1};
 if(p==='/api/actions')return [{id:'fixture-action',run_id:run.id,role:'developer',kind:'permission',reason:'ТЕСТ: разрешение команды',command:'git status',cwd:run.workspace,risk:'low',allowed_decisions:['deny'],questions:[]}];if(p==='/api/agents')return defaultAgents;if(p==='/api/packs')return defaultPacks;
 if(p==='/api/models')return {data:[]};if(p==='/api/usage')return {available:false};
 if(p.startsWith('/api/suite')){
  if(p.endsWith('/ai/status'))return {state:'running',active:true};
  if(p.endsWith('/ai/cancel'))return {state:'cleanup',active:true};
  if(p.endsWith('/retention'))return {policy:{enabled:false,keep_latest:null,max_age_days:null},automatic_deletion:false,logical_referenced_bytes:1024,checkpoints:[{id:'cp1',label:'Тестовая точка',protected:true,reasons:['Связана с историей запуска']}],size_note:'Логический объём; физическое место не обещается.'};
  if(p.endsWith('/retention/preview'))return {preview_token:'ret-preview',candidates:[],protected:[{id:'cp1'}]};
  if(p.endsWith('/qa/setup'))return {docker:{available:false,healthy:false,local:true,os_type:null,reason:'ТЕСТОВЫЕ ДАННЫЕ: Docker недоступен'},images:[],suggestions:[{id:'test',category:'test',argv:['python','-m','pytest'],required:true}],remediation:['Подготовьте доверенный локальный Linux-образ вручную.'],automatic_pull:false,automatic_install:false};
  if(p.endsWith('/qa/setup/verify'))return {available:false,tools_executed:false,reason:'Тестовый образ отсутствует'};
  
  if(p.endsWith('/intelligence'))return intel;
  if(p.endsWith('/source'))return {path:'src/auth.py',content:'def login(): pass'};
  if(p.endsWith('/knowledge')){if(method==='POST'){knowledge.push(wrap('k1',body));return knowledge.at(-1);}return {items:knowledge,total:knowledge.length};}
  if(p.endsWith('/budget')&&p.includes('/projects/'))return method==='PUT'?body:{max_agent_calls:5,max_total_tokens:1000};
  if(p==='/api/suite/budget')return {items:[{id:'fixture-run',task:'ТЕСТОВЫЙ запуск',calls:4,measured_tokens:750,max_agent_calls:5,max_total_tokens:1000,percent:{calls:80,tokens:75},thresholds:{calls:[50,75],tokens:[50,75]}}],total:1,roles:{developer:{calls:4,measured_tokens:750}},aggregation_scope:'current_page',account_quota:null};
  if(p.endsWith('/checkpoints'))return method==='POST'?cp:{items:[cp],total:1};
  if(p.endsWith('/checkpoints/compare'))return {files:['src/auth.py'],diff:'- old\n+ new'};
  if(p.endsWith('/preview'))return {preview_token:'preview1',data:{preview_token:'preview1',strategy:'new_worktree',dirty:true,files:['src/auth.py']}};
  if(p.endsWith('/restore'))return {path:'C:\\fixture-restored',branch:'codex-restore/fixture',head:'a'.repeat(40)};
  if(p.endsWith('/qa/config'))return wrap('cfg',{image:'sha256:'+'a'.repeat(64),commands:[{id:'test',category:'test',argv:['python','-m','pytest'],required:true}]});
  if(p.endsWith('/qa/discover'))return {suggestions:[],limitation:'Тестовые данные'};
  if(p==='/api/suite/qa')return {items:[qa],total:1};
  if(p.endsWith('/qa/qa1'))return qa;if(p.endsWith('/report'))return {report:'# QA fixture: PASS'};
  if(p.endsWith('/baseline'))return {ok:true};
  if(p==='/api/suite/specifications'){if(method==='POST'){const labels=['Цель','Контекст проекта','Текущее поведение','Ожидаемое поведение','Функциональные требования','Нефункциональные требования','Затрагиваемые компоненты','Ограничения','Риски','Acceptance Criteria','Test Plan','Definition of Done'];spec=wrap('spec1',{idea:body.idea,sections:Object.fromEntries(labels.map(x=>[x,'Тестовый раздел '+x])),status:'draft',recommended_mode:'standard'});return spec;}return {items:spec?[spec]:[],total:spec?1:0};}
  if(p==='/api/suite/specifications/spec1'){if(method==='PUT'){spec={...spec,version:spec.version+1,data:{...spec.data,sections:body.sections}};}return spec;}
  if(p.endsWith('/approve')){spec={...spec,version:spec.version+1,data:{...spec.data,status:'approved'}};return spec;}
 }
 unknown.push(p);return {detail:'Unmapped explicit fixture: '+p};
}
const server=http.createServer((req,res)=>{const url=new URL(req.url,'http://localhost');if(url.pathname.startsWith('/api/')||url.pathname==='/health'){let raw='';req.on('data',c=>raw+=c);req.on('end',()=>{res.setHeader('Content-Type','application/json');res.end(JSON.stringify(fixture(url,req.method,raw?JSON.parse(raw):{})));});return;}const file=path.join(staticRoot,url.pathname==='/'?'index.html':url.pathname.slice(1));if(!file.startsWith(staticRoot)||!fs.existsSync(file)){res.statusCode=404;res.end();return;}res.setHeader('Content-Type',file.endsWith('.css')?'text/css':file.endsWith('.js')?'text/javascript':'text/html');res.end(fs.readFileSync(file));});
(async()=>{
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 const phase=process.env.QA_PHASE||'after';
 const contrast=[],untranslated=[];
 try{
  const page=await browser.newPage({viewport:{width:1366,height:768}});
  page.on('pageerror',error=>errors.push(error.message));
  let cancelLanguage=false,warned=false;page.on('dialog',async dialog=>{if(cancelLanguage){warned=true;await dialog.dismiss();}else await dialog.accept();});
  await page.goto(`http://127.0.0.1:${server.address().port}`);
  await page.waitForFunction(()=>window.CodexTeamSuite?.state?.status);
  const screens=['workbench','projects','runs-list','runs','agents','packs','history','actions','usage','settings','intelligence','architect','budget','git','qa'];
  const visit=async name=>{
   if(process.env.QA_VERBOSE)console.log('visit',name);
   if(['intelligence','architect','budget','git','qa'].includes(name)){
    await page.locator(`[data-suite-feature-link="${name}"]`).first().click();
    await page.waitForFunction(()=>document.querySelector('#suite-root .suite-panel')); 
   }else{
    await page.locator(`.navigation [data-page="${name==='runs-list'?'runs':name}"]`).first().click();
    if(name==='runs')await page.locator('#runs-list button').first().click();
   }
   await page.waitForTimeout(60);
   await page.evaluate(()=>window.scrollTo(0,0));
  };
  const themes=(process.env.QA_THEMES||'obsidian-violet,neon-blue,emerald-tech,crimson-night,light,system,dark,purple-neon,dark-fantasy').split(',');
  const languages=(process.env.QA_LANGUAGES||'ru,en').split(',');
  for(const language of languages){
   await visit('settings');
   if(await page.locator('#settings-language').count()){if(await page.locator('#settings-language').inputValue()!==language)await Promise.all([page.waitForNavigation({waitUntil:'load'}),page.locator('#settings-language').selectOption(language)]);}
   else if(language!=='ru')throw new Error('Language selector missing');
   for(const theme of themes){
    await visit('settings');await page.locator('#settings-theme').selectOption(theme);
    contrast.push(...await page.evaluate(({theme,language})=>{
     const probe=document.createElement('span');document.body.append(probe);const canvas=document.createElement('canvas');canvas.width=canvas.height=1;const context=canvas.getContext('2d');
     const rgb=token=>{probe.style.color=`var(${token})`;context.clearRect(0,0,1,1);context.fillStyle=getComputedStyle(probe).color;context.fillRect(0,0,1,1);return [...context.getImageData(0,0,1,1).data].slice(0,3);};
     const lum=values=>values.map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4;}).reduce((a,v,i)=>a+v*[.2126,.7152,.0722][i],0);
     const pairs=[['--text','--panel'],['--muted','--panel'],['--red','--panel'],['--yellow','--panel'],['--green','--panel'],['--accent-ink','--accent']];
     const rows=pairs.map(([fg,bg])=>{const a=lum(rgb(fg)),b=lum(rgb(bg));return {theme,language,fg,bg,ratio:Number(((Math.max(a,b)+.05)/(Math.min(a,b)+.05)).toFixed(2))};});probe.remove();return rows;
    },{theme,language}));
    for(const [width,height]of (process.env.QA_SIZES||'1024x768,1366x768,1920x1080').split(',').map(size=>size.split('x').map(Number))){
     await page.setViewportSize({width,height});
     for(const name of screens){
      await visit(name);
      const dims=await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth,lang:document.documentElement.lang,theme:document.documentElement.dataset.theme}));
      checks.push({phase,language,theme,name,...dims});
      if(language==='en'&&theme==='obsidian-violet'&&width===1366){const labels=await page.evaluate(()=>[...document.querySelectorAll('button,label,legend,summary,option,h1,h2,h3,th')].filter(n=>n.getClientRects().length&&!n.closest('pre,code')).map(n=>n.textContent.trim()).filter(text=>/[А-Яа-яЁё]/.test(text)&&!/(?:ТЕСТ|Тестов|тестов|Русский)/.test(text)));for(const text of labels)untranslated.push({name,text});}

      if(width===1366&&((theme==='obsidian-violet')||(name==='intelligence'&&language==='ru'))){
       await page.screenshot({path:path.join(output,`${phase}-${language}-${theme}-${name}.png`),fullPage:true});
      }
     }
    }
   }
  }
  // User content must survive localization and navigation byte-for-byte.
  if(languages.includes('en')){
  await visit('architect');const idea=page.locator('#suite-root textarea').first();
  const draft='Пользовательский текст — User content: Обзор, Ошибка, Projects';await idea.fill(draft);
  await visit('settings');cancelLanguage=true;warned=false;await page.locator('#settings-language').selectOption('ru');await page.waitForTimeout(100);assert(warned,'Unsaved form language warning missing');cancelLanguage=false;
  await visit('architect');assert.equal(await page.locator('#suite-root textarea').first().inputValue(),draft);
  await page.reload();await visit('settings');await page.locator('#settings-theme').selectOption('emerald-tech');await page.locator('#save-appearance-button').click();await page.waitForTimeout(200);await page.reload();await visit('settings');
  assert.equal(await page.locator('#settings-language').inputValue(),'en');assert.equal(await page.locator('#settings-theme').inputValue(),'emerald-tech');
  }
  // Error, loading, offline and first-run states use explicit HTTP fixtures.
  await visit('architect');let releaseScan,scanEntered;
  const entered=new Promise(resolve=>scanEntered=resolve);
  await page.route('**/api/suite/projects/*/intelligence',async route=>{scanEntered();await new Promise(resolve=>releaseScan=resolve);await route.fulfill({contentType:'application/json',body:JSON.stringify(intel)});});
  await page.locator('[data-suite-feature-link="intelligence"]').first().click();await entered;
  assert(/Loading|Загрузка/.test(await page.locator('.suite-status').innerText()));
  await page.screenshot({path:path.join(output,`${phase}-loading-fixture.png`),fullPage:true});releaseScan();
  await page.waitForFunction(()=>document.querySelector('#suite-root .suite-panel'));await page.unroute('**/api/suite/projects/*/intelligence');
  const moduleCard=page.locator('.intelligence-module').first();await moduleCard.click();assert.equal(await moduleCard.getAttribute('aria-pressed'),'true');
  await page.locator('.intelligence-inspector button').click();assert.equal(await page.locator('.intelligence-sources input').inputValue(),'src/');assert.equal(await page.locator('.suite-file-list button').count(),1);
  await page.locator('.suite-file-list button').first().click();await page.locator('.intelligence-source-preview').filter({hasText:'def login(): pass'}).waitFor();
  const knowledgeEditor=page.locator('.intelligence-knowledge-editor');await knowledgeEditor.locator('summary').click();
  await knowledgeEditor.locator('input').fill('QA user knowledge: Обзор');await knowledgeEditor.locator('textarea').nth(0).fill('Fixture fact content left unchanged');await knowledgeEditor.locator('textarea').nth(1).fill('src/auth.py');
  await knowledgeEditor.locator('button').click();await page.getByRole('heading',{name:'QA user knowledge: Обзор',exact:true}).waitFor();
  await knowledgeEditor.locator('summary').click();await page.locator('.intelligence-knowledge-card').filter({hasText:'QA user knowledge: Обзор'}).locator('.suite-toolbar button').first().click();assert(await knowledgeEditor.evaluate(node=>node.open));assert.equal(await knowledgeEditor.locator('input').inputValue(),'QA user knowledge: Обзор');
  await page.screenshot({path:path.join(output,`${phase}-intelligence-interaction-fixture.png`),fullPage:true});
  await visit('architect');
  await page.locator('.architect-brief textarea').fill('Fixture specification: user content Обзор');await page.locator('.architect-brief button').click();await page.locator('.architect-editor textarea').first().waitFor();
  assert.equal(await page.locator('.architect-editor textarea').count(),12);await page.locator('.architect-editor textarea').first().fill('Edited user goal Обзор');
  await page.getByRole('button',{name:/^(Save draft|Сохранить черновик)$/}).click();await page.waitForTimeout(120);assert(writes.some(write=>write.path==='/api/suite/specifications/spec1'&&write.method==='PUT'&&Object.values(write.body.sections).includes('Edited user goal Обзор')));
  await page.screenshot({path:path.join(output,`${phase}-architect-editor-fixture.png`),fullPage:true});
  await page.route('**/api/suite/projects/*/intelligence',route=>route.fulfill({status:422,contentType:'application/json',body:JSON.stringify({detail:'Проверьте заполнение полей.',validation_errors:[{loc:['body','workspace'],type:'missing',msg:'Field required',input:'fixture-secret-must-never-render'}]})}));
  await page.locator('[data-suite-feature-link="intelligence"]').first().click();await page.locator('.suite-error').waitFor();
  assert(!(await page.locator('body').innerText()).includes('fixture-secret-must-never-render'));
  assert((await page.locator('.suite-status').innerText()).length>10);
  await page.screenshot({path:path.join(output,`${phase}-validation-error-fixture.png`),fullPage:true});await page.unroute('**/api/suite/projects/*/intelligence');
  await page.route('**/api/status',route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Fixture backend unavailable'})}));
  await page.locator('#refresh-button').click();await page.locator('#service-banner').waitFor();
  await page.screenshot({path:path.join(output,`${phase}-offline-fixture.png`),fullPage:true});await page.unroute('**/api/status');await page.locator('#refresh-button').click();await page.locator('#service-banner').waitFor({state:'hidden'});
  const fresh=await browser.newPage({viewport:{width:1024,height:768}});fresh.on('pageerror',error=>errors.push(error.message));
  await fresh.route('**/api/projects',route=>route.fulfill({contentType:'application/json',body:'[]'}));
  await fresh.route('**/api/runs?*',route=>route.fulfill({contentType:'application/json',body:JSON.stringify({items:[],total:0})}));
  await fresh.route('**/api/status',route=>route.fulfill({contentType:'application/json',body:JSON.stringify({auth:{status:'AUTH_REQUIRED'},settings:{...settings,onboarding_dismissed:true}})}));
  await fresh.goto(`http://127.0.0.1:${server.address().port}/#intelligence`);await fresh.locator('#suite-root .suite-panel').waitFor();
  assert((await fresh.locator('#suite-root').innerText()).includes('project')||(await fresh.locator('#suite-root').innerText()).includes('проект'));
  await fresh.screenshot({path:path.join(output,`${phase}-empty-project-fixture.png`),fullPage:true});
  await fresh.locator('.navigation [data-page="workbench"]').click();await fresh.locator('#auth-banner').waitFor();assert(await fresh.locator('#start-button').isDisabled());
  await fresh.screenshot({path:path.join(output,`${phase}-unauthorized-fixture.png`),fullPage:true});await fresh.close();
  const overflows=checks.filter(c=>c.scroll>c.width+1);
  fs.writeFileSync(path.join(output,`${phase}-redesign-results.json`),JSON.stringify({fixtureOnly:true,windowsDpi:false,checks,contrast,untranslated,errors,unknown,overflows,writes:writes.length},null,2));
  console.log(JSON.stringify({checks:checks.length,contrast,untranslated,errors,unknown,overflows,fixtureOnly:true,windowsDpi:false}));
  assert(contrast.every(row=>row.ratio>=4.5),'Theme contrast below AA');assert.deepEqual(errors,[]);assert.deepEqual(unknown,[]);assert.deepEqual(overflows,[]);
 }finally{fs.writeFileSync(path.join(output,`${phase}-redesign-results.json`),JSON.stringify({fixtureOnly:true,windowsDpi:false,checks,contrast,untranslated,errors,unknown,overflows:checks.filter(c=>c.scroll>c.width+1),writes:writes.length},null,2));await browser.close();server.close();}
})().catch(error=>{console.error(error);server.close();process.exitCode=1;});
