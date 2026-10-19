"""Local run annotations and bounded, factual review reports.

Neither operation changes a run, executes code, reads its workspace, or calls a
provider. Notes remain literal in the local database; only exports are redacted.
"""
import re
from itertools import islice
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from .productivity import normalize_run
from .storage import now, sanitize


class UpdateNotebook(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=0, le=2**63 - 2, strict=True)
    favorite: bool = Field(strict=True)
    note: str = Field(max_length=10000, strict=True)


class RunNotebooks:
    def __init__(self, store):
        self.store = store
        with store.lock, store.db:
            store.db.execute("""CREATE TABLE IF NOT EXISTS run_notebooks(
                run_id TEXT PRIMARY KEY, revision INTEGER NOT NULL CHECK(revision>=1),
                favorite INTEGER NOT NULL CHECK(favorite IN (0,1)),
                note TEXT NOT NULL, updated_at TEXT NOT NULL)""")

    def _require_run(self, run_id):
        if self.store.db.execute("SELECT 1 FROM runs WHERE id=?", (run_id,)).fetchone() is None:
            raise HTTPException(status_code=404, detail="Запуск не найден. Обновите историю.")

    def _get(self, run_id):
        row = self.store.db.execute(
            "SELECT revision,favorite,note,updated_at FROM run_notebooks WHERE run_id=?", (run_id,),
        ).fetchone()
        if row is None:
            return {"run_id": run_id, "revision": 0, "favorite": False, "note": "", "updated_at": None}
        return {"run_id": run_id, "revision": row[0], "favorite": bool(row[1]), "note": row[2], "updated_at": row[3]}

    def get(self, run_id):
        with self.store.lock:
            self._require_run(run_id)
            return self._get(run_id)

    def update(self, run_id, body: UpdateNotebook):
        # BEGIN IMMEDIATE serializes the read/compare/write across connections,
        # including the first write where the implicit revision is zero.
        with self.store.lock, self.store.db:
            self.store.db.execute("BEGIN IMMEDIATE")
            self._require_run(run_id)
            current = self._get(run_id)
            if current["revision"] != body.expected_revision:
                raise HTTPException(status_code=409, detail={
                    "code": "notebook_conflict", "revision": current["revision"],
                    "message": "Заметка изменена в другом окне. Обновите её перед сохранением.",
                })
            self.store.db.execute(
                "INSERT INTO run_notebooks VALUES (?,?,?,?,?) ON CONFLICT(run_id) DO UPDATE SET "
                "revision=excluded.revision,favorite=excluded.favorite,note=excluded.note,updated_at=excluded.updated_at",
                (run_id, current["revision"] + 1, int(body.favorite), body.note, now()),
            )
            return self._get(run_id)


