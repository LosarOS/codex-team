"""Exercise the UI's wire contracts against FastAPI and an isolated fake engine."""
from test_server import local_app
import pytest
from codex_team.secrets import MemorySecretStore


@pytest.fixture(autouse=True)
def ui_secret_store(monkeypatch):
    monkeypatch.setattr('codex_team.server.WindowsSecretStore', lambda _: MemorySecretStore())


def test_control_center_wire_contracts(local_app):
    client, app, _, db, _ = local_app
    assert 'id="page-actions"' in client.get('/').text
    preferences = {
        'theme': 'purple-neon', 'accent_color': '#cbb2ff',
        'role_model_defaults': {'developer': {'model': None, 'reasoning_effort': 'high'}},
        'notifications': {'task_complete': True, 'needs_attention': True, 'stage_complete': False},
        'permission_policy': {'network_access': 'ask'},
        'minimize_to_tray': True, 'onboarding_dismissed': True,
    }
    response = client.post('/api/settings', json=preferences)
    assert response.status_code == 200, response.text
    settings = client.get('/api/status').json()['settings']
    assert settings['execution_backend'] == 'codex_chatgpt'
    assert settings['role_model_defaults'] == preferences['role_model_defaults']
    providers = client.get('/api/providers').json()
    assert providers['active'] == 'codex_chatgpt'
    assert isinstance(providers['openai_api']['configured'], bool)
    assert 'api_key' not in providers['openai_api']

    agent = {
        'name': 'ui-reader', 'role': 'Читатель', 'instructions': 'Read only',
        'permission': 'read-only', 'model': None, 'reasoning_effort': None,
        'enabled': True, 'description': 'UI contract', 'can_execute': True,
        'can_network': False, 'enabled_modes': ['standard'],
    }
    response = client.post('/api/agents', json=agent)
    assert response.status_code == 200, response.text
    assert client.put('/api/agents/ui-reader', json={**agent, 'description': 'Edited'}).status_code == 200
    pack = {
        'name': 'ui-pack', 'title': 'UI pack', 'description': 'Read specialist',
        'default_mode': 'standard',
        'agents': ['coordinator', 'analyst', 'ui-reader', 'developer', 'qa', 'reviewer'],
        'specialists': [],
    }
    assert client.post('/api/packs', json=pack).status_code == 200
    assert client.put('/api/packs/ui-pack', json=pack).status_code == 200

    run = {
        'id': 'run_ui_contract', 'state': 'USER_DECISION_REQUIRED', 'task': 'UI only',
        'workspace': 'fixture', 'original_workspace': 'fixture', 'mode': 'standard',
        'created_at': '2026-10-10', 'diff': '+first\n+second\n', 'usage': [],
        'calls': 3, 'iteration': 1, 'max_iterations': 1, 'max_agent_calls': 3,
        'max_run_duration': 120,
    }
    db.save_run(run)
    db.event(run['id'], 'run_state', {'state': run['state']})
    action = app.state.engine.actions.product_request(run['id'], 'qa', 'USER_DECISION_REQUIRED', 'Need a decision')
    pending = client.get('/api/actions?status=pending').json()
    assert action['id'] in [item['id'] for item in pending]
    assert 'stop' in action['allowed_decisions'] and 'allow_once' not in action['allowed_decisions']
    response = client.post('/api/actions/' + action['id'] + '/resolve', json={
        'decision': 'stop', 'answers': {}, 'confirmed': False,
    })
    assert response.status_code == 200, response.text
    page = client.get('/api/runs?summary=true&limit=20&offset=0&archived=true').json()
    assert page['items'][0]['id'] == run['id'] and page['total'] == 1
    events = client.get('/api/runs/' + run['id'] + '/events?after=0&limit=100&meaningful=true').json()
    assert {'items', 'next_cursor', 'has_more'} <= events.keys()
    diff = client.get('/api/runs/' + run['id'] + '/diff?offset=0&limit=1').json()
    assert diff['diff'] == '+first\n' and diff['has_more']
    assert client.post('/api/runs/' + run['id'] + '/archive', json={}).status_code == 200
    assert client.get('/api/runs?summary=true&archived=true').json()['items'][0]['archived']
    assert not client.get('/api/runs?summary=true').json()['items']
    assert client.request('DELETE', '/api/packs/ui-pack', json={}).status_code == 200
    assert client.request('DELETE', '/api/agents/ui-reader', json={}).status_code == 200


def test_every_authored_ui_asset_is_served_by_production_backend(local_app):
    from html.parser import HTMLParser
    class Assets(HTMLParser):
        def __init__(self):
            super().__init__()
            self.paths = []
        def handle_starttag(self, tag, attributes):
            values = dict(attributes)
            if tag == 'script' and values.get('src'):
                self.paths.append(values['src'])
            if tag == 'link' and values.get('rel') == 'stylesheet':
                self.paths.append(values['href'])
    client, *_ = local_app
    markup = Assets()
    markup.feed(client.get('/').text)
    assert '/i18n.js' in markup.paths and '/i18n-catalog.js' in markup.paths
    for asset in [*markup.paths, *[f'/icon-{name}.svg' for name in ('project', 'run', 'action', 'tokens')]]:
        result = client.get(asset)
        assert result.status_code == 200, asset
        assert result.content, asset
        assert 'nosniff' == result.headers['x-content-type-options']
        if asset.endswith('.js'):
            assert 'javascript' in result.headers['content-type']
        elif asset.endswith('.svg'):
            assert 'image/svg+xml' in result.headers['content-type']
    for private in ['/auth.json', '/state.db', '/.env', '/server.py']:
        assert client.get(private).status_code == 404
