import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading

import pytest

from codex_team.engine import Engine
from codex_team.models import RunRequest
from codex_team.provider import FakeCodexProvider, ProviderError
from codex_team.storage import Store
from codex_team.context import ContextManager
from codex_team.lease import AppLease
from codex_team.workspace import WorkspaceError

ROOT = Path(__file__).resolve().parents[1]


def result(verdict, *, findings=False, tests=True, summary="Evidence-backed result"):
    return {"verdict": verdict, "summary": summary, "plan": ["Implement requested behavior"],
            "acceptance_criteria": ["Relevant checks pass"], "relevant_files": ["original.txt"],
            "build_commands": [], "tests": [{"command": "pytest -q", "exit_code": 0, "output": "1 passed"}] if tests else [],
            "findings": [{"severity": "high", "file": "original.txt", "problem": "Missing behavior",
                          "evidence": "Observed failing regression test", "expected_behavior": "Test passes",
                          "suggested_fix": "Implement missing behavior"}] if findings else [],
            "assumptions": [], "specialists": [],
            "project_map": {name: [] for name in ("modules", "entry_points", "important_files", "dependencies", "tests",
                                                 "build_commands", "runtime_commands", "architecture_notes")}}


def git(root, *args):
    completed = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, encoding="utf-8")
    assert completed.returncode == 0, completed.stderr
    return completed.stdout.strip()


@pytest.fixture
def rig(tmp_path):
    repo = tmp_path / "project"
    repo.mkdir()
    git(repo, "init")
    git(repo, "config", "user.name", "Test User")
    git(repo, "config", "user.email", "test@example.invalid")
    (repo / "original.txt").write_text("baseline\n", encoding="utf-8")
    git(repo, "add", "original.txt")
    git(repo, "commit", "-m", "Initial")
    app = tmp_path / "app"
    app.mkdir()
    for folder in ("agents", "packs"):
        shutil.copytree(ROOT / folder, app / folder)
    store = Store(app / "state.db")
    engines = []

    def make(provider, **options):
        engine = Engine(app, store, provider_factory=lambda: provider)
        engines.append(engine)
        request = RunRequest(workspace=str(repo), task="Fix requested behavior", **options)
        return engine, engine.create(request)

    yield make, repo, app, store
    for engine in engines:
        engine.close()
    store.close()


def standard_results():
    return [result("PLAN"), result("ANALYSIS"), result("IMPLEMENTED"), result("PASS"), result("APPROVED")]


def test_standard_independent_threads_persist_usage_and_artifacts(rig):
    make, repo, app, store = rig
    provider = FakeCodexProvider(standard_results())
    engine, run = make(provider)
    finished = engine.launch(run["id"], background=False)
    assert finished["state"] == "DONE", finished.get("error")
    assert finished["calls"] == 5
    assert finished["stage"] == 5
    assert len(set(finished["threads"].values())) == 5
    assert [c["agent"] for c in provider.calls] == ["coordinator", "analyst", "developer", "qa", "reviewer"]
    assert len(finished["usage"]) == 5
    assert finished["worktree"] != str(repo)
    assert Path(finished["worktree"]).is_dir()
    assert git(repo, "status", "--porcelain") == ""
    artifact = app / ".ai-team" / "runs" / run["id"] / "state.json"
    assert json.loads(artifact.read_text(encoding="utf-8"))["state"] == "DONE"
    assert Path(finished["workspace"], ".ai-team", "artifacts", run["id"], "result.json").is_file()
    assert [e["type"] for e in store.events(run["id"])].count("agent_completed") == 5


@pytest.mark.parametrize("rejected_role,rejected_verdict", [("qa", "FAIL"), ("reviewer", "CHANGES_REQUIRED")])
def test_repair_reruns_validation_tail_and_resumes_developer_thread(rig, rejected_role, rejected_verdict):
    make, _, _, _ = rig
    responses = standard_results()
    index = 3 if rejected_role == "qa" else 4
    responses = responses[:index] + [result(rejected_verdict, findings=True)] + standard_results()[2:]
    provider = FakeCodexProvider(responses)
    engine, run = make(provider)
    finished = engine.launch(run["id"], background=False)
    assert finished["state"] == "DONE", finished.get("error")
    assert finished["iteration"] == 2
    developers = [c for c in provider.calls if c["agent"] == "developer"]
    assert len(developers) == 2
    assert developers[0]["thread_id"] == developers[1]["thread_id"]
    assert rejected_verdict in developers[1]["prompt"]
    assert [c["agent"] for c in provider.calls][-3:] == ["developer", "qa", "reviewer"]
    assert finished["result_history"][index]["result"]["findings"]


