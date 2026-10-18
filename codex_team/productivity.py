"""Local task templates and factual, read-only run comparisons.

Templates are editor buffers, not requests to run a task. Their field allowlist
is deliberately shared with drafts and cannot store security consent.
"""
import json
import math
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .budget_guardian import evaluate
from .storage import now
from .task_drafts import DraftData


class CreateTemplate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=1000)
    data: DraftData

    @field_validator("name")
    @classmethod
    def nonempty_name(cls, value):
        if not value.strip():
            raise ValueError("Укажите название шаблона")
        return value


class UpdateTemplate(CreateTemplate):
    expected_revision: int = Field(ge=1, le=2**63 - 2, strict=True)


class TaskTemplates:
    MAX_TEMPLATES = 200

    def __init__(self, store):
        self.store = store
        with store.lock, store.db:
            store.db.execute("""CREATE TABLE IF NOT EXISTS task_templates(
                id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL,
                revision INTEGER NOT NULL CHECK(revision>=1), created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL, data TEXT NOT NULL)""")

    @staticmethod
    def _response(row):
        result = dict(zip(("id", "name", "description", "revision", "created_at", "updated_at"), row[:6]))
        if len(row) > 6:
            result["data"] = json.loads(row[6])
        return result

    def page(self, query="", limit=50, offset=0):
        if len(query) > 200 or not 1 <= limit <= 50 or not 0 <= offset <= 100000:
            raise HTTPException(status_code=422, detail="Проверьте параметры списка шаблонов.")
        search = "%" + query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        where = " WHERE name LIKE ? ESCAPE '\\' OR description LIKE ? ESCAPE '\\'" if query else ""
        params = [search, search] if query else []
        with self.store.lock:
            total = self.store.db.execute("SELECT count(*) FROM task_templates" + where, params).fetchone()[0]
            rows = self.store.db.execute(
                "SELECT id,name,description,revision,created_at,updated_at FROM task_templates" + where
                + " ORDER BY updated_at DESC,id LIMIT ? OFFSET ?", [*params, limit, offset],
            ).fetchall()
        return {"items": [self._response(row) for row in rows], "total": total}

    def _row(self, template_id):
        row = self.store.db.execute("SELECT * FROM task_templates WHERE id=?", (template_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Шаблон не найден. Обновите список шаблонов.")
        return row

    def get(self, template_id):
        with self.store.lock:
            return self._response(self._row(template_id))

    def create(self, body: CreateTemplate):
        with self.store.lock, self.store.db:
            self.store.db.execute("BEGIN IMMEDIATE")
            if self.store.db.execute("SELECT count(*) FROM task_templates").fetchone()[0] >= self.MAX_TEMPLATES:
                raise HTTPException(status_code=409, detail={
                    "code": "template_limit",
                    "message": "Достигнут предел в 200 шаблонов. Удалите ненужный шаблон перед созданием нового.",
                })
            timestamp = now()
            row = (uuid4().hex, body.name, body.description, 1, timestamp, timestamp,
                   json.dumps(body.data.model_dump(), ensure_ascii=False))
            # Preserve literal local editor text, including documentation that
            # resembles credentials. Never copy it to settings, events or runs.
            self.store.db.execute("INSERT INTO task_templates VALUES (?,?,?,?,?,?,?)", row)
            return self._response(row)

    @staticmethod
    def _check_revision(row, expected_revision):
        if row[3] != expected_revision:
            raise HTTPException(status_code=409, detail={
                "code": "template_conflict", "revision": row[3],
                "message": "Шаблон изменён в другом окне. Обновите его перед сохранением или удалением.",
            })

    def update(self, template_id, body: UpdateTemplate):
        with self.store.lock, self.store.db:
            self.store.db.execute("BEGIN IMMEDIATE")
            row = self._row(template_id)
            self._check_revision(row, body.expected_revision)
            self.store.db.execute(
                "UPDATE task_templates SET name=?,description=?,revision=?,updated_at=?,data=? WHERE id=?",
                (body.name, body.description, row[3] + 1, now(),
                 json.dumps(body.data.model_dump(), ensure_ascii=False), template_id),
            )
            return self._response(self._row(template_id))

    def delete(self, template_id, expected_revision):
        with self.store.lock, self.store.db:
            self.store.db.execute("BEGIN IMMEDIATE")
            row = self._row(template_id)
            self._check_revision(row, expected_revision)
            self.store.db.execute("DELETE FROM task_templates WHERE id=?", (template_id,))
            return {"deleted": True, "id": template_id}


def _number(value, *, integer=False, positive=False):
    if type(value) not in ((int,) if integer else (int, float)):
        return None
    if value < (1 if positive else 0) or (type(value) is float and not math.isfinite(value)):
        return None
    if type(value) is int and value > 2**63 - 1:
        return None
    return value


def _text(value, limit):
    return value[:limit] if isinstance(value, str) else None


def _stages(run):
    """Latest recorded role result; no role name implies a QA Arena verdict."""
    stages, attempts = {}, {}
    history = run.get("result_history")
    history = history if isinstance(history, list) else []
    for entry in history[-1000:]:
        if not isinstance(entry, dict) or not isinstance(entry.get("role"), str):
            continue
        role = entry["role"][:100]
        if role not in stages and len(stages) >= 64:
            continue
        result = entry.get("result")
        stages[role] = {**(result if isinstance(result, dict) else {}),
                        "error": result.get("error", entry.get("error")) if isinstance(result, dict) else entry.get("error")}
        attempts[role] = attempts.get(role, 0) + 1
    results = run.get("results")
    if isinstance(results, dict):
        for role, result in results.items():
            if isinstance(role, str) and role[:100] not in stages and len(stages) < 64:
                stages[role[:100]] = result
    output = []
    for role, result in stages.items():
        result = result if isinstance(result, dict) else {}
        output.append({"role": role, "summary": _text(result.get("summary"), 4000),
                       "verdict": _text(result.get("verdict"), 100),
                       "error": _text(result.get("error"), 4000), "attempts": attempts.get(role)})
    return output


def normalize_run(run):
    calls = _number(run.get("calls"), integer=True)
    usage = run.get("usage")
    usage = usage if isinstance(usage, list) else []
    # Old or interrupted records may contain incomplete provider events. Let
    # Budget Guardian measure valid token observations without inventing zeros.
    budget = evaluate({"calls": calls or 0,
                       "max_agent_calls": _number(run.get("max_agent_calls"), integer=True, positive=True) or 100,
                       "max_total_tokens": _number(run.get("max_total_tokens"), integer=True, positive=True),
                       "usage": [entry if isinstance(entry, dict) else {} for entry in usage]})
    result = {key: _text(run.get(key), limit) for key, limit in (
        ("id", 200), ("state", 100), ("task", 30000), ("workspace", 4096),
        ("original_workspace", 4096), ("project_id", 200), ("mode", 100), ("pack", 100),
        ("access_level", 100), ("created_at", 100), ("started_at", 100),
        ("completed_at", 100), ("error", 4000))}
    result.update(calls=calls, measured_tokens=budget["measured_tokens"],
                  usage_complete=calls is not None and budget["usage_complete"],
                  duration_seconds=_number(run.get("elapsed_seconds")),
                  changed_files_count=len(run["changed_files"]) if isinstance(run.get("changed_files"), list) else None,
                  stages=_stages(run))
    for key in ("max_iterations", "max_agent_calls", "max_run_duration", "max_total_tokens", "max_parallel_agents"):
        result[key] = _number(run.get(key), integer=True, positive=True)
    for key in ("isolated", "auto_commit"):
        result[key] = run.get(key) if type(run.get(key)) is bool else None
    specialists = run.get("specialists")
    result["specialists"] = [_text(role, 100) for role in specialists[:50] if isinstance(role, str)] if isinstance(specialists, list) else None
    return result


def compare_runs(store, left, right):
    if left == right:
        raise HTTPException(status_code=422, detail="Выберите два разных запуска для сравнения.")
    try:
        runs = [store.run(left), store.run(right)]
    except KeyError:
        raise HTTPException(status_code=404, detail="Один из запусков не найден. Обновите историю.") from None
    left_run, right_run = map(normalize_run, runs)
    projects = [item["original_workspace"] or item["workspace"] for item in (left_run, right_run)]
    comparable = bool(all(projects) and projects[0] == projects[1])
    warnings = []
    if not all(projects):
        warnings.append("project_unknown")
    elif not comparable:
        warnings.append("different_projects")
    if any(run["state"] in {"QUEUED", "RUNNING", "PAUSING", "STOPPING"} for run in (left_run, right_run)):
        warnings.append("active_runs_partial")
    if not all(run["usage_complete"] for run in (left_run, right_run)):
        warnings.append("incomplete_usage")
    if any(isinstance(run.get("result_history"), list) and len(run["result_history"]) > 1000 for run in runs):
        warnings.append("stage_history_truncated")
    return {"left": left_run, "right": right_run, "comparable_project": comparable, "warnings": warnings}


def create_productivity_router(store):
    templates = TaskTemplates(store)
    router = APIRouter(prefix="/api")

    @router.get("/task-templates")
    def list_templates(query: str = Query(default="", max_length=200),
                       limit: int = Query(default=50, ge=1, le=50),
                       offset: int = Query(default=0, ge=0, le=100000)):
        return templates.page(query, limit, offset)

    @router.post("/task-templates", status_code=201)
    def create_template(body: CreateTemplate):
        return templates.create(body)

    @router.get("/task-templates/{template_id}")
    def get_template(template_id: str):
        return templates.get(template_id)

    @router.put("/task-templates/{template_id}")
    def update_template(template_id: str, body: UpdateTemplate):
        return templates.update(template_id, body)

    @router.delete("/task-templates/{template_id}")
    def delete_template(template_id: str, expected_revision: int = Query(ge=1, le=2**63 - 2)):
        return templates.delete(template_id, expected_revision)

    @router.get("/run-comparison")
    def get_comparison(left: str = Query(min_length=1, max_length=200),
                       right: str = Query(min_length=1, max_length=200)):
        return compare_runs(store, left, right)

    return router
