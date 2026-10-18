"""Local persistence and comparison contracts. These tests never launch a model."""
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from codex_team.productivity import (
    CreateTemplate, TaskTemplates, UpdateTemplate, create_productivity_router, normalize_run,
)
from codex_team.storage import Store
from test_server import local_app


@pytest.fixture
def productivity(tmp_path):
    store = Store(tmp_path / "state.db")
    app = FastAPI()
    app.include_router(create_productivity_router(store))
    with TestClient(app) as client:
        yield client, store
    store.close()


def create(client, name="Шаблон", **data):
    return client.post("/api/task-templates", json={"name": name, "data": data})


def test_literal_template_persists_and_additive_migration_leaves_other_records(tmp_path):
    path = tmp_path / "Профиль" / "state.db"
    store = Store(path)
    store.save_run({"id": "old", "task": "Existing"})
    store.save_settings({"theme": "emerald-tech"})
    text = "  Задание\nAPI_KEY=documentation-only\npassword=example\n<script>alert(1)</script>\n  "
    template = TaskTemplates(store).create(CreateTemplate(
        name="../Local/template", description="Описание", data={"task": text, "workspace": "D:\\Проекты"},
    ))
    assert len(template["id"]) == 32 and template["id"].isalnum()
    assert template["revision"] == 1
    store.close()
    store = Store(path)
    try:
        templates = TaskTemplates(store)
        assert templates.get(template["id"]) == template
        assert template["data"]["task"] == text
        assert store.run("old")["task"] == "Existing"
        assert store.settings() == {"theme": "emerald-tech"}
        assert store.db.execute("SELECT count(*) FROM events").fetchone()[0] == 0
        assert store.actions() == []
        other = Store(tmp_path / "different-profile" / "state.db")
        try:
            assert TaskTemplates(other).page() == {"items": [], "total": 0}
        finally:
            other.close()
    finally:
        store.close()


def test_crud_revision_conflicts_missing_and_summary_list(productivity):
    client, store = productivity
    response = create(client, task="Original")
    assert response.status_code == 201
    first = response.json()
    url = "/api/task-templates/" + first["id"]
    assert client.get(url).json() == first
    listing = client.get("/api/task-templates").json()
    assert listing["total"] == 1 and "data" not in listing["items"][0]
    body = {"expected_revision": 1, "name": "Edited", "description": "Updated", "data": {"task": "Latest"}}
    edited = client.put(url, json=body).json()
    assert edited["revision"] == 2 and edited["created_at"] == first["created_at"]
    assert client.put(url, json=body).status_code == 409
    conflict = client.delete(url + "?expected_revision=1")
    assert conflict.status_code == 409 and conflict.json()["detail"]["revision"] == 2
    assert "Обновите" in conflict.json()["detail"]["message"]
    assert client.get(url).json()["data"]["task"] == "Latest"
    assert client.delete(url + "?expected_revision=2").json() == {"deleted": True, "id": first["id"]}
    assert client.get(url).status_code == client.put(url, json=body).status_code == 404
    assert client.delete(url + "?expected_revision=2").status_code == 404
    assert create(client).json()["id"] != first["id"]
    assert store.runs() == [] and store.actions() == [] and store.settings() == {}


def test_search_is_literal_bounded_and_paginated(productivity):
    client, _ = productivity
    first = create(client, "100%_done", task="Full task excluded from summaries").json()
    create(client, "Other")
    assert client.get("/api/task-templates?query=%25_").json()["items"][0]["id"] == first["id"]
    assert client.get("/api/task-templates?query=%27%20OR%201=1--").json()["total"] == 0
    page = client.get("/api/task-templates?limit=1&offset=1").json()
    assert page["total"] == 2 and len(page["items"]) == 1
    for suffix in ("limit=0", "limit=51", "offset=-1", "offset=100001", "query=" + "x" * 201):
        assert client.get("/api/task-templates?" + suffix).status_code == 422


