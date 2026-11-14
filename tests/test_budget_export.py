"""Read-only, bounded factual exports; no SDK or provider required."""
import json
import pytest
from codex_team.budget_guardian import BudgetGuardian, measured_tokens
from test_engine import rig
from codex_team.provider import FakeCodexProvider


def test_export_unknown_tokens_privacy_and_zero_model_calls(rig):
    make, repo, _, store = rig
    provider = FakeCodexProvider({})
    _, run = make(provider)
    export = BudgetGuardian(store).export()
    assert export['exported_runs'] == 1
    assert export['items'][0]['id'] == run['id']
    assert export['items'][0]['measured_tokens'] is None
    assert export['measured_tokens'] is None
    assert export['cost'] is export['account_quota'] is None
    assert export['models_called'] is False
    assert not provider.calls
    text = json.dumps(export)
    assert str(repo) not in text and run['task'] not in text
    assert 'usage' not in export['items'][0]


def test_export_is_current_page_and_preserves_partial_and_real_zero(rig):
    make, _, _, store = rig
    _, first = make(FakeCodexProvider({}))
    first.update(calls=1,usage=[{'last':{'totalTokens':0}}]);store.save_run(first)
    _, second = make(FakeCodexProvider({}))
    second.update(calls=2,usage=[{'last':{'totalTokens':7}},{}]);store.save_run(second)
    guardian=BudgetGuardian(store)
    page=guardian.export(limit=1)
    assert page['aggregation_scope']=='current_page'
    assert page['total_matching']==2 and page['exported_runs']==1
    assert page['measured_tokens']==7 and page['usage_complete'] is False
    page=guardian.export(limit=1,offset=1)
    assert page['measured_tokens']==0 and page['usage_complete'] is True
    empty=guardian.export(offset=10)
    assert empty['items']==[] and empty['measured_tokens'] is None
    assert empty['usage_complete'] is False


@pytest.mark.parametrize('date',['2026-02-30','2026-1-01','today','20260101'])
def test_export_rejects_invalid_or_ambiguous_dates(rig,date):
    with pytest.raises(ValueError,match='YYYY-MM-DD'):
        BudgetGuardian(rig[3]).export(date=date)


def test_malformed_usage_entry_is_unknown():
    for entry in [None,1,'bad',[]]:
        assert measured_tokens(entry) is None

from test_server import local_app


def test_export_endpoint_bounded_read_only_and_invalid_filters(local_app,monkeypatch):
    client, app, _, store, _ = local_app
    monkeypatch.setattr(app.state.engine,'launch',lambda *a,**k: pytest.fail('Export must not launch'))
    before=store.runs()
    response=client.get('/api/suite/budget/export',params={'limit':1,'offset':5,'date':'2026-11-14'})
    assert response.status_code==200,response.text
    report=response.json()
    assert report['offset']==5 and report['limit']==1 and report['exported_runs']==0
    assert report['filters']['date_utc']=='2026-11-14'
    assert report['usage_complete'] is False
    assert store.runs()==before
    assert client.get('/api/suite/budget/export?limit=201').status_code==422
    assert client.get('/api/suite/budget/export?date=bad').status_code==400
    assert client.get('/api/suite/budget/export?project_id=absent').status_code==404


def test_export_applies_project_and_utc_day_without_mutation(rig):
    make, repo, _, store = rig
    store.save_project({'id':'export_project','path':str(repo),'name':'Fixture'})
    _, first=make(FakeCodexProvider({}))
    first['created_at']='2026-11-13T23:59:59+00:00';store.save_run(first)
    _, second=make(FakeCodexProvider({}))
    second['created_at']='2026-11-14T00:00:00+00:00';store.save_run(second)
    result=BudgetGuardian(store).export('export_project','2026-11-14')
    assert result['total_matching']==1 and result['items'][0]['id']==second['id']
    assert result['filters']=={'project_id':'export_project','date_utc':'2026-11-14'}
    assert store.run(first['id'])['created_at']==first['created_at']


def test_export_corrupt_entry_keeps_unknown_and_valid_observations(rig):
    make, _, _, store=rig
    _,run=make(FakeCodexProvider({}))
    run.update(calls=2,usage=[None,{'last':{'totalTokens':5}}]);store.save_run(run)
    result=BudgetGuardian(store).export()
    assert result['measured_tokens']==5 and result['usage_complete'] is False
