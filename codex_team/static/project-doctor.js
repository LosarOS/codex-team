/* Local discovery only. Recommendations never execute from this panel. */
((root) => {
  'use strict';
  const labels = {
    'Диагностика проекта': 'Project Doctor', 'Обновить диагностику': 'Refresh diagnostics',
    'Закрыть диагностику': 'Close diagnostics', 'Читаем декларации проекта…': 'Reading project declarations…',
    'Проверка не удалась. Повторите попытку.': 'Inspection failed. Try again.',
    'Обнаружено локально': 'Discovered locally', 'Не проверено': 'Not verified',
    'Не обнаружено': 'Not discovered', 'Среда не поддерживает Windows runtime': 'Environment cannot run Windows applications',
    'Тип проекта': 'Project type', 'Решения и проекты': 'Solutions and projects',
    'Версия SDK из исходников': 'SDK declared in source', 'Среда проверки': 'Inspection environment',
    'Раздельные этапы проверки': 'Separate validation gates', 'Рекомендации команд': 'Suggested commands',
    'Команды не выполнялись. Передайте задачу существующему движку с нужными разрешениями и подтверждением.': 'Commands have not run. Use the existing engine with appropriate permissions and confirmation.',
    'Статический анализ не подтверждает сборку, установку или запуск приложения.': 'Static analysis does not verify building, installation or application startup.',
    'Предупреждения': 'Warnings', 'Структурированный отчёт': 'Structured report',
    'Декларации .NET не найдены': 'No .NET declarations found', 'Исходная ревизия': 'Source revision',
    'SDK .NET': '.NET SDK', 'Windows SDK': 'Windows SDK', 'Совместимость среды': 'Environment compatibility',
    'Компиляция исходников': 'Source compilation', 'Тесты': 'Tests', 'Windows publish': 'Windows publish',
    'Проверка установщика': 'Installer smoke', 'Интерактивный GUI': 'Interactive GUI', 'Файлы релиза': 'Release artifacts',
    'Ограничения анализа': 'Inspection limitations', 'Происхождение: декларации и локальная среда': 'Provenance: source declarations and local environment',
    'Условия MSBuild и импортированные свойства не вычислялись. Скрытые, игнорируемые и слишком большие файлы исключены.': 'MSBuild conditions and imported properties were not evaluated. Sensitive, ignored and oversized files are excluded.',
    'Не было запуска команд, установки SDK, сетевых проверок или вызовов модели.': 'No commands, SDK installations, network probes or model calls were performed.',
  };
  const I=root.CodexI18n||{t:s=>s,register(){}};I.register(labels);
  const gates={dotnet_sdk:'SDK .NET',windows_sdk:'Windows SDK',environment:'Совместимость среды',source_compilation:'Компиляция исходников',tests:'Тесты',windows_publish:'Windows publish',installer_smoke:'Проверка установщика',interactive_gui:'Интерактивный GUI',release_artifacts:'Файлы релиза'};
  function valid(report){
    const strings=v=>Array.isArray(v)&&v.length<=4000&&v.every(x=>typeof x==='string'&&x.length<=4096);
    const paths=v=>Array.isArray(v)&&v.length<=4000&&v.every(x=>x&&typeof x.path==='string'&&x.path.length<=4096);
    return !!(report?.schema_version===1&&typeof report.project_id==='string'&&report.environment&&typeof report.environment.os==='string'&&typeof report.environment.architecture==='string'&&strings(report.environment.dotnet_sdks)&&paths(report.projects)&&report.projects.every(p=>strings(p.frameworks))&&paths(report.solutions)&&Array.isArray(report.checks)&&report.checks.length<=20&&report.checks.every(c=>c&&Object.hasOwn(gates,c.id)&&['discovered','not_discovered','unsupported','not_verified','not_tested','unknown'].includes(c.status))&&Array.isArray(report.recommendations)&&report.recommendations.length<=100&&report.recommendations.every(c=>c&&strings(c.argv)));
  }
  function mount({anchor,api}){
    const t=s=>I.t(s),el=(tag,cls,text)=>{const n=root.document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n;};
    const panel=el('section','panel editor-panel project-doctor');panel.id='project-doctor-panel';panel.hidden=true;
    const header=el('div','panel-heading'),title=el('h2','',t('Диагностика проекта')),actions=el('div','button-row'),body=el('div','doctor-body');title.tabIndex=-1;
    let epoch=0,selected=null,opener=null;
    const button=(text,fn)=>{const b=el('button','button secondary',t(text));b.type='button';b.addEventListener('click',fn);return b;};
    const refresh=button('Обновить диагностику',()=>load()),close=button('Закрыть диагностику',()=>{++epoch;selected=null;panel.hidden=true;panel.setAttribute('aria-busy','false');opener?.focus?.();});
    actions.append(refresh,close);header.append(title,actions);panel.append(header,body);anchor.after(panel);
    function render(report){
      body.replaceChildren(el('p','field-note',t('Статический анализ не подтверждает сборку, установку или запуск приложения.')),el('p','muted',t('Происхождение: декларации и локальная среда')));
      body.append(el('p','mono',t('Исходная ревизия')+': '+(report.head||'—')));
      const facts=el('div','doctor-grid');
      for(const [label,value] of [['Тип проекта',report.project_type],['Среда проверки',report.environment.os+' · '+report.environment.architecture],['SDK .NET',(report.environment.dotnet_sdks||[]).join(', ')||t('Не обнаружено')],['Версия SDK из исходников',(report.sdk_requirements||[]).map(s=>s.version+' ('+s.source+')').join(', ')||'—']]){const f=el('div','doctor-fact');f.append(el('span','muted',t(label)),el('strong','',String(value)));facts.append(f);}body.append(facts);
      body.append(el('h3','',t('Раздельные этапы проверки')));const checks=el('div','doctor-grid');
      for(const check of report.checks){const line=el('div','doctor-fact');line.append(el('span','',t(gates[check.id])),el('strong',check.status==='unsupported'?'state-warning':'muted',t(check.status==='discovered'?'Обнаружено локально':check.status==='not_discovered'?'Не обнаружено':check.status==='unsupported'?'Среда не поддерживает Windows runtime':'Не проверено')));checks.append(line);}body.append(checks);
      body.append(el('h3','',t('Решения и проекты')));const projects=el('ul','doctor-projects');
      for(const p of [...(report.solutions||[]),...report.projects])projects.append(el('li','mono',p.path+(p.frameworks?.length?' · '+p.frameworks.join(', '):'')));
      body.append(projects);if(!report.projects.length)body.append(el('p','muted',t('Декларации .NET не найдены')));
      body.append(el('h3','',t('Рекомендации команд')),el('p','field-note',t('Команды не выполнялись. Передайте задачу существующему движку с нужными разрешениями и подтверждением.')));
      for(const c of report.recommendations)body.append(el('pre','code-block',JSON.stringify(c.argv)));
      if(report.warnings?.length){body.append(el('h3','',t('Предупреждения')));for(const warning of report.warnings)body.append(el('p','doctor-warning',warning.source+': '+warning.detail));}
      body.append(el('h3','',t('Ограничения анализа')),el('p','muted',t('Условия MSBuild и импортированные свойства не вычислялись. Скрытые, игнорируемые и слишком большие файлы исключены.')),el('p','muted',t('Не было запуска команд, установки SDK, сетевых проверок или вызовов модели.')));
      const raw=el('details','raw-details');raw.append(el('summary','',t('Структурированный отчёт')),el('pre','code-block',JSON.stringify(report,null,2)));body.append(raw);
    }
    async function load(){if(!selected)return;const generation=++epoch,id=selected.id;refresh.disabled=true;panel.setAttribute('aria-busy','true');body.replaceChildren(el('p','loading-state',t('Читаем декларации проекта…')));
      try{const report=await api('/api/projects/'+encodeURIComponent(id)+'/doctor');if(generation!==epoch)return;if(!valid(report)||report.project_id!==id)throw Error('Invalid diagnostic report');render(report);}
      catch(error){if(generation===epoch){const warning=el('p','form-error',t('Проверка не удалась. Повторите попытку.'));warning.setAttribute('role','alert');body.replaceChildren(warning,el('pre','code-block',String(error.message)));}}
      finally{if(generation===epoch){refresh.disabled=false;panel.setAttribute('aria-busy','false');}}
    }
    return {open(project){selected=project;opener=root.document.activeElement;panel.hidden=false;title.textContent=t('Диагностика проекта')+' · '+project.name;title.focus();panel.scrollIntoView?.({block:'start'});return load();}};
  }
  root.CodexProjectDoctor={mount,valid};if(typeof module!=='undefined')module.exports={valid};
})(typeof window!=='undefined'?window:globalThis);
