'use strict';
const assert=require('assert/strict'),fs=require('fs'),path=require('path');
const sourceRoot=process.argv.find(arg=>!arg.startsWith('-')&&arg.endsWith('/static'))||path.join(__dirname,'../codex_team/static');
const {createController,cleanData,fingerprint}=require(path.resolve(sourceRoot,'run-replay.js'));
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};};
const draft=(task='Saved full task')=>({task,workspace:'D:\\Проект',mode:'standard',pack:'software-development',specialists:['qa'],max_iterations:3,max_agent_calls:15,max_run_duration:1800});
const result=(id='r1',data=draft())=>({run_id:id,data,warnings:['security_reset']});
async function pureTests(){
  assert.deepEqual(cleanData(draft()),draft());
  for(const data of [null,[],{}, {...draft(),task:' '},{...draft(),task:'x'.repeat(30001)},{...draft(),workspace:'x'.repeat(4097)},{...draft(),mode:'unknown'},{...draft(),pack:1},{...draft(),specialists:['x'.repeat(101)]},{...draft(),specialists:Array(51).fill('qa')},{...draft(),max_iterations:0},{...draft(),max_agent_calls:'15'},{...draft(),max_run_duration:86401},{...draft(),access_level:'full-access'}])assert.equal(cleanData(data),null);
  assert(cleanData(draft('😀'.repeat(30000)))); assert.equal(fingerprint({b:2,a:1}),fingerprint({a:1,b:2}));
  let form=draft('Current unsaved task'),selected='r1',ready=true,accepted=true, confirmHold=null, apiFailure=null, apiHold=null;
  const calls=[],applied=[],notices=[],confirmations=[],states=[];
  const c=createController({api:async(...args)=>{calls.push(args);if(apiHold)return apiHold.promise;if(apiFailure)throw apiFailure;return result(selected);},read:()=>form,apply:data=>applied.push(data),getSelectedRun:()=>selected,canApply:()=>ready,notify:(...args)=>notices.push(args),onState:value=>states.push(value),confirm:async(...args)=>{confirmations.push(args);return confirmHold?confirmHold.promise:accepted;}});
  assert.equal(await c.replay(),true); assert.equal(calls[0][0],'/api/runs/r1/replay'); assert.equal(calls[0].length,1,'GET-only, no mutation or task execution');assert.deepEqual(applied[0],draft());assert.match(confirmations[0][1],/заменят текущую форму/);assert.match(confirmations[0][1],/Разрешения не копируются/);assert.equal(notices.at(-1)[1],false);
  accepted=false;assert.equal(await c.replay(),false);assert.equal(applied.length,1);accepted=true;
  apiHold=deferred();const pending=c.replay();assert.equal(c.busy,true);assert.equal(await c.replay(),false);assert.equal(calls.length,3,'repeated click is serialized');apiHold.resolve(result());await pending;apiHold=null;
  for(const failure of [{status:0},{status:403},{status:404},new Error('private diagnostic')]){apiFailure=failure;const before=applied.length;assert.equal(await c.replay(),false);assert.equal(applied.length,before);assert(!notices.at(-1)[0].includes('private diagnostic'));}apiFailure=null;
  apiHold=deferred();const malformed=c.replay();apiHold.resolve({...result(),data:{...draft(),auto_commit:true}});await malformed;apiHold=null;assert.match(notices.at(-1)[0],/Не удалось подготовить/);
  apiHold=deferred();const stale=c.replay();selected='r2';apiHold.resolve(result('r1'));assert.equal(await stale,false);assert.match(notices.at(-1)[0],/выбранный запуск изменились/);apiHold=null;selected='r1';
  apiHold=deferred();const edited=c.replay();form={...form,task:'New user text'};apiHold.resolve(result());assert.equal(await edited,false);apiHold=null;assert.equal(form.task,'New user text');
  confirmHold=deferred();const editDuringConfirm=c.replay();await Promise.resolve();form={...form,workspace:'/new'};confirmHold.resolve(true);assert.equal(await editDuringConfirm,false);confirmHold=null;
  ready=false;const before=calls.length;assert.equal(await c.replay(),false);assert.equal(calls.length,before);ready=true;
  confirmHold=deferred();const blockedAfterConfirm=c.replay();await Promise.resolve();ready=false;confirmHold.resolve(true);assert.equal(await blockedAfterConfirm,false);confirmHold=null;ready=true;
  selected='a/b?x=1';assert.equal(await c.replay(),true);assert.equal(calls.at(-1)[0],'/api/runs/a%2Fb%3Fx%3D1/replay');
  apiHold=deferred();const destroyed=c.replay();const beforeDestroy=applied.length,stateCount=states.length;c.destroy();apiHold.resolve(result(selected));assert.equal(await destroyed,false);assert.equal(applied.length,beforeDestroy);assert.equal(states.length,stateCount);assert.equal(await c.replay(),false);
  console.log('PASS replay controller: full draft schema/Unicode limits, strict safe allowlist, encoded GET-only requests, cancel, repeat serialization, errors, selected-run/composer drift, canApply and destroy.');
}
async function browserTests(){
  const {chromium}=require('playwright');const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
  try{const page=await browser.newPage({viewport:{width:1024,height:768}});await page.setContent('<!doctype html><html><body><div id="tools"></div><textarea id="task">Unsaved</textarea></body></html>');
    for(const file of ['style.css','design-system.css'])await page.addStyleTag({content:fs.readFileSync(path.resolve(sourceRoot,file),'utf8')});
    await page.addScriptTag({content:fs.readFileSync(path.resolve(sourceRoot,'i18n.js'),'utf8')});await page.evaluate(()=>window.CodexI18n.setLanguage('en'));await page.addScriptTag({content:fs.readFileSync(path.resolve(sourceRoot,'run-replay.js'),'utf8')});
    await page.evaluate(data=>{window.calls=[];window.applied=[];window.notices=[];window.confirmed=[];window.accept=false;window.mounted=window.CodexRunReplay.mount({anchor:document.querySelector('#tools'),api:async(...args)=>{window.calls.push(args);if(window.hold)await new Promise(resolve=>window.release=resolve);return {run_id:'r1',data,warnings:['security_reset','missing_workspace','invalid_settings']};},read:()=>({task:document.querySelector('#task').value}),apply:value=>{window.applied.push(value);document.querySelector('#task').value=value.task;},getSelectedRun:()=>({id:'r1'}),confirm:async(...args)=>{window.confirmed.push(args);return window.accept;},notify:(...args)=>window.notices.push(args)});},draft('<img src=x onerror=alert(1)> literal saved task'));
    const button=page.getByRole('button',{name:'Reuse task',exact:true});await button.click();assert.equal(await page.locator('#task').inputValue(),'Unsaved');assert.equal(await page.evaluate(()=>window.applied.length),0);assert.match(await page.evaluate(()=>window.confirmed[0][1]),/Permissions are not copied/);
    await page.evaluate(()=>{window.accept=true;window.hold=true;});await button.click();assert.equal(await page.getByRole('button',{name:'Preparing task…',exact:true}).isDisabled(),true);await page.evaluate(()=>{window.hold=false;window.release();});await page.waitForFunction(()=>window.applied.length===1);assert.equal(await page.locator('#task').inputValue(),'<img src=x onerror=alert(1)> literal saved task');assert.equal(await page.locator('img').count(),0);assert.equal(await page.evaluate(()=>window.calls.every(args=>args.length===1)),true);assert.match(await page.evaluate(()=>window.notices.at(-1)[0]),/Review its settings/);
    await page.evaluate(()=>window.mounted.destroy());assert.equal(await page.locator('#run-replay-open').count(),0);console.log('PASS browser replay: English labels, explicit confirmation, cancellation, busy state, literal full task and no execution request.');
  }finally{await browser.close();}
}
(async()=>{await pureTests();if(process.argv.includes('--browser'))await browserTests();})().catch(error=>{console.error(error);process.exitCode=1;});
