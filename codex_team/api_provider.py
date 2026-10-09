"""Explicit API configuration for the official Codex SDK; never a fallback."""
import json
from dataclasses import replace
import urllib.request
from .storage import now, sanitize


API_PROVIDER = "codex-team-openai-api"
KEY_VARIABLE = "CODEX_TEAM_OPENAI_API_KEY"


def api_config(config, key):
    if not key:
        raise ValueError("Save an OpenAI API key in Settings before selecting this provider")
    overrides = tuple(x for x in config.config_overrides if not x.startswith(("model_provider=", "forced_login_method=")))
    overrides += (
        f'model_provider="{API_PROVIDER}"',
        'forced_login_method="api"',
        f'model_providers.{API_PROVIDER}.name="OpenAI API (separate billing)"',
        f'model_providers.{API_PROVIDER}.base_url="https://api.openai.com/v1"',
        f'model_providers.{API_PROVIDER}.env_key="{KEY_VARIABLE}"',
        f'model_providers.{API_PROVIDER}.wire_api="responses"',
        f'model_providers.{API_PROVIDER}.requires_openai_auth=false',
        # The SDK transport receives the credential; shell tools must not.
        'shell_environment_policy.ignore_default_excludes=false',
        'shell_environment_policy.filters={"CODEX_TEAM_OPENAI_API_KEY"="exclude","OPENAI_API_KEY"="exclude","CODEX_API_KEY"="exclude","*TOKEN*"="exclude","*SECRET*"="exclude","*PASSWORD*"="exclude","*KEY*"="exclude"}',
        'shell_environment_policy.set.CODEX_TEAM_OPENAI_API_KEY=""',
    )
    return replace(config, config_overrides=overrides, env={**(config.env or {}), KEY_VARIABLE:key})


class ProviderSettings:
    def __init__(self, store, secrets, auth):
        self.store, self.secrets, self.auth = store, secrets, auth
        self.tested = None
        self.error = None

    def status(self):
        secret = self.secrets.status()
        return {"active":self.store.settings().get("execution_backend","codex_chatgpt"),
                "codex":self.auth.account_status(),
                "openai_api":{**secret,"status":"ERROR" if self.error else "CONNECTED" if self.tested and secret["configured"] else "CONFIGURED" if secret["configured"] else "NOT CONFIGURED",
                              "billing":"separate","tested_at":self.tested,"error":self.error}}

    def select(self, provider, acknowledge_billing=False):
        if provider not in {"codex_chatgpt","openai_api"}:
            raise ValueError("Choose Codex / ChatGPT or OpenAI API")
        if provider == "openai_api":
            if not acknowledge_billing:
                raise ValueError("Confirm: this provider uses separate API billing")
            if not self.secrets.status()["configured"]:
                raise ValueError("Save an OpenAI API key in Settings first")
        self.store.save_settings({"execution_backend":provider})
        return {"active":provider}

    def save(self, key):
        self.secrets.save(key)
        self.tested = self.error = None
        return self.secrets.status()

    def remove(self):
        if self.store.settings().get("execution_backend") == "openai_api":
            raise ValueError("Select Codex / ChatGPT before removing the active provider key")
        self.secrets.remove()
        self.tested = self.error = None
        return self.secrets.status()

    def test(self):
        key = self.secrets.read()
        if not key:
            raise ValueError("Save an API key before testing connection")
        # Explicit connectivity only: no inference, no usage charges or quota claim.
        request = urllib.request.Request("https://api.openai.com/v1/models", headers={"Authorization":"Bearer " + key})
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                data = json.loads(response.read(1024 * 1024))
            if not isinstance(data.get("data"),list):
                raise ValueError("The provider returned an unexpected models response")
        except Exception:
            self.error = "Connection could not be verified. Check the API key and network connection."
            self.tested = None
            return {"status":"ERROR","error":self.error}
        self.tested, self.error = now(), None
        return {"status":"CONNECTED","tested_at":self.tested,"billing":"separate"}
