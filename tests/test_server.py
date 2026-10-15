from pathlib import Path
import shutil
import subprocess

from fastapi.testclient import TestClient
import pytest

from codex_team.models import RunRequest
from codex_team.provider import CodexProvider, FakeCodexProvider
from codex_team.server import create_app
from codex_team.storage import Store

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def local_app(tmp_path, monkeypatch):
    def no_sdk(*args, **kwargs):
        raise AssertionError("HTTP tests must never contact the real Codex SDK")

    monkeypatch.setattr(CodexProvider, "_connect", no_sdk)
    monkeypatch.setattr(CodexProvider, "account_status", lambda self: {"status": "AUTH_REQUIRED", "account": None})
    root = tmp_path / "app"
    root.mkdir()
    for folder in ("agents", "packs", "codex_team/static"):
        shutil.copytree(ROOT / folder, root / folder)
    repo = tmp_path / "project"
    repo.mkdir()
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    store = Store(root / "state.db")
    app = create_app(root, store, provider_factory=lambda: FakeCodexProvider(connected=False))
    try:
        with TestClient(app) as client:
            yield client, app, root, store, repo
    finally:
        store.close()


@pytest.mark.parametrize("host", ["evil.invalid", "127.0.0.1.evil.invalid", "localhost@evil.invalid"])
def test_nonlocal_hosts_are_denied(local_app, host):
    client, *_ = local_app
    response = client.get("/api/status", headers={"host": host})
    assert response.status_code == 403


@pytest.mark.parametrize("origin", ["https://evil.invalid", "http://localhost", "null"])
def test_cross_origin_mutations_are_denied(local_app, origin):
    client, _, _, store, _ = local_app
    response = client.post("/api/settings", json={"model": "test-model"}, headers={"origin": origin})
    assert response.status_code == 403
    assert store.settings() == {}


@pytest.mark.parametrize("fetch_site", ["cross-site", "same-site"])
def test_fetch_site_csrf_rejected_even_with_json(local_app, fetch_site):
    client, _, _, store, _ = local_app
    response = client.post("/api/settings", json={"model": "test-model"}, headers={"sec-fetch-site": fetch_site})
    assert response.status_code == 403
    assert store.settings() == {}


@pytest.mark.parametrize("content_type", ["text/plain", "application/x-www-form-urlencoded", "multipart/form-data"])
def test_mutations_require_json_content_type(local_app, content_type):
    client, _, _, store, _ = local_app
    response = client.post("/api/settings", content='{"model":"test-model"}', headers={"content-type": content_type})
    assert response.status_code == 415
    assert store.settings() == {}


def test_same_origin_json_and_security_headers(local_app):
    client, *_ = local_app
    response = client.post("/api/settings", json={"model": "test-model"},
                           headers={"origin": "http://testserver", "sec-fetch-site": "same-origin"})
    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cache-control"] == "no-store"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert client.get("/").status_code == 200
    assert client.get("/app.js").status_code == 200
    helper = client.get("/mission-control.js")
    assert helper.status_code == 200
    assert "javascript" in helper.headers["content-type"]


@pytest.mark.parametrize("backend", ["openai_api", "fake_test_only", "custom"])
def test_api_backend_is_denied_without_persisting(local_app, backend):
    client, _, _, store, _ = local_app
    response = client.post("/api/settings", json={"execution_backend": backend})
    assert response.status_code == 400
    assert "disabled" in response.json()["detail"]
    assert store.settings() == {}


def test_api_login_method_has_no_fallback(local_app):
    client, *_ = local_app
    response = client.post("/api/login", json={"method": "apiKey"})
    assert response.status_code == 400
    assert "ChatGPT" in response.json()["detail"]


def test_settings_model_applies_to_new_run_and_preserves_agent_override(local_app):
    client, app, _, _, repo = local_app
    developer = next(a for a in client.get("/api/agents").json() if a["name"] == "developer")
    developer["model"] = "developer-specific"
    assert client.put("/api/agents/developer", json=developer).status_code == 200
    response = client.post("/api/settings", json={"model": "default-model", "reasoning_effort": "high"})
    assert response.status_code == 200
    run = app.state.engine.create(RunRequest(workspace=str(repo), task="Test settings propagation"))
    assert run["agents"]["coordinator"]["model"] == "default-model"
    assert run["agents"]["developer"]["model"] == "developer-specific"
    assert all(agent["reasoning_effort"] == "high" for agent in run["agents"].values())


@pytest.mark.parametrize("name", ["coordinator", "qa", "reviewer", "final-audit"])
def test_agents_put_cannot_grant_core_review_write_permission(local_app, name):
    client, _, root, store, _ = local_app
    original = next(a for a in client.get("/api/agents").json() if a["name"] == name)
    before = (root / "agents" / f"{name}.md").read_text(encoding="utf-8")
    modified = {**original, "permission": "workspace-write", "instructions": "Unsafe replacement"}
    response = client.put(f"/api/agents/{name}", json=modified)
    assert response.status_code == 400
    assert (root / "agents" / f"{name}.md").read_text(encoding="utf-8") == before
    assert next(a for a in store.agents() if a["name"] == name)["permission"] == "read-only"


def test_agents_put_rejects_renaming_and_unknown_agents(local_app):
    client, *_ = local_app
    qa = next(a for a in client.get("/api/agents").json() if a["name"] == "qa")
    assert client.put("/api/agents/qa", json={**qa, "name": "new-name"}).status_code == 400
    assert client.put("/api/agents/missing", json={**qa, "name": "missing"}).status_code == 400
    assert client.post("/api/agents", json=qa).status_code == 400
