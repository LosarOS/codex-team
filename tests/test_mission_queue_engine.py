"""Real queue + Engine integration, with the existing disconnected fake provider."""
import time
import uuid
from test_server import local_app


def test_auth_gate_stops_batch_before_second_real_engine_run(local_app):
    client, app, _, store, repo=local_app
    for text in ['First isolated mission','Must remain pending']:
        response=client.post('/api/mission-queue',json={'client_id':str(uuid.uuid4()),'request':{'workspace':str(repo),'task':text,'mode':'quick'}})
        assert response.status_code==200,response.text
    assert store.runs()==[]
    response=client.post('/api/mission-queue/start',json={'confirmed':True})
    assert response.status_code==200,response.text
    deadline=time.monotonic()+5
    while time.monotonic()<deadline:
        result=client.get('/api/mission-queue').json()
        if result['summary']['state']=='blocked':
            break
        time.sleep(.02)
    assert result['summary']['state']=='blocked'
    assert [item['status'] for item in result['items']]==['blocked','pending']
    first=store.run(result['items'][0]['run_id'])
    assert first['state']=='AUTH_REQUIRED' and first['calls']==0
    assert len(store.runs())==1 and result['items'][1]['run_id'] is None
    assert client.post('/api/mission-queue/start',json={'confirmed':True}).status_code==409
