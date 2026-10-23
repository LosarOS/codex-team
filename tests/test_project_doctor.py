"""Discovery must never be confused with execution or leave the registered project."""
import json
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from codex_team.project_doctor import ProjectDoctor, environment_facts
from codex_team.storage import Store


def git(repo, *args):
    return subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True, text=True).stdout


@pytest.fixture
def doctor(tmp_path):
    repo = tmp_path / 'Проект SHIFT'
    repo.mkdir()
    git(repo, 'init')
    git(repo, 'config', 'user.email', 'test@example.test')
    git(repo, 'config', 'user.name', 'Test')
    files = {
        'SHIFT.slnx': '<Solution><Project Path="src/App.csproj" /></Solution>',
        'global.json': json.dumps({'sdk': {'version': '10.0.100', 'rollForward': 'latestFeature'}}),
        'src/App.csproj': '<Project><PropertyGroup><TargetFramework>net10.0-windows10.0.19041.0</TargetFramework><UseWinUI>true</UseWinUI><RuntimeIdentifier>win-x64</RuntimeIdentifier></PropertyGroup><ItemGroup><PackageReference Include="Microsoft.WindowsAppSDK" /></ItemGroup></Project>',
        'tests/Tests.csproj': '<Project><PropertyGroup><TargetFramework>net10.0</TargetFramework></PropertyGroup><ItemGroup><PackageReference Include="Microsoft.NET.Test.Sdk" /></ItemGroup></Project>',
        'src/packages.lock.json': '{}',
        'packaging/Build-Release.ps1': 'throw "Must never execute"',
        '.github/workflows/release.yml': 'name: Release',
        '.gitignore': 'ignored/\n',
        'credentials/global.json': '{"token":"not-readable"}',
    }
    for name, content in files.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
    git(repo, 'add', '.')
    git(repo, 'commit', '-m', 'fixture')
    store = Store(tmp_path / 'state.db')
    store.save_project({'id': 'shift', 'path': str(repo)})
    environment = lambda: {'os': 'Linux', 'architecture': 'x86_64', 'tools': {}, 'dotnet_sdks': ['10.0.100'], 'windows_sdks': [], 'provenance': 'discovered'}
    yield ProjectDoctor(tmp_path, store, environment), repo, store
    store.close()


def test_discovers_windows_projects_without_claiming_validation(doctor):
    service, repo, _ = doctor
    report = service.inspect('shift')
    assert report['head'] == git(repo, 'rev-parse', 'HEAD').strip()
    assert report['project_type'] == 'windows_dotnet'
    assert report['solutions'][0]['format'] == 'slnx'
    assert report['sdk_requirements'][0]['version'] == '10.0.100'
    app, tests = report['projects']
    assert app['windows'] and app['winui'] and app['lock_file']
    assert tests['test_project'] and not tests['windows']
    checks = {c['id']: c for c in report['checks']}
    assert checks['environment']['status'] == 'unsupported'
    for name in ('source_compilation', 'tests', 'windows_publish', 'installer_smoke', 'interactive_gui', 'release_artifacts'):
        assert checks[name]['status'] == 'not_verified' and checks[name]['evidence'] is None
    assert all(c['provenance'] == 'discovered' for c in report['checks'])
    assert report['build_scripts'] == ['packaging/Build-Release.ps1']
    assert report['workflows'] == ['.github/workflows/release.yml']
    assert ['pwsh', '-NoProfile', '-File', './packaging/Build-Release.ps1'] in [c['argv'] for c in report['recommendations']]


