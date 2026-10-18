const assert=require('assert'),fs=require('fs'),vm=require('vm'),path=require('path');
const context={setTimeout,clearTimeout};vm.runInNewContext(fs.readFileSync(path.join(process.argv[2],'refresh-loop.js'),'utf8'),context);
(async()=>{
 let pending=[],shown=true,calls=0,resolve;const seen=[];
 const loop=context.CodexRefreshLoop.create({visible:()=>shown,run:async()=>{calls++;return false;},schedule:(fn,ms)=>{const job={fn,ms};pending.push(job);return job;},cancel:job=>pending=pending.filter(j=>j!==job),onChange:s=>seen.push(s)});
 const tick=async()=>{const job=pending.shift();assert(job);await job.fn();};
 loop.start();assert.equal(pending[0].ms,2000);await tick();assert.equal(pending[0].ms,4000);
 await tick();assert.equal(pending[0].ms,8000);await tick();await tick();await tick();assert.equal(pending[0].ms,30000);
 shown=false;loop.visibilityChanged();assert.equal(pending.length,0);shown=true;loop.visibilityChanged();assert.equal(pending[0].ms,0);
 loop.stop();assert.equal(pending.length,0);
 const held=context.CodexRefreshLoop.create({run:()=>new Promise(r=>resolve=r),schedule:(fn,ms)=>{const job={fn,ms};pending.push(job);return job;},cancel:job=>pending=pending.filter(j=>j!==job)});
 held.start();const work=pending.shift().fn();held.wake();held.wake();assert.equal(pending.length,0);resolve(true);await work;assert.equal(pending.length,1);assert.equal(pending[0].ms,0);
 const next=pending.shift().fn();held.stop();resolve(false);await next;assert.equal(pending.length,0);
 console.log('PASS: bounded backoff, visibility, deduplicated wake and late completion after stop');
})().catch(e=>{console.error(e);process.exit(1);});
