from unittest.mock import patch

import pytest

from codex_team.workspace import CommandPolicy, CommandRunner, WorkspaceError


@pytest.mark.parametrize("argv", [
    ["git", "status", "--short"], ["git", "diff", "--no-ext-diff"],
    ["git", "branch", "--show-current"], ["rg", "needle", "src"],
])
def test_safe_reads(argv):
    assert CommandPolicy.classify(argv) == "SAFE"


@pytest.mark.parametrize("argv", [
    [], ["cmd", "/c", "git status"], ["powershell", "-Command", "Get-Content file"],
    ["python", "-c", "exec('bad')"], ["git", "status", ";", "rm"],
    ["git", "status && git reset --hard"], ["git", "status\nother"],
    ["git", "-c", "alias.status=!bad", "status"], ["git", "mystery"],
    ["C:/evil/git.exe", "status"], ["git", "diff", "--output=outside"],
    ["git", "diff", "--ext-diff"], ["git", "show", "--textconv"],
    ["rg", "--pre=sh", "needle"], ["git", "show", "$(bad)"],
])
def test_policy_bypasses_fail_closed(argv):
    assert CommandPolicy.classify(argv) == "BLOCKED"


@pytest.mark.parametrize("argv", [["git", "reset", "--hard"], ["git", "clean", "-fd"], ["git", "push"], ["git", "worktree", "remove", "project"]])
def test_dangerous_commands_never_run_even_approved(argv, tmp_path):
    assert CommandPolicy.classify(argv) == "DANGEROUS"
    with patch("codex_team.workspace.subprocess.run") as execute:
        with pytest.raises(WorkspaceError):
            CommandRunner().run(argv, tmp_path, approved=True)
        execute.assert_not_called()


def test_caution_requires_explicit_approval(tmp_path):
    runner = CommandRunner()
    with pytest.raises(WorkspaceError, match="CAUTION"):
        runner.run(["git", "add", "file"], tmp_path)
    with patch("codex_team.workspace.subprocess.run") as execute:
        execute.return_value.returncode = 0
        execute.return_value.stdout = "done"
        execute.return_value.stderr = ""
        result = runner.run(["git", "add", "file"], tmp_path, approved=True)
        assert execute.call_args.kwargs["shell"] is False
        assert result["exit_code"] == 0
        assert result["stdout"] == "done"
        assert runner.history == [result]


def test_safe_command_returns_real_output(tmp_path):
    runner = CommandRunner()
    result = runner.run(["git", "rev-parse", "--verify", "refs/heads/nonexistent-test-branch"], tmp_path)
    assert result["exit_code"] != 0
    assert result["stderr"]
    assert result["classification"] == "SAFE"


def test_git_runner_disables_hooks_and_repository_helpers(tmp_path):
    with patch("codex_team.workspace.subprocess.run") as execute:
        execute.return_value.returncode = 0
        execute.return_value.stdout = ""
        execute.return_value.stderr = ""
        CommandRunner().run(["git", "diff"], tmp_path)
        argv = execute.call_args.args[0]
        assert any(a.startswith("core.hooksPath=") for a in argv)
        assert "core.fsmonitor=false" in argv
        assert "--no-ext-diff" in argv
        assert "--no-textconv" in argv
        assert execute.call_args.kwargs["shell"] is False
