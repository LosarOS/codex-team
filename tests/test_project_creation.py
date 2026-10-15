import subprocess

import pytest
from fastapi.testclient import TestClient

from codex_team.projects import Projects
from codex_team.storage import Store
from codex_team.server import create_app


@pytest.fixture
def service(tmp_path, monkeypatch):
    monkeypatch.setenv('GIT_CEILING_DIRECTORIES', str(tmp_path.parent))
    monkeypatch.setattr('codex_team.runtimes.preflight', lambda path: {})
    store = Store(tmp_path / 'state.db')
    yield Projects(tmp_path, store), store
    store.close()


def test_create_ready_unicode_project_without_github_or_global_identity(service, tmp_path):
    projects, store = service
    path = tmp_path / 'Новый проект'
    result = projects.create(str(path), 'Мой проект')
    assert result['ready'] and result['head'] and not result['dirty']
    assert result['name'] == 'Мой проект'
    assert store.project(result['id'])['path'] == str(path)
    assert subprocess.check_output(['git', '-C', str(path), 'remote'], text=True) == ''
    assert (path / 'README.md').read_text(encoding='utf-8') == '# Мой проект\n'
    assert not subprocess.run(['git', '-C', str(path), 'config', '--local', 'user.email'], capture_output=True).stdout


def test_existing_files_are_never_overwritten(service, tmp_path):
    projects, store = service
    path = tmp_path / 'existing'
    path.mkdir()
    (path / 'README.md').write_text('Мои данные', encoding='utf-8')
    with pytest.raises(ValueError, match='уже существует'):
        projects.create(str(path), 'Проект')
    assert (path / 'README.md').read_text(encoding='utf-8') == 'Мои данные'
    assert store.projects() == []


def test_repeat_creation_does_not_duplicate_or_reset(service, tmp_path):
    projects, store = service
    path = tmp_path / 'new'
    first = projects.create(str(path), 'Новый')
    with pytest.raises(ValueError):
        projects.create(str(path), 'Новый')
    assert len(store.projects()) == 1
    assert projects.inspect(first['id'])['head'] == first['head']


def test_nested_repository_is_rejected(service, tmp_path):
    projects, _ = service
    parent = tmp_path / 'parent'
    projects.create(str(parent), 'Родитель')
    with pytest.raises(ValueError, match='вне существующего'):
        projects.create(str(parent / 'child'), 'Вложенный')
    assert not (parent / 'child').exists()


def test_create_endpoint_contract(service, tmp_path):
    _, store = service
    app = create_app(tmp_path, store=store)
    with TestClient(app) as client:
        response = client.post('/api/projects/create', json={'name': 'Тест', 'path': str(tmp_path / 'api-project')})
        assert response.status_code == 200, response.text
        assert response.json()['ready']
        duplicate = client.post('/api/projects/create', json={'name': 'Тест', 'path': str(tmp_path / 'api-project')})
        assert duplicate.status_code in (400, 409)
        assert client.post('/api/projects/create', json={'name': 'Тест', 'path': 'relative'}).status_code == 400
