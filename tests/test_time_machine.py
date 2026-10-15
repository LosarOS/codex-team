import copy
from pathlib import Path
import subprocess
import pytest
from codex_team.time_machine import TimeMachine
from codex_team.workspace import WorkspaceError


class Records:
    def __init__(self,path): self.path=path; self.records={}; self.store=self; self.run_records=[]
    def project(self,key):
        if key != 'p': raise KeyError(key)
        return {'path':str(self.path)}
    def get(self,kind,key): return copy.deepcopy(self.records[(kind,key)])
    def put(self,kind,project_id,data,record_id=None,expected_version=None):
        key=record_id or f'record{len(self.records)}'
        old=self.records.get((kind,key))
        if expected_version is not None: assert old['version']==expected_version
        item={'id':key,'kind':kind,'project_id':project_id,'version':old['version']+1 if old else 1,'data':copy.deepcopy(data)}
        self.records[(kind,key)]=item
        return copy.deepcopy(item)
    def runs(self): return self.run_records
    def delete(self,kind,key,expected_version=None):
        assert self.records[(kind,key)]['version']==expected_version
        del self.records[(kind,key)]
    def page(self,kind,project_id,limit=50,offset=0,q=''):
        items=[v for (k,_),v in self.records.items() if k==kind and v['project_id']==project_id and q in str(v)]
        return {'items':items[offset:offset+limit],'total':len(items)}


def git(path,*args):
    return subprocess.check_output(['git',*args],cwd=path,text=True).strip()


@pytest.fixture
def machine(tmp_path):
    repo=tmp_path/'repo'; repo.mkdir()
    git(repo,'init','-q'); git(repo,'config','user.email','test@example.com'); git(repo,'config','user.name','Test')
    (repo/'code.py').write_text('initial\n')
    git(repo,'add','.'); git(repo,'commit','-qm','Initial')
    store=Records(repo)
    return TimeMachine(tmp_path/'app',store),repo,store


def test_dirty_snapshot_keeps_index_branch_and_untracked(machine):
    tm,repo,_=machine
    head=git(repo,'rev-parse','HEAD')
    (repo/'code.py').write_text('staged\n'); git(repo,'add','code.py')
    index=git(repo,'diff','--cached')
    (repo/'code.py').write_text('working\n'); (repo/'untracked.txt').write_text('private')
    cp=tm.create('p',label='Checkpoint',request_id='same')
    assert git(repo,'show',cp['data']['sha']+':code.py')=='working'
    assert git(repo,'rev-parse','HEAD')==head
    assert git(repo,'diff','--cached')==index
    assert git(repo,'ls-tree','--name-only',cp['data']['sha'])=='code.py'
    assert tm.create('p',request_id='same')['id']==cp['id']
    assert git(repo,'rev-parse','refs/codex-team/checkpoints/'+cp['id'])==cp['data']['sha']


def test_restore_new_worktree_confirmation_replay_persistence(machine):
    tm,repo,store=machine
    cp=tm.create('p'); (repo/'code.py').write_text('dirty\n')
    preview=tm.preview('p',cp['id'])
    with pytest.raises(WorkspaceError): tm.restore('p',cp['id'],preview['preview_token'])
    restarted=TimeMachine(tm.root,store)
    result=restarted.restore('p',cp['id'],preview['preview_token'],True)
    assert Path(result['path'],'code.py').read_text()=='initial\n'
    assert (repo/'code.py').read_text()=='dirty\n'
    assert restarted.restore('p',cp['id'],preview['preview_token'],True)==result
    assert git(repo,'branch','--show-current') != result['branch']


def test_preview_invalidated_by_changes_and_foreign_checkpoint(machine):
    tm,repo,store=machine
    cp=tm.create('p'); preview=tm.preview('p',cp['id'])
    (repo/'code.py').write_text('new\n')
    with pytest.raises(WorkspaceError,match='изменился'):
        tm.restore('p',cp['id'],preview['preview_token'],True)
    store.records[('git_checkpoint',cp['id'])]['project_id']='foreign'
    with pytest.raises(WorkspaceError): tm.preview('p',cp['id'])


@pytest.mark.parametrize('filename',['.env','credentials.json','private_key.pem'])
def test_secrets_never_snapshotted(machine,filename):
    tm,repo,_=machine
    (repo/filename).write_text('sensitive')
    git(repo,'add',filename)
    with pytest.raises(WorkspaceError): tm.create('p')
    assert tm.list('p')['total']==0


def test_symlink_and_foreign_workspace_rejected(machine,tmp_path):
    tm,repo,_=machine
    (repo/'linked').symlink_to(repo/'code.py'); git(repo,'add','linked')
    with pytest.raises(WorkspaceError): tm.create('p')
    with pytest.raises(WorkspaceError): tm.create('p',workspace=repo/'..')


def test_compare_and_paging(machine):
    tm,repo,_=machine
    a=tm.create('p',label='first'); (repo/'code.py').write_text('second\n')
    b=tm.create('p',label='second')
    result=tm.compare('p',a['id'],b['id'])
    assert result['files']==['code.py']
    assert '+second' in result['diff']
    assert tm.list('p',limit=1)['total']==2


