"""Five-tool HTTP workflow on real temporary Git/SQLite. No model execution."""
import json
import subprocess
import time
from pathlib import Path
import pytest
from test_server import local_app
from test_engine import rig
from codex_team.storage import Store
from codex_team.suite_store import SuiteStore,SuiteConflict


def git(path,*args):
    return subprocess.check_output(['git',*args],cwd=path,text=True).strip()

def project(client,repo):
    git(repo,'config','user.email','fixture@example.com');git(repo,'config','user.name','Fixture')
    (repo/'main.py').write_text('print("hello")\n')
    (repo/'pyproject.toml').write_text('[project]\nname="fixture"\nversion="0.1"\n')
    (repo/'.env').write_text('PRIVATE_SECRET=never-send\n')
    (repo/'.gitignore').write_text('.env\n')
    git(repo,'add','main.py','pyproject.toml','.gitignore');git(repo,'commit','-qm','initial')
    response=client.post('/api/projects',json={'path':str(repo)})
    assert response.status_code==200,response.text
    return response.json()['id']


def test_versioned_storage_restart_conflict_and_tombstone(tmp_path):
    path=tmp_path/'db.sqlite3';db=Store(path);records=SuiteStore(db)
    first=records.put('knowledge','p',{'title':'Русский контекст'})
    updated=records.put('knowledge','p',{'title':'Обновлено'},record_id=first['id'],expected_version=1)
    with pytest.raises(SuiteConflict):records.put('knowledge','p',{},record_id=first['id'],expected_version=1)
    assert updated['version']==2
    assert len(records.history('knowledge',first['id'])['items'])==2
    db.close();db=Store(path);records=SuiteStore(db)
    assert records.get('knowledge',first['id'])['data']['title']=='Обновлено'
    records.delete('knowledge',first['id'],2)
    assert records.page('knowledge','p')['total']==0
    with pytest.raises(KeyError):records.get('knowledge',first['id'])
    with pytest.raises(ValueError):records.put('knowledge','p',{},record_id=first['id'])
    db.close()


def test_five_feature_http_workflow_and_existing_engine(local_app,monkeypatch):
    client,app,root,db,repo=local_app
    pid=project(client,repo)
    assert client.get(f'/api/suite/projects/{pid}/intelligence').json() is None
    scanned=client.post(f'/api/suite/projects/{pid}/intelligence',json={'refresh':True})
    assert scanned.status_code==200,scanned.text
    assert '.env' not in scanned.json()['data']['files']
    assert client.get(f'/api/suite/projects/{pid}/source',params={'path':'.env'}).status_code==400
    fact=client.post(f'/api/suite/projects/{pid}/knowledge',json={'category':'verified_fact','title':'Python main','content':'main.py — точка входа','sources':['main.py']})
    assert fact.status_code==200,fact.text
    spec=client.post('/api/suite/specifications',json={'project_id':pid,'idea':'Исправить main.py и проверить существующие функции и тесты'}).json()
    assert len(spec['data']['sections'])==12
    edited=client.put(f"/api/suite/specifications/{spec['id']}",json={'expected_version':spec['version'],'sections':{**spec['data']['sections'],'Ожидаемое поведение':'Работа без ошибки'}}).json()
    approved=client.post(f"/api/suite/specifications/{spec['id']}/approve",json={'expected_version':edited['version']}).json()
    assert client.post(f"/api/suite/specifications/{spec['id']}/ai",json={'confirmed':False,'expected_version':approved['version']}).status_code==400
    assert client.put(f'/api/suite/projects/{pid}/budget',json={'max_agent_calls':8,'max_total_tokens':40000}).status_code==200
    calls=[]
    def launch(run_id):
        calls.append(run_id)
        return db.run(run_id)
    monkeypatch.setattr(app.state.engine,'launch',launch)
    response=client.post(f"/api/suite/specifications/{spec['id']}/launch",json={'expected_version':approved['version'],'run_options':{'mode':'standard'}})
    assert response.status_code==200,response.text
    run=response.json()
    assert run['max_agent_calls']==8 and run['max_total_tokens']==40000
    assert run['task_specification']=={'id':spec['id'],'version':approved['version']}
    assert run['project_intelligence']['head']==git(repo,'rev-parse','HEAD')
    again=client.post(f"/api/suite/specifications/{spec['id']}/launch",json={'expected_version':approved['version']})
    assert again.status_code==200 and again.json()['id']==run['id'] and len(calls)==1
    cp1=client.post(f'/api/suite/projects/{pid}/checkpoints',json={'label':'до','request_id':'one'})
    assert cp1.status_code==200,cp1.text
    (repo/'main.py').write_text('print("changed")\n')
    cp2=client.post(f'/api/suite/projects/{pid}/checkpoints',json={'label':'после','request_id':'two'})
    assert cp2.status_code==200,cp2.text
    diff=client.get(f'/api/suite/projects/{pid}/checkpoints/compare',params={'from_id':cp1.json()['id'],'to_id':cp2.json()['id']})
    assert diff.status_code==200 and 'changed' in diff.json()['diff']
    preview=client.post(f"/api/suite/checkpoints/{cp1.json()['id']}/preview",json={}).json()
    restored=client.post(f"/api/suite/checkpoints/{cp1.json()['id']}/restore",json={'preview_token':preview['preview_token'],'confirmed':True})
    assert restored.status_code==200,restored.text
    assert (Path(restored.json()['path'])/'main.py').read_text()=='print("hello")\n'
    assert (repo/'main.py').read_text()=='print("changed")\n'
    assert (repo/'.env').read_text()=='PRIVATE_SECRET=never-send\n'
    class Unavailable:
        def available(self,image):return False,'Тест: изоляция недоступна'
    app.state.suite['qa'].runner=Unavailable()
    configuration={'image':'sha256:'+'a'*64,'commands':[{'id':'test','category':'test','argv':['python','-m','unittest'],'required':True}]}
    assert client.put(f'/api/suite/projects/{pid}/qa/config',json=configuration).status_code==200
    qa_preview=client.post(f'/api/suite/projects/{pid}/qa/preview',json={}).json()
    assert qa_preview['available'] is False
    blocked=client.post(f'/api/suite/projects/{pid}/qa',json={'confirmation_token':qa_preview['confirmation_token'],'confirmed':True})
    assert blocked.status_code==200,blocked.text
    for _ in range(100):
        result=client.get('/api/suite/qa/'+blocked.json()['id']).json()
        if result['status']!='RUNNING':break
        time.sleep(.01)
    assert result['status']=='BLOCKED'
    assert 'изоляция' in result['error']
    report=client.get('/api/suite/qa/'+result['id']+'/report')
    assert report.status_code==200 and 'BLOCKED' in report.json()['markdown']
    assert client.get('/suite.js').status_code==200 and client.get('/suite.css').status_code==200
    assert client.get('/api/suite/budget',params={'project_id':pid}).json()['items'][0]['max_total_tokens']==40000
    changed=client.put(f"/api/suite/specifications/{spec['id']}",json={'expected_version':approved['version'],'sections':approved['data']['sections']})
    assert changed.status_code==200
    stale=client.post(f"/api/suite/specifications/{spec['id']}/launch",json={'expected_version':approved['version']})
    assert stale.status_code==400 and len(calls)==1


