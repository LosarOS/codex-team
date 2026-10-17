'use strict';
const assert=require('assert'),fs=require('fs'),vm=require('vm'),path=require('path');
const dir=path.resolve(process.argv[2]||'codex_team/static');
const context={localStorage:{getItem:()=>null,setItem(){}},console};context.window=context;
vm.createContext(context);vm.runInContext(fs.readFileSync(path.join(dir,'i18n-catalog.js'),'utf8'),context);vm.runInContext(fs.readFileSync(path.join(dir,'i18n.js'),'utf8'),context);
const I=context.CodexI18n;assert.equal(I.language,'ru');assert.equal(I.t('Проекты'),'Проекты');I.setLanguage('en');assert.equal(I.t('Проекты'),'Projects');assert.equal(I.locale,'en-US');
I.register({'Ошибка: {message}':'Error: {message}','Версия {0}':'Version {0}'});
assert.equal(I.t('Ошибка: {message}',{message:'Собственный текст <script>'}),'Error: Собственный текст <script>');
assert.equal(I.tr(['Версия ',''],'1.2.3'),'Version 1.2.3');
assert.equal(I.t('my private task text'),'my private task text');
assert.throws(()=>I.setLanguage('de'));assert.equal(I.language,'en');
const source=fs.readFileSync(path.join(dir,'suite.js'),'utf8');assert(source.includes("d.sections?.['Цель']"));assert(!source.includes("d.sections?.[I.t('Цель')]"));
for(const [key,value]of Object.entries(context.CodexI18nCatalog)) {assert.equal(typeof value,'string'); const placeholders=s=>[...s.matchAll(/\{\d+\}/g)].map(x=>x[0]).sort(); assert.deepEqual(placeholders(key),placeholders(value),key);}
console.log(JSON.stringify({result:'PASS',catalog:Object.keys(context.CodexI18nCatalog).length,evidence:['RU/EN selection','named and template placeholders','user data unchanged','unknown strings unchanged','invalid language rejected','specification keys stable']}));