def test_iteration_limit_retains_findings_and_requires_decision(rig):
    make, _, _, _ = rig
    provider = FakeCodexProvider(standard_results()[:3] + [result("FAIL", findings=True)])
    engine, run = make(provider, max_iterations=1)
    finished = engine.launch(run["id"], background=False)
    assert finished["state"] == "USER_DECISION_REQUIRED"
    assert "iteration limit" in finished["error"]
    assert finished["results"]["qa"]["findings"]
    assert finished["calls"] == 4


def test_call_budget_stops_before_next_turn(rig):
    make, _, _, _ = rig
    provider = FakeCodexProvider(standard_results())
    engine, run = make(provider, max_agent_calls=2)
    finished = engine.launch(run["id"], background=False)
    assert finished["state"] == "USER_DECISION_REQUIRED"
    assert finished["calls"] == 2
    assert len(provider.calls) == 2
    assert "budget" in finished["error"]


def test_auth_required_never_runs_agent_or_prepares_worktree(rig):
    make, _, _, _ = rig
    provider = FakeCodexProvider(standard_results(), connected=False)
    engine, run = make(provider)
    finished = engine.launch(run["id"], background=False)
    assert finished["state"] == "AUTH_REQUIRED"
    assert not provider.calls
    assert not finished.get("prepared")
    assert finished["worktree"] is None


@pytest.mark.parametrize("invalid", [{"verdict": "PLAN"}, result("APPROVED"), result("FAIL")])
def test_malformed_or_wrong_role_result_fails_and_preserves_usage(rig, invalid):
    make, _, _, _ = rig
    provider = FakeCodexProvider([invalid])
    engine, run = make(provider)
    finished = engine.launch(run["id"], background=False)
    assert finished["state"] == "FAILED"
    assert finished["stage"] == 0
    assert finished["usage"][0]["agent"] == "coordinator"
    assert finished["threads"]["coordinator"]


@pytest.mark.parametrize("test_evidence", [[], [{"command": "pytest", "exit_code": 1, "output": "FAILED"}],
                                         [{"command": "pytest", "exit_code": None, "output": "Not executed"}]])
def test_qa_pass_requires_actual_successful_test_evidence(rig, test_evidence):
    make, _, _, _ = rig
    qa = result("PASS")
    qa["tests"] = test_evidence
    provider = FakeCodexProvider(standard_results()[:3] + [qa])
    engine, run = make(provider)
    finished = engine.launch(run["id"], background=False)
    assert finished["state"] == "USER_DECISION_REQUIRED"
    assert "test evidence" in finished["error"]
    assert not any(c["agent"] == "reviewer" for c in provider.calls)


def test_audit_reports_findings_without_developer_or_write_access(rig):
    make, _, _, _ = rig

    class AuditProvider(FakeCodexProvider):
        def execute(self, agent, *args, **kwargs):
            assert agent["permission"] == "read-only"
            return super().execute(agent, *args, **kwargs)

    provider = AuditProvider()
    engine, run = make(provider, mode="audit")
    verdicts = {"coordinator": "PLAN", "analyst": "ANALYSIS", "reviewer": "CHANGES_REQUIRED",
                "qa": "FAIL", "final-audit": "CHANGES_REQUIRED"}
    provider.results = [result(verdicts.get(role, "ANALYSIS"), findings=role in {"reviewer", "qa", "final-audit"})
                        for role in run["pipeline"]]
    finished = engine.launch(run["id"], background=False)
    assert finished["state"] == "DONE", finished.get("error")
    assert "developer" not in finished["pipeline"]
    assert finished["iteration"] == 1
    assert finished["results"]["reviewer"]["findings"]