_LABELS = {
    "ru": {
        "title": "Отчёт по запуску Codex Team", "generated": "Сформирован (UTC)",
        "source": "Источник: сохранённая запись запуска и локальная заметка. Это снимок данных, а не новая проверка кода.",
        "unknown": "Нет данных", "yes": "Да", "no": "Нет", "task": "Сохранённая задача",
        "facts": "Фактические показатели", "settings": "Сохранённые параметры запуска",
        "stages": "Сохранённые результаты агентов", "role": "Роль", "summary": "Результат",
        "verdict": "Вердикт агента (не статус QA Arena)", "error": "Ошибка",
        "attempts": "Результатов в истории", "files": "Сохранённые пути изменённых файлов",
        "notebook": "Локальная заметка пользователя", "favorite": "В избранном",
        "note": "Текст пользователя (не вывод агента)", "warnings": "Ограничения отчёта",
        "none": "Нет сохранённых результатов", "empty_files": "Список пуст",
        "id": "Запуск", "state": "Состояние", "calls": "Вызовы агентов",
        "measured_tokens": "Наблюдаемые токены", "usage_complete": "Полнота наблюдаемых токенов",
        "duration_seconds": "Сохранённая длительность, с", "changed_files_count": "Изменённых файлов в записи",
        "created_at": "Создан", "started_at": "Начат", "completed_at": "Завершён",
        "workspace": "Рабочий каталог", "original_workspace": "Исходный каталог", "mode": "Режим",
        "pack": "Набор агентов", "access_level": "Уровень доступа", "specialists": "Специалисты",
        "max_iterations": "Лимит итераций", "max_agent_calls": "Лимит вызовов",
        "max_run_duration": "Лимит времени, с", "max_total_tokens": "Пользовательский лимит токенов",
        "max_parallel_agents": "Настроенный предел параллельности", "isolated": "Изоляция worktree",
        "auto_commit": "Автоматический коммит",
        "active_run": "Запуск не завершён. Данные могут измениться после экспорта.",
        "incomplete_usage": "Учёт токенов неполный или неизвестен; это не официальная квота аккаунта.",
        "truncated": "Часть длинных данных сокращена. Отчёт не содержит всех артефактов и журналов.",
        "scope": "Отчёт не подтверждает прохождение QA Arena и не проверяет текущее состояние файлов. Число результатов в истории не равно числу всех попыток агента.",
        "redaction": "Распознаваемые секреты скрыты автоматически. Перед передачей отчёта проверьте оставшийся текст и локальные пути.",
    },
    "en": {
        "title": "Codex Team run report", "generated": "Generated (UTC)",
        "source": "Source: the saved run record and local notebook. This is a data snapshot, not a new code check.",
        "unknown": "No data", "yes": "Yes", "no": "No", "task": "Saved task",
        "facts": "Recorded metrics", "settings": "Saved run settings",
        "stages": "Saved agent results", "role": "Role", "summary": "Result",
        "verdict": "Agent verdict (not a QA Arena status)", "error": "Error",
        "attempts": "Recorded results", "files": "Saved changed file paths",
        "notebook": "Local user notebook", "favorite": "Favorite",
        "note": "User text (not an agent finding)", "warnings": "Report limitations",
        "none": "No saved results", "empty_files": "The list is empty",
        "id": "Run", "state": "State", "calls": "Agent calls",
        "measured_tokens": "Observed tokens", "usage_complete": "Observed token completeness",
        "duration_seconds": "Recorded duration, seconds", "changed_files_count": "Changed files in the record",
        "created_at": "Created", "started_at": "Started", "completed_at": "Completed",
        "workspace": "Working directory", "original_workspace": "Original directory", "mode": "Mode",
        "pack": "Agent pack", "access_level": "Access level", "specialists": "Specialists",
        "max_iterations": "Iteration limit", "max_agent_calls": "Call limit",
        "max_run_duration": "Time limit, seconds", "max_total_tokens": "User token budget",
        "max_parallel_agents": "Configured concurrency limit", "isolated": "Worktree isolation",
        "auto_commit": "Automatic commit",
        "active_run": "The run is unfinished. Its data may change after export.",
        "incomplete_usage": "Token observations are incomplete or unknown; they are not the official account quota.",
        "truncated": "Some long data was shortened. The report does not include all artifacts or logs.",
        "scope": "This report does not certify QA Arena results or inspect the current files. Recorded result counts are not counts of all agent attempts.",
        "redaction": "Recognizable secrets were redacted automatically. Review the remaining text and local paths before sharing.",
    },
}


def _fence(value):
    """A longer fence keeps raw HTML, images, links and hostile fences inert."""
    value = sanitize(value).replace("\x00", "\ufffd")
    longest = max((len(match.group()) for match in re.finditer(r"`+", value)), default=0)
    fence = "`" * max(3, longest + 1)
    return f"{fence}text\n{value}\n{fence}"


def _export_text(value, limit):
    # A small lookahead lets recognizable credentials crossing a display limit
    # be redacted before trimming. Never scan an unbounded imported string.
    return sanitize(value[:limit + 1024])[:limit] if isinstance(value, str) else value


