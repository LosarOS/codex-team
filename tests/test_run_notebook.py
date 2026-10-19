"""Production notebook/report router tests. No SDK, engine, repo or model calls."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import json
import re

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest

from codex_team.run_notebook import RunNotebooks, UpdateNotebook, _fence, build_report, create_run_notebook_router
from codex_team.storage import Store


@pytest.fixture
def notebook(tmp_path):
    store = Store(tmp_path / "state.db")
    store.save_run({"id": "run_one", "task": "Сделать страницу", "state": "DONE"})
    app = FastAPI()
    app.include_router(create_run_notebook_router(store))
    with TestClient(app) as client:
        yield client, store
    store.close()


def update(client, revision=0, favorite=True, note="Заметка", run_id="run_one"):
    return client.put(f"/api/runs/{run_id}/notebook", json={
        "expected_revision": revision, "favorite": favorite, "note": note,
    })


def test_default_is_not_persisted_and_missing_run_has_no_notebook(notebook):
    client, store = notebook
    assert client.get("/api/runs/run_one/notebook").json() == {
        "run_id": "run_one", "revision": 0, "favorite": False, "note": "", "updated_at": None,
    }
    assert store.db.execute("SELECT count(*) FROM run_notebooks").fetchone()[0] == 0
    for response in (client.get("/api/runs/missing/notebook"), update(client, run_id="missing"),
                     client.get("/api/runs/missing/report")):
        assert response.status_code == 404
        assert "Запуск не найден" in response.json()["detail"]
    assert store.db.execute("SELECT count(*) FROM run_notebooks").fetchone()[0] == 0


def test_revision_conflict_and_literal_local_text(notebook):
    client, store = notebook
    text = "  <script>literal</script>\nAPI_KEY=documentation-only\n```\n\x00 "
    first = update(client, note=text).json()
    assert first["revision"] == 1 and first["favorite"] is True and first["note"] == text
    assert datetime.fromisoformat(first["updated_at"]).utcoffset().total_seconds() == 0
    conflict = update(client, note="Lost update")
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "notebook_conflict"
    assert conflict.json()["detail"]["revision"] == 1
    assert client.get("/api/runs/run_one/notebook").json() == first
    second = update(client, revision=1, favorite=False, note="").json()
    assert second["revision"] == 2 and second["favorite"] is False and second["note"] == ""
    assert store.run("run_one")["task"] == "Сделать страницу"
    assert "notebook" not in store.run("run_one")
    assert store.events("run_one") == [] and store.actions() == []


@pytest.mark.parametrize("field,bad", [
    ("expected_revision", None), ("expected_revision", -1), ("expected_revision", True),
    ("expected_revision", "0"), ("expected_revision", 2**63 - 1), ("expected_revision", 0.0),
    ("favorite", 1), ("favorite", "true"), ("favorite", None),
    ("note", None), ("note", 123), ("note", "x" * 10001),
])
def test_strict_validation_never_mutates(notebook, field, bad):
    client, store = notebook
    body = {"expected_revision": 0, "favorite": True, "note": "Okay", field: bad}
    assert client.put("/api/runs/run_one/notebook", json=body).status_code == 422
    assert store.db.execute("SELECT count(*) FROM run_notebooks").fetchone()[0] == 0


def test_unknown_fields_missing_fields_malformed_json_and_limit_boundary(notebook):
    client, _ = notebook
    body = {"expected_revision": 0, "favorite": False, "note": ""}
    for key in body:
        assert client.put("/api/runs/run_one/notebook", json={k: v for k, v in body.items() if k != key}).status_code == 422
    assert client.put("/api/runs/run_one/notebook", json={**body, "access_level": "full-access"}).status_code == 422
    assert client.put("/api/runs/run_one/notebook", content="{", headers={"content-type": "application/json"}).status_code == 422
    assert update(client, note="я" * 10000).json()["note"] == "я" * 10000


def test_restart_persistence_additive_table_and_profile_isolation(tmp_path):
    path = tmp_path / "Профиль" / "state.db"
    store = Store(path)
    store.save_run({"id": "old", "state": "DONE", "task": "Original"})
    store.save_settings({"language": "en"})
    before = store.run("old")
    text = "\n  password=literal-local-note\n"
    saved = RunNotebooks(store).update("old", UpdateNotebook(expected_revision=0, favorite=True, note=text))
    store.close()
    store = Store(path)
    other = Store(tmp_path / "Other" / "state.db")
    try:
        assert RunNotebooks(store).get("old") == saved
        assert saved["note"] == text
        assert store.run("old") == before
        assert store.settings() == {"language": "en"}
        with pytest.raises(HTTPException) as missing:
            RunNotebooks(other).get("old")
        assert missing.value.status_code == 404
    finally:
        store.close()
        other.close()


@pytest.mark.parametrize("initial_revision", [0, 1])
def test_two_connections_serialize_first_and_later_writes(tmp_path, initial_revision):
    stores = [Store(tmp_path / "state.db"), Store(tmp_path / "state.db")]
    stores[0].save_run({"id": "r", "task": "unchanged"})
    services = [RunNotebooks(store) for store in stores]
    if initial_revision:
        services[0].update("r", UpdateNotebook(expected_revision=0, favorite=False, note="Initial"))
    try:
        def write(index):
            try:
                return services[index].update("r", UpdateNotebook(
                    expected_revision=initial_revision, favorite=bool(index), note=str(index),
                ))["revision"]
            except HTTPException as error:
                assert error.status_code == 409 and error.detail["code"] == "notebook_conflict"
                return "conflict"
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(write, range(2)))
        assert sorted(results, key=str) == [initial_revision + 1, "conflict"]
        assert services[0].get("r") == services[1].get("r")
        assert stores[0].run("r") == {"id": "r", "task": "unchanged"}
    finally:
        for store in stores:
            store.close()


def report(client, language="ru", run_id="run_one"):
    response = client.get(f"/api/runs/{run_id}/report", params={"language": language})
    assert response.status_code == 200, response.text
    return response.json()


def test_report_is_local_read_only_and_allowlisted(notebook, monkeypatch):
    client, store = notebook
    original = {
        "id": "run_one", "task": "Сделать страницу", "state": "DONE", "workspace": "D:\\Работа",
        "calls": 1, "usage": [{"last": {"totalTokens": 17}}], "elapsed_seconds": 0,
        "changed_files": ["src/main.py"], "results": {"developer": {"summary": "Done", "verdict": "PASS"}},
        "max_agent_calls": 3, "provider": {"api_key": "provider-secret", "private": "private-provider-sentinel"},
        "prompts": "prompt-sentinel", "events": "event-sentinel", "logs": "log-sentinel",
        "diff": "diff-sentinel", "agents": {"instructions": "hidden-agent-sentinel"},
    }
    store.save_run(original)
    saved = store.run("run_one")
    update(client, note="User observation")
    def forbidden(*args, **kwargs):
        raise AssertionError("Reports must not read runtime settings, events, agents or projects")
    for name in ("settings", "events", "agents", "projects", "actions"):
        monkeypatch.setattr(store, name, forbidden)
    exported = report(client)
    markdown = exported["markdown"]
    for expected in ("Сделать страницу", "src/main.py", "Done", "User observation", "D:\\Работа", "17"):
        assert expected in markdown
    for secret in ("private-provider-sentinel", "prompt-sentinel", "event-sentinel", "log-sentinel", "diff-sentinel", "hidden-agent-sentinel"):
        assert secret not in markdown
    assert "не статус QA Arena" in markdown and "не подтверждает прохождение QA Arena" in markdown
    assert store.run("run_one") == saved
    assert exported["run_id"] == "run_one" and exported["filename"] == "codex-team-run_one.md"
    assert exported["truncated"] is False and exported["warnings"] == []
    assert datetime.fromisoformat(exported["generated_at"]).utcoffset().total_seconds() == 0


def test_report_redacts_but_does_not_change_notebook(notebook):
    client, store = notebook
    text = "API_KEY=do-not-export\nBearer abcdefghijklmnop\nsk-1234567890abcdefgh\npassword=keep-local"
    update(client, note=text)
    exported = report(client)["markdown"]
    for secret in ("do-not-export", "abcdefghijklmnop", "sk-1234567890abcdefgh", "keep-local"):
        assert secret not in exported
    assert "[REDACTED]" in exported
    assert client.get("/api/runs/run_one/notebook").json()["note"] == text
    assert store.events("run_one") == []


@pytest.mark.parametrize("hostile", [
    '<script>alert(1)</script><img src="https://example.invalid/track">',
    "![image](https://example.invalid/track) [click](javascript:alert(1))",
    "```\n# Fake heading\n```\n````\n<img src=x>\n~~~~\n",
    "`" * 2000 + "\n<iframe src=x></iframe>",
])
def test_markdown_fence_keeps_html_images_links_and_hostile_fences_inert(hostile):
    rendered = _fence(hostile)
    lines = rendered.splitlines()
    opening = lines[0]
    closing = lines[-1]
    assert opening == closing + "text"
    assert len(closing) >= 3 and set(closing) == {"`"}
    assert all(len(group) < len(closing) for group in re.findall(r"`+", hostile))
    assert "\n" + hostile + "\n" in rendered


def test_report_fences_all_free_strings_and_sanitizes_filename(notebook):
    client, store = notebook
    evil = "\n```\n<img src=x>\n````\n![img](javascript:evil)"
    store.save_run({"id": "evil.id", "state": evil, "task": evil, "workspace": evil,
                    "results": {evil: {"summary": evil, "error": evil, "verdict": evil}}, "changed_files": [evil]})
    exported = report(client, run_id="evil.id")
    assert exported["filename"] == "codex-team-evil-id.md"
    assert exported["markdown"].count(_fence(evil)) >= 8
    assert re.fullmatch(r"[A-Za-z0-9_-]+\.md", exported["filename"])


def test_unknown_values_are_distinct_from_observed_zero(notebook):
    client, store = notebook
    missing = report(client, "en")
    assert "### Observed tokens\n\n```text\nNo data\n```" in missing["markdown"]
    assert "### Recorded duration, seconds\n\n```text\nNo data\n```" in missing["markdown"]
    assert "incomplete_usage" in missing["warnings"]
    store.save_run({"id": "run_one", "state": "DONE", "calls": 1, "usage": [{"last": {"totalTokens": 0}}],
                    "elapsed_seconds": 0, "changed_files": []})
    zero = report(client, "en")
    assert "### Observed tokens\n\n```text\n0\n```" in zero["markdown"]
    assert "### Recorded duration, seconds\n\n```text\n0\n```" in zero["markdown"]
    assert "### Changed files in the record\n\n```text\n0\n```" in zero["markdown"]
    assert "incomplete_usage" not in zero["warnings"]


def test_report_locales_and_invalid_language(notebook):
    client, _ = notebook
    ru = report(client)
    en = report(client, "en")
    assert ru["language"] == "ru" and "Сохранённая задача" in ru["markdown"]
    assert en["language"] == "en" and "Saved task" in en["markdown"]
    assert "Сохранённая задача" not in en["markdown"]
    assert client.get("/api/runs/run_one/report?language=fr").status_code == 422


def test_saved_result_history_count_is_not_called_attempt_count(notebook):
    client, store = notebook
    store.save_run({"id": "run_one", "state": "RUNNING", "result_history": [
        {"role": "developer", "result": {"summary": "First"}},
        {"role": "developer", "result": {"summary": "Latest"}},
    ]})
    exported = report(client, "en")
    assert "Latest" in exported["markdown"] and "First" not in exported["markdown"]
    assert "### Recorded results\n\n```text\n2\n```" in exported["markdown"]
    assert "not counts of all agent attempts" in exported["markdown"]
    assert "active_run" in exported["warnings"]


def test_top_level_history_error_is_preserved(notebook):
    client, store = notebook
    store.save_run({"id": "run_one", "state": "FAILED", "result_history": [
        {"role": "developer", "result": {"summary": "Stopped"}, "error": "Recorded outer error"},
    ]})
    assert "Recorded outer error" in report(client)["markdown"]


def test_imported_secrets_crossing_truncation_boundaries_are_redacted(notebook):
    client, store = notebook
    secret = "sk-1234567890abcdefghijklmnopqrstuvwxyz"
    raw = {"id": "run_one", "state": "DONE", "task": "t" * 29994 + secret,
           "results": {"developer": {"summary": "s" * 3994 + secret}},
           "changed_files": ["p" * 4090 + secret]}
    # Imported data may predate Store.save_run's sanitizer.
    with store.lock, store.db:
        store.db.execute("UPDATE runs SET data=? WHERE id=?", (json.dumps(raw), "run_one"))
    exported = report(client)
    assert "sk-123" not in exported["markdown"]
    assert "truncated" in exported["warnings"]


@pytest.mark.parametrize("identifier", [None, 42, {"wrong": "shape"}])
def test_standalone_report_filename_handles_malformed_identifier(identifier):
    result = build_report({"id": identifier, "state": "DONE"}, {"favorite": False, "note": ""}, "en")
    assert result["filename"] == "codex-team-run.md"


def test_long_records_are_bounded_and_explicitly_truncated(notebook):
    client, store = notebook
    store.save_run({
        "id": "run_one", "state": "DONE", "task": "t" * 30001, "workspace": "p" * 5000,
        "result_history": [{"role": f"role{index}", "result": {"summary": "`" * 5000, "error": "e" * 5000}}
                           for index in range(1001)],
        "results": {f"extra{index}": {"summary": "Not included"} for index in range(100)},
        "changed_files": [f"{index}/" + "f" * 5000 for index in range(201)],
    })
    exported = report(client, "en")
    assert exported["truncated"] is True and "truncated" in exported["warnings"]
    assert len(exported["markdown"]) < 600000
    assert "Some long data was shortened" in exported["markdown"]
    assert "t" * 30001 not in exported["markdown"]
    assert "### Role 65" not in exported["markdown"]


@pytest.mark.parametrize("fields", [
    {"task": None, "changed_files": None, "usage": None, "calls": "bad"},
    {"task": 123, "results": ["wrong"], "result_history": [None, "bad", {"role": "r", "result": None}]},
    {"usage": [None, "wrong", {"last": {"totalTokens": "wrong"}}], "specialists": [None, 42, "qa"]},
])
def test_legacy_partial_fields_do_not_crash_report(notebook, fields):
    client, store = notebook
    store.save_run({"id": "run_one", "state": "DONE", **fields})
    exported = report(client)
    assert "incomplete_usage" in exported["warnings"]


def test_unsupported_record_shape_has_explicit_error(notebook):
    client, store = notebook
    with store.lock, store.db:
        store.db.execute("UPDATE runs SET data=? WHERE id=?", (json.dumps(["broken"]), "run_one"))
    response = client.get("/api/runs/run_one/report")
    assert response.status_code == 422 and "неверный формат" in response.json()["detail"]
