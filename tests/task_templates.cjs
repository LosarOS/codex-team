'use strict';
const fs = require('fs'), path = require('path'), vm = require('vm'), assert = require('assert');
const context = {}; context.globalThis = context;
vm.runInNewContext(fs.readFileSync(path.resolve(process.argv[2] || 'codex_team/static', 'task-templates.js'), 'utf8'), context);
const factory = context.CodexTaskTemplates.createController;
const deferred = () => { let resolve, reject; const promise = new Promise((a,b) => { resolve=a; reject=b; }); return {promise, resolve, reject}; };
const sample = (id='one', revision=1) => ({id, revision, name:'A template <script>', description:'literal user text', data:{task:'review code',workspace:'/repo',mode:'standard',pack:'default',specialists:['reviewer'],max_iterations:3,max_agent_calls:10,max_run_duration:300},created_at:'2026-10-18',updated_at:'2026-10-18'});
function setup(handler) {
  let current = {...sample().data, task:'current composer', access_level:'full-access',confirmed_full_access:true,api_key:'secret',provider:'secret',auto_commit:true,isolation:'unsafe'}, calls=[], states=[];
  const api = async (url, method='GET', body) => { calls.push({url,method,body}); return handler ? handler(url,method,body) : method === 'GET' ? url.includes('?') ? {items:[sample()],total:1} : sample() : method === 'DELETE' ? {} : {...sample('one',2),name:body.name,description:body.description,data:body.data}; };
  const controller = factory({api,read:()=>current,onState:value=>states.push(value),limit:2});
  return {controller,calls,states,edit:patch=>{current={...current,...patch};},get current(){return current;},last:()=>states.at(-1)};
}
(async()=>{
  {
    const s=setup(); await s.controller.open(); assert.equal(s.calls.length,1); assert.equal(s.last().total,1); assert.equal(s.last().selected,null,'listing never applies or selects content');
    await s.controller.select('one'); assert.equal(s.last().selected.data.task,'review code'); assert.equal(s.current.task,'current composer','viewing template never overwrites composer');
    await s.controller.update({name:'Renamed',description:'Updated'}); const metadata=s.calls.find(call=>call.method==='PUT'); assert.equal(metadata.body.expected_revision,1); assert.equal(metadata.body.data.task,'review code','metadata update keeps saved content');
    s.edit({task:'new snapshot'}); await s.controller.update({name:'Renamed',description:'Updated',replaceData:true}); const snapshot=s.calls.filter(call=>call.method==='PUT').at(-1); assert.equal(snapshot.body.expected_revision,2); assert.equal(snapshot.body.data.task,'new snapshot');
    for (const key of ['access_level','confirmed_full_access','api_key','provider','auto_commit','isolation']) assert(!(key in snapshot.body.data),`template excludes ${key}`);
    await s.controller.remove(); assert.equal(s.calls.find(call=>call.method==='DELETE').url,'/api/task-templates/one?expected_revision=2'); assert.equal(s.last().selected,null); assert.equal(s.current.task,'new snapshot','deleting template preserves composer');
  }
  {
    const s=setup(); await s.controller.open(); s.controller.newTemplate(); await s.controller.create({name:'New',description:''});
    const post=s.calls.find(call=>call.method==='POST'); assert.equal(post.url,'/api/task-templates'); assert.equal(post.body.data.task,'current composer'); assert(!('expected_revision' in post.body));
    assert.equal(Object.keys(post.body.data).sort().join(','),'max_agent_calls,max_iterations,max_run_duration,mode,pack,specialists,task,workspace');
    post.body.data.specialists.push('planner'); assert.equal(s.current.specialists.length,1,'allowlisted arrays are copied');
  }
  {
    const stale=deferred(), latest=deferred(); let n=0;
    const s=setup(()=>++n===1?stale.promise:latest.promise); const open=s.controller.open(); const search=s.controller.list({query:'new & exact',offset:2});
    latest.resolve({items:[sample('latest')],total:4}); await search; stale.resolve({items:[sample('stale')],total:1}); await open;
    assert.equal(s.last().items[0].id,'latest','late list cannot overwrite latest search'); assert.equal(s.last().offset,2); assert(s.calls.at(-1).url.includes('query=new%20%26%20exact'));
  }
  {
    const stale=deferred(); const s=setup(()=>stale.promise); const pending=s.controller.open(); s.controller.close(); stale.resolve({items:[sample()],total:1}); await pending;
    assert.equal(s.controller.state.items.length,0,'closed dialog ignores late list');
  }
  {
    const a=deferred(),b=deferred(); const s=setup(url=>url.includes('?')?{items:[sample('a'),sample('b')],total:2}:url.endsWith('/a')?a.promise:b.promise);
    await s.controller.open(); const first=s.controller.select('a'),second=s.controller.select('b'); b.resolve(sample('b')); await second; a.resolve(sample('a')); await first;
    assert.equal(s.last().selected.id,'b','late details cannot replace newer selection');
  }
  {
    let fail=true; const s=setup((url,method)=>{ if(method==='GET')return url.includes('?')?{items:[sample()],total:1}:sample(); if(fail){const error=new Error('changed');error.status=409;throw error;} return sample('one',7); });
    await s.controller.open(); await s.controller.select('one'); assert.equal(await s.controller.update({name:'My metadata',description:''}),false); assert.equal(s.last().error,'conflict'); assert.equal(s.last().selected.revision,1); assert.equal(s.current.task,'current composer');
    fail=false; await s.controller.select('one'); await s.controller.update({name:'My metadata',description:''}); assert.equal(s.last().selected.revision,7);
  }
  {
    for (const {status, technical, expected} of [
      {status:409,technical:{code:'template_limit'},expected:'limit'},
      {status:409,technical:{detail:{code:'template_limit'}},expected:'limit'},
      {status:409,technical:{code:'revision_conflict'},expected:'conflict'},
      {status:401,technical:null,expected:'access'},
      {status:403,technical:null,expected:'access'},
    ]) {
      const s=setup((url,method)=>{if(method==='GET')return {items:[sample()],total:1};const error=new Error('backend details');Object.assign(error,{status,technical});throw error;});
      await s.controller.open(); const before=JSON.stringify(s.current); await s.controller.create({name:'Keep my title',description:'Keep my description'});
      assert.equal(s.last().error,expected); assert.equal(s.last().busy,false); assert.equal(JSON.stringify(s.current),before,'capacity and access errors preserve the composer'); assert.equal(s.last().items[0].name,sample().name,'failed creates preserve existing templates');
      assert.equal(s.calls.at(-1).body.name,'Keep my title'); assert.equal(s.calls.at(-1).body.description,'Keep my description');
    }
  }
  {
    const put=deferred(); const s=setup((url,method)=>method==='GET'?url.includes('?')?{items:[sample()],total:1}:sample():put.promise);
    await s.controller.open(); await s.controller.select('one'); const saving=s.controller.update({name:'Once',description:''}); assert.equal(s.last().busy,true);
    assert.equal(await s.controller.update({name:'Twice',description:''}),false); assert.equal(await s.controller.remove(),false); assert.equal(await s.controller.select('another'),false);
    assert.equal(s.calls.filter(call=>call.method==='PUT').length,1,'mutations cannot overlap'); put.resolve(sample('one',2)); await saving; assert.equal(s.last().busy,false);
  }
  {
    const s=setup(()=>{throw new Error('offline');}); await s.controller.open(); assert.equal(s.last().error,'offline'); assert.equal(s.current.task,'current composer');
  }
  {
    const late=deferred(); const s=setup((url,method)=>method==='GET'?url.includes('?')?{items:[sample()],total:1}:sample():late.promise);
    await s.controller.open(); await s.controller.select('one'); const save=s.controller.update({name:'Later',description:''}); const before=s.states.length; s.controller.destroy(); late.resolve(sample('one',2)); await save; assert.equal(s.states.length,before,'destroyed controller never emits late mutation');
  }
  console.log('PASS: template pagination, metadata versus snapshots, privacy allowlist, CAS conflicts, request guards, offline input preservation and late response safety.');
})().catch(error=>{console.error(error);process.exit(1);});
