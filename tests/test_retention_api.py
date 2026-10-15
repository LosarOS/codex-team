"""Retention HTTP contracts on disposable Git/SQLite; no model calls."""
from test_server import local_app
from test_suite_integration import project, git


def test_retention_http_confirmation_active_guard_and_idempotency(local_app):
    client,app,root,db,repo=local_app
    pid=project(client,repo); base=f'/api/suite/projects/{pid}/retention'
    assert client.get(base).json()['policy']['enabled'] is False
    for label in ['first','second']:
        assert client.post(f'/api/suite/projects/{pid}/checkpoints',json={'label':label}).status_code==200
    assert client.post(base+'/preview',json={}).json()['candidates']==[]
    assert client.put(base,json={'enabled':True,'keep_latest':1}).status_code==200
    preview=client.post(base+'/preview',json={}).json(); assert len(preview['candidates'])==1
    body={'preview_token':preview['preview_token'],'confirmed':True}
    assert client.post(base+'/confirm',json={**body,'confirmed':False}).status_code==400
    original_active=app.state.engine.active
    app.state.engine.active={'active-fixture-run':object()}
    try:
        response=client.post(base+'/confirm',json=body)
        assert response.status_code==400 and 'активного' in response.json()['detail']
        assert client.get(f'/api/suite/projects/{pid}/checkpoints').json()['total']==2
    finally: app.state.engine.active=original_active
    result=client.post(base+'/confirm',json=body)
    assert result.status_code==200,result.text
    assert len(result.json()['deleted'])==1 and result.json()['git_gc_run'] is False
    assert client.post(base+'/confirm',json=body).json()==result.json()
    assert client.get(f'/api/suite/projects/{pid}/checkpoints').json()['total']==1


def test_retention_http_strict_validation_origin_and_stale_policy(local_app):
    client,app,root,db,repo=local_app
    pid=project(client,repo); base=f'/api/suite/projects/{pid}/retention'
    for invalid in [{'enabled':'true','keep_latest':1},{'enabled':True,'keep_latest':0},
                    {'enabled':True,'keep_latest':True},{'enabled':False,'auto_delete':True}]:
        assert client.put(base,json=invalid).status_code==422
    assert client.put(base,json={'enabled':True}).status_code==400
    assert client.put(base,json={'enabled':True,'keep_latest':1},headers={'origin':'http://evil.invalid'}).status_code==403
    assert client.post(base+'/confirm',json={'preview_token':'missing','confirmed':'true'}).status_code==422
    client.post(f'/api/suite/projects/{pid}/checkpoints',json={})
    client.put(base,json={'enabled':True,'keep_latest':1})
    preview=client.post(base+'/preview',json={}).json()
    client.put(base,json={'enabled':False})
    response=client.post(base+'/confirm',json={'preview_token':preview['preview_token'],'confirmed':True})
    assert response.status_code==400 and 'изменилось' in response.json()['detail']
