import hashlib
import json
from pathlib import Path

import pytest

from codex_team.workspace import WorkspaceError

import codex_team.context as module
from codex_team.context import ContextManager


def run_for(root):
    return {"workspace": str(root), "original_workspace": str(root), "worktree": str(root),
            "pipeline": ["coordinator", "analyst", "architect", "developer", "documentation", "security", "reviewer", "qa"],
            "results": {}, "task": "Implement clamp with invalid-range handling", "mode": "deep", "iteration": 2,
            "checkpoint_git": {"head": "a" * 40}, "instructions": ["Keep the public signature"]}


def artifact(verdict="ANALYSIS", summary="Evidence"):
    return {"verdict": verdict, "summary": summary, "acceptance_criteria": ["Bounds inclusive", "Invalid range raises"],
            "relevant_files": ["number_utils.py", "test_number_utils.py"], "tests": []}


def payload(manager, run, role="qa", diff=None):
    return json.loads(manager.build(run, role, diff or {}) .split("\n", 1)[1])


@pytest.mark.parametrize("role", ["qa", "reviewer"])
def test_targeted_verification_contains_task_acceptance_diff_files_and_previous_test_output(tmp_path, role):
    run = run_for(tmp_path)
    run["results"] = {"developer": artifact("IMPLEMENTED"), "qa": artifact("FAIL"),
                      "documentation": artifact(summary="UNRELATED SECRET DESIGN")}
    run["results"]["qa"]["tests"] = [{"command": "python -m unittest", "exit_code": 1, "output": "Ran 4 tests\nFAILED"}]
    actual = payload(ContextManager(), run, role, {"diff": "CURRENT PATCH", "changed_files": ["number_utils.py"]})
    assert actual["original_task"] == run["task"]
    assert actual["acceptance_criteria"] == ["Bounds inclusive", "Invalid range raises"]
    assert actual["relevant_files"] == ["number_utils.py", "test_number_utils.py"]
    assert actual["diff"] == "CURRENT PATCH"
    assert "Ran 4 tests" in actual["prior_test_results"]["qa"][0]["output"]
    assert "documentation" not in actual["artifacts"]
    assert "untrusted" in actual["artifact_trust"]
    assert actual["experimental_parallel_specialists"]["enabled"] is False


def test_failed_specialist_retained_for_repair_and_review(tmp_path):
    run = run_for(tmp_path)
    run["results"] = {"security": artifact("FAIL", "Critical evidence"), "documentation": artifact()}
    for role in ("developer", "qa", "reviewer"):
        actual = payload(ContextManager(), run, role)
        assert actual["artifacts"]["security"]["summary"] == "Critical evidence"
        assert "documentation" not in actual["artifacts"]


def memory(root, fingerprint, text):
    folder = root / ".ai-team"
    folder.mkdir(exist_ok=True)
    (folder / "project_summary.md").write_text(text, encoding="utf-8")
    (folder / "project_summary.meta.json").write_text(json.dumps({**fingerprint, "summary_hash": hashlib.sha256(text.encode()).hexdigest()}), encoding="utf-8")


@pytest.mark.parametrize("changed", ["head", "diff", "workspace", "summary"])
def test_project_memory_cache_invalidated_by_current_workspace_head_diff_or_text(tmp_path, changed):
    run = run_for(tmp_path)
    manager = ContextManager()
    first = payload(manager, run)
    memory(tmp_path, first["workspace_fingerprint"], "Current verified summary")
    assert payload(manager, run)["project_summary"] == "Current verified summary"
    diff = {}
    if changed == "head":
        run["checkpoint_git"]["head"] = "b" * 40
    elif changed == "diff":
        diff = {"diff": "New code"}
    elif changed == "workspace":
        worktree = tmp_path / "new-worktree"
        worktree.mkdir()
        run["worktree"] = str(worktree)
    else:
        (tmp_path / ".ai-team/project_summary.md").write_text("Injected stale summary", encoding="utf-8")
    actual = payload(manager, run, diff=diff)
    assert actual["project_summary"] == ""
    assert actual["project_memory"]["status"] == "stale"


def test_legacy_summary_without_fingerprint_is_not_reused(tmp_path):
    run = run_for(tmp_path)
    (tmp_path / ".ai-team").mkdir()
    (tmp_path / ".ai-team/project_summary.md").write_text("Old repository summary", encoding="utf-8")
    actual = payload(ContextManager(), run)
    assert actual["project_memory"]["status"] == "unverified"
    assert actual["project_summary"] == ""


def test_memory_metadata_parent_traversal_refused(tmp_path):
    run = run_for(tmp_path)
    original_resolver = module.WorkspaceManager.resolve_inside
    # Exercise the actual containment guard without relying on Windows symlink privileges.
    with pytest.raises(WorkspaceError):
        original_resolver(tmp_path, ".ai-team/../../outside/project_summary.meta.json")


def test_no_snapshot_does_not_claim_verified_git(tmp_path):
    run = run_for(tmp_path)
    run.pop("checkpoint_git")
    assert payload(ContextManager(), run)["git_verified_by_orchestrator"] is False


def test_prior_native_outputs_are_distinct_from_model_claims_and_bounded(tmp_path):
    run = run_for(tmp_path)
    run["results"] = {"developer": artifact("IMPLEMENTED"), "qa": artifact("FAIL")}
    run["executions"] = {"qa": [{"command": "python -m unittest", "status": "completed", "exit_code": 1, "output": "FAILED\n" + "x" * 20000}]}
    actual = payload(ContextManager(), run)
    execution = actual["prior_native_executions"]["qa"][0]
    assert execution["exit_code"] == 1
    assert len(execution["output"]) == 16000
    assert execution["output_truncated"]
    assert "model artifacts" in actual["acceptance_source"]


def test_registered_argv_commands_are_in_context_without_host_execution(tmp_path):
    run = run_for(tmp_path)
    run["project_commands"] = {"test": ["python", "-m", "unittest"]}
    prompt = ContextManager().build(run, "qa", {})
    assert payload(ContextManager(), run)["configured_commands"] == run["project_commands"]
    assert "native Codex execution" in prompt
    assert "no host execution bridge" in prompt
