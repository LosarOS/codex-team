"""Bounded synthetic dataset against actual HTTP routes; no provider calls."""
import json
import shutil
import statistics
import tempfile
import time
from pathlib import Path
from fastapi.testclient import TestClient
from codex_team.provider import FakeCodexProvider
from codex_team.secrets import MemorySecretStore
from codex_team.server import create_app
from codex_team.storage import Store


def main():
    source=Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(dir=source/'.local-tmp') as folder:
        root=Path(folder)
        for name in ('agents','packs'):
            shutil.copytree(source/name,root/name)
        db=Store(root/'benchmark.sqlite3')
        large=''.join(f'+line {n:06d} '+('x'*64)+'\n' for n in range(20000))
        rows=[]
        for i in range(1000):
            run={'id':f'run_bench_{i}','state':'DONE','task':f'Benchmark {i}','mode':'standard','workspace':'fixture','created_at':'2026-10-10','results':{'qa':{'summary':'x'*2000}},'usage':[],'changed_files':['file.py'],'diff':large if i==999 else 'x'*4096}
            rows.append((run['id'],json.dumps(run)))
        db.db.executemany('INSERT INTO runs VALUES (?,?)',rows)
        db.db.commit()
        app=create_app(root,db,lambda:FakeCodexProvider(),secret_store=MemorySecretStore())
        timings={}
        with TestClient(app) as client:
            for label,url in [('history_1000','/api/runs?summary=true&limit=20'),('large_diff_20000_lines','/api/runs/run_bench_999/diff?limit=1000')]:
                samples=[]
                for _ in range(5):
                    start=time.perf_counter(); response=client.get(url); samples.append((time.perf_counter()-start)*1000)
                    assert response.status_code==200
                timings[label]={'median_ms':round(statistics.median(samples),2),'max_ms':round(max(samples),2),'samples':5}
        db.close()
    result={'source':'Actual FastAPI routes and SQLite; synthetic 1000-run dataset, 20000-line Diff; no AI calls','timings':timings}
    (source/'reports/performance-data.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result))


if __name__=='__main__':
    main()