def test_resume_after_provider_error_does_not_replay_completed_stages(rig):
    make, _, app, store = rig
    first = FakeCodexProvider(standard_results()[:2] + [ProviderError("USAGE_LIMIT", "Limit reached")])
    engine, run = make(first)
    interrupted = engine.launch(run["id"], background=False)
    assert interrupted["state"] == "USAGE_LIMIT"
    assert interrupted["stage"] == 2
    developer_thread = interrupted["threads"]["developer"]
    second = FakeCodexProvider(standard_results()[2:])
    restarted = Engine(app, store, provider_factory=lambda: second)
    finished = restarted.launch(run["id"], background=False)
    assert finished["state"] == "DONE", finished.get("error")
    assert [c["agent"] for c in second.calls] == ["developer", "qa", "reviewer"]
    assert second.calls[0]["thread_id"] == developer_thread
    assert finished["calls"] == 6


class BlockingProvider(FakeCodexProvider):
    def __init__(self, responses):
        super().__init__(responses)
        self.entered = threading.Event()
        self.release = threading.Event()
        self.steered = []
        self.block_first = True

    def execute(self, *args, **kwargs):
        if self.block_first:
            self.block_first = False
            self.entered.set()
            assert self.release.wait(10), "Test controller did not release provider"
        return super().execute(*args, **kwargs)

    def interrupt(self):
        super().interrupt()
        self.release.set()

    def steer(self, instruction):
        self.steered.append(instruction)
        return True


def test_pause_finishes_stage_then_resume_keeps_checkpoint_and_instruction(rig):
    make, _, _, store = rig
    provider = BlockingProvider(standard_results())
    engine, run = make(provider)
    engine.launch(run["id"])
    assert provider.entered.wait(10)
    worker = engine.active[run["id"]]["worker"]
    engine.control(run["id"], "queue", "Preserve public interfaces")
    engine.control(run["id"], "steer", "Add regression coverage")
    engine.control(run["id"], "pause")
    provider.release.set()
    worker.join(timeout=10)
    assert not worker.is_alive()
    paused = store.run(run["id"])
    assert paused["state"] == "PAUSED"
    assert paused["stage"] == 1
    assert paused["instructions"] == ["Preserve public interfaces", "Add regression coverage"]
    assert provider.steered == ["Add regression coverage"]
    finished = engine.launch(run["id"], background=False)
    assert finished["state"] == "DONE", finished.get("error")
    assert [c["agent"] for c in provider.calls].count("coordinator") == 1
    assert "Preserve public interfaces" in provider.calls[1]["prompt"]


def test_stop_interrupts_current_turn_and_single_writer_is_enforced(rig):
    make, _, _, store = rig
    provider = BlockingProvider(standard_results())
    engine, run = make(provider)
    second = engine.create(RunRequest(workspace=run["workspace"], task="Second task"))
    engine.launch(run["id"])
    assert provider.entered.wait(10)
    worker = engine.active[run["id"]]["worker"]
    with pytest.raises(ValueError, match="Another run"):
        engine.launch(second["id"])
    engine.control(run["id"], "stop")
    worker.join(timeout=10)
    assert not worker.is_alive()
    assert store.run(run["id"])["state"] == "STOPPED"
    assert provider.interrupted
    assert store.run(run["id"])["stage"] == 0


def test_denied_approval_requires_decision_before_advancing(rig):
    make, _, _, _ = rig

    class DeniedProvider(FakeCodexProvider):
        def execute(self, *args, **kwargs):
            response = super().execute(*args, **kwargs)
            response["denied"] = True
            return response

    provider = DeniedProvider([result("PLAN", summary="Permission required")])
    engine, run = make(provider)
    finished = engine.launch(run["id"], background=False)
    assert finished["state"] == "USER_DECISION_REQUIRED"
    assert finished["error"] == "Permission required"
    assert finished["stage"] == 0


def test_resumed_duration_budget_exhausted_before_auth_or_agent(rig):
    make, _, _, store = rig
    provider = FakeCodexProvider(standard_results())
    engine, run = make(provider, max_run_duration=30)
    run["elapsed_seconds"] = 31
    store.save_run(run)
    finished = engine.launch(run["id"], background=False)
    assert finished["state"] == "USER_DECISION_REQUIRED"
    assert "duration budget" in finished["error"]
    assert not provider.calls