def test_staged_addition_captured_restored_and_source_index_preserved(machine):
    tm,repo,_=machine
    (repo/'new tracked.py').write_text('staged content\n')
    git(repo,'add','new tracked.py')
    (repo/'new tracked.py').write_text('working content\n')
    (repo/'never-tracked.py').write_text('untracked content\n')
    original_index=(repo/'.git'/'index').read_bytes()
    cp=tm.create('p')
    assert (repo/'.git'/'index').read_bytes()==original_index
    assert git(repo,'show',cp['data']['sha']+':new tracked.py')=='working content'
    assert 'never-tracked.py' not in git(repo,'ls-tree','--name-only',cp['data']['sha'])
    preview=tm.preview('p',cp['id'])
    result=tm.restore('p',cp['id'],preview['preview_token'],True)
    assert Path(result['path'],'new tracked.py').read_text()=='working content\n'
    assert not Path(result['path'],'never-tracked.py').exists()
    assert (repo/'.git'/'index').read_bytes()==original_index


def test_retention_default_protects_all_and_logical_size(machine):
    tm,repo,_=machine
    tm.create('p')
    info=tm.retention('p')
    assert info['automatic_deletion'] is False
    assert info['logical_referenced_bytes']>0
    assert tm.retention_preview('p')['candidates']==[]


def test_retention_manual_confirm_only_index_unchanged_and_idempotent(machine):
    tm,repo,_=machine
    old=tm.create('p'); tm.create('p')
    tm.set_retention_policy('p',{'enabled':True,'keep_latest':1})
    (repo/'code.py').write_text('dirty')
    index=(repo/'.git'/'index').read_bytes(); head=git(repo,'rev-parse','HEAD')
    preview=tm.retention_preview('p')
    assert len(preview['candidates'])==1
    with pytest.raises(WorkspaceError): tm.retention_confirm('p',preview['preview_token'])
    result=tm.retention_confirm('p',preview['preview_token'],True)
    assert len(result['deleted'])==1 and result['git_gc_run'] is False
    assert tm.retention_confirm('p',preview['preview_token'],True)==result
    assert (repo/'code.py').read_text()=='dirty'
    assert (repo/'.git'/'index').read_bytes()==index
    assert git(repo,'rev-parse','HEAD')==head
    assert tm.list('p')['total']==1


@pytest.mark.parametrize('change',['ref','policy','history','expiry'])
def test_retention_stale_protection(machine,change):
    tm,repo,store=machine
    cp=tm.create('p'); tm.create('p')
    tm.set_retention_policy('p',{'enabled':True,'keep_latest':1})
    preview=tm.retention_preview('p')
    candidate=preview['candidates'][0]
    if change=='ref': git(repo,'update-ref','refs/codex-team/checkpoints/'+candidate['id'],git(repo,'rev-parse','HEAD'))
    if change=='policy': tm.set_retention_policy('p',{'enabled':False})
    if change=='history': store.run_records.append({'id':'run','git_checkpoints':[candidate['id']]})
    if change=='expiry': store.records[('git_retention_preview',preview['preview_token'])]['data']['expires_at']=0
    with pytest.raises(WorkspaceError): tm.retention_confirm('p',preview['preview_token'],True)
    assert tm.list('p')['total']==2


def test_retention_protects_runs_restores_and_tagged_points(machine):
    tm,repo,store=machine
    linked=tm.create('p',run_id='old_archived_run')
    restored=tm.create('p'); preview=tm.preview('p',restored['id'])
    tm.restore('p',restored['id'],preview['preview_token'],True)
    tagged=tm.create('p'); git(repo,'tag','keep',tagged['data']['sha'])
    tm.create('p')
    tm.set_retention_policy('p',{'enabled':True,'keep_latest':1})
    assert tm.retention_preview('p')['candidates']==[]


def test_retention_restart_tombstone_history_and_age(tmp_path):
    from codex_team.storage import Store
    from codex_team.suite_store import SuiteStore
    repo=tmp_path/'repository'; repo.mkdir()
    git(repo,'init','-q'); git(repo,'config','user.email','test@example.com'); git(repo,'config','user.name','Test')
    (repo/'file').write_text('content'); git(repo,'add','.'); git(repo,'commit','-qm','Initial')
    database=tmp_path/'state.db'; storage=Store(database)
    storage.save_project({'id':'p','name':'repository','path':str(repo)})
    suite=SuiteStore(storage); tm=TimeMachine(tmp_path/'app',suite)
    old=tm.create('p'); tm.create('p')
    # Retention age is anchored to immutable record creation, not later edits.
    storage.db.execute("UPDATE suite_records SET created_at='2000-01-01T00:00:00+00:00' WHERE id=?",(old['id'],)); storage.db.commit()
    tm.set_retention_policy('p',{'enabled':True,'max_age_days':7})
    preview=tm.retention_preview('p'); assert [cp['id'] for cp in preview['candidates']]==[old['id']]
    storage.close()
    storage=Store(database); tm=TimeMachine(tmp_path/'app',SuiteStore(storage))
    result=tm.retention_confirm('p',preview['preview_token'],True)
    assert result['deleted']==[old['id']]
    assert storage.db.execute('SELECT deleted FROM suite_records WHERE id=?',(old['id'],)).fetchone()[0]==1
    assert storage.db.execute('SELECT count(*) FROM suite_revisions WHERE id=?',(old['id'],)).fetchone()[0]==1
    assert tm.retention_confirm('p',preview['preview_token'],True)==result
    storage.close()
