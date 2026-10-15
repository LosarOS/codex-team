/* Synthetic persisted data only; no provider/model calls. */
const assert=require('node:assert/strict'),path=require('node:path');
const {attempts,category}=require(path.join(process.argv[2],'mission-control.js'));
const modes={quick:['coordinator','developer','qa'],standard:['coordinator','analyst','developer','qa','reviewer'],deep:['coordinator','analyst','developer','qa','reviewer','final-audit'],audit:['coordinator','analyst','reviewer','qa','final-audit'],plan:['coordinator','analyst','architect'],implement:['coordinator','developer','qa','reviewer']};
for(const [mode,pipeline] of Object.entries(modes)){
 const rows=attempts({mode,pipeline,state:'QUEUED',stage:0,current_role:null,calls:0});
 assert.deepEqual(rows.map(r=>r.role),pipeline);assert.equal(rows[0].state,'WAITING');assert(rows.slice(1).every(r=>r.state==='WAITING'));assert(rows.every(r=>r.started===undefined&&r.ended===undefined));
}
const start=(id,role,created_at)=>({id,type:'agent_started',role,created_at,payload:{iteration:1,call:id}});
const end=(id,role,created_at,verdict)=>({id,type:'agent_completed',role,created_at,payload:{verdict,summary:'Фактический результат'}});
const events=[start(1,'developer','2026-10-15T10:00:00Z'),end(2,'developer','2026-10-15T10:01:00Z','CHANGES_REQUIRED'),start(3,'qa','2026-10-15T10:02:00Z'),end(4,'qa','2026-10-15T10:03:00Z','FAIL'),start(5,'developer','2026-10-15T10:04:00Z')];
const run={pipeline:['developer','qa','reviewer'],state:'RUNNING',current_role:'developer',stage:0,result_history:[{role:'developer',result:{verdict:'CHANGES_REQUIRED',summary:'Первый результат'}},{role:'qa',result:{verdict:'FAIL'}}]};
let rows=attempts(run,events);
assert.deepEqual(rows.map(r=>[r.role,r.number,r.state]),[['developer',1,'CHANGES_REQUIRED'],['qa',1,'FAIL'],['developer',2,'RUNNING'],['qa',0,'WAITING'],['reviewer',0,'WAITING']]);assert.equal(rows[0].result.summary,'Первый результат');assert.equal(rows[0].ended,events[1].created_at);assert.equal(rows[2].started,events[4].created_at);
for(const state of ['PAUSED','USER_DECISION_REQUIRED','FAILED','AUTH_REQUIRED','USAGE_LIMIT','STOPPED']){rows=attempts({...run,state,error:'Причина остановки'},events);assert.equal(rows[2].state,state);assert.equal(rows[2].error,'Причина остановки');}
rows=attempts({...run,state:'DONE',current_role:null},[]);assert.equal(rows[0].state,'CHANGES_REQUIRED');assert.equal(rows[0].started,undefined);
rows=attempts({state:'DONE',pipeline:['qa'],results:{qa:{verdict:'PASS'}}});assert.equal(rows[0].state,'PASS');assert.equal(rows[0].started,undefined);
rows=attempts({...run,result_history:[]},[start(1,'developer',undefined)]);assert.equal(rows[0].state,'RUNNING','missing timestamp must not imply interrupted execution');
rows=attempts({...run,result_history:[]},[start(1,'developer','2026-10-15T10:00:00Z'),end(2,'developer',undefined,'PASS')]);assert.equal(rows[0].state,'PASS','missing completion timestamp must not erase completed result');
rows=attempts({pipeline:['developer'],state:'RUNNING',current_role:'developer',stage:0,calls:1},[start(1,'developer','2026-10-15T10:00:00Z'),end(2,'developer','2026-10-15T10:01:00Z','PASS')]);assert.equal(rows.length,1,'completed call must not invent another running attempt');
rows=attempts({pipeline:['developer','qa','reviewer','qa'],stage:1,calls:1,state:'RUNNING',current_role:'qa'},[start(1,'developer','2026-10-15T10:00:00Z'),end(2,'developer','2026-10-15T10:01:00Z','PASS')]);assert.equal(rows.filter(r=>r.role==='qa'&&r.state==='WAITING').length,2,'planned QA recheck must remain visible');
const finished={state:'DONE',stage:2,calls:2,pipeline:['developer','qa'],result_history:[{role:'developer',result:{verdict:'IMPLEMENTED'}},{role:'qa',result:{verdict:'PASS'}}]};
rows=attempts(finished,[start(1,'developer','2026-10-15T10:00:00Z')],false);
assert.deepEqual(rows.map(r=>r.state),['IMPLEMENTED','PASS'],'partial event pages must preserve all persisted results');
assert(rows.every(r=>r.historyOnly&&!r.started),'partial timing must remain unknown');
rows=attempts({...finished,state:'RUNNING',calls:3,current_role:'developer',stage:0},[start(1,'developer','2026-10-15T10:00:00Z')],false);
assert.equal(rows.filter(r=>r.state==='RUNNING').length,1);assert.equal(rows.find(r=>r.state==='RUNNING').started,undefined,'old first-page start must not become current retry');
rows=attempts({...finished,state:'AUTH_REQUIRED',calls:3,current_role:'developer',stage:0,error:'Нужен вход'},[],false);assert.equal(rows.find(r=>r.call===3).state,'AUTH_REQUIRED');assert.equal(rows.find(r=>r.call===3).error,'Нужен вход');
for(const e of [{type:'agent_failed'},{type:'sdk',payload:{item:{type:'command_execution',exitCode:2}}},{type:'sdk',payload:{item:{type:'command_execution',exit_code:2}}},{type:'agent_completed',payload:{verdict:'CHANGES_REQUIRED'}}])assert.equal(category(e),'errors');
for(const type of ['instruction_queued','steering','approval_requested','action_required','pause_requested','stop_requested'])assert.equal(category({type}),'decisions');
for(const e of [{type:'command_started'},{type:'sdk',payload:{item:{type:'command_execution',command:'git status',exitCode:0}}}])assert.equal(category(e),'commands');
assert.equal(category({type:'agent_started',role:'qa'}),'agents');assert.equal(category({type:'run_state'}),'all');
console.log(JSON.stringify({result:'PASS',evidence:['six mode pipelines','retry history retained','actual timestamps only','terminal states','missing timestamp resilience','activity filters']}));
