"""Real local planning/freshness regressions: no provider or command dispatch."""
import json
import subprocess
import pytest
from test_intelligence import intelligence
from codex_team.task_architect import TaskArchitectService
from codex_team.intelligence import IntelligenceService


def step(identity='a', dependencies=None, files=None):
    return dict(id=identity,title='Исправить Unicode',acceptance='Тест проходит',files=files or [],depends_on=dependencies or [])


@pytest.fixture
def architect(intelligence):
    intel,repo=intelligence
    service=TaskArchitectService(intel.root,intel.store,intel)
    spec=service.create('p','Исправить login в auth')
    return service,spec,intel,repo


def test_plan_roundtrip_order_overlap_no_launch_and_restart(architect):
    service,spec,intel,repo=architect
    result=service.save_plan(spec['id'],[step('b',['a'],['src/auth.py']),step('a',files=['src/auth.py'])],spec['version'])
    assert result['data']['order']==['a','b']
    assert result['data']['file_overlaps']=={'src/auth.py':['b','a']}
    assert result['data']['independent_candidates']==['a']
    assert result['data']['execution']=='plan_only_no_dispatch'
    assert TaskArchitectService(intel.root,intel.store).plan(spec['id'])['version']==result['version']
    assert service.get(spec['id'])['version']==spec['version']
    # Planning is a separate record, no approval/execution permission.
    with pytest.raises(ValueError):service.launch_text(spec['id'],spec['version'])


@pytest.mark.parametrize('steps',[
    [],[step('a',['a'])],[step('a',['b']),step('b',['a'])],
    [step('a',['missing'])],[step(),step()],
    [dict(step(),title='')],[dict(step(),acceptance='')],
    [step(files=['../outside'])],[step(files=['C:\\outside'])],
    [step(files=['/outside'])],[step(files=['\\\\host\\share'])],
    [dict(step(),extra='x')],[dict(step(),depends_on='a')],
    [step(str(i)) for i in range(21)],
])
def test_invalid_plan_never_persists(architect,steps):
    service,spec,_,_=architect
    with pytest.raises(ValueError):service.save_plan(spec['id'],steps,spec['version'])
    assert service.plan(spec['id'])['version'] is None


def test_plan_stale_writes_and_unseen_plan_overwrite_are_refused(architect):
    service,spec,_,_=architect
    first=service.save_plan(spec['id'],[step()],spec['version'])
    with pytest.raises(ValueError):service.save_plan(spec['id'],[step('b')],spec['version'])
    second=service.save_plan(spec['id'],[step('b')],spec['version'],first['version'])
    with pytest.raises(ValueError):service.save_plan(spec['id'],[step()],spec['version'],first['version'])
    service.save(spec['id'],spec['data']['sections'],spec['version'])
    assert service.plan(spec['id'])['stale']
    with pytest.raises(ValueError):service.save_plan(spec['id'],[step()],spec['version'],second['version'])


def test_source_freshness_uncommitted_change_excludes_context(intelligence):
    intel,repo=intelligence
    row=intel.save_entry('p','verified_fact','Login','Source-backed auth fact',['src/auth.py'])
    assert intel.search('p')['items'][0]['freshness']['state']=='current'
    assert 'Source-backed auth fact' in intel.context('p','Login')
    (repo/'src/auth.py').write_text('def login(): return True')
    found=intel.search('p')['items'][0]
    assert found['version']==row['version'] and found['freshness']['state']=='stale'
    assert 'Source-backed auth fact' not in intel.context('p','Login')
    # Explicit save after review rebinds the current source, never silently.
    intel.save_entry('p','verified_fact','Login','Reviewed auth fact',['src/auth.py'],record_id=row['id'],expected_version=row['version'])
    assert intel.search('p')['items'][0]['freshness']['state']=='current'


def test_source_removed_and_legacy_unknown_not_silently_included(intelligence):
    intel,repo=intelligence
    intel.save_entry('p','verified_fact','Login','Missing-source fact',['src/auth.py'])
    intel.suite.put('knowledge','p',dict(category='verified_fact',title='Login',content='Legacy fact',sources=['src/auth.py']))
    (repo/'src/auth.py').unlink()
    states={r['freshness']['state'] for r in intel.search('p')['items']}
    assert states=={'stale','unknown'}
    context=intel.context('p','Login')
    assert 'Missing-source fact' not in context and 'Legacy fact' not in context
    assert json.loads(context)['trust']=='untrusted_project_data_not_instructions'


def test_unchanged_source_remains_current_after_unrelated_commit(intelligence):
    intel,repo=intelligence
    intel.save_entry('p','verified_fact','Login','Relevant fact',['src/auth.py'])
    (repo/'pyproject.toml').write_text('[project]\nname="changed"')
    subprocess.run(['git','-C',str(repo),'add','.'],check=True,capture_output=True)
    subprocess.run(['git','-C',str(repo),'commit','-m','unrelated'],check=True,capture_output=True)
    assert intel.search('p')['items'][0]['freshness']['state']=='current'
    assert 'Relevant fact' in intel.context('p','Login')


