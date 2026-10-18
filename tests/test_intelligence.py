import subprocess
import pytest
from codex_team.storage import Store
from codex_team.intelligence import IntelligenceService

@pytest.fixture
def intelligence(tmp_path):
    repo=tmp_path/'repo'; repo.mkdir()
    subprocess.run(['git','init',str(repo)],check=True,capture_output=True)
    subprocess.run(['git','-C',str(repo),'config','user.email','test@example.com'],check=True)
    subprocess.run(['git','-C',str(repo),'config','user.name','Test'],check=True)
    (repo/'pyproject.toml').write_text('[project]\nname="demo"')
    (repo/'src').mkdir(); (repo/'src'/'auth.py').write_text('def login(): pass')
    (repo/'.env').write_text('SECRET=never')
    (repo/'.gitignore').write_text('ignored.txt\n')
    (repo/'ignored.txt').write_text('hidden')
    (repo/'credentials.json').write_text('private')
    (repo/'blob.dat').write_bytes(b'\0binary')
    subprocess.run(['git','-C',str(repo),'add','.'],check=True)
    subprocess.run(['git','-C',str(repo),'add','-f','ignored.txt'],check=True)
    subprocess.run(['git','-C',str(repo),'commit','-m','initial'],check=True,capture_output=True)
    store=Store(tmp_path/'db.sqlite'); store.save_project({'id':'p','path':str(repo)})
    return IntelligenceService(tmp_path,store),repo

def test_index_is_bounded_source_backed_and_cached(intelligence):
    service,repo=intelligence
    first=service.analyze('p')
    assert first['data']['technologies'][0]['name']=='Python'
    files=first['data']['files']
    assert 'src/auth.py' in files
    assert not {'.env','credentials.json','ignored.txt','blob.dat'} & set(files)
    assert service.analyze('p')['id']==first['id']
    (repo/'src'/'auth.py').write_text('def login(): return True')
    assert service.analyze('p')['id'] != first['id']

def test_sources_refuse_untracked_and_secrets(intelligence):
    service,repo=intelligence
    (repo/'new.txt').write_text('not tracked')
    for path in ('.env','../db.sqlite','new.txt','credentials.json'):
        with pytest.raises(ValueError): service.source('p',path)
    assert 'login' in service.source('p','src/auth.py')['content']

def test_knowledge_categories_context_and_restart(intelligence):
    service,repo=intelligence
    with pytest.raises(ValueError): service.save_entry('p','verified_fact','Login','Fact')
    entry=service.save_entry('p','verified_fact','Login','Located here',['src/auth.py'])
    service.save_entry('p','ai_suggestion','Login','unconfirmed hypothesis')
    service.save_entry('p','decision','Login','approved decision',approved=True)
    text=service.context('p','Login auth')
    assert 'Located here' in text and 'approved decision' in text
    assert 'unconfirmed hypothesis' not in text
    restart=IntelligenceService(service.root,service.store)
    assert restart.search('p')['total']==3
    restart.delete_entry(entry['id'],expected_version=entry['version'])
    assert restart.search('p')['total']==2


def test_cached_analysis_does_not_reopen_unchanged_source_files(intelligence, monkeypatch):
    from pathlib import Path
    service, repo = intelligence
    first = service.analyze('p')
    opened = []
    original = Path.open
    def track(path, *args, **kwargs):
        if path.is_relative_to(repo):
            opened.append(path)
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', track)
    assert service.analyze('p')['id'] == first['id']
    assert opened == []
    assert service.analyze('p', refresh=True)['id'] != first['id']
    assert repo/'src'/'auth.py' in opened


def test_same_size_same_mtime_edit_and_consecutive_dirty_changes_invalidate(intelligence):
    import os
    service, repo = intelligence
    first = service.analyze('p')
    path = repo/'src'/'auth.py'
    before = path.stat()
    original = path.read_text()
    path.write_text(original.replace('pass', 'True'))
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    second = service.analyze('p')
    assert second['id'] != first['id']
    before = path.stat()
    path.write_text(original.replace('pass', 'None'))
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    assert service.analyze('p')['id'] != second['id']


def test_index_rename_delete_ignore_and_head_invalidate(intelligence):
    service, repo = intelligence
    def git(*args):
        subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True)
    first = service.analyze('p')
    git('mv', 'src/auth.py', 'src/login.py')
    renamed = service.analyze('p')
    assert renamed['id'] != first['id']
    assert 'src/login.py' in renamed['data']['files']
    assert 'src/auth.py' not in renamed['data']['files']
    (repo/'.gitignore').write_text('ignored.txt\nsrc/login.py\n')
    ignored = service.analyze('p')
    assert 'src/login.py' not in ignored['data']['files']
    git('rm', 'blob.dat')
    deleted = service.analyze('p')
    assert deleted['id'] != ignored['id']
    git('add', '.gitignore')
    staged = service.analyze('p')
    assert staged['id'] != deleted['id']
    git('commit', '-m', 'rename and exclude')
    committed = service.analyze('p')
    assert committed['data']['head'] != first['data']['head']


def test_restart_reuses_persisted_cache_without_content_read(intelligence, monkeypatch):
    service, _ = intelligence
    first = service.analyze('p')
    restarted = IntelligenceService(service.root, service.store)
    def fail(*args, **kwargs):
        raise AssertionError('Cache hit must not rescan content')
    monkeypatch.setattr(restarted, '_files', fail)
    assert restarted.analyze('p')['id'] == first['id']


def test_analysis_never_executes_repository_fsmonitor(intelligence):
    service, repo = intelligence
    marker = repo/'executed'
    script = repo/'monitor.sh'
    script.write_text('#!/bin/sh\ntouch "' + str(marker) + '"\n')
    script.chmod(0o755)
    subprocess.run(['git', '-C', str(repo), 'config', 'core.fsmonitor', str(script)], check=True)
    service.analyze('p')
    assert not marker.exists()


def test_unavailable_change_metadata_hashes_bounded_files_despite_git_clean_cache(intelligence, monkeypatch):
    import os
    import codex_team.intelligence as module
    service, repo = intelligence
    monkeypatch.setattr(module, '_change_time', lambda path, stat: None)
    original_git = service.workspace._git
    def cached_status(root, *args, **kwargs):
        if 'status' in args:
            return {'stdout': '', 'returncode': 0}
        return original_git(root, *args, **kwargs)
    monkeypatch.setattr(service.workspace, '_git', cached_status)
    first = service.analyze('p')
    path = repo/'src'/'auth.py'
    before = path.stat()
    path.write_text(path.read_text().replace('pass', 'True'))
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    second = service.analyze('p')
    assert second['id'] != first['id']
    assert service.analyze('p')['id'] == second['id']


def test_change_metadata_detects_write_with_restored_mtime(tmp_path):
    import os
    from codex_team.intelligence import _change_time
    path = tmp_path/'change.txt'
    path.write_text('AAAA')
    before = path.stat()
    first = _change_time(path, before)
    path.write_text('BBBB')
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    second = _change_time(path, path.stat())
    # A filesystem without reliable change metadata must use the hashing fallback.
    assert first is None or second is None or first != second
