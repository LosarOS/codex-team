import copy
import pytest
from test_engine import rig, standard_results
from codex_team.provider import FakeCodexProvider
from test_server import local_app


class CaptureProvider(FakeCodexProvider):
    def execute(self, agent, *args, **kwargs):
        self.seen.append(copy.deepcopy(agent))
        return super().execute(agent, *args, **kwargs)

    def __init__(self):
        super().__init__(standard_results())
        self.seen = []


def test_full_access_requires_explicit_confirmation_before_creation(rig):
    make, _, _, store = rig
    with pytest.raises(ValueError, match='Подтвердите'):
        make(FakeCodexProvider(), access_level='full-access')
    assert store.runs() == []


@pytest.mark.parametrize('level', ['standard', 'read-only', 'full-access'])
def test_access_reaches_provider_without_escalating_other_roles(rig, level):
    make, _, _, store = rig
    provider = CaptureProvider()
    engine, run = make(provider, access_level=level, confirmed_full_access=level == 'full-access')
    finished = engine.launch(run['id'], background=False)
    assert finished['state'] == 'DONE', finished.get('error')
    developer = next(a for a in provider.seen if a['name'] == 'developer')
    assert developer['access_level'] == level
    if level == 'read-only':
        assert all(a['permission'] == 'read-only' for a in provider.seen)
    if level == 'full-access':
        assert developer['can_execute'] and developer['can_network']
        assert all(a['access_level'] != 'full-access' for a in provider.seen if a['name'] != 'developer')
    assert 'confirmed_full_access' not in store.run(run['id'])


def test_changing_access_preserves_checkpoint_and_usage_and_requires_consent(rig):
    make, _, _, store = rig
    engine, run = make(FakeCodexProvider())
    run.update(state='USER_DECISION_REQUIRED', threads={'developer': 'old-thread'}, usage=[{'total_tokens': 123}], checkpoint_git={'head': 'known'}, stage=2)
    store.save_run(run)
    with pytest.raises(ValueError):
        engine.set_access(run['id'], 'full-access')
    assert store.run(run['id'])['threads'] == {'developer': 'old-thread'}
    changed = engine.set_access(run['id'], 'full-access', True)
    assert changed['threads'] == {}
    assert changed['usage'] == run['usage'] and changed['checkpoint_git'] == run['checkpoint_git']
    assert changed['stage'] == 2 and changed['state'] == 'USER_DECISION_REQUIRED'
    assert store.events(run['id'])[-1]['payload']['previous_threads'] == {'developer': 'old-thread'}


def test_active_and_completed_runs_cannot_change_access(rig):
    make, _, _, store = rig
    engine, run = make(FakeCodexProvider())
    engine.active[run['id']] = {}
    try:
        with pytest.raises(ValueError): engine.set_access(run['id'], 'full-access', True)
    finally:
        engine.active.clear()
    run['state'] = 'DONE'
    store.save_run(run)
    with pytest.raises(ValueError): engine.set_access(run['id'], 'full-access', True)


def test_existing_native_threads_are_refreshed_once_without_deleting_history(rig):
    make, _, _, store = rig
    engine, run = make(FakeCodexProvider(standard_results()))
    run.pop('access_profile_version')
    run['threads'] = {'developer': 'legacy-profile-thread'}
    store.save_run(run)
    finished = engine.launch(run['id'], background=False)
    assert finished['state'] == 'DONE'
    assert finished['threads']['developer'] != 'legacy-profile-thread'
    events = [e for e in store.events(run['id']) if e['type'] == 'access_profile_refreshed']
    assert len(events) == 1
    assert events[0]['payload']['previous_threads']['developer'] == 'legacy-profile-thread'


def test_api_requires_consent_and_does_not_resume_when_changing_access(local_app):
    client, _, _, store, _ = local_app
    store.save_run({'id': 'blocked', 'state': 'USER_DECISION_REQUIRED', 'threads': {}, 'stage': 2, 'calls': 9})
    endpoint = '/api/runs/blocked/control'
    assert client.post(endpoint, json={'action': 'set_access', 'access_level': 'full-access'}).status_code == 400
    response = client.post(endpoint, json={'action': 'set_access', 'access_level': 'full-access', 'confirmed_full_access': True})
    assert response.status_code == 200, response.text
    assert response.json()['state'] == 'USER_DECISION_REQUIRED'
    assert response.json()['calls'] == 9
    assert client.post(endpoint, json={'action': 'resume', 'access_level': 'full-access'}).status_code == 400


def test_explicit_full_access_overrides_old_developer_readonly_preference(rig):
    make, _, _, store = rig
    provider = CaptureProvider()
    engine, run = make(provider, access_level='full-access', confirmed_full_access=True)
    run['agents']['developer'].update(permission='read-only', can_execute=False, can_network=False)
    store.save_run(run)
    assert engine.launch(run['id'], background=False)['state'] == 'DONE'
    developer = next(a for a in provider.seen if a['name'] == 'developer')
    assert developer['permission'] == 'workspace-write' and developer['can_execute'] and developer['can_network']
