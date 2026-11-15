/* Deferred real transport projection; no SDK/provider calls. */
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const root=process.argv[2];const ctx={AbortController,setTimeout,clearTimeout,URL,TypeError,fetch:()=>{throw Error('unexpected fetch')}};ctx.window=ctx;vm.createContext(ctx);vm.runInContext(fs.readFileSync(path.join(root,'api-client.js'),'utf8'),ctx);
const defer=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b});return {promise,resolve,reject}};
(async()=>{
 const changes=[],readiness=ctx.CodexApi.createReadiness({onChange:s=>changes.push(s)});
 assert.equal(readiness.snapshot().phase,'checking');assert.equal(changes.length,0);
 const a=defer(),b=defer(),first=readiness.probe(()=>a.promise),second=readiness.probe(()=>b.promise);
 b.reject(Error('actual latest health failed'));await second;a.resolve({status:'ok'});assert.equal((await first).accepted,false);assert.equal(readiness.snapshot().phase,'offline');assert.equal(changes.length,1);
 const c=defer(),d=defer(),third=readiness.probe(()=>c.promise),fourth=readiness.probe(()=>d.promise);
 d.resolve({status:'ok',checks:{backend:true}});await fourth;c.reject(Error('old failure'));assert.equal((await third).accepted,false);assert.equal(readiness.snapshot().online,true);assert.equal(changes.length,2);
 await readiness.probe(async()=>({status:'ok',checks:{backend:false}}));assert.equal(readiness.snapshot().online,false);
 await readiness.probe(async()=>({status:'not-ready'}));assert.equal(readiness.snapshot().online,false);
 console.log(JSON.stringify({result:'PASS',evidence:['initial checking','latest offline wins','latest online wins','explicit backend failure','invalid health readiness']}));
})().catch(e=>{console.error(e);process.exitCode=1});