def test_resume_rejects_changed_head_before_replaying_stage(rig):
    make, _, _, _ = rig
    provider = FakeCodexProvider([ProviderError("USAGE_LIMIT", "Limit reached")])
    engine, run = make(provider)
    interrupted = engine.launch(run["id"], background=False)
    cwd = Path(interrupted["worktree"])
    (cwd / "original.txt").write_text("external change\n", encoding="utf-8")
    git(cwd, "add", "original.txt")
    git(cwd, "commit", "-m", "External change")
    calls = len(provider.calls)
    finished = engine.launch(run["id"], background=False)
    assert finished["state"] == "USER_DECISION_REQUIRED"
    assert "HEAD changed" in finished["error"]
    assert len(provider.calls) == calls
    assert (cwd / "original.txt").read_text(encoding="utf-8") == "external change\n"


def test_session_lease_excludes_competing_engine_and_releases_on_close(rig):
    make, _, app, store = rig
    first, _ = make(FakeCodexProvider())
    second = Engine(app, store, provider_factory=FakeCodexProvider)
    try:
        first.acquire_session()
        with pytest.raises(ValueError, match="another process"):
            second.acquire_session()
        first.close()
        second.acquire_session()
        assert second.lease is not None
    finally:
        first.close()
        second.close()


def test_process_lease_is_released_after_unclean_exit(tmp_path):
    script = ("import os,sys; from pathlib import Path; from codex_team.lease import AppLease; "
              "lease=AppLease(Path(sys.argv[1])); print('ready',flush=True); sys.stdin.read(1); os._exit(17)")
    child = subprocess.Popen([sys.executable, "-c", script, str(tmp_path)], cwd=ROOT,
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        assert child.stdout.readline().strip() == "ready"
        with pytest.raises(ValueError, match="another process"):
            AppLease(tmp_path)
        _, stderr = child.communicate("x", timeout=10)
        assert child.returncode == 17, stderr
        lease = AppLease(tmp_path)
        lease.close()
    finally:
        if child.poll() is None:
            child.kill()
            child.communicate(timeout=10)


def test_deep_specialist_failure_reaches_developer_and_is_rechecked(rig):
    make, _, _, _ = rig

    class SpecialistProvider(FakeCodexProvider):
        def __init__(self):
            super().__init__()
            self.security_calls = 0

        def execute(self, agent, *args, **kwargs):
            role = agent["name"]
            verdict = {"coordinator": "PLAN", "analyst": "ANALYSIS", "developer": "IMPLEMENTED",
                       "qa": "PASS", "reviewer": "APPROVED", "final-audit": "APPROVED"}.get(role, "ANALYSIS")
            if role == "security":
                self.security_calls += 1
                if self.security_calls == 1:
                    verdict = "FAIL"
            self.results = [result(verdict, findings=verdict == "FAIL", summary="Security evidence" if role == "security" else "Result")]
            return super().execute(agent, *args, **kwargs)

    provider = SpecialistProvider()
    engine, run = make(provider, mode="deep")
    required = set(run["pipeline"])
    finished = engine.launch(run["id"], background=False)
    assert finished["state"] == "DONE", finished.get("error")
    developers = [c for c in provider.calls if c["agent"] == "developer"]
    assert "Security evidence" in developers[0]["prompt"]
    assert "Observed failing regression test" in developers[0]["prompt"]
    assert provider.security_calls == 2
    assert finished["results"]["security"]["verdict"] == "ANALYSIS"
    roles = [c["agent"] for c in provider.calls]
    assert roles.index("developer") < max(i for i, r in enumerate(roles) if r == "security") < roles.index("qa")
    assert required <= set(finished["results"]), "Required specialists were skipped after an earlier specialist failed"


@pytest.mark.parametrize("binary", [False, True])
def test_paused_external_uncommitted_change_refuses_resume(rig, binary):
    make, _, _, store = rig
    filename = "asset.bin" if binary else "original.txt"
    saved_content = b"\x00a" if binary else b"agent edit\n"
    external_content = b"\x00b" if binary else b"outside edit\n"

    class EditingProvider(BlockingProvider):
        def __init__(self, responses):
            super().__init__(responses)
            self.block_first = False
        def execute(self, agent, workspace, *args, **kwargs):
            if agent["name"] == "developer":
                self.entered.set()
                assert self.release.wait(20), "Test controller did not release Developer"
            response = super().execute(agent, workspace, *args, **kwargs)
            if agent["name"] == "developer":
                (Path(workspace) / filename).write_bytes(saved_content)
            return response

    provider = EditingProvider(standard_results())
    engine, run = make(provider)
    engine.launch(run["id"])
    assert provider.entered.wait(20)
    worker = engine.active[run["id"]]["worker"]
    engine.control(run["id"], "pause")
    provider.release.set()
    worker.join(timeout=10)
    assert not worker.is_alive()
    paused = store.run(run["id"])
    assert paused["state"] == "PAUSED"
    file = Path(paused["worktree"]) / filename
    file.write_bytes(external_content)
    count = len(provider.calls)
    finished = engine.launch(run["id"], background=False)
    assert finished["state"] == "USER_DECISION_REQUIRED"
    assert "outside the saved checkpoint" in finished["error"]
    assert len(provider.calls) == count
    assert file.read_bytes() == external_content


@pytest.mark.parametrize("link_kind", ["symlink", "junction"])
def test_project_summary_link_escape_is_refused(tmp_path, link_kind):
    project, outside = tmp_path / "project", tmp_path / "outside"
    project.mkdir()
    outside.mkdir()
    (outside / "project_summary.md").write_text("PRIVATE OUTSIDE CONTENT", encoding="utf-8")
    link = project / ".ai-team"
    if link_kind == "junction":
        if os.name != "nt":
            pytest.skip("Windows junction test")
        created = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(outside)], capture_output=True, text=True)
        assert created.returncode == 0, created.stderr
    else:
        try:
            link.symlink_to(outside, target_is_directory=True)
        except OSError:
            pytest.skip("Windows symlinks need Developer Mode or privilege; junction checked separately")
    run = {"workspace": str(project), "pipeline": ["developer"], "results": {}, "task": "Task", "mode": "deep", "iteration": 1}
    with pytest.raises(WorkspaceError, match="escapes workspace"):
        ContextManager().build(run, "developer", {})


