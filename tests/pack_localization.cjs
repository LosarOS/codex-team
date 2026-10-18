const assert=require('assert'),fs=require('fs'),vm=require('vm');
const source=fs.readFileSync('codex_team/static/app.js','utf8');const snippet=source.slice(source.indexOf('  const builtInPackText ='),source.indexOf('  function renderRegistry()'));
const context={I:{t:value=>'EN:'+value}};vm.createContext(context);vm.runInContext(snippet+';this.display=packDisplay;',context);
assert.equal(context.display({name:'software-development',builtin:true,title:'Разработка ПО'},'title'),'EN:Разработка ПО');
assert.equal(context.display({name:'software-development',builtin:true,title:'Моя команда'},'title'),'Моя команда');
assert.equal(context.display({name:'custom',builtin:false,title:'Разработка ПО'},'title'),'Разработка ПО');
assert.equal(context.display({name:'audit',builtin:true,description:'Проверка безопасности и производительности'},'description'),'EN:Проверка безопасности и производительности');
console.log('PASS: unchanged bundled pack labels translated; custom titles and descriptions preserved.');
