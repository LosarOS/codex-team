'use strict';
const assert=require('node:assert/strict');const path=require('node:path');
const {valid}=require(path.resolve(process.argv[2]||path.join(__dirname,'../codex_team/static'),'mission-queue.js'));
const entry={id:'mission-fixture',task:'ТЕСТОВЫЕ ДАННЫЕ: <script>literal</script>',workspace:'C:\\Проект',position:0,status:'pending',access_level:'standard',isolated:true,max_agent_calls:15,max_run_duration:1800,max_total_tokens:null};
const data={items:[entry],summary:{state:'paused',pending:1,total_pending_call_limit:15}};assert(valid(data));
for(const status of ['pending','running','done','blocked','skipped'])assert(valid({...data,items:[{...entry,status}]}));
for(const patch of [{status:'SUCCESS'},{position:-1},{task:'x'.repeat(401)},{isolated:false},{access_level:'unsafe'},{max_agent_calls:101},{max_run_duration:0},{max_total_tokens:-1}])assert(!valid({...data,items:[{...entry,...patch}]}));
for(const value of [null,{},[],{...data,items:[null]},{...data,items:Array(121).fill(entry)},{...data,summary:{state:'passed',pending:0,total_pending_call_limit:0}}])assert(!valid(value));
console.log('PASS mission queue: strict bounded factual UI schema, states, access and budget fields.');
