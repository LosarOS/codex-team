"""Resume the explicitly authorized real fixture demonstration."""
import json
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from codex_team.storage import Store
from codex_team.engine import Engine
root=Path(__file__).resolve().parents[1]
store=Store(root/".ai-team/team.sqlite3")
engine=Engine(root,store)
run_id=sys.argv[1]
cursor=store.db.execute("SELECT COALESCE(MAX(id),0) FROM events WHERE run_id=?", (run_id,)).fetchone()[0]
try:
    engine.launch(run_id)
    while engine.active:
        for e in store.events(run_id,cursor):
            cursor=e["id"]
            if e["type"] in {"agent_started","agent_completed","repair_requested","run_state","approval_required"}:
                print(e["type"],e["role"],json.dumps(e["payload"],ensure_ascii=False),flush=True)
        time.sleep(1)
    run=store.run(run_id)
    (root/"reports/demo.json").write_text(json.dumps(run,ensure_ascii=False,indent=2),encoding="utf-8")
    (root/"reports/demo.diff").write_text(run.get("diff",""),encoding="utf-8")
    print(json.dumps({k:run.get(k) for k in ['id','state','threads','changed_files','error']},ensure_ascii=False,indent=2))
    if run["state"]!="DONE": raise SystemExit(1)
finally:
    engine.close();store.close()
