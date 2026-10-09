import threading
import tomllib
import fnmatch
import subprocess
from types import SimpleNamespace

import pytest

import codex_team.provider as module
from codex_team.provider import CodexProvider, ProviderError, config_for
from codex_team.evidence import successful_test_execution


@pytest.mark.parametrize("permission,access", [("read-only", "read"), ("workspace-write", "write")])
def test_config_enforces_chatgpt_scoped_permissions_and_no_credentials(tmp_path, monkeypatch, permission, access):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-live-not-used")
    monkeypatch.setenv("CODEX_API_KEY", "private")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://private.invalid")
    config = config_for(str(tmp_path), {"permission": permission})
    parsed = {}
    for override in config.config_overrides:
        # Each override is a complete TOML assignment. Check actual parseability.
        parsed.update(tomllib.loads(override))
        # CLI override keys are literal dotted paths. Special keys stay inside values.
        lhs = override.split("=", 1)[0]
        assert '"' not in lhs and "'" not in lhs and ":" not in lhs and "\\" not in lhs
    assert parsed["model_provider"] == "openai"
    assert parsed["forced_login_method"] == "chatgpt"
    assert config.env == {"OPENAI_API_KEY": "", "CODEX_API_KEY": "", "OPENAI_BASE_URL": ""}
    filesystem = next(tomllib.loads(x)["permissions"]["codex-team"]["filesystem"]
                      for x in config.config_overrides if ".filesystem=" in x)
    assert filesystem[str(tmp_path.resolve())] == access
    assert filesystem[":minimal"] == "read"
    for secret in (".env", ".aws", ".codex", ".ssh"):
        assert filesystem[str(tmp_path / secret)] == "deny"
    assert 'permissions.codex-team.network.enabled=false' in config.config_overrides
    assert 'features.apps=false' in config.config_overrides
    assert 'features.multi_agent=false' in config.config_overrides


class StubClient:
    account_type = "chatgpt"
    notifications = []
    instances = []

    def __init__(self, config, approval_handler):
        self.config = config
        self.approval_handler = approval_handler
        self.closed = False
        self.started_threads = []
        self.resumed_threads = []
        self.interruptions = []
        self.steers = []
        self.events = list(type(self).notifications)
        type(self).instances.append(self)

    def start(self): pass
    def initialize(self): pass
    def close(self): self.closed = True
    def __enter__(self): return self
    def __exit__(self, *args): self.close()
    def account_read(self, params): return {"account": {"type": self.account_type}}
    def request(self, method, params, response_model):
        assert method == "config/read"
        return SimpleNamespace(root={"config": {"mcp_servers": {"remote": {"enabled": True}}}})
    def thread_start(self, params):
        self.started_threads.append(params)
        return SimpleNamespace(thread=SimpleNamespace(id="new-thread"))
    def thread_resume(self, thread_id, params):
        self.resumed_threads.append((thread_id, params))
        return SimpleNamespace(thread=SimpleNamespace(id=thread_id))
    def turn_start(self, thread_id, prompt, params):
        self.turn_params = params
        return SimpleNamespace(turn=SimpleNamespace(id="turn-1"))
    def next_turn_notification(self, turn_id): return self.events.pop(0)
    def turn_interrupt(self, thread_id, turn_id): self.interruptions.append((thread_id, turn_id))
    def turn_steer(self, thread_id, turn_id, instruction): self.steers.append(instruction)


def notification(method, payload):
    return SimpleNamespace(method=method, payload=payload)


@pytest.fixture
def sdk(monkeypatch):
    StubClient.account_type = "chatgpt"
    StubClient.instances = []
    StubClient.notifications = []
    monkeypatch.setattr(module, "CodexClient", StubClient)
    return StubClient


