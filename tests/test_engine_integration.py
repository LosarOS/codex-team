import json
from pathlib import Path
import threading
import time
from types import SimpleNamespace

import pytest
import codex_team.engine

from test_engine import rig, result, standard_results, git
from codex_team.actions import COMMAND, FILE, PERMISSIONS
from codex_team.provider import FakeCodexProvider, ProviderError


@pytest.fixture
def engine_module():
    return codex_team.engine


def test_run_provider_is_saved_at_creation_and_never_follows_later_settings(rig, engine_module, monkeypatch):
    make, _, _, store = rig
    store.save_settings({"execution_backend": "openai_api"})
    engine, run = make(FakeCodexProvider(standard_results()))
    assert run["execution_backend"] == "openai_api"
    store.save_settings({"execution_backend": "codex_chatgpt"})
    captured = []
    monkeypatch.setattr(engine_module, "CodexProvider", lambda root, **options: captured.append(options) or FakeCodexProvider(standard_results()))
    engine.provider_factory = None
    engine.launch(run["id"], background=False)
    assert captured[0]["backend"] == "openai_api"
    assert captured[0]["secret_store"] is engine.secret_store


def test_role_defaults_and_modes_are_applied_without_overriding_agent_model(rig):
    make, _, _, store = rig
    store.save_settings({"model": "global-model", "reasoning_effort": "low",
                         "role_model_defaults": {"qa": {"model": "qa-model", "reasoning_effort": "high"}}})
    engine, run = make(FakeCodexProvider(standard_results()))
    assert run["agents"]["qa"]["model"] == "qa-model"
    assert run["agents"]["qa"]["reasoning_effort"] == "high"
    assert run["agents"]["developer"]["model"] == "global-model"


def test_own_developer_edit_saved_before_user_decision_same_thread_resume(rig):
    class EditingProvider(FakeCodexProvider):
        def execute(self, agent, workspace, prompt, schema, thread_id, on_event, on_thread, cancel):
            if agent["name"] == "developer":
                (Path(workspace) / "original.txt").write_text("owned stage edit\n", encoding="utf-8")
            return super().execute(agent, workspace, prompt, schema, thread_id, on_event, on_thread, cancel)
    make, _, _, store = rig
    provider = EditingProvider(standard_results()[:2] + [result("USER_DECISION_REQUIRED")])
    engine, run = make(provider)
    blocked = engine.launch(run["id"], background=False)
    assert blocked["stage"] == 2
    assert blocked["state"] == "USER_DECISION_REQUIRED"
    assert "original.txt" in blocked["checkpoint_git"]["file_hashes"]
    assert store.actions(run["id"], "pending")[0]["kind"] == "product"
    tid = blocked["threads"]["developer"]
    provider.results = standard_results()[2:]
    finished = engine.launch(run["id"], background=False)
    assert finished["state"] == "DONE", finished["error"]
    assert finished["threads"]["developer"] == tid


def test_external_change_rejection_does_not_advance_saved_checkpoint(rig):
    make, _, _, store = rig
    engine, run = make(FakeCodexProvider(standard_results()), max_agent_calls=2)
    blocked = engine.launch(run["id"], background=False)
    checkpoint = blocked["checkpoint_git"]
    (Path(blocked["worktree"]) / "original.txt").write_text("external tamper\n", encoding="utf-8")
    blocked["max_agent_calls"] = 8
    store.save_run(blocked)
    retried = engine.launch(run["id"], background=False)
    assert retried["state"] == "USER_DECISION_REQUIRED"
    assert retried["checkpoint_git"] == checkpoint
    assert "outside the saved checkpoint" in retried["error"]


@pytest.mark.parametrize("method,params,agent", [
    (COMMAND, {"command": "python -m unittest"}, {"can_execute": False, "permission": "read-only"}),
    (FILE, {}, {"can_execute": True, "permission": "read-only"}),
    (PERMISSIONS, {"permissions": {"fileSystem": {"write": ["C:/project/output"]}}}, {"permission": "read-only"}),
    (PERMISSIONS, {"permissions": {"network": {"enabled": True}}}, {"permission": "read-only", "can_network": True}),
])
def test_core_role_gate_cannot_receive_disabled_native_capabilities(rig, method, params, agent):
    make, _, _, store = rig
    engine, run = make(FakeCodexProvider(standard_results()))
    engine.actions.request = lambda *args, **kwargs: kwargs
    control = {"cancel": threading.Event()}
    narrowed = engine._approval(run["id"], "qa", agent, control, method, params)
    assert narrowed["grant_allowed"] is False
    assert narrowed["limitation"]