def test_usage_totals_are_per_thread_deltas_across_repair(rig):
    make, _, _, _ = rig

    class CumulativeProvider(FakeCodexProvider):
        def __init__(self, results):
            super().__init__(results)
            self.turns = {}

        def execute(self, agent, *args, **kwargs):
            response = super().execute(agent, *args, **kwargs)
            role = agent["name"]
            count = self.turns[role] = self.turns.get(role, 0) + 1
            response["usage"] = {"total": {"inputTokens": count * 10, "cachedInputTokens": count * 2,
                                             "outputTokens": count * 5, "totalTokens": count * 15},
                                 "last": {"totalTokens": 999}}
            return response

    provider = CumulativeProvider(standard_results()[:3] + [result("FAIL", findings=True)] + standard_results()[2:])
    engine, run = make(provider)
    finished = engine.launch(run["id"], background=False)
    assert finished["state"] == "DONE", finished.get("error")
    assert len(finished["usage"]) == 7
    assert sum(u["last"]["totalTokens"] for u in finished["usage"]) == 105
    assert sum(u["last"]["inputTokens"] for u in finished["usage"]) == 70
    assert sum(u["last"]["cachedInputTokens"] for u in finished["usage"]) == 14
    assert all(u["last"]["totalTokens"] == 15 for u in finished["usage"])


