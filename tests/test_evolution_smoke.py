"""Source-side exercise of smoke protocol; not a Windows runtime substitute."""
import importlib.util
from pathlib import Path
import urllib.error
import pytest
from test_server import local_app
from test_engine import rig
from test_suite_integration import project

SPEC=importlib.util.spec_from_file_location('smoke_evolution',Path('packaging/smoke_evolution.py'))
smoke=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(smoke)


def test_smoke_protocol_against_real_local_api_and_saved_plan(local_app,monkeypatch):
    client,app,root,store,repo=local_app
    pid=project(client,repo)
    monkeypatch.setattr(app.state.engine,'create',lambda *a,**k:pytest.fail('No run creation permitted'))
    def request(path,method='GET',body=None):
        response=client.request(method,path,json=body)
        if response.status_code>=400:
            raise urllib.error.HTTPError(path,response.status_code,'fixture',None,None)
        return response.json()
    first=smoke.verify(request,pid)
    assert all(first[key] for key in ('evolution_budget_export_verified','evolution_plan_verified','evolution_context_preview_verified','evolution_no_dispatch_verified'))
    repeated=smoke.verify(request,pid,first['evolution_specification_id'])
    assert repeated==first
    assert len(store.runs())==0


def test_smoke_rejects_dependent_prepare_that_silently_succeeds(local_app):
    client,app,root,store,repo=local_app
    pid=project(client,repo)
    def request(path,method='GET',body=None):
        if '/plan/prepare?' in path and 'step_id=dependent' in path:
            return {'execution':'composer_only_no_dispatch'}
        response=client.request(method,path,json=body)
        if response.status_code>=400:
            raise urllib.error.HTTPError(path,response.status_code,'fixture',None,None)
        return response.json()
    with pytest.raises(AssertionError,match='Dependent'):
        smoke.verify(request,pid)


def test_smoke_cli_refuses_owner_or_non_disposable_environment(monkeypatch):
    monkeypatch.delenv('GITHUB_ACTIONS',raising=False)
    with pytest.raises(RuntimeError,match='disposable Windows'):
        smoke.main()
