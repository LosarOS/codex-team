"""Actual application routes and assets; no SDK or repository execution."""
from test_server import local_app


def test_new_feature_assets_are_served_by_production_whitelist(local_app):
    client, *_ = local_app
    for filename in ['task-templates.js', 'run-comparison.js', 'task-templates.css', 'run-comparison.css', 'run-notebook.js', 'run-notebook.css', 'run-replay.js']:
        response = client.get('/' + filename)
        assert response.status_code == 200
        assert response.content
        assert ('javascript' if filename.endswith('.js') else 'text/css') in response.headers['content-type']
        assert response.headers['x-content-type-options'] == 'nosniff'
    assert client.get('/productivity.py').status_code == 404


def test_actual_comparison_route_reads_stored_facts_without_launching(local_app):
    client, app, _, store, _ = local_app
    store.save_run({'id': 'unknown', 'workspace': 'C:\\Проект', 'task': 'First', 'calls': 1, 'usage': []})
    store.save_run({'id': 'zero', 'workspace': 'c:\\проект\\', 'task': 'Second', 'calls': 1,
                    'usage': [{'last': {'totalTokens': 0}}]})
    response = client.get('/api/run-comparison?left=unknown&right=zero')
    assert response.status_code == 200
    data = response.json()
    assert data['comparable_project'] is True
    assert data['left']['measured_tokens'] is None and data['right']['measured_tokens'] == 0
    assert 'incomplete_usage' in data['warnings']
    assert app.state.engine.active == {}
    assert store.events('unknown') == store.events('zero') == []


def test_notebook_routes_filter_whole_history_and_keep_notes_out_of_summaries(local_app):
    client, app, _, store, _ = local_app
    for i in range(25):
        store.save_run({'id': f'run-{i}', 'task': f'Авторизация {i}', 'workspace': '/project', 'state': 'DONE'})
    original = store.run('run-0')
    for run_id in ['run-0', 'run-24']:
        response = client.put(f'/api/runs/{run_id}/notebook', json={
            'expected_revision': 0, 'favorite': True, 'note': 'PRIVATE_NOTE_LITERAL'})
        assert response.status_code == 200
    page = client.get('/api/runs?summary=true&favorite=true&limit=1').json()
    assert page['total'] == 2 and page['items'][0]['id'] == 'run-24'
    assert page['items'][0]['notebook']['favorite'] is True
    assert page['items'][0]['notebook']['has_note'] is True
    assert 'PRIVATE_NOTE_LITERAL' not in str(page)
    second = client.get('/api/runs?summary=true&favorite=true&limit=1&offset=1&q=АВТОРИЗАЦИЯ').json()
    assert second['total'] == 2 and second['items'][0]['id'] == 'run-0'
    assert client.get('/api/runs?summary=true&favorite=true&state=FAILED').json()['total'] == 0
    report = client.get('/api/runs/run-0/report?language=en').json()
    assert report['run_id'] == 'run-0' and 'PRIVATE_NOTE_LITERAL' in report['markdown']
    assert store.run('run-0') == original
    assert app.state.engine.active == {} and store.events('run-0') == []


def test_notebook_uses_existing_same_origin_and_json_boundaries(local_app):
    client, _, _, store, _ = local_app
    store.save_run({'id': 'protected', 'task': 'Task'})
    path = '/api/runs/protected/notebook'
    body = {'expected_revision': 0, 'favorite': True, 'note': 'Untrusted'}
    assert client.put(path, json=body, headers={'origin': 'https://evil.invalid'}).status_code == 403
    assert client.put(path, content='{}', headers={'content-type': 'text/plain'}).status_code == 415
    assert client.get(path).json()['revision'] == 0
    assert client.get('/api/runs/protected/report?language=en', headers={'host': 'evil.invalid'}).status_code == 403


def test_nonempty_literal_note_with_zero_character_keeps_history_indicator(local_app):
    client, _, _, store, _ = local_app
    store.save_run({'id': 'literal-note', 'task': 'Task'})
    note = '\x00Follow-up decision'
    saved = client.put('/api/runs/literal-note/notebook', json={'expected_revision': 0, 'favorite': False, 'note': note})
    assert saved.status_code == 200 and saved.json()['note'] == note
    page = client.get('/api/runs?summary=true').json()
    assert page['items'][0]['notebook']['has_note'] is True