def _export_result(result):
    if not isinstance(result, dict):
        return result
    return {key: _export_text(result.get(key), limit)
            for key, limit in (("summary", 4000), ("error", 4000), ("verdict", 100)) if key in result}


def build_report(run, notebook, language="ru"):
    labels = _LABELS[language]
    # Imported/older records can be larger than today's configured call limits.
    # Bound normalization inputs too, rather than only shortening the output.
    snapshot = dict(run)
    for key, limit in (("task", 30000), ("error", 4000), ("workspace", 4096), ("original_workspace", 4096),
                       ("state", 100), ("mode", 100), ("pack", 100), ("access_level", 100),
                       ("id", 200), ("created_at", 100), ("started_at", 100), ("completed_at", 100)):
        snapshot[key] = _export_text(run.get(key), limit)
    if isinstance(run.get("usage"), list):
        snapshot["usage"] = run["usage"][:10000]
    if isinstance(run.get("result_history"), list):
        snapshot["result_history"] = [
            {"role": _export_text(entry.get("role"), 100), "result": _export_result(entry.get("result")),
             "error": _export_text(entry.get("error"), 4000)} if isinstance(entry, dict) else entry
            for entry in run["result_history"][-1000:]
        ]
    if isinstance(run.get("results"), dict):
        snapshot["results"] = {_export_text(role, 100): _export_result(result)
                               for role, result in islice(run["results"].items(), 64)}
    if isinstance(run.get("specialists"), list):
        snapshot["specialists"] = [_export_text(role, 100) for role in run["specialists"][:50]]
    normalized = normalize_run(snapshot)
    generated = now()
    warnings = []
    # Normalization bounds role history and free text. Track those reductions
    # explicitly instead of silently presenting an exhaustive record.
    history = run.get("result_history")
    results = run.get("results")
    truncated = isinstance(history, list) and len(history) > 1000
    truncated = truncated or isinstance(results, dict) and len(results) > 64
    truncated = truncated or isinstance(run.get("usage"), list) and len(run["usage"]) > 10000
    for key, limit in (("task", 30000), ("error", 4000), ("workspace", 4096), ("original_workspace", 4096),
                       ("state", 100), ("mode", 100), ("pack", 100), ("access_level", 100)):
        truncated = truncated or isinstance(run.get(key), str) and len(run[key]) > limit
    truncated = truncated or isinstance(run.get("specialists"), list) and len(run["specialists"]) > 50
    entries = history[-1000:] if isinstance(history, list) else []
    role_names = set()
    for entry in entries:
        if isinstance(entry, dict) and isinstance(entry.get("role"), str):
            role_names.add(entry["role"][:100])
    if isinstance(results, dict):
        role_names.update(role[:100] for role in islice(results, 64) if isinstance(role, str))
    truncated = truncated or len(role_names) > 64
    for entry in [*entries, *islice(results.values() if isinstance(results, dict) else [], 64)]:
        result = entry.get("result", entry) if isinstance(entry, dict) else {}
        if isinstance(result, dict):
            truncated = truncated or any(isinstance(result.get(key), str) and len(result[key]) > limit
                                         for key, limit in (("summary", 4000), ("error", 4000), ("verdict", 100)))
    if normalized["state"] not in {"COMPLETED", "FAILED", "STOPPED", "CANCELLED", "DONE", "ERROR"}:
        warnings.append("active_run")
    if not normalized["usage_complete"]:
        warnings.append("incomplete_usage")
    lines = [f"# {labels['title']}", f"{labels['generated']}: {generated}", labels["source"]]

    def value(value):
        if value is None:
            return labels["unknown"]
        if type(value) is bool:
            return labels["yes"] if value else labels["no"]
        return str(value)

    remaining = 150000

    def text(content):
        nonlocal remaining, truncated
        # Redact before the aggregate cut, so cutting inside a credential does
        # not turn its recognizable prefix into an unrecognized secret fragment.
        content = sanitize(value(content))
        if len(content) > remaining:
            content = content[:remaining]
            truncated = True
        remaining -= len(content)
        return _fence(content)

    def field(key, content):
        # User-controlled strings never enter headings, tables, links or HTML.
        lines.extend([f"### {labels[key]}", text(content)])

    field("id", normalized["id"])
    lines.append(f"## {labels['task']}")
    lines.append(text(normalized["task"]))
    # Reserve visibility for the user's note before large saved agent results
    # consume the bounded report text budget.
    lines.append(f"## {labels['notebook']}")
    field("favorite", notebook["favorite"])
    if notebook["note"]:
        field("note", notebook["note"][:10000])
    lines.append(f"## {labels['facts']}")
    for key in ("state", "calls", "measured_tokens", "usage_complete", "duration_seconds", "changed_files_count",
                "created_at", "started_at", "completed_at"):
        field(key, normalized[key])
    lines.append(f"## {labels['settings']}")
    for key in ("workspace", "original_workspace", "mode", "pack", "access_level", "max_iterations", "max_agent_calls",
                "max_run_duration", "max_total_tokens", "max_parallel_agents", "isolated", "auto_commit"):
        field(key, normalized[key])
    field("specialists", "\n".join(normalized["specialists"]) if normalized["specialists"] is not None else None)
    lines.append(f"## {labels['stages']}")
    if not normalized["stages"]:
        lines.append(labels["none"])
    for index, stage in enumerate(normalized["stages"], 1):
        lines.append(f"### {labels['role']} {index}")
        lines.append(text(stage["role"]))
        for key in ("summary", "verdict", "error", "attempts"):
            field(key, stage[key])
    if normalized["error"] is not None:
        field("error", normalized["error"])
    lines.append(f"## {labels['files']}")
    files = run.get("changed_files")
    if isinstance(files, list):
        paths = []
        truncated = truncated or len(files) > 200
        for path in files[:200]:
            if isinstance(path, str):
                truncated = truncated or len(path) > 4096
                paths.append(_export_text(path, 4096))
        lines.append(text("\n".join(paths)) if paths else labels["empty_files"])
    else:
        lines.append(labels["unknown"])
    if truncated:
        warnings.append("truncated")
    lines.append(f"## {labels['warnings']}")
    lines.extend(f"- {labels[key]}" for key in [*warnings, "scope", "redaction"])
    identifier = run.get("id") if isinstance(run.get("id"), str) else "run"
    safe_id = re.sub(r"[^A-Za-z0-9_-]", "-", identifier).strip("-")[:80] or "run"
    return {"run_id": run["id"], "filename": f"codex-team-{safe_id}.md", "language": language,
            "generated_at": generated, "truncated": bool(truncated), "warnings": warnings,
            "markdown": "\n\n".join(lines) + "\n"}


def create_run_notebook_router(store):
    notebooks = RunNotebooks(store)
    router = APIRouter(prefix="/api/runs/{run_id}")

    @router.get("/notebook")
    def get_notebook(run_id: str):
        return notebooks.get(run_id)

    @router.put("/notebook")
    def update_notebook(run_id: str, body: UpdateNotebook):
        return notebooks.update(run_id, body)

    @router.get("/report")
    def get_report(run_id: str, language: Literal["ru", "en"] = Query(default="ru")):
        # Hold one Store lock while reading both local sources, so a concurrent
        # in-process save cannot mix a different note into this snapshot.
        with store.lock:
            try:
                run = store.run(run_id)
            except KeyError:
                raise HTTPException(status_code=404, detail="Запуск не найден. Обновите историю.") from None
            notebook = notebooks.get(run_id)
        if not isinstance(run, dict):
            raise HTTPException(status_code=422, detail="Сохранённая запись запуска имеет неверный формат.")
        return build_report({**run, "id": run_id}, notebook, language)

    return router
