"""Replay produces only an editor buffer; it cannot issue security consent."""
import pytest
from test_server import local_app
from codex_team.task_drafts import DraftData


def prepare(client, store, **fields):
    store.save_run({'id':'source', 'task':'  Полная задача\n'+'x'*600, 'workspace':'C:\\Проект', **fields})
    return client.get('/api/runs/source/replay')


def test_replay_reads_full_task_and_original_project_without_side_effects(local_app):
    client, app, _, store, _ = local_app
    response = prepare(client, store, original_workspace='D:\\Исходный проект', worktree='Z:\\temporary',
        mode='deep', pack='custom', specialists=['security'], max_iterations=2, max_agent_calls=12, max_run_duration=600,
        access_level='full-access', confirmed_full_access=True, isolated=False, auto_commit=True,
        max_total_tokens=99999, provider={'api_key':'private'}, instructions=[{'text':'hidden'}])
    assert response.status_code == 200
    body=response.json(); data=body['data']
    assert data['task']==store.run('source')['task'] and len(data['task'])>400
    assert data['workspace']=='D:\\Исходный проект'
    assert data['mode']=='deep' and data['pack']=='custom' and data['specialists']==['security']
    assert data['max_agent_calls']==12 and data['max_iterations']==2 and data['max_run_duration']==600
    assert set(data)==set(DraftData.model_fields)
    assert body['warnings']==['security_reset']
    assert 'provider' not in str(body) and 'hidden' not in str(body)
    assert app.state.engine.active=={} and store.events('source')==[]
    assert client.get('/api/task-draft').json()['draft'] is None
    assert store.run('source')['access_level']=='full-access'


@pytest.mark.parametrize('fields', [dict(mode='unknown'),dict(pack=None),dict(pack='   '),
    dict(specialists='security'),dict(max_iterations=True),dict(max_agent_calls='12'),dict(max_run_duration=-1)])
def test_invalid_saved_options_get_safe_defaults_with_warning(local_app, fields):
    client, _, _, store, _=local_app
    body=prepare(client,store,**fields).json()
    assert 'invalid_settings' in body['warnings']
    key=next(iter(fields));assert body['data'][key]==getattr(DraftData(),key)


@pytest.mark.parametrize('task',[None,42,'','  ','x'*30001],ids=['null','number','empty','spaces','oversized'])
def test_invalid_or_oversized_task_is_never_silently_truncated(local_app,task):
    client, _, _, store, _=local_app
    assert prepare(client,store,task=task).status_code==422


@pytest.mark.parametrize('workspace',[None,42,'','x'*4097],ids=['null','number','empty','oversized'])
def test_missing_project_is_explicit_and_not_replaced_with_worktree(local_app, workspace):
    client, _, _, store, _=local_app
    body=prepare(client,store,workspace=workspace,worktree='C:\\temporary').json()
    assert body['data']['workspace']=='' and 'missing_workspace' in body['warnings']


def test_replay_requires_existing_run_and_local_host(local_app):
    client, _, _, store, _=local_app
    assert client.get('/api/runs/missing/replay').status_code==404
    prepare(client,store)
    assert client.get('/api/runs/source/replay',headers={'host':'evil.invalid'}).status_code==403