def test_resolve_native_action_returns_only_exact_live_grant(rig):
    make, _, _, store = rig
    engine, run = make(FakeCodexProvider(standard_results()))
    response = []
    worker = threading.Thread(target=lambda: response.append(engine.actions.request(run["id"], "developer", COMMAND, {"command": "pytest"}, timeout=2)))
    worker.start()
    deadline = time.monotonic() + 1
    while not store.actions(run["id"], "pending"):
        assert time.monotonic() < deadline
        time.sleep(.01)
    card = store.actions(run["id"], "pending")[0]
    engine.resolve_action(card["id"], "allow_once", confirmed=True)
    worker.join(1)
    assert response == [{"decision": "accept"}]


def test_product_resume_adds_confirmed_total_budget_and_instruction_after_acceptance(rig, monkeypatch):
    make, _, _, store = rig
    engine, run = make(FakeCodexProvider(standard_results()), max_agent_calls=2)
    engine.launch(run["id"], background=False)
    card = store.actions(run["id"], "pending")[0]
    accepted = []
    monkeypatch.setattr(engine, "launch", lambda run_id: accepted.append(store.run(run_id)))
    engine.resolve_action(card["id"], "resume", instruction="Proceed with saved acceptance criteria", budget={"max_agent_calls": 7}, confirmed=True)
    assert accepted[0]["max_agent_calls"] == 7
    assert accepted[0]["instructions"][-1] == "Proceed with saved acceptance criteria"
    assert store.action(card["id"])["status"] == "resolved"


def test_product_launch_error_keeps_pending_card_and_original_budget(rig, monkeypatch):
    make, _, _, store = rig
    engine, run = make(FakeCodexProvider(standard_results()), max_agent_calls=2)
    engine.launch(run["id"], background=False)
    card = store.actions(run["id"], "pending")[0]
    monkeypatch.setattr(engine, "launch", lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("Another run is active")))
    with pytest.raises(ValueError, match="active"):
        engine.resolve_action(card["id"], "resume", instruction="Continue", budget={"max_agent_calls": 7}, confirmed=True)
    assert store.action(card["id"])["status"] == "pending"
    assert store.run(run["id"])["max_agent_calls"] == 2
    assert not store.run(run["id"])["instructions"]


@pytest.mark.parametrize("budget,confirmed", [({"max_agent_calls": 1000}, True), ({"unknown": 7}, True), ({"max_agent_calls": True}, True)])
def test_budget_change_requires_confirmation_and_valid_explicit_total_bounds(rig, budget, confirmed):
    make, _, _, store = rig
    engine, run = make(FakeCodexProvider(standard_results()), max_agent_calls=2)
    engine.launch(run["id"], background=False)
    card = store.actions(run["id"], "pending")[0]
    with pytest.raises(ValueError):
        engine.resolve_action(card["id"], "resume", budget=budget, confirmed=confirmed)
    assert store.action(card["id"])["status"] == "pending"


def test_product_explain_queues_instruction_and_preserves_all_budgets(rig, monkeypatch):
    make, _, _, store = rig
    engine, run = make(FakeCodexProvider(standard_results()), max_agent_calls=2)
    blocked = engine.launch(run["id"], background=False)
    card = store.actions(run["id"], "pending")[0]
    monkeypatch.setattr(engine, "launch", lambda *args, **kwargs: None)
    engine.resolve_action(card["id"], "explain")
    actual = store.run(run["id"])
    assert actual["instructions"][-1].startswith("Explain why this run is blocked")
    assert actual["max_agent_calls"] == blocked["max_agent_calls"]


def test_product_stop_inactive_resolves_card_and_preserves_artifacts(rig):
    make, _, _, store = rig
    engine, run = make(FakeCodexProvider(standard_results()), max_agent_calls=2)
    blocked = engine.launch(run["id"], background=False)
    card = store.actions(run["id"], "pending")[0]
    resolved = engine.resolve_action(card["id"], "stop")
    assert resolved["status"] == "resolved"
    assert store.run(run["id"])["state"] == "STOPPED"
    assert store.run(run["id"])["results"] == blocked["results"]
    assert not store.actions(run["id"], "pending")


