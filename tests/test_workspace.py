from pathlib import Path
import json
import os
import subprocess

import pytest

from codex_team.workspace import WorkspaceError, WorkspaceManager


def git(root, *args):
    result = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


@pytest.fixture
def repository(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    git(root, "init")
    git(root, "config", "user.name", "Test User")
    git(root, "config", "user.email", "test@example.invalid")
    (root / "original.txt").write_text("baseline\n", encoding="utf-8")
    git(root, "add", "original.txt")
    git(root, "commit", "-m", "Initial")
    return root


def test_validate_requires_actual_repository_root(repository, tmp_path):
    manager = WorkspaceManager(tmp_path)
    assert manager.validate(repository) == repository.resolve()
    folder = repository / "src"
    folder.mkdir()
    with pytest.raises(WorkspaceError, match="root"):
        manager.validate(folder)
    with pytest.raises(WorkspaceError):
        manager.validate(tmp_path)
    with pytest.raises(WorkspaceError):
        manager.validate(Path.home())


@pytest.mark.parametrize("isolated", [True, False])
def test_dirty_checkout_requires_decision_preserves_changes(repository, tmp_path, isolated):
    manager = WorkspaceManager(tmp_path)
    (repository / "original.txt").write_text("user changes\n", encoding="utf-8")
    (repository / "new file.txt").write_text("user new file\n", encoding="utf-8")
    git(repository, "add", "original.txt")
    before = git(repository, "diff", "--cached")
    with pytest.raises(WorkspaceError, match="USER_DECISION"):
        manager.prepare(repository, "dirty", isolated=isolated)
    assert (repository / "original.txt").read_text() == "user changes\n"
    assert (repository / "new file.txt").read_text() == "user new file\n"
    assert git(repository, "diff", "--cached") == before
    assert not (repository / ".ai-team" / "worktrees" / "dirty").exists()


def test_isolated_worktree_and_local_exclude(repository, tmp_path):
    manager = WorkspaceManager(tmp_path)
    baseline = manager.snapshot(repository)
    prepared = manager.prepare(repository, "run_123")
    worktree = Path(prepared["workspace"])
    assert prepared["branch"] == "codex/run_123"
    assert prepared["baseline"] == baseline
    assert worktree.is_dir()
    assert git(worktree, "rev-parse", "HEAD") == baseline["head"]
    (worktree / "original.txt").write_text("agent change\n", encoding="utf-8")
    assert (repository / "original.txt").read_text() == "baseline\n"
    assert not manager.snapshot(repository)["dirty"]
    assert "/.ai-team/" in (repository / ".git" / "info" / "exclude").read_text()
    assert not (repository / ".gitignore").exists()
    with pytest.raises(WorkspaceError, match="already exists"):
        manager.prepare(repository, "run_123")


def test_existing_untracked_metadata_is_not_silently_hidden(repository, tmp_path):
    metadata = repository / ".ai-team"
    metadata.mkdir()
    (metadata / "user-file.txt").write_text("preserve me", encoding="utf-8")
    manager = WorkspaceManager(tmp_path)
    with pytest.raises(WorkspaceError, match="USER_DECISION"):
        manager.prepare(repository, "existing")
    assert manager.snapshot(repository)["untracked"] == [".ai-team/user-file.txt"]
    assert (metadata / "user-file.txt").read_text() == "preserve me"


def test_shared_can_prepare_unborn_repository(tmp_path):
    root = tmp_path / "unborn"
    root.mkdir()
    git(root, "init")
    manager = WorkspaceManager(tmp_path)
    with pytest.raises(WorkspaceError, match="initial commit"):
        manager.prepare(root, "first")
    prepared = manager.prepare(root, "first", isolated=False)
    assert prepared["baseline"]["head"] is None
    assert prepared["workspace"] == str(root.resolve())


@pytest.mark.parametrize("relative", ["../outside.txt", ".git/config", "a/../../x", ".codex/auth.json", ".aws/credentials", "foo:stream", "name."])
def test_boundary_refuses_sensitive_or_escaping_paths(tmp_path, relative):
    with pytest.raises(WorkspaceError):
        WorkspaceManager.resolve_inside(tmp_path, relative)


def test_boundary_refuses_external_absolute_path(tmp_path):
    with pytest.raises(WorkspaceError):
        WorkspaceManager.resolve_inside(tmp_path, tmp_path.parent / "outside")


def test_boundary_detects_symlinks(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        (root / "escape").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Creating Windows symlinks requires Developer Mode or privilege")
    with pytest.raises(WorkspaceError, match="escapes"):
        WorkspaceManager.resolve_inside(root, "escape/file")
    sensitive = root / ".git"
    sensitive.mkdir()
    (root / "alias").symlink_to(sensitive, target_is_directory=True)
    with pytest.raises(WorkspaceError, match="Sensitive"):
        WorkspaceManager.resolve_inside(root, "alias/config")


@pytest.mark.skipif(os.name != "nt", reason="NTFS junction test")
def test_boundary_detects_windows_junction(tmp_path):
    root = tmp_path / "root"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    link = root / "escape"
    env = os.environ.copy()
    env.update(TEST_JUNCTION=str(link), TEST_JUNCTION_TARGET=str(outside))
    created = subprocess.run([
        "powershell", "-NoProfile", "-NonInteractive", "-Command",
        "New-Item -ItemType Junction -Path $env:TEST_JUNCTION -Target $env:TEST_JUNCTION_TARGET | Out-Null",
    ], env=env, capture_output=True)
    assert created.returncode == 0, created.stderr
    with pytest.raises(WorkspaceError, match="escapes"):
        WorkspaceManager.resolve_inside(root, "escape/file")
    # Remove the link itself; never recursively delete its external target.
    link.rmdir()
    assert outside.exists()


def test_diff_includes_staged_unstaged_untracked_without_index_mutation(repository, tmp_path):
    manager = WorkspaceManager(tmp_path)
    baseline = manager.snapshot(repository)
    (repository / "original.txt").write_text("staged\n", encoding="utf-8")
    git(repository, "add", "original.txt")
    (repository / "original.txt").write_text("unstaged\n", encoding="utf-8")
    (repository / "new file.txt").write_text("fresh\n", encoding="utf-8")
    (repository / "image.bin").write_bytes(b"\x00\xff\x01")
    index_before = (repository / ".git" / "index").read_bytes()
    result = manager.diff(repository, baseline)
    assert result["changed_files"] == ["image.bin", "new file.txt", "original.txt"]
    assert "+unstaged" in result["diff"]
    assert "+fresh" in result["diff"]
    assert "Binary files" in result["diff"]
    assert "new file.txt" in result["diff_stat"]
    assert (repository / ".git" / "index").read_bytes() == index_before


def test_memory_uses_structured_analysis_and_is_excluded(repository, tmp_path):
    manager = WorkspaceManager(tmp_path)
    analysis = {"architecture": ["Python"], "risks": ["Concurrency"]}
    files = manager.memory(repository, "memory", {"analysis": analysis, "status": "completed"})
    project = json.loads(Path(files["project"]).read_text(encoding="utf-8"))
    assert project["analysis"] == analysis
    assert Path(files["run"]).exists()
    assert Path(files["artifact"]).exists()
    assert not manager.snapshot(repository)["dirty"]
    with pytest.raises(WorkspaceError):
        manager.memory(repository, "../../bad", {})


def test_commit_requires_clean_preparation_and_commits_changes_only(repository, tmp_path):
    manager = WorkspaceManager(tmp_path)
    with pytest.raises(WorkspaceError, match="baseline"):
        manager.commit(repository, "Task")
    manager.prepare(repository, "shared", isolated=False)
    (repository / "agent.txt").write_text("done\n", encoding="utf-8")
    manager.memory(repository, "shared", {"status": "completed"})
    result = manager.commit(repository, "Complete task")
    assert result["committed"]
    assert result["changed_files"] == ["agent.txt"]
    assert git(repository, "show", "--pretty=format:", "--name-only", "HEAD") == "agent.txt"
    assert not manager.snapshot(repository)["dirty"]


def test_commit_refuses_changed_head(repository, tmp_path):
    manager = WorkspaceManager(tmp_path)
    manager.prepare(repository, "head", isolated=False)
    git(repository, "commit", "--allow-empty", "-m", "External change")
    with pytest.raises(WorkspaceError, match="HEAD changed"):
        manager.commit(repository, "Task")


def test_unborn_diff_includes_staged_files(tmp_path):
    root = tmp_path / "unborn-diff"
    root.mkdir()
    git(root, "init")
    manager = WorkspaceManager(tmp_path)
    manager.prepare(root, "empty", isolated=False)
    (root / "added.txt").write_text("staged\n", encoding="utf-8")
    git(root, "add", "added.txt")
    result = manager.diff(root)
    assert result["changed_files"] == ["added.txt"]
    assert "+staged" in result["diff"]


def test_prepare_never_executes_host_post_checkout_hook(repository, tmp_path, monkeypatch):
    hooks = tmp_path / "host-hooks"
    hooks.mkdir()
    hook = hooks / "post-checkout"
    hook.write_text('#!/bin/sh\nprintf hook-ran > "$HOOK_SENTINEL"\nexit 17\n', encoding="utf-8")
    hook.chmod(0o755)
    sentinel = tmp_path / "outside-workspace-sentinel.txt"
    monkeypatch.setenv("HOOK_SENTINEL", str(sentinel))
    git(repository, "config", "core.hooksPath", str(hooks))
    manager = WorkspaceManager(tmp_path)
    prepared = manager.prepare(repository, "nohooks")
    assert Path(prepared["worktree"]).is_dir()
    assert not sentinel.exists(), "Git checkout hook escaped the orchestration sandbox"


def test_active_checkout_filter_refused_before_host_command(repository, tmp_path, monkeypatch):
    (repository / ".gitattributes").write_text("original.txt filter=unsafe\n", encoding="utf-8")
    git(repository, "add", ".gitattributes")
    git(repository, "commit", "-m", "Activate checkout filter")
    sentinel = tmp_path / "filter-sentinel.txt"
    monkeypatch.setenv("FILTER_SENTINEL", str(sentinel))
    git(repository, "config", "filter.unsafe.smudge", 'printf filter-ran > "$FILTER_SENTINEL"; cat')
    manager = WorkspaceManager(tmp_path)
    with pytest.raises(WorkspaceError, match="active Git filters"):
        manager.prepare(repository, "unsafe-filter")
    assert not sentinel.exists()
    assert not (repository / ".ai-team" / "worktrees" / "unsafe-filter").exists()
    assert (repository / "original.txt").read_text() == "baseline\n"


def test_active_clean_filter_refused_before_status_comparison(repository, tmp_path, monkeypatch):
    (repository / ".gitattributes").write_text("original.txt filter=unsafe\n", encoding="utf-8")
    git(repository, "add", ".gitattributes")
    git(repository, "commit", "-m", "Activate fixture clean filter")
    sentinel = tmp_path / "clean-filter-sentinel.txt"
    monkeypatch.setenv("FILTER_SENTINEL", str(sentinel))
    git(repository, "config", "filter.unsafe.clean", 'printf clean-ran > "$FILTER_SENTINEL"; cat')
    # Force Git to compare contents rather than accepting cached index stat data.
    original = repository / "original.txt"
    old_stat = original.stat()
    os.utime(original, ns=(old_stat.st_atime_ns, old_stat.st_mtime_ns + 2_000_000_000))
    with pytest.raises(WorkspaceError, match="active Git filters"):
        WorkspaceManager(tmp_path).prepare(repository, "clean-filter")
    assert not sentinel.exists(), "Git status executed a clean filter before the filter safety check"


def test_unused_global_filter_does_not_block_isolation(repository, tmp_path, monkeypatch):
    temporary_home = tmp_path / "test-home"
    temporary_home.mkdir()
    (temporary_home / ".gitconfig").write_text('[filter "unused"]\n\tsmudge = cat\n', encoding="utf-8")
    monkeypatch.setenv("HOME", str(temporary_home))
    manager = WorkspaceManager(tmp_path)
    assert manager._git(repository, "config", "--get", "filter.unused.smudge")["stdout"].strip() == "cat"
    prepared = manager.prepare(repository, "unused-filter")
    assert Path(prepared["worktree"]).is_dir()


@pytest.mark.parametrize("relative", [".env", ".env.production", "src/.env", "src/.env.local", "config/.ENV.TEST"])
def test_sensitive_env_paths_rejected(tmp_path, relative):
    with pytest.raises(WorkspaceError, match="Sensitive"):
        WorkspaceManager.resolve_inside(tmp_path, relative)


@pytest.mark.parametrize("relative", [".env", "src/.env", "config/.env.production"])
@pytest.mark.parametrize("tracked", [False, True])
def test_env_changes_refused_before_patch_export(repository, tmp_path, monkeypatch, relative, tracked):
    sensitive = repository / relative
    sensitive.parent.mkdir(parents=True, exist_ok=True)
    if tracked:
        sensitive.write_text("password=baseline-test-secret\n", encoding="utf-8")
        git(repository, "add", "--", relative)
        git(repository, "commit", "-m", "Track fixture configuration")
    sensitive.write_text("password=new-test-secret\n", encoding="utf-8")
    manager = WorkspaceManager(tmp_path)
    actual_git = manager._git
    commands = []

    def audited_git(root, *args, **kwargs):
        commands.append(args)
        return actual_git(root, *args, **kwargs)

    monkeypatch.setattr(manager, "_git", audited_git)
    with pytest.raises(WorkspaceError, match="cannot be exported"):
        manager.diff(repository)
    # Filename discovery is allowed, but no actual patch or stat is read.
    assert all("--name-only" in args for args in commands if args[0] == "diff")
    assert sensitive.read_text() == "password=new-test-secret\n"


def test_resumed_manager_can_commit_clean_original_baseline(repository, tmp_path):
    original = WorkspaceManager(tmp_path)
    prepared = original.prepare(repository, "resume-commit")
    worktree = Path(prepared["workspace"])
    (worktree / "resumed.txt").write_text("preserved run changes\n", encoding="utf-8")
    restarted = WorkspaceManager(tmp_path)
    restarted.resume(worktree, prepared["baseline"])
    committed = restarted.commit(worktree, "Commit resumed run")
    assert committed["committed"]
    assert committed["changed_files"] == ["resumed.txt"]
    assert git(repository, "rev-parse", "HEAD") == prepared["baseline"]["head"]
    assert not (repository / "resumed.txt").exists()
    assert (worktree / "resumed.txt").read_text() == "preserved run changes\n"


def test_resume_rejects_preexisting_dirty_baseline(repository, tmp_path):
    manager = WorkspaceManager(tmp_path)
    baseline = manager.snapshot(repository)
    baseline["dirty"] = True
    (repository / "user.txt").write_text("user data\n", encoding="utf-8")
    with pytest.raises(WorkspaceError, match="baseline"):
        manager.resume(repository, baseline)
    with pytest.raises(WorkspaceError, match="baseline"):
        manager.commit(repository, "Must not commit")
    assert (repository / "user.txt").read_text() == "user data\n"


def test_resume_rejects_external_head_change(repository, tmp_path):
    baseline = WorkspaceManager(tmp_path).snapshot(repository)
    git(repository, "commit", "--allow-empty", "-m", "External HEAD")
    restarted = WorkspaceManager(tmp_path)
    with pytest.raises(WorkspaceError, match="HEAD"):
        restarted.resume(repository, baseline)
    with pytest.raises(WorkspaceError, match="baseline"):
        restarted.commit(repository, "Must not commit")
