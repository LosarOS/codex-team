"""Optional API provider contracts; no network or real credential-store calls."""
import fnmatch
import json
import tomllib
from pathlib import Path

import pytest

import codex_team.api_provider as module
from codex_team.api_provider import API_PROVIDER, KEY_VARIABLE, ProviderSettings, api_config
from codex_team.provider import CodexProvider
from codex_team.secrets import MemorySecretStore, SecretStoreError
from openai_codex import CodexConfig


KEY = "sk-mock-api-regression-only"


class SettingsStore:
    def __init__(self):
        self.values = {"execution_backend": "codex_chatgpt", "model": "user-model", "max_iterations": 7}
        self.writes = []
    def settings(self):
        return dict(self.values)
    def save_settings(self, changes):
        self.writes.append(dict(changes))
        self.values.update(changes)


class ChatGPTAuth:
    def __init__(self):
        self.status_calls = 0
    def account_status(self):
        self.status_calls += 1
        return {"status": "AUTH_REQUIRED", "backend": "codex_chatgpt"}
    def execute(self, *args):
        raise AssertionError("API status/test must never execute a ChatGPT fallback")
    def authenticate(self, *args):
        raise AssertionError("API status/test must never start a global login")


@pytest.fixture
def settings(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Only the explicit Test connection action may use the network")
    monkeypatch.setattr(module.urllib.request, "urlopen", forbidden)
    return ProviderSettings(SettingsStore(), MemorySecretStore(), ChatGPTAuth())


def test_api_schema_keeps_auth_separate_and_filters_child_environment():
    base = CodexConfig(config_overrides=('model_provider="openai"', 'forced_login_method="chatgpt"',
                                         'features.multi_agent=false'), env={"OPENAI_API_KEY": "", "CODEX_API_KEY": ""})
    config = api_config(base, KEY)
    parsed = tomllib.loads("\n".join(config.config_overrides))
    assert parsed["model_provider"] == API_PROVIDER
    assert parsed["forced_login_method"] == "api"
    provider = parsed["model_providers"][API_PROVIDER]
    assert provider["base_url"] == "https://api.openai.com/v1"
    assert provider["env_key"] == KEY_VARIABLE
    assert provider["requires_openai_auth"] is False
    assert provider["wire_api"] == "responses"
    assert parsed["features"]["multi_agent"] is False
    policy = parsed["shell_environment_policy"]
    assert policy["ignore_default_excludes"] is False
    assert policy["set"][KEY_VARIABLE] == ""
    for name in (KEY_VARIABLE, "OPENAI_API_KEY", "CODEX_API_KEY", "APP_TOKEN", "aws_secret_access_key", "db_password"):
        assert any(access == "exclude" and fnmatch.fnmatchcase(name.casefold(), pattern.casefold())
                   for pattern, access in policy["filters"].items())
    assert "exclude" not in policy and "include_only" not in policy
    assert config.env[KEY_VARIABLE] == KEY
    assert config.env["OPENAI_API_KEY"] == config.env["CODEX_API_KEY"] == ""
    assert KEY not in "\n".join(config.config_overrides)


def test_api_selection_requires_key_and_explicit_billing_consent(settings):
    with pytest.raises(ValueError, match="Confirm"):
        settings.select("openai_api")
    with pytest.raises(ValueError, match="Save"):
        settings.select("openai_api", acknowledge_billing=True)
    assert settings.store.writes == []
    settings.save(KEY)
    assert settings.select("openai_api", acknowledge_billing=True) == {"active": "openai_api"}
    assert settings.store.writes == [{"execution_backend": "openai_api"}]
    assert settings.store.settings()["model"] == "user-model"
    assert settings.store.settings()["max_iterations"] == 7
    assert KEY not in json.dumps(settings.store.values)


def test_status_has_no_api_probe_billing_or_automatic_fallback(settings):
    settings.save(KEY)
    settings.select("openai_api", acknowledge_billing=True)
    result = settings.status()
    assert result["active"] == "openai_api"
    assert result["codex"]["status"] == "AUTH_REQUIRED"
    assert result["openai_api"]["status"] == "CONFIGURED"
    assert result["openai_api"]["tested_at"] is None
    assert result["openai_api"]["billing"] == "separate"
    assert settings.auth.status_calls == 1
    assert KEY not in json.dumps(result)
    assert settings.store.values["execution_backend"] == "openai_api"


def test_explicit_connection_test_uses_only_bounded_models_request(settings, monkeypatch):
    settings.save(KEY)
    requests, limits = [], []
    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def read(self, limit):
            limits.append(limit)
            return b'{"data":[{"id":"mock-model"}]}'
    def urlopen(request, timeout):
        requests.append((request.full_url, request.get_method(), request.get_header("Authorization"), timeout))
        return Response()
    monkeypatch.setattr(module.urllib.request, "urlopen", urlopen)
    result = settings.test()
    assert result["status"] == "CONNECTED"
    assert requests == [("https://api.openai.com/v1/models", "GET", "Bearer " + KEY, 15)]
    assert limits == [1024 * 1024]
    assert settings.auth.status_calls == 0
    assert settings.store.writes == []
    assert KEY not in json.dumps(result)


@pytest.mark.parametrize("body", [b'not-json', b'{"data":null}', b'{"data":{}}'])
def test_malformed_models_result_cannot_claim_connected(settings, monkeypatch, body):
    settings.save(KEY)
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, limit): return body
    monkeypatch.setattr(module.urllib.request, "urlopen", lambda *a, **kw: Response())
    result = settings.test()
    assert result["status"] == "ERROR"
    assert settings.tested is None
    assert settings.auth.status_calls == 0


