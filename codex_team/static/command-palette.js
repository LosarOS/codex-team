/* Local workspace search. This module never executes tasks or fetches remote data. */
((root) => {
  'use strict';
  const labels = {
    'Поиск и команды':'Search and commands', 'Поиск по рабочему пространству':'Search workspace',
    'Разделы, проекты и загруженные запуски…':'Pages, projects and loaded runs…',
    'Новая задача':'New task', 'Создать задачу':'Create task', 'Раздел':'Page', 'Проект':'Project', 'Запуск':'Run',
    'Обзор':'Overview', 'Проекты':'Projects', 'Запуски и управление':'Runs and Mission Control', 'История':'History',
    'Архитектор задач':'Task Architect', 'Знания проекта':'Project Intelligence', 'Проверка качества':'QA Arena',
    'Машина времени Git':'Git Time Machine', 'Агенты':'Agents', 'Наборы агентов':'Agent Packs',
    'Бюджет запусков':'Run budgets', 'Использование':'Usage', 'Центр действий':'Action Center', 'Настройки':'Settings',
    'Закрыть поиск':'Close search', 'Ничего не найдено':'No matches',
    'Попробуйте название раздела, проекта, путь или текст задачи.':'Try a page, project, path or task description.',
    'Локальный поиск: только уже загруженные проекты и запуски.':'Local search: only projects and runs already loaded.',
    'Нет связи. Доступны разделы и ранее загруженные записи.':'Offline. Pages and previously loaded entries remain available.',
    'Показано {count} из {total} результатов':'Showing {count} of {total} results',
    'Перейти':'Open', 'Выбрать':'Select', 'Закрыть':'Close',
    'Не удалось открыть запись. Обновите данные и повторите поиск.':'Could not open this entry. Refresh the data and search again.',
    'Рабочее пространство ещё загружается. Повторите поиск через несколько секунд.':'Workspace is still loading. Try searching again in a few seconds.',
    'Выполняется':'Running', 'Завершён':'Completed', 'Ошибка':'Failed', 'Ожидает':'Waiting', 'Пауза':'Paused',
    'Остановлен':'Stopped', 'Ожидает решения':'Needs action', 'Ожидание этапа':'Waiting for stage',
    'Приостановка':'Pausing', 'Остановка':'Stopping', 'Прерван':'Interrupted', 'Нужен вход':'Sign-in required',
    'Лимит Codex':'Codex limit', 'Заблокировано':'Blocked', 'Выполнено частично':'Partially completed'
  };
  const navigation = [
    ['workbench','Обзор','overview home dashboard обзор главная'],
    ['projects','Проекты','projects repository repositories github git проекты репозиторий'],
    ['runs','Запуски и управление','runs mission control agents pipeline запуски управление'],
    ['history','История','history completed resume история восстановление'],
    ['architect','Архитектор задач','task architect specification план техническое задание архитектор'],
    ['intelligence','Знания проекта','project intelligence architecture memory аналитика знания память архитектура'],
    ['qa','Проверка качества','qa arena quality tests build lint проверка качество тесты'],
    ['git','Машина времени Git','git time machine checkpoints diff машина времени контрольные точки'],
    ['agents','Агенты','agents roles instructions агенты роли инструкции'],
    ['packs','Наборы агентов','packs teams наборы команды'],
    ['budget','Бюджет запусков','budget guardian limits бюджет лимиты'],
    ['usage','Использование','usage tokens resources использование токены ресурсы'],
    ['actions','Центр действий','action center approvals permissions разрешения решения действия'],
    ['settings','Настройки','settings preferences language theme appearance настройки язык тема доступ']
  ];
  const string = value => typeof value === 'string' ? value : '';
  const normalize = value => string(value).normalize('NFKC').toLocaleLowerCase().trim();
  function entries(snapshot = {}, translate = value => value) {
    const result = [{id:'new-task',kind:'new',label:translate('Новая задача'),detail:translate('Создать задачу'),search:'new task create задача создать новая'}];
    for (const [page,label,aliases] of navigation) result.push({id:'page:'+page,kind:'page',page,label:translate(label),detail:translate('Раздел'),search:label+' '+aliases});
    for (const project of (Array.isArray(snapshot.projects) ? snapshot.projects : []).slice(0,5000)) {
      if (!project || !string(project.id)) continue;
      result.push({id:'project:'+project.id,kind:'project',target:project.id,label:string(project.name)||string(project.path)||project.id,detail:string(project.path),search:translate('Проект')+' project проект '+project.id});
    }
    const states={RUNNING:'Выполняется',COMPLETED:'Завершён',FAILED:'Ошибка',ERROR:'Ошибка',QUEUED:'Ожидает',PAUSED:'Пауза',STOPPED:'Остановлен',CANCELLED:'Остановлен',WAITING_USER:'Ожидает решения',WAITING:'Ожидание этапа',PAUSING:'Приостановка',STOPPING:'Остановка',INTERRUPTED:'Прерван',DONE:'Завершён',USER_DECISION_REQUIRED:'Ожидает решения',AUTH_REQUIRED:'Нужен вход',USAGE_LIMIT:'Лимит Codex',BLOCKED:'Заблокировано',PARTIAL:'Выполнено частично'};
    for (const run of (Array.isArray(snapshot.runs) ? snapshot.runs : []).slice(0,5000)) {
      if (!run || !string(run.id)) continue;
      const state=string(run.state);
      const path=string(run.path)||string(run.workspace);
      result.push({id:'run:'+run.id,kind:'run',target:run.id,label:string(run.task)||run.id,detail:[translate(states[state]||state),path].filter(Boolean).join(' · '),search:'run запуск '+run.id+' '+state});
    }
    return result;
  }
  function search(items, query, limit = 40) {
    const words=normalize(query).split(/\s+/).filter(Boolean);
    return items.map((item,index)=>({item,index,text:normalize(item.label+' '+item.detail+' '+item.search)}))
      .filter(row=>words.every(word=>row.text.includes(word)))
      .sort((a,b)=>{
        if (!words.length) return a.index-b.index;
        const score=row=>words.reduce((sum,word)=>sum+(normalize(row.item.label).startsWith(word)?4:normalize(row.item.label).includes(word)?2:0),0);
        return score(b)-score(a)||a.index-b.index;
      }).slice(0, Math.max(0,limit)).map(row=>row.item);
  }
  function moveSelection(current, count, direction) {
    return count ? (current + direction + count) % count : -1;
  }
  const api={entries,search,moveSelection};
  if (typeof module !== 'undefined' && module.exports) module.exports=api;
  if (!root.document) return;
  const doc=root.document;
  const I=root.CodexI18n||{t:value=>value,register:()=>{}};
  I.register(labels);
  const t=source=>I.t(source);
  const el=(tag,className,text)=>{const node=doc.createElement(tag);if(className)node.className=className;if(text!==undefined)node.textContent=text;return node;};
  const icon=()=>{
    const svg=doc.createElementNS('http://www.w3.org/2000/svg','svg');
    for(const [key,value] of Object.entries({width:'18',height:'18',viewBox:'0 0 24 24',fill:'none',stroke:'currentColor','stroke-width':'1.8','aria-hidden':'true'}))svg.setAttribute(key,value);
    const circle=doc.createElementNS(svg.namespaceURI,'circle');circle.setAttribute('cx','10.5');circle.setAttribute('cy','10.5');circle.setAttribute('r','6.5');
    const line=doc.createElementNS(svg.namespaceURI,'path');line.setAttribute('d','m16 16 5 5');svg.append(circle,line);return svg;
  };
  function resultIcon(kind) {
    const svg=doc.createElementNS('http://www.w3.org/2000/svg','svg');
    for(const [key,value] of Object.entries({width:'17',height:'17',viewBox:'0 0 24 24',fill:'none',stroke:'currentColor','stroke-width':'1.7','stroke-linecap':'round','stroke-linejoin':'round','aria-hidden':'true'}))svg.setAttribute(key,value);
    const path=doc.createElementNS(svg.namespaceURI,'path');
    path.setAttribute('d',({new:'M12 5v14M5 12h14',project:'M3 7h7l2 2h9v11H3ZM3 7V4h7l2 3',run:'m9 5 10 7-10 7Z',page:'M4 4h16v16H4ZM4 9h16M9 9v11'})[kind]);svg.append(path);return svg;
  }
  const trigger=el('button','command-search-trigger');trigger.type='button';trigger.append(icon(),el('span','command-search-label',t('Поиск и команды')),el('kbd','',/Mac|iPhone|iPad/.test(root.navigator?.platform||'')?'⌘ K':'Ctrl K'));
  trigger.setAttribute('aria-haspopup','dialog');trigger.setAttribute('aria-keyshortcuts','Control+k Meta+k');
  const dialog=el('dialog','command-palette');dialog.id='command-palette';dialog.setAttribute('aria-labelledby','command-palette-title');
  const heading=el('h2','command-palette-title',t('Поиск по рабочему пространству'));heading.id='command-palette-title';
  const field=el('div','command-palette-field');field.append(icon());
  const input=el('input','command-palette-input');input.type='search';input.autocomplete='off';input.spellcheck=false;
  input.setAttribute('role','combobox');input.setAttribute('aria-autocomplete','list');input.setAttribute('aria-expanded','false');input.setAttribute('aria-controls','command-palette-results');input.setAttribute('aria-label',t('Поиск по рабочему пространству'));input.placeholder=t('Разделы, проекты и загруженные запуски…');
  const closeButton=el('button','command-palette-close','Esc');closeButton.type='button';closeButton.setAttribute('aria-label',t('Закрыть поиск'));field.append(input,closeButton);
  const hint=el('p','command-palette-hint');hint.id='command-palette-hint';input.setAttribute('aria-describedby',hint.id);
  const list=el('div','command-palette-results');list.id='command-palette-results';list.setAttribute('role','listbox');list.setAttribute('aria-label',t('Поиск и команды'));
  const empty=el('div','command-palette-empty');empty.append(el('strong','',t('Ничего не найдено')),el('p','',t('Попробуйте название раздела, проекта, путь или текст задачи.')));
  const status=el('p','command-palette-status');status.setAttribute('role','status');status.setAttribute('aria-live','polite');status.setAttribute('aria-atomic','true');
  const footer=el('div','command-palette-footer');
  for(const [key,label] of [['↑ ↓','Выбрать'],['Enter','Перейти'],['Esc','Закрыть']]){const item=el('span');item.append(el('kbd','',key),doc.createTextNode(' '+t(label)));footer.append(item);}
  dialog.append(heading,field,hint,list,empty,status,footer);doc.body.append(dialog);
  const topbar=doc.querySelector('.topbar');if(topbar)topbar.insertBefore(trigger,doc.querySelector('.topbar-right'));else return;
  let visible=[],selected=-1,previousFocus=null,snapshot={},failure='';
  function updateSelection(next) {
    selected=next;
    for(const [index,option] of [...list.children].entries())option.setAttribute('aria-selected',String(index===selected));
    if(selected>=0&&list.children[selected]){input.setAttribute('aria-activedescendant',list.children[selected].id);list.children[selected].scrollIntoView?.({block:'nearest'});}else input.removeAttribute('aria-activedescendant');
  }
  function render(preserveSelection=true) {
    const active=preserveSelection?visible[selected]?.id:null;
    try{snapshot=root.CodexWorkspace?.entries()||{};}catch(_){snapshot={};}
    const all=entries(snapshot,t);const matches=search(all,input.value,all.length);visible=matches.slice(0,40);const count=matches.length;
    list.replaceChildren();
    const groupNames={new:'Создать задачу',page:'Раздел',project:'Проект',run:'Запуск'};
    visible.forEach((entry,index)=>{
      const option=el('div','command-palette-option');option.id='command-result-'+index;option.setAttribute('role','option');option.setAttribute('aria-selected','false');option.dataset.kind=entry.kind;option.title=[entry.label,entry.detail].filter(Boolean).join(' — ');
      const symbol=el('span','command-result-symbol');symbol.append(resultIcon(entry.kind));option.append(symbol);
      const content=el('div','command-result-copy');content.append(el('strong','',entry.label),el('small','',entry.detail));option.append(content,el('span','command-result-kind',t(groupNames[entry.kind])));
      option.addEventListener('pointerdown',event=>event.preventDefault());option.addEventListener('click',()=>activate(index));list.append(option);
    });
    empty.hidden=visible.length>0;list.hidden=!visible.length;
    hint.textContent=snapshot.online===false?t('Нет связи. Доступны разделы и ранее загруженные записи.'):!root.CodexWorkspace?t('Рабочее пространство ещё загружается. Повторите поиск через несколько секунд.'):t('Локальный поиск: только уже загруженные проекты и запуски.');
    status.textContent=failure||I.t('Показано {count} из {total} результатов',{count:visible.length,total:count});
    updateSelection(visible.length?Math.max(0,visible.findIndex(entry=>entry.id===active)):-1);
  }
  function close(restore=true){if(!dialog.open)return;input.setAttribute('aria-expanded','false');dialog.close();if(restore&&previousFocus?.isConnected&&!previousFocus.closest?.('[hidden]'))previousFocus.focus();}
  function open(keepQuery=false){if(dialog.open){input.focus();return;}if(doc.querySelector('dialog[open]'))return;previousFocus=doc.activeElement;if(!keepQuery){input.value='';failure='';}render(keepQuery);dialog.showModal();input.setAttribute('aria-expanded','true');input.focus();}
  async function activate(index) {
    const entry=visible[index];if(!entry)return;
    const bridge=root.CodexWorkspace;
    if(!bridge){failure=t('Рабочее пространство ещё загружается. Повторите поиск через несколько секунд.');render();return;}
    close(false);
    try{if(entry.kind==='new')await bridge.newTask();else if(entry.kind==='page')await bridge.navigate(entry.page);else if(entry.kind==='project')await bridge.selectProject(entry.target);else await bridge.openRun(entry.target);if(entry.kind!=='new')doc.getElementById('main')?.focus();}
    catch(_){failure=t('Не удалось открыть запись. Обновите данные и повторите поиск.');open(true);}
  }
  trigger.addEventListener('click',()=>open());closeButton.addEventListener('click',()=>close());
  dialog.addEventListener('cancel',event=>{event.preventDefault();close();});
  dialog.addEventListener('click',event=>{if(event.target!==dialog)return;const bounds=dialog.getBoundingClientRect();if(event.clientX<bounds.left||event.clientX>bounds.right||event.clientY<bounds.top||event.clientY>bounds.bottom)close();});
  input.addEventListener('input',()=>{failure='';render(false);});
  dialog.addEventListener('keydown',event=>{
    if(event.key==='Escape'){event.preventDefault();close();}
    else if(event.target===input&&['ArrowDown','ArrowUp'].includes(event.key)){event.preventDefault();updateSelection(moveSelection(selected,visible.length,event.key==='ArrowDown'?1:-1));}
    else if(event.target===input&&event.key==='Enter'){event.preventDefault();activate(selected);}
    else if(event.key==='Tab'){const ends=[input,closeButton];const index=ends.indexOf(doc.activeElement);event.preventDefault();ends[(index+(event.shiftKey?-1:1)+ends.length)%ends.length].focus();}
  });
  doc.addEventListener('keydown',event=>{
    if(event.defaultPrevented||event.isComposing||event.altKey)return;
    const modified=(event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='k';
    const typing=event.target?.closest?.('input,textarea,select,[contenteditable]:not([contenteditable="false"]),[role="textbox"]');
    const slash=event.key==='/'&&!event.ctrlKey&&!event.metaKey&&!typing;
    if(modified||slash){if(!dialog.open&&doc.querySelector('dialog[open]'))return;event.preventDefault();if(modified&&dialog.open)close();else open();}
  });
  root.addEventListener('codex-workspace-change',()=>{if(dialog.open)render();});
})(typeof window!=='undefined'?window:globalThis);
