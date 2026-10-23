"""Archive safety and execution boundary tests; these do not emulate Windows acceptance."""
import importlib.util
import json
from pathlib import Path
import stat
import zipfile

import pytest

SPEC = importlib.util.spec_from_file_location('portable_smoke', Path('packaging/smoke_portable.py'))
smoke = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(smoke)


def archive(tmp_path, extra=None):
    target = tmp_path / 'portable.zip'
    with zipfile.ZipFile(target, 'w') as bundle:
        bundle.writestr('CodexTeam/portable.json', json.dumps({'format': 1, 'data_folder': 'data'}))
        bundle.writestr('CodexTeam/CodexTeam.exe', b'synthetic archive fixture, not an executable')
        if extra:
            entry, data = extra
            if isinstance(entry, str):
                info = zipfile.ZipInfo(entry)
                # Preserve intentionally malformed raw names even on Windows,
                # where ZipInfo construction otherwise normalizes backslashes.
                info.filename = entry
                info.orig_filename = entry
            else:
                info = entry
            bundle.writestr(info, data)
    return target


def test_extract_validates_portable_marker_without_running_binary(tmp_path):
    app = smoke.extract_portable(archive(tmp_path), tmp_path / 'извлечено')
    assert app.name == 'CodexTeam' and (app / 'CodexTeam.exe').is_file()
    assert not (app / 'data').exists()


@pytest.mark.parametrize('entry', ['../escape', '/absolute', 'CodexTeam/../escape', 'CodexTeam/drive:stream', r'CodexTeam\escape'])
def test_extract_rejects_unsafe_paths_before_any_extraction(tmp_path, entry):
    target = archive(tmp_path, (entry, 'unsafe fixture'))
    with zipfile.ZipFile(target) as bundle:
        assert bundle.infolist()[-1].orig_filename == entry
    destination = tmp_path / 'extract'
    with pytest.raises(ValueError, match='Unsafe portable archive entry'):
        smoke.extract_portable(target, destination)
    assert not destination.exists()


def test_extract_rejects_link_and_preshipped_user_profile(tmp_path):
    link = zipfile.ZipInfo('CodexTeam/link')
    link.create_system = 3
    link.external_attr = (stat.S_IFLNK | 0o777) << 16
    with pytest.raises(ValueError, match='Unsafe portable archive entry'):
        smoke.extract_portable(archive(tmp_path, (link, '../outside')), tmp_path / 'links')
    with pytest.raises(ValueError, match='pre-existing user data'):
        smoke.extract_portable(archive(tmp_path, ('CodexTeam/data/state', 'fixture')), tmp_path / 'profile')


def test_smoke_refuses_non_disposable_environment_before_writes(tmp_path, monkeypatch):
    monkeypatch.delenv('GITHUB_ACTIONS', raising=False)
    diagnostics = tmp_path / 'logs'
    with pytest.raises(RuntimeError, match='disposable Windows GitHub Actions'):
        smoke.smoke(tmp_path / 'absent.zip', diagnostics, {})
    assert not diagnostics.exists()


def test_rejects_raw_backslash_even_when_windows_reader_normalizes_it(tmp_path, monkeypatch):
    target = archive(tmp_path, (r'CodexTeam\escape', 'raw ZIP fixture'))
    # Reproduce ZipInfo's Windows-only normalization on the Linux test host.
    with monkeypatch.context() as patch:
        patch.setattr(zipfile.os, 'sep', '\\')
        with zipfile.ZipFile(target) as bundle:
            member = bundle.infolist()[-1]
            assert member.filename == 'CodexTeam/escape'
            assert member.orig_filename == r'CodexTeam\escape'
        with pytest.raises(ValueError, match='Unsafe portable archive entry'):
            smoke.extract_portable(target, tmp_path / 'extract')
    assert not (tmp_path / 'extract').exists()