def test_approval_handler_denies_all_escalations_and_sanitizes(tmp_path, sdk):
    provider = CodexProvider(tmp_path)
    events = []
    client = provider._connect(str(tmp_path), on_event=lambda *args: events.append(args))
    try:
        handler = client.approval_handler
        assert handler("item/commandExecution/requestApproval", {"api_key": "private"}) == {"decision": "decline"}
        assert handler("item/permissions/requestApproval", {}) == {"permissions": {}, "scope": "turn"}
        assert handler("item/tool/requestUserInput", {}) == {"answers": {}}
        assert handler("mcpServer/elicitation/request", {}) == {"action": "decline", "content": None}
        assert events[0][1]["request"]["api_key"] == "[REDACTED]"
    finally:
        client.close()


@pytest.mark.parametrize("account_type", ["apiKey", "unknown"])
def test_api_accounts_do_not_authenticate_or_fallback(tmp_path, sdk, account_type):
    sdk.account_type = account_type
    provider = CodexProvider(tmp_path)
    assert provider.account_status()["status"] == "AUTH_REQUIRED"
    with pytest.raises(ProviderError) as error:
        provider.model_list()
    assert error.value.code == "AUTH_REQUIRED"
    assert all(client.closed for client in sdk.instances)
    assert not any(client.started_threads for client in sdk.instances)
    with pytest.raises(ValueError, match="ChatGPT"):
        provider.authenticate("apiKey")


@pytest.mark.parametrize("thread_id", [None, "saved-thread"])
def test_execute_streams_usage_resumes_and_excludes_hidden_reasoning(tmp_path, sdk, thread_id):
    sdk.notifications = [
        notification("item/reasoning/textDelta", {"text": "hidden"}),
        notification("rawResponseItem/completed", {"item": "raw hidden"}),
        notification("item/completed", {"item": {"type": "reasoning", "text": "hidden"}}),
        notification("thread/tokenUsage/updated", {"tokenUsage": {"last": {"totalTokens": 12}}}),
        notification("item/completed", {"item": {"type": "agentMessage", "phase": "final_answer", "text": '{"verdict":"PLAN"}'}}),
        notification("turn/completed", {"turn": {"status": "completed"}}),
    ]
    events, threads = [], []
    agent = {"name": "coordinator", "instructions": "coordinate", "permission": "read-only"}
    result = CodexProvider(tmp_path).execute(agent, str(tmp_path), "task", {}, thread_id,
                                             lambda *args: events.append(args), threads.append, threading.Event())
    client = sdk.instances[-1]
    assert threads == [thread_id or "new-thread"]
    assert result["usage"]["last"]["totalTokens"] == 12
    assert all("hidden" not in str(event) for event in events)
    params = client.resumed_threads[0][1] if thread_id else client.started_threads[0]
    assert params["approvalPolicy"] == "never"
    assert params["config"] == {"mcp_servers.remote.enabled": False}
    assert client.closed


@pytest.mark.parametrize("status,message,code", [("failed", "usage limit exceeded", "USAGE_LIMIT"),
                                               ("failed", "401 unauthorized", "AUTH_REQUIRED"),
                                               ("interrupted", "cancelled", "INTERRUPTED"),
                                               ("failed", "unexpected error", "AGENT_FAILED")])
def test_terminal_sdk_errors_keep_specific_state(tmp_path, sdk, status, message, code):
    sdk.notifications = [notification("turn/completed", {"turn": {"status": status, "error": {"message": message}}})]
    agent = {"name": "qa", "instructions": "test", "permission": "read-only"}
    provider = CodexProvider(tmp_path)
    with pytest.raises(ProviderError) as error:
        provider.execute(agent, str(tmp_path), "task", {}, None, lambda *args: None, lambda tid: None, threading.Event())
    assert error.value.code == code
    assert sdk.instances[-1].closed
    assert provider.active is None


