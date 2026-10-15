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
    @staticmethod
    def endpoint():
        endpoint = os.environ.get("DOCKER_HOST") or ("npipe:////./pipe/docker_engine" if os.name == "nt" else "unix:///var/run/docker.sock")
        if not (endpoint.startswith("unix:///") or endpoint.startswith("npipe:////./pipe/")):
            raise ValueError("Удалённый сервер Docker не разрешён для QA: выберите локальный сокет или именованный канал")
        return endpoint

    @classmethod
    def command(cls, *args):
        return ["docker", "--host", cls.endpoint(), *args]

    @staticmethod
    def environment():
        # Explicit local --host must not be overridden by saved contexts/TLS settings.
        return {key: value for key, value in os.environ.items() if key not in {"DOCKER_CONTEXT", "DOCKER_TLS", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH"}}

    @classmethod
    def _call(cls, *args):
        return subprocess.run(cls.command(*args), check=True, capture_output=True, timeout=10, env=cls.environment()).stdout.decode("utf-8", errors="replace")

    def inspect_daemon(self):
        result = {"available": bool(shutil.which("docker")), "healthy": False, "local": True, "os_type": None, "endpoint": None, "reason": None}
        if not result["available"]:
            result["reason"] = "Командный клиент Docker не установлен. Запуск команд на основном компьютере запрещён."
            return result
        try:
            result["endpoint"] = self.endpoint()
            info = json.loads(self._call("info", "--format", '{"os_type":{{json .OSType}},"id":{{json .ID}},"name":{{json .Name}},"version":{{json .ServerVersion}}}'))
            result.update(os_type=info["os_type"], daemon_id=info.get("id"), daemon_name=info.get("name"), version=info.get("version"))
            result["healthy"] = info["os_type"] == "linux"
            if not result["healthy"]:
                result["reason"] = "Включите режим контейнеров Linux; эта среда проверки не поддерживает контейнеры Windows."
        except ValueError as exc:
            result["reason"] = str(exc) if "Удалённый сервер Docker" in str(exc) else "Не удалось прочитать сведения сервера Docker"
            result["local"] = False if "Удалённый сервер Docker" in str(exc) else True
        except (subprocess.SubprocessError, OSError):
            result["reason"] = "Локальный сервер Docker недоступен. Запустите Docker Desktop и включите контейнеры Linux."
        return result

    def images(self, limit=50):
        ids = list(dict.fromkeys(self._call("image", "ls", "--quiet", "--no-trunc").splitlines()))[:min(50, max(1, limit))]
        if not ids:
            return []
        image_format = '{"id":{{json .Id}},"tags":{{json .RepoTags}},"digests":{{json .RepoDigests}},"size_bytes":{{.Size}},"os_type":{{json .Os}}}'
        return [json.loads(line) for line in self._call("image", "inspect", "--format", image_format, *ids).splitlines()][:50]

    def inspect_image(self, image):
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_./:-]*@sha256:[a-f0-9]{64}|sha256:[a-f0-9]{64}", image):
            raise ValueError("Требуется локальный образ, закреплённый идентификатором SHA256")
        image_format = '{"id":{{json .Id}},"tags":{{json .RepoTags}},"digests":{{json .RepoDigests}},"size_bytes":{{.Size}},"os_type":{{json .Os}}}'
        value = json.loads(self._call("image", "inspect", "--format", image_format, image))
        if image.startswith("sha256:") and image != value.get("id"):
            raise ValueError("SHA256 локального образа не совпадает")
        if "@sha256:" in image and image not in (value.get("digests") or []):
            raise ValueError("Контрольная сумма локального образа не совпадает")
        if value.get("os_type") != "linux":
            raise ValueError("Для изоляции нужен Linux-образ")
        return value

    def available(self, image):
        daemon = self.inspect_daemon()
        if not daemon["healthy"]:
            return False, daemon["reason"]
        try:
            self.inspect_image(image)
        except (subprocess.SubprocessError, OSError, ValueError):
            return False, "Подтверждённый локальный Linux-образ Docker недоступен. Загрузка образов отключена."
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
            command = self.command("run", "--pull=never", "--name", name, "--rm", "--network=none", "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges", "--pids-limit=128", "--memory=512m", "--cpus=1", "--user=65534:65534", "--tmpfs=/work:rw,nosuid,nodev,size=192m,mode=1777", "--tmpfs=/tmp:rw,nosuid,nodev,size=64m,mode=1777", "--mount", f"type=bind,source={source},target=/source,readonly", "--workdir=/work", "--entrypoint=/bin/sh", image, "-c", 'cp -R /source/. /work/ && exec "$@"', "qa", *argv)
            # Docker client proxy defaults must not leak credentials/configuration
            # into untrusted test processes, even with container networking disabled.
            position = command.index("--workdir=/work")
            proxy_overrides = [part for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "all_proxy", "no_proxy") for part in ("--env", key + "=")]
            command[position:position] = proxy_overrides
            started = time.monotonic()
            with tempfile.TemporaryFile() as log:
                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=self.environment())
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
                            subprocess.run(self.command("rm", "-f", name), capture_output=True, timeout=15, env=self.environment())
                        finally:
                            process.kill()
                    process.wait(timeout=10)
                    reader.join(timeout=3)
                if reason is None and process.returncode in {125, 126, 127}:
                    reason = "Изолированная среда не смогла запустить команду: проверьте Docker, образ и инструменты (код завершения " + str(process.returncode) + ")"
                return {"exit_code": process.returncode, "duration_seconds": round(time.monotonic() - started, 3), "log": output.decode("utf-8", errors="replace"), "error": reason}


