"""Read-only queue observations. Never invokes a provider or creates a worktree."""
import hashlib
import json
import shutil

from .models import RunRequest
from .storage import sanitize, now

REASONS = {
    'AUTH_REQUIRED': 'authentication_required', 'USAGE_LIMIT': 'usage_limit',
    'USER_DECISION_REQUIRED': 'user_decision', 'PAUSED': 'user_decision',
    'FAILED': 'failed_run', 'INTERRUPTED': 'interrupted_run', 'STOPPED': 'interrupted_run',
    'PERMISSION_REQUIRED': 'permission_denied',
}


def blocked_diagnostic(item, run_state):
    if item['status'] != 'blocked':
        return None
    reason = REASONS.get(run_state, item.get('reason_code') or 'unknown_outcome')
    return {'code': reason, 'run_state': run_state,
            'actions': (['open_run'] if item.get('run_id') else []) + ['inspect_workspace', 'skip'],
            'continuation': 'resolve_linked_run_or_skip_then_explicit_start',
            'automatic_retry': False}


def revision(rows):
    snapshot = [{k: row.get(k) for k in ('id', 'position', 'status', 'run_id', 'updated_at', 'request')}
                for row in rows if row['status'] in {'pending', 'running', 'blocked'}]
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def inspect(queue, item_ids, which=shutil.which):
    # Snapshot under normal lock order, then release before filesystem inspection.
    # In particular do NOT call list()/_reconcile(): these persist recovery state.
    with queue.engine.lock, queue.lock:
        queue._check()
        rows = queue._rows()
        current = revision(rows)
        active = list(queue.engine.active)
        items = [row for row in rows if row['status'] in queue.OPEN]
    expected = [row['id'] for row in items if row['status'] in {'pending', 'running'}]
    checks = []
    def check(code, ok, detail, item_id=None):
        checks.append({'code': code, 'status': 'ready' if ok else 'error',
                       'detail': sanitize(detail), 'item_id': item_id, 'provenance': 'discovered'})
    check('stale_batch', item_ids == expected, 'Queue IDs and ordering match the inspected batch.' if item_ids == expected else 'Queue changed. Refresh and inspect the current batch.')
    check('git_available', bool(which('git')), 'Git availability on local PATH; not an execution test.')
    check('blocked_mission', not any(row['status'] == 'blocked' for row in items), 'Resolve or explicitly skip blocked missions before starting.')
    check('unknown_outcome', not any(row['status'] == 'running' and row.get('run_id') not in active for row in items),
          'A claimed mission without an active worker needs recovery review; this inspection does not retry or reconcile it.')
    own = {row.get('run_id') for row in items if row['status'] == 'running'}
    check('other_run', not any(run_id not in own for run_id in active), 'An unrelated active run must finish before dispatch.')
    permissions, projects = [], []
    for item in items:
        if item['status'] not in {'pending', 'running'}:
            continue
        identity = item['id']
        try:
            request = RunRequest.model_validate(item['request'])
            check('isolation', request.isolated, 'Independent Git worktree required.', identity)
            check('permission', request.access_level != 'full-access' or request.confirmed_full_access,
                  'Full access requires recorded explicit confirmation.', identity)
            queue.engine.registry.pipeline(request.mode, request.pack, request.specialists)
            snapshot = queue.engine.workspace.snapshot(request.workspace)
            projects.append({'item_id': identity, 'head': snapshot['head'], 'dirty': snapshot['dirty'], 'provenance': 'discovered'})
            check('workspace', bool(snapshot['head']) and not snapshot['dirty'],
                  'Committed clean Git workspace required for isolation.', identity)
            permissions.append({'item_id': identity, 'access_level': request.access_level,
                                'full_access_confirmed': request.confirmed_full_access,
                                'runtime_approvals': 'Provider may request additional permissions during execution.'})
        except PermissionError as exc:
            check('permission_denied', False, str(exc), identity)
        except (ValueError, OSError) as exc:
            check('invalid_workspace', False, str(exc), identity)
    with queue.engine.lock, queue.lock:
        check('snapshot_current', current == revision(queue._rows()), 'Queue must remain unchanged through confirmation.')
    return {'schema_version': 1, 'observed_at': now(), 'queue_revision': current,
            'item_ids': expected, 'ready': bool(expected) and all(c['status'] == 'ready' for c in checks),
            'checks': checks, 'projects': projects, 'permissions': permissions,
            'provider_verified': False, 'models_called': False,
            'limitations': ['Local observations only. Authentication, quota and model execution are not verified.',
                            'Workspace state can change after inspection; Engine validates again at dispatch.']}
