import concurrent.futures
import json

import pytest

from codex_team.storage import Store, sanitize


def test_sanitize_nested_credentials_without_changing_evidence():
    payload = {"access_token": "private", "nested": [{"PASSWORD": "p", "command": "pytest -q"}],
               "message": "Bearer secret.value and sk-abcdefghijklmnop",
               "jwt": "eyJabcdefghijklmnop.payload.signature", "exit_code": 0}
    result = sanitize(payload)
    assert result["access_token"] == "[REDACTED]"
    assert result["nested"] == [{"PASSWORD": "[REDACTED]", "command": "pytest -q"}]
    assert "secret.value" not in json.dumps(result)
    assert "sk-" not in result["message"]
    assert result["jwt"] == "[REDACTED]"
    assert result["exit_code"] == 0
    assert payload["access_token"] == "private"


def test_store_roundtrip_and_secret_redaction(tmp_path):
    store = Store(tmp_path / "state.db")
    try:
        store.save_run({"id": "run_a", "state": "DONE", "task": "Задача", "api_key": "private"})
        store.event("run_a", "output", {"text": "Bearer abc.def", "cookie": "session"}, "qa")
        store.save_agent({"name": "custom", "instructions": "sk-abcdefghijklmnop"})
        store.save_settings({"password": {"secret": "private"}, "mode": "standard"})
        assert store.run("run_a")["task"] == "Задача"
        assert store.run("run_a")["api_key"] == "[REDACTED]"
        event = store.events("run_a")[0]
        assert event["role"] == "qa"
        assert event["payload"] == {"text": "[REDACTED]", "cookie": "[REDACTED]"}
        assert store.events("run_a", after=event["id"]) == []
        assert store.agents()[0]["instructions"] == "[REDACTED]"
        assert store.settings()["password"] == {"secret": "[REDACTED]"}
        with pytest.raises(KeyError):
            store.run("missing")
    finally:
        store.close()
    reopened = Store(tmp_path / "state.db")
    try:
        assert len(reopened.runs()) == 1
        assert reopened.settings()["mode"] == "standard"
    finally:
        reopened.close()


@pytest.mark.parametrize("state", ["RUNNING", "QUEUED", "PAUSING", "STOPPING"])
def test_restart_recovers_only_inflight_states(tmp_path, state):
    store = Store(tmp_path / "state.db")
    try:
        checkpoint = {"id": "inflight", "state": state, "stage": 2, "threads": {"developer": "dev-thread"}}
        store.save_run(checkpoint)
        store.save_run({"id": "completed", "state": "DONE"})
        store.recover()
        restored = store.run("inflight")
        assert restored["state"] == "INTERRUPTED"
        assert restored["stage"] == 2
        assert restored["threads"] == {"developer": "dev-thread"}
        assert store.run("completed")["state"] == "DONE"
        assert store.events("inflight")[0]["type"] == "recovered"
    finally:
        store.close()


def test_concurrent_events_have_unique_ordered_ids(tmp_path):
    store = Store(tmp_path / "state.db")
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda i: store.event("run", "chunk", {"index": i}), range(80)))
        events = store.events("run")
        assert len(events) == 80
        assert len({e["id"] for e in events}) == 80
        assert [e["id"] for e in events] == sorted(e["id"] for e in events)
        assert {e["payload"]["index"] for e in events} == set(range(80))
    finally:
        store.close()


def test_camelcase_keys_and_environment_assignments_are_redacted(tmp_path):
    payload = {"accessToken": "access-private", "refreshToken": "refresh-private", "idToken": "id-private",
               "apiKey": "key-private", "database_url": "db-private", "aws_secret_access_key": "aws-private",
               "output": "APP_TOKEN=token-private\nDB_PASSWORD=password-private\nDATABASE_URL=postgres://db-private\n"
                         "AWS_SECRET_ACCESS_KEY=aws-private\napiKey: key-private\nnormal=value"}
    sanitized = sanitize(payload)
    assert all(value == "[REDACTED]" for key, value in sanitized.items() if key != "output")
    assert "private" not in sanitized["output"]
    assert "normal=value" in sanitized["output"]
    store = Store(tmp_path / "state.db")
    try:
        store.event("run", "output", payload)
        assert store.events("run")[0]["payload"] == sanitized
    finally:
        store.close()
