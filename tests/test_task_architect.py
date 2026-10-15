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
