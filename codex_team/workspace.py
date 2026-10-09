"""Conservative Git workspaces and policy for commands issued by this application.

This policy does not intercept Codex native shell tools. Configure Codex's own
sandbox and approval policy separately; do not treat this module as a sandbox.
"""
from __future__ import annotations

import difflib
import json
import hashlib
import os
from pathlib import Path
import re
import subprocess
from typing import Any


class WorkspaceError(ValueError):
    pass


class CommandPolicy:
    """Small allowlist. Unknown executables and command compounds fail closed."""

    SAFE = "SAFE"
    CAUTION = "CAUTION"
    DANGEROUS = "DANGEROUS"
    BLOCKED = "BLOCKED"

    @classmethod
    def classify(cls, argv: list[str]) -> str:
        if not argv or any(not isinstance(a, str) or not a or any(c in a for c in "\x00\n\r;&|`<>") or "$(" in a for a in argv):
            return cls.BLOCKED
        executable = argv[0].lower()
        # A path, wrapper, shell or renamed binary must not inherit an allowlist.
        if executable not in {"git", "git.exe", "rg", "rg.exe", "pytest", "pytest.exe", "npm"}:
            return cls.BLOCKED
        if executable.startswith("git"):
            if len(argv) < 2 or argv[1].startswith("-"):
                return cls.BLOCKED
            action = argv[1]
            args = argv[2:]
            if action in {"reset", "clean", "push", "checkout", "switch", "restore", "rebase", "merge", "reflog", "gc", "prune"}:
                return cls.DANGEROUS
            if action in {"status", "diff", "show", "log", "rev-parse", "ls-files", "ls-tree", "cat-file"}:
                # Options which invoke helpers, write files or change other paths.
                forbidden = ("--output", "--ext-diff", "--textconv", "--exec", "--git-dir", "--work-tree", "--config", "--filters", "--no-index")
                if any(a.startswith(forbidden) for a in args):
                    return cls.BLOCKED
                return cls.SAFE
            if action == "branch":
                return cls.SAFE if not args or all(a in {"--show-current", "--list", "-a", "-r", "-v", "-vv"} for a in args) else cls.CAUTION
            if action in {"add", "commit", "fetch", "worktree"}:
                if action == "worktree" and args and args[0] in {"remove", "prune", "repair", "move"}:
                    return cls.DANGEROUS
                return cls.CAUTION
            return cls.BLOCKED
        if executable.startswith("rg"):
            return cls.BLOCKED if any(a.startswith("--pre") for a in argv[1:]) else cls.SAFE
        return cls.CAUTION


class CommandRunner:
    """Run application commands, never shell strings; record outcomes."""

    def __init__(self) -> None:
        self.history: list[dict[str, Any]] = []

    def run(self, argv: list[str], cwd: Path, timeout: int = 120, approved: bool = False) -> dict[str, Any]:
        classification = CommandPolicy.classify(argv)
        if classification != CommandPolicy.SAFE and not (classification == CommandPolicy.CAUTION and approved):
            raise WorkspaceError(f"Command requires explicit policy authorization: {classification}")
        result = _execute(argv, Path(cwd), timeout)
        result["classification"] = classification
        self.history.append(result)
        return result


