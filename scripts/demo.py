"""Real five-thread fixture demo. Explicit invocation consumes Codex allowance."""
import json
import subprocess
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from codex_team.engine import Engine
from codex_team.models import RunRequest
from codex_team.storage import Store

root = Path(__file__).resolve().parents[1]
fixture = root / "demo-workspaces" / ("email-" + str(int(time.time())))
fixture.mkdir(parents=True)
(fixture / "tests").mkdir()
(fixture / "email_utils.py").write_text('def normalize_name(name):\n    return name.strip().lower()\n',encoding="utf-8")
(fixture / "tests/test_existing.py").write_text('import unittest\nfrom email_utils import normalize_name\nclass ExistingTests(unittest.TestCase):\n    def test_normalize(self):\n        self.assertEqual(normalize_name(" ALICE "), "alice")\n',encoding="utf-8")
(fixture / "README.md").write_text('Python stdlib fixture. No network or package installation needed. Tests use unittest.\n',encoding="utf-8")
for args in (["init"], ["add","."], ["-c","user.name=Codex Team Demo","-c","user.email=demo@localhost","commit","-m","Initial fixture"]):
    subprocess.run(["git",*args],cwd=fixture,check=True,capture_output=True)
store=Store(root/".ai-team/team.sqlite3")
engine=Engine(root,store)
python=str(root/".venv/Scripts/python.exe")
task=("Add validate_email(value) to email_utils.py and comprehensive unittest tests. Return bool. "
      "For this pragmatic ASCII validator: reject non-string values, whitespace, missing or repeated @, "
      "empty segments, consecutive/leading/trailing dots in local part, invalid domain labels, "
      "domain without a dot, local part over 64 chars and total length over 254 chars; "
      "accept ordinary addresses and plus-tags. Keep normalize_name compatible. This is not full RFC validation. "
      f"Run actual independent tests using the available interpreter: & '{python}' -B -c <code>. "
      "The code should import sys and unittest, insert the absolute worktree path into sys.path, "
      "discover tests using the absolute worktree/tests path, and exit nonzero if any fail. "
      "Use git -C WORKTREE status/diff and absolute file paths because native Windows restricted read may deny Set-Location. "
      "No dependencies, package installs or network. Inspect only relevant fixture files. "
      "Avoid committing. QA must independently run tests and negative edge probes.")
run=engine.create(RunRequest(workspace=str(fixture),task=task,max_agent_calls=12,max_run_duration=1800))
print("Run",run["id"],"fixture",fixture,flush=True)
try:
    engine.launch(run["id"])
    cursor=0
    while engine.active:
        for event in store.events(run["id"],cursor):
            cursor=event["id"]
            if event["type"] in {"agent_started","agent_completed","run_state","repair_requested","approval_required"}:
                print(event["type"],event["role"],json.dumps(event["payload"],ensure_ascii=False),flush=True)
        time.sleep(1)
    result=store.run(run["id"])
    (root/"reports/demo.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    (root/"reports/demo.diff").write_text(result.get("diff",""),encoding="utf-8")
    print(json.dumps({"id":run["id"],"state":result["state"],"threads":result["threads"],"changed_files":result.get("changed_files"),"error":result["error"]},ensure_ascii=False,indent=2),flush=True)
    if result["state"]!="DONE":
        raise SystemExit(1)
finally:
    engine.close()
    store.close()
