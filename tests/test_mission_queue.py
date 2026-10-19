import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from codex_team.mission_queue import MissionQueue, QueueConflict
from codex_team.models import RunRequest
from codex_team.storage import Store


class FakeEngine:
    def __init__(self, store):
        self.store = store
        self.lock = threading.RLock()
        self.active = {}
        self.closed = False
        self.created = []
        self.launched = []
        self.launch_error = None
        self.workspace = SimpleNamespace(validate=lambda path: path)
        self.registry = SimpleNamespace(pipeline=lambda *args: ["coordinator"])

    def create(self, request):
        run = {"id": f"run_{len(self.created)}", "state": "QUEUED", "task": request.task}
        self.created.append(request)
        self.store.save_run(run)
        return run

    def launch(self, run_id):
        assert not self.active, "Concurrent dispatch"
        if self.launch_error:
            raise ValueError(self.launch_error)
        self.active[run_id] = {}
        self.launched.append(run_id)
        run = self.store.run(run_id)
        run["state"] = "RUNNING"
        self.store.save_run(run)

    def finish(self, state="DONE"):
        with self.lock:
            run_id = next(iter(self.active))
            run = self.store.run(run_id)
            run.update(state=state, error=None if state == "DONE" else "Review required")
            self.store.save_run(run)
            del self.active[run_id]


@pytest.fixture
def queue(tmp_path):
    store = Store(tmp_path / "queue.db")
    engine = FakeEngine(store)
    service = MissionQueue(engine, store, poll_interval=0.01)
    yield service, engine, store
    service.close()
    engine.closed = True
    store.close()


def add(service, task="Mission", **kwargs):
    return service.enqueue(RunRequest(workspace="/local", task=task, **kwargs), uuid.uuid4())


def eventually(predicate):
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    assert predicate()


def test_enqueue_and_reads_are_inert_literal_and_bounded(queue):
    service, engine, _ = queue
    task = '<script>do things</script>\nTOKEN=secret\n$HOME `literal`'
    item = add(service, task=task)
    assert not engine.created and not engine.launched
    assert service.get(item["id"])["request"]["task"] == task
    assert "secret" not in service.list()["items"][0]["task"]
    assert service.list()["summary"]["total_pending_call_limit"] == 15
    for index in range(19):
        add(service, str(index))
    with pytest.raises(QueueConflict, match="заполнена"):
        add(service)
    assert not engine.created


def test_full_access_consent_survives_dispatch(queue):
    service, engine, _ = queue
    with pytest.raises(ValueError, match="подтверждение"):
        add(service, access_level="full-access")
    add(service, access_level="full-access", confirmed_full_access=True)
    with pytest.raises(ValueError):
        service.start()
    with pytest.raises(ValueError):
        service.start(confirmed=1)
    service.start(confirmed=True)
    eventually(lambda: len(engine.launched) == 1)
    assert engine.created[0].confirmed_full_access is True
    assert engine.created[0].access_level == "full-access"


def test_serial_done_advances_but_only_once(queue):
    service, engine, _ = queue
    add(service, "First")
    add(service, "Second")
    service.start(True)
    service.start(True)
    eventually(lambda: len(engine.launched) == 1)
    time.sleep(0.04)
    assert len(engine.created) == 1
    engine.finish()
    eventually(lambda: len(engine.launched) == 2)
    assert [request.task for request in engine.created] == ["First", "Second"]
    engine.finish()
    eventually(lambda: service.list()["summary"]["pending"] == 0)
    assert [item["status"] for item in service.list()["items"]] == ["done", "done"]


@pytest.mark.parametrize("state", ["FAILED", "AUTH_REQUIRED", "USAGE_LIMIT", "PAUSED", "STOPPED", "INTERRUPTED", "USER_DECISION_REQUIRED", "QUEUED"])
def test_non_done_always_gates_following_mission(queue, state):
    service, engine, store = queue
    first = add(service)
    add(service, "Following")
    service.start(True)
    eventually(lambda: len(engine.launched) == 1)
    engine.finish(state)
    eventually(lambda: service.get(first["id"])["status"] == "blocked")
    assert len(engine.created) == 1
    assert service.get(first["id"])["run_id"] == "run_0"
    with pytest.raises(QueueConflict, match="заблокированный"):
        service.start(True)
    # A normal, user-controlled resume can satisfy the gate, but never autostarts.
    run = store.run("run_0")
    run["state"] = "DONE"
    store.save_run(run)
    assert service.get(first["id"])["status"] == "done"
    assert len(engine.created) == 1
    service.start(True)
    eventually(lambda: len(engine.created) == 2)


def test_pause_finishes_current_without_next(queue):
    service, engine, _ = queue
    first = add(service)
    add(service, "Next")
    service.start(True)
    eventually(lambda: len(engine.launched) == 1)
    service.pause()
    assert "run_0" in engine.active
    engine.finish()
    eventually(lambda: service.get(first["id"])["status"] == "done")
    time.sleep(0.03)
    assert len(engine.created) == 1
    service.start(True)
    eventually(lambda: len(engine.launched) == 2)