def _execute(argv: list[str], cwd: Path, timeout: int = 120) -> dict[str, Any]:
    env = os.environ.copy()
    # Avoid an inherited repository override and any interactive pager/prompts.
    for name in list(env):
        if name.startswith("GIT_"):
            env.pop(name)
    env.update(GIT_TERMINAL_PROMPT="0", GIT_PAGER="cat")
    if argv[0].lower() in {"git", "git.exe"}:
        if any(action in argv[1:] for action in ("status", "diff", "add", "commit", "worktree")):
            WorkspaceManager(cwd)._check_filters(cwd)
        # Even read commands can invoke a repository's fsmonitor or diff driver.
        # A non-existent hooks directory is valid Git configuration and cannot
        # run repo/global hooks during automatic worktree/commit operations.
        cache_root = Path(os.environ.get("CODEX_TEAM_DATA_ROOT") or Path(__file__).resolve().parents[1]).resolve()
        hooks = cache_root / ".ai-team" / "disabled-hooks"
        if not hooks.resolve().is_relative_to(cache_root):
            raise WorkspaceError("Application hooks directory escapes app root")
        hooks.mkdir(parents=True, exist_ok=True)
        if hooks.is_symlink() or any(hooks.iterdir()):
            raise WorkspaceError("Empty application hooks directory was modified")
        argv = [argv[0], "-c", "core.fsmonitor=false", "-c", f"core.hooksPath={hooks}", *argv[1:]]
        if "diff" in argv or "show" in argv or "log" in argv:
            index = next(i for i, item in enumerate(argv) if item in {"diff", "show", "log"})
            argv[index + 1:index + 1] = ["--no-ext-diff", "--no-textconv"]
    try:
        completed = subprocess.run(argv, cwd=cwd, shell=False, capture_output=True, text=True,
                                   encoding="utf-8", errors="replace", timeout=timeout, env=env,
                                   stdin=subprocess.DEVNULL)
        return {"argv": list(argv), "cwd": str(cwd), "exit_code": completed.returncode,
                "stdout": completed.stdout, "stderr": completed.stderr}
    except subprocess.TimeoutExpired as exc:
        def decode(value: Any) -> str:
            return value.decode("utf-8", "replace") if isinstance(value, bytes) else value or ""
        return {"argv": list(argv), "cwd": str(cwd), "exit_code": -1, "stdout": decode(exc.stdout),
                "stderr": decode(exc.stderr) + f"\nCommand timed out after {timeout}s", "timed_out": True}
    except OSError as exc:
        raise WorkspaceError(f"Cannot execute command: {exc}") from exc


