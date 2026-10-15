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
