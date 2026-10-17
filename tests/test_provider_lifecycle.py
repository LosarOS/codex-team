"""Provider lifecycle regressions. SDK and HTTP interactions are test doubles."""
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

import codex_team.provider as module
from codex_team.provider import CodexProvider, ProviderError
from codex_team.api_provider import API_PROVIDER, KEY_VARIABLE, ProviderSettings, api_config
from codex_team.secrets import MemorySecretStore
from openai_codex import CodexConfig


def worker(call):
    result = {}
    def invoke():
        try:
            result["value"] = call()
        except Exception as exc:
            result["error"] = exc
    thread = threading.Thread(target=invoke, daemon=True)
    thread.start()
    return thread, result


class Client:
    def __init__(self, config, approval_handler):
        self.config = config
        self.running = False
        self.closed = threading.Event()
    def start(self):
        self.running = True
    def initialize(self):
        return None
    def close(self):
        self.running = False
        self.closed.set()
    def account_read(self, params):
        return {"account": {"type": "chatgpt"}}
    def account_login_start(self, params):
        return {"loginId": "mock-login"}


@pytest.fixture
def mock_sdk(monkeypatch):
    monkeypatch.setattr(module, "config_for", lambda *a: CodexConfig(config_overrides=('default_permissions="lifecycle-test-profile"',)))
    monkeypatch.setattr(module, "CodexClient", Client)
    return CodexProvider(Path.cwd())


def test_connect_cannot_start_after_provider_close(mock_sdk, monkeypatch):
    """SDK close-before-start is a no-op, so late startup must be owned/closed."""
    entered, resume = threading.Event(), threading.Event()
    clients = []
    class DelayedStart(Client):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            clients.append(self)
        def start(self):
            entered.set()
            assert resume.wait(2)
            super().start()
    monkeypatch.setattr(module, "CodexClient", DelayedStart)
    thread, result = worker(lambda: mock_sdk._connect(str(Path.cwd())))
    try:
        assert entered.wait(1)
        mock_sdk.close()
        resume.set()
        thread.join(1)
        assert not thread.is_alive()
        assert not clients[0].running, "late initialized transport survived close and lost ownership"
        assert isinstance(result.get("error"), ProviderError)
        assert result["error"].code == "INTERRUPTED"
    finally:
        resume.set()
        thread.join(2)
        for client in clients:
            client.close()


def test_login_initialization_does_not_block_close_lock(mock_sdk, monkeypatch):
    entered, resume = threading.Event(), threading.Event()
    class StalledInitialize(Client):
        def initialize(self):
            entered.set()
            assert resume.wait(2)
    monkeypatch.setattr(module, "CodexClient", StalledInitialize)
    login, _ = worker(mock_sdk.authenticate)
    closing = None
    try:
        assert entered.wait(1)
        closing, _ = worker(mock_sdk.close)
        closing.join(0.2)
        assert not closing.is_alive(), "close waits on authentication initialization lock"
    finally:
        resume.set()
        login.join(2)
        if closing:
            closing.join(2)
        mock_sdk.close()


def test_bounded_rpc_closes_stalled_owned_client(mock_sdk):
    client = Client(CodexConfig(), None)
    mock_sdk.clients.add(client)
    with pytest.raises(ProviderError) as error:
        mock_sdk._bounded(client, lambda: client.closed.wait(2), timeout=0.02)
    assert error.value.code == "INTERRUPTED"
    assert client.closed.is_set()
    assert client not in mock_sdk.clients


def test_interrupt_returns_promptly_and_releases_stalled_rpc(mock_sdk):
    class StalledInterrupt(Client):
        def turn_interrupt(self, *args):
            self.closed.wait(3)
    client = StalledInterrupt(CodexConfig(), None)
    mock_sdk.clients.add(client)
    mock_sdk.active = (client, "thread", "turn")
    interrupt, _ = worker(mock_sdk.interrupt)
    try:
        interrupt.join(0.3)
        assert not interrupt.is_alive()
        assert client.closed.wait(2.5)
    finally:
        mock_sdk.close()