def test_concurrent_idempotence_payload_conflict(queue):
    service, engine, _ = queue
    client_id = uuid.uuid4()
    request = RunRequest(workspace="/local", task="Same")
    with ThreadPoolExecutor(max_workers=8) as pool:
        ids = list(pool.map(lambda _: service.enqueue(request, client_id)["id"], range(20)))
    assert len(set(ids)) == 1
    assert len(service.list()["items"]) == 1
    assert not engine.created
    with pytest.raises(QueueConflict, match="другому"):
        service.enqueue(RunRequest(workspace="/local", task="Different"), client_id)


def test_restart_requires_start_and_reconciles_interrupted(tmp_path):
    path = tmp_path / "queue.db"
    store = Store(path)
    engine = FakeEngine(store)
    service = MissionQueue(engine, store, 0.01)
    item = add(service)
    add(service, "Next")
    service.start(True)
    eventually(lambda: len(engine.launched) == 1)
    service.close()
    engine.finish("INTERRUPTED")
    store.close()
    store = Store(path)
    engine = FakeEngine(store)
    service = MissionQueue(engine, store, 0.01)
    try:
        assert service.get(item["id"])["status"] == "blocked"
        assert not engine.created
        with pytest.raises(QueueConflict):
            service.start(True)
        service.skip(item["id"])
        assert not engine.created
        service.start(True)
        eventually(lambda: len(engine.launched) == 1)
    finally:
        service.close()
        store.close()


def test_restart_pending_is_inert(queue):
    service, engine, store = queue
    add(service)
    service.close()
    restarted = MissionQueue(engine, store, .01)
    try:
        time.sleep(.03)
        assert not engine.created
        assert restarted.list()["summary"]["state"] == "paused"
    finally:
        restarted.close()


def test_launch_failure_is_not_success(queue):
    service, engine, _ = queue
    item = add(service)
    add(service)
    engine.launch_error = "Credentials unavailable"
    service.start(True)
    eventually(lambda: service.get(item["id"])["status"] == "blocked")
    assert service.get(item["id"])["run_id"] == "run_0"
    assert "Credentials unavailable" in service.get(item["id"])["reason"]
    assert not engine.launched
    assert len(engine.created) == 1


def test_foreign_active_never_dispatches(queue):
    service, engine, _ = queue
    add(service)
    engine.active["foreign"] = {}
    with pytest.raises(QueueConflict, match="другой запуск"):
        service.start(True)
    assert not engine.created


def test_reorder_skip_stale_and_running_races(queue):
    service, engine, _ = queue
    first, second = add(service, "First"), add(service, "Second")
    service.move(second["id"], "up")
    assert service.list()["items"][0]["id"] == second["id"]
    service.skip(first["id"])
    with pytest.raises(QueueConflict):
        service.move(first["id"], "up")
    with pytest.raises(QueueConflict):
        service.skip(first["id"])
    service.start(True)
    eventually(lambda: len(engine.launched) == 1)
    with pytest.raises(QueueConflict):
        service.skip(second["id"])
    with pytest.raises(QueueConflict):
        service.move(second["id"], "down")


def test_missing_run_and_interrupted_claim_never_count_as_done(queue):
    service, engine, _ = queue
    item = add(service)
    with engine.lock, service.lock:
        raw = service._find(item["id"])
        raw.update(status="running", run_id=None)
        service._save(raw)
    assert service.get(item["id"])["status"] == "blocked"
    with pytest.raises(QueueConflict):
        service.start(True)


def test_shutdown_revokes_late_preparation_and_store_can_close(queue):
    service, engine, store = queue
    entered, release = threading.Event(), threading.Event()
    original_create = engine.create

    def slow_create(request):
        entered.set()
        assert release.wait(5)
        return original_create(request)

    engine.create = slow_create
    add(service)
    service.start(True)
    assert entered.wait(2)
    closer = threading.Thread(target=service.close)
    closer.start()
    eventually(lambda: service._closed)
    release.set()
    closer.join(3)
    assert not closer.is_alive()
    assert not engine.launched
    with pytest.raises(QueueConflict):
        service.list()


def test_nonisolated_request_rejected_without_creation(queue):
    service, engine, _ = queue
    with pytest.raises(ValueError, match="изолированная"):
        add(service, isolated=False)
    assert service.list()["items"] == []
    assert not engine.created


def test_history_is_bounded_in_response_preserved_and_idempotent_in_database(queue):
    service, engine, store = queue
    client_id = uuid.uuid4()
    request = RunRequest(workspace="/local", task="Old preserved literal task")
    oldest = service.enqueue(request, client_id)
    service.skip(oldest["id"])
    for index in range(105):
        item = add(service, task=f"History {index}")
        service.skip(item["id"])
    assert len(service.list()["items"]) == 100
    assert oldest["id"] not in {item["id"] for item in service.list()["items"]}
    assert service.get(oldest["id"])["request"]["task"] == request.task
    assert service.enqueue(request, client_id)["id"] == oldest["id"]
    with pytest.raises(QueueConflict):
        service.enqueue(RunRequest(workspace="/local", task="Changed"), client_id)
    with store.lock:
        assert store.db.execute("SELECT count(*) FROM mission_queue").fetchone()[0] == 106
    for index in range(20):
        add(service, task=f"Open {index}")
    assert len(service.list()["items"]) == 120
    assert service.list()["summary"]["pending"] == 20
    assert not engine.created