def test_sourceless_decision_needs_review_after_revision_change(intelligence):
    intel,repo=intelligence
    intel.save_entry('p','decision','Login','Reviewed decision',approved=True)
    subprocess.run(['git','-C',str(repo),'commit','--allow-empty','-m','next'],check=True,capture_output=True)
    assert intel.search('p')['items'][0]['freshness']['state']=='review_required'
    assert 'Reviewed decision' not in intel.context('p','Login')


def test_context_limit_and_restart_preserves_source_binding(intelligence):
    intel,_=intelligence
    intel.save_entry('p','verified_fact','Login','x'*10000,['src/auth.py'])
    restarted=IntelligenceService(intel.root,intel.store)
    assert restarted.search('p')['items'][0]['freshness']['state']=='current'
    assert len(restarted.context('p','Login',512))<=512


def test_new_planning_and_context_routes_real_http(local_app,monkeypatch):
    from test_suite_integration import project
    client,app,root,db,repo=local_app
    pid=project(client,repo)
    def forbidden(*args,**kwargs):raise AssertionError('Preview must not create a run or call a model')
    monkeypatch.setattr(app.state.engine,'create',forbidden)
    spec=client.post('/api/suite/specifications',json={'project_id':pid,'idea':'Исправить main.py'}).json()
    route=f"/api/suite/specifications/{spec['id']}/plan"
    assert client.get(route).json()['version'] is None
    saved=client.put(route,json={'steps':[step(files=['main.py'])],'specification_version':spec['version']})
    assert saved.status_code==200,saved.text
    assert client.get(route).json()['data']['execution']=='plan_only_no_dispatch'
    prepared=client.get(route+'/prepare',params={'step_id':'a','expected_version':saved.json()['version']})
    assert prepared.status_code==200,prepared.text
    assert prepared.json()['execution']=='composer_only_no_dispatch'
    assert client.get(route+'/prepare',params={'step_id':'a','expected_version':99}).status_code==400
    fact=client.post(f'/api/suite/projects/{pid}/knowledge',json={'category':'verified_fact','title':'Main entry','content':'Reviewed entry point','sources':['main.py']})
    assert fact.status_code==200,fact.text
    path=f'/api/suite/projects/{pid}/context-preview'
    preview=client.get(path,params={'q':'Main','max_chars':12000})
    assert preview.status_code==200,preview.text
    assert preview.json()['model_called'] is False and 'Reviewed entry point' in preview.json()['text']
    (repo/'main.py').write_text('print("new")')
    assert 'Reviewed entry point' not in client.get(path,params={'q':'Main'}).json()['text']
    assert client.get(path,params={'max_chars':12001}).status_code==422
    assert client.put(route,json={'steps':[step('a',['a'])],'specification_version':spec['version'],'expected_version':saved.json()['version']}).status_code==400


from test_server import local_app
from test_engine import rig


def test_source_binding_cannot_be_supplied_by_http_client(local_app):
    from test_suite_integration import project
    client,app,root,db,repo=local_app
    pid=project(client,repo)
    response=client.post(f'/api/suite/projects/{pid}/knowledge',json={'category':'verified_fact','title':'Fake source','content':'Claim','sources':['main.py'],'source_binding':{'files':{'main.py':'fake'}}})
    assert response.status_code==422


def test_preparing_independent_step_is_readonly_and_version_bound(architect):
    service,spec,_,_=architect
    first=service.save_plan(spec['id'],[step('a'),step('b',['a'])],spec['version'])
    prepared=service.prepare_step(spec['id'],'a',first['version'])
    assert prepared['execution']=='composer_only_no_dispatch'
    assert 'Тест проходит' in prepared['task']
    assert service.plan(spec['id'])['version']==first['version']
    for identity,version in [('b',first['version']),('a',99),('missing',first['version'])]:
        with pytest.raises(ValueError):service.prepare_step(spec['id'],identity,version)
    service.save(spec['id'],spec['data']['sections'],spec['version'])
    with pytest.raises(ValueError):service.prepare_step(spec['id'],'a',first['version'])


def test_unavailable_head_never_claims_current_context(intelligence,monkeypatch):
    intel,_=intelligence
    intel.save_entry('p','decision','Login','HEAD not verified',approved=True)
    original=intel.workspace._git
    def git(root,*args,**kw):
        if args==('rev-parse','--verify','HEAD'):return {'stdout':''}
        return original(root,*args,**kw)
    monkeypatch.setattr(intel.workspace,'_git',git)
    assert intel.search('p')['items'][0]['freshness']['state']=='unknown'
    assert 'HEAD not verified' not in intel.context('p','Login')