@pytest.mark.parametrize("executions", [[],
    [{"command": "echo hello", "status": "completed", "exit_code": 0}],
    [{"command": "echo pytest passed", "status": "completed", "exit_code": 0, "output": "13 passed"}],
    [{"command": 'python -c "print(\'13 passed\')"', "status": "completed", "exit_code": 0, "output": "13 passed"}],
    [{"command": "python -m unittest", "status": "completed", "exit_code": 0, "output": "Ran 0 tests\nOK"}],
    [{"command": "python -m unittest", "status": "completed", "exit_code": 0, "output": "Ran 1 test\nFAILED (failures=1)"}],
    [{"command": "pytest -q", "status": "inProgress", "exit_code": 0}],
    [{"command": "pytest -q", "status": "completed", "exit_code": 1}],
])
def test_qa_fabricated_pass_without_successful_native_test_event_is_blocked(rig, executions):
    make, _, _, _ = rig

    class FabricatedProvider(FakeCodexProvider):
        def execute(self, agent, *args, **kwargs):
            response = super().execute(agent, *args, **kwargs)
            if agent["name"] == "qa":
                response["executions"] = executions
            return response

    provider = FabricatedProvider(standard_results())
    engine, run = make(provider)
    finished = engine.launch(run["id"], background=False)
    assert finished["state"] == "USER_DECISION_REQUIRED"
    assert "native test" in finished["error"]
    assert finished["stage"] == 3
    assert not any(c["agent"] == "reviewer" for c in provider.calls)


def test_checkpoint_retries_transient_windows_permission_error(rig, monkeypatch):
    make, _, app, store = rig
    engine, run = make(FakeCodexProvider())
    replace = Path.replace
    attempts = []

    def scanner_locked(source, target):
        if source.name == "state.json.tmp":
            attempts.append(str(target))
            if len(attempts) <= 2:
                raise PermissionError(5, "Simulated temporary Windows scanner lock")
        return replace(source, target)

    monkeypatch.setattr(Path, "replace", scanner_locked)
    engine._save(run)
    artifact = app / ".ai-team" / "runs" / run["id"] / "state.json"
    assert len(attempts) == 3
    assert json.loads(artifact.read_text(encoding="utf-8"))["id"] == run["id"]
    assert store.run(run["id"])["state"] == "QUEUED"
    assert not artifact.with_name("state.json.tmp").exists()


def test_resumed_qa_context_requires_current_turn_test_execution(tmp_path):
    run = {"workspace": str(tmp_path), "pipeline": ["qa"], "results": {"qa": result("PASS")},
           "task": "Fix behavior", "mode": "standard", "iteration": 2, "threads": {"qa": "resumed-thread"}}
    prompt = ContextManager().build(run, "qa", {})
    assert "Every QA turn must independently rerun actual relevant tests in this turn" in prompt
    assert "earlier turns cannot satisfy current execution evidence" in prompt
    assert "diagnostic inspection commands" in prompt


def test_qa_cannot_omit_failed_native_test_when_another_command_passed(rig):
    make, _, _, _ = rig

    class ConcealedFailureProvider(FakeCodexProvider):
        def execute(self, agent, *args, **kwargs):
            response = super().execute(agent, *args, **kwargs)
            if agent["name"] == "qa":
                response["executions"] = [
                    {"command": "pytest full_suite", "status": "completed", "exit_code": 1, "output": "3 failed"},
                    {"command": "pytest one_test", "status": "completed", "exit_code": 0, "output": "1 passed"},
                ]
            return response

    provider = ConcealedFailureProvider(standard_results())
    engine, run = make(provider)
    finished = engine.launch(run["id"], background=False)
    assert finished["state"] == "USER_DECISION_REQUIRED"
    assert finished["stage"] == 3
    assert not any(c["agent"] == "reviewer" for c in provider.calls)
    assert finished["executions"]["qa"][0]["output"] == "3 failed"


