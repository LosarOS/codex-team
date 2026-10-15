"""Deterministic acceptance checks in an optional, explicitly selected Docker sandbox.

No host command fallback and no image pull or dependency installation is performed.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

from codex_team.suite_store import SuiteStore
from codex_team.workspace import WorkspaceManager


def _git(path, *args):
    result = WorkspaceManager(Path(path))._git(Path(path), *args)
    return result["stdout"].encode("utf-8")


def safe_files(path):
    """Only tracked, regular, bounded files; secrets and symlinks never enter QA."""
    result = []
    size = 0
    names = _git(path, "ls-files", "-z").decode("utf-8").split("\0")
    if len(names) > 20001:
        raise ValueError("Репозиторий превышает лимит QA: 20000 файлов")
    for name in names:
        if not name:
            continue
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Небезопасный путь Git")
        if any(part.lower() in {".git", "node_modules", ".venv", "venv", "dist", "build", "credentials", "secrets"} or part.lower().startswith(".env") for part in relative.parts):
            continue
        if re.search(r"(?i)(\.pem$|\.key$|id_rsa|id_ed25519|credentials|token|secret)", name):
            continue
        source = path / relative
        if any(parent.is_symlink() for parent in [source, *source.parents] if parent != path.parent):
            continue
        if not source.is_file():
            continue
        length = source.stat().st_size
        if length > 5 * 1024 * 1024:
            continue
        size += length
        if size > 100 * 1024 * 1024:
            raise ValueError("Контекст QA превышает 100 МБ")
        result.append(name)
    return sorted(result)


def safe_read(path, name):
    source = path / name
    resolved = source.resolve(strict=True)
    if not resolved.is_relative_to(path.resolve()) or any(p.is_symlink() for p in [source, *source.parents] if p != path.parent):
        raise ValueError("Символические ссылки запрещены в QA")
    fd = os.open(source, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        if source.resolve(strict=True) != resolved or source.is_symlink():
            raise ValueError("Путь изменился во время снимка")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            content = stream.read(5 * 1024 * 1024 + 1)
        if len(content) > 5 * 1024 * 1024:
            raise ValueError("Файл превышает лимит QA")
        return content
    finally:
        os.close(fd)


def snapshot(path):
    files = safe_files(path)
    digest = hashlib.sha256()
    for name in files:
        digest.update(name.encode())
        digest.update(safe_read(path, name))
    return {"head": _git(path, "rev-parse", "HEAD").decode().strip(), "digest": digest.hexdigest(), "files": files}


class DockerRunner:
    def available(self, image):
        if not shutil.which("docker"):
            return False, "Docker недоступен. Запуск команд на хосте запрещён."
        try:
            subprocess.run(["docker", "image", "inspect", image], check=True, capture_output=True, timeout=10)
        except (subprocess.SubprocessError, OSError):
            return False, "Подтверждённый локальный образ Docker недоступен. Загрузка образов отключена."
        return True, None

    def execute(self, path, files, image, argv, timeout, cancel, expected_digest=None):
        name = "codex-qa-" + uuid.uuid4().hex
        with tempfile.TemporaryDirectory(prefix="codex-qa-") as temporary:
            source = Path(temporary) / "source"
            source.mkdir()
            source.chmod(0o755)
            digest = hashlib.sha256()
            for relative in files:
                target = source / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                for directory in [target.parent, *target.parent.parents]:
                    if directory == source.parent:
                        break
                    directory.chmod(0o755)
                content = safe_read(path, relative)
                digest.update(relative.encode())
                digest.update(content)
                target.write_bytes(content)
                target.chmod(0o644)
            if expected_digest and digest.hexdigest() != expected_digest:
                raise ValueError("Код изменился во время подготовки QA")
            # Source is read-only; copy into ephemeral writable tmpfs inside the container.
            command = ["docker", "run", "--pull=never", "--name", name, "--rm", "--network=none", "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges", "--pids-limit=128", "--memory=512m", "--cpus=1", "--user=65534:65534", "--tmpfs=/work:rw,nosuid,nodev,size=192m,mode=1777", "--tmpfs=/tmp:rw,nosuid,nodev,size=64m,mode=1777", "--mount", f"type=bind,source={source},target=/source,readonly", "--workdir=/work", "--entrypoint=/bin/sh", image, "-c", 'cp -R /source/. /work/ && exec "$@"', "qa", *argv]
            # Docker client proxy defaults must not leak credentials/configuration
            # into untrusted test processes, even with container networking disabled.
            position = command.index("--workdir=/work")
            proxy_overrides = [part for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "all_proxy", "no_proxy") for part in ("--env", key + "=")]
            command[position:position] = proxy_overrides
            started = time.monotonic()
            with tempfile.TemporaryFile() as log:
                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                output = bytearray()
                exceeded = threading.Event()
                def consume():
                    for block in iter(lambda: process.stdout.read(4096), b""):
                        remaining = 65536 - len(output)
                        if remaining > 0:
                            output.extend(block[:remaining])
                        if len(block) > remaining:
                            exceeded.set()
                reader = threading.Thread(target=consume, daemon=True)
                reader.start()
                reason = None
                try:
                    while process.poll() is None:
                        if cancel.wait(0.05):
                            reason = "Проверка отменена"
                            break
                        if time.monotonic() - started >= timeout:
                            reason = "Превышено время проверки"
                            break
                        if exceeded.is_set():
                            reason = "Превышен лимит журнала (64 КиБ)"
                            break
                finally:
                    if process.poll() is None:
                        try:
                            subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=15)
                        finally:
                            process.kill()
                    process.wait(timeout=10)
                    reader.join(timeout=3)
                return {"exit_code": process.returncode, "duration_seconds": round(time.monotonic() - started, 3), "log": output.decode("utf-8", errors="replace"), "error": reason}


def quality_gate(results, required_categories):
    if not results:
        return "NOT RUN"
    required = [r for r in results if r.get("required", True)]
    if any(r["status"] == "FAIL" for r in required):
        return "FAIL"
    if any(r["status"] == "BLOCKED" for r in required):
        return "BLOCKED"
    passed_categories = {r["category"] for r in results if r["status"] == "PASS"}
    if not set(required_categories).issubset(passed_categories):
        return "PARTIAL"
    if not required or any(r["status"] != "PASS" for r in results):
        return "PARTIAL"
    return "PASS"


class QAArena:
    def __init__(self, root, store, runner=None):
        self.root, self.store = Path(root), store
        self.suite = SuiteStore(store)
        self.runner = runner or DockerRunner()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="qa-arena")
        self.lock = threading.Lock()
        self.cancel = threading.Event()
        self.active = None
        self.previews = {}
    def recover(self):
        """Call only after the application owns its data-root lease."""
        if self.active is not None:
            raise ValueError("Нельзя восстанавливать результаты во время активной проверки")
        # Collect IDs before updates reorder the page by updated_at.
        interrupted = []
        offset = 0
        while True:
            page = self._page("qa_result", limit=200, offset=offset)
            interrupted.extend(item for item in page["items"] if item.get("status") == "RUNNING")
            offset += len(page["items"])
            if offset >= page["total"]:
                break
        for item in interrupted:
            item.update(status="BLOCKED", error="Приложение завершилось во время проверки")
            self._save("qa_result", item["project_id"], item)

    def _save(self, kind, project_id, data):
        return self._unpack(self.suite.put(kind, project_id, data, record_id=data.get("id")))

    @staticmethod
    def _unpack(record):
        return {**record["data"], "id": record["id"], "project_id": record["project_id"]}

    def _page(self, kind, **kwargs):
        page = self.suite.page(kind, **kwargs)
        return {**page, "items": [self._unpack(item) for item in page["items"]]}

    def _path(self, project_id, run_id=None):
        project = self.store.project(project_id)
        path = Path(project["path"]).resolve()
        if run_id:
            run = self.store.run(run_id)
            if Path(run.get("original_workspace", run["workspace"])).resolve() != path:
                raise ValueError("Запуск относится к другому проекту")
            worktree = run.get("worktree")
            if isinstance(worktree, dict):
                worktree = worktree.get("path")
            path = Path(worktree or run["workspace"]).resolve()
            if run.get("worktree_deleted"):
                raise ValueError("Рабочее дерево запуска удалено")
        _git(path, "rev-parse", "--show-toplevel")
        return path

    def discover(self, project_id):
        path = self._path(project_id)
        suggestions = []
        for filename, argv, category in [("pytest.ini", ["python", "-m", "pytest"], "test"), ("Cargo.toml", ["cargo", "test", "--offline"], "test")]:
            if (path / filename).is_file():
                suggestions.append({"id": category, "category": category, "argv": argv, "required": True})
        package = path / "package.json"
        if package.is_file() and package.stat().st_size < 100000:
            try:
                scripts = json.loads(package.read_text()).get("scripts", {})
                for key in ("test", "build", "lint"):
                    if key in scripts:
                        suggestions.append({"id": key, "category": key, "argv": ["npm", "run", key], "required": True})
            except (ValueError, OSError):
                pass
        return {"suggestions": suggestions, "configuration": self.configuration(project_id), "limitation": "Предложения не выполняются автоматически. Нужен локальный Linux-образ Docker с инструментами и зависимостями; сеть отключена. В QA передаются только отслеживаемые безопасные файлы."}

    def configuration(self, project_id):
        self.store.project(project_id)
        items = self._page("qa_config", project_id=project_id, limit=1)["items"]
        return items[0] if items else None

    def configure(self, project_id, data):
        self.store.project(project_id)
        image = str(data.get("image", ""))
        if not re.fullmatch(r"[a-zA-Z0-9_./:-]+@sha256:[a-f0-9]{64}|sha256:[a-f0-9]{64}", image):
            raise ValueError("Требуется неизменяемый локальный образ: image@sha256:… или sha256:…")
        commands = data.get("commands", [])
        if not isinstance(commands, list) or not 1 <= len(commands) <= 12:
            raise ValueError("Настройте от 1 до 12 команд")
        ids = set()
        normalized = []
        for command in commands:
            argv = command.get("argv")
            key = command.get("id")
            if not isinstance(key, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,60}", key) or key in ids:
                raise ValueError("ID команд должны быть уникальны")
            if not isinstance(argv, list) or not 1 <= len(argv) <= 32 or any(not isinstance(a, str) or not a or len(a) > 2000 or "\x00" in a for a in argv):
                raise ValueError("Команда задаётся массивом аргументов JSON")
            if command.get("category") not in {"test", "build", "lint", "typecheck", "other"}:
                raise ValueError("Неизвестная категория проверки")
            ids.add(key)
            normalized.append({"id": key, "argv": argv, "category": command["category"], "required": bool(command.get("required", True))})
        categories = data.get("required_categories", ["test"])
        if not isinstance(categories, list) or not set(categories).issubset({"test", "build", "lint", "typecheck", "other"}):
            raise ValueError("Некорректные обязательные категории")
        existing = self.configuration(project_id)
        value = {"id": existing["id"] if existing else "qa_config_" + uuid.uuid4().hex, "image": image, "commands": normalized, "timeout_seconds": max(1, min(600, int(data.get("timeout_seconds", 120)))), "required_categories": categories}
        return self._save("qa_config", project_id, value)

    def preview(self, project_id, run_id=None):
        path = self._path(project_id, run_id)
        config = self.configuration(project_id)
        if not config:
            raise ValueError("Сначала настройте команды QA и локальный образ")
        snap = snapshot(path)
        available, reason = self.runner.available(config["image"])
        token = uuid.uuid4().hex
        value = {"project_id": project_id, "run_id": run_id, "configuration": config, "head": snap["head"], "digest": snap["digest"], "files_count": len(snap["files"]), "available": available, "reason": reason, "confirmation_token": token, "expires": time.time() + 300}
        with self.lock:
            self.previews = {k: v for k, v in self.previews.items() if v["expires"] > time.time()}
            if len(self.previews) >= 20:
                self.previews.pop(next(iter(self.previews)))
            self.previews[token] = value
        return value

    def start(self, project_id, confirmation_token, run_id=None):
        with self.lock:
            if self.active is not None:
                raise ValueError("QA уже выполняется")
            preview = self.previews.get(confirmation_token)
            if not preview or preview["expires"] < time.time() or preview["project_id"] != project_id or preview["run_id"] != run_id:
                raise ValueError("Предварительный просмотр устарел: подтвердите команды заново")
            path = self._path(project_id, run_id)
            snap = snapshot(path)
            if snap["head"] != preview["head"] or snap["digest"] != preview["digest"] or self.configuration(project_id) != preview["configuration"]:
                raise ValueError("Код или настройки изменились после подтверждения")
            self.previews.pop(confirmation_token)
            config = preview["configuration"]
            value = {"id": "qa_" + uuid.uuid4().hex, "project_id": project_id, "run_id": run_id, "head": snap["head"], "digest": snap["digest"], "configuration": config, "fingerprint": hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest(), "status": "RUNNING", "checks": [], "started_at": time.time()}
            value = self._save("qa_result", project_id, value)
            self.active = value["id"]
            self.cancel.clear()
            self.executor.submit(self._execute, value, path, snap)
            return value

    def _execute(self, value, path, snap):
        try:
            available, reason = self.runner.available(value["configuration"]["image"])
            if not available:
                value.update(status="BLOCKED", error=reason)
            else:
                for command in value["configuration"]["commands"]:
                    if snapshot(path) != snap:
                        raise ValueError("Рабочее дерево изменилось: проверка заблокирована")
                    result = self.runner.execute(path, snap["files"], value["configuration"]["image"], command["argv"], value["configuration"]["timeout_seconds"], self.cancel, expected_digest=snap["digest"])
                    status = "BLOCKED" if result.get("error") else "PASS" if result["exit_code"] == 0 else "FAIL"
                    # pytest exit 5 is a failed check; no tests can never produce PASS.
                    if command["category"] == "test" and status == "PASS" and not re.search(r"(?i)([1-9]\d*\s+(?:passed|tests?\b)|ran\s+[1-9]\d*\s+tests?|tests:\s*[1-9]\d*|test result:\s*ok\.\s*[1-9]\d*\s+passed)", result.get("log", "")):
                        status = "PARTIAL"
                        result["error"] = "Команда завершилась успешно, но число выполненных тестов не подтверждено"
                    value["checks"].append({**command, **result, "status": status})
                    self._save("qa_result", value["project_id"], value)
                    if self.cancel.is_set():
                        break
                value["status"] = quality_gate(value["checks"], value["configuration"]["required_categories"])
                if len(value["checks"]) != len(value["configuration"]["commands"]):
                    value["status"] = "PARTIAL"
                baseline = self._page("qa_baseline", project_id=value["project_id"], limit=1)["items"]
                value["comparison"] = {"status": "Нет baseline"}
                if baseline and baseline[0].get("fingerprint") == value["fingerprint"]:
                    prior = {r["id"]: r["status"] for r in baseline[0]["checks"]}
                    value["comparison"] = {"status": "Сопоставимая конфигурация", "baseline_id": baseline[0]["result_id"], "new_regressions": [r["id"] for r in value["checks"] if prior.get(r["id"]) == "PASS" and r["status"] != "PASS"], "limitation": "Сравнение на уровне команд; отдельные test-case и нестабильность среды не выводятся из exit code"}
        except Exception as exc:
            value.update(status="BLOCKED", error=str(exc))
        finally:
            value["finished_at"] = time.time()
            self._save("qa_result", value["project_id"], value)
            with self.lock:
                self.active = None

    def results(self, project_id, limit=50, offset=0):
        self.store.project(project_id)
        return self._page("qa_result", project_id=project_id, limit=limit, offset=offset)

    def get_result(self, result_id):
        return self._unpack(self.suite.get("qa_result", result_id))

    def promote_baseline(self, project_id, result_id):
        value = self.get_result(result_id)
        if value["project_id"] != project_id or value["status"] != "PASS":
            raise ValueError("Baseline может быть только успешно завершённой проверкой этого проекта")
        existing = self._page("qa_baseline", project_id=project_id, limit=1)["items"]
        return self._save("qa_baseline", project_id, {"id": existing[0]["id"] if existing else "qa_baseline_" + uuid.uuid4().hex, "result_id": result_id, "head": value["head"], "fingerprint": value["fingerprint"], "checks": value["checks"]})

    def report(self, result_id):
        value = self.get_result(result_id)
        lines = ["# QA Arena", f"Статус: {value['status']}", f"Git HEAD: {value['head']}", f"Запуск: {value.get('run_id') or 'Не связан'}", "", f"Среда: Docker без сети; команд выполнено: {len(value['checks'])}. Зависимости не устанавливались."]
        for check in value["checks"]:
            lines.append(f"- {check['id']}: {check['status']}; exit={check['exit_code']}; {check['duration_seconds']} сек.")
        if value.get("comparison"):
            lines.extend(["", "## Сравнение с baseline", json.dumps(value["comparison"],ensure_ascii=False)])
        if value.get("error"):
            lines.append(value["error"])
        return "\n".join(lines)

    def close(self):
        self.cancel.set()
        self.executor.shutdown(wait=True, cancel_futures=True)
