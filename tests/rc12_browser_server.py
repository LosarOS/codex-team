"""Disposable synthetic real-backend fixture; forbids live SDK inference."""
import tempfile, shutil, subprocess, json, os
from pathlib import Path
import uvicorn
from codex_team.server import create_app
from codex_team.storage import Store
from codex_team.provider import CodexProvider,FakeCodexProvider
source=Path(__file__).resolve().parents[1];root=Path(tempfile.mkdtemp(prefix='codex-rc12-browser-'))
for name in ['agents','packs']:shutil.copytree(source/name,root/name)
repo=root/'synthetic-project';repo.mkdir();(repo/'main.py').write_text('print("Synthetic RC12 acceptance")\n');(repo/'README.md').write_text('# Synthetic RC12 project\n')
for argv in [['init'],['config','user.name','Synthetic acceptance'],['config','user.email','fixture@example.invalid'],['add','.'],['commit','-qm','Synthetic baseline']]:subprocess.run(['git',*argv],cwd=repo,check=True,capture_output=True)
CodexProvider.account_status=lambda self:{'status':'AUTH_REQUIRED','account':None}
CodexProvider._connect=lambda *a,**k: (_ for _ in ()).throw(AssertionError('No real SDK calls allowed'))
store=Store(root/'fixture.sqlite');store.save_project({'id':'rc12_fixture','path':str(repo),'name':'Synthetic RC12 acceptance'})
app=create_app(root,store,provider_factory=lambda:FakeCodexProvider(connected=False),static_root=source/'codex_team/static')
(root/'manifest.json').write_text(json.dumps({'project':str(repo)}));Path(os.environ.get('RC12_BROWSER_MANIFEST','/workspace/scratch/rc12-browser-root.txt')).write_text(str(root))
uvicorn.run(app,host='127.0.0.1',port=int(os.environ.get('RC12_BROWSER_PORT','8768')),log_level='warning')