@pytest.mark.parametrize("extra", [
    {"provider": "openai"}, {"api_key": "example"}, {"access_level": "full-access"},
    {"confirmed_full_access": True}, {"permission": "workspace-write"}, {"auto_commit": True},
    {"isolated": False}, {"task": "x" * 30001}, {"workspace": "x" * 4097},
    {"mode": "bad"}, {"specialists": ["x"] * 51}, {"max_agent_calls": True},
    {"max_iterations": "3"}, {"max_run_duration": 0},
])
def test_template_safe_allowlist_rejects_permissions_credentials_and_bad_data(productivity, extra):
    client, store = productivity
    assert create(client, **extra).status_code == 422
    assert client.get("/api/task-templates").json() == {"items": [], "total": 0}
    assert store.runs() == []


@pytest.mark.parametrize("body", [
    {"name": "", "data": {}}, {"name": "   ", "data": {}},
    {"name": "x" * 121, "data": {}}, {"name": "Okay", "description": "x" * 1001, "data": {}},
    {"name": "Okay", "data": {}, "provider": "openai"}, {"name": "Okay"},
])
def test_template_envelope_is_validated(productivity, body):
    client, _ = productivity
    assert client.post("/api/task-templates", json=body).status_code == 422


def test_revision_validation_and_malformed_json_never_mutate(productivity):
    client, _ = productivity
    item = create(client).json()
    url = "/api/task-templates/" + item["id"]
    for revision in (None, 0, -1, True, "1", 2**63):
        assert client.put(url, json={"expected_revision": revision, "name": "Name", "data": {}}).status_code == 422
    for suffix in ("", "?expected_revision=0", "?expected_revision=bad", f"?expected_revision={2**63}"):
        assert client.delete(url + suffix).status_code == 422
    assert client.post("/api/task-templates", content="{", headers={"content-type": "application/json"}).status_code == 422
    assert client.get(url).json() == item


def test_template_limit_and_parallel_connections_enforce_cas(tmp_path):
    stores = [Store(tmp_path / "state.db"), Store(tmp_path / "state.db")]
    services = [TaskTemplates(store) for store in stores]
    try:
        item = services[0].create(CreateTemplate(name="Original", data={}))
        def update(index):
            try:
                return services[index].update(item["id"], UpdateTemplate(expected_revision=1, name=str(index), data={}))["revision"]
            except HTTPException as error:
                assert error.status_code == 409
                return "conflict"
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(update, range(2)))
        assert sorted(results, key=str) == [2, "conflict"]
        for index in range(199):
            services[0].create(CreateTemplate(name=str(index), data={}))
        with pytest.raises(HTTPException) as caught:
            services[1].create(CreateTemplate(name="Overflow", data={}))
        assert caught.value.detail["code"] == "template_limit"
        services[0].delete(item["id"], 2)
        assert services[1].create(CreateTemplate(name="Room again", data={}))["revision"] == 1
    finally:
        for store in stores:
            store.close()


def test_comparison_partial_unknown_and_measured_usage_and_latest_stage(productivity):
    client, store = productivity
    common = {"workspace": "/project", "original_workspace": "/project", "max_agent_calls": 10}
    store.save_run({**common, "id": "left", "task": "Original", "state": "DONE", "mode": "quick",
                    "access_level": "read-only", "calls": 2, "elapsed_seconds": 2.5, "changed_files": [],
                    "usage": [{"last": {"inputTokens": 10, "cachedInputTokens": 7, "outputTokens": 2}},
                              {"last": {"total_tokens": 5}}],
                    "result_history": [{"role": "qa", "result": {"verdict": "FAIL", "summary": "First"}},
                                       {"role": "qa", "result": {"verdict": "PASS", "summary": "Latest"}}],
                    "results": {"qa": {"verdict": "FAIL", "summary": "Old map"}}})
    store.save_run({**common, "id": "right", "state": "RUNNING", "calls": 1,
                    "usage": [{}], "results": {"developer": {"verdict": "IMPLEMENTED", "summary": "Partial"}}})
    response = client.get("/api/run-comparison?left=left&right=right")
    assert response.status_code == 200
    result = response.json()
    assert result["comparable_project"] is True
    assert result["warnings"] == ["active_runs_partial", "incomplete_usage"]
    left, right = result["left"], result["right"]
    assert (left["calls"], left["measured_tokens"], left["usage_complete"]) == (2, 17, True)
    assert left["duration_seconds"] == 2.5 and left["changed_files_count"] == 0
    assert left["access_level"] == "read-only"
    assert left["stages"] == [{"role": "qa", "summary": "Latest", "verdict": "PASS", "error": None, "attempts": 2}]
    assert right["measured_tokens"] is right["duration_seconds"] is right["changed_files_count"] is None
    assert right["stages"][0]["attempts"] is None
    assert "qa_arena" not in response.text and "account_quota" not in response.text