def test_inspection_does_not_write_data_or_execute_tools(doctor, monkeypatch):
    service, repo, store = doctor
    before = {str(p.relative_to(repo)): p.read_bytes() for p in repo.rglob('*') if p.is_file() and '.git' not in p.parts}
    statements = []
    store.db.set_trace_callback(statements.append)
    original = service.intelligence.workspace._git
    calls = []
    def tracked(root, *args, **kwargs):
        calls.append(args)
        return original(root, *args, **kwargs)
    monkeypatch.setattr(service.intelligence.workspace, '_git', tracked)
    service.inspect('shift')
    assert not any(s.lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE', 'CREATE', 'REPLACE')) for s in statements)
    assert all(args[0] in {'rev-parse', 'ls-files', '-c'} for args in calls)
    assert before == {str(p.relative_to(repo)): p.read_bytes() for p in repo.rglob('*') if p.is_file() and '.git' not in p.parts}


@pytest.mark.parametrize('content', ['[', '[]', '{"sdk": []}', '<not-json>'])
def test_invalid_global_json_is_reported_without_hiding_other_projects(doctor, content):
    service, repo, _ = doctor
    (repo / 'global.json').write_text(content)
    report = service.inspect('shift')
    assert len(report['projects']) == 2
    assert any(w['source'] == 'global.json' and w['code'] == 'source_unreadable' for w in report['warnings'])


@pytest.mark.parametrize('content', ['<Project>', '<!DOCTYPE Project [<!ENTITY x SYSTEM "file:///secret">]><Project>&x;</Project>'])
def test_broken_xml_and_entities_are_rejected(doctor, content):
    service, repo, _ = doctor
    (repo / 'src/App.csproj').write_text(content)
    report = service.inspect('shift')
    assert len(report['projects']) == 1
    assert any(w['source'] == 'src/App.csproj' for w in report['warnings'])


def test_untracked_ignored_sensitive_oversized_and_linked_sources_excluded(doctor, tmp_path):
    service, repo, _ = doctor
    (repo / 'untracked.csproj').write_text('<Project/>')
    (repo / 'ignored').mkdir()
    (repo / 'ignored/I.csproj').write_text('<Project/>')
    git(repo, 'add', '-f', 'ignored/I.csproj')
    (repo / 'huge.csproj').write_text('<Project>' + ' ' * 65536 + '</Project>')
    git(repo, 'add', 'huge.csproj')
    outside = tmp_path / 'outside.csproj'
    outside.write_text('<Project><TargetFramework>secret</TargetFramework></Project>')
    try:
        (repo / 'link.csproj').symlink_to(outside)
    except OSError:
        pass  # Windows non-developer accounts cannot create symlinks; other exclusions still run.
    else:
        git(repo, 'add', 'link.csproj')
    report = service.inspect('shift')
    assert len(report['projects']) == 2 and len(report['sdk_requirements']) == 1
    assert 'secret' not in json.dumps(report)


def test_unknown_project_cannot_read_an_arbitrary_path(doctor):
    service, repo, _ = doctor
    with pytest.raises(KeyError):
        service.inspect(str(repo))


def test_inherited_framework_is_unknown_not_a_build_pass(doctor):
    service, repo, _ = doctor
    (repo / 'src/App.csproj').write_text('<Project><Import Project="arbitrary.targets"/><Target Name="Build"><Exec Command="never"/></Target></Project>')
    report = service.inspect('shift')
    assert report['projects'][0]['frameworks'] == []
    assert any(w['code'] == 'framework_not_declared' for w in report['warnings'])


def test_environment_discovery_does_not_invoke_dotnet(monkeypatch, tmp_path):
    executable = tmp_path / 'dotnet'
    executable.write_text('not executable')
    (tmp_path / 'sdk/10.0.402').mkdir(parents=True)
    (tmp_path / 'sdk/not-a-version').mkdir()
    monkeypatch.setattr('codex_team.project_doctor.shutil.which', lambda name: str(executable) if name == 'dotnet' else None)
    result = environment_facts()
    assert result['dotnet_sdks'] == ['10.0.402']
    assert result['provenance'] == 'discovered'


def test_api_is_readonly_and_validates_registered_project(doctor, tmp_path):
    from codex_team.server import create_app
    _, _, store = doctor
    with TestClient(create_app(tmp_path, store=store)) as client:
        response = client.get('/api/projects/shift/doctor')
        assert response.status_code == 200, response.text
        assert response.json()['schema_version'] == 1
        assert client.get('/api/projects/unknown/doctor').status_code == 404
        assert client.post('/api/projects/shift/doctor', json={}).status_code == 405


@pytest.mark.parametrize('name,content', [('SHIFT.slnx', '<NotASolution/>'), ('src/App.csproj', '<NotAProject/>')])
def test_wrong_xml_document_kind_is_not_reported_as_a_solution_or_project(doctor, name, content):
    service, repo, _ = doctor
    (repo / name).write_text(content, encoding='utf-8')
    report = service.inspect('shift')
    assert any(w['source'] == name and w['code'] == 'source_unreadable' for w in report['warnings'])
    assert name not in {p['path'] for p in report['solutions'] + report['projects']}
