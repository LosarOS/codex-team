import json
from pathlib import Path
import pytest
from test_intelligence import intelligence
from codex_team.task_architect import TaskArchitectService, SECTIONS


def test_draft_edit_approve_and_stale_launch(intelligence):
    intel,_=intelligence
    service=TaskArchitectService(intel.root,intel.store,intel)
    draft=service.create('p','Исправь auth и улучши интерфейс')
    assert set(draft['data']['sections'])==set(SECTIONS)
    with pytest.raises(ValueError): service.launch_text(draft['id'],draft['version'])
    sections=dict(draft['data']['sections']); sections['Цель']='Исправить login'
    saved=service.save(draft['id'],sections,draft['version'])
    approved=service.approve(saved['id'],saved['version'])
    assert 'Исправить login' in service.launch_text(approved['id'],approved['version'])
    edited=service.save(approved['id'],sections,approved['version'])
    with pytest.raises(ValueError): service.launch_text(edited['id'],approved['version'])
    assert TaskArchitectService(intel.root,intel.store).get(edited['id'])['version']==edited['version']


def test_input_validation_and_ai_requires_explicit_chatgpt(intelligence):
    intel,_=intelligence
    service=TaskArchitectService(intel.root,intel.store,intel)
    with pytest.raises(ValueError): service.create('p','x')
    draft=service.create('p','Исправить auth')
    with pytest.raises(ValueError): service.save(draft['id'],{},draft['version'])
    class Provider: backend='openai_api'
    with pytest.raises(ValueError): service.ai_refine(draft['id'],Provider(),confirmed=True,expected_version=1)
    Provider.backend='codex_chatgpt'
    with pytest.raises(ValueError): service.ai_refine(draft['id'],Provider(),confirmed=False,expected_version=1)


def test_ai_fake_is_readonly_structured_and_closes(intelligence,monkeypatch):
    intel,_=intelligence
    service=TaskArchitectService(intel.root,intel.store,intel)
    draft=service.create('p','Исправить авторизацию auth')
    class Fake:
        backend='codex_chatgpt'
        def __init__(self,*args): pass
        def execute(self,agent,workspace,prompt,schema,*args):
            assert agent['permission']=='read-only' and agent['can_execute'] is False
            assert list(Path(workspace).iterdir()) == []
            assert Path(workspace) != intel.project_root('p')
            assert agent['can_network'] is False
            assert schema['additionalProperties'] is False
            return {'text':json.dumps({s:'Уточнено '+s for s in SECTIONS})}
        def close(self): pass
    monkeypatch.setattr('codex_team.provider.CodexProvider',Fake)
    refined=service.ai_refine(draft['id'],Fake(),confirmed=True,expected_version=draft['version'])
    assert refined['data']['sections']['Цель']=='Уточнено Цель'
    assert refined['data']['status']=='draft'


def test_ai_concurrent_request_is_rejected(intelligence):
    intel,_=intelligence
    service=TaskArchitectService(intel.root,intel.store,intel)
    draft=service.create('p','Исправить авторизацию auth')
    class Provider: backend='codex_chatgpt'
    service._ai_lock.acquire()
    try:
        with pytest.raises(ValueError,match='уже выполняется'):
            service.ai_refine(draft['id'],Provider(),confirmed=True,expected_version=draft['version'])
    finally:
        service._ai_lock.release()


@pytest.fixture
def ai_lifecycle(intelligence, monkeypatch):
    import threading
    intel, _ = intelligence
    service = TaskArchitectService(intel.root, intel.store, intel)
    service.AI_TIMEOUT_SECONDS = .08
    service.CLEANUP_WAIT_SECONDS = .01
    draft = service.create('p', 'Исправить авторизацию auth')
    class Fake:
        backend = 'codex_chatgpt'
        execute_entered = threading.Event()
        execute_release = threading.Event()
        interrupt_entered = threading.Event()
        interrupt_release = threading.Event()
        close_entered = threading.Event()
        close_release = threading.Event()
        workspace = None
        error = False
        def __init__(self, *args): pass
        def execute(self, agent, workspace, prompt, schema, *args):
            Fake.workspace = Path(workspace)
            Fake.execute_entered.set()
            assert Fake.execute_release.wait(3)
            if Fake.error:
                raise RuntimeError('provider failure')
            return {'text': json.dumps({s: 'AI '+s for s in SECTIONS})}
        def interrupt(self):
            Fake.interrupt_entered.set()
            assert Fake.interrupt_release.wait(3)
        def close(self):
            Fake.close_entered.set()
            assert Fake.close_release.wait(3)
    monkeypatch.setattr('codex_team.provider.CodexProvider', Fake)
    yield service, draft, Fake
    Fake.execute_release.set(); Fake.interrupt_release.set(); Fake.close_release.set()
    job = service._ai_job
    if job:
        assert job['cleaned'].wait(3)


def test_ai_timeout_keeps_directory_and_blocks_overlap_until_all_operations_end(ai_lifecycle):
    service, draft, Fake = ai_lifecycle
    with pytest.raises(ValueError, match='вовремя'):
        service.ai_refine(draft['id'], Fake(), True, draft['version'])
    assert Fake.workspace.exists()
    assert service.get(draft['id'])['version'] == draft['version']
    assert Fake.interrupt_entered.wait(1) and Fake.close_entered.wait(1)
    with pytest.raises(ValueError, match='уже выполняется'):
        service.ai_refine(draft['id'], Fake(), True, draft['version'])
    Fake.execute_release.set()
    assert service._ai_job['execute_done'].wait(1)
    assert Fake.workspace.exists()  # close and interrupt are still unresolved
    Fake.close_release.set()
    assert service._ai_job['close_done'].wait(1)
    assert Fake.workspace.exists()  # interrupt still owns the cwd
    Fake.interrupt_release.set()
    assert service._ai_job['cleaned'].wait(1)
    assert not Fake.workspace.exists()
    assert service.get(draft['id'])['version'] == draft['version']  # no late save
    assert service.ai_status(draft['id'])['active'] is False


