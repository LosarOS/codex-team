"""Explicit real account test for the production adapter (no mocks)."""
import json
import sys
import threading
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from codex_team.provider import CodexProvider
from codex_team.models import AgentResult, parse_result

root = Path(__file__).resolve().parents[1]
fixture = root / "demo-workspaces/spike"
events = []
provider = CodexProvider(root)
try:
    response = provider.execute({"name":"coordinator", "instructions":"You are Coordinator. Read only marker.txt using native tools. Return PLAN with summary equal to file contents. Do not modify files. Use empty arrays for all unrelated fields.", "permission":"read-only", "model":None, "reasoning_effort":"low"},
                                str(fixture), "Read marker.txt; return requested JSON. Do not use external MCP tools.",
                                AgentResult.model_json_schema(), None,
                                lambda kind, data: events.append({"type":kind,"payload":data}),
                                lambda tid: print("thread",tid,flush=True), threading.Event())
    result = parse_result(response["text"], "coordinator")
    proof = {"auth":"chatgpt", "thread_id":response["thread_id"], "result":result,
             "usage":response["usage"], "events":events}
    (root / "reports/provider-spike.json").write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"thread_id":response["thread_id"], "summary":result["summary"], "event_count":len(events)},ensure_ascii=False))
    if result["summary"].strip() != "codex-team-workspace-ok":
        raise SystemExit("Workspace proof missing")
finally:
    provider.close()
