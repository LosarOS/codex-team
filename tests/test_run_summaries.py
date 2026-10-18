import pytest

from codex_team.budget_guardian import measured_tokens
from codex_team.storage import Store
from test_server import local_app


@pytest.fixture
def store(tmp_path):
    instance = Store(tmp_path / "state.db")
    yield instance
    instance.close()


def summary(store, **fields):
    store.save_run({"id": "run_summary", "state": "DONE", "task": "Task", **fields})
    return store.run_page()["items"][0]


def test_unreported_usage_is_unknown_instead_of_zero(store):
    run = summary(store, calls=1, usage=[])
    assert run["usage_total"] == dict.fromkeys(("input", "output", "cached", "total"))
    assert run["usage_available"] is False
    assert run["usage_complete"] is False


def test_measured_zero_is_distinct_from_unknown(store):
    run = summary(store, calls=1, usage=[{"last": {"totalTokens": 0}}])
    assert run["usage_total"] == {"input": None, "output": None, "cached": None, "total": 0}
    assert run["usage_available"] is True
    assert run["usage_complete"] is True


def test_all_known_camel_counters_keep_the_existing_object_contract(store):
    run = summary(store, calls=1, usage=[{"last": {"inputTokens": 10, "outputTokens": 2, "cachedInputTokens": 3, "totalTokens": 12}}])
    assert run["usage_total"] == {"input": 10, "output": 2, "cached": 3, "total": 12}
    assert run["usage_available"] is True
    assert run["usage_complete"] is True


def test_input_only_is_available_without_inventing_a_total(store):
    run = summary(store, calls=1, usage=[{"last": {"inputTokens": 10}}])
    assert run["usage_total"] == {"input": 10, "output": None, "cached": None, "total": None}
    assert run["usage_available"] is True
    assert run["usage_complete"] is False


def test_camel_snake_and_derived_totals_match_budget_measurements(store):
    entries = [
        {"last": {"inputTokens": 10, "outputTokens": 2, "cachedInputTokens": 3, "totalTokens": 12}},
        {"last": {"input_tokens": 20, "output_tokens": 4, "cached_input_tokens": 5}},
        {"last": {"total_tokens": 7}, "total": {"totalTokens": 999}},
    ]
    run = summary(store, calls=3, usage=entries)
    assert run["usage_total"] == {"input": 30, "output": 6, "cached": 8, "total": 43}
    assert run["usage_total"]["total"] == sum(measured_tokens(entry) for entry in entries)
    assert run["usage_complete"] is True
    assert "usage" not in run
    assert store.run("run_summary")["usage"] == entries


def test_partial_usage_keeps_observed_counts_and_marks_incomplete(store):
    run = summary(store, calls=3, usage=[{"last": {"totalTokens": 12}}, {}, {"total": {"totalTokens": 900}}])
    assert run["usage_total"]["total"] == 12
    assert run["usage_available"] is True
    assert run["usage_complete"] is False


@pytest.mark.parametrize("usage", [None, "unavailable", {}, [None, "bad", 1, [], {"last": None}],
    [{"last": {"inputTokens": True, "outputTokens": "4", "totalTokens": -1, "cachedInputTokens": 1.5}}]])
def test_malformed_usage_does_not_break_the_run_list(store, usage):
    run = summary(store, calls=1, usage=usage)
    assert run["usage_total"] == dict.fromkeys(("input", "output", "cached", "total"))
    assert run["usage_available"] is False
    assert run["usage_complete"] is False


def test_invalid_camel_counter_can_fall_back_to_valid_snake_counter(store):
    run = summary(store, calls=1, usage=[{"last": {"totalTokens": "12", "total_tokens": 12}}])
    assert run["usage_total"]["total"] == 12
    assert run["usage_complete"] is True


def test_missing_usage_from_some_calls_is_incomplete(store):
    run = summary(store, calls=2, usage=[{"last": {"totalTokens": 12}}])
    assert run["usage_total"]["total"] == 12
    assert run["usage_complete"] is False


@pytest.mark.parametrize("calls", [None, True, "1", -1])
def test_invalid_call_count_cannot_claim_complete_usage(store, calls):
    run = summary(store, calls=calls, usage=[{"last": {"totalTokens": 12}}])
    assert run["usage_total"]["total"] == 12
    assert run["usage_complete"] is False


def test_summary_strips_large_artifacts_without_changing_saved_run(store):
    fields = {key: "large artifact" for key in ("diff", "diff_stat", "results", "result_history", "executions", "agents", "instructions", "checkpoint_git")}
    fields.update(task="Task " * 100, changed_files=["file.py"], usage=[])
    run = summary(store, **fields)
    assert not (set(fields) - {"task", "changed_files", "usage"}) & set(run)
    assert len(run["task"]) == 400
    assert run["changed_files_count"] == 1
    assert store.run("run_summary")["diff"] == fields["diff"]
    assert store.run("run_summary")["task"] == fields["task"]


def test_summary_api_preserves_unknown_usage_and_full_run_evidence(local_app):
    client, _, _, store, _ = local_app
    saved = {"id": "run_summary", "state": "DONE", "task": "Task", "calls": 2,
             "usage": [None, {"last": {"total_tokens": 12}}], "diff": "saved diff"}
    store.save_run(saved)
    response = client.get("/api/runs?summary=true")
    assert response.status_code == 200
    run = response.json()["items"][0]
    assert run["usage_total"] == {"input": None, "output": None, "cached": None, "total": 12}
    assert run["usage_complete"] is False
    assert client.get("/api/runs/run_summary").json()["usage"] == saved["usage"]
