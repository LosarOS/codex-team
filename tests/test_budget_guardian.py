import pytest
from codex_team.budget_guardian import evaluate, measured_tokens, validate_policy
from test_engine import rig, standard_results
from codex_team.provider import FakeCodexProvider


@pytest.mark.parametrize('bad', [{'max_agent_calls': True}, {'max_agent_calls': 0}, {'max_total_tokens': -1}, {'weekly_quota': 1}, {'max_total_tokens': '10'}])
def test_policy_rejects_invalid_values(bad):
    with pytest.raises(ValueError):
        validate_policy(bad)


def test_unknown_usage_is_not_zero_or_account_quota():
    status = evaluate({'calls': 1, 'max_agent_calls': 4, 'usage': [{}], 'max_total_tokens': 50})
    assert status['measured_tokens'] is None
    assert status['percent']['tokens'] is None
    assert status['account_quota'] is None
    assert status['usage_complete'] is False


def test_camel_snake_and_cached_tokens_not_double_counted():
    assert measured_tokens({'last': {'inputTokens': 10, 'cachedInputTokens': 3, 'outputTokens': 2}}) == 12
    assert measured_tokens({'last': {'total_tokens': 20}}) == 20
    assert measured_tokens({'total': {'totalTokens': 500}}) is None


def test_thresholds_use_observed_user_budget():
    status = evaluate({'calls': 3, 'max_agent_calls': 4, 'max_total_tokens': 100, 'usage': [{'last': {'totalTokens': 90}}]})
    assert status['thresholds'] == {'calls': [50, 75], 'tokens': [50, 75, 90]}
    assert not status['reached']


def test_engine_stops_before_next_call_and_keeps_checkpoint(rig):
    make, repo, app, store = rig
    provider = FakeCodexProvider(standard_results())
    engine, run = make(provider)
    engine.set_budget_policy(run['id'], {'max_total_tokens': 15})
    finished = engine.launch(run['id'], background=False)
    assert finished['state'] == 'USER_DECISION_REQUIRED'
    assert len(provider.calls) == 1
    assert finished['calls'] == 1
    assert finished['checkpoint_git']
    assert evaluate(finished)['measured_tokens'] == 15
    before = [e for e in store.events(run['id']) if e['type'] == 'budget_threshold']
    engine._budget_events(finished)
    after = [e for e in store.events(run['id']) if e['type'] == 'budget_threshold']
    assert before == after
    assert len(before) == 4
    assert store.run(run['id'])['max_total_tokens'] == 15


def test_project_policy_versioned_and_applied_and_dashboard_persisted(rig):
    from codex_team.budget_guardian import BudgetGuardian
    make, repo, app, store = rig
    store.save_project({'id': 'project_1', 'path': str(repo), 'name': 'Project'})
    guardian = BudgetGuardian(store)
    first = guardian.set_project_policy('project_1', {'max_agent_calls': 2, 'max_total_tokens': 100})
    second = guardian.set_project_policy('project_1', {'max_agent_calls': 3, 'max_total_tokens': 200})
    assert second['version'] == first['version'] + 1
    engine, run = make(FakeCodexProvider(standard_results()))
    assert run['max_agent_calls'] == 3
    assert run['max_total_tokens'] == 200
    assert BudgetGuardian(store).project_policy('project_1')['max_total_tokens'] == 200
    dashboard = guardian.dashboard('project_1')
    assert dashboard['total'] == 1
    assert dashboard['items'][0]['measured_tokens'] is None
    assert dashboard['aggregation_scope'] == 'current_page'


def test_explicit_run_budget_overrides_project_default(rig):
    from codex_team.budget_guardian import BudgetGuardian
    make, repo, app, store = rig
    store.save_project({'id': 'project_1', 'path': str(repo), 'name': 'Project'})
    BudgetGuardian(store).set_project_policy('project_1', {'max_agent_calls': 2, 'max_total_tokens': 100})
    _, run = make(FakeCodexProvider(standard_results()), max_agent_calls=5, max_total_tokens=30)
    assert run['max_agent_calls'] == 5
    assert run['max_total_tokens'] == 30


def test_active_budget_change_blocked(rig):
    make, _, _, store = rig
    engine, run = make(FakeCodexProvider(standard_results()))
    engine.active[run['id']] = {}
    try:
        with pytest.raises(ValueError, match='приостановите'):
            engine.set_budget_policy(run['id'], {'max_agent_calls': 10})
    finally:
        engine.active.pop(run['id'])
    assert store.run(run['id'])['max_agent_calls'] == run['max_agent_calls']
