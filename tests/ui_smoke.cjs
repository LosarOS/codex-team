const fs=require('fs'),vm=require('vm'),assert=require('assert');
const path=require('path');const folder=process.argv[2]||__dirname;
const all=[];
class ClassList{constructor(el){this.el=el;}add(v){const s=new Set(this.el.className.split(/\s+/).filter(Boolean));s.add(v);this.el.className=[...s].join(' ');}remove(v){this.el.className=this.el.className.split(/\s+/).filter(c=>c!==v).join(' ');}contains(v){return this.el.className.split(/\s+/).includes(v);}toggle(v,force){const yes=force===undefined?!this.contains(v):force;if(yes)this.add(v);else this.remove(v);return yes;}}
class El{constructor(tag){this.tagName=tag.toUpperCase();this.children=[];this.dataset={};this.attributes={};this.className='';this.classList=new ClassList(this);this.value='';this.textContent='';this.hidden=false;this.disabled=false;this.listeners={};this.style={setProperty(){},removeProperty(){}};all.push(this);}append(...nodes){nodes.forEach(n=>{if(n.parentElement)n.parentElement.children=n.parentElement.children.filter(x=>x!==n);if(typeof n==='object')n.parentElement=this;this.children.push(n);});}replaceChildren(...nodes){this.children.forEach(n=>{if(typeof n==="object"&&n.parentElement===this)n.parentElement=null;});this.children=[];this.append(...nodes);}remove(){if(this.parentElement)this.parentElement.children=this.parentElement.children.filter(n=>n!==this);}setAttribute(k,v){this.attributes[k]=String(v);if(k==='id')this.id=v;}removeAttribute(k){delete this.attributes[k];}addEventListener(k,fn,opts){(this.listeners[k]??=[]).push({fn,opts});}dispatchEvent(e){e.target??=this;return Promise.all((this.listeners[e.type]||[]).map(x=>x.fn(e)));}querySelectorAll(s){return query(s,this);}querySelector(s){return query(s,this)[0]||null;}scrollIntoView(){}focus(){}click(){return this.dispatchEvent({type:'click',preventDefault(){}});}reportValidity(){return true;}get childElementCount(){return this.children.length;}get innerHTML(){throw new Error('Unsafe innerHTML read');}set innerHTML(v){throw new Error('Unsafe innerHTML write');}get scrollHeight(){return 100;}get clientHeight(){return 100;}get scrollTop(){return this._scroll||0;}set scrollTop(v){this._scroll=v;}}
function query(selector,parent){let selectors=selector.split(',').map(s=>s.trim());return all.filter(el=>selectors.some(s=>{let scope=null;if(s.startsWith('#')&&s.includes(' ')){const [id,...rest]=s.split(' ');scope=id.slice(1);s=rest.join(' ');}if(parent||scope){let p=el.parentElement,found=false;while(p){if(p===parent||p.id===scope){found=true;break;}p=p.parentElement;}if(!found)return false;}const checked=s.includes(':checked'),opened=s.includes('[open]');s=s.replace(':checked','').replace('[open]','');if(checked&&!el.checked)return false;if(opened&&!el.open)return false;const attr=s.match(/\[([^=\]]+)(?:="([^"]*)")?\]/);if(attr){const key=attr[1],v=key.startsWith('data-')?el.dataset[key.slice(5).replace(/-([a-z])/g,(_,c)=>c.toUpperCase())]:el.attributes[key];if(v===undefined||attr[2]!==undefined&&v!==attr[2])return false;s=s.replace(attr[0],'');}if(s.startsWith('#'))return el.id===s.slice(1);if(s.startsWith('.'))return el.classList.contains(s.slice(1));if(s&&s!=='*')return el.tagName===s.toUpperCase();return true;}));}
const html=fs.readFileSync(path.join(folder,'index.html'),'utf8');const idMap={};
for(const match of html.matchAll(/<([a-z][a-z0-9]*)\b([^>]*)>/gi)){const el=new El(match[1]);for(const a of match[2].matchAll(/([\w-]+)(?:="([^"]*)")?/g)){const [_,k,v]=a;if(k==='class')el.className=v||'';else if(k==='id'){el.id=v;assert(!idMap[v],`duplicate ID ${v}`);idMap[v]=el;}else if(k.startsWith('data-'))el.dataset[k.slice(5).replace(/-([a-z])/g,(_,c)=>c.toUpperCase())]=v||'';else el.attributes[k]=v||'';if(k==='value')el.value=v||'';if(k==='checked')el.checked=true;if(k==='hidden')el.hidden=true;if(k==='name')el.name=v;}}
for(const [id,value]of Object.entries({'run-mode':'standard','run-pack':'software-development','settings-theme':'system','agent-permission':'read-only','max-iterations':'3','max-calls':'15','max-parallel':'2','max-duration':'30'}))idMap[id].value=value;
const document={getElementById:id=>{assert(idMap[id],`missing ID ${id}`);return idMap[id];},querySelectorAll:query,querySelector:s=>query(s)[0],createElement:tag=>new El(tag),createTextNode:t=>new El('#text'),createDocumentFragment:()=>new El('#fragment'),documentElement:new El('html'),body:new El('body'),addEventListener(){},hidden:false};
const commands=[];const agent={name:'developer',role:'Разработчик',instructions:'<img src=x onerror=alert(1)>',permission:'workspace-write',enabled:true,builtin:true};
const run={id:'fixture_run',task:'Проверить локальную задачу '.repeat(50),workspace:'C:\\fixture',state:'USER_DECISION_REQUIRED',current_role:'developer',calls:3,iteration:1,max_iterations:1,max_agent_calls:3,max_run_duration:120,elapsed_seconds:130,mode:'standard',created_at:'2026-10-10T00:00:00Z',pipeline:['coordinator','developer','qa'],worktree:{path:'C:\\fixture-worktree',branch:'codex/fixture'},results:{developer:{verdict:'USER_DECISION_REQUIRED',summary:'Требуется решение'}},usage:[],error:'Test-only decision',usage_total:{input:20,output:10,cached:0,total:30}};
const action={id:'fixture_action',run_id:run.id,role:'developer',kind:'permission',reason:'Проверка',command:'npm install',cwd:run.workspace,scope:'Current fixture',risk:'high',requires_confirmation:true,status:'pending',allowed_decisions:['deny','cancel'],questions:[],details:{},limitation:'No grant supported in fixture'};
const productAction={...action,id:'fixture_budget',kind:'product',risk:'low',requires_confirmation:false,allowed_decisions:['resume','stop','explain']};
const settingsResponse={theme:'dark',execution_backend:'openai_api'};
const responses={'/api/settings':settingsResponse,'/api/providers/openai/key':{ok:true},'/api/providers/openai/test':{ok:true},'/api/status':{auth:{status:'CONNECTED',account:{type:'chatgpt'}},capabilities:{},settings:{theme:'dark',execution_backend:'codex_chatgpt'}},'/api/agents':[agent],'/api/packs':[{name:'software-development',description:'fixture',builtin:true}],'/health':{status:'ok',version:'0.2.0',checks:{backend:true,codex:true}},'/api/providers':{active:'codex_chatgpt',codex:{status:'CONNECTED'},openai_api:{status:'NOT CONFIGURED',configured:false}},'/api/actions':[action,productAction],'/api/actions/fixture_budget/resolve':{ok:true},'/api/projects':[],'/api/models':{data:[{model:'fixture-model',isDefault:true,supportedReasoningEfforts:[{reasoningEffort:'medium'},{reasoningEffort:'high'}]}]}};
const sandbox={document,window:{location:{hash:''},matchMedia:()=>({matches:false,addEventListener(){}}),addEventListener(){},confirm:()=>false},location:{hash:''},history:{replaceState(){}},navigator:{clipboard:{writeText:async()=>{}}},localStorage:{getItem(){return null;},setItem(k,v){commands.push({storage:k,value:v});}},Node:El,Event:class{constructor(type,opts){this.type=type;Object.assign(this,opts);}},Intl,Date,JSON,Set,Map,URL,URLSearchParams,AbortController,Blob,console,setTimeout:()=>1,clearTimeout(){},setInterval(){},fetch:async(url,opts)=>{commands.push({url,method:opts.method,body:opts.body});if(url==='/api/settings'&&opts.method==='POST')Object.assign(settingsResponse,JSON.parse(opts.body));if(url==='/api/providers/openai/key'&&opts.method==='POST')responses['/api/providers'].openai_api.configured=true;let body=responses[url.split('?')[0]];if(url.startsWith('/api/runs?'))body={items:[run],total:1};if(url==='/api/runs/'+run.id)body=run;if(url.includes('/events'))body={items:[],next_cursor:0,has_more:false};if(url.includes('/diff'))body={diff:'+safe line',has_more:false};return {ok:!!body,status:body?200:404,headers:{get:()=> 'application/json'},json:async()=>body||{detail:'not found'}};}};
const code=fs.readFileSync(path.join(folder,'app.js'),'utf8');
vm.createContext(sandbox);vm.runInContext(fs.readFileSync(path.join(folder,'api-client.js'),'utf8'),sandbox);vm.runInContext(fs.readFileSync(path.join(folder,'mission-control.js'),'utf8'),sandbox);vm.runInContext(code,sandbox);
const settle=async()=>{for(let i=0;i<30;i++)await Promise.resolve();};
(async()=>{await settle();assert.equal(idMap['dashboard-actions'].textContent,2);assert(!commands.some(c=>c.url?.includes('/test')),'provider test ran automatically');assert(!commands.some(c=>c.method==='POST'),'startup mutated server');assert(!commands.some(c=>/api[-_]key/i.test(c.storage||'')),'secret storage key present');const actions=query('button',idMap['actions-list']).map(x=>x.textContent);assert(actions.includes('Запретить'));assert(!actions.includes('Разрешить один раз'),'unsupported grant rendered');await query('[data-page="runs"]')[0].click();await settle();await query('button',idMap['runs-list'])[0].click();await settle();assert.equal(idMap['detail-task-text'].textContent,run.task);assert.equal(idMap['run-error'].classList.contains('error'),false,'user decision shown red');assert(!commands.some(c=>c.url?.includes('/diff')),'diff eager loaded');await idMap['open-diff-button'].click();await settle();assert(commands.some(c=>c.url?.includes('/diff')),'diff not lazily loaded');await query('[data-page="settings"]')[0].click();await settle();
responses['/api/providers'].active='openai_api';responses['/api/providers'].openai_api.configured=false;
await idMap['refresh-button'].click();await settle();
assert.equal(idMap['api-required-banner'].hidden,false,'API key missing banner absent');assert.equal(idMap['start-button'].disabled,true,'API without key enabled start');assert(!commands.some(c=>c.url==='/api/providers/select'),'automatic provider switch');
await idMap['settings-form'].dispatchEvent({type:'submit',preventDefault(){}});await settle();const settingsCall=commands.find(c=>c.url==='/api/settings'&&c.method==='POST');assert(settingsCall);assert(!('execution_backend' in JSON.parse(settingsCall.body)),'budget save changed provider');
idMap['api-key-input'].value='fixture-dummy-key';await idMap['api-key-form'].dispatchEvent({type:'submit',preventDefault(){}});await settle();assert.equal(idMap['api-key-input'].value,'','saved key not cleared');assert(!commands.some(c=>c.storage&&c.value?.includes('fixture-dummy-key')),'key persisted to localStorage');assert(!commands.some(c=>c.url==='/api/providers/openai/test'),'key save tested provider automatically');
await query('[data-page="actions"]')[0].click();await settle();
let productCard=idMap['actions-list'].children.find(c=>query('button',c).some(b=>b.textContent==='Продолжить задачу'));
assert(productCard,'product card missing');await query('button',productCard).find(b=>b.textContent==='Продолжить задачу').click();await settle();
let budgetCalls=commands.filter(c=>c.url==='/api/actions/fixture_budget/resolve');assert.equal(budgetCalls.length,1);assert(!('budget' in JSON.parse(budgetCalls[0].body)),'unchecked budget sent automatically');
productCard=idMap['actions-list'].children.find(c=>query('button',c).some(b=>b.textContent==='Продолжить задачу'));
const enableBudget=query('input',productCard).find(i=>i.type==='checkbox');assert(enableBudget);enableBudget.checked=true;await enableBudget.dispatchEvent({type:'change'});
const budgetFields=query('input',productCard).filter(i=>i.type==='number');assert.equal(budgetFields.length,3);assert.deepEqual(budgetFields.map(i=>i.value),['1','3','120']);assert(budgetFields.every(i=>!i.disabled));budgetFields[0].value='2';budgetFields[1].value='7';budgetFields[2].value='3600';
await query('button',productCard).find(b=>b.textContent==='Продолжить задачу').click();await settle();budgetCalls=commands.filter(c=>c.url==='/api/actions/fixture_budget/resolve');assert.deepEqual(JSON.parse(budgetCalls.at(-1).body).budget,{max_iterations:2,max_agent_calls:7,max_run_duration:3600});
await query('button',productCard).find(b=>b.textContent==='Остановить задачу').click();await settle();budgetCalls=commands.filter(c=>c.url==='/api/actions/fixture_budget/resolve');assert(!('budget' in JSON.parse(budgetCalls.at(-1).body)),'stop changed budget');
assert(idMap['delete-worktree-button'].hidden,'unfinished run offers destructive worktree removal');
await query('[data-page="settings"]')[0].click();await settle();
let roleModel=query('input',idMap['role-defaults-list']).find(i=>i.id==='role-model-developer'),roleEffort=query('select',idMap['role-defaults-list']).find(i=>i.id==='role-effort-developer');assert(roleModel&&roleEffort,'role model controls absent');roleModel.value='fixture-model';await roleModel.dispatchEvent({type:'input'});roleEffort.value='high';await roleEffort.dispatchEvent({type:'change'});
await idMap['role-defaults-form'].dispatchEvent({type:'submit',preventDefault(){}});await settle();const roleCall=commands.filter(c=>c.url==='/api/settings'&&c.method==='POST').at(-1);assert.deepEqual(JSON.parse(roleCall.body),{role_model_defaults:{developer:{model:'fixture-model',reasoning_effort:'high'}}});roleEffort=query('select',idMap['role-defaults-list']).find(i=>i.id==='role-effort-developer');assert.equal(roleEffort.value,'high','persisted role effort lost');
// Unrelated Action Center updates must preserve an in-progress budget draft.
await query('[data-page="actions"]')[0].click();await settle();
productCard=idMap['actions-list'].children.find(c=>query('button',c).some(b=>b.textContent==='Продолжить задачу'));
const draftToggle=query('input',productCard).find(i=>i.type==='checkbox');draftToggle.checked=true;await draftToggle.dispatchEvent({type:'change'});
const draftField=query('input',productCard).find(i=>i.type==='number');draftField.value='17';
responses['/api/actions'].push({...action,id:'another_fixture_action',reason:'Другой запрос'});
await idMap['refresh-button'].click();await settle();
assert(idMap['actions-list'].children.includes(productCard),'unrelated action update replaced draft card');assert.equal(draftField.value,'17','unrelated action update erased draft');
// Search changes must rerender even when server registry is unchanged.
await query('[data-page="agents"]')[0].click();await settle();
idMap['agents-search'].value='не существующий агент';await idMap['agents-search'].dispatchEvent({type:'input'});await settle();assert(!query('button',idMap['agents-list']).some(b=>b.textContent==='Изменить'),'agent search failed to filter');
idMap['agents-search'].value='developer';await idMap['agents-search'].dispatchEvent({type:'input'});await settle();assert(idMap['agents-list'].children.length>0,'agent search failed to restore');
// Hold the response to reproduce repeated actions while a request is in flight.
let releaseRequest;let heldUrl;const originalFetch=sandbox.fetch;
sandbox.fetch=async(url,opts)=>{if(url===heldUrl&&opts.method==='POST')await new Promise(resolve=>releaseRequest=resolve);return originalFetch(url,opts);};
await query('[data-page="runs"]')[0].click();await settle();await query('button',idMap['runs-list'])[0].click();await settle();
heldUrl='/api/runs/'+run.id+'/control';const beforeControl=commands.filter(c=>c.url===heldUrl).length;
const controlOne=idMap['stop-button'].click();await settle();const controlTwo=idMap['stop-button'].click();await settle();assert(releaseRequest,'control did not start');releaseRequest();await Promise.all([controlOne,controlTwo]);await settle();assert.equal(commands.filter(c=>c.url===heldUrl).length,beforeControl+1,'duplicate control request');
responses['/api/agents'].push(...['coordinator','analyst','qa','reviewer'].map(name=>({...agent,name,permission:'read-only'})));await idMap['refresh-button'].click();await settle();
heldUrl='/api/runs';releaseRequest=null;idMap['workspace'].value='C:\\fixture';idMap['task'].value='Проверка повторной отправки';responses['/api/runs']=run;
const beforeCreate=commands.filter(c=>c.url===heldUrl&&c.method==='POST').length;
const createOne=idMap['run-form'].dispatchEvent({type:'submit',preventDefault(){}});await settle();const createTwo=idMap['run-form'].dispatchEvent({type:'submit',preventDefault(){}});await settle();assert(releaseRequest,'creation did not start');releaseRequest();await Promise.all([createOne,createTwo]);await settle();assert.equal(commands.filter(c=>c.url===heldUrl&&c.method==='POST').length,beforeCreate+1,'duplicate run creation');
sandbox.fetch=originalFetch;
// A delayed action refresh for A must never overwrite a later selection of B.
const secondRun={...run,id:'fixture_second_run',task:'Вторая выбранная задача',state:'PAUSED'};
responses['/api/runs/'+secondRun.id]=secondRun;
let releaseOldDetail=null,holdOldDetail=false;
sandbox.fetch=async(url,opts)=>{
 if(url.startsWith('/api/runs?'))return {ok:true,status:200,headers:{get:()=> 'application/json'},json:async()=>({items:[run,secondRun],total:2})};
 if(url==='/api/runs/'+run.id&&holdOldDetail){holdOldDetail=false;await new Promise(resolve=>releaseOldDetail=resolve);}
 return originalFetch(url,opts);
};
await idMap['refresh-button'].click();await settle();await query('button',idMap['runs-list'])[0].click();await settle();
await query('[data-page="actions"]')[0].click();await settle();
productCard=idMap['actions-list'].children.find(c=>query('button',c).some(b=>b.textContent==='Продолжить задачу'));
holdOldDetail=true;const resolvingOldAction=query('button',productCard).find(b=>b.textContent==='Остановить задачу').click();await settle();assert(releaseOldDetail,'action did not request old run detail');
await query('[data-page="runs"]')[0].click();await settle();await query('button',idMap['runs-list']).find(b=>query('.run-card-title',b).some(t=>t.textContent===secondRun.task)).click();await settle();assert.equal(idMap['detail-task-text'].textContent,secondRun.task);
releaseOldDetail();await resolvingOldAction;await settle();assert.equal(idMap['detail-task-text'].textContent,secondRun.task,'stale action response replaced current run');
sandbox.fetch=originalFetch;
idMap['runs-search'].value='Нет подходящей задачи';await idMap['runs-search'].dispatchEvent({type:'input'});assert.equal(query('button',idMap['runs-list']).length,0,'run search did not filter');
idMap['runs-search'].value='';await idMap['runs-search'].dispatchEvent({type:'input'});assert(query('button',idMap['runs-list']).length>0,'run search did not restore');
idMap['runs-state-filter'].value='active';await idMap['runs-state-filter'].dispatchEvent({type:'change'});assert.equal(query('button',idMap['runs-list']).length,0,'active filter included inactive runs');
idMap['runs-state-filter'].value='all';await idMap['runs-state-filter'].dispatchEvent({type:'change'});
responses['/api/agents'].push({name:'security',role:'security',instructions:'English fixture instructions',permission:'read-only',enabled:true});
await idMap['refresh-button'].click();await settle();
await query('[data-page="agents"]')[0].click();await settle();
idMap['agents-search'].value='безопасность';await idMap['agents-search'].dispatchEvent({type:'input'});await settle();
assert(query('h3',idMap['agents-list']).some(el=>el.textContent==='Безопасность'),'Russian specialist display/search failed');
assert(!query('p',idMap['agents-list']).some(el=>el.textContent==='English fixture instructions'),'technical instructions leaked into builtin description');
// Dedicated feature routes keep the legacy suite URL compatible.
const routeHashes=[];sandbox.history.replaceState=(_state,_title,hash)=>routeHashes.push(hash);
for(const [route,title]of [['architect','Архитектор задач'],['intelligence','Знания проекта'],['qa','Проверка качества'],['git','Машина времени Git'],['budget','Бюджет запусков']]){
 sandbox.window.CodexTeamSuite.setPage(route);assert.equal(routeHashes.at(-1),'#'+route);assert.equal(idMap['page-label'].textContent,title);assert.equal(idMap['page-suite'].hidden,false);
}
sandbox.window.CodexTeamSuite.setPage('suite/qa');assert.equal(routeHashes.at(-1),'#qa');
// Creating a project uses the new endpoint once and selects the returned path.
const createFetch=sandbox.fetch;let createRequests=0;
const createdProject={id:'created-project',name:'Новый проект',path:'C:\\Projects\\NewProject'};
sandbox.fetch=async(url,opts)=>{if(url==='/api/projects/create'){createRequests++;assert.deepEqual(JSON.parse(opts.body),{name:createdProject.name,path:createdProject.path});responses['/api/projects']=[createdProject];return {ok:true,status:200,headers:{get:()=> 'application/json'},json:async()=>createdProject};}return createFetch(url,opts);};
idMap['project-create-name'].value=createdProject.name;idMap['project-create-path'].value=createdProject.path;idMap['project-create-form'].reset=()=>{};
await Promise.all([idMap['project-create-form'].dispatchEvent({type:'submit',preventDefault(){}}),idMap['project-create-form'].dispatchEvent({type:'submit',preventDefault(){}})]);
assert.equal(createRequests,1);assert.equal(idMap.workspace.value,createdProject.path);assert.equal(sandbox.window.CodexTeamSuite.state.suiteProjectId,createdProject.id);assert.equal(idMap['project-create-button'].disabled,false);sandbox.fetch=createFetch;
sandbox.window.CodexTeamSuite.setPage('qa');idMap['suite-root'].getAttribute=key=>key==='aria-busy'?'true':null;sandbox.window.CodexTeamSuite.setPage('architect');assert.equal(sandbox.window.CodexTeamSuite.state.suiteFeature,'qa');assert.equal(idMap['page-label'].textContent,'Проверка качества');delete idMap['suite-root'].getAttribute;
let pickerCalls=0;sandbox.window.pywebview={api:{choose_project:async()=>{pickerCalls++;return {path:'C:'+String.fromCharCode(92)+'Projects'};}}};sandbox.window.CodexTeamSuite.state.desktopReady=true;idMap['project-create-name'].value='FreshProject';await idMap['project-create-browse'].click();assert.equal(idMap['project-create-path'].value,'C:'+String.fromCharCode(92)+'Projects'+String.fromCharCode(92)+'FreshProject');assert.equal(createRequests,1,'picker must not create or attach a repository');idMap['project-create-name'].value='CON';await idMap['project-create-browse'].click();assert.equal(pickerCalls,1,'invalid folder name reached native picker');
// Full access is opt-in: rejecting the dialog must not create a run.
idMap['run-access-level'].value='full-access';sandbox.window.confirm=()=>false;let countAccessCreates=commands.filter(c=>c.url==='/api/runs'&&c.method==='POST').length;
await idMap['run-form'].dispatchEvent({type:'submit',preventDefault(){}});assert.equal(commands.filter(c=>c.url==='/api/runs'&&c.method==='POST').length,countAccessCreates,'full access created without consent');
sandbox.window.confirm=()=>true;await idMap['run-form'].dispatchEvent({type:'submit',preventDefault(){}});const accessCreate=JSON.parse(commands.filter(c=>c.url==='/api/runs'&&c.method==='POST').at(-1).body);assert.equal(accessCreate.access_level,'full-access');assert.equal(accessCreate.confirmed_full_access,true);
const priorAccessFetch=sandbox.fetch;sandbox.fetch=async(url,opts)=>{if(url==='/api/runs/'+run.id+'/control'){const payload=JSON.parse(opts.body);if(payload.action==='set_access')run.access_level=payload.access_level;}return priorAccessFetch(url,opts);};run.state='PAUSED';await sandbox.window.CodexTeamSuite.selectRun(run.id,false);idMap['detail-access-select'].value='read-only';await idMap['detail-access-select'].dispatchEvent({type:'change'});await idMap['run-access-form'].dispatchEvent({type:'submit',preventDefault(){}});const accessControl=JSON.parse(commands.filter(c=>c.url==='/api/runs/'+run.id+'/control').at(-1).body);assert.deepEqual(accessControl,{action:'set_access',access_level:'read-only'});assert.equal(idMap['detail-access-level'].textContent,'Только чтение');assert.equal(run.state,'PAUSED','access apply unexpectedly resumed run');run.state='RUNNING';await sandbox.window.CodexTeamSuite.selectRun(run.id,false);assert.equal(idMap['run-access-form'].hidden,true);sandbox.fetch=priorAccessFetch;
// Failed navigation preserves the current run's draft and loaded inspector data.
const selectionState=sandbox.window.CodexTeamSuite.state;
selectionState.detailTab='tests';
selectionState.events=[{id:41,type:'fixture_event'}];selectionState.eventsLoaded=true;
selectionState.stageEvents=[{id:42,type:'agent_started',role:'developer'}];
selectionState.diffLines=['+keep loaded diff'];selectionState.eventCursor=41;selectionState.selectedRole='developer';
const preservedContext={events:selectionState.events,stageEvents:selectionState.stageEvents,diffLines:selectionState.diffLines};
idMap['steer-instruction'].value='Не потерять моё указание';
const selectedBeforeFailedOpen=selectionState.selectedRun.id;
await sandbox.window.CodexTeamSuite.selectRun('missing_run',false);
assert.equal(selectionState.selectedRun.id,selectedBeforeFailedOpen);
assert.equal(idMap['steer-instruction'].value,'Не потерять моё указание','failed selection discarded steering draft');
for(const [key,value]of Object.entries(preservedContext))assert.strictEqual(selectionState[key],value,`failed selection discarded ${key}`);
assert.equal(selectionState.eventsLoaded,true);assert.equal(selectionState.eventCursor,41);assert.equal(selectionState.selectedRole,'developer');assert.equal(selectionState.selecting,false);
// A slow older selection cannot clear a draft entered after a newer run opens.
const beforeSelectionFetch=sandbox.fetch;let releaseSlowSelection;
sandbox.fetch=async(url,opts)=>{if(url==='/api/runs/'+run.id)await new Promise(resolve=>releaseSlowSelection=resolve);return beforeSelectionFetch(url,opts);};
const slowSelection=sandbox.window.CodexTeamSuite.selectRun(run.id,false);await settle();assert(releaseSlowSelection);
await sandbox.window.CodexTeamSuite.selectRun(secondRun.id,false);
assert.equal(selectionState.selectedRun.id,secondRun.id);assert.equal(selectionState.selecting,false);
assert.equal(idMap['steer-instruction'].value,'','successful selection retained prior instruction');
assert.equal(selectionState.events.length,0);assert.equal(selectionState.stageEvents.length,0);assert.equal(selectionState.diffLines.length,0);assert.equal(selectionState.eventCursor,0);
idMap['steer-instruction'].value='Новое указание для второго запуска';
selectionState.events=[{id:73,type:'fixture_event'}];const newerEvents=selectionState.events;
releaseSlowSelection();await slowSelection;
assert.equal(selectionState.selectedRun.id,secondRun.id,'older selection replaced newer run');
assert.equal(idMap['steer-instruction'].value,'Новое указание для второго запуска','stale selection discarded newer steering draft');
assert.strictEqual(selectionState.events,newerEvents,'stale selection discarded newer events');assert.equal(selectionState.selecting,false);
sandbox.fetch=beforeSelectionFetch;
// Favorites are a server query, and deleting the final item on a page clamps pagination.
const originalHistoryFetch=sandbox.fetch,historyQueries=[];
sandbox.fetch=async(url,opts)=>{
  if(url.startsWith('/api/runs?')){
    const params=new URL(url,'http://localhost').searchParams;historyQueries.push(params);
    const offset=Number(params.get('offset'));
    return {ok:true,status:200,headers:{get:()=> 'application/json'},json:async()=>({items:offset?[]:[run],total:20})};
  }
  return originalHistoryFetch(url,opts);
};
idMap['history-favorites'].checked=true;
await idMap['history-favorites'].dispatchEvent({type:'change'});await settle();
assert.equal(historyQueries.at(-1).get('favorite'),'true','favorite checkbox did not filter the whole server history');
selectionState.historyTotal=21;
await idMap['history-next'].click();await settle();
assert.equal(selectionState.historyPage,0,'history did not return to last available page');
assert.deepEqual(historyQueries.slice(-2).map(params=>params.get('offset')),['20','0']);
assert.equal(selectionState.historyRows[0].id,run.id);
sandbox.fetch=originalHistoryFetch;
// Failed navigation must release the previous selection's in-flight readers.
// Their stale finally blocks cannot own the new version's busy indicators.
const beforeReaderFetch=sandbox.fetch;let releaseEventsRead;
sandbox.fetch=async(url,opts)=>{if(url.includes('/events'))await new Promise(resolve=>releaseEventsRead=resolve);return beforeReaderFetch(url,opts);};
selectionState.detailTab='overview';selectionState.eventsLoaded=false;selectionState.eventsRequest=null;
sandbox.window.CodexTeamSuite.setPage('runs');await settle();assert(releaseEventsRead,'activity request was not held');
assert.equal(idMap['more-events-button'].disabled,true);
await sandbox.window.CodexTeamSuite.selectRun('missing_run',false);
assert.equal(selectionState.eventsRequest,null,'failed selection stranded pending activity request');
assert.equal(idMap['more-events-button'].disabled,false,'failed selection stranded activity loading button');
releaseEventsRead();await settle();assert.equal(selectionState.eventsRequest,null,'stale activity response reclaimed a request');
sandbox.fetch=beforeReaderFetch;sandbox.window.CodexTeamSuite.setPage('runs');await settle();assert.equal(selectionState.eventsLoaded,true,'activity could not load after failed navigation');
let releaseDiffRead;
sandbox.fetch=async(url,opts)=>{if(url.includes('/diff'))await new Promise(resolve=>releaseDiffRead=resolve);return beforeReaderFetch(url,opts);};
selectionState.diffRun=null;selectionState.diffLines=['+preserved loaded diff'];selectionState.diffHasMore=true;
await idMap['open-diff-button'].click();await settle();assert(releaseDiffRead,'diff request was not held');
assert.equal(selectionState.diffLoading,true);assert.equal(idMap['more-diff-button'].disabled,true);
await sandbox.window.CodexTeamSuite.selectRun('missing_run',false);
assert.equal(selectionState.diffLoading,false,'failed selection stranded diff loading state');
assert.equal(idMap['more-diff-button'].disabled,false,'failed selection stranded diff loading button');
assert.deepEqual(selectionState.diffLines,['+preserved loaded diff']);
releaseDiffRead();await settle();assert.equal(selectionState.diffLoading,false);assert.deepEqual(selectionState.diffLines,['+preserved loaded diff'],'stale diff response replaced preserved content');
sandbox.fetch=beforeReaderFetch;await idMap['open-diff-button'].click();await settle();assert.equal(selectionState.diffLoading,false);assert.deepEqual(selectionState.diffLines,['+safe line'],'diff could not reload after failed navigation');
console.log(JSON.stringify({result:'PASS',ids:Object.keys(idMap).length,fetches:commands.filter(c=>c.url).length,evidence:['startup no POST','provider test explicit only','unsupported grants hidden','USER_DECISION_REQUIRED amber','full task available','diff lazy fetch','unique DOM IDs','API key missing actionable','no automatic provider select','budget save preserves provider','key cleared and absent localStorage','key save does not test API','budget opt in only','resume exact total budget','stop excludes budget','unfinished worktree removal hidden','canonical role model defaults','role effort retained after save','agent search reacts to input','duplicate control suppressed','duplicate creation suppressed','unrelated action preserves draft','stale action response preserves selected run','failed selection preserves current context','latest successful selection owns draft and events','favorites server filter and page clamp']}));})().catch(e=>{console.error(e);process.exitCode=1;});
