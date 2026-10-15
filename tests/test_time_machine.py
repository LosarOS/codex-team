import copy
from pathlib import Path
import subprocess
import pytest
from codex_team.time_machine import TimeMachine
from codex_team.workspace import WorkspaceError


class Records:
    def __init__(self,path): self.path=path; self.records={}; self.store=self
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