def test_new_endpoints_retain_local_security_boundaries(local_app):
    client,app,root,db,repo=local_app
    pid=project(client,repo)
    assert client.post(f'/api/suite/projects/{pid}/intelligence',json={'refresh':True},headers={'origin':'http://evil.invalid'}).status_code==403
    assert client.post('/api/suite/specifications',json={'project_id':pid,'idea':'test'},headers={'sec-fetch-site':'cross-site'}).status_code==403
    assert client.get(f'/api/suite/projects/{pid}/source',params={'path':'../outside'}).status_code==400
    assert client.put(f'/api/suite/projects/{pid}/budget',json={'max_agent_calls':0}).status_code==422
    assert client.post(f'/api/suite/projects/{pid}/qa',json={'confirmed':False,'confirmation_token':'fake'}).status_code==400
    assert client.get(f'/api/suite/projects/{pid}/knowledge',params={'limit':100000}).status_code==422


def test_existing_engine_binds_knowledge_budget_and_stage_checkpoints(rig):
    from test_engine import standard_results
    from codex_team.provider import FakeCodexProvider
    from codex_team.intelligence import IntelligenceService
    from codex_team.budget_guardian import BudgetGuardian
    make,repo,root,store=rig
    store.save_project({'id':'suite_project','path':str(repo),'name':'Fixture'})
    intelligence=IntelligenceService(root,store)
    intelligence.analyze('suite_project')
    BudgetGuardian(store).set_project_policy('suite_project',{'max_agent_calls':1,'max_total_tokens':1000})
    provider=FakeCodexProvider(standard_results())
    engine,run=make(provider)
    finished=engine.launch(run['id'],background=False)
    assert finished['state']=='USER_DECISION_REQUIRED'
    assert len(provider.calls)==1
    assert finished['project_intelligence']['head']
    assert 'project_intelligence' in provider.calls[0]['prompt']
    assert len(finished['git_checkpoints'])==1
    records=SuiteStore(store)
    checkpoint=records.get('git_checkpoint',finished['git_checkpoints'][0])
    assert checkpoint['data']['run_id']==run['id']
    assert checkpoint['data']['stage']=='coordinator'
    assert checkpoint['data']['source_workspace']==finished['worktree']
    assert git(repo,'status','--porcelain')==''
