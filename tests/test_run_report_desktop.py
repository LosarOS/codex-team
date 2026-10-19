"""Native report saving contract; dialogs are faked, never Windows GUI E2E."""
import sys
from pathlib import Path
from types import SimpleNamespace
import pytest
from codex_team import desktop, desktop_services


def bridge(tmp_path, monkeypatch, response=None, choice=True):
    instance = object.__new__(desktop.DesktopBridge)
    instance.root, instance.ready = tmp_path, True
    calls = []
    report = response if response is not None else {'run_id': 'run_1', 'markdown': '# Отчёт\nТекст\n'}
    instance.runtime = SimpleNamespace(url='http://127.0.0.1:4321', request=lambda path: calls.append(path) or report)
    instance.window = SimpleNamespace(get_current_url=lambda: instance.runtime.url+'/',
        create_file_dialog=lambda *args, **kwargs: (str(tmp_path/'отчёт.md'),) if choice else None)
    instance.services = SimpleNamespace(invoke=lambda callback, **kwargs: callback())
    monkeypatch.setitem(sys.modules, 'webview', SimpleNamespace(FileDialog=SimpleNamespace(SAVE='save')))
    return instance, calls


def test_native_report_fetches_own_backend_and_writes_chosen_markdown(tmp_path, monkeypatch):
    instance, calls = bridge(tmp_path, monkeypatch)
    result = desktop.NativeApi(instance).export_run_report('run_1', 'en')
    assert result == {'ok': True, 'path': str(tmp_path/'отчёт.md')}
    assert calls == ['/api/runs/run_1/report?language=en']
    assert (tmp_path/'отчёт.md').read_text() == '# Отчёт\nТекст\n'
    assert not list(tmp_path.glob('.codex-report-*'))


def test_cancelled_native_dialog_does_not_write(tmp_path, monkeypatch):
    instance, _ = bridge(tmp_path, monkeypatch, choice=False)
    assert instance.export_run_report('run_1') == {'cancelled': True}
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('identifier,language', [('../secret','ru'),('run_1','ru&secret=1'),(42,'ru'),('','ru')])
def test_native_export_rejects_unsafe_ids_and_language_before_request(tmp_path, monkeypatch, identifier, language):
    instance, calls = bridge(tmp_path, monkeypatch)
    assert 'error' in instance.export_run_report(identifier, language)
    assert calls == [] and list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('ready,url', [(False,'http://127.0.0.1:4321/'),(True,'https://evil.invalid/')])
def test_native_export_requires_ready_trusted_local_page(tmp_path, monkeypatch, ready, url):
    instance, calls = bridge(tmp_path, monkeypatch)
    instance.ready = ready
    instance.window.get_current_url = lambda: url
    assert 'error' in instance.export_run_report('run_1')
    assert calls == []


@pytest.mark.parametrize('response', [{'run_id':'other','markdown':'x'}, {'run_id':'run_1','markdown':None}, []])
def test_native_export_rejects_malformed_backend_report(tmp_path, monkeypatch, response):
    instance, _ = bridge(tmp_path, monkeypatch, response=response)
    assert 'error' in instance.export_run_report('run_1')
    assert not (tmp_path/'отчёт.md').exists()


@pytest.mark.parametrize('name', ['report.exe', 'report.txt', 'report'])
def test_report_file_restricts_format(tmp_path, name):
    with pytest.raises(ValueError):
        desktop_services.save_run_report(tmp_path/name, '# Report')
    assert not (tmp_path/name).exists()


def test_report_does_not_follow_selected_symlink(tmp_path):
    target = tmp_path/'original.md'; target.write_text('original')
    link = tmp_path/'link.md'
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip('This runner cannot create user symlinks')
    with pytest.raises(ValueError):
        desktop_services.save_run_report(link, 'replacement')
    assert target.read_text() == 'original'


def test_failed_atomic_export_preserves_existing_file_and_removes_temporary(tmp_path, monkeypatch):
    target = tmp_path/'report.md'; target.write_text('original')
    def fail_replace(*args):
        raise OSError('disk or permission failure')
    monkeypatch.setattr(desktop_services.os, 'replace', fail_replace)
    with pytest.raises(OSError):
        desktop_services.save_run_report(target, 'new report')
    assert target.read_text() == 'original'
    assert not list(tmp_path.glob('.codex-report-*'))