@pytest.mark.parametrize("reset", ["access", "legacy-profile"])
def test_new_native_thread_restarts_cumulative_usage_without_losing_history(rig, reset):
    make, _, _, store = rig

    class CumulativeProvider(BlockingProvider):
        def execute(self, *args, **kwargs):
            response = super().execute(*args, **kwargs)
            response["usage"] = {"total": {"inputTokens": 10, "outputTokens": 5, "totalTokens": 15}}
            return response

    provider = CumulativeProvider([result("PLAN")])
    engine, run = make(provider)
    engine.launch(run["id"])
    assert provider.entered.wait(10)
    worker = engine.active[run["id"]]["worker"]
    engine.control(run["id"], "pause")
    provider.release.set()
    worker.join(10)
    paused = store.run(run["id"])
    assert paused["state"] == "PAUSED"
    old_thread = paused["threads"]["coordinator"]
    # Resume the same role after a user changes the native permission profile.
    paused["stage"] = 0
    store.save_run(paused)
    if reset == "access":
        engine.set_access(run["id"], "read-only")
    else:
        paused["access_profile_version"] = 0
        store.save_run(paused)
    provider.results = standard_results()
    finished = engine.launch(run["id"], background=False)
    assert finished["state"] == "DONE", finished.get("error")
    assert finished["threads"]["coordinator"] != old_thread
    assert len(finished["usage"]) == 6
    assert sum(item["last"]["totalTokens"] for item in finished["usage"]) == 90
    assert all(item["last"]["totalTokens"] == 15 for item in finished["usage"])


@pytest.mark.parametrize("failure", [ProviderError("USAGE_LIMIT", "Limit reached"),
                                     ProviderError("INTERRUPTED", "Cancelled"),
                                     RuntimeError("Transport disconnected")])
def test_failed_turn_preserves_observed_tokens_and_budget_blocks_resume(rig, failure):
    make, _, _, _ = rig

    class FailedUsageProvider(FakeCodexProvider):
        def execute(self, agent, workspace, prompt, schema, thread_id, on_event, on_thread, cancel):
            on_thread(thread_id or "observed-thread")
            self.calls.append({"agent": agent["name"]})
            # These are SDK observations, not estimates or account-wide quota.
            on_event("thread/tokenUsage/updated", {"tokenUsage": {
                "total": {"inputTokens": 80, "outputTokens": 20, "totalTokens": 100},
                "last": {"totalTokens": 100}}})
            raise failure

    provider = FailedUsageProvider()
    engine, run = make(provider, max_total_tokens=100)
    failed = engine.launch(run["id"], background=False)
    assert failed["state"] == (failure.code if isinstance(failure, ProviderError) else "FAILED")
    assert failed["stage"] == 0
    assert len(failed["usage"]) == 1
    assert failed["usage"][0]["last"]["totalTokens"] == 100
    resumed = engine.launch(run["id"], background=False)
    assert resumed["state"] == "USER_DECISION_REQUIRED"
    assert "budget" in resumed["error"]
    assert len(provider.calls) == 1
    assert len(resumed["usage"]) == 1


def test_failed_turn_resume_counts_only_new_cumulative_usage_and_no_duplicate_events(rig):
    make, _, _, _ = rig

    class RetryingProvider(FakeCodexProvider):
        coordinator_calls = 0

        def execute(self, agent, workspace, prompt, schema, thread_id, on_event, on_thread, cancel):
            response = super().execute(agent, workspace, prompt, schema, thread_id, on_event, on_thread, cancel)
            if agent["name"] == "coordinator":
                self.coordinator_calls += 1
                total = 100 if self.coordinator_calls == 1 else 140
                usage = {"total": {"totalTokens": total}, "last": {"totalTokens": 40}}
                on_event("thread/tokenUsage/updated", {"tokenUsage": {"total": {"totalTokens": total - 10}}})
                on_event("thread/tokenUsage/updated", {"tokenUsage": usage})
                if self.coordinator_calls == 1:
                    raise ProviderError("USAGE_LIMIT", "Retry later")
                response["usage"] = usage
            return response

    provider = RetryingProvider([result("PLAN"), *standard_results()])
    engine, run = make(provider)
    interrupted = engine.launch(run["id"], background=False)
    assert interrupted["state"] == "USAGE_LIMIT"
    first_thread = interrupted["threads"]["coordinator"]
    finished = engine.launch(run["id"], background=False)
    assert finished["state"] == "DONE", finished.get("error")
    assert finished["threads"]["coordinator"] == first_thread
    assert len(finished["usage"]) == 6
    assert [entry["last"]["totalTokens"] for entry in finished["usage"][:2]] == [100, 40]
    assert sum(entry["last"]["totalTokens"] for entry in finished["usage"]) == 200