def test_ai_explicit_cancel_returns_without_waiting_for_stuck_execution(ai_lifecycle):
    import threading
    service, draft, Fake = ai_lifecycle
    service.AI_TIMEOUT_SECONDS = 5
    errors = []
    def call():
        try: service.ai_refine(draft['id'], Fake(), True, draft['version'])
        except ValueError as exc: errors.append(str(exc))
    caller = threading.Thread(target=call)
    caller.start()
    assert Fake.execute_entered.wait(1)
    status = service.cancel_ai(draft['id'])
    assert status['cancel_requested'] is True
    service.cancel_ai(draft['id'])  # repeated cancel remains idempotent
    caller.join(1)
    assert not caller.is_alive() and 'отменена' in errors[0]
    assert Fake.workspace.exists()
    assert service.get(draft['id'])['version'] == draft['version']


def test_ai_provider_error_retains_draft_and_waits_for_close(ai_lifecycle):
    service, draft, Fake = ai_lifecycle
    Fake.error = True; Fake.execute_release.set()
    with pytest.raises(ValueError, match='Не удалось'):
        service.ai_refine(draft['id'], Fake(), True, draft['version'])
    assert Fake.workspace.exists()
    assert service.ai_status(draft['id'])['state'] == 'cleanup'
    assert service.get(draft['id'])['version'] == draft['version']
    Fake.close_release.set()
    assert service._ai_job['cleaned'].wait(1)
    assert not Fake.workspace.exists()


def test_ai_result_cannot_overwrite_user_edit(ai_lifecycle):
    import threading
    service, draft, Fake = ai_lifecycle
    service.AI_TIMEOUT_SECONDS = 5
    errors = []
    def call():
        try: service.ai_refine(draft['id'], Fake(), True, draft['version'])
        except ValueError as exc: errors.append(str(exc))
    caller = threading.Thread(target=call); caller.start()
    assert Fake.execute_entered.wait(1)
    sections = dict(draft['data']['sections'], **{'Цель': 'Ручная правка'})
    saved = service.save(draft['id'], sections, draft['version'])
    Fake.execute_release.set(); Fake.close_release.set()
    caller.join(1)
    assert not caller.is_alive() and errors
    assert service.get(draft['id'])['version'] == saved['version']
    assert service.get(draft['id'])['data']['sections']['Цель'] == 'Ручная правка'


def test_ai_shutdown_is_bounded_and_preserves_owned_resources(ai_lifecycle):
    import threading
    import time
    service, draft, Fake = ai_lifecycle
    service.AI_TIMEOUT_SECONDS = 5
    errors = []
    def call():
        try: service.ai_refine(draft['id'], Fake(), True, draft['version'])
        except ValueError as exc: errors.append(str(exc))
    caller = threading.Thread(target=call); caller.start()
    assert Fake.execute_entered.wait(1)
    started = time.monotonic()
    service.close()
    assert time.monotonic() - started < .5
    assert Fake.workspace.exists()
    with pytest.raises(ValueError, match='завершает работу'):
        service.ai_refine(draft['id'], Fake(), True, draft['version'])
    caller.join(1)
    assert not caller.is_alive() and errors
    assert service.get(draft['id'])['version'] == draft['version']


def test_ai_routes_expose_status_cancel_and_do_not_close_provider(intelligence, monkeypatch):
    from types import SimpleNamespace
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from codex_team.suite_api import install_suite
    intel, _ = intelligence
    app = FastAPI()
    install_suite(app, intel.root, intel.store, SimpleNamespace(active=False))
    service = app.state.suite['architect']
    draft = service.create('p', 'Исправить авторизацию auth')
    class Fake:
        backend = 'codex_chatgpt'
        def __init__(self, *args): pass
        def close(self):
            raise AssertionError('Route must not close service-owned lifecycle')
    monkeypatch.setattr('codex_team.suite_api.CodexProvider', Fake)
    monkeypatch.setattr(service, 'ai_refine', lambda *args: {'ok': True})
    client = TestClient(app)
    base = f"/api/suite/specifications/{draft['id']}/ai"
    assert client.post(base, json={'confirmed':True,'expected_version':draft['version']}).json() == {'ok':True}
    assert client.get(base+'/status').json()['active'] is False
    assert client.post(base+'/cancel',json={}).json()['state'] == 'idle'
    assert client.post(base+'/cancel',json={'unexpected':True}).status_code == 422


def test_ai_invalid_json_has_russian_error_and_preserves_draft(ai_lifecycle, monkeypatch):
    service, draft, Fake = ai_lifecycle
    Fake.close_release.set()
    monkeypatch.setattr(Fake, 'execute', lambda *args: {'text': '{invalid json'})
    with pytest.raises(ValueError, match='Codex вернул некорректный формат ТЗ; черновик сохранён'):
        service.ai_refine(draft['id'], Fake(), True, draft['version'])
    assert service.get(draft['id'])['version'] == draft['version']
