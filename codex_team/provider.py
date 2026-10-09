"""Official SDK adapter. No private endpoints, token handling or API fallback."""
import json
import os
import threading
import shutil
import sys
import subprocess
import time
import copy
import weakref
from pathlib import Path
from typing import Protocol
from pydantic import RootModel
from openai_codex import CodexConfig
from openai_codex.client import CodexClient
from .storage import sanitize
from .runtimes import runtime_read_roots, _narrow

class ProviderError(RuntimeError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)

class AgentProvider(Protocol):
    def account_status(self) -> dict: ...
    def execute(self, agent: dict, workspace: str, prompt: str, schema: dict,
                thread_id: str | None, on_event, on_thread, cancel: threading.Event) -> dict: ...
    def interrupt(self): ...
    def steer(self, instruction: str): ...
    def close(self): ...

class ObjectResponse(RootModel[dict]):
    pass

def dump(model):
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json", by_alias=True)
    return model

def config_for(workspace: str, agent: dict | None = None) -> CodexConfig:
    """Add a narrow native permission profile without changing saved user config.

    Preserve managed environment restrictions. Explicitly select official OpenAI
    provider + ChatGPT-only login. Blank inherited API keys in the child.
    """
    profile = "codex-team"
    access = "write" if agent and agent["permission"] == "workspace-write" else "read"
    fs = {":minimal": "read", str(Path(workspace).resolve()): access}
    # Tools need their installed runtime libraries. Grant exact executable
    # installation directories read-only, never user document/credential roots.
    for executable in ("pwsh", "powershell", "git"):
        tool = shutil.which(executable)
        if tool:
            tool_dir = Path(tool).resolve().parent
            if executable == "git" and tool_dir.name.lower() in {"cmd", "bin"}:
                tool_dir = tool_dir.parent
            if _narrow(tool_dir):
                fs[str(tool_dir)] = "read"
            elif _narrow(Path(tool)):
                # A PATH executable in home/root must not authorize its parent.
                fs[str(Path(tool).resolve())] = "read"
    # Git worktrees have a pointer to read-only shared repository metadata.
    git = subprocess.run(["git", "-c", "core.fsmonitor=false", "-C", workspace, "rev-parse", "--git-common-dir"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10)
    project_root = Path(workspace)
    if git.returncode == 0:
        common = Path(git.stdout.strip())
        common = common if common.is_absolute() else Path(workspace) / common
        fs[str(common.resolve())] = "read"
        if common.name == ".git" and _narrow(common.resolve().parent):
            project_root = common.resolve().parent
            # A worktree is nested under the user's selected original project.
            # Native Git needs directory metadata there to resolve worktree pointers.
            fs.setdefault(str(common.resolve().parent), "read")
            for name in (".env", ".aws", ".codex", ".ssh", ".azure", ".kube", ".agents"):
                fs[str(common.resolve().parent / name)] = "deny"
    # Runtime paths are discovered without executing repository code. Grant
    # exact interpreter/standard-library paths, never a broad base_prefix/home.
    for runtime_path in runtime_read_roots(workspace, project_root=project_root):
        fs.setdefault(runtime_path, "read")
    # A more-specific deny prevents reading obvious credentials inside the repo.
    for name in (".env", ".aws", ".codex", ".ssh", ".azure", ".kube", ".agents"):
        fs[str(Path(workspace) / name)] = "deny"
    # The exact current working tree alone is granted, not the whole disk or app.
    overrides = (
        'model_provider="openai"', 'forced_login_method="chatgpt"',
        'features.multi_agent=false', 'features.apps=false', 'features.prefer_mxc=true',
        'allow_login_shell=false',
        f'default_permissions="{profile}"',
        f'permissions.{profile}.network.enabled=false',
    )
    # JSON object syntax isn't TOML; form an inline table with JSON-escaped keys/values.
    table = "{ " + ", ".join(json.dumps(k, ensure_ascii=False) + " = " + json.dumps(v) for k, v in fs.items()) + " }"
    secret_patterns = [".env", ".env.*", "**/.env", "**/.env.*", *[f"**/{name}" for name in (".aws", ".codex", ".ssh", ".azure", ".kube", ".agents")]]
    glob_rules = "{ " + ", ".join(json.dumps(pattern) + ' = "deny"' for pattern in secret_patterns) + " }"
    # CLI config override keys are dotted paths, not TOML quoted-key parsers.
    # Keep special/root keys inside an inline table rather than quoted dotted keys.
    table = table[:-2] + f', glob_scan_max_depth = 16, ":workspace_roots" = {glob_rules} }}'
    overrides = (*overrides, f"permissions.{profile}.filesystem={table}")
    if git.returncode == 0 and common.name == ".git" and _narrow(common.resolve().parent):
        overrides = (*overrides, f"permissions.{profile}.workspace_roots={{ {json.dumps(str(common.resolve().parent), ensure_ascii=False)} = true }}")
    return CodexConfig(cwd=workspace, client_name="codex_team", client_title="Codex Team",
                       config_overrides=overrides,
                       env={"OPENAI_API_KEY": "", "CODEX_API_KEY": "", "OPENAI_BASE_URL": ""})

class CodexProvider:
    capabilities = {"backend": "codex_chatgpt", "sdk": "openai-codex 0.162.1",
                    "thread_start": True, "thread_resume": True, "thread_fork": True,
                    "stream": True, "steer": True, "interrupt": True, "token_usage": True,
                      "models": True, "approvals": "Native supported requests through Action Center; unsupported requests declined",
                      "openai_api": "Optional; explicit selection and separate billing; no automatic fallback", "parallel_writers": False,
                    "multi_solution": False}

    def __init__(self, app_root: Path, backend="codex_chatgpt", secret_store=None):
        self.app_root = app_root
        self.client = None
        self.active = None
        self.lock = threading.RLock()
        self.clients = set()
        self.retired = weakref.WeakSet()
        self.closed = False
        self.approval_handler = None
        self.backend = backend
        self.secret_store = secret_store
        self.status_cache = None
        self.status_time = 0
        self.status_lock = threading.Lock()
        if backend not in {"codex_chatgpt", "openai_api"}:
            raise ValueError("Unsupported provider; automatic fallback is disabled")

    def _bounded(self, client, call, timeout=20):
        """A stuck SDK RPC cannot hold shutdown or an HTTP worker indefinitely."""
        finished = threading.Event()
        result = {}
        def worker():
            try:
                result["value"] = call()
            except Exception as exc:
                result["error"] = exc
            finally:
                finished.set()
        threading.Thread(target=worker, daemon=True, name="codex-rpc").start()
        if not finished.wait(timeout):
            self._release(client)
            raise ProviderError("INTERRUPTED", "Codex did not respond in time. Retry or resume from History.")
        if "error" in result:
            raise result["error"]
        return result.get("value")

    def _release(self, client):
        with self.lock:
            self.clients.discard(client)
            self.retired.add(client)
            if self.client is client:
                self.client = None
        # close() owns only the SDK subprocess. Bound even defective test transports.
        worker = threading.Thread(target=client.close, daemon=True, name="codex-transport-close")
        worker.start()
        worker.join(timeout=4)

    def _connect(self, workspace, agent=None, on_event=None):
        def approvals(method, params):
            if on_event:
                on_event("approval_required", {"method": method, "request": sanitize(params or {})})
            if self.approval_handler:
                response = self.approval_handler(method, params or {})
                if on_event:
                    granted = response.get("decision") in {"accept", "acceptForSession"} or bool(response.get("permissions")) or bool(response.get("answers"))
                    on_event("approval_resolved", {"method":method,"granted":granted})
                return response
            if method == "item/permissions/requestApproval":
                return {"permissions": {}, "scope": "turn"}
            if method == "item/tool/requestUserInput":
                return {"answers": {}}
            if method == "mcpServer/elicitation/request":
                return {"action": "decline", "content": None}
            return {"decision": "decline"}
        config = config_for(workspace, agent)
        if agent and not agent.get("can_execute", True):
            from dataclasses import replace
            config = replace(config, config_overrides=(*config.config_overrides,'features.shell_tool=false','features.unified_exec=false'))
        if self.backend == "openai_api":
            from .api_provider import api_config
            if self.secret_store is None:
                raise ProviderError("CONFIGURATION_REQUIRED", "Configure the Windows secure key store first")
            config = api_config(config, self.secret_store.read())
        client = CodexClient(config, approval_handler=approvals)
        with self.lock:
            if self.closed:
                raise ProviderError("INTERRUPTED", "This provider session has ended")
            self.clients.add(client)
        try:
            def start():
                with self.lock:
                    if self.closed or client in self.retired:
                        raise ProviderError("INTERRUPTED", "This provider session has ended")
                client.start()
                # SDK.start may complete after close() interrupted an initialization.
                # Recheck ownership before initialize and close the newly created child.
                with self.lock:
                    stopped = self.closed or client in self.retired
                if stopped:
                    client.close()
                    raise ProviderError("INTERRUPTED", "This provider session has ended")
                try:
                    client.initialize()
                finally:
                    with self.lock:
                        stopped = self.closed or client in self.retired
                    if stopped:
                        client.close()
            self._bounded(client, start)
            with self.lock:
                if self.closed:
                    raise ProviderError("INTERRUPTED", "This provider session has ended")
            return client
        except Exception:
            self._release(client)
            raise

    def account_status(self):
        if self.backend == "openai_api":
            configured = bool(self.secret_store and self.secret_store.status()["configured"])
            return {"status":"CONNECTED" if configured else "CONFIGURATION_REQUIRED","backend":"openai_api","account":None,"api_key_required":True,"billing":"separate","connectivity_verified":False}
        with self.status_lock:
            if self.status_cache and time.monotonic() - self.status_time < 30:
                return copy.deepcopy(self.status_cache)
            client = self._connect(str(self.app_root))
            try:
                data = dump(self._bounded(client,lambda:client.account_read({"refreshToken":False})))
                account = data.get("account")
                connected = bool(account and account.get("type") == "chatgpt")
                self.status_cache = {"status":"CONNECTED" if connected else "AUTH_REQUIRED","account":account,"backend":"codex_chatgpt","api_key_required":False}
                self.status_time = time.monotonic()
                return copy.deepcopy(self.status_cache)
            finally:
                self._release(client)

    def _require_account(self, client):
        if self.backend == "openai_api":
            if not self.secret_store or not self.secret_store.status()["configured"]:
                raise ProviderError("CONFIGURATION_REQUIRED", "Save an OpenAI API key in Settings")
            return
        self._bounded(client, lambda:self._require_chatgpt(client))

    @staticmethod
    def _require_chatgpt(client):
        data = dump(client.account_read({"refreshToken": False}))
        if not data.get("account") or data["account"].get("type") != "chatgpt":
            raise ProviderError("AUTH_REQUIRED", "Sign in with ChatGPT or Device Code Login. API fallback is disabled.")

    def authenticate(self, method="chatgpt"):
        if self.backend != "codex_chatgpt":
            raise ValueError("Official ChatGPT login belongs to the Codex / ChatGPT provider. Configure API credentials in Settings.")
        if method not in {"chatgpt", "chatgptDeviceCode"}:
            raise ValueError("Only official ChatGPT login is supported")
        # Keep app-server alive until browser/device login completes.
        with self.lock:
            client = self.client
        if client is None:
            candidate = self._connect(str(self.app_root))
            with self.lock:
                stopped = self.closed
                client = self.client or candidate
                if not stopped:
                    self.client = client
            if stopped:
                self._release(candidate)
                raise ProviderError("INTERRUPTED", "This provider session has ended")
            if candidate is not client:
                self._release(candidate)
        self.status_cache = None
        return dump(self._bounded(client,lambda:client.account_login_start({"type":method})))

    def model_list(self):
        client = self._connect(str(self.app_root))
        try:
            self._require_account(client)
            return dump(self._bounded(client,client.model_list))
        finally:
            self._release(client)

    def read_usage(self):
        from openai_codex.generated.v2_all import GetAccountRateLimitsResponse
        client = self._connect(str(self.app_root))
        try:
            self._require_account(client)
            if self.backend == "openai_api":
                return {"unavailable":"OpenAI API does not expose this account quota. Separate API billing applies."}
            return dump(self._bounded(client,lambda:client.request("account/rateLimits/read", {}, response_model=GetAccountRateLimitsResponse)))
        finally:
            self._release(client)

    @staticmethod
    def _thread_params(agent, workspace):
        return {"cwd": workspace, "modelProvider": "openai", "model": agent.get("model"),
                "developerInstructions": agent["instructions"], "approvalPolicy": "never"}

    def fork(self, thread_id, agent, workspace):
        client = self._connect(workspace, agent)
        try:
            self._require_account(client)
            params = self._thread_params(agent,workspace)
            if self.approval_handler:
                params["approvalPolicy"] = "on-request"
            if self.backend == "openai_api":
                from .api_provider import API_PROVIDER
                params["modelProvider"] = API_PROVIDER
            return self._bounded(client,lambda:client.thread_fork(thread_id,params)).thread.id
        finally:
            self._release(client)

    def execute(self, agent, workspace, prompt, schema, thread_id, on_event, on_thread, cancel):
        approval_requests = []
        declined_requests = []
        def relay(kind, payload):
            if kind == "approval_required":
                approval_requests.append(payload)
            if kind == "approval_resolved" and not payload.get("granted"):
                declined_requests.append(payload)
            on_event(kind, payload)
        client = self._connect(workspace, agent, relay)
        with self.lock:
            self.client = client
        try:
            self._require_account(client)
            params = self._thread_params(agent, workspace)
            if self.approval_handler:
                params["approvalPolicy"] = "on-request"
            if self.backend == "openai_api":
                from .api_provider import API_PROVIDER
                params["modelProvider"] = API_PROVIDER
            # Disable configured external MCP servers for the agent thread. Their
            # individual permission models cannot establish workspace isolation.
            config = self._bounded(client,lambda:client.request("config/read", {"includeLayers": False}, response_model=ObjectResponse)).root
            mcp = config.get("config", {}).get("mcp_servers", {})
            params["config"] = {f"mcp_servers.{name}.enabled": False for name in mcp}
            if thread_id:
                thread = self._bounded(client,lambda:client.thread_resume(thread_id, params)).thread
            else:
                thread = self._bounded(client,lambda:client.thread_start(params)).thread
            on_thread(thread.id)
            on_event("thread_ready", {"thread_id": thread.id, "resumed": bool(thread_id)})
            if cancel.is_set():
                raise ProviderError("INTERRUPTED", "Run interrupted before turn start")
            turn = self._bounded(client,lambda:client.turn_start(thread.id, prompt, {"effort": agent.get("reasoning_effort"), "outputSchema": schema}))
            with self.lock:
                self.active = (client, thread.id, turn.turn.id)
            if cancel.is_set():
                self.interrupt()
            final = None
            usage = None
            denied = False
            executions = []
            while True:
                event = client.next_turn_notification(turn.turn.id)
                payload = dump(event.payload)
                if not isinstance(payload, dict):
                    continue
                # Never persist hidden reasoning or raw model response items.
                if "reasoning" in event.method.lower() or event.method == "rawResponseItem/completed":
                    continue
                if event.method in {"item/started", "item/completed"} and payload.get("item", {}).get("type") == "reasoning":
                    continue
                on_event(event.method, sanitize(payload))
                if event.method == "thread/tokenUsage/updated":
                    usage = payload.get("tokenUsage")
                if event.method == "item/completed":
                    item = payload.get("item", {})
                    if item.get("type") == "commandExecution":
                        executions.append(sanitize({"id": item.get("id"), "command": item.get("command", ""),
                                                    "cwd": item.get("cwd"), "exit_code": item.get("exitCode"),
                                                    "output": item.get("aggregatedOutput", ""), "status": item.get("status"),
                                                    "actions": item.get("commandActions", [])}))
                    if item.get("type") == "agentMessage" and item.get("phase") in {"final_answer", None}:
                        final = item.get("text")
                    if item.get("status") == "declined":
                        denied = True
                if event.method == "turn/completed":
                    status = payload.get("turn", {}).get("status")
                    if status != "completed":
                        error = payload.get("turn", {}).get("error") or {}
                        code = "INTERRUPTED" if status == "interrupted" else "AGENT_FAILED"
                        message = error.get("message", f"Turn {status}")
                        if any(x in message.lower() for x in ("usage limit", "rate limit", "quota")):
                            code = "USAGE_LIMIT"
                        elif any(x in message.lower() for x in ("unauthorized", "authentication", "401")):
                            code = "AUTH_REQUIRED"
                        raise ProviderError(code, message)
                    break
            if not final:
                raise ProviderError("INVALID_RESULT", "Agent returned no final structured result")
            return {"text": final, "usage": usage, "thread_id": thread.id, "denied": denied or bool(declined_requests) or (bool(approval_requests) and not self.approval_handler), "executions": executions}
        finally:
            with self.lock:
                self.active = None
                if self.client is client:
                    self.client = None
            self._release(client)

    def interrupt(self):
        with self.lock:
            active = self.active
        if active:
            def interrupt():
                try:
                    self._bounded(active[0],lambda:active[0].turn_interrupt(active[1],active[2]),timeout=2)
                except Exception:
                    pass
            worker = threading.Thread(target=interrupt,daemon=True,name="codex-interrupt")
            worker.start()
            worker.join(timeout=0.1)

    def steer(self, instruction):
        with self.lock:
            active = self.active
        if active:
            self._bounded(active[0],lambda:active[0].turn_steer(active[1],active[2],instruction),timeout=5)
            return True
        return False

    def close(self):
        with self.lock:
            clients = list(self.clients)
            if self.client and self.client not in clients:
                clients.append(self.client)
            self.closed = True
            self.client = None
            self.clients.clear()
            self.retired.update(clients)
        workers = [threading.Thread(target=c.close,daemon=True,name="codex-close") for c in clients]
        for worker in workers:
            worker.start()
        deadline = time.monotonic() + 4
        for worker in workers:
            worker.join(timeout=max(0,deadline-time.monotonic()))

class FakeCodexProvider:
    """Deterministic test double. Never used as a production fallback."""
    capabilities = {"backend": "fake_test_only"}
    def __init__(self, results=None, connected=True):
        self.results = list(results or [])
        self.connected = connected
        self.calls = []
        self.interrupted = False
    def account_status(self):
        return {"status": "CONNECTED" if self.connected else "AUTH_REQUIRED", "account": {"type": "chatgpt"}}
    def execute(self, agent, workspace, prompt, schema, thread_id, on_event, on_thread, cancel):
        if not self.connected:
            raise ProviderError("AUTH_REQUIRED", "ChatGPT login required")
        if cancel.is_set():
            raise ProviderError("INTERRUPTED", "Interrupted")
        import uuid
        tid = thread_id or str(uuid.uuid4())
        on_thread(tid)
        self.calls.append({"agent": agent["name"], "thread_id": tid, "prompt": prompt})
        on_event("item/completed", {"item": {"type": "commandExecution", "command": "test", "exitCode": 0}})
        if not self.results:
            raise ProviderError("AGENT_FAILED", "No fake response configured")
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return {"text": json.dumps(result), "thread_id": tid,
                "executions": [{"id": "fake-test", "command": t["command"], "exit_code": t["exit_code"], "output": t["output"], "status": "completed"} for t in result.get("tests", [])],
                "usage": {"last": {"inputTokens": 10, "cachedInputTokens": 2, "outputTokens": 5, "totalTokens": 15}}, "denied": False}
    def interrupt(self):
        self.interrupted = True
    def steer(self, instruction):
        return False
    def close(self):
        pass