def test_comparison_different_projects_missing_and_identical_ids(productivity):
    client, store = productivity
    store.save_run({"id": "a", "workspace": "/a", "state": "DONE"})
    store.save_run({"id": "b", "workspace": "/b", "state": "FAILED"})
    result = client.get("/api/run-comparison?left=a&right=b").json()
    assert result["comparable_project"] is False and "different_projects" in result["warnings"]
    assert client.get("/api/run-comparison?left=a&right=a").status_code == 422
    assert client.get("/api/run-comparison?left=a&right=missing").status_code == 404
    assert client.get("/api/run-comparison?left=a").status_code == 422
    store.save_run({"id": "b"})
    assert "project_unknown" in client.get("/api/run-comparison?left=a&right=b").json()["warnings"]


def test_latest_recorded_stage_error_does_not_reuse_an_older_pass():
    result = normalize_run({"result_history": [
        {"role": "qa", "result": {"verdict": "PASS", "summary": "Old result"}},
        {"role": "qa", "error": "Stage interrupted", "result": None},
    ]})
    assert result["stages"] == [{"role": "qa", "summary": None, "verdict": None,
                                  "error": "Stage interrupted", "attempts": 2}]


@pytest.mark.parametrize("bad", [None, "unknown", -1, True, float("nan"), float("inf"), 10**400])
def test_bad_persisted_metrics_are_nullable_and_do_not_crash(bad):
    result = normalize_run({"calls": bad, "elapsed_seconds": bad, "changed_files": bad,
                            "usage": [None, {"last": None}], "results": None,
                            "result_history": [None, "invalid", {"role": []}]})
    assert result["calls"] is result["duration_seconds"] is result["changed_files_count"] is None
    assert result["measured_tokens"] is None and result["usage_complete"] is False
    assert result["stages"] == []


def test_comparison_only_reads_requested_store_records_and_bounded_role_results():
    class ReadOnlyStore:
        def __init__(self):
            self.reads = []
        def run(self, run_id):
            self.reads.append(run_id)
            return {"id": run_id, "workspace": "/does-not-need-to-exist", "calls": 0,
                    "provider": {"api_key": "secret-must-not-return"}, "agents": {"qa": {"password": "secret"}},
                    "result_history": [{"role": "qa", "result": {"summary": "s" * 5000, "error": "e" * 5000}}] * 1001}
    from codex_team.productivity import compare_runs
    store = ReadOnlyStore()
    result = compare_runs(store, "a", "b")
    assert store.reads == ["a", "b"]
    assert result["left"]["stages"][0]["attempts"] == 1000
    assert len(result["left"]["stages"][0]["summary"]) == 4000
    assert "stage_history_truncated" in result["warnings"]
    assert "provider" not in result["left"] and "agents" not in result["left"]


def test_productivity_inherits_server_same_origin_json_and_permission_boundaries(local_app):
    client, app, _, store, _ = local_app
    if not any(getattr(route, "path", None) == "/api/task-templates" for route in app.routes):
        app.include_router(create_productivity_router(store))
    body = {"name": "Local", "data": {"task": "Task"}}
    assert client.post("/api/task-templates", json=body, headers={"origin": "https://evil.invalid"}).status_code == 403
    assert client.post("/api/task-templates", json=body, headers={"sec-fetch-site": "cross-site"}).status_code == 403
    assert client.get("/api/task-templates", headers={"host": "evil.invalid"}).status_code == 403
    assert client.post("/api/task-templates", content="{}", headers={"content-type": "text/plain"}).status_code == 415
    item = client.post("/api/task-templates", json=body).json()
    url = "/api/task-templates/" + item["id"] + "?expected_revision=1"
    assert client.delete(url).status_code == 415
    assert client.request("DELETE", url, json={}).status_code == 200
    assert client.get("/api/run-comparison?left=a&right=b", headers={"origin": "https://evil.invalid"}).status_code == 403
    assert app.state.engine.active == {} and store.runs() == []