def quality_gate(results, required_categories, planned_count=None, cancelled=False, blocked=False):
    """One precedence rule for every exit, including interruptions: FAIL > BLOCKED."""
    if any(r["status"] == "FAIL" for r in results):
        return "FAIL"
    if blocked or cancelled or any(r["status"] == "BLOCKED" for r in results):
        return "BLOCKED"
    if not results:
        return "NOT RUN"
    required = [r for r in results if r.get("required", True)]
    passed_categories = {r["category"] for r in results if r["status"] == "PASS"}
    if planned_count is not None and len(results) != planned_count:
        return "PARTIAL"
    if not required or "test" not in passed_categories or not set(required_categories).issubset(passed_categories):
        return "PARTIAL"
    if any(r["status"] != "PASS" for r in results):
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
            config = item.get("configuration", {})
            item.update(status=quality_gate(item.get("checks", []), config.get("required_categories", ["test"]), planned_count=len(config.get("commands", [])), blocked=True), error="Приложение завершилось во время проверки")
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
        names = set(safe_files(path))
        suggestions = []
        def suggest(key, category, argv, source):
            suggestions.append({"id": key, "category": category, "argv": argv, "required": True, "source": source, "confirmed": False})
        if "pytest.ini" in names or "conftest.py" in names:
            suggest("pytest", "test", ["python", "-m", "pytest"], "pytest.ini" if "pytest.ini" in names else "conftest.py")
        elif "pyproject.toml" in names:
            text = safe_read(path, "pyproject.toml").decode("utf-8", errors="replace")
            if "[tool.pytest" in text:
                suggest("pytest", "test", ["python", "-m", "pytest"], "pyproject.toml")
        if "Cargo.toml" in names:
            suggest("cargo_test", "test", ["cargo", "test", "--offline"], "Cargo.toml")
        if any(name.endswith((".sln", ".csproj", ".fsproj")) and "/" not in name for name in names):
            suggest("dotnet_test", "test", ["dotnet", "test", "--no-restore"], "Git: .sln/.csproj/.fsproj")
        if "package.json" in names:
            try:
                scripts = json.loads(safe_read(path, "package.json")).get("scripts", {})
                for key in ("test", "build", "lint"):
                    if key in scripts:
                        suggest("npm_" + key, key, ["npm", "run", key], "package.json scripts." + key)
            except (ValueError, OSError):
                pass
        if not any(item["category"] == "test" for item in suggestions) and any(Path(name).name.startswith("test_") and name.endswith(".py") for name in names):
            suggest("unittest", "test", ["python", "-m", "unittest", "discover", "-v"], "Git: test_*.py; проверьте используемую систему тестирования")
        project_commands = self.store.project(project_id).get("commands", {})
        if isinstance(project_commands, dict):
            for category in ("test", "build", "lint", "typecheck"):
                argv = project_commands.get(category)
                if isinstance(argv, list) and argv and all(isinstance(part, str) for part in argv):
                    suggest("project_" + category, category, argv[:32], "Настройки проекта (требуется подтверждение в QA)")
        return {"suggestions": suggestions, "configuration": self.configuration(project_id), "files_scanned": len(names), "limitation": "Статический анализ отслеживаемых Git-файлов; команды и инструменты не запускались. Предложения не подтверждают наличие инструментов в образе. Нужен локальный Linux-образ Docker с зависимостями; сеть отключена. Секреты, симлинки и неотслеживаемые файлы исключены."}

    def setup(self, project_id):
        discovery = self.discover(project_id)
        runner = self.runner if isinstance(self.runner, DockerRunner) else DockerRunner()
        daemon = runner.inspect_daemon()
        images, image_error = [], None
        if daemon["healthy"]:
            try:
                images = runner.images()
            except (subprocess.SubprocessError, OSError, ValueError):
                image_error = "Не удалось прочитать список локальных образов"
        return {**discovery, "docker": daemon, "images": images, "image_error": image_error,
                "remediation": ["Установите или запустите Docker Desktop самостоятельно; включите контейнеры Linux.", "Подготовьте доверенный Linux-образ с /bin/sh, cp, инструментами проекта и уже установленными зависимостями. QA не скачивает образы и пакеты.", "Выберите локальный идентификатор образа SHA256 или RepoDigest, подтвердите образ и проверьте предложенные команды — массивы аргументов JSON.", "Сохраните конфигурацию, откройте предварительный просмотр и явно подтвердите тестовый запуск. Тестовый запуск использует ту же изолированную среду QA."],
                "test_run_requires_confirmation": True, "automatic_pull": False, "automatic_install": False}

    def verify_setup(self, project_id, image, confirmed=False):
        self.store.project(project_id)
        if confirmed is not True:
            raise ValueError("Подтвердите выбранный локальный образ перед проверкой")
        runner = self.runner if isinstance(self.runner, DockerRunner) else DockerRunner()
        daemon = runner.inspect_daemon()
        if not daemon["healthy"]:
            return {"available": False, "docker": daemon, "reason": daemon["reason"], "tools_executed": False}
        try:
            inspected = runner.inspect_image(image)
        except (subprocess.SubprocessError, OSError, ValueError) as exc:
            reason = str(exc) if isinstance(exc, ValueError) else "Выбранный неизменяемый локальный образ не найден"
            return {"available": False, "docker": daemon, "reason": reason, "tools_executed": False}
        return {"available": True, "docker": daemon, "image": inspected, "pinned_image": inspected["id"], "tools_executed": False,
                "limitation": "Проверены сервер Docker и метаданные локального образа. Наличие и работоспособность инструментов проверяются только при подтверждённом тестовом запуске.",
                "next_step": "Сохраните команды QA, откройте предварительный просмотр и подтвердите тестовый запуск"}

    def configuration(self, project_id):
        self.store.project(project_id)
        items = self._page("qa_config", project_id=project_id, limit=1)["items"]
        return items[0] if items else None

    def configure(self, project_id, data):
        self.store.project(project_id)
        image = str(data.get("image", ""))
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_./:-]*@sha256:[a-f0-9]{64}|sha256:[a-f0-9]{64}", image):
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
        interrupted = False
        try:
            available, reason = self.runner.available(value["configuration"]["image"])
            if not available:
                interrupted = True
                value.update(error=reason)
            else:
                for command in value["configuration"]["commands"]:
                    if self.cancel.is_set():
                        break
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
                baseline = self._page("qa_baseline", project_id=value["project_id"], limit=1)["items"]
                value["comparison"] = {"status": "Нет эталона проверок"}
                if baseline and baseline[0].get("fingerprint") == value["fingerprint"]:
                    prior = {r["id"]: r["status"] for r in baseline[0]["checks"]}
                    value["comparison"] = {"status": "Сопоставимая конфигурация", "baseline_id": baseline[0]["result_id"], "new_regressions": [r["id"] for r in value["checks"] if prior.get(r["id"]) == "PASS" and r["status"] != "PASS"], "limitation": "Сравнение на уровне команд; по коду завершения нельзя определить отдельные тестовые сценарии и нестабильность среды"}
        except Exception as exc:
            interrupted = True
            value.update(error="Не удалось выполнить проверку QA. Подробности: " + str(exc))
        finally:
            cancelled = self.cancel.is_set()
            if cancelled:
                value["error"] = "QA отменена: оставшиеся команды не выполнялись; результаты выполненных проверок сохранены"
            value["cancelled"] = cancelled
            value["planned_count"] = len(value["configuration"]["commands"])
            value["status"] = quality_gate(value["checks"], value["configuration"]["required_categories"], planned_count=value["planned_count"], cancelled=cancelled, blocked=interrupted)
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
            raise ValueError("Эталоном может быть только успешно завершённая проверка этого проекта")
        existing = self._page("qa_baseline", project_id=project_id, limit=1)["items"]
        return self._save("qa_baseline", project_id, {"id": existing[0]["id"] if existing else "qa_baseline_" + uuid.uuid4().hex, "result_id": result_id, "head": value["head"], "fingerprint": value["fingerprint"], "checks": value["checks"]})

    def report(self, result_id):
        value = self.get_result(result_id)
        lines = ["# QA Arena", f"Статус: {value['status']}", f"Git HEAD: {value['head']}", f"Запуск: {value.get('run_id') or 'Не связан'}", "", f"Среда: Docker без сети; команд выполнено: {len(value['checks'])}. Зависимости не устанавливались."]
        for check in value["checks"]:
            lines.append(f"- {check['id']}: {check['status']}; код завершения={check['exit_code']}; {check['duration_seconds']} сек.")
        if value.get("comparison"):
            lines.extend(["", "## Сравнение с эталоном проверок", json.dumps(value["comparison"],ensure_ascii=False)])
        if value.get("error"):
            lines.append(value["error"])
        return "\n".join(lines)

    def close(self):
        self.cancel.set()
        self.executor.shutdown(wait=True, cancel_futures=True)