def test_streamed_tool_output_redacts_camelcase_and_environment_secrets(tmp_path, sdk):
    sdk.notifications = [
        notification("item/completed", {"item": {"type": "commandExecution", "accessToken": "private-access",
                                                   "output": "APP_TOKEN=private-token\nAWS_SECRET_ACCESS_KEY=private-aws"}}),
        notification("item/completed", {"item": {"type": "agentMessage", "phase": "final_answer", "text": "{}"}}),
        notification("turn/completed", {"turn": {"status": "completed"}}),
    ]
    agent = {"name": "qa", "instructions": "test", "permission": "read-only"}
    events = []
    CodexProvider(tmp_path).execute(agent, str(tmp_path), "task", {}, None,
                                     lambda *args: events.append(args), lambda tid: None, threading.Event())
    output_event = next(payload for kind, payload in events if payload.get("item", {}).get("type") == "commandExecution")
    assert output_event["item"]["accessToken"] == "[REDACTED]"
    assert "private" not in output_event["item"]["output"]


def test_execute_returns_native_completed_command_ledger(tmp_path, sdk):
    sdk.notifications = [
        notification("item/completed", {"item": {"id": "test-command", "type": "commandExecution", "status": "completed",
                                                   "command": "pytest -q", "cwd": str(tmp_path), "exitCode": 0,
                                                   "commandActions": [{"type": "unknown", "command": "pytest -q"}],
                                                   "aggregatedOutput": "1 passed\nAPP_TOKEN=private-token"}}),
        notification("item/completed", {"item": {"type": "agentMessage", "phase": "final_answer", "text": "{}"}}),
        notification("turn/completed", {"turn": {"status": "completed"}}),
    ]
    agent = {"name": "qa", "instructions": "test", "permission": "read-only"}
    response = CodexProvider(tmp_path).execute(agent, str(tmp_path), "task", {}, None,
                                                lambda *args: None, lambda tid: None, threading.Event())
    assert response["executions"] == [{"id": "test-command", "command": "pytest -q", "cwd": str(tmp_path),
                                       "exit_code": 0, "status": "completed", "output": "1 passed\nAPP_TOKEN=[REDACTED]",
                                       "actions": [{"type": "unknown", "command": "pytest -q"}]}]


@pytest.mark.parametrize("command,output", [
    ("pytest -q", "13 passed in 0.1s"),
    ("python -m pytest -q", "13 passed in 0.1s"),
    ("python -m unittest discover -s tests -v", "Ran 13 tests in 0.1s\nOK"),
    ('"C:\\Program Files\\Python\\python.exe" -m unittest discover', "Ran 1 test in 0.1s\nOK"),
    ("& 'C:\\Python\\python.exe' -c \"import unittest; unittest.TextTestRunner().run(suite)\"", "Ran 13 tests in 0.1s\nOK"),
    ('python -c "import pytest; pytest.main([\'-q\'])"', "13 passed in 0.1s"),
    ("dotnet test", "Passed: 13"),
    ("cargo test", "test result: ok. 13 passed; 0 failed"),
    ("npm test", "13 passed"),
    ("node --test", "# tests 13\n# pass 13\n# fail 0"),
    ("ctest", "100% tests passed, 0 tests failed out of 13"),
])
def test_successful_native_test_commands_have_nonzero_evidence(command, output):
    assert successful_test_execution({"command": command, "status": "completed", "exit_code": 0, "output": output})


def test_sdk_unknown_action_identifies_test_inside_powershell_wrapper():
    runner = "& 'C:\\Project\\.venv\\Scripts\\python.exe' -m unittest discover -s 'C:\\Project\\tests' -v"
    event = {"command": '"C:\\Program Files\\PowerShell\\7\\pwsh.exe" -NoProfile -Command "<runner>"',
             "actions": [{"type": "unknown", "command": runner}], "status": "completed", "exit_code": 0,
             "output": "Ran 13 tests in 0.05s\nOK"}
    assert successful_test_execution(event)


@pytest.mark.parametrize("command,output", [
    ("echo pytest passed", "13 passed"),
    ('python -c "print(\'13 passed\')"', "13 passed"),
    ('python -c "print(\'Ran 13 tests\')"', "Ran 13 tests"),
    ("Get-Content tests/test_sample.py", "13 passed"),
    ("rg pytest tests", "13 passed"),
    ("pytest -q", "0 passed in 0.1s"),
    ("python -m unittest discover", "Ran 0 tests in 0.1s\nOK"),
    ("ctest", "100% tests passed, 0 tests failed out of 0"),
    ("pytest -q", "No tests ran"),
])
def test_fabricated_or_zero_test_output_is_not_success(command, output):
    assert not successful_test_execution({"command": command, "status": "completed", "exit_code": 0, "output": output})


