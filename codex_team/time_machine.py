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
        env.update(GIT_TERMINAL_PROMPT='0', GIT_PAGER='cat', GIT_AUTHOR_NAME='Codex Team',
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
            if data.get('result'): return data['result']
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
