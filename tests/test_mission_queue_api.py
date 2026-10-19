import uuid
from test_server import local_app


def test_queue_api_is_explicit_idempotent_and_inert(local_app):
    client, app, _, store, repo=local_app
    payload={'request':{'workspace':str(repo),'task':'<script>literal</script>\nTOKEN=private fixture','max_agent_calls':2},'client_id':str(uuid.uuid4())}
    response=client.post('/api/mission-queue',json=payload)
    assert response.status_code==200,response.text
    item=response.json();assert item['status']=='pending' and item['run_id'] is None
    assert store.runs()==[] and app.state.engine.active=={}
    assert client.post('/api/mission-queue',json=payload).json()['id']==item['id']
    changed={**payload,'request':{**payload['request'],'task':'Different'}}
    assert client.post('/api/mission-queue',json=changed).status_code==409
    assert client.get('/api/mission-queue/'+item['id']).json()['request']['task']==payload['request']['task']
    assert client.post('/api/mission-queue/start',json={}).status_code==400
    assert client.post('/api/mission-queue/start',json={'confirmed':'yes'}).status_code==422
    assert client.get('/api/mission-queue',headers={'host':'evil.invalid'}).status_code==403
    assert client.post('/api/mission-queue/start',json={'confirmed':True},headers={'origin':'https://evil.invalid'}).status_code==403
    assert store.runs()==[]
    assert client.post('/api/mission-queue/'+item['id']+'/skip',json={}).json()['items'][0]['status']=='skipped'


def test_queue_api_requires_isolation_and_per_task_full_access_consent(local_app):
    client, app, _, store, repo=local_app
    for fields in [{'isolated':False},{'access_level':'full-access'}]:
        response=client.post('/api/mission-queue',json={'client_id':str(uuid.uuid4()),'request':{'workspace':str(repo),'task':'No execution',**fields}})
        assert response.status_code==400,response.text
    assert client.get('/api/mission-queue').json()['items']==[] and store.runs()==[]
    for name in ['mission-queue.js','mission-queue.css']:
        assert client.get('/'+name).status_code==200
