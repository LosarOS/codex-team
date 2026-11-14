"""Native budget export contract. Dialogs mocked; not real WebView2 acceptance."""
import json
import sys
from types import SimpleNamespace
import pytest
from codex_team import desktop, desktop_services


def fixture(tmp_path, monkeypatch, choice=True):
    instance=object.__new__(desktop.DesktopBridge)
    instance.root,instance.ready=tmp_path,True
    calls=[]
    report={'schema_version':1,'models_called':False,'aggregation_scope':'current_page',
            'items':[],'measured_tokens':None,'account_quota':None,'cost':None,'generated_at':'Синтетическая проверка'}
    instance.runtime=SimpleNamespace(url='http://127.0.0.1:4321',request=lambda path:calls.append(path) or report)
    dialogs=[]
    def picker(*args,**kwargs):
        dialogs.append((args,kwargs))
        return [str(tmp_path/'бюджет.json')] if choice else None
    instance.window=SimpleNamespace(get_current_url=lambda:instance.runtime.url+'/',create_file_dialog=picker)
    instance.services=SimpleNamespace(invoke=lambda callback,**kwargs:callback())
    monkeypatch.setitem(sys.modules,'webview',SimpleNamespace(FileDialog=SimpleNamespace(SAVE='save')))
    return instance,calls,report,dialogs


def test_native_budget_fetches_only_fixed_backend_route_and_picker_path(tmp_path,monkeypatch):
    host,calls,report,dialogs=fixture(tmp_path,monkeypatch)
    result=desktop.NativeApi(host).export_budget_report({'project_id':'project_1','date':'2026-11-14','limit':50,'offset':3})
    target=tmp_path/'бюджет.json'
    assert result=={'ok':True,'path':str(target)}
    assert calls==['/api/suite/budget/export?project_id=project_1&date=2026-11-14&limit=50&offset=3']
    assert json.loads(target.read_text(encoding='utf-8'))==report
    assert 'Синтетическая' in target.read_text(encoding='utf-8')
    assert dialogs[0][0]==('save',) and dialogs[0][1]['save_filename']=='codex-team-budget.json'
    assert not list(tmp_path.glob('.codex-budget-*'))


def test_native_budget_cancel_writes_nothing(tmp_path,monkeypatch):
    host,calls,_,_=fixture(tmp_path,monkeypatch,False)
    assert host.export_budget_report({})=={'cancelled':True}
    assert calls and list(tmp_path.iterdir())==[]


@pytest.mark.parametrize('filters',[None,[],{'destination':'evil.json'},{'report':{}},{'project_id':'../other'},
    {'project_id':'p?override=1'},{'project_id':None},{'date':'bad'},{'date':'2026-02-30'},
    {'date':'20260101'},{'limit':True},{'limit':0},{'limit':101},{'offset':-1},{'offset':1.1},{'offset':1000001}])
def test_invalid_native_filters_never_request_or_open_dialog(tmp_path,monkeypatch,filters):
    host,calls,_,dialogs=fixture(tmp_path,monkeypatch)
    assert 'error' in host.export_budget_report(filters)
    assert calls==[] and dialogs==[] and list(tmp_path.iterdir())==[]


@pytest.mark.parametrize('ready,url',[(False,'http://127.0.0.1:4321/'),(True,'https://evil.invalid/')])
def test_native_budget_requires_trusted_ready_host(tmp_path,monkeypatch,ready,url):
    host,calls,_,dialogs=fixture(tmp_path,monkeypatch)
    host.ready=ready;host.window.get_current_url=lambda:url
    assert 'error' in host.export_budget_report({})
    assert calls==[] and dialogs==[]


@pytest.mark.parametrize('name',['budget.exe','budget.txt','budget'])
def test_budget_writer_rejects_non_json(tmp_path,name):
    with pytest.raises(ValueError):desktop_services.save_budget_report(tmp_path/name,{})
    assert list(tmp_path.iterdir())==[]


def test_atomic_budget_failure_preserves_existing_file_and_cleans_temp(tmp_path,monkeypatch):
    host,_,report,_=fixture(tmp_path,monkeypatch)
    target=tmp_path/'бюджет.json';target.write_text('original')
    def fail(*args):raise OSError('disk failure')
    monkeypatch.setattr(desktop_services.os,'replace',fail)
    assert 'error' in host.export_budget_report({})
    assert target.read_text()=='original' and not list(tmp_path.glob('.codex-budget-*'))


def test_budget_writer_rejects_oversized_and_malformed_reports(tmp_path):
    base={'schema_version':1,'models_called':False,'aggregation_scope':'current_page','items':[]}
    for report in [None,[],{},dict(base,items=[{}]*101),dict(base,extra='x'*2000001)]:
        with pytest.raises(ValueError):desktop_services.save_budget_report(tmp_path/'budget.json',report)
    assert list(tmp_path.iterdir())==[]


@pytest.mark.parametrize('response',[None,[],{}, {'schema_version':1,'models_called':True}])
def test_native_budget_rejects_invalid_backend_before_picker(tmp_path,monkeypatch,response):
    host,calls,_,dialogs=fixture(tmp_path,monkeypatch)
    host.runtime.request=lambda path: calls.append(path) or response
    assert 'error' in host.export_budget_report({})
    assert len(calls)==1 and dialogs==[] and list(tmp_path.iterdir())==[]
