'use strict';
const fs = require('fs'), path = require('path'), vm = require('vm'), assert = require('assert');
const context = {setTimeout, clearTimeout}; context.globalThis = context;
vm.runInNewContext(fs.readFileSync(path.resolve(process.argv[2] || 'codex_team/static', 'task-draft.js'), 'utf8'), context);
const factory = context.CodexTaskDraft.createController;
const tick = () => new Promise(resolve => setImmediate(resolve));
const deferred = () => {let resolve, reject; const promise = new Promise((a,b) => {resolve=a;reject=b;});return {resolve,reject,promise};};
function setup({data={task:'',workspace:'/repo',mode:'standard'}, response={revision:0,draft:null}, handler}={}) {
  let live={...data}, states=[], calls=[], timers=[], applied=[];
  const api = async (url, method='GET', body) => {calls.push({url,method,body});return handler ? handler(url,method,body) : method==='GET' ? response : {revision:calls.length,draft:method==='PUT'?{data:body.data}:null};};
  const draft = factory({api,read:()=>live,apply:value=>{live={...value};applied.push(value);},onState:value=>states.push(value),schedule:fn=>{timers.push(fn);return fn;},unschedule:fn=>{timers=timers.filter(value=>value!==fn);}});
  return {draft, calls, states, applied, input:value=>{live={...live,...value};draft.changed();}, data:()=>live,
    fire:async()=>{const pending=timers;timers=[];pending.forEach(fn=>fn());await tick();},last:()=>states.at(-1)};
}
(async()=>{
  {
    const s=setup();assert.equal(s.draft.canReplace,false,'unloaded draft cannot be replaced');await s.draft.load();assert.equal(s.draft.canReplace,true);assert.equal(s.calls.length,1);assert.equal(s.last().status,'empty');
    s.input({workspace:'/another'});await s.fire();assert.equal(s.calls.length,1,'empty initial task never mutates backend');
    s.input({task:'literal <script> user text',access_level:'full-access',confirmed_full_access:true,provider:'secret',api_key:'NO'});await s.fire();
    const data=s.calls.at(-1).body.data;assert.equal(data.task,'literal <script> user text');for(const key of ['access_level','confirmed_full_access','provider','api_key'])assert(!(key in data));
    assert.equal(s.last().status,'saved');const count=s.calls.length;s.input({task:data.task});await s.fire();assert.equal(s.calls.length,count,'identical snapshots deduplicated');
    s.input({task:''});await s.fire();assert.equal(s.calls.at(-1).method,'DELETE');assert.deepEqual(s.calls.at(-1).body,{});
  }
  {
    const late=deferred();const saved={revision:3,draft:{revision:3,data:{task:'saved remote',workspace:'/old'}}};
    const s=setup({handler:()=>late.promise});const loading=s.draft.load();assert.equal(s.draft.canReplace,false,'pending draft cannot be replaced');s.input({task:'typing during GET'});late.resolve(saved);await loading;
    assert.equal(s.data().task,'typing during GET');assert.equal(s.applied.length,0);assert.equal(s.last().status,'conflict');assert.equal(s.draft.canReplace,false,'remote conflict must be resolved before replay');
    await s.draft.restore();assert.equal(s.draft.canReplace,true);assert.equal(s.data().task,'saved remote');assert.equal(s.calls.length,1,'restoration does not autosave');
    const next=s.draft.checkpoint();s.input({task:'newer than submitted'});assert.equal(await s.draft.consume(next),false);assert.equal(s.calls.length,1,'run success cannot clear newer editing');
  }
  {
    let online=false,rev=7;
    const s=setup({handler:async(url,method,body)=>{if(!online)throw new Error('offline');return method==='GET'?{revision:rev,draft:null}:{revision:++rev,draft:{data:body?.data}};}});
    await s.draft.load();assert.equal(s.last().status,'offline');s.input({task:'offline remains'});await s.fire();assert.equal(s.calls.length,1);
    online=true;await s.draft.retry();await s.fire();assert.equal(s.last().status,'saved');assert.equal(s.calls.at(-1).body.expected_revision,7);assert.equal(s.data().task,'offline remains');
  }
  {
    let put=deferred(),count=0,rev=0;
    const s=setup({handler:async(url,method)=>{if(method==='GET')return{revision:0,draft:null};count++;if(count===1)return put.promise;return{revision:++rev};}});
    await s.draft.load();s.input({task:'first'});const saving=s.draft.flush();s.input({task:'second'});const repeated=s.draft.flush();assert.equal(count,1,'no concurrent PUTs');
    rev=1;put.resolve({revision:1});await saving;await repeated;await s.fire();assert.equal(count,2);assert.equal(s.calls.at(-1).body.data.task,'second');assert.equal(s.calls.at(-1).body.expected_revision,1);
  }
  {
    let conflict=true;
    const s=setup({handler:async(url,method)=>{if(method==='GET')return{revision:conflict?0:9,draft:conflict?null:{data:{task:'other window'}}};if(conflict){const error=new Error('conflict');error.status=409;throw error;}return{revision:10};}});
    await s.draft.load();s.input({task:'my unchanged local draft'});await s.draft.flush();assert.equal(s.last().status,'conflict');assert.equal(s.data().task,'my unchanged local draft');
    conflict=false;await s.draft.retry();assert.equal(s.last().remote.data.task,'other window');assert.equal(s.applied.length,0);await s.draft.keepCurrent();assert.equal(s.calls.at(-1).body.expected_revision,9);assert.equal(s.last().status,'saved');
  }
  {
    const s=setup({response:{revision:8,draft:{data:{task:'unrestored remote'}}}});await s.draft.load();const submitted=s.draft.checkpoint();
    assert.equal(await s.draft.consume(submitted),false);assert.equal(s.calls.length,1,'a successful unrelated task cannot erase the remote draft');
  }
  {
    let del=deferred();const s=setup({data:{task:'submitted'},handler:async(url,method)=>method==='GET'?{revision:0,draft:null}:method==='DELETE'?del.promise:{revision:2}});
    await s.draft.load();const consumed=s.draft.consume(s.draft.checkpoint());s.input({task:'typed while deleting'});del.resolve({revision:1});await consumed;await s.fire();
    assert.equal(s.calls.at(-1).method,'PUT');assert.equal(s.calls.at(-1).body.data.task,'typed while deleting');assert.equal(s.calls.at(-1).body.expected_revision,1);
  }
  {
    const s=setup();await s.draft.load();s.input({task:'task',max_iterations:NaN});await s.fire();assert.equal(s.last().status,'invalid');assert.equal(s.calls.length,1);
    s.input({max_iterations:3});await s.fire();assert.equal(s.last().status,'saved');
  }
  {
    const s=setup();await s.draft.load();s.input({task:'not submitted'});const c=s.draft.checkpoint();await s.draft.consume(c);assert.equal(s.calls.at(-1).method,'DELETE');
    s.input({task:'not submitted'});await s.fire();assert.equal(s.calls.at(-1).method,'PUT','a new edit after consumed draft saves even when text matches previous task');
  }
  {
    const pending=deferred();const s=setup({handler:async(url,method)=>method==='GET'?{revision:0,draft:null}:pending.promise});
    await s.draft.load();s.input({task:'submitted before save'});const saving=s.draft.flush();const clear=s.draft.consume(s.draft.checkpoint());
    s.input({task:'a genuinely new task'});pending.resolve({revision:1});await saving;assert.equal(await clear,false);assert.equal(s.calls.filter(call=>call.method==='DELETE').length,0,'new edits while awaiting an earlier save prevent deletion');
    s.draft.destroy();
  }
  console.log('PASS: durable draft recovery, CAS conflicts, offline edits, late responses, request serialization, privacy allowlist and run-success clearing.');
})().catch(error=>{console.error(error);process.exit(1);});
