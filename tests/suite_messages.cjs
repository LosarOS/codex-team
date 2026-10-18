'use strict';
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync(path.resolve(process.argv[2]||'codex_team/static','suite.js'),'utf8');
const start=source.indexOf('  function message('),end=source.indexOf('  function button(',start);
class ApiError extends Error {constructor(message){super(message);this.technical={request:'fixture'};}}
let shown=[];const status={replaceChildren(...v){shown=v;},classList:{toggle(){}},setAttribute(){},append(){}};
const I={language:'en',t:x=>x};const context={window:{CodexApi:{ApiError}},I,status,el:(tag,cls,text)=>({text,append(){}}),safeTechnical:x=>JSON.stringify(x)};
vm.createContext(context);vm.runInContext(source.slice(start,end)+'\nthis.message=message;',context);
context.message(new ApiError('Select a trusted local Docker image.'),true);assert.equal(shown[0].text,'Select a trusted local Docker image.');
I.language='ru';context.message(new ApiError('Авторизуйтесь в Codex.'),true);assert.equal(shown[0].text,'Авторизуйтесь в Codex.');
context.message(new Error('opaque internal failure'),true);assert(shown[0].text.includes('Не удалось'));
I.language='en';context.message(new Error('Fill in the title and content.'),true);assert.equal(shown[0].text,'Fill in the title and content.');
console.log('PASS: localized suite errors retain actionable API guidance and system validation.');
