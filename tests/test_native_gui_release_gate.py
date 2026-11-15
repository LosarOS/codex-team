"""Mandatory canonical GUI proof. Synthetic contract fixtures, never runtime evidence."""
import json
import zipfile
from pathlib import Path
import pytest
from test_publish_windows_artifact import _valid_artifact_fixture

GUI_GATES=('window_verified','task_form_verified','backend_connection_verified','portable_marker_profile_verified',
           'budget_picker_verified','budget_saved_verified','graceful_quit_verified')


def test_canonical_gui_runs_in_windows_ps_sta_after_backend_before_stage():
    text=Path('.github/workflows/windows-release.yml').read_text()
    before=text.index('./packaging/smoke-installed.ps1')
    gui=text.index('- name: Actual portable WebView2 GUI and native Save smoke')
    stage=text.index('- name: Stage verified downloadable files')
    assert before < gui < stage
    step=text[gui:stage]
    for required in ('WindowsPowerShell\\v1.0\\powershell.exe','-NoProfile -STA',
                     '-File ./packaging/Smoke-DesktopGui.ps1','-SourceCommit $env:GITHUB_SHA',
                     '$LASTEXITCODE -ne 0'):
        assert required in step
    for name in GUI_GATES:assert name in text[stage:]
    assert 'OBSERVED_NATIVE_GUI_SCENARIOS_PASSED' in text[stage:]
    assert '$gui.source_commit -cne $env:GITHUB_SHA' in text[stage:]
    assert '$gui.probe_commit -cne $env:GITHUB_SHA' in text[stage:]
    assert '$gui.owned_process_force_cleanup -isnot [bool]' in text[stage:]
    assert "-notcontains 'sdk_account_calls'" in text[stage:]
    assert 'release-assets/native-gui-proof.json' in text
    assert 'CodexTeam-Native-GUI-Evidence.zip' in text
    assert "Compress-Archive -LiteralPath $guiEvidence" in text
    failure=text.split('- name: Upload failure diagnostics')[1]
    assert '.build-tools/native-gui/native-gui-proof.json' in failure
    assert '.build-tools/native-gui/*.png' in failure
    assert '.build-tools/native-gui/profile-logs' not in text


def test_publication_rejects_missing_native_gui_proof(tmp_path,monkeypatch):
    script,root,*_=_valid_artifact_fixture(tmp_path,monkeypatch)
    exec(script,{})
    (root/'native-gui-proof.json').unlink()
    with pytest.raises(FileNotFoundError):exec(script,{})


@pytest.mark.parametrize('gate',GUI_GATES)
@pytest.mark.parametrize('value',[None,False,'true',1])
def test_publication_rejects_missing_false_or_coerced_gui_gates(tmp_path,monkeypatch,gate,value):
    script,root,*_=_valid_artifact_fixture(tmp_path,monkeypatch)
    gui=json.loads((root/'native-gui-proof.json').read_text())
    if value is None:del gui[gate]
    else:gui[gate]=value
    (root/'native-gui-proof.json').write_text(json.dumps(gui))
    with pytest.raises(AssertionError,match='Missing native GUI release gate: '+gate):exec(script,{})


@pytest.mark.parametrize('field,value',[
    ('status','NOT VERIFIED'),('backend_connection_observed_label','Сервер недоступен'),('backend_connection_observed_label','Проверяем локальный сервер…'),('backend_connection_observed_label',None),('source_commit','b'*40),('probe_commit','b'*40),
    ('owned_process_force_cleanup',True),('owned_process_force_cleanup',None),
    ('owned_gui_backend_processes_remaining',1),('owned_gui_backend_processes_remaining',False),
    ('sdk_account_calls',0),('login_requested',True),('model_execution_requested',True)])
def test_publication_rejects_unverified_scope_or_incomplete_cleanup(tmp_path,monkeypatch,field,value):
    script,root,*_=_valid_artifact_fixture(tmp_path,monkeypatch)
    gui=json.loads((root/'native-gui-proof.json').read_text());gui[field]=value
    (root/'native-gui-proof.json').write_text(json.dumps(gui))
    with pytest.raises(AssertionError):exec(script,{})


@pytest.mark.parametrize('change',['missing','extra','bad_png','different_proof'])
def test_publication_validates_allowlisted_archive_contents(tmp_path,monkeypatch,change):
    script,root,*_=_valid_artifact_fixture(tmp_path,monkeypatch)
    path=root/'CodexTeam-Native-GUI-Evidence.zip'
    with zipfile.ZipFile(path) as z:entries={name:z.read(name) for name in z.namelist()}
    if change=='missing':del entries['native-budget-preview.png']
    if change=='extra':entries['profile-logs/private.log']=b'not allowed'
    if change=='bad_png':entries['native-budget-preview.png']=b'not a screenshot'
    if change=='different_proof':entries['native-gui-proof.json']=b'{}'
    with zipfile.ZipFile(path,'w') as z:
        for name,data in entries.items():z.writestr(name,data)
    with pytest.raises(AssertionError):exec(script,{})


def test_backend_connection_gate_observes_actual_uia_before_dashboard_capture():
    script=Path('packaging/Smoke-DesktopGui.ps1').read_text(encoding='utf-8-sig')
    assert 'backend_connection_verified=$false' in script
    function=script.split('function Wait-BackendConnectionIndicator',1)[1].split('function Invoke-Control',1)[0]
    assert 'AutomationElement]::NameProperty' in function
    assert '$root.FindFirst([Windows.Automation.TreeScope]::Descendants,$condition)' in function
    assert '$node.Current.IsOffscreen' in function
    assert '$stable -ge 3' in function
    assert 'Invoke-RestMethod' not in function
    for healthy in ('Сервер доступен · проверяем Codex…','Сервер доступен · Codex не проверен','Нужен вход','Codex подключён'):
        assert healthy in function
    assert 'Сервер недоступен' not in function and 'Проверяем локальный сервер…' not in function
    observe=script.index('$report.backend_connection_observed_label=Wait-BackendConnectionIndicator $window 60')
    verified=script.index('$report.backend_connection_verified=$true')
    capture=script.index("Capture 'native-dashboard-task-form.png'")
    assert observe < verified < capture
    assert 'sdk_account_calls=$null' in script
