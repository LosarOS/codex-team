import json
import pytest
from test_server import local_app
from codex_team.secrets import MemorySecretStore


def test_preferences_merge_and_no_implicit_provider_switch(local_app):
    client, _, _, db, _ = local_app
    assert client.post('/api/settings', json={'theme':'dark','notifications':{'task_complete':False}}).status_code == 200
    assert client.post('/api/settings', json={'accent_color':'#abcdef','notifications':{'needs_attention':False}}).status_code == 200
    saved=client.get('/api/settings').json()
    assert saved['theme']=='dark' and saved['notifications']=={'task_complete':False,'needs_attention':False}
    assert saved['execution_backend']=='codex_chatgpt'
    assert client.post('/api/settings',json={'execution_backend':'openai_api'}).status_code==400
    assert client.post('/api/providers/select',json={'provider':'openai_api'}).status_code==400
    assert db.settings().get('execution_backend','codex_chatgpt')=='codex_chatgpt'


def test_invalid_secret_is_never_echoed(local_app):
    client, *_=local_app
    marker='private-marker-123'
    response=client.post('/api/providers/openai/key',json={'key':marker,'unexpected':marker})
    assert response.status_code==422 and marker not in response.text


def test_custom_agent_pack_lifecycle_and_references(local_app):
    client, _, _, _, _=local_app
    agent={'name':'custom-reader','role':'Reader','instructions':'Inspect only','permission':'read-only'}
    assert client.post('/api/agents',json=agent).status_code==200
    assert client.post('/api/agents',json=agent).status_code==400
    pack={'name':'custom-pack','title':'Custom','agents':['coordinator','analyst','custom-reader','developer','qa','reviewer'],'default_mode':'standard'}
    assert client.post('/api/packs',json=pack).status_code==200
    assert client.delete('/api/agents/custom-reader',headers={'content-type':'application/json'}).status_code==400
    assert client.delete('/api/agents/coordinator',headers={'content-type':'application/json'}).status_code==400
    assert client.delete('/api/packs/custom-pack',headers={'content-type':'application/json'}).status_code==200
    assert client.delete('/api/agents/custom-reader',headers={'content-type':'application/json'}).status_code==200


def test_summary_archive_diff_and_notification_preferences(local_app):
    client, _, _, db, _=local_app
    run={'id':'run_rc','state':'DONE','task':'Fixture','workspace':'fixture','mode':'Standard','created_at':'2026-10-10','diff':'one\ntwo\nthree\n','usage':[], 'changed_files':['file.py']}
    db.save_run(run)
    db.event('run_rc','run_state',{'state':'DONE'})
    page=client.get('/api/runs?summary=true&limit=1').json()
    assert page['items'][0]['id']=='run_rc' and 'diff' not in page['items'][0]
    part=client.get('/api/runs/run_rc/diff?offset=1&limit=1').json()
    assert part['diff']=='two\n' and part['has_more']
    client.post('/api/settings',json={'notifications':{'needs_attention':False}})
    assert client.get('/api/desktop/state').json()['notifications'][0]['type']=='completed'
    client.post('/api/settings',json={'notifications':{'task_complete':False}})
    assert not client.get('/api/desktop/state').json()['notifications']
    assert client.post('/api/runs/run_rc/archive',json={}).status_code==200
    assert client.get('/api/runs?summary=true').json()['items']==[]
    assert client.get('/api/runs?summary=true&archived=true').json()['items'][0]['id']=='run_rc'
    assert client.get('/api/runs/run_rc').json()['diff']==run['diff']


def test_product_action_is_durable_and_sdk_grants_not_simulated(local_app):
    client, app, _, db, _=local_app
    run={'id':'run_action','state':'USER_DECISION_REQUIRED','task':'Fixture','workspace':'fixture','mode':'Standard','created_at':'2026-10-10'}
    db.save_run(run)
    card=app.state.engine.actions.product_request('run_action','qa','USER_DECISION_REQUIRED','Review the result')
    response=client.post('/api/actions/'+card['id']+'/resolve',json={'decision':'allow_once'})
    assert response.status_code==400
    assert db.actions('run_action','pending')
    response=client.post('/api/actions/'+card['id']+'/resolve',json={'decision':'stop'})
    assert response.status_code==200
    assert db.run('run_action')['state']=='STOPPED'
    assert not db.actions('run_action','pending')
