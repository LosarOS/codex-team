"""Real same-origin API boundaries; no SDK or model execution."""
import sqlite3
from test_server import local_app


def test_health_reports_failed_database_without_leaking_exception(local_app):
    client, _, _, store, _ = local_app
    original = store.db
    class BrokenDatabase:
        def execute(self, *args):
            raise sqlite3.OperationalError('private-database-path-and-secret')
    store.db = BrokenDatabase()
    try:
        response = client.get('/health')
    finally:
        store.db = original
    assert response.status_code == 503
    assert response.json()['status'] == 'degraded'
    assert response.json()['checks']['database'] is False
    assert 'private-database' not in response.text


def test_health_reports_missing_git_as_unavailable(local_app, monkeypatch):
    import shutil
    client, *_ = local_app
    monkeypatch.setattr(shutil, 'which', lambda _: None)
    response = client.get('/health')
    assert response.status_code == 503
    assert response.json()['checks']['git'] is False
    assert response.json()['checks']['database'] is True


def test_draft_is_mounted_and_keeps_same_origin_security(local_app):
    client, app, _, store, _ = local_app
    assert client.get('/api/task-draft').json() == {'revision': 0, 'draft': None}
    payload = {'expected_revision': 0, 'data': {'task': 'Локальный черновик', 'workspace': 'C:\\Проект'}}
    assert client.put('/api/task-draft', json=payload, headers={'origin': 'https://evil.invalid'}).status_code == 403
    assert client.put('/api/task-draft', json=payload, headers={'host': 'evil.invalid'}).status_code == 403
    assert client.get('/api/task-draft', headers={'origin': 'https://evil.invalid'}).status_code == 403
    response = client.put('/api/task-draft', json=payload)
    assert response.status_code == 200
    assert response.json()['draft']['data']['task'] == 'Локальный черновик'
    assert store.runs() == [] and app.state.engine.active == {}
    assert client.put('/api/task-draft', json=payload).status_code == 409
    assert client.request('DELETE', '/api/task-draft?expected_revision=1', json={}).status_code == 200
    assert client.get('/api/task-draft').json() == {'revision': 2, 'draft': None}
