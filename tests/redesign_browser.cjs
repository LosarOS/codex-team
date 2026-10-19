/* Explicit HTTP contract fixtures; no Codex calls, repository commands or Windows E2E. */
const {chromium}=require('playwright');
const fs=require('fs'),path=require('path'),http=require('http'),assert=require('assert');
const staticRoot=process.env.UI_DIR||path.join(__dirname,'../codex_team/static');
const output=process.env.QA_OUTPUT||'/workspace/redesign-evidence';fs.mkdirSync(output,{recursive:true});
const settings={theme:'dark',execution_backend:'codex_chatgpt',onboarding_dismissed:true};
const writes=[],unknown=[],errors=[],checks=[],languageIssues=[];
const run={id:'fixture-run',task:'ТЕСТОВЫЕ ДАННЫЕ: исправление авторизации, длинный русский текст '.repeat(5),workspace:'C:\\Пользователи\\Разработчик\\ПроектОченьДлинныйПуть\\'.repeat(3),state:'RUNNING',current_role:'developer',calls:2,iteration:1,stage:1,mode:'standard',created_at:'2026-10-15T10:00:00Z',elapsed_seconds:120,pipeline:['coordinator','developer','qa'],worktree:null,results:{coordinator:{verdict:'PLAN',summary:'План готов'}},result_history:[{role:'coordinator',iteration:1,result:{verdict:'PLAN',summary:'План готов'}}],usage:[],usage_total:{input:20,output:10,total:30}};
const secondRun={...run,id:'fixture-run-2',task:'ТЕСТОВЫЕ ДАННЫЕ: документировать локальную проверку',state:'DONE',current_role:'qa',calls:1,stage:3,elapsed_seconds:0,changed_files:[],usage:[{last:{total_tokens:0}}],usage_total:{input:null,output:null,cached:null,total:0},usage_available:true,usage_complete:true,results:{qa:{verdict:'PASS',summary:'ТЕСТОВЫЕ ДАННЫЕ: сохранённый результат роли; отдельный QA Arena не запускался.'}},result_history:[]};
let fixtureRuns=[run,secondRun];
const notebooks=new Map(fixtureRuns.map(item=>[item.id,{run_id:item.id,revision:0,favorite:false,note:'',updated_at:null}]));
const notebookReads=[],reportReads=[];
const runMetadata=item=>{const notebook=notebooks.get(item.id);return {...item,notebook:{revision:notebook.revision,favorite:notebook.favorite,has_note:!!notebook.note,updated_at:notebook.updated_at}};};
const comparisonReads=[],productivityChecks=[];
const templateData={task:'ТЕСТОВЫЕ ДАННЫЕ: повторить проверку документации <script>literal</script>',workspace:run.workspace,mode:'standard',pack:'default',specialists:[],max_iterations:1,max_agent_calls:5,max_run_duration:1800};
let templates=[{id:'fixture-template-1',name:'ТЕСТОВЫЕ ДАННЫЕ: проверка документации',description:'Локальный HTTP fixture. Разрешения не сохраняются.',revision:1,created_at:'2026-10-18T10:00:00Z',updated_at:'2026-10-18T10:00:00Z',data:templateData}];
function comparisonRun(source){return {id:source.id,state:source.state,task:source.task,workspace:source.workspace,original_workspace:null,project_id:null,mode:source.mode,pack:null,access_level:null,created_at:source.created_at,started_at:null,completed_at:null,error:null,calls:source.calls,measured_tokens:source.id===secondRun.id?0:null,usage_complete:source.id===secondRun.id,duration_seconds:source.elapsed_seconds,changed_files_count:Array.isArray(source.changed_files)?source.changed_files.length:null,max_iterations:null,max_agent_calls:null,max_run_duration:null,max_total_tokens:null,max_parallel_agents:null,isolated:null,auto_commit:null,specialists:null,stages:Object.entries(source.results).map(([role,result])=>({role,summary:result.summary,verdict:result.verdict,error:null,attempts:source.id===run.id?1:null}))};}
const defaultPacks=fs.readdirSync(path.join(__dirname,'../packs')).filter(f=>f.endsWith('.json')).map(f=>({...JSON.parse(fs.readFileSync(path.join(__dirname,'../packs',f),'utf8')),builtin:true,agents:['coordinator','developer','qa']}));
const defaultAgents=fs.readdirSync(path.join(__dirname,'../agents')).filter(f=>f.endsWith('.md')).map(f=>({name:f.slice(0,-3),role:f.slice(0,-3),instructions:'Fixture technical instructions',enabled:true,builtin:true,permission:f==='developer.md'?'workspace-write':'read-only'}));
const project={id:'fixture-project',name:'ТЕСТОВЫЕ ДАННЫЕ — проект',path:'C:\\Projects\\fixture'};
if(process.env.QA_REPLAY_ONLY==='1'){run.task='ТЕСТОВЫЕ ДАННЫЕ: повторная задача — user content <script>literal</script> & "quotes".\n'.repeat(80);run.original_workspace=project.path;}
const replayReads=[];
const replaySnapshot=id=>({run_id:id,data:{task:run.task,workspace:project.path,mode:'quick',pack:'software-development',specialists:[],max_iterations:2,max_agent_calls:7,max_run_duration:31},warnings:['security_reset']});
const wrap=(id,data)=>({id,project_id:project.id,version:1,created_at:'2026-10-15T12:00:00Z',data});
const intel=wrap('arch1',{head:'a'.repeat(40),files:['src/auth.py','pyproject.toml'],technologies:[{name:'Python',source:'pyproject.toml'}],modules:[{path:'src',files:1}],dependencies:[],summary:'Локальный анализ fixture',limitations:'Тестовые данные'});
const cp=wrap('cp1',{label:'ТЕСТОВАЯ контрольная точка',sha:'a'.repeat(40),stage:'developer',run_id:'fixture-run'});
const qa=wrap('qa1',{status:'PASS',head:'a'.repeat(40),checks:[{id:'test',category:'test',status:'PASS',exit_code:0,log:'1 passed'}]});
let knowledge=[];let spec;let composeDraft={revision:0,draft:null};
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
 const replayRoute=p.match(/^\/api\/runs\/([^/]+)\/replay$/);
 if(replayRoute){const id=decodeURIComponent(replayRoute[1]);replayReads.push(id);return id===run.id?replaySnapshot(id):{__status:404,detail:'ТЕСТ: исходный запуск недоступен'};}
 const notebookRoute=p.match(/^\/api\/runs\/([^/]+)\/(notebook|report)$/);
 if(notebookRoute){
  const id=decodeURIComponent(notebookRoute[1]),entry=notebooks.get(id);
  if(!entry)return {__status:404,detail:'ТЕСТ: запуск не найден'};
  if(notebookRoute[2]==='report'){
   reportReads.push({id,language:url.searchParams.get('language')});
   return {run_id:id,filename:`codex-team-${id}.md`,language:url.searchParams.get('language'),markdown:`# TEST FIXTURE: Codex Team run report\n\nRun: ${id}\n\n${entry.note}\n\nFixture only; no live agent execution.\n`};
  }
  notebookReads.push({id,method});
  if(method==='GET')return entry;
  if(body.expected_revision!==entry.revision)return {__status:409,detail:{code:'notebook_conflict',revision:entry.revision,message:'ТЕСТ: заметка изменена в другом окне'}};
  const saved={run_id:id,revision:entry.revision+1,favorite:body.favorite,note:body.note,updated_at:'2026-10-19T10:01:00Z'};notebooks.set(id,saved);return saved;
 }
 if(p==='/api/task-templates'){
  if(method==='POST'&&body.description.length>1000)return {__status:422,detail:'ТЕСТ: описание не более 1000 символов'};
  if(method==='POST'){const saved={id:'fixture-template-created',name:body.name,description:body.description,revision:1,created_at:'2026-10-18T10:01:00Z',updated_at:'2026-10-18T10:01:00Z',data:body.data};templates.unshift(saved);return saved;}
  const query=(url.searchParams.get('query')||'').toLocaleLowerCase(),offset=Number(url.searchParams.get('offset')||0),limit=Number(url.searchParams.get('limit')||50);
  const matches=templates.filter(item=>(item.name+' '+item.description).toLocaleLowerCase().includes(query));
  return {items:matches.slice(offset,offset+limit).map(({data,...metadata})=>metadata),total:matches.length};
 }
 if(p.startsWith('/api/task-templates/')){
  const id=decodeURIComponent(p.slice('/api/task-templates/'.length)),selected=templates.find(item=>item.id===id);
  if(!selected)return {__status:404,detail:'ТЕСТ: шаблон не найден'};
  if(method==='GET')return selected;
  const expected=method==='DELETE'?Number(url.searchParams.get('expected_revision')):body.expected_revision;
  if(expected!==selected.revision)return {__status:409,detail:{code:'template_conflict',revision:selected.revision,message:'ТЕСТ: шаблон изменён в другом окне'}};
  if(method==='DELETE'){templates=templates.filter(item=>item.id!==id);return {deleted:true,id};}
  Object.assign(selected,{name:body.name,description:body.description,data:body.data,revision:selected.revision+1,updated_at:'2026-10-18T10:02:00Z'});return selected;
 }
 if(p==='/api/run-comparison'){
  const left=url.searchParams.get('left'),right=url.searchParams.get('right');comparisonReads.push({left,right});
  if(left===right)return {__status:422,detail:'ТЕСТ: выберите разные запуски'};
  const first=fixtureRuns.find(item=>item.id===left),second=fixtureRuns.find(item=>item.id===right);
  if(!first||!second)return {__status:404,detail:'ТЕСТ: запуск не найден'};
  return {left:comparisonRun(first),right:comparisonRun(second),comparable_project:first.workspace===second.workspace,warnings:['active_runs_partial','incomplete_usage']};
 }
 if(p==='/api/task-draft'){
  if(method==='GET')return composeDraft;
  const expected=method==='DELETE'?Number(url.searchParams.get('expected_revision')):body.expected_revision;
  if(expected!==composeDraft.revision)return {__status:409,detail:{code:'draft_conflict',message:'Черновик изменён в другом окне.'}};
  if(method==='PUT')composeDraft={revision:expected+1,draft:{revision:expected+1,updated_at:new Date().toISOString(),data:body.data}};
  if(method==='DELETE'&&composeDraft.draft)composeDraft={revision:expected+1,draft:null};
  return composeDraft;
 }
 if(p==='/api/settings'){Object.assign(settings,body);return settings;}
 if(p==='/api/status')return {auth:{status:'CONNECTED',account:{type:'chatgpt'}},settings,capabilities:{steering:true}};
 if(p==='/health')return {status:'ok',version:'fixture-only',checks:{backend:true}};
 if(p==='/api/providers')return {active:'codex_chatgpt',codex:{status:'CONNECTED'},openai_api:{configured:false}};
 if(p==='/api/projects')return [project];
 if(p==='/api/runs'){const items=fixtureRuns.map(runMetadata).filter(item=>url.searchParams.get('favorite')!=='true'||item.notebook.favorite);return {items,total:items.length};}if(p==='/api/runs/fixture-run')return run;if(p==='/api/runs/fixture-run-2')return secondRun;if(p.endsWith('/events'))return {items:[{id:1,type:'agent_started',role:'developer',created_at:'2026-10-15T10:00:00Z',payload:{iteration:1,call:2}},{id:2,type:'item/completed',role:'developer',created_at:'2026-10-15T10:00:01Z',payload:{item:{type:'commandExecution',command:'git status',status:'completed',exitCode:0}}}],next_cursor:2,has_more:false};if(p.endsWith('/diff'))return {diff:'+ Тестовое изменение\n',diff_stat:'1 file changed',has_more:false,total_lines:1};
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
const server=http.createServer((req,res)=>{res.setHeader('X-Content-Type-Options','nosniff');res.setHeader('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'");const url=new URL(req.url,'http://localhost');if(url.pathname.startsWith('/api/')||url.pathname==='/health'){let raw='';req.on('data',c=>raw+=c);req.on('end',()=>{res.setHeader('Content-Type','application/json');const result=fixture(url,req.method,raw?JSON.parse(raw):{});if(result?.__status){res.statusCode=result.__status;delete result.__status;}res.end(JSON.stringify(result));});return;}const file=path.join(staticRoot,url.pathname==='/'?'index.html':url.pathname.slice(1));if(!file.startsWith(staticRoot)||!fs.existsSync(file)){res.statusCode=404;res.end();return;}res.setHeader('Content-Type',file.endsWith('.svg')?'image/svg+xml':file.endsWith('.css')?'text/css':file.endsWith('.js')?'text/javascript':'text/html');res.end(fs.readFileSync(file));});
(async()=>{
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 const phase=process.env.QA_PHASE||'after';
 const contrast=[],untranslated=[];
 try{
  const page=await browser.newPage({viewport:{width:1366,height:768}});
  page.on('pageerror',error=>errors.push(error.message));
  page.on('console',message=>{if(message.type()==='error'&&/Content Security|Refused to|MIME|nosniff/i.test(message.text()))errors.push(message.text());});
  page.on('response',response=>{const path=new URL(response.url()).pathname;if(!path.startsWith('/api/')&&path!=='/health'&&path!=='/favicon.ico'&&response.status()>=400)errors.push(`Static asset ${path}: ${response.status()}`);});
  let cancelLanguage=false,warned=false;page.on('dialog',async dialog=>{if(cancelLanguage){warned=true;await dialog.dismiss();}else await dialog.accept();});
  await page.goto(`http://127.0.0.1:${server.address().port}`);
  await page.waitForFunction(()=>window.CodexTeamSuite?.state?.status);
  const screens=(process.env.QA_SCREENS||'workbench,projects,runs-list,runs,run-notebook,agents,packs,history,actions,usage,settings,intelligence,architect,budget,git,qa').split(',');
  const visit=async name=>{
   if(process.env.QA_VERBOSE)console.log('visit',name);
   if(await page.locator('#confirm-dialog[open]').count()){
    if(name==='replay-composer'){await page.locator('#confirm-accept').click();await page.locator('#confirm-dialog').waitFor({state:'hidden'});await page.locator('#compose-replay-note').waitFor();return;}
    await page.locator('#confirm-cancel').click();await page.locator('#confirm-dialog').waitFor({state:'hidden'});
   }
   if(await page.locator('#run-notebook[open]').count()){await page.locator('.run-notebook-close').click();await page.locator('#run-notebook').waitFor({state:'hidden'});}
   if(name==='replay-confirmation'||name==='replay-composer'){
    await visit('workbench');
    await page.waitForFunction(()=>window.CodexTeamSuite.state.initialRefreshDone&&document.querySelector('.task-draft-panel')?.dataset.state!=='loading');
    if(await page.locator('#task-draft-restore').isVisible()){
     await page.locator('#task-draft-restore').click();
     if(await page.locator('#confirm-dialog[open]').count())await page.locator('#confirm-accept').click();
    }
    await page.waitForFunction(()=>!['loading','saving','available','conflict'].includes(document.querySelector('.task-draft-panel')?.dataset.state));
    await visit('runs');await page.locator('#run-replay-open').click();await page.locator('#confirm-dialog[open]').waitFor();
    if(name==='replay-composer'){await page.locator('#confirm-accept').click();await page.locator('#confirm-dialog').waitFor({state:'hidden'});await page.locator('#compose-replay-note').waitFor();}
    return;
   }
   if(name==='run-notebook'){
    await page.locator('.navigation [data-page="runs"]').first().click();
    await page.locator('#runs-list button').first().click();
    await page.locator('#run-notebook-open').click();
    await page.waitForFunction(()=>!document.querySelector('#run-notebook-note').disabled);
    await page.locator('#run-notebook-note').focus();return;
   }
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
  const auditDialog=async(selector,name,language,theme)=>{
   const dims=await page.locator(selector).evaluate(dialog=>({width:innerWidth,scroll:document.documentElement.scrollWidth,dialog_width:dialog.clientWidth,dialog_scroll:dialog.scrollWidth,lang:document.documentElement.lang,theme:document.documentElement.dataset.theme}));
   checks.push({phase,language,theme,name,...dims});
   assert(dims.dialog_scroll<=dims.dialog_width+1,`${name} must fit horizontally`);
   assert(await page.locator(selector).evaluate(dialog=>dialog.contains(document.activeElement)),`${name} must contain focus`);
   const closeVisible=await page.locator(selector).evaluate(dialog=>{
    dialog.scrollTop=dialog.scrollHeight;
    const bounds=dialog.getBoundingClientRect(),close=dialog.querySelector('#task-templates-close,.run-comparison-close,.run-notebook-close,#confirm-cancel').getBoundingClientRect();
    const visible=close.top>=bounds.top&&close.bottom<=bounds.bottom;
    dialog.scrollTop=0;return visible;
   });
   assert(closeVisible,`${name} close control must remain visible after scrolling`);
   if(language==='en'){
    const labels=await page.locator(selector).evaluate(dialog=>[...dialog.querySelectorAll('button,label,h1,h2,h3,h4,dt')].filter(node=>node.getClientRects().length).map(node=>node.textContent.trim()).filter(value=>/[А-Яа-яЁё]/.test(value)&&!/(?:ТЕСТ|Тестов|тестов)/.test(value)));
    for(const text of labels)untranslated.push({name,language,theme,text});
   }
   if(theme==='obsidian-violet')await page.screenshot({path:path.join(output,`${phase}-${language}-${theme}-${name}.png`)});
  };
  const captureCurated=async(name,dialog,scroll=0)=>{
   const viewport=page.viewportSize();await page.setViewportSize({width:1600,height:1000});
   if(dialog)await page.locator(dialog).evaluate((node,top)=>{node.scrollTop=top;},scroll);
   await page.screenshot({path:path.join(output,`${phase}-${name}-fixture.png`)});
   await page.setViewportSize(viewport);
  };
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
      if(name==='run-notebook'){await auditDialog('#run-notebook',name,language,theme);continue;}
      if(name==='replay-confirmation'){await auditDialog('#confirm-dialog',name,language,theme);continue;}
      const dims=await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth,lang:document.documentElement.lang,theme:document.documentElement.dataset.theme}));
      checks.push({phase,language,theme,name,...dims});
      if(language==='en'&&theme==='obsidian-violet'&&width===1366){const labels=await page.evaluate(()=>[...document.querySelectorAll('button,label,legend,summary,option,h1,h2,h3,th')].filter(n=>n.getClientRects().length&&!n.closest('pre,code')).map(n=>n.textContent.trim()).filter(text=>/[А-Яа-яЁё]/.test(text)&&!/(?:ТЕСТ|Тестов|тестов|Русский)/.test(text)));for(const text of labels)untranslated.push({name,text});}

      if(width===1366&&((theme==='obsidian-violet')||(name==='intelligence'))){
       await page.screenshot({path:path.join(output,`${phase}-${language}-${theme}-${name}.png`),fullPage:true});
      }
     }
    // Optional focused matrix avoids unrelated rc7 dialogs while testing rc8 integrations.
    if(process.env.QA_NOTEBOOK_ONLY==='1'||process.env.QA_REPLAY_ONLY==='1')continue;
    // rc7 dialogs receive the same requested RU/EN, theme and viewport coverage as pages.
    await visit('workbench');
    await page.locator('#task-templates-open').click();await page.locator('[data-template-id="fixture-template-1"]').click();await page.locator('#task-template-save').waitFor();await page.waitForFunction(()=>!document.querySelector('#task-template-name').disabled);
    await auditDialog('#task-templates-dialog','task-templates',language,theme);await page.locator('#task-templates-close').click();
    await visit('history');await page.locator('#run-comparison-open').click();
    await page.locator('#run-comparison-left').selectOption('fixture-run');await page.locator('#run-comparison-right').selectOption('fixture-run-2');
    await page.waitForFunction(()=>document.querySelectorAll('.run-comparison-card').length===2);
    await auditDialog('#run-comparison','run-comparison',language,theme);await page.locator('.run-comparison-close').click();
    }
   }
  }
  if(process.env.QA_REPLAY_MATRIX_ONLY==='1'){
   assert(contrast.every(row=>row.ratio>=4.5),'Theme contrast below AA');assert.deepEqual(errors,[]);assert.deepEqual(unknown,[]);assert.deepEqual(untranslated,[]);assert.deepEqual(checks.filter(c=>c.scroll>c.width+1),[]);
   console.log(JSON.stringify({checks:checks.length,errors,unknown,untranslated,fixtureOnly:true,windowsDpi:false}));return;
  }
  if(process.env.QA_REPLAY_ONLY==='1'){
   await visit('settings');
   if(await page.locator('#settings-language').inputValue()!=='ru')await Promise.all([page.waitForNavigation({waitUntil:'load'}),page.locator('#settings-language').selectOption('ru')]);
   await visit('settings');await page.locator('#settings-theme').selectOption('obsidian-violet');await visit('workbench');
   if(await page.locator('#task-draft-restore').isVisible())await page.locator('#task-draft-restore').click();
   await page.locator('#task').fill('ТЕСТ: текущая задача до повторения');await page.locator('#workspace').fill(project.path);
   await page.locator('#run-access-level').selectOption('full-access');await page.locator('#run-form .advanced-options').evaluate(node=>node.open=true);
   await page.locator('#auto-commit').check();await page.locator('#isolated').uncheck();await page.locator('#max-parallel').fill('4');
   const readEditor=()=>page.evaluate(()=>Object.fromEntries(['task','workspace','run-mode','run-pack','run-access-level','max-iterations','max-calls','max-duration','max-parallel','auto-commit','isolated'].map(id=>{const input=document.getElementById(id);return [id,input.type==='checkbox'?input.checked:input.value];})));
   const originalEditor=await readEditor();
   await visit('runs');await page.locator('#run-replay-open').click();await page.locator('#confirm-dialog[open]').waitFor();await page.waitForFunction(()=>!document.querySelector('#toast-region .toast'));await captureCurated('replay-confirmation','#confirm-dialog');
   await page.locator('#confirm-cancel').click();await page.locator('#confirm-dialog').waitFor({state:'hidden'});assert.deepEqual(await readEditor(),originalEditor,'Cancelled replay changed the task form');
   await page.route('**/api/runs/*/replay',route=>route.fulfill({status:404,contentType:'application/json',body:JSON.stringify({detail:'ТЕСТ: исходный запуск недоступен'})}));
   await page.locator('#run-replay-open').click();await page.waitForFunction(()=>!document.querySelector('#run-replay-open').disabled);assert.deepEqual(await readEditor(),originalEditor,'Unavailable source changed the task form');assert.equal(await page.locator('#confirm-dialog[open]').count(),0);await page.unroute('**/api/runs/*/replay');
   let releaseReplay,replayEntered,replayFinished;const enteredReplay=new Promise(resolve=>replayEntered=resolve),finishedReplay=new Promise(resolve=>replayFinished=resolve);
   await page.route('**/api/runs/*/replay',async route=>{replayEntered();await new Promise(resolve=>releaseReplay=resolve);await route.fulfill({contentType:'application/json',body:JSON.stringify(replaySnapshot(run.id))});replayFinished();});
   await page.locator('#run-replay-open').click();await enteredReplay;await visit('workbench');await page.locator('#task').fill('ТЕСТ: новый ввод, пока источник загружается');
   releaseReplay();await finishedReplay;await page.waitForFunction(()=>!document.querySelector('#run-replay-open').disabled);assert.equal(await page.locator('#task').inputValue(),'ТЕСТ: новый ввод, пока источник загружается');assert.equal(await page.locator('#confirm-dialog[open]').count(),0);await page.unroute('**/api/runs/*/replay');
   await visit('replay-composer');
   const applied=await readEditor();assert.equal(applied.task,run.task,'Replay must use the complete literal task, not a summary');assert.equal(applied.workspace,run.original_workspace,'Replay must use the original project, not the isolated run path');
   assert.equal(applied['run-mode'],'quick');assert.equal(applied['run-pack'],'software-development');assert.equal(applied['max-iterations'],'2');assert.equal(applied['max-calls'],'7');
   assert.equal(Math.round(Number(applied['max-duration'])*60),31,'Replay changed a valid second-based limit');assert(await page.locator('#max-duration').evaluate(input=>input.validity.valid),'31 seconds must be a valid composer limit');
   assert.equal(applied['run-access-level'],'standard');assert.equal(applied.isolated,true);assert.equal(applied['auto-commit'],false);assert.equal(applied['max-parallel'],'2');
   assert((await page.locator('#compose-replay-note').innerText()).includes(run.id));
   await page.waitForFunction(()=>document.querySelector('.task-draft-panel').dataset.state==='saved');assert.equal(composeDraft.draft.data.task,run.task);assert.equal(composeDraft.draft.data.max_run_duration,31);assert(!('access_level' in composeDraft.draft.data));
   await page.waitForFunction(()=>!document.querySelector('#toast-region .toast'));await page.locator('#task-composer').scrollIntoViewIfNeeded();await captureCurated('replay-composer');
   await page.locator('#compose-replay-note button').click();assert(await page.locator('#compose-replay-note').isHidden());
   assert.equal(writes.filter(write=>write.path==='/api/runs').length,0,'Replay must not start a run');assert(!writes.some(write=>/\/providers\/.*\/test|\/login|\/control$/.test(write.path)),'Replay must not invoke providers, login or control');
   productivityChecks.push('replay confirmation and cancel preserve editor; missing source and late form edit do not overwrite; complete literal task uses original project; unsafe controls reset; 31-second limit remains valid and autosaved; hint dismiss works; zero run creation or provider calls');
   assert(contrast.every(row=>row.ratio>=4.5),'Theme contrast below AA');assert.deepEqual(errors,[]);assert.deepEqual(unknown,[]);assert.deepEqual(untranslated,[]);assert.deepEqual(checks.filter(c=>c.scroll>c.width+1),[]);
   console.log(JSON.stringify({checks:checks.length,errors,unknown,untranslated,fixtureOnly:true,windowsDpi:false,productivityChecks}));return;
  }
  if(process.env.QA_NOTEBOOK_MATRIX_ONLY==='1'){
   assert(contrast.every(row=>row.ratio>=4.5),'Theme contrast below AA');assert.deepEqual(errors,[]);assert.deepEqual(unknown,[]);assert.deepEqual(untranslated,[]);assert.deepEqual(checks.filter(c=>c.scroll>c.width+1),[]);
   console.log(JSON.stringify({checks:checks.length,errors,unknown,untranslated,fixtureOnly:true,windowsDpi:false}));return;
  }
  // rc8 run notebook: production mount, History callbacks and an actual browser download.
  if(await page.locator('#run-notebook-open').count()){
   await visit('settings');
   if(await page.locator('#settings-language').inputValue()!=='ru')await Promise.all([page.waitForNavigation({waitUntil:'load'}),page.locator('#settings-language').selectOption('ru')]);
   await visit('settings');await page.locator('#settings-theme').selectOption('obsidian-violet');
   await visit('run-notebook');
   const localNote='ТЕСТОВЫЕ ДАННЫЕ: проверить страницу авторизации и сохранить решение.\nЛичная заметка: <script>literal</script> — User content stays unchanged.';
   await page.locator('#run-notebook-note').fill(localNote);await page.locator('#run-notebook-favorite').check();
   assert(await page.locator('#run-notebook-export').isDisabled(),'Dirty note must block exporting an older report');
   const beforeSave=writes.filter(write=>write.path.endsWith('/notebook')).length;
   await page.locator('#run-notebook-save').evaluate(button=>{button.click();button.click();});
   await page.waitForFunction(()=>/Заметка сохранена|Note saved/.test(document.querySelector('.run-notebook-status').textContent));
   assert.equal(writes.filter(write=>write.path.endsWith('/notebook')).length,beforeSave+1,'Repeated save must be serialized');
   assert.equal(notebooks.get(run.id).note,localNote);assert.equal(notebooks.get(run.id).favorite,true);
   await captureCurated('run-notebook','#run-notebook');
   const downloaded=page.waitForEvent('download',{timeout:10000});await page.locator('#run-notebook-export').click();const download=await downloaded.catch(async error=>{throw new Error(`${error.message}; notebook status=${await page.locator('.run-notebook-status').innerText()}; report reads=${JSON.stringify(reportReads)}; page errors=${JSON.stringify(errors)}`);});
   assert.equal(download.suggestedFilename(),'codex-team-fixture-run.md');
   const downloadPath=await download.path(),downloadText=fs.readFileSync(downloadPath,'utf8');
   assert(downloadText.includes(localNote));assert(downloadText.includes('TEST FIXTURE'));assert.equal(reportReads.at(-1).language,'ru');
   await download.saveAs(path.join(output,`${phase}-run-report-fixture.md`));
   await page.locator('.run-notebook-close').click();await page.locator('#run-notebook').waitFor({state:'hidden'});
   assert.equal(await page.evaluate(()=>document.activeElement.id),'run-notebook-open','Close should restore the integration trigger focus');
   await visit('history');await page.locator('#history-list .notebook-favorite-badge').waitFor();
   const favoriteContrast=await page.locator('#history-list .notebook-favorite-badge').first().evaluate(badge=>{
    const canvas=document.createElement('canvas');canvas.width=canvas.height=1;const context=canvas.getContext('2d'),layers=[];
    for(let node=badge;node;node=node.parentElement)layers.push(getComputedStyle(node).backgroundColor);
    context.fillStyle='#000';context.fillRect(0,0,1,1);for(const color of layers.reverse()){context.fillStyle=color;context.fillRect(0,0,1,1);}
    const background=[...context.getImageData(0,0,1,1).data].slice(0,3);context.clearRect(0,0,1,1);context.fillStyle=getComputedStyle(badge).color;context.fillRect(0,0,1,1);
    const foreground=[...context.getImageData(0,0,1,1).data].slice(0,3),lum=rgb=>rgb.map(value=>{value/=255;return value<=.04045?value/12.92:((value+.055)/1.055)**2.4;}).reduce((sum,value,index)=>sum+value*[.2126,.7152,.0722][index],0),a=lum(foreground),b=lum(background);
    return {theme:document.documentElement.dataset.theme,language:document.documentElement.lang,fg:'favorite badge text',bg:'composited ancestor surfaces',foreground,background,ratio:Number(((Math.max(a,b)+.05)/(Math.min(a,b)+.05)).toFixed(2))};
   });contrast.push(favoriteContrast);assert(favoriteContrast.ratio>=4.5,'Favorite badge text must remain readable');
   assert((await page.locator('#history-list').innerText()).includes('Есть заметка'));
   await page.locator('#history-favorites').check();await page.waitForFunction(()=>window.CodexTeamSuite.state.historyRows.length===1);
   assert.equal(await page.locator('#history-list .history-note-action').count(),1);await captureCurated('history-favorites');
   await page.locator('#history-list .history-note-action').first().click();await page.waitForFunction(()=>!document.querySelector('#run-notebook-note').disabled);
   assert.equal(await page.locator('#run-notebook-note').inputValue(),localNote,'History action must reopen the saved notebook');
   const remote={...notebooks.get(run.id),revision:notebooks.get(run.id).revision+1,note:'ТЕСТ: актуальная заметка из другого окна'};notebooks.set(run.id,remote);
   const conflicting='ТЕСТ: мой несохранённый текст после конфликта';await page.locator('#run-notebook-note').fill(conflicting);await page.locator('#run-notebook-save').click();
   await page.locator('.run-notebook-status.is-error').waitFor();assert.equal(await page.locator('#run-notebook-note').inputValue(),conflicting);
   assert(await page.locator('#run-notebook-export').isDisabled());assert.equal(notebooks.get(run.id).note,remote.note);
   await captureCurated('run-notebook-conflict','#run-notebook');
   await page.locator('.run-notebook-close').click();await page.locator('#confirm-dialog[open]').waitFor();await page.locator('#confirm-cancel').click();
   assert.equal(await page.locator('#run-notebook-note').inputValue(),conflicting,'Cancel discard must retain the local note');
   await page.locator('#confirm-dialog').waitFor({state:'hidden'});await page.locator('#run-notebook-note').focus();await page.waitForTimeout(50);
   await page.keyboard.press('Escape');await page.locator('#confirm-dialog[open]').waitFor();await page.locator('#confirm-accept').click();await page.locator('#run-notebook').waitFor({state:'hidden'});
   await page.locator('#history-favorites').uncheck();await page.waitForFunction(()=>window.CodexTeamSuite.state.historyRows.length===2);
   await page.locator('#history-list .history-note-action').first().click();await page.waitForFunction(()=>!document.querySelector('#run-notebook-note').disabled);
   assert.equal(await page.locator('#run-notebook-note').inputValue(),remote.note,'Reopen must load the server revision after confirmed discard');
   await page.locator('#run-notebook-favorite').uncheck();await page.locator('#run-notebook-save').click();await page.waitForFunction(()=>/Заметка сохранена|Note saved/.test(document.querySelector('.run-notebook-status').textContent));
   await page.locator('.run-notebook-close').click();await page.locator('#history-favorites').check();await page.waitForFunction(()=>window.CodexTeamSuite.state.historyRows.length===0);
   assert.equal(await page.locator('#history-list .history-note-action').count(),0,'Unfavorite must disappear from the saved favorites filter');
   await page.locator('#history-favorites').uncheck();await page.waitForFunction(()=>window.CodexTeamSuite.state.historyRows.length===2);
   // Closing during report preparation must suppress the late browser download.
   await visit('run-notebook');let releaseReport,reportEntered,reportFinished;const enteredReport=new Promise(resolve=>reportEntered=resolve),finishedReport=new Promise(resolve=>reportFinished=resolve);
   await page.route('**/api/runs/*/report?*',async route=>{reportEntered();await new Promise(resolve=>releaseReport=resolve);await route.fulfill({contentType:'application/json',body:JSON.stringify({run_id:run.id,filename:'late-fixture.md',markdown:'# TEST FIXTURE: late report'})});reportFinished();});
   let lateDownloads=0;const countLate=()=>lateDownloads++;page.on('download',countLate);
   await page.locator('#run-notebook-export').click();await enteredReport;await page.locator('.run-notebook-close').click();await page.locator('#run-notebook').waitFor({state:'hidden'});
   releaseReport();await finishedReport;await page.waitForTimeout(100);page.off('download',countLate);assert.equal(lateDownloads,0);await page.unroute('**/api/runs/*/report?*');
   productivityChecks.push('run notebook saved once; real Markdown download includes saved literal note; History marks and persisted favorites filter; 409 keeps input; discard cancellation and late export are safe');
   await visit('runs');await captureCurated('runs');
  }
  if(process.env.QA_NOTEBOOK_ONLY==='1'){
   assert(contrast.every(row=>row.ratio>=4.5),'Theme contrast below AA');assert.deepEqual(errors,[]);assert.deepEqual(unknown,[]);assert.deepEqual(untranslated,[]);assert.deepEqual(checks.filter(c=>c.scroll>c.width+1),[]);
   console.log(JSON.stringify({checks:checks.length,errors,unknown,untranslated,fixtureOnly:true,windowsDpi:false,productivityChecks}));return;
  }
  // rc6 production modules under the actual application, with controlled local HTTP data.
  await visit('workbench');await page.locator('#task-draft-status').waitFor();
  await page.locator('#task').fill('ТЕСТОВЫЙ ЧЕРНОВИК: сохранить после перезапуска <script>literal</script>');
  await page.locator('#workspace').fill(project.path);await page.locator('#run-access-level').selectOption('full-access');
  await page.waitForFunction(()=>/saved on this computer|сохранён на этом компьютере/.test(document.querySelector('#task-draft-status').textContent));
  assert(!('access_level' in composeDraft.draft.data),'Consent cannot enter a draft');
  await page.screenshot({path:path.join(output,`${phase}-draft-saved-fixture.png`),fullPage:true});
  composeDraft.draft.data.pack='missing-fixture-pack';
  await page.reload();await page.locator('#task-draft-restore').waitFor();
  assert.equal(await page.locator('#task').inputValue(),'');await page.locator('#task-draft-restore').click();
  assert.equal(await page.locator('#task').inputValue(),'ТЕСТОВЫЙ ЧЕРНОВИК: сохранить после перезапуска <script>literal</script>');
  assert.equal(await page.locator('#run-access-level').inputValue(),'standard');
  assert.equal(await page.locator('#run-pack').inputValue(),'missing-fixture-pack');
  defaultAgents[0].description='TEST changed registry';await page.locator('#refresh-button').click();
  await page.waitForTimeout(200);assert.equal(await page.locator('#run-pack').inputValue(),'missing-fixture-pack');
  await page.locator('#run-pack').selectOption(defaultPacks[0].name);
  await page.locator('#task').focus();await page.keyboard.press('Control+k');
  await page.locator('#command-palette[open]').waitFor();await page.screenshot({path:path.join(output,`${phase}-command-palette-fixture.png`)});
  await page.keyboard.press('Escape');assert.equal(await page.evaluate(()=>document.activeElement.id),'task');
  await page.keyboard.press('Control+k');await page.locator('.command-palette-input').fill('quality');await page.keyboard.press('Enter');
  await page.waitForFunction(()=>window.CodexTeamSuite.state.suiteFeature==='qa');
  await visit('workbench');composeDraft.revision++;composeDraft.draft.revision=composeDraft.revision;composeDraft.draft.data.task='ТЕСТ: другое окно';
  await page.locator('#task').fill('ТЕСТ: мой локальный ввод');await page.waitForFunction(()=>document.querySelector('.task-draft-panel').dataset.state==='conflict');
  assert.equal(await page.locator('#task').inputValue(),'ТЕСТ: мой локальный ввод');
  await page.screenshot({path:path.join(output,`${phase}-draft-conflict-fixture.png`),fullPage:true});
  // Discard only this fixture's persistent buffer; never create a model run.
  composeDraft={revision:composeDraft.revision+1,draft:null};await page.reload();
  // User content must survive localization and navigation byte-for-byte.
  if(languages.includes('en')){
  await visit('architect');const idea=page.locator('#suite-root textarea').first();
  const draft='Пользовательский текст — User content: Обзор, Ошибка, Projects';await idea.fill(draft);
  await visit('settings');cancelLanguage=true;warned=false;await page.locator('#settings-language').selectOption('ru');await page.waitForTimeout(100);assert(warned,'Unsaved form language warning missing');cancelLanguage=false;
  await visit('architect');assert.equal(await page.locator('#suite-root textarea').first().inputValue(),draft);
  await page.reload();await visit('settings');await page.locator('#settings-theme').selectOption('emerald-tech');await page.locator('#save-appearance-button').click();await page.waitForTimeout(200);await page.reload();await visit('settings');
  assert.equal(await page.locator('#settings-language').inputValue(),'en');assert.equal(await page.locator('#settings-theme').inputValue(),'emerald-tech');
  }
  // rc7 product workflows use the production application and explicit HTTP contracts.
  await visit('settings');const previousLanguage=await page.locator('#settings-language').inputValue();
  if(previousLanguage!=='ru')await Promise.all([page.waitForNavigation({waitUntil:'load'}),page.locator('#settings-language').selectOption('ru')]);
  await visit('settings');await page.locator('#settings-theme').selectOption('obsidian-violet');await visit('workbench');
  const templateTask='ТЕСТОВЫЕ ДАННЫЕ: проверить документацию <script>literal</script>';
  await page.locator('#task').fill(templateTask);await page.locator('#workspace').fill(project.path);await page.locator('#run-pack').selectOption(defaultPacks[0].name);await page.locator('#run-access-level').selectOption('full-access');
  await page.locator('#task-templates-open').click();await page.locator('#task-templates-new').click();
  await page.locator('#task-template-name').fill('ТЕСТОВЫЕ ДАННЫЕ: мой шаблон');assert.equal(await page.locator('#task-template-description').getAttribute('maxlength'),'1000');
  const createsBeforeBoundary=writes.filter(write=>write.path==='/api/task-templates'&&write.method==='POST').length;
  await page.locator('#task-template-description').evaluate(node=>{node.value='д'.repeat(1001);node.dispatchEvent(new Event('input',{bubbles:true}));});await page.locator('#task-template-save').click();await page.locator('#task-templates-error').waitFor();
  assert.equal(writes.filter(write=>write.path==='/api/task-templates'&&write.method==='POST').length,createsBeforeBoundary,'Overlong metadata must be rejected before a request');assert.equal((await page.locator('#task-template-description').inputValue()).length,1001);
  await page.locator('#task-template-description').fill('ТЕСТ '+ 'д'.repeat(995));await page.locator('#task-template-save').click();
  await page.waitForFunction(()=>/сохранён|saved/.test(document.querySelector('.task-templates-status').textContent));
  const createdTemplate=()=>templates.find(item=>item.id==='fixture-template-created');
  assert.equal(createdTemplate().data.task,templateTask);assert.equal(createdTemplate().description.length,1000);assert(!('access_level' in createdTemplate().data),'Access consent must never enter a template');
  const templatePreview=await page.locator('.task-templates-preview').textContent();assert(templatePreview.includes(templateTask),'User task text must stay literal');assert(templatePreview.includes('Режим: Стандартный'),'Known template metadata must use localized labels');
  const capturedData=JSON.stringify(createdTemplate().data);
  await page.locator('#task-templates-close').click();await page.locator('#task').fill('ТЕСТ: текущая задача остаётся до подтверждения');await page.locator('#run-access-level').selectOption('read-only');
  await page.locator('#task-templates-open').click();await page.locator('#task-template-name').fill('ТЕСТОВЫЕ ДАННЫЕ: проверка документации — сохранено');await page.locator('#task-template-description').fill('ТЕСТ: имя изменено, сохранённая задача не заменяется текущей');await page.locator('#task-template-save').click();
  await page.waitForFunction(()=>/сохранён|saved/.test(document.querySelector('.task-templates-status').textContent));assert.equal(createdTemplate().revision,2);assert.equal(JSON.stringify(createdTemplate().data),capturedData);
  await captureCurated('task-templates','#task-templates-dialog');
  await page.locator('#task-template-apply').click();await page.locator('#confirm-dialog[open]').waitFor();await page.locator('#confirm-cancel').click();assert.equal(await page.locator('#task').inputValue(),'ТЕСТ: текущая задача остаётся до подтверждения');
  await page.locator('#task-template-apply').click();await page.locator('#confirm-dialog[open]').waitFor();await page.locator('#confirm-accept').click();await page.locator('#task-templates-dialog').waitFor({state:'hidden'});
  assert.equal(await page.locator('#task').inputValue(),templateTask);assert.equal(await page.locator('#run-access-level').inputValue(),'read-only');assert(!writes.some(write=>write.path==='/api/runs'&&write.method==='POST'),'Applying a template cannot start a run');
  productivityChecks.push('template 1000/1001 boundary, localized metadata and literal task, create/revision update, confirmed apply, retained permissions, no run start');
  await page.locator('#task-templates-open').click();const preservedName='ТЕСТ: несохранённое имя сохраняется при ошибках';await page.locator('#task-template-name').fill(preservedName);
  const preservedDescription=await page.locator('#task-template-description').inputValue();
  for(const failure of [401,403,409,404,500,'offline']){
   await page.route('**/api/task-templates/fixture-template-created',route=>failure==='offline'?route.abort('failed'):route.fulfill({status:failure,contentType:'application/json',body:JSON.stringify({detail:'ТЕСТ: ошибка шаблона'})}));
   await page.locator('#task-template-save').click();await page.locator('#task-templates-error').waitFor();assert.equal(await page.locator('#task-template-name').inputValue(),preservedName);assert.equal(await page.locator('#task-template-description').inputValue(),preservedDescription);assert.equal(await page.locator('#task').inputValue(),templateTask);assert(await page.evaluate(()=>window.CodexTeamSuite.state.online),'Template errors must not mark the server offline');
   await page.unroute('**/api/task-templates/fixture-template-created');
  }
  await page.locator('#task-template-save').click();await page.waitForFunction(()=>/сохранён|saved/.test(document.querySelector('.task-templates-status').textContent));
  let releaseTemplates,templatesEntered,templatesFinished;const templateEntered=new Promise(resolve=>templatesEntered=resolve),templateFinished=new Promise(resolve=>templatesFinished=resolve);
  await page.route('**/api/task-templates?*',async route=>{templatesEntered();await new Promise(resolve=>releaseTemplates=resolve);await route.fulfill({contentType:'application/json',body:JSON.stringify({items:[],total:0})});templatesFinished();});
  await page.locator('#task-templates-query').fill('');await page.locator('#task-templates-query').press('Enter');await templateEntered;await page.locator('#task-templates-close').click();releaseTemplates();await templateFinished;await page.unroute('**/api/task-templates?*');
  await page.locator('#task-templates-open').click();await page.locator('[data-template-id="fixture-template-created"]').waitFor();assert.equal(await page.locator('#task').inputValue(),templateTask);
  await page.locator('#task-template-delete').click();await page.locator('#confirm-dialog[open]').waitFor();await page.locator('#confirm-cancel').click();assert(createdTemplate());
  await page.locator('#task-template-delete').click();await page.locator('#confirm-dialog[open]').waitFor();await page.locator('#confirm-accept').click();await page.waitForFunction(()=>/удалён|deleted/.test(document.querySelector('.task-templates-status').textContent));assert(!createdTemplate());assert.equal(await page.locator('#task').inputValue(),templateTask);await page.locator('#task-templates-close').click();
  productivityChecks.push('template conflict, missing, server failure, offline and late list preserve user input; confirmed delete');
  await visit('history');await captureCurated('history');await page.locator('#run-comparison-open').click();await page.locator('#run-comparison-left').selectOption('fixture-run');await page.locator('#run-comparison-right').selectOption('fixture-run-2');
  await page.waitForFunction(()=>document.querySelectorAll('.run-comparison-card').length===2);
  const metrics=await page.locator('.run-comparison-metrics').evaluateAll(nodes=>nodes.map(node=>[...node.querySelectorAll('dd')].map(item=>item.textContent)));
  assert.equal(metrics[0][2],'Нет данных');assert.equal(metrics[1][2],'0');assert.equal(metrics[1][1],'0 с');assert.equal(metrics[1][3],'0');assert.equal(await page.locator('.run-comparison-warning').count(),2);
  assert.equal(await page.locator('.run-comparison-role h5').first().innerText(),'Координатор');
  await captureCurated('run-comparison','#run-comparison',430);
  const comparisonButton=pattern=>page.locator('.run-comparison-actions button').filter({hasText:pattern});
  await comparisonButton(/Поменять местами|Swap runs/).click();await page.waitForFunction(()=>document.querySelector('.run-comparison-id')?.textContent==='fixture-run-2');assert.equal(comparisonReads.at(-1).left,'fixture-run-2');
  const beforeRefresh=comparisonReads.length;await comparisonButton(/Обновить сравнение|Refresh comparison/).click();await page.waitForFunction(()=>document.querySelectorAll('.run-comparison-card').length===2);assert.equal(comparisonReads.length,beforeRefresh+1);
  for(const failure of [403,404,500,'offline']){
   await page.route('**/api/run-comparison?*',route=>failure==='offline'?route.abort('failed'):route.fulfill({status:failure,contentType:'application/json',body:JSON.stringify({detail:'ТЕСТ: ошибка сравнения'})}));
   await comparisonButton(/Обновить сравнение|Refresh comparison/).click();await page.locator('.run-comparison-status.is-error').waitFor();assert(await page.evaluate(()=>window.CodexTeamSuite.state.online),'Comparison errors must not mark unrelated services offline');assert.equal(await page.locator('#run-comparison-left').inputValue(),'fixture-run-2');assert.equal(await page.locator('#task').inputValue(),templateTask);await page.unroute('**/api/run-comparison?*');
  }
  let releaseComparison,comparisonEntered,comparisonFinished;const enteredComparison=new Promise(resolve=>comparisonEntered=resolve),finishedComparison=new Promise(resolve=>comparisonFinished=resolve);
  await page.route('**/api/run-comparison?*',async route=>{comparisonEntered();await new Promise(resolve=>releaseComparison=resolve);await route.fulfill({contentType:'application/json',body:JSON.stringify({left:comparisonRun(secondRun),right:comparisonRun(run),comparable_project:true,warnings:['incomplete_usage']})});comparisonFinished();});
  await comparisonButton(/Обновить сравнение|Refresh comparison/).click();await enteredComparison;await page.locator('.run-comparison-close').click();releaseComparison();await finishedComparison;await page.unroute('**/api/run-comparison?*');assert.equal(await page.locator('#task').inputValue(),templateTask);
  await page.locator('#run-comparison-open').click();await page.waitForFunction(()=>document.querySelectorAll('.run-comparison-card').length===2);await page.locator('.run-comparison-card').first().getByRole('button',{name:/Открыть запуск|Open run/}).click();await page.waitForFunction(()=>window.CodexTeamSuite.state.selectedRun?.id==='fixture-run-2');assert.equal(await page.locator('#detail-task-text').innerText(),secondRun.task);
  productivityChecks.push('comparison unknown versus zero, factual warnings, swap, explicit refresh, errors/offline/late safety and correct open-run navigation');
  const savedTotals=run.usage_total,savedComplete=run.usage_complete;
  run.usage_total={input:null,output:null,cached:null,total:null};run.usage_complete=false;fixtureRuns=[run];await visit('workbench');await page.locator('#refresh-button').click();await page.waitForFunction(()=>document.querySelector('#dashboard-usage').textContent==='—');assert(/SDK/.test(await page.locator('#dashboard-usage-scope').innerText()));
  fixtureRuns=[run,secondRun];await page.locator('#refresh-button').click();await page.waitForFunction(()=>document.querySelector('#dashboard-usage').textContent==='0');assert(/Часть|Part/.test(await page.locator('#dashboard-usage-scope').innerText()));
  run.usage_total=savedTotals;if(savedComplete===undefined)delete run.usage_complete;else run.usage_complete=savedComplete;await page.locator('#refresh-button').click();await page.waitForFunction(()=>document.querySelector('#dashboard-usage').textContent==='30');productivityChecks.push('dashboard unknown is em dash; observed zero with unknown run is explicitly partial');
  // Restore the locale expected by the existing rc6 interaction checks.
  composeDraft={revision:composeDraft.revision+1,draft:null};await page.reload();await visit('settings');
  if(previousLanguage!=='ru')await Promise.all([page.waitForNavigation({waitUntil:'load'}),page.locator('#settings-language').selectOption(previousLanguage)]);
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
  await visit('workbench');await page.locator('#task').fill('ТЕСТ: ввод при частичной ошибке');
  await page.route('**/api/runs?*',route=>route.fulfill({status:500,contentType:'application/json',body:JSON.stringify({detail:'Fixture summary failure'})}));
  await page.locator('#refresh-button').click();await page.locator('#service-banner.service-partial').waitFor();
  assert(await page.evaluate(()=>window.CodexTeamSuite.state.online),'A failed summary is not an offline server');
  assert.equal(await page.locator('#task').inputValue(),'ТЕСТ: ввод при частичной ошибке');
  await page.screenshot({path:path.join(output,`${phase}-partial-data-fixture.png`),fullPage:true});
  await page.unroute('**/api/runs?*');await page.locator('#service-banner button').click();await page.locator('#service-banner').waitFor({state:'hidden'});
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
  fs.writeFileSync(path.join(output,`${phase}-redesign-results.json`),JSON.stringify({fixtureOnly:true,windowsDpi:false,checks,contrast,untranslated,errors,unknown,overflows,productivityChecks,writes:writes.length},null,2));
  console.log(JSON.stringify({checks:checks.length,contrast,untranslated,errors,unknown,overflows,fixtureOnly:true,windowsDpi:false}));
  assert(contrast.every(row=>row.ratio>=4.5),'Theme contrast below AA');assert.deepEqual(errors,[]);assert.deepEqual(unknown,[]);assert.deepEqual(untranslated,[]);assert.deepEqual(overflows,[]);
 }finally{fs.writeFileSync(path.join(output,`${phase}-redesign-results.json`),JSON.stringify({fixtureOnly:true,windowsDpi:false,checks,contrast,untranslated,errors,unknown,productivityChecks,overflows:checks.filter(c=>c.scroll>c.width+1),writes:writes.length},null,2));await browser.close();server.close();}
})().catch(error=>{console.error(error);server.close();process.exitCode=1;});
