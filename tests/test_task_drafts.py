from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from codex_team.storage import Store
from codex_team.task_drafts import SaveDraft, TaskDrafts, create_draft_router


@pytest.fixture
def draft_client(tmp_path):
    store = Store(tmp_path / "state.db")
    app = FastAPI()
    app.include_router(create_draft_router(store))
    with TestClient(app) as client:
        yield client, store
    store.close()


def save(client, revision=0, **data):
    return client.put("/api/task-draft", json={"expected_revision": revision, "data": data})


def test_empty_draft_and_clear_are_idempotent(draft_client):
    client, store = draft_client
    assert client.get("/api/task-draft").json() == {"revision": 0, "draft": None}
    for _ in range(2):
        assert client.delete("/api/task-draft?expected_revision=0").json() == {"revision": 0, "draft": None}
    assert store.runs() == []
    assert store.settings() == {}


def test_literal_editor_text_survives_restart_in_selected_data_root(tmp_path):
    path = tmp_path / "Профиль пользователя" / "state.db"
    original = "  Сделай страницу\npassword=example-for-docs\nAPI_KEY=placeholder\n<script>alert(1)</script>\n  "
    store = Store(path)
    result = TaskDrafts(store).save(SaveDraft(expected_revision=0, data={
        "task": original, "workspace": "D:\\Проекты\\страница", "mode": "quick",
        "pack": "custom", "specialists": ["designer"], "max_agent_calls": 3,
    }))
    assert result["revision"] == result["draft"]["revision"] == 1
    assert result["draft"]["updated_at"]
    store.close()
    reopened = Store(path)
    try:
        assert TaskDrafts(reopened).get() == result
        assert result["draft"]["data"]["task"] == original
        assert reopened.runs() == []
        assert reopened.db.execute("SELECT count(*) FROM events").fetchone()[0] == 0
        other = Store(tmp_path / "other-profile" / "state.db")
        try:
            assert TaskDrafts(other).get() == {"revision": 0, "draft": None}
        finally:
            other.close()
    finally:
        reopened.close()


def test_conflict_does_not_overwrite_and_tombstone_prevents_aba(draft_client):
    client, _ = draft_client
    assert save(client, task="Первый").status_code == 200
    response = save(client, task="Устаревший")
    assert response.status_code == 409
    assert response.json()["detail"]["revision"] == 1
    assert client.delete("/api/task-draft?expected_revision=0").status_code == 409
    assert client.get("/api/task-draft").json()["draft"]["data"]["task"] == "Первый"
    assert client.delete("/api/task-draft?expected_revision=1").json() == {"revision": 2, "draft": None}
    assert save(client, task="Повтор старого запроса").status_code == 409
    assert client.delete("/api/task-draft?expected_revision=2").json()["revision"] == 2
    assert save(client, 2, task="Новый").json()["revision"] == 3


@pytest.mark.parametrize("data", [
    {"api_key": "example"}, {"provider": "openai"}, {"access_level": "full-access"},
    {"confirmed_full_access": True}, {"auto_commit": True}, {"isolated": False},
    {"task": "x" * 30001}, {"workspace": "x" * 4097}, {"pack": "x" * 101},
    {"specialists": ["x"] * 51}, {"specialists": ["x" * 101]},
    {"mode": "unknown"}, {"max_iterations": 0}, {"max_iterations": 11},
    {"max_agent_calls": 101}, {"max_run_duration": 29}, {"max_run_duration": 86401},
    {"max_agent_calls": True}, {"max_iterations": "3"}, {"task": None},
])
def test_untrusted_or_unbounded_data_is_rejected_without_mutation(draft_client, data):
    client, _ = draft_client
    assert save(client, **data).status_code == 422
    assert client.get("/api/task-draft").json() == {"revision": 0, "draft": None}


@pytest.mark.parametrize("body", [
    {"data": {}}, {"expected_revision": -1, "data": {}},
    {"expected_revision": True, "data": {}}, {"expected_revision": "0", "data": {}},
    {"expected_revision": 2**63, "data": {}},
    {"expected_revision": 0, "data": {}, "provider": "openai"},
])
def test_revision_and_envelope_validation(draft_client, body):
    client, _ = draft_client
    assert client.put("/api/task-draft", json=body).status_code == 422


def test_clear_requires_valid_explicit_revision(draft_client):
    client, _ = draft_client
    for query in ("", "?expected_revision=-1", "?expected_revision=bad", f"?expected_revision={2**63}"):
        assert client.delete("/api/task-draft" + query).status_code == 422


def test_defaults_allow_incomplete_composer_and_no_execution(draft_client):
    client, store = draft_client
    result = save(client).json()
    assert result["draft"]["data"] == {
        "task": "", "workspace": "", "mode": "standard", "pack": "software-development",
        "specialists": [], "max_iterations": 3, "max_agent_calls": 15, "max_run_duration": 1800,
    }
    assert store.runs() == []
    assert store.actions() == []


def test_concurrent_connections_only_one_revision_wins(tmp_path):
    path = tmp_path / "state.db"
    stores = [Store(path), Store(path)]
    drafts = [TaskDrafts(store) for store in stores]
    def change(item):
        index, service = item
        try:
            return service.save(SaveDraft(expected_revision=0, data={"task": str(index)}))["revision"]
        except Exception as error:
            assert getattr(error, "status_code", None) == 409
            return "conflict"
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            result = list(pool.map(change, enumerate(drafts)))
        assert sorted(result, key=str) == [1, "conflict"]
        assert drafts[0].get() == drafts[1].get()
    finally:
        for store in stores:
            store.close()


def test_additive_table_preserves_existing_records(tmp_path):
    store = Store(tmp_path / "state.db")
    try:
        store.save_run({"id": "previous", "task": "Existing history"})
        store.save_settings({"theme": "emerald-tech"})
        TaskDrafts(store).save(SaveDraft(expected_revision=0, data={"task": "Draft"}))
        assert store.run("previous")["task"] == "Existing history"
        assert store.settings()["theme"] == "emerald-tech"
        assert len(store.runs()) == 1
    finally:
        store.close()


def test_clear_tombstone_survives_restart_and_maximum_valid_task_is_preserved(tmp_path):
    path = tmp_path / "state.db"
    store = Store(path)
    service = TaskDrafts(store)
    task = "я" * 30000
    assert service.save(SaveDraft(expected_revision=0, data={"task": task}))["draft"]["data"]["task"] == task
    assert service.clear(1) == {"revision": 2, "draft": None}
    store.close()
    store = Store(path)
    try:
        service = TaskDrafts(store)
        assert service.get() == {"revision": 2, "draft": None}
        assert service.save(SaveDraft(expected_revision=2, data={"task": "After restart"}))["revision"] == 3
    finally:
        store.close()