def test_api_error_stays_selected_and_redacts_response_exception(settings, monkeypatch):
    settings.save(KEY)
    settings.select("openai_api", acknowledge_billing=True)
    def fail(*args, **kwargs):
        raise OSError("private server diagnostic " + KEY)
    monkeypatch.setattr(module.urllib.request, "urlopen", fail)
    result = settings.test()
    assert result["status"] == "ERROR"
    assert KEY not in json.dumps(result)
    assert settings.store.values["execution_backend"] == "openai_api"
    assert settings.auth.status_calls == 0


def test_key_rotation_invalidates_previous_verified_connection(settings, monkeypatch):
    settings.save(KEY)
    settings.tested = "previous-test-time"
    settings.error = "previous-error"
    result = settings.save("sk-mock-replacement-only")
    assert settings.tested is None and settings.error is None
    assert "sk-mock-replacement-only" not in json.dumps(result)
    assert settings.status()["openai_api"]["status"] == "CONFIGURED"


def test_active_api_key_cannot_be_removed_and_switch_preserves_other_settings(settings):
    settings.save(KEY)
    settings.select("openai_api", acknowledge_billing=True)
    with pytest.raises(ValueError, match="Select"):
        settings.remove()
    assert settings.secrets.read() == KEY
    settings.select("codex_chatgpt")
    settings.remove()
    assert settings.secrets.read() is None
    assert settings.store.values["model"] == "user-model"
    assert settings.store.values["max_iterations"] == 7


def test_failed_secure_storage_has_no_plaintext_or_settings_fallback(settings):
    class UnavailableStore(MemorySecretStore):
        def save(self, key):
            raise SecretStoreError("secure storage unavailable")
    settings.secrets = UnavailableStore()
    with pytest.raises(SecretStoreError, match="secure storage"):
        settings.save(KEY)
    assert settings.store.writes == []
    assert settings.secrets.read() is None


@pytest.mark.parametrize("backend", ["unknown", "fake_test_only", "custom"])
def test_unknown_production_provider_never_falls_back(backend):
    with pytest.raises(ValueError, match="fallback"):
        CodexProvider(Path.cwd(), backend=backend)
