"""Durable, opt-in sequential dispatch through the existing Engine.

Lock order is engine -> service -> store. The worker releases the service lock
around Engine.create/launch so close() can revoke dispatch promptly. Engine.close
must follow this service's close, and precede Store.close (including on timeout).
Tasks use the normal independent run/worktree lifecycle; no automatic merge occurs.
"""
import json
import threading
import uuid

from codex_team.models import RunRequest
from codex_team.storage import now, sanitize


class QueueConflict(ValueError):
    """The queue changed, is blocked, or cannot perform the requested operation."""


class MissionQueue:
    MAX_PENDING = 20
    HISTORY_LIMIT = 100
    OPEN = {"pending", "running", "blocked"}

    def __init__(self, engine, store, poll_interval=0.1):
        self.engine, self.store = engine, store
        self.lock = threading.RLock()
        self._wake = threading.Event()
        self._closed = False
        self._enabled = False
        self._worker = None
        self._poll = max(0.01, poll_interval)
        self._reason = None
        with self.store.lock:
            self.store.db.execute("CREATE TABLE IF NOT EXISTS mission_queue (id TEXT PRIMARY KEY, client_id TEXT UNIQUE NOT NULL, data TEXT NOT NULL)")
            self.store.db.commit()

    def _check(self):
        if self._closed or self.engine.closed:
            raise QueueConflict("Очередь миссий закрыта")

    def _rows(self):
        # Preserve every historical request/idempotency key in SQLite; only the
        # response and reconciliation working set are bounded.
        with self.store.lock:
            rows = self.store.db.execute("""
                SELECT data FROM mission_queue
                WHERE json_extract(data,'$.status') IN ('pending','running','blocked')
                OR id IN (SELECT id FROM mission_queue
                    WHERE json_extract(data,'$.status') NOT IN ('pending','running','blocked')
                    ORDER BY json_extract(data,'$.updated_at') DESC, id DESC LIMIT ?)
            """, (self.HISTORY_LIMIT,)).fetchall()
        return sorted((json.loads(row[0]) for row in rows), key=lambda item: (item["position"], item["created_at"], item["id"]))

    def _save(self, item):
        if self._closed:
            return
        item["updated_at"] = now()
        with self.store.lock:
            self.store.db.execute("INSERT INTO mission_queue VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data", (item["id"], item["client_id"], json.dumps(item, ensure_ascii=False)))
            self.store.db.commit()

    def _find(self, item_id):
        with self.store.lock:
            row = self.store.db.execute("SELECT data FROM mission_queue WHERE id=?", (item_id,)).fetchone()
        if row is None:
            raise KeyError(item_id)
        return json.loads(row[0])

    def _run(self, item):
        if not item.get("run_id"):
            return None
        try:
            return self.store.run(item["run_id"])
        except KeyError:
            return None

    def _reconcile(self):
        """Never infer success from thread disappearance or a missing run."""
        for item in self._rows():
            if item["status"] not in {"running", "blocked"}:
                continue
            if item.get("run_id") in self.engine.active:
                continue
            run = self._run(item)
            state = run.get("state") if run else None
            if state == "DONE":
                item.update(status="done", reason=None)
                self._save(item)
            elif item["status"] == "running":
                detail = run.get("error") if run else None
                item.update(status="blocked", reason=f"Запуск {state or 'не найден'}: {detail or 'возобновите связанный запуск до DONE или пропустите миссию, затем явно запустите очередь.'}")
                self._save(item)
                self._enabled = False
                self._reason = item["reason"]

    def _view(self, item, full=False):
        request = RunRequest.model_validate(item["request"])
        run = self._run(item)
        result = {key: item.get(key) for key in ("id", "client_id", "position", "status", "run_id", "reason", "created_at", "updated_at")}
        result.update(task=sanitize(request.task)[:400], workspace=request.workspace, mode=request.mode,
                      access_level=request.access_level, isolated=request.isolated,
                      max_agent_calls=request.max_agent_calls, max_run_duration=request.max_run_duration,
                      max_total_tokens=request.max_total_tokens, run_state=run.get("state") if run else None)
        result["reason"] = sanitize(result["reason"])
        if full:
            result["request"] = {**request.model_dump(), "confirmed_full_access": request.confirmed_full_access}
        return result

    def _list(self):
        rows = self._rows()
        pending = [item for item in rows if item["status"] in self.OPEN]
        blocked = next((item for item in pending if item["status"] == "blocked"), None)
        active = next((item for item in pending if item["status"] == "running"), None)
        state = "running" if self._enabled else "blocked" if blocked else "paused" if pending or self._reason else "idle"
        reason = blocked["reason"] if blocked else self._reason
        if pending and not self._enabled and not reason:
            reason = "Очередь приостановлена. Для выполнения миссий явно нажмите «Запустить»."
        return {"items": [self._view(item) for item in rows], "summary": {
            "state": state, "pending": len(pending), "active_id": active["id"] if active else None,
            "reason": sanitize(reason), "max_pending": self.MAX_PENDING,
            "total_pending_call_limit": sum(RunRequest.model_validate(item["request"]).max_agent_calls for item in pending)}}

    def list(self):
        with self.engine.lock, self.lock:
            self._check()
            self._reconcile()
            return self._list()

    def get(self, item_id):
        with self.engine.lock, self.lock:
            self._check()
            self._reconcile()
            return self._view(self._find(item_id), full=True)

    def enqueue(self, request: RunRequest, client_id):
        request = RunRequest.model_validate(request)
        try:
            client_id = str(uuid.UUID(str(client_id)))
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError("client_id должен быть UUID") from exc
        if request.access_level == "full-access" and not request.confirmed_full_access:
            raise ValueError("Требуется явное подтверждение полного доступа")
        if not request.isolated:
            raise ValueError("Для миссий очереди требуется изолированная рабочая копия Git")
        # Preserve explicit fields: project policy defaults are applied by Engine.create.
        payload = {**request.model_dump(exclude_unset=True), "confirmed_full_access": request.confirmed_full_access}
        with self.engine.lock, self.lock:
            self._check()
            rows = self._rows()
            with self.store.lock:
                row = self.store.db.execute("SELECT data FROM mission_queue WHERE client_id=?", (client_id,)).fetchone()
            existing = json.loads(row[0]) if row else None
            if existing:
                if existing["request"] != payload:
                    raise QueueConflict("Этот client_id уже принадлежит другому запросу")
                return self._view(existing)
            if sum(item["status"] in self.OPEN for item in rows) >= self.MAX_PENDING:
                raise QueueConflict("Очередь заполнена: не более 20 незавершённых миссий")
            # Validation is local and never creates a run/provider or changes Git.
            self.engine.workspace.validate(request.workspace)
            self.engine.registry.pipeline(request.mode, request.pack, request.specialists)
            with self.store.lock:
                last_position = self.store.db.execute("SELECT COALESCE(MAX(json_extract(data,'$.position')),-1) FROM mission_queue").fetchone()[0]
            item = {"id": "mission_" + uuid.uuid4().hex, "client_id": client_id, "request": payload,
                    "position": last_position + 1,
                    "status": "pending", "run_id": None, "reason": None, "created_at": now()}
            self._save(item)
            return self._view(item)

    def start(self, confirmed=False):
        if confirmed is not True:
            raise ValueError("Требуется явное подтверждение запуска очереди")
        with self.engine.lock, self.lock:
            self._check()
            self._reconcile()
            rows = self._rows()
            own_ids = {item["run_id"] for item in rows if item["status"] == "running"}
            if any(run_id not in own_ids for run_id in self.engine.active):
                raise QueueConflict("Уже выполняется другой запуск. Дождитесь завершения или приостановите его перед запуском очереди.")
            if any(item["status"] == "blocked" for item in rows):
                raise QueueConflict("Завершите заблокированный связанный запуск до DONE или пропустите миссию перед запуском очереди.")
            self._enabled = True
            self._reason = None
            if self._worker is None:
                self._worker = threading.Thread(target=self._work, name="mission-queue", daemon=True)
                self._worker.start()
            self._wake.set()
            return self._list()

    def pause(self):
        with self.engine.lock, self.lock:
            self._check()
            self._enabled = False
            self._reason = "Очередь приостановлена. Текущий запуск завершится; для продолжения явно запустите очередь."
            self._wake.set()
            self._reconcile()
            return self._list()

    def move(self, item_id, direction):
        if direction not in {"up", "down"}:
            raise ValueError("Направление должно быть up или down")
        with self.engine.lock, self.lock:
            self._check()
            self._reconcile()
            item = self._find(item_id)
            if item["status"] != "pending":
                raise QueueConflict("Изменять порядок можно только у ожидающих миссий")
            rows = [row for row in self._rows() if row["status"] == "pending"]
            index = next(index for index, row in enumerate(rows) if row["id"] == item_id)
            target = index + (-1 if direction == "up" else 1)
            if not 0 <= target < len(rows):
                raise QueueConflict("Миссия уже находится на краю очереди ожидания")
            other = rows[target]
            item["position"], other["position"] = other["position"], item["position"]
            self._save(item)
            self._save(other)
            return self._list()

    def skip(self, item_id):
        with self.engine.lock, self.lock:
            self._check()
            self._reconcile()
            item = self._find(item_id)
            if item["status"] not in self.OPEN:
                raise QueueConflict("Миссия уже завершена или пропущена")
            if item.get("run_id") in self.engine.active or item["status"] == "running":
                raise QueueConflict("Выполняемую миссию нельзя пропустить. Сначала приостановите или остановите связанный запуск.")
            item.update(status="skipped", reason="Миссия явно пропущена пользователем")
            self._save(item)
            return self._list()

    def _tick(self):
        # Engine lock also prevents a manual launch racing create + queue launch.
        with self.engine.lock:
            with self.lock:
                if self._closed or self.engine.closed or not self._enabled:
                    return
                self._reconcile()
                if not self._enabled:
                    return
                rows = self._rows()
                own_ids = {item["run_id"] for item in rows if item["status"] == "running"}
                if self.engine.active:
                    if any(run_id not in own_ids for run_id in self.engine.active):
                        self._enabled = False
                        self._reason = "Начался другой запуск. После его завершения явно запустите очередь."
                    return
                item = next((item for item in rows if item["status"] == "pending"), None)
                if item is None:
                    self._enabled = False
                    self._reason = None
                    return
                # Claim durably before any execution; interrupted claims never auto retry.
                item.update(status="running")
                self._save(item)
                request = RunRequest.model_validate(item["request"])
            try:
                run = self.engine.create(request)
                with self.lock:
                    if self._closed or self.engine.closed:
                        return
                    item["run_id"] = run["id"]
                    self._save(item)
                    if not self._enabled:  # Pause during local preparation must not launch.
                        item.update(status="blocked", reason="Очередь приостановлена перед запуском. Возобновите связанный запуск или пропустите миссию.")
                        self._save(item)
                        return
                # Do not hold service lock during provider setup: close can revoke future work.
                if self._closed or self.engine.closed:
                    return
                self.engine.launch(run["id"])
            except Exception as exc:
                with self.lock:
                    if not self._closed:
                        item.update(status="blocked", reason=f"Не удалось запустить миссию: {str(exc)[:1000]}. Возобновите связанный запуск или пропустите миссию, затем явно запустите очередь.")
                        self._save(item)
                        self._enabled = False
                        self._reason = item["reason"]

    def _work(self):
        while not self._closed:
            with self.lock:
                enabled = self._enabled
            self._wake.wait(self._poll if enabled else None)
            self._wake.clear()
            if self._closed:
                return
            try:
                self._tick()
            except Exception:
                # An unexpected storage/lifecycle error must never advance the queue.
                with self.lock:
                    self._enabled = False
                    self._reason = "Очередь остановлена из-за локальной ошибки. Проверьте связанные запуски перед продолжением."

    def close(self):
        # No engine lock: do not block behind preparation/provider setup. Parent must
        # subsequently close Engine before Store, which joins engine-owned work.
        with self.lock:
            self._closed = True
            self._enabled = False
            self._wake.set()
            worker = self._worker
        if worker and worker is not threading.current_thread():
            worker.join(timeout=2)