def test_sdk_read_actions_cannot_claim_test_execution():
    assert not successful_test_execution({"command": "pytest -q", "actions": [{"type": "read", "path": "tests/test_sample.py"}],
                                          "status": "completed", "exit_code": 0, "output": "13 passed"})


@pytest.mark.parametrize("command,output", [
    ("python -m unittest discover", "Ran 1 test in 0.1s\nFAILED (failures=1)"),
    ("python -m unittest discover", "Ran 1 test in 0.1s\nFAILED (errors=1)"),
    ("python -m unittest discover", "Ran 13 tests in 0.1s"),
    ('python -c "import unittest; unittest.TextTestRunner().run(suite)"', "Ran 1 test\nFAILED (failures=1)"),
    ("pytest -q", "1 failed, 13 passed in 0.1s"),
    ("dotnet test", "Passed: 13, Failed: 1"),
    ("node --test", "# tests 13\n# pass 12\n# fail 1"),
])
def test_failed_test_output_is_rejected_even_when_wrapper_exits_zero(command, output):
    assert not successful_test_execution({"command": command, "status": "completed", "exit_code": 0, "output": output})


@pytest.mark.parametrize("relative", [".env", ".env.local", "src/.env", "src/deep/.env.production",
                                      "src/.aws", "src/.codex", "src/.ssh", "src/.azure", "src/.kube", "src/.agents"])
def test_workspace_globs_deny_nested_secret_names(tmp_path, relative):
    config = config_for(str(tmp_path), {"permission": "workspace-write"})
    filesystem_overrides = [x for x in config.config_overrides if "permissions.codex-team.filesystem=" in x]
    assert len(filesystem_overrides) == 1
    assert not any("filesystem." in x.split("=", 1)[0] for x in config.config_overrides)
    filesystem = tomllib.loads(filesystem_overrides[0])["permissions"]["codex-team"]["filesystem"]
    globs = filesystem[":workspace_roots"]
    assert all(access == "deny" for access in globs.values())
    assert any(fnmatch.fnmatchcase(relative, pattern) for pattern in globs), f"No secret denial pattern covers {relative}"
    assert filesystem["glob_scan_max_depth"] == 16
    assert not any(fnmatch.fnmatchcase("src/application.py", pattern) for pattern in globs)


def test_worktree_policy_registers_original_root_for_secret_globs(tmp_path):
    repo = tmp_path / "project"
    repo.mkdir()

    def git(*args):
        completed = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, encoding="utf-8")
        assert completed.returncode == 0, completed.stderr

    git("init")
    git("config", "user.name", "Test User")
    git("config", "user.email", "test@example.invalid")
    (repo / "sample.txt").write_text("fixture\n", encoding="utf-8")
    git("add", "sample.txt")
    git("commit", "-m", "Initial")
    worktree = tmp_path / "worktree"
    git("worktree", "add", "--detach", str(worktree))
    config = config_for(str(worktree), {"permission": "workspace-write"})
    override = next(x for x in config.config_overrides if x.startswith("permissions.codex-team.workspace_roots="))
    roots = tomllib.loads(override)["permissions"]["codex-team"]["workspace_roots"]
    assert roots[str(repo.resolve())] is True
    filesystem = next(tomllib.loads(x)["permissions"]["codex-team"]["filesystem"]
                      for x in config.config_overrides if ".filesystem=" in x)
    assert filesystem[str(worktree.resolve())] == "write"
    assert filesystem[str(repo.resolve())] == "read"
    for name in (".env", ".aws", ".codex", ".ssh", ".azure", ".kube", ".agents"):
        assert filesystem[str(repo / name)] == "deny"
        assert filesystem[str(worktree / name)] == "deny"
