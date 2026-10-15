"""Private Git snapshots and confirmed, non-destructive worktree recovery."""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
import re
import subprocess
import tempfile
import threading
import uuid
from .workspace import WorkspaceManager, WorkspaceError
from .storage import sanitize


class TimeMachine:
    def __init__(self, root, store):
        self.root = Path(root).resolve()
        self.store = store
        self.workspace = WorkspaceManager(self.root)
        self.lock = threading.RLock()
        self.hooks = self.root / '.ai-team' / 'time-machine-hooks'
        self.hooks.mkdir(parents=True, exist_ok=True)
        if not self.hooks.resolve().is_relative_to(self.root) or self.hooks.is_symlink() or any(self.hooks.iterdir()):
            raise WorkspaceError('Unsafe Git hooks directory')

    def _project(self, project_id):
        source = self.store if hasattr(self.store, 'project') else self.store.store
        return self.workspace.validate(Path(source.project(project_id)['path']))

    def _git(self, path, *args, index=None):
        env = {k:v for k,v in os.environ.items() if not k.startswith('GIT_')}
        env.update(GIT_TERMINAL_PROMPT='0', GIT_OPTIONAL_LOCKS='0', GIT_PAGER='cat', GIT_AUTHOR_NAME='Codex Team',
                   GIT_AUTHOR_EMAIL='codex-team@localhost', GIT_COMMITTER_NAME='Codex Team',
                   GIT_COMMITTER_EMAIL='codex-team@localhost')
        if index: env['GIT_INDEX_FILE'] = str(index)
        # Spool Git output to disk before reading a bounded amount into memory.
        # Huge diffs fail explicitly instead of freezing the desktop process.
        with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
            result = subprocess.run(['git','-c','core.fsmonitor=false','-c',f'core.hooksPath={self.hooks}',
                                     '-c','commit.gpgSign=false',*args],cwd=path,env=env,
                                    stdout=output,stderr=errors,timeout=60)
            errors.seek(0)
            error = errors.read(2000).decode('utf-8','replace')
            if result.returncode:
                raise WorkspaceError('Git operation failed: ' + str(sanitize(error)))
            output.seek(0)
            raw = output.read(8_000_001)
            if len(raw) > 8_000_000:
                raise WorkspaceError('Git output exceeds the safe 8 MB limit; narrow the comparison')
            text = raw.decode('utf-8','replace')
            return text.strip() if '\x00' not in text else text

    @staticmethod
    def _sensitive(name):
        return WorkspaceManager.sensitive(name) or any(
            re.search(r'(secret|credential|token|password|private[_.-]?key)', part, re.I) or
            part.lower().endswith(('.pem','.key','.p12','.pfx')) for part in Path(name).parts)

    def _safe_tree(self, path, revision):
        entries = self._git(path,'ls-tree','-r','-z',revision)
        for entry in entries.split('\x00'):
            if not entry: continue
            meta,name = entry.split('\t',1)
            if self._sensitive(name) or meta.split()[0] in {'120000','160000'}:
                raise WorkspaceError('Контрольная точка заблокирована: секреты, symlink или submodule в Git tree')

    def _record(self, project_id, checkpoint_id):
        record = self.store.get('git_checkpoint',checkpoint_id)
        if record['project_id'] != project_id:
            raise WorkspaceError('Checkpoint belongs to another project')
        sha = record['data']['sha']
        if not re.fullmatch('[0-9a-f]{40,64}',sha): raise WorkspaceError('Invalid checkpoint SHA')
        return record

    def list(self, project_id, limit=50, offset=0, q=''):
        self._project(project_id)
        return self.store.page('git_checkpoint',project_id,limit=min(max(limit,1),100),offset=max(offset,0),q=q)

    def create(self, project_id, label='', run_id=None, stage=None, request_id=None, workspace=None):
        with self.lock:
            path = self._project(project_id)
            if workspace:
                candidate = self.workspace.validate(Path(workspace))
                if self._git(path,'rev-parse','--path-format=absolute','--git-common-dir') != self._git(candidate,'rev-parse','--path-format=absolute','--git-common-dir'):
                    raise WorkspaceError('Workspace is not part of this project')
                path = candidate
            if request_id:
                record_id = 'cp_' + hashlib.sha256(f'{project_id}:{request_id}'.encode()).hexdigest()[:32]
                try: return self._record(project_id,record_id)
                except KeyError: pass
            else: record_id = 'cp_' + uuid.uuid4().hex
            self.workspace._check_filters(path)
            head = self._git(path,'rev-parse','--verify','HEAD')
            self._safe_tree(path,head)
            tracked = self._git(path,'ls-files','-z').split('\x00')
            for name in filter(None,tracked):
                if self._sensitive(name) or (path/name).is_symlink():
                    raise WorkspaceError('Небезопасный отслеживаемый файл')
            with tempfile.TemporaryDirectory(prefix='codex-checkpoint-') as tmp:
                index = Path(tmp)/'index'
                self._git(path,'read-tree',head,index=index)
                # Update tracked files only: untracked files are intentionally not captured.
                self._git(path,'add','-u','--','.',index=index)
                # Original index additions are tracked too; replay their safe names
                # through a NUL pathspec without touching the user's index.
                additions = [name for name in tracked if name and (path/name).is_file()]
                if len(additions) > 100000 or sum(len(name.encode('utf-8')) + 1 for name in additions) > 8_000_000:
                    raise WorkspaceError('Tracked file list exceeds checkpoint safety limit')
                if additions:
                    pathspec = Path(tmp)/'tracked-pathspec'
                    pathspec.write_bytes(b''.join(name.encode('utf-8') + b'\x00' for name in additions))
                    self._git(path,'--literal-pathspecs','add','-f',f'--pathspec-from-file={pathspec}',
                              '--pathspec-file-nul',index=index)
                tree = self._git(path,'write-tree',index=index)
                self._safe_tree(path,tree)
                sha = self._git(path,'commit-tree',tree,'-p',head,'-m','Codex Team checkpoint')
            self._git(path,'update-ref',f'refs/codex-team/checkpoints/{record_id}',sha)
            return self.store.put('git_checkpoint',project_id,{'label':str(sanitize(label))[:200],
                'sha':sha,'source_head':head,'run_id':run_id,'stage':stage,
                'source_workspace':str(path),'untracked_captured':False},record_id=record_id)

    def compare(self, project_id, from_id, to_id):
        path = self._project(project_id)
        a,b = self._record(project_id,from_id),self._record(project_id,to_id)
        for record in (a,b): self._safe_tree(path,record['data']['sha'])
        args = [a['data']['sha'],b['data']['sha'],'--']
        names = self._git(path,'diff','--no-ext-diff','--no-textconv','--name-only','-z',*args).split('\x00')
        diff = self._git(path,'diff','--no-ext-diff','--no-textconv','--no-renames',*args)
        return {'files':[n for n in names if n][:1000],'diff':str(sanitize(diff[:200000])),
                'truncated':len(diff)>200000 or len(names)>1000}

    def _state(self,path):
        # Full porcelain includes untracked names; use digest only in persisted preview.
        status = self._git(path,'status','--porcelain=v1','-z','--untracked-files=all')
        changes = self._git(path,'diff','--no-ext-diff','--no-textconv','HEAD','--')
        return self._git(path,'rev-parse','HEAD'),hashlib.sha256((status+changes).encode()).hexdigest(),bool(status)

    def preview(self,project_id,checkpoint_id):
        with self.lock:
            path = self._project(project_id)
            checkpoint = self._record(project_id,checkpoint_id)
            self._safe_tree(path,checkpoint['data']['sha'])
            self.workspace._check_filters(path)
            head,digest,dirty = self._state(path)
            files = self._git(path,'diff','--no-ext-diff','--no-textconv','--name-only','-z',head,checkpoint['data']['sha'],'--').split('\x00')
            data = {'checkpoint_id':checkpoint_id,'sha':checkpoint['data']['sha'],'source_head':head,
                    'state_digest':digest,'dirty':dirty,'files':[n for n in files if n and not self._sensitive(n)][:1000],
                    'strategy':'new_worktree','warning':'Исходные файлы сохраняются. Неотслеживаемые файлы не восстанавливаются.'}
            preview = self.store.put('git_restore',project_id,data)
            return {**preview,'preview_token':preview['id']}

    def restore(self,project_id,checkpoint_id,preview_token,confirmed=False):
        with self.lock:
            if confirmed is not True: raise WorkspaceError('Требуется подтверждение восстановления')
            path = self._project(project_id)
            checkpoint = self._record(project_id,checkpoint_id)
            preview = self.store.get('git_restore',preview_token)
            data = preview['data']
            if preview['project_id'] != project_id or data['checkpoint_id'] != checkpoint_id or data['sha'] != checkpoint['data']['sha']:
                raise WorkspaceError('Preview does not match checkpoint')
            if data.get('result'):
                result=data['result']
                if self._git(Path(result['path']),'rev-parse','HEAD')!=data['sha']:
                    raise WorkspaceError('Восстановленная копия изменилась; создайте новый preview')
                return result
            head,digest,_ = self._state(path)
            if (head,digest) != (data['source_head'],data['state_digest']):
                raise WorkspaceError('Проект изменился. Повторите предварительный просмотр.')
            self._safe_tree(path,data['sha'])
            self.workspace._check_filters(path)
            destination = self.root / '.ai-team' / 'restored' / ('restore_' + uuid.uuid4().hex)
            destination.parent.mkdir(parents=True,exist_ok=True)
            if not destination.resolve().is_relative_to(self.root) or destination.parent.is_symlink():
                raise WorkspaceError('Unsafe restore destination')
            branch = 'codex-restore/' + uuid.uuid4().hex
            self._git(path,'worktree','add','-b',branch,str(destination),data['sha'])
            actual = self._git(destination,'rev-parse','HEAD')
            if actual != data['sha']: raise WorkspaceError('Restored HEAD verification failed')
            result = {'path':str(destination),'branch':branch,'head':actual,'checkpoint_id':checkpoint_id}
            self.store.put('git_restore',project_id,{**data,'result':result},record_id=preview_token,
                           expected_version=preview['version'])
            return result

    def capture_for_run(self,run,role):
        get = (lambda key:run.get(key)) if isinstance(run,dict) else (lambda key:getattr(run,key,None))
        project_id = get('project_id')
        if not project_id: return None
        return self.create(project_id,label=f'Этап: {role}',run_id=get('id'),stage=role,workspace=get('workspace'))

    def _all_records(self, kind, project_id):
        items, offset = [], 0
        while True:
            page = self.store.page(kind,project_id,limit=100,offset=offset)
            items.extend(page['items'])
            if len(items) >= page['total']: return items
            offset += 100
            if offset > 100000: raise WorkspaceError('Слишком много записей для безопасной очистки')

    def _retention_policy(self, project_id):
        key = 'retention_' + hashlib.sha256(project_id.encode()).hexdigest()[:32]
        try: return self.store.get('git_retention_policy',key)['data']
        except KeyError: return {'enabled':False,'keep_latest':None,'max_age_days':None}

    def set_retention_policy(self, project_id, policy):
        with self.lock:
            self._project(project_id)
            if not isinstance(policy,dict) or set(policy)-{'enabled','keep_latest','max_age_days'}:
                raise WorkspaceError('Некорректная политика хранения')
            normalized = {'enabled':policy.get('enabled',False),'keep_latest':policy.get('keep_latest'),
                          'max_age_days':policy.get('max_age_days')}
            if type(normalized['enabled']) is not bool:
                raise WorkspaceError('enabled должен быть boolean')
            for name in ('keep_latest','max_age_days'):
                value=normalized[name]
                if value is not None and (type(value) is not int or not 1<=value<=100000):
                    raise WorkspaceError('Лимиты хранения должны быть положительными целыми')
            if normalized['enabled'] and all(normalized[k] is None for k in ('keep_latest','max_age_days')):
                raise WorkspaceError('Укажите ограничение хранения')
            key = 'retention_' + hashlib.sha256(project_id.encode()).hexdigest()[:32]
            self.store.put('git_retention_policy',project_id,normalized,record_id=key)
            return normalized

    def _retention_inventory(self,project_id,measure=False):
        import json
        from datetime import datetime,timezone,timedelta
        path=self._project(project_id)
        policy=self._retention_policy(project_id)
        checkpoints=self._all_records('git_checkpoint',project_id)
        checkpoints.sort(key=lambda r:(r.get('created_at',''),r['id']),reverse=True)
        restores=self._all_records('git_restore',project_id)
        source=self.store if hasattr(self.store,'runs') else self.store.store
        # Missing history access fails closed: never assume a checkpoint is unreferenced.
        history_available=hasattr(source,'runs')
        runs=source.runs() if history_available else []
        referenced=set()
        for run in runs:
            referenced.update(run.get('git_checkpoints',[]))
        restored={r['data'].get('checkpoint_id') for r in restores if r['data'].get('result')}
        refs=self._git(path,'for-each-ref','--format=%(refname) %(objectname)').splitlines()
        refmap=dict(line.split(' ',1) for line in refs)
        other_sha=[sha for name,sha in refmap.items() if not name.startswith('refs/codex-team/checkpoints/')]
        reachable=set(self._git(path,'rev-list',*other_sha).splitlines()) if other_sha else set()
        sizes={}
        if measure:
            for line in self._git(path,'cat-file','--batch-all-objects','--batch-check=%(objectname) %(objectsize)').splitlines():
                sha,size=line.split(); sizes[sha]=int(size)
        inventory=[]; union=set()
        for index,cp in enumerate(checkpoints):
            data=cp['data']; sha=data['sha']; reasons=[]
            ref='refs/codex-team/checkpoints/'+cp['id']
            if not history_available: reasons.append('История запусков недоступна')
            if data.get('run_id') or cp['id'] in referenced: reasons.append('Связана с историей запуска')
            if cp['id'] in restored: reasons.append('Использована для восстановления')
            if sha in reachable: reasons.append('Достижима из другой ветки или тега')
            if refmap.get(ref)!=sha: reasons.append('Приватная ссылка отсутствует или изменена')
            if not policy['enabled']: reasons.append('Хранение всех точек включено')
            if policy['keep_latest'] is not None and index<policy['keep_latest']:
                reasons.append('Входит в последние сохраняемые точки')
            if policy['max_age_days'] is not None:
                try:
                    created=datetime.fromisoformat(cp['created_at'].replace('Z','+00:00'))
                    if created.tzinfo is None: created=created.replace(tzinfo=timezone.utc)
                    if created>datetime.now(timezone.utc)-timedelta(days=policy['max_age_days']):
                        reasons.append('Срок хранения ещё не истёк')
                except (KeyError,ValueError): reasons.append('Дата создания неизвестна')
            objects=set()
            if measure:
                objects={line.split(' ',1)[0] for line in self._git(path,'rev-list','--objects',sha).splitlines()}
                union.update(objects)
            inventory.append({'id':cp['id'],'label':data.get('label',''),'sha':sha,'version':cp['version'],
                              'protected':bool(reasons),'reasons':reasons,
                              'logical_referenced_bytes':sum(sizes.get(obj,0) for obj in objects) if measure else None})
        fingerprint=hashlib.sha256(json.dumps({'policy':policy,'checkpoints':checkpoints,'refs':refs,
                'runs':runs,'restores':restores},sort_keys=True,default=str).encode()).hexdigest()
        return {'policy':policy,'automatic_deletion':False,'checkpoints':inventory,
                'logical_referenced_bytes':sum(sizes.get(obj,0) for obj in union) if measure else None,
                'size_note':'Логический объём достижимых Git-объектов, включая общую историю. Это не освобождаемое место; GC не запускается.',
                '_fingerprint':fingerprint}

    def retention(self,project_id):
        with self.lock:
            inventory=self._retention_inventory(project_id,measure=True)
            inventory.pop('_fingerprint')
            return inventory

    def retention_preview(self,project_id):
        import time
        with self.lock:
            inventory=self._retention_inventory(project_id)
            candidates=[cp for cp in inventory['checkpoints'] if not cp['protected']]
            data={'fingerprint':inventory['_fingerprint'],'candidates':candidates,
                  'protected':[cp for cp in inventory['checkpoints'] if cp['protected']],
                  'expires_at':time.time()+300,'automatic_deletion':False}
            record=self.store.put('git_retention_preview',project_id,data)
            return {**data,'preview_token':record['id']}

    def retention_confirm(self,project_id,preview_token,confirmed=False):
        import time
        with self.lock:
            if confirmed is not True: raise WorkspaceError('Требуется явное подтверждение очистки')
            preview=self.store.get('git_retention_preview',preview_token)
            if preview['project_id']!=project_id: raise WorkspaceError('Чужой preview')
            data=preview['data']
            if data.get('result'): return data['result']
            if time.time()>data['expires_at']: raise WorkspaceError('Предпросмотр устарел')
            inventory=self._retention_inventory(project_id)
            if inventory['_fingerprint']!=data['fingerprint']:
                raise WorkspaceError('Состояние изменилось. Повторите предпросмотр очистки.')
            path=self._project(project_id); deleted=[]
            for candidate in data['candidates']:
                # Lease protects against concurrent external ref changes. Never GC,
                # reset, remove worktrees or touch any user branch/index/file.
                self._git(path,'update-ref','-d','refs/codex-team/checkpoints/'+candidate['id'],candidate['sha'])
                self.store.delete('git_checkpoint',candidate['id'],expected_version=candidate['version'])
                deleted.append(candidate['id'])
            result={'deleted':deleted,'history_retained':True,'git_gc_run':False}
            self.store.put('git_retention_preview',project_id,{**data,'result':result},record_id=preview_token,
                           expected_version=preview['version'])
            return result