class WorkspaceManager:
    SENSITIVE = {".git", ".codex", ".aws", ".ssh", ".azure", ".kube", ".agents"}

    @classmethod
    def sensitive(cls, relative):
        return any(p.lower() in cls.SENSITIVE or p.lower() == ".env" or p.lower().startswith(".env.") for p in Path(relative).parts)

    def __init__(self, app_root: Path):
        self.app_root = Path(app_root).resolve()
        self._prepared: dict[str, dict[str, Any]] = {}

    @staticmethod
    def resolve_inside(root: Path, relative: str | Path) -> Path:
        try:
            root = Path(root).resolve(strict=True)
        except OSError as exc:
            raise WorkspaceError("Cannot resolve workspace root") from exc
        relative = Path(relative)
        if relative.is_absolute() or relative.drive or ".." in relative.parts:
            raise WorkspaceError("Path must be relative and cannot traverse parents")
        if WorkspaceManager.sensitive(relative):
            raise WorkspaceError("Sensitive directory access refused")
        target = (root / relative).resolve()
        try:
            resolved_relative = target.relative_to(root)
        except ValueError as exc:
            raise WorkspaceError("Path escapes workspace through a link or junction") from exc
        if WorkspaceManager.sensitive(resolved_relative):
            raise WorkspaceError("Sensitive directory access refused")
        # NTFS alternate data streams and ambiguous Windows spellings are unsafe.
        if any(":" in part or part.endswith((".", " ")) for part in relative.parts):
            raise WorkspaceError("Ambiguous path refused")
        return target

    def _git(self, root: Path, *args: str, check: bool = True) -> dict[str, Any]:
        result = _execute(["git", "--no-pager", *args], root)
        if check and result["exit_code"]:
            raise WorkspaceError(result["stderr"].strip() or result["stdout"].strip() or "Git command failed")
        return result

    def validate(self, path: Path) -> Path:
        try:
            root = Path(path).expanduser().resolve(strict=True)
        except OSError as exc:
            raise WorkspaceError(f"Workspace does not exist: {path}") from exc
        if not root.is_dir() or root == Path(root.anchor) or root == Path.home().resolve():
            raise WorkspaceError("Select a project directory, not a filesystem root or home")
        actual = Path(self._git(root, "rev-parse", "--show-toplevel")["stdout"].strip()).resolve()
        if actual != root:
            raise WorkspaceError("Select the Git repository root, not a subdirectory")
        return root

    def snapshot(self, path: Path) -> dict[str, Any]:
        root = self.validate(path)
        self._check_filters(root)
        status = self._git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all")["stdout"]
        records = self._status_records(status)
        head = self._git(root, "rev-parse", "--verify", "HEAD", check=False)
        branch = self._git(root, "symbolic-ref", "--quiet", "--short", "HEAD", check=False)
        return {"branch": branch["stdout"].strip() or None,
                "head": head["stdout"].strip() if head["exit_code"] == 0 else None,
                "status": status, "dirty": bool(records),
                "untracked": [name for code, name in records if code == "??"]}

    @staticmethod
    def _status_records(status: str) -> list[tuple[str, str]]:
        pieces = iter(status.split("\x00"))
        records = []
        for piece in pieces:
            if not piece:
                continue
            code, name = piece[:2], piece[3:]
            records.append((code, name))
            if "R" in code or "C" in code:
                next(pieces, None)
        return records

    @staticmethod
    def _run_id(run_id: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", run_id):
            raise WorkspaceError("Invalid run ID")
        return run_id

    def _exclude_metadata(self, root: Path) -> None:
        common = Path(self._git(root, "rev-parse", "--git-common-dir")["stdout"].strip())
        common = (root / common).resolve() if not common.is_absolute() else common.resolve()
        exclude = common / "info" / "exclude"
        if exclude.is_symlink() or exclude.parent.is_symlink():
            raise WorkspaceError("Refusing linked Git exclude file")
        exclude.parent.mkdir(parents=True, exist_ok=True)
        text = exclude.read_text(encoding="utf-8") if exclude.exists() else ""
        if "/.ai-team/" not in text.splitlines():
            with exclude.open("a", encoding="utf-8") as stream:
                stream.write(("\n" if text and not text.endswith("\n") else "") + "/.ai-team/\n")

    def prepare(self, path: Path, run_id: str, isolated: bool = True) -> dict[str, Any]:
        root = self.validate(path)
        run_id = self._run_id(run_id)
        baseline = self.snapshot(root)
        if baseline["dirty"]:
            raise WorkspaceError("USER_DECISION: checkout has existing changes; commit or stash them yourself before a run")
        if isolated and baseline["head"] is None:
            raise WorkspaceError("USER_DECISION: isolated worktree requires an initial commit")
        self._exclude_metadata(root)
        workspace = root
        branch = baseline["branch"]
        worktree: str | None = None
        if isolated:
            self._check_filters(root)
            destination = self.resolve_inside(root, Path(".ai-team") / "worktrees" / run_id)
            if destination.exists():
                raise WorkspaceError("Run worktree already exists; refusing to overwrite it")
            destination.parent.mkdir(parents=True, exist_ok=True)
            branch = f"codex/{run_id}"
            self._git(root, "worktree", "add", "-b", branch, str(destination), baseline["head"])
            workspace, worktree = destination, str(destination)
        result = {"workspace": str(workspace), "worktree": worktree, "baseline": baseline, "branch": branch}
        self._prepared[str(workspace)] = result
        return result

    def _check_filters(self, root):
        files = [f for f in self._git(root, "ls-files", "--cached", "--others", "--exclude-standard", "-z")["stdout"].split("\x00") if f]
        if files:
            attrs = self._git(root, "check-attr", "-z", "filter", "--", *files)["stdout"].split("\x00")
            if any(v not in {"unspecified", "unset", ""} for v in attrs[2::3]):
                raise WorkspaceError("USER_DECISION: active Git filters may run host commands; automatic checkout/commit refused")

    def resume(self, path: Path, baseline: dict):
        root = self.validate(path)
        if baseline.get("dirty") or self.snapshot(root)["head"] != baseline.get("head"):
            raise WorkspaceError("Resume commit baseline is not clean or HEAD changed")
        self._prepared[str(root)] = {"workspace": str(root), "baseline": baseline}

    def diff(self, path: Path, baseline: str | dict[str, Any] | None = None) -> dict[str, Any]:
        root = self.validate(path)
        snap = self.snapshot(root)
        revision = baseline.get("head") if isinstance(baseline, dict) else baseline
        revision = revision or snap["head"]
        if not revision:
            # Comparing with the empty tree includes staged files in an unborn
            # shared repository without writing objects or altering the index.
            revision = self._git(root, "hash-object", "-t", "tree", "--stdin")["stdout"].strip()
        if revision and not re.fullmatch(r"[0-9a-fA-F]{40,64}", revision):
            raise WorkspaceError("Baseline must be a full Git commit hash")
        args = ["diff", "--no-ext-diff", "--no-textconv"]
        if revision:
            args.append(revision)
        names = self._git(root, *args, "--name-only", "-z", "--")["stdout"].split("\x00")
        changed = [name for name in names if name]
        if any(self.sensitive(name) for name in [*changed, *snap["untracked"]]):
            raise WorkspaceError("Credential or sensitive file changes cannot be exported to agent context")
        patch = self._git(root, *args, "--")["stdout"]
        stat = self._git(root, *args, "--stat", "--")["stdout"]
        for name in snap["untracked"]:
            file = self.resolve_inside(root, name)
            if not file.is_file() or file.is_symlink():
                raise WorkspaceError(f"Cannot safely include untracked path: {name}")
            raw = file.read_bytes()
            def label(prefix: str) -> str:
                full = prefix + name
                return json.dumps(full, ensure_ascii=False) if any(c.isspace() or c in '\\"' for c in name) else full
            left, right = label("a/"), label("b/")
            patch += f"diff --git {left} {right}\nnew file mode 100644\n"
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                text = None
            if b"\x00" in raw or text is None:
                patch += f"Binary files /dev/null and {right} differ\n"
                stat += f" {name} | Bin 0 -> {len(raw)} bytes\n"
            else:
                lines = text.splitlines(keepends=True)
                patch += "".join(difflib.unified_diff([], lines, fromfile="/dev/null", tofile=right))
                if text and not text.endswith("\n"):
                    patch += "\n\\ No newline at end of file\n"
                stat += f" {name} | {len(lines)} +\n"
            changed.append(name)
        return {"diff": patch, "diff_stat": stat, "changed_files": sorted(set(changed))}

    def memory(self, path: Path, run_id: str, result: dict[str, Any]) -> dict[str, str]:
        root = self.validate(path)
        run_id = self._run_id(run_id)
        self._exclude_metadata(root)
        locations = {
            "project": self.resolve_inside(root, ".ai-team/project.json"),
            "run": self.resolve_inside(root, f".ai-team/runs/{run_id}.json"),
            "artifact": self.resolve_inside(root, f".ai-team/artifacts/{run_id}/result.json"),
        }
        analysis = result.get("results", {}).get("analyst", result.get("analysis", {}))
        project = {"workspace": str(root), "last_run": run_id, "analysis": analysis, "schema_version": 1}
        for key, file in locations.items():
            file.parent.mkdir(parents=True, exist_ok=True)
            payload = project if key == "project" else {"run_id": run_id, "result": result}
            file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        docs = {"project_summary.md": analysis.get("summary", "No analysis yet."),
                "architecture.md": "\n".join(analysis.get("project_map", {}).get("architecture_notes", [])),
                "commands.md": "\n".join(analysis.get("build_commands", [])),
                "decisions.md": "\n".join(result.get("results", {}).get("coordinator", {}).get("plan", [])),
                "known_issues.md": "\n".join(f.get("problem", "") for r in result.get("results", {}).values() for f in r.get("findings", []))}
        for name, content in docs.items():
            self.resolve_inside(root, ".ai-team/" + name).write_text(content + "\n", encoding="utf-8")
        fingerprint = result.get("artifact_snapshots", {}).get("analyst")
        if fingerprint:
            summary = self.resolve_inside(root, ".ai-team/project_summary.md")
            metadata = {key: fingerprint.get(key) for key in ("workspace", "head", "diff_hash")}
            metadata["summary_hash"] = hashlib.sha256(summary.read_bytes()).hexdigest()
            self.resolve_inside(root, ".ai-team/project_summary.meta.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        self.resolve_inside(root, ".ai-team/project_map.json").write_text(json.dumps(analysis.get("project_map", {}), ensure_ascii=False, indent=2), encoding="utf-8")
        return {key: str(value) for key, value in locations.items()}

    def commit(self, path: Path, task: str) -> dict[str, Any]:
        root = self.validate(path)
        prepared = self._prepared.get(str(root))
        if not prepared or prepared["baseline"]["dirty"]:
            raise WorkspaceError("Commit requires this manager's clean prepared run baseline")
        current_head = self.snapshot(root)["head"]
        if current_head != prepared["baseline"]["head"]:
            raise WorkspaceError("HEAD changed since run started; refusing automatic commit")
        change = self.diff(root, prepared["baseline"])
        files = change["changed_files"]
        if not files:
            return {"committed": False, "head": current_head}
        for file in files:
            self.resolve_inside(root, file)
            if Path(file).parts[0] == ".ai-team":
                raise WorkspaceError("Run metadata must not be committed")
        self._check_filters(root)
        self._git(root, "add", "--", *files)
        self._git(root, "commit", "-m", task.strip()[:200] or "Codex team changes", "--", *files)
        return {"committed": True, "head": self.snapshot(root)["head"], "changed_files": files}
