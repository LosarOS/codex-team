"""Local queue endpoints share the application's existing security middleware."""
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, StrictBool, Field
from .models import RunRequest
from .mission_queue import QueueConflict

class Enqueue(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request: RunRequest
    client_id: UUID

class StartQueue(BaseModel):
    model_config = ConfigDict(extra='forbid')
    confirmed: StrictBool = False
    expected_revision: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    item_ids: list[str] = Field(max_length=20)

class Preflight(BaseModel):
    model_config = ConfigDict(extra="forbid")
    item_ids: list[str] = Field(max_length=20)

class Move(BaseModel):
    model_config = ConfigDict(extra='forbid')
    direction: Literal['up', 'down']


def create_queue_router(queue):
    router = APIRouter(prefix='/api/mission-queue')
    def call(method, *args, **kwargs):
        try:
            return method(*args, **kwargs)
        except QueueConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from None
    @router.get('')
    def listing():
        return call(queue.list)
    @router.post('')
    def enqueue(body: Enqueue):
        return call(queue.enqueue, body.request, body.client_id)
    @router.post('/preflight')
    def preflight(body: Preflight):
        return call(queue.preflight, body.item_ids)
    @router.post('/start')
    def start(body: StartQueue):
        return call(queue.start, body.confirmed, body.item_ids, body.expected_revision)
    @router.post('/pause')
    def pause():
        return call(queue.pause)
    @router.get('/{item_id}')
    def item(item_id: str):
        return call(queue.get, item_id)
    @router.post('/{item_id}/move')
    def move(item_id: str, body: Move):
        return call(queue.move, item_id, body.direction)
    @router.post('/{item_id}/skip')
    def skip(item_id: str):
        return call(queue.skip, item_id)
    return router
