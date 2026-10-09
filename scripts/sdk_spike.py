"""Explicit real integration test; consumes a small amount of Codex allowance."""
import json
import os
from pathlib import Path
from openai_codex import Codex, CodexConfig, Sandbox, ApprovalMode

root = Path(__file__).resolve().parents[1]
fixture = root / "demo-workspaces" / "spike"
fixture.mkdir(parents=True, exist_ok=True)
(fixture / "marker.txt").write_text("codex-team-workspace-ok", encoding="utf-8")
# Block accidental API credentials even if inherited by the host process.
for key in ("OPENAI_API_KEY", "CODEX_API_KEY", "OPENAI_BASE_URL"):
    os.environ.pop(key, None)
config = CodexConfig(cwd=str(fixture), client_name="codex_team_spike", client_title="Codex Team spike",
                     config_overrides=('model_provider="openai"', 'forced_login_method="chatgpt"'))
with Codex(config) as codex:
    account = codex.account()
    data = account.model_dump(mode="json", by_alias=True)
    if not data.get("account") or data["account"].get("type") != "chatgpt":
        raise SystemExit("AUTH_REQUIRED: codex login or codex login --device-auth")
    thread = codex.thread_start(cwd=str(fixture), sandbox=Sandbox.read_only,
                                approval_mode=ApprovalMode.deny_all,
                                developer_instructions="Read only marker.txt in the workspace. Do not modify files.")
    result = thread.run("Read marker.txt and return its exact contents, with no other text.", effort="low")
    proof = {"auth": "chatgpt", "thread_id": thread.id, "workspace": str(fixture),
             "status": str(result.status.value), "result": result.final_response,
             "usage": result.usage.model_dump(mode="json", by_alias=True) if result.usage else None,
             "actions": [i.model_dump(mode="json", by_alias=True) for i in result.items if getattr(i.root, "type", "") != "reasoning"]}
    target = root / "reports" / "sdk-spike.json"
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(proof, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(proof, ensure_ascii=False, indent=2))
    if result.final_response != "codex-team-workspace-ok":
        raise SystemExit("Spike failed: workspace proof missing")
