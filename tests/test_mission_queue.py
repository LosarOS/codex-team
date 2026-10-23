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


def test_project_budget_is_frozen_and_idempotent_after_policy_change(queue):
    from pathlib import Path
    from codex_team.budget_guardian import BudgetGuardian
    service, engine, store = queue
    store.save_project({'id':'budget-project','path':str(Path('/local').resolve()),'name':'Budget'})
    guardian=BudgetGuardian(store)
    guardian.set_project_policy('budget-project', {'max_agent_calls':30,'max_total_tokens':1000})
    request=RunRequest(workspace='/local',task='Frozen policy')
    key=uuid.uuid4();item=service.enqueue(request,key)
    assert item['max_agent_calls']==30 and item['max_total_tokens']==1000
    guardian.set_project_policy('budget-project', {'max_agent_calls':90,'max_total_tokens':9000})
    assert service.enqueue(request,key)['id']==item['id']
    service.start(True);eventually(lambda: len(engine.created)==1)
    assert engine.created[0].max_agent_calls==30 and engine.created[0].max_total_tokens==1000
    assert set(RunRequest.model_fields)-{'confirmed_full_access'}<=engine.created[0].model_fields_set


def test_new_tasks_and_repeated_start_do_not_extend_confirmed_batch(queue):
    service, engine, _=queue
    add(service,'Approved first');service.start(True)
    eventually(lambda: len(engine.launched)==1)
    second=add(service,'Added later, not approved to run yet')
    service.start(True)  # A duplicate start must remain idempotent.
    engine.finish();eventually(lambda: service.list()['summary']['state']!='running')
    assert len(engine.launched)==1 and service.get(second['id'])['status']=='pending'
    service.start(True,[second['id']]);eventually(lambda: len(engine.launched)==2)


def test_stale_start_snapshot_cannot_launch_changed_members_or_order(queue):
    service, engine, _=queue
    first=add(service,'First');second=add(service,'Second')
    ids=[first['id'],second['id']]
    service.move(second['id'],'up')
    with pytest.raises(QueueConflict,match='изменился'):
        service.start(True,ids)
    with pytest.raises(QueueConflict,match='изменился'):
        service.start(True,[second['id']])
    assert engine.created==[] and engine.launched==[]


@pytest.mark.parametrize('state,code', [
    ('AUTH_REQUIRED', 'authentication_required'), ('USAGE_LIMIT', 'usage_limit'),
    ('USER_DECISION_REQUIRED', 'user_decision'), ('FAILED', 'failed_run'),
    ('INTERRUPTED', 'interrupted_run'), ('STOPPED', 'interrupted_run'),
    ('PAUSED', 'user_decision'), ('QUEUED', 'unknown_outcome'),
])
def test_blocked_diagnostic_preserves_exact_run_state_and_no_retry(queue, state, code):
    service, engine, _ = queue
    first = add(service)
    add(service, 'Untouched following mission')
    service.start(True)
    eventually(lambda: bool(engine.launched))
    engine.finish(state)
    item = service.get(first['id'])
    assert item['diagnostic']['code'] == code
    assert item['diagnostic']['run_state'] == state
    assert item['diagnostic']['automatic_retry'] is False
    assert item['diagnostic']['actions'] == ['open_run', 'inspect_workspace', 'skip']
    assert service.list()['items'][1]['status'] == 'pending'


def test_preflight_is_readonly_and_does_not_reconcile_unknown_outcome(queue):
    service, engine, store = queue
    first = add(service)
    row = service._find(first['id'])
    row.update(status='running', run_id='missing-run')
    service._save(row)
    engine.workspace.snapshot = lambda _: {'head': 'a' * 40, 'dirty': False}
    before = store.db.execute('SELECT data FROM mission_queue').fetchall()
    report = service.preflight([first['id']])
    assert report['models_called'] is False and report['provider_verified'] is False
    assert not report['ready']
    assert store.db.execute('SELECT data FROM mission_queue').fetchall() == before
    assert not engine.created and not engine.launched


def test_preflight_reports_stale_dirty_and_missing_git(queue, monkeypatch):
    from codex_team.queue_diagnostics import inspect
    service, engine, _ = queue
    first = add(service)
    engine.workspace.snapshot = lambda _: {'head': 'a' * 40, 'dirty': True}
    report = inspect(service, [], which=lambda _: None)
    assert not report['ready']
    errors = {c['code'] for c in report['checks'] if c['status'] == 'error'}
    assert {'stale_batch', 'workspace', 'git_available'} <= errors
    assert report['item_ids'] == [first['id']]


@pytest.mark.parametrize('error,code', [(PermissionError('denied'), 'permission_denied'), (ValueError('missing'), 'invalid_workspace')])
def test_preflight_handles_project_errors_without_dispatch(queue, error, code):
    service, engine, _ = queue
    item = add(service)
    def fail(_):
        raise error
    engine.workspace.snapshot = fail
    report = service.preflight([item['id']])
    assert not report['ready']
    assert any(c['code'] == code and c['item_id'] == item['id'] for c in report['checks'])
    assert not engine.created


def test_preflight_revision_rejects_change_between_inspection_and_start(queue):
    service, engine, _ = queue
    first = add(service)
    engine.workspace.snapshot = lambda _: {'head': 'a' * 40, 'dirty': False}
    report = service.preflight([first['id']])
    assert report['ready']
    second = add(service, 'Added after review')
    with pytest.raises(QueueConflict, match='Пакет изменился'):
        service.start(True, [first['id'], second['id']], report['queue_revision'])
    assert not engine.created


def test_move_is_atomic_when_second_database_update_fails(queue):
    service, _, store = queue
    first, second = add(service, 'First'), add(service, 'Second')
    before = [(i['id'], i['position']) for i in service.list()['items']]
    # Fail on the second row of the swap; SQLite must roll back the first.
    store.db.execute("CREATE TRIGGER reject_swap BEFORE UPDATE ON mission_queue WHEN NEW.id='" + first['id'] + "' BEGIN SELECT RAISE(ABORT,'test injected failure'); END")
    store.db.commit()
    import sqlite3
    with pytest.raises(sqlite3.IntegrityError, match='test injected failure'):
        service.move(second['id'], 'up')
    assert [(i['id'], i['position']) for i in service.list()['items']] == before