def test_clean_worktree_delete_retains_history_and_blocks_resume(rig):
    make, _, _, store = rig
    engine, run = make(FakeCodexProvider(standard_results()))
    finished = engine.launch(run["id"], background=False)
    deleted = engine.delete_worktree(run["id"])
    assert deleted["worktree_deleted"]
    assert deleted["worktree"] == finished["worktree"]
    assert not Path(deleted["worktree"]).exists()
    assert store.run(run["id"])["results"] == finished["results"]
    with pytest.raises(ValueError, match="deleted"):
        engine.launch(run["id"])


def test_dirty_worktree_and_forged_deletion_target_preserved(rig):
    make, repo, _, store = rig
    engine, run = make(FakeCodexProvider(standard_results()))
    finished = engine.launch(run["id"], background=False)
    target = Path(finished["worktree"])
    (target / "original.txt").write_text("valuable user edit", encoding="utf-8")
    with pytest.raises(ValueError, match="Dirty"):
        engine.delete_worktree(run["id"])
    assert target.exists()
    finished["worktree"] = str(repo)
    store.save_run(finished)
    with pytest.raises(ValueError, match="exact run path"):
        engine.delete_worktree(run["id"])
    assert repo.exists()


def test_stopped_native_owned_edit_can_resume_but_unattributed_change_is_not_blessed(rig):
    class NativeEditingProvider(FakeCodexProvider):
        def execute(self, agent, workspace, prompt, schema, thread_id, on_event, on_thread, cancel):
            if agent["name"] == "developer":
                path = Path(workspace) / "original.txt"
                path.write_text("owned partial native edit\n", encoding="utf-8")
                on_event("item/completed", {"item": {"type": "fileChange", "status": "completed", "changes": [{"path": str(path)}]}})
                raise ProviderError("INTERRUPTED", "Interrupted after native file change")
            return super().execute(agent, workspace, prompt, schema, thread_id, on_event, on_thread, cancel)
    make, _, _, store = rig
    provider = NativeEditingProvider(standard_results())
    engine, run = make(provider)
    interrupted = engine.launch(run["id"], background=False)
    assert interrupted["state"] == "INTERRUPTED"
    assert "original.txt" in interrupted["checkpoint_git"]["file_hashes"]
    assert any(event["type"] == "owned_partial_checkpoint" for event in store.events(run["id"]))
    engine.provider_factory = lambda: FakeCodexProvider(standard_results()[2:])
    finished = engine.launch(run["id"], background=False)
    assert finished["state"] == "DONE", finished.get("error")


@pytest.mark.parametrize("actual_hash,accepted", [("native-content", True), ("external-tamper", False)])
def test_partial_checkpoint_requires_exact_native_completion_content(tmp_path, actual_hash, accepted):
    engine = codex_team.engine.Engine.__new__(codex_team.engine.Engine)
    before = {"head": "a" * 40, "file_hashes": {"src/utils.py": "baseline"}}
    after = {"head": "a" * 40, "file_hashes": {"src/utils.py": actual_hash}}
    engine.workspace = SimpleNamespace(diff=lambda *args: {"diff": "partial native edit"})
    engine._checkpoint = lambda *args: after
    engine.store = SimpleNamespace(event=lambda *args: None)
    run = {"id": "run_partial", "workspace": str(tmp_path), "state": "INTERRUPTED", "checkpoint_git": before}
    control = {"stage_writer": True, "stage_before": before, "owned_paths": {"src/utils.py"},
               "owned_hashes": {"src/utils.py": "native-content"}}
    engine._preserve_interrupted_edits(run, control)
    assert run["checkpoint_git"] == (after if accepted else before)


@pytest.mark.parametrize("enabled,allowed", [(True, True), (False, False)])
def test_developer_network_permission_honors_explicit_user_capability(enabled, allowed):
    engine = codex_team.engine.Engine.__new__(codex_team.engine.Engine)
    engine.actions = SimpleNamespace(request=lambda *args, **kwargs: kwargs)
    agent = {"permission": "workspace-write", "can_network": enabled}
    result = engine._approval("run_test", "developer", agent, {"cancel": threading.Event()}, PERMISSIONS,
                              {"permissions": {"network": {"enabled": True}}})
    assert result["grant_allowed"] is allowed
