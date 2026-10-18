"""Actual application routes and assets; no SDK or repository execution."""
from test_server import local_app


def test_new_feature_assets_are_served_by_production_whitelist(local_app):
    client, *_ = local_app
    for filename in ['task-templates.js', 'run-comparison.js', 'task-templates.css', 'run-comparison.css']:
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
