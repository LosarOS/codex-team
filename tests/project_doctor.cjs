'use strict';
const assert=require('node:assert/strict');
const {valid}=require('../codex_team/static/project-doctor.js');
const report={schema_version:1,project_id:'p',environment:{os:'Linux',architecture:'x64',dotnet_sdks:[]},projects:[{path:'app.csproj',frameworks:['net10.0']}],solutions:[],checks:[{id:'interactive_gui',status:'not_verified'}],recommendations:[]};
assert(valid(report));
for(const value of [null,{},[],{...report,checks:[null]},{...report,checks:[{id:'interactive_gui',status:'PASS'}]},{...report,projects:[null]},{...report,recommendations:[{argv:'pwsh command'}]}])assert(!valid(value));
console.log('PASS Project Doctor schema: malformed reports rejected; discovery cannot claim runtime PASS.');