def test_pre_turn_config_rpc_has_a_local_deadline(mock_sdk, monkeypatch):
    entered = threading.Event()
    class StalledConfig(Client):
        def request(self, *args, **kwargs):
            entered.set()
            assert self.closed.wait(2)
            raise ProviderError("INTERRUPTED", "transport closed")
    monkeypatch.setattr(module, "CodexClient", StalledConfig)
    original = mock_sdk._bounded
    monkeypatch.setattr(mock_sdk, "_bounded", lambda client, call, timeout=20: original(client, call, timeout=0.03))
    cancel = threading.Event()
    agent = {"instructions": "review", "permission": "read-only"}
    execution, result = worker(lambda: mock_sdk.execute(agent, str(Path.cwd()), "mock", {}, None,
                                                        lambda *a: None, lambda *a: None, cancel))
    try:
        assert entered.wait(1)
        execution.join(0.2)
        assert not execution.is_alive(), "config/read bypassed the bounded RPC helper"
        assert isinstance(result.get("error"), ProviderError)
        assert result["error"].code == "INTERRUPTED"
    finally:
        mock_sdk.close()
        execution.join(2)


def test_api_login_never_starts_global_chatgpt_login(monkeypatch):
    calls = []
    class ApiClient(Client):
        def account_login_start(self, params):
            calls.append(params)
            return {}
    monkeypatch.setattr(module, "config_for", lambda *a: CodexConfig(config_overrides=('default_permissions="lifecycle-test-profile"',)))
    monkeypatch.setattr(module, "CodexClient", ApiClient)
    provider = CodexProvider(Path.cwd(), backend="openai_api", secret_store=MemorySecretStore())
    provider.secret_store.save("sk-mock-review-only")
    try:
        with pytest.raises(ValueError):
            provider.authenticate("chatgpt")
        assert calls == []
    finally:
        provider.close()


def test_explicit_api_fork_preserves_provider(monkeypatch):
    params_seen = []
    class ApiClient(Client):
        def thread_fork(self, thread_id, params):
            params_seen.append(params)
            return SimpleNamespace(thread=SimpleNamespace(id="fork"))
    monkeypatch.setattr(module, "config_for", lambda *a: CodexConfig(config_overrides=('default_permissions="lifecycle-test-profile"',)))
    monkeypatch.setattr(module, "CodexClient", ApiClient)
    secrets = MemorySecretStore()
    secrets.save("sk-mock-review-only")
    provider = CodexProvider(Path.cwd(), backend="openai_api", secret_store=secrets)
    try:
        assert provider.fork("thread", {"instructions": "review"}, str(Path.cwd())) == "fork"
        assert params_seen[0]["modelProvider"] == API_PROVIDER
        assert params_seen[0]["config"]["default_permissions"] == "lifecycle-test-profile"
    finally:
        provider.close()


def test_api_key_exists_only_in_transport_env_and_not_arguments():
    import tomllib
    key = "sk-mock-review-only"
    config = api_config(CodexConfig(), key)
    assert config.env[KEY_VARIABLE] == key
    assert key not in repr(config.config_overrides)
    filters = next(tomllib.loads(x)["shell_environment_policy"]["filters"]
                   for x in config.config_overrides if "policy.filters=" in x)
    assert filters[KEY_VARIABLE] == "exclude"
    assert f'shell_environment_policy.set.{KEY_VARIABLE}=""' in config.config_overrides


def test_failed_api_connectivity_does_not_fallback_or_reveal_key(monkeypatch):
    import codex_team.api_provider as api
    class Store:
        def settings(self):
            return {"execution_backend": "openai_api"}
    class Auth:
        def account_status(self):
            raise AssertionError("no ChatGPT fallback/probe during explicit API test")
    secrets = MemorySecretStore()
    secrets.save("sk-mock-review-only")
    settings = ProviderSettings(Store(), secrets, Auth())
    calls = []
    def fail(request, timeout):
        calls.append((request.full_url, timeout))
        raise OSError("server included sk-mock-review-only")
    monkeypatch.setattr(api.urllib.request, "urlopen", fail)
    result = settings.test()
    assert result["status"] == "ERROR"
    assert "sk-mock-review-only" not in repr(result)
    assert calls == [("https://api.openai.com/v1/models", 15)]


def test_missing_permission_profile_blocks_thread_before_rpc(mock_sdk, monkeypatch):
    """Malformed adapter config must never fall back to persisted permissions."""
    monkeypatch.setattr(module, "config_for", lambda *a: CodexConfig())
    with pytest.raises(ProviderError) as error:
        mock_sdk.execute({"instructions": "review", "permission": "read-only"},
                         str(Path.cwd()), "mock", {}, "persisted-thread",
                         lambda *a: None, lambda *a: None, threading.Event())
    assert error.value.code == "CONFIGURATION_REQUIRED"
    assert "StopIteration" not in str(error.value)
    assert not mock_sdk.clients
