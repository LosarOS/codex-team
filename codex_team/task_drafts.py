"""Local compose drafts, independent of run creation and security consent.

Draft text is an editor buffer: preserve it literally, never send it to a
provider, and never interpret it as a request to execute a task.
"""
import json
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from .models import Mode
from .storage import now


class DraftData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task: str = Field(default="", max_length=30000)
    workspace: str = Field(default="", max_length=4096)
    mode: Mode = "standard"
    pack: str = Field(default="software-development", max_length=100)
    specialists: list[Annotated[str, Field(max_length=100)]] = Field(default_factory=list, max_length=50)
    max_iterations: int = Field(default=3, ge=1, le=10, strict=True)
    max_agent_calls: int = Field(default=15, ge=1, le=100, strict=True)
    max_run_duration: int = Field(default=1800, ge=30, le=86400, strict=True)


class SaveDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=0, le=2**63 - 2, strict=True)
    data: DraftData


class TaskDrafts:
    """A singleton draft with a retained revision tombstone after deletion."""

    def __init__(self, store):
        self.store = store
        with store.lock, store.db:
            store.db.execute("""CREATE TABLE IF NOT EXISTS task_draft(
                singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                revision INTEGER NOT NULL CHECK(revision>=0),
                updated_at TEXT, data TEXT)""")
            store.db.execute("INSERT OR IGNORE INTO task_draft VALUES (1,0,NULL,NULL)")

    @staticmethod
    def _response(row):
        revision, timestamp, data = row
        return {
            "revision": revision,
            "draft": None if data is None else {
                "revision": revision, "updated_at": timestamp, "data": json.loads(data)
            },
        }

    def get(self):
        with self.store.lock:
            row = self.store.db.execute("SELECT revision,updated_at,data FROM task_draft WHERE singleton=1").fetchone()
        return self._response(row)

    def _change(self, expected_revision, data):
        with self.store.lock, self.store.db:
            # Serialize other Store connections too, not only requests sharing
            # this instance's RLock. No read/modify/write race across processes.
            self.store.db.execute("BEGIN IMMEDIATE")
            row = self.store.db.execute("SELECT revision,updated_at,data FROM task_draft WHERE singleton=1").fetchone()
            if row[0] != expected_revision:
                raise HTTPException(status_code=409, detail={
                    "code": "draft_conflict", "revision": row[0],
                    "message": "Черновик изменён в другом окне. Обновите его перед сохранением.",
                })
            if data is None and row[2] is None:
                return self._response(row)
            revision = row[0] + 1
            timestamp = now()
            self.store.db.execute(
                "UPDATE task_draft SET revision=?,updated_at=?,data=? WHERE singleton=1",
                (revision, timestamp, data),
            )
            return self._response((revision, timestamp, data))

    def save(self, body: SaveDraft):
        # Deliberately bypass log/history sanitization: it would corrupt a user
        # editor buffer. Only these explicitly allowed local fields are stored.
        return self._change(body.expected_revision, json.dumps(body.data.model_dump(), ensure_ascii=False))

    def clear(self, expected_revision: int):
        return self._change(expected_revision, None)


def create_draft_router(store):
    drafts = TaskDrafts(store)
    router = APIRouter(prefix="/api/task-draft")

    @router.get("")
    def get_draft():
        return drafts.get()

    @router.put("")
    def save_draft(body: SaveDraft):
        return drafts.save(body)

    @router.delete("")
    def clear_draft(expected_revision: int = Query(ge=0, le=2**63 - 2)):
        return drafts.clear(expected_revision)

    return router
