import importlib.util
import json
from pathlib import Path
from zipfile import ZipFile

import pytest
from codex_team.desktop_runtime import configure_bundled_tools

spec = importlib.util.spec_from_file_location('release_archives', Path(__file__).parents[1] / 'packaging/archive.py')
archive = importlib.util.module_from_spec(spec)
spec.loader.exec_module(archive)


def bundle(root):
    app=root/'dist/CodexTeam';app.mkdir(parents=True)
    (app/'CodexTeam.exe').write_bytes(b'fake-pe-for-archive-contract')
    (app/'НАЧАЛО.txt').write_text('Инструкция',encoding='utf-8')
    (app/'Обновить.cmd').write_bytes(b'updater-fixture')
    (app/'Update.ps1').write_bytes(b'updater-fixture')
    (root/'installer').mkdir();(root/'installer/CodexTeam-Setup-x64.exe').write_bytes(b'installer-fixture')
    (root/'packaging').mkdir()
    return app


def test_setup_and_portable_archives_have_separate_profiles_and_checksums(tmp_path):
    bundle(tmp_path)
    result=archive.create_archives(tmp_path)
    assert len(result)==3
    with ZipFile(tmp_path/'dist/CodexTeam-Setup-x64.zip') as z:
        assert set(z.namelist())=={'CodexTeam-Setup-x64.exe','INSTALL-WINDOWS.txt','Обновить.cmd','Update.ps1'}
    with ZipFile(tmp_path/'dist/CodexTeam-Portable-x64.zip') as z:
        assert json.loads(z.read('CodexTeam/portable.json'))['data_folder']=='data'
    assert not (tmp_path/'dist/CodexTeam/portable.json').exists()
    assert len((tmp_path/'dist/SHA256SUMS.txt').read_text().splitlines())==3


@pytest.mark.parametrize('secret',['auth.json','.env','.ai-team/team.sqlite3'])
def test_release_archive_refuses_user_data(tmp_path,secret):
    app=bundle(tmp_path);file=app/secret;file.parent.mkdir(parents=True,exist_ok=True);file.write_text('private')
    with pytest.raises(ValueError,match='credentials'):archive.create_archives(tmp_path)
    assert not (tmp_path/'dist/CodexTeam-Setup-x64.zip').exists()


def test_release_archive_refuses_linked_external_content(tmp_path):
    app=bundle(tmp_path);external=tmp_path/'private';external.write_text('private')
    try:(app/'link').symlink_to(external)
    except OSError:pytest.skip('Symlink creation unavailable')
    with pytest.raises(ValueError,match='Linked'):archive.create_archives(tmp_path)


def test_bundled_git_is_process_local_and_idempotent(tmp_path):
    exe=tmp_path/'runtime/git/cmd/git.exe';exe.parent.mkdir(parents=True);exe.write_bytes(b'git')
    environment={'PATH':'existing-path'}
    assert configure_bundled_tools(tmp_path,environment,True)==exe
    configure_bundled_tools(tmp_path,environment,True)
    assert environment['PATH'].count(str(exe.parent))==1
    assert environment['PATH'].endswith('existing-path')
    assert configure_bundled_tools(tmp_path,{},False) is None


def test_frozen_install_missing_git_reports_reinstall(tmp_path):
    with pytest.raises(RuntimeError,match='установите'):configure_bundled_tools(tmp_path,{},True)
