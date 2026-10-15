const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const context={AbortController,setTimeout,clearTimeout,TypeError,fetch:async()=>({ok:true,status:200,headers:{get:()=> 'application/json'},json:async()=>({ok:true})})};context.window=context;vm.createContext(context);vm.runInContext(fs.readFileSync(process.argv[2]+'/api-client.js','utf8'),context);
(async()=>{const api=context.CodexApi.request;
assert.equal((await api('/api/status')).ok,true);
for(const path of ['https://evil.test','//evil.test','/\\evil.test','/api/\nstatus'])await assert.rejects(api(path),e=>e.kind==='validation');
context.fetch=async()=>({ok:false,status:403,headers:{get:()=> 'application/json'},json:async()=>({detail:'denied'})});await assert.rejects(api('/api/status'),e=>e.status===403);
context.fetch=async()=>({ok:true,status:200,headers:{get:()=> 'application/json'},json:async()=>{throw Error('bad')}});await assert.rejects(api('/api/status'),e=>e.kind==='protocol');
context.fetch=async()=>({ok:true,status:200,headers:{get:()=> 'text/html'},text:async()=> '<html>wrong server</html>'});await assert.rejects(api('/api/status'),e=>e.kind==='protocol');
context.fetch=async()=>{throw new TypeError('network')};await assert.rejects(api('/api/status'),e=>e.kind==='offline');
context.fetch=async(path,init)=>new Promise((resolve,reject)=>{const abort=()=>{const e=new Error('abort');e.name='AbortError';reject(e)};if(init.signal.aborted)abort();else init.signal.addEventListener('abort',abort,{once:true})});
await assert.rejects(api('/api/status','GET',undefined,{timeoutMs:5}),e=>e.kind==='timeout');const controller=new AbortController();controller.abort();await assert.rejects(api('/api/status','GET',undefined,{signal:controller.signal}),e=>e.kind==='cancelled');
const format=context.CodexApi.formatError;
for(const [type,ctx,expected]of [['missing',{},'Заполните'],['string_too_short',{min_length:3},'не менее 3'],['int_parsing',{},'число'],['literal_error',{},'доступного списка'],['extra_forbidden',{},'не поддерживается']]){
 const result=format({detail:[{loc:['body','task'],type,ctx,msg:'English validation message',input:'SECRET-FIXTURE'}]});assert(result.includes('Задача:'));assert(result.includes(expected));assert(!result.includes('English'));assert(!result.includes('SECRET-FIXTURE'));
}
assert(!format({detail:'arbitrary English stack message'}).includes('English'));
context.fetch=async()=>({ok:false,status:422,headers:{get:()=> 'application/json'},json:async()=>({detail:[{loc:['body','key'],type:'string_type',msg:'Input should be a valid string',input:'SECRET-FIXTURE'}]})});
await assert.rejects(api('/api/settings'),e=>e.message.includes('Ключ API: Введите текст.')&&!JSON.stringify(e.technical).includes('SECRET-FIXTURE'));
context.fetch=async()=>({ok:false,status:422,headers:{get:()=> 'application/json'},json:async()=>({detail:'Проверьте поля ввода.',validation_errors:[{loc:['body','task'],type:'string_too_short',ctx:{min_length:3},msg:'String should have at least 3 characters'}]})});
await assert.rejects(api('/api/settings'),e=>e.message.includes('Задача: Введите не менее 3 символов.'));
context.fetch=async()=>({ok:false,status:403,headers:{get:()=> 'application/json'},json:async()=>({detail:'Forbidden'})});
await assert.rejects(api('/api/settings'),e=>e.message.includes('Доступ к действию запрещён'));
console.log(JSON.stringify({result:'PASS'}));})().catch(e=>{console.error(e);process.exitCode=1});
